"""The pass, booth hand-over and event check-in (§9 rules 20, 24-28, 32).

Once means once (§3 rule 3). A claim is one INSERT, and the partial unique
index `claims_once` on (attendee_id, item) WHERE voided_at IS NULL is what
refuses the second one — there is deliberately no "has this been claimed?"
check before the insert, because two booths can both pass such a check in the
same second.
"""

import base64
import io
import re
import sqlite3
from datetime import datetime
from functools import lru_cache

import config
import db

ITEMS = config.ITEM_KEYS


def label(item):
    return config.ITEM_LABELS.get(item, item)


def items_view():
    """The item list both apps render from. An item that comes in kinds
    (the pastry) lists them, so the booth can ask which one went."""
    return [{"key": k, "label": v, "note": config.ITEM_NOTES.get(k, ""),
             "choices": [{"key": ck, "label": cl} for ck, cl in config.ITEM_CHOICES.get(k, ())]}
            for k, v in config.ITEMS]


def variant_label(item, variant):
    return dict(config.ITEM_CHOICES.get(item, ())).get(variant, variant)


# Two groups of four, with at most one space or hyphen between them.
_CODE_RE = re.compile(r"^([A-Z0-9]{4})[ \-]?([A-Z0-9]{4})$")


class ClaimError(Exception):
    """A refusal with a §12 error code. `extra` goes into the error envelope."""

    STATUS = {
        "NOT_A_YARD_CODE": 400, "UNKNOWN_CODE": 404, "INACTIVE": 403,
        "PAYMENT_NOT_VERIFIED": 403, "ALREADY_CLAIMED": 409, "OUT_OF_STOCK": 409,
        "FORBIDDEN": 403, "VALIDATION_FAILED": 400,
        "NOT_FOUND": 404, "DUPLICATE_TXN_REF": 409,
    }

    def __init__(self, code, message="", **extra):
        super().__init__(code)
        self.code = code
        self.message = message
        self.extra = extra

    @property
    def status(self):
        return self.STATUS.get(self.code, 400)


# ---------------------------------------------------------------------------
# Codes and the pass QR (§9 rule 20)
# ---------------------------------------------------------------------------

def parse_code(raw):
    """Turn whatever the booth sent into a stored pass code like '7K3M-Q9XT'.

    `YARD:7K3MQ9XT` (the QR payload), `7K3M-Q9XT`, `7k3m q9xt` all work.
    Anything that is not shaped like a Yard code is NOT_A_YARD_CODE; a Yard-shaped
    code that cannot exist (bad letters, wrong length after YARD:) is
    UNKNOWN_CODE, because that is almost always a typo.
    """
    s = str(raw or "").strip().upper()
    namespaced = s.startswith(config.QR_PREFIX)
    if namespaced:
        s = s[len(config.QR_PREFIX):]
    m = _CODE_RE.match(s)
    if not m:
        raise ClaimError("UNKNOWN_CODE" if namespaced else "NOT_A_YARD_CODE",
                         "That is not a Yard pass." if not namespaced
                         else "A Yard code, but nobody has it.")
    body = m.group(1) + m.group(2)
    if any(c not in config.CODE_ALPHABET for c in body):
        raise ClaimError("UNKNOWN_CODE", "A Yard code, but nobody has it.")
    return f"{body[:4]}-{body[4:]}"


def qr_payload(pass_code):
    return config.QR_PREFIX + pass_code.replace("-", "")


@lru_cache(maxsize=512)
def pass_qr_data_uri(pass_code):
    """The pass QR as a PNG data URI, so it rides inside GET /api/me instead of
    costing a request of its own (§3 rule 6)."""
    import qrcode
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=8, border=2)
    qr.add_data(qr_payload(pass_code))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def local_iso(utc_iso):
    """A stored UTC time, shown in the event timezone."""
    if not utc_iso:
        return None
    return datetime.fromisoformat(utc_iso).astimezone(config.TIMEZONE).isoformat(timespec="seconds")


def clock(utc_iso):
    """'7:14 PM' in the event timezone."""
    d = datetime.fromisoformat(utc_iso).astimezone(config.TIMEZONE)
    return f"{d.hour % 12 or 12}:{d.minute:02d} {'PM' if d.hour >= 12 else 'AM'}"


