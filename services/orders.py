"""Made-to-order matcha and panini, and the message that says it's ready.

STATE.md decision 125, 22 Sep. The flow starts at the order, not at the
hand-over: staff scan the pass when someone **orders** and tap what they
ordered, and it joins a waiting list. When it's made, one tap on it queues a
Telegram message. Scanning when the food is ready would not work — by then
the person has walked off, which is why they are being called at all.

These are paid extras from Loft, not pass items, so an order is not a claim.
Nothing here is once-only: two matchas are two orders. Payment status does
not matter either; they paid at the counter.

Every write leaves an audit row, which is also what makes every other signed-
in console redraw its list within a second (app.py's live channel watches the
newest audit id).
"""

from datetime import datetime, timedelta

import config
import db
from services import claims, notify
from services.bookings import _run
from services.claims import ClaimError

# A second tap on Call inside this window is taken as a double tap, not as
# "call them again", so nobody gets two identical messages a second apart.
RECALL_SECONDS = 60
# A "your matcha is ready" message that has sat unsent this long is noise.
READY_MESSAGE_MINUTES = 30
OPEN = ("waiting", "called")


def label(item):
    return config.ORDER_ITEM_LABELS.get(item, item)


def items_view():
    return [{"key": k, "label": v} for k, v, _ in config.ORDER_ITEMS]


def _get(conn, order_id):
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if row is None:
        raise ClaimError("NOT_FOUND", "No such order.")
    return row


def _message_state(conn, order_id):
    """What happened to the latest ready message for this order, in words the
    counter can act on."""
    n = conn.execute(
        "SELECT status, last_error FROM notifications WHERE dedupe_key LIKE ? ORDER BY id DESC LIMIT 1",
        (f"order_ready:{order_id}:%",)).fetchone()
    if n is None:
        return None
    return {"queued": "sending", "sending": "sending", "sent": "sent",
            "suppressed": "test_mode", "skipped": "cannot_message",
            "expired": "not_sent", "failed": "cannot_message"}.get(n["status"], n["status"])


def _view(conn, row, person=None):
    person = person or conn.execute("SELECT * FROM attendees WHERE id=?", (row["attendee_id"],)).fetchone()
    first = (person["tg_first_name"] or (person["name"] or "").split(" ")[0] or "").strip()
    return {
        "id": row["id"], "item": row["item"], "label": label(row["item"]), "status": row["status"],
        "ordered_at": claims.local_iso(row["ordered_at"]), "ordered_by": row["ordered_by"],
        "station": row["station"],
        "called_at": claims.local_iso(row["called_at"]), "called_by": row["called_by"],
        "calls": row["calls"],
        "message": _message_state(conn, row["id"]),
        "person": {"id": person["id"], "name": person["name"], "first_name": first,
                   "handle": person["handle"], "pass_code": person["pass_code"],
                   "reachable": notify.reachable(person)},
    }


def board(conn):
    """The waiting list: everything not yet collected, oldest first, and a
    count of what has been handed over, for the counter's own sense of pace."""
    rows = conn.execute(
        "SELECT * FROM orders WHERE status IN ('waiting','called') ORDER BY ordered_at, id").fetchall()
    done = conn.execute("SELECT item, COUNT(*) FROM orders WHERE status='collected' GROUP BY item").fetchall()
    return {
        "items": items_view(),
        "open": [_view(conn, r) for r in rows],
        "collected": {item: n for item, n in done},
        "test_mode": db.get_setting(conn, "notify_mode", "owner") != "on",
    }


def place(conn, *, item, actor, code=None, attendee_id=None):
    """A new order, from a scanned pass (or the person page)."""
    if item not in config.ORDER_ITEM_KEYS:
        raise ClaimError("VALIDATION_FAILED", "Only " + " or ".join(label(k) for k in config.ORDER_ITEM_KEYS) + ".")
    person = claims.find_attendee(conn, code, attendee_id)
    if person["status"] != "active":
        raise ClaimError("INACTIVE", f"{person['name']} isn't on the current list. Send them to the front desk.")
    now = db.utcnow()

    def run():
        cur = conn.execute(
            "INSERT INTO orders (attendee_id, item, status, ordered_at, ordered_by, station) "
            "VALUES (?,?,'waiting',?,?,?)",
            (person["id"], item, now, actor["name"], actor.get("station")))
        db.audit(conn, actor["role"], f"{label(item)} ordered", actor_name=actor["name"],
                 station=actor.get("station"), entity="attendee", entity_id=person["id"],
                 details={"order": cur.lastrowid, "item": item})
        return _view(conn, _get(conn, cur.lastrowid), person)

    return _run(conn, run)


def call(conn, order_id, actor, now=None):
    """It's made: message them. Tapping again later calls them again; a second
    tap inside a minute is taken as a slip and sends nothing new."""
    now = now or notify.utc_now()
    row = _get(conn, order_id)
    if row["status"] not in OPEN:
        raise ClaimError("VALIDATION_FAILED", f"That {label(row['item']).lower()} is already {row['status']}.")
    if row["called_at"]:
        last = datetime.fromisoformat(row["called_at"])
        if (now - last).total_seconds() < RECALL_SECONDS:
            return {**_view(conn, row), "repeat": True}

    def run():
        calls = row["calls"] + 1
        stamp = notify._iso(now)
        conn.execute("UPDATE orders SET status='called', called_at=?, called_by=?, calls=? WHERE id=?",
                     (stamp, actor["name"], calls, order_id))
        notify.queue(conn, row["attendee_id"], "order_ready",
                     notify.text_order_ready(row["item"],
                                             db.get_setting(conn, f"{row['item']}_pickup", "the counter")),
                     dedupe_key=f"order_ready:{order_id}:{calls}",
                     expires_at=now + timedelta(minutes=READY_MESSAGE_MINUTES), now=now)
        db.audit(conn, actor["role"], f"{label(row['item'])} ready — called" + (" again" if calls > 1 else ""),
                 actor_name=actor["name"], station=actor.get("station"), entity="attendee",
                 entity_id=row["attendee_id"], details={"order": order_id, "call": calls})
        return {**_view(conn, _get(conn, order_id)), "repeat": False}

    return _run(conn, run)


def close(conn, order_id, how, actor):
    """Handed over, or cancelled. Either takes it off the waiting list."""
    if how not in ("collected", "cancelled"):
        raise ClaimError("VALIDATION_FAILED", "Collected or cancelled.")
    row = _get(conn, order_id)
    if row["status"] not in OPEN:
        raise ClaimError("VALIDATION_FAILED", f"That {label(row['item']).lower()} is already {row['status']}.")
    now = db.utcnow()

    def run():
        conn.execute("UPDATE orders SET status=?, closed_at=?, closed_by=? WHERE id=?",
                     (how, now, actor["name"], order_id))
        db.audit(conn, actor["role"], f"{label(row['item'])} " + ("collected" if how == "collected" else "order cancelled"),
                 actor_name=actor["name"], station=actor.get("station"), entity="attendee",
                 entity_id=row["attendee_id"], details={"order": order_id})
        return _view(conn, _get(conn, order_id))

    return _run(conn, run)