def find_attendee(conn, code=None, attendee_id=None):
    if attendee_id is not None:
        row = conn.execute("SELECT * FROM attendees WHERE id = ?", (attendee_id,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM attendees WHERE pass_code = ?",
                           (parse_code(code),)).fetchone()
    if row is None:
        raise ClaimError("UNKNOWN_CODE", "A Yard code, but nobody has it.")
    return row


def payment_ok(conn, row):
    """§9 rule 25 — verified, or submitted too when the setting relaxes it.

    Since 23 Sep the organiser can also turn the check off altogether
    (`claim_requires` = "none", STATE.md 138): with 150 receipts still
    unchecked the day before, they chose to hand over to anyone on the list
    rather than verify each one. The screenshots are still on the person
    page; nothing stops an admin looking, it just isn't a gate any more.
    """
    requires = db.get_setting(conn, "claim_requires", "verified")
    if requires == "none":
        return True
    allowed = {"verified"}
    if requires == "submitted":
        allowed.add("submitted")
    return row["payment_status"] in allowed


def _claim_view(r):
    return {"claimed": True, "id": r["id"], "at": local_iso(r["claimed_at"]),
            "staff": r["staff_name"], "station": r["station"], "variant": r["variant"],
            "variant_label": variant_label(r["item"], r["variant"]) if r["variant"] else None}


def active_claim(conn, attendee_id, item):
    return conn.execute(
        "SELECT * FROM claims WHERE attendee_id=? AND item=? AND voided_at IS NULL",
        (attendee_id, item),
    ).fetchone()


def claims_for(conn, attendee_id):
    out = {item: {"claimed": False} for item in ITEMS}
    for r in conn.execute(
        "SELECT * FROM claims WHERE attendee_id=? AND voided_at IS NULL", (attendee_id,)
    ):
        if r["item"] in out:
            out[r["item"]] = _claim_view(r)
    return out


def stock_for(conn, item):
    """§9 rule 27. None when no stock is set for this item (0 means untracked)."""
    try:
        total = int(db.get_setting(conn, f"{item}_stock", 0) or 0)
    except (TypeError, ValueError):
        total = 0
    if total <= 0:
        return None
    used = conn.execute(
        "SELECT COUNT(*) FROM claims WHERE item=? AND voided_at IS NULL", (item,)
    ).fetchone()[0]
    left = max(0, total - used)
    try:
        low_at = int(db.get_setting(conn, "low_stock_at", config.LOW_STOCK_AT))
    except (TypeError, ValueError):
        low_at = config.LOW_STOCK_AT
    return {"total": total, "left": left, "low": left <= low_at,
            "blocks_at_zero": bool(db.get_setting(conn, "block_at_zero", False))}


def lookup(conn, code, role):
    """What the booth shows after a scan or a typed code."""
    row = find_attendee(conn, code)
    claims = claims_for(conn, row["id"])
    active = row["status"] == "active"
    paid = payment_ok(conn, row)
    open_items = [i for i in ITEMS if not claims[i]["claimed"]]
    can_hand_over = active and paid and bool(open_items)
    return {
        "code": None if active else "INACTIVE",
        "pass_code": row["pass_code"],
        "person": {
            "id": row["id"], "name": row["name"], "handle": row["handle"],
            "tg_first_name": row["tg_first_name"],
            "checked_in_at": local_iso(row["checked_in_at"]),
            "checked_in_by": row["checked_in_by"],
            "escape": None,          # app.py adds the booking
            "is_test": bool(row["is_test"]),
            # Whether a bot message can reach them — the Orders screen warns
            # the counter up front when it can't (decision 125).
            "reachable": bool(row["tg_user_id"]) and bool(row["can_message"]),
        },
        "items": items_view(),
        "payment_status": row["payment_status"],
        "payment_ok": paid,
        "claims": claims,
        "can_hand_over": can_hand_over,
        # §9 r25 — only an admin, only with a reason, only when something blocks.
        "can_override": role == "admin" and bool(open_items) and not can_hand_over,
        "stock": {item: stock_for(conn, item) for item in ITEMS},
    }


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def claim(conn, *, item, actor, code=None, attendee_id=None, variant=None,
          override_reason=None):
    """Hand over one item, once. `actor` is {'role','name','station'} from the
    signed-in console session — never from the request body.

    Returns the new claim. Raises ClaimError otherwise; ALREADY_CLAIMED carries
    the winning claim's time, staff and station (§9 rule 24).
    """
    if item not in ITEMS:
        raise ClaimError("VALIDATION_FAILED", "Unknown item: " + ", ".join(ITEMS) + " only.")
    row = find_attendee(conn, code, attendee_id)
    reason = (override_reason or "").strip()
    if reason and actor["role"] != "admin":
        raise ClaimError("FORBIDDEN", "Only an admin can override.")

    blockers = []
    if row["status"] != "active":
        blockers.append("inactive")
    if not payment_ok(conn, row):
        blockers.append("payment " + row["payment_status"])
    if blockers and not reason:
        if row["status"] != "active":
            raise ClaimError("INACTIVE", "Removed from the latest roster. Front desk decides.")
        raise ClaimError("PAYMENT_NOT_VERIFIED",
                         "Payment is not verified — you cannot hand over.",
                         payment_status=row["payment_status"])
    override = bool(blockers)

    variant = (variant or "").strip() or None
    # Which pastry went. Optional on the server (an older booth tab sends
    # none), but when one is sent it has to be a real kind.
    kinds = dict(config.ITEM_CHOICES.get(item, ()))
    if variant and variant not in kinds:
        raise ClaimError("VALIDATION_FAILED",
                         f"{label(item)} comes as: " + ", ".join(kinds.values()) + "." if kinds
                         else f"{label(item)} has no kinds to choose from.")
    now = db.utcnow()
    conn.execute("BEGIN IMMEDIATE")
    try:
        stock = stock_for(conn, item)
        if stock and stock["left"] <= 0 and stock["blocks_at_zero"]:
            raise ClaimError("OUT_OF_STOCK", f"{label(item)} is out of stock.")
        cur = conn.execute(
            "INSERT INTO claims (attendee_id, item, variant, claimed_at, staff_name, station) "
            "VALUES (?,?,?,?,?,?)",
            (row["id"], item, variant, now, actor["name"], actor.get("station")),
        )
        claim_id = cur.lastrowid
        details = {"claim_id": claim_id, "item": item, "variant": variant,
                   "pass_code": row["pass_code"], "after": {"claimed_at": now}}
        if override:
            details.update({"override": True, "reason": reason, "blocked_by": blockers})
        db.audit(conn, actor["role"],
                 f"{label(item)} handed over" + (f" ({kinds[variant]})" if variant else "")
                 + (" (admin override)" if override else ""),
                 actor_name=actor["name"], station=actor.get("station"),
                 entity="attendee", entity_id=row["id"], details=details)
        conn.execute("COMMIT")
    except sqlite3.IntegrityError:
        conn.execute("ROLLBACK")
        first = active_claim(conn, row["id"], item)
        _refused(conn, actor, row, item, first)
        view = _claim_view(first) if first else {}
        where = ", ".join(x for x in (view.get("station"), view.get("staff")) if x)
        raise ClaimError(
            "ALREADY_CLAIMED",
            f"{label(item)} already collected"
            + (f" at {clock(first['claimed_at'])}" if first else "")
            + (f" ({where})" if where else "") + ".",
            claim={"item": item, **view},
        )
    except BaseException:
        conn.execute("ROLLBACK")
        raise

    after = stock_for(conn, item)
    return {
        "id": claim_id, "item": item, "variant": variant,
        "variant_label": kinds.get(variant) if variant else None,
        "at": local_iso(now), "staff": actor["name"], "station": actor.get("station"),
        "override": override,
        "person": {"id": row["id"], "name": row["name"], "handle": row["handle"]},
        "stock": after,
    }


def _refused(conn, actor, row, item, first):
    """A lost race is worth a line in the log — it is what the front desk
    will be asked about."""
    db.audit(conn, actor["role"], f"{label(item)} hand-over refused — already collected",
             actor_name=actor["name"], station=actor.get("station"),
             entity="attendee", entity_id=row["id"],
             details={"item": item, "first_claim_id": first["id"] if first else None})


def void_claim(conn, *, attendee_id, item, reason, by):
    """§9 rule 26 — admins only, reason required, soft: the row stays."""
    reason = (reason or "").strip()
    if not reason:
        raise ClaimError("VALIDATION_FAILED", "A reason is required to void a claim.")
    first = active_claim(conn, attendee_id, item)
    if first is None:
        raise ClaimError("VALIDATION_FAILED", f"No {label(item).lower()} to void for this person.")
    now = db.utcnow()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE claims SET voided_at=?, voided_by=?, void_reason=? "
            "WHERE id=? AND voided_at IS NULL", (now, by, reason, first["id"]))
        db.audit(conn, "admin", f"{label(item)} claim voided", actor_name=by,
                 entity="attendee", entity_id=attendee_id,
                 details={"claim_id": first["id"], "reason": reason,
                          "before": {"voided_at": None}, "after": {"voided_at": now}})
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"id": first["id"], "voided_at": local_iso(now)}


def check_in(conn, *, actor, code=None, attendee_id=None, kind="event"):
    """Event check-in. Once: a second check-in reports the first one."""
    if kind != "event":
        raise ClaimError("VALIDATION_FAILED",
                         "Escape and jam check-in arrive with those bookings.")
    row = find_attendee(conn, code, attendee_id)
    if row["status"] != "active":
        raise ClaimError("INACTIVE", "Removed from the latest roster. Front desk decides.")
    by = " · ".join(x for x in (actor["name"], actor.get("station")) if x)
    now = db.utcnow()
    conn.execute("BEGIN IMMEDIATE")
    try:
        cur = conn.execute(
            "UPDATE attendees SET checked_in_at=?, checked_in_by=?, updated_at=? "
            "WHERE id=? AND checked_in_at IS NULL", (now, by, now, row["id"]))
        first_time = cur.rowcount == 1
        if first_time:
            db.audit(conn, actor["role"], "Event check-in",
                     actor_name=actor["name"], station=actor.get("station"),
                     entity="attendee", entity_id=row["id"],
                     details={"pass_code": row["pass_code"],
                              "before": {"checked_in_at": None},
                              "after": {"checked_in_at": now, "checked_in_by": by}})
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    fresh = conn.execute("SELECT checked_in_at, checked_in_by FROM attendees WHERE id=?",
                         (row["id"],)).fetchone()
    return {
        "checked_in_at": local_iso(fresh["checked_in_at"]),
        "checked_in_by": fresh["checked_in_by"],
        "already": not first_time,
        "person": {"id": row["id"], "name": row["name"], "handle": row["handle"]},
    }
