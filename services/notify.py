"""Bot messages: what we say, when, and the outbox that carries it (§11).

The web process never talks to Telegram. It calls `queue()` inside the same
transaction as the change, and bot.py calls `schedule_due()` and `deliver()`
every few seconds. A rolled-back change therefore sends nothing, a failed send
is retried, and `dedupe_key` makes every message at-most-once.

Only messages that change what someone does next, or that someone will want
to find again (a booking receipt), are sent. No message for a hand-over or a
check-in — the person is standing there.
"""

from datetime import datetime, timedelta, timezone

import config
import db
from services import claims

MODES = ("owner", "on", "off")
MAX_ATTEMPTS = 5

# Where the "Open The Yard" button lands. The Mini App reads ?go= after Start.
GO_TICKET, GO_FOOD, GO_HOME, GO_BOOKINGS = "ticket", "food", "home", "bookings"
# The escape room's phone. This message's button is one way in; the escape
# screen carries another, shown only once the phone is genuinely open (23 Sep).
GO_PHONE = "phone"
BUTTON_LABELS = {GO_PHONE: "\U0001f4f1 Open Kai Chen's phone"}


class Blocked(Exception):
    """The person blocked the bot, or never started it."""


def _iso(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def utc_now():
    return datetime.now(timezone.utc)


def queue(conn, attendee_id, kind, text, *, go=GO_HOME, dedupe_key=None,
          send_after=None, expires_at=None, now=None):
    """Add one message. Returns True if queued, False if it was a duplicate."""
    now = now or utc_now()
    cur = conn.execute(
        "INSERT OR IGNORE INTO notifications (attendee_id, kind, dedupe_key, text, button_path, "
        "created_at, send_after, expires_at) VALUES (?,?,?,?,?,?,?,?)",
        (attendee_id, kind, dedupe_key, text, go, _iso(now),
         _iso(send_after or now), _iso(expires_at) if expires_at else None))
    return cur.rowcount == 1


def who(row):
    return "@" + row["handle"] if row["handle"] else row["name"]


# ---------------------------------------------------------------------------
# The copy. One function per message, so tests and `manage.py notify-test`
# see exactly what attendees see.
# ---------------------------------------------------------------------------

def esc(value):
    """Escape anything a person supplied. Names come off a sign-up form and
    can hold & or <, which would break the whole message rather than just
    look wrong."""
    return (str(value if value is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _msg(heading, facts=(), section=None, rows=(), footer=None):
    """Every message has the same shape, because they are read on a phone,
    usually while walking.

    A heading that says what happened, the facts on their own lines right
    under it (time, place, ref), then an optional list, then one short line
    about what to do. The organiser asked for the shape on 19 Sep ("word
    vomit" was the complaint) and for the voice on 22 Sep: lower case and
    chatty, like their earlier "🔔 order #128 is ready / please collect the
    following at the bakes station:" — relaxed, but the time and the place
    still get a line each.
    """
    out = [f"<b>{heading}</b>"]
    out.extend(f"{k} {v}" for k, v in facts if v)
    if rows:
        out.append("")
        if section:
            out.append(f"{section}:")
        out.extend(rows)
    if footer:
        out.append("")
        out.append(footer)
    return "\n".join(out)


def _when(starts_utc, ends_utc=None):
    t = claims.clock(starts_utc)
    return f"{t}–{claims.clock(ends_utc)}" if ends_utc else t


def _instrument_label(key):
    return config.INSTRUMENT_LABELS.get(key, key or "")


def place(conn, room):
    """Where to go, from Settings: the escape room's gathering point, or the
    jamming studio's own name (22 Sep, STATE.md 132)."""
    key = "escape_meet" if room == "escape" else "jam_room"
    return db.get_setting(conn, key, config.DEFAULT_SETTINGS[key])


def _place(value, room):
    key = "escape_meet" if room == "escape" else "jam_room"
    return esc(value or config.DEFAULT_SETTINGS[key])


def text_booked(starts_utc, ref, friends, where=None):
    """The booker's own receipt — the one message they can find again later."""
    return _msg(
        "✅ you're booked for The Last Guest",
        [("\U0001f550", _when(starts_utc)),
         ("\U0001f4cd", _place(where, "escape")),
         ("\U0001f3ab", f"ref {esc(ref)}")],
        section="who's in",
        rows=["you"] + [esc(f) for f in friends],
        footer="come 5 mins early, we'll give you a nudge before it starts")


def text_jam_booked(starts_utc, ends_utc, ref, line_up=(), where=None):
    """The booker's receipt for the jam room.

    Names who is on what, because since 19 Sep the booking is an instrument
    rather than a seat, and "you have the bass" is the useful part.
    """
    return _msg(
        "✅ you're booked for The Jamming Studio",
        [("\U0001f550", _when(starts_utc, ends_utc)),
         ("\U0001f4cd", _place(where, "jam")),
         ("\U0001f3ab", f"ref {esc(ref)}")],
        section="line-up",
        rows=[f"{esc('@' + h)} – {_instrument_label(i)}" for h, i in line_up],
        footer="you can change the line-up in the app until 5 mins before. "
               "anyone can grab the instruments nobody's claimed")


def text_friend_added(by, starts_utc, lock_utc, where=None):
    return _msg(
        "\U0001f4c5 you're in for The Last Guest",
        [("\U0001f550", _when(starts_utc)),
         ("\U0001f4cd", _place(where, "escape")),
         ("\U0001f465", f"booked by {esc(by)}")],
        footer=f"come 5 mins early. can't make it? open your ticket and tap leave this game, "
               f"until {claims.clock(lock_utc)}")


def text_jam_friend_added(by, starts_utc, ends_utc, instrument=None, where=None):
    return _msg(
        "\U0001f3b8 you're in for The Jamming Studio",
        [("\U0001f550", _when(starts_utc, ends_utc)),
         ("\U0001f4cd", _place(where, "jam")),
         ("\U0001f3b5", _instrument_label(instrument) if instrument else None),
         ("\U0001f465", f"booked by {esc(by)}")],
        footer="can't make it? open your bookings and tap leave this slot")


def text_moved(old_utc, new_utc, where=None):
    return _msg(
        "\U0001f501 your game has moved",
        [("❌", f"was {claims.clock(old_utc)}"),
         ("✅", f"now {claims.clock(new_utc)}"),
         ("\U0001f4cd", _place(where, "escape"))],
        footer="the front desk moved it for you. come 5 mins early")


def text_friend_removed(by, starts_utc):
    return _msg(
        "❌ you've been taken off The Last Guest",
        [("\U0001f550", _when(starts_utc)),
         ("\U0001f465", f"by {esc(by)}")],
        footer="no worries, you're free to book another game")


def text_member_left(member, starts_utc):
    return _msg(
        "\U0001f6aa someone left your game",
        [("\U0001f550", _when(starts_utc)),
         ("\U0001f464", esc(member))],
        footer="there's a seat free if you want to add someone else")


def text_jam_removed(by):
    return _msg(
        "❌ you've been taken off The Jamming Studio",
        [("\U0001f465", f"by {esc(by)}")],
        footer="no worries, you're free to book a slot of your own")


def text_jam_friend_left(member, starts_utc):
    return _msg(
        "\U0001f6aa someone left your jam slot",
        [("\U0001f550", _when(starts_utc)),
         ("\U0001f464", esc(member))],
        footer="their instrument is up for grabs again. add someone, or leave it open")


def text_jam_cancelled_by_owner(by, starts_utc):
    return _msg(
        "❌ your jam slot was cancelled",
        [("\U0001f550", _when(starts_utc)),
         ("\U0001f465", f"by {esc(by)}")],
        footer="nothing's booked for you now. grab your own slot if you still want to play")


def text_reminder(starts_utc, minutes, where=None):
    return _msg(
        "⏰ The Last Guest starts soon",
        [("\U0001f550", f"{claims.clock(starts_utc)}, in {minutes} mins"),
         ("\U0001f4cd", _place(where, "escape"))],
        footer="head over now. when your time comes, kai chen's phone "
               "arrives here as a message")


def text_phone(lock_utc):
    """Sent to everyone in the game the moment its phone opens. Since 24 Sep
    the escape screen has a button too, so this no longer claims to be the
    only way in — saying so was true when the GM's Start opened the phone."""
    return _msg(
        "\U0001f4f1 kai chen's phone is open",
        [("\U0001f550", f"open until {claims.clock(lock_utc)}")],
        footer="tap below to open it")


def text_phone_test():
    """The same thing for the test group, who have no game and so no clock."""
    return _msg(
        "\U0001f4f1 kai chen's phone is open for testing",
        footer="tap below to open it. this is the tester's copy, so it does "
               "not close and it is not tied to a game")


def text_jam_reminder(starts_utc, minutes, where=None):
    """Goes to every member of the group, not only the booker: they each hold
    an instrument, so they each need telling."""
    return _msg(
        "⏰ The Jamming Studio starts soon",
        [("\U0001f550", f"{claims.clock(starts_utc)}, in {minutes} mins"),
         ("\U0001f4cd", _place(where, "jam"))],
        footer="head over now")


def text_order_ready(item, pickup):
    """The counter's one-tap call (22 Sep, decision 125). Short, because it is
    read on a lock screen by someone who has wandered off. Worded after the
    organiser's own example, without the "2x": an order is one thing."""
    label = config.ORDER_ITEM_LABELS.get(item, item)
    return (f"<b>\U0001f514 your order is ready</b>\n"
            f"please collect the following at {esc(pickup)}:\n"
            f"{config.ORDER_ITEM_EMOJI.get(item, '')} {esc(label)}".rstrip())


def _items_sentence(items):
    names = [claims.label(i).lower() for i in items]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def text_doors(opens, closes, venue):
    return _msg(
        "\U0001f39f The Yard is on today",
        [("\U0001f550", f"{opens}–{closes}"),
         ("\U0001f4cd", esc(venue))],
        footer="your pass and bookings are all in the app. see you there")


def text_last_call(items, close):
    return _msg(
        "⏳ last call for your Yard Pass",
        [("\U0001f550", f"we close at {close}"),
         ("\U0001f381", f"still to collect: {_items_sentence(items)}")],
        footer="show your pass before then")


def hhmm_text(hhmm):
    h, m = (int(x) for x in str(hhmm).split(":"))
    return f"{h % 12 or 12}:{m:02d} {'PM' if h >= 12 else 'AM'}"


# ---------------------------------------------------------------------------
# Scheduled messages (bot.py calls this every few seconds)
# ---------------------------------------------------------------------------

def event_local(hhmm):
    h, m = (int(x) for x in str(hhmm).split(":"))
    d = datetime.fromisoformat(config.EVENT_DATE)
    return datetime(d.year, d.month, d.day, h, m, tzinfo=config.TIMEZONE)


REMINDERS = (
    # (table, active statuses, kind, text, screen, room)
    ("escape_bookings", "('booked','checked_in')", "escape_reminder", text_reminder, GO_TICKET, "escape"),
    ("jam_bookings", "('confirmed')", "jam_reminder", text_jam_reminder, GO_BOOKINGS, "jam"),
)


def schedule_due(conn, now=None):
    """Queue reminders, doors-open and last-call messages that are due now.
    Safe to call as often as you like. Returns how many were queued."""
    now = now or utc_now()
    s = db.get_settings(conn)
    added = 0

    mins = int(s.get("reminder_minutes") or 10)
    window_end = _iso(now + timedelta(minutes=mins))
    for table, statuses, kind, text, go, room in REMINDERS:
        where = s.get("escape_meet" if room == "escape" else "jam_room")
        rows = conn.execute(
            f"SELECT b.id, b.attendee_id, s.starts_at FROM {table} b "  # noqa: S608 - fixed names
            "JOIN slots s ON s.id = b.slot_id "
            f"WHERE b.status IN {statuses} AND b.reminder_sent_at IS NULL "
            "AND s.starts_at <= ? AND s.starts_at > ?", (window_end, _iso(now))).fetchall()
        for r in rows:
            starts = datetime.fromisoformat(r["starts_at"])
            left = max(1, round((starts - now).total_seconds() / 60))
            conn.execute("BEGIN IMMEDIATE")
            try:
                added += queue(conn, r["attendee_id"], kind, text(r["starts_at"], left, where), go=go,
                               dedupe_key=f"{kind}:{r['id']}", expires_at=starts, now=now)
                conn.execute(f"UPDATE {table} SET reminder_sent_at=? WHERE id=?",  # noqa: S608
                             (_iso(now), r["id"]))
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise

    # The phone opens at the booked time and nothing has to be pressed for it
    # (24 Sep), so the message that carries it goes out from here, every tick.
    # Imported here because game imports this module.
    from services import game
    added += game.send_phone_for_started_games(conn, now)

    # Event-day broadcasts go out on the day, in real time, each only if its
    # own switch is on. Test time never sends them: a rehearsal must not tell
    # the whole list the doors are open. (Until 22 Sep both waited for
    # "event-day mode"; STATE.md 129.)
    local = now.astimezone(config.TIMEZONE)
    if s.get("test_clock") or local.date().isoformat() != config.EVENT_DATE:
        return added

    doors_open = event_local(s["doors_open"])
    if s.get("doors_message") and event_local(s["doors_message_at"]) <= local < doors_open:
        text = text_doors(hhmm_text(s["doors_open"]), hhmm_text(s["doors_close"]), s["venue"])
        for r in conn.execute("SELECT id FROM attendees WHERE status='active' AND tg_user_id IS NOT NULL"):
            added += queue(conn, r["id"], "doors_open", text, dedupe_key=f"doors:{r['id']}",
                           expires_at=doors_open, now=now)

    close = event_local(s["doors_close"])
    if s.get("last_call") and close - timedelta(minutes=int(s["last_call_minutes"])) <= local < close:
        # Everybody who is here and still has something on their pass. Since
        # 24 Sep "here" includes anybody who redeemed something, not only
        # somebody the desk scanned — before that, a person who walked past the
        # front desk to the pastry table got no last call for the two items
        # they had left.
        #
        # This uses `ever_seen` rather than `at_the_event`, so it is not
        # bounded by the doors. The overview needs that bound because it is
        # measuring turnout and a rehearsal would inflate it; this is a
        # message, and the two mistakes are not the same size. Pinging somebody
        # who went home is noise. Failing to tell somebody standing in the room
        # that they have a photo strip unclaimed and thirty minutes left is the
        # thing the message exists to prevent.
        for r in conn.execute(
                "SELECT a.* FROM attendees a WHERE a.status='active' "
                f"AND {claims.ever_seen('a')} "  # noqa: S608 - fixed fragment
                "AND a.tg_user_id IS NOT NULL"):
            if not claims.payment_ok(conn, r):
                continue
            open_items = [i for i, c in claims.claims_for(conn, r["id"]).items() if not c["claimed"]]
            if open_items:
                added += queue(conn, r["id"], "last_call",
                               text_last_call(open_items, hhmm_text(s["doors_close"])),
                               go=GO_FOOD, dedupe_key=f"lastcall:{r['id']}", expires_at=close, now=now)
    return added


def withdraw(conn, dedupe_key):
    """Drop a message that has not gone out yet, e.g. for a booking since
    cancelled. True if there was one to drop."""
    return conn.execute("UPDATE notifications SET status='withdrawn' WHERE dedupe_key=? AND status='queued'",
                        (dedupe_key,)).rowcount > 0


# ---------------------------------------------------------------------------
# Delivery (bot.py calls this every few seconds)
# ---------------------------------------------------------------------------

def _allowed(mode, person):
    if mode == "on":
        return True
    if mode == "owner":
        return bool(person["is_test"]) or (person["handle"] or "") in config.ALWAYS_ALLOW_HANDLES
    return False


def _finish(conn, nid, status, error=None, now=None):
    conn.execute("UPDATE notifications SET status=?, last_error=?, sent_at=? WHERE id=?",
                 (status, error, _iso(now or utc_now()) if status == "sent" else None, nid))


def deliver(conn, send, now=None, limit=20):
    """Send what is due. `send(chat_id, text, go)` raises Blocked when the
    person can't be messaged, or any other exception to retry later.
    Returns a dict of counts by outcome."""
    now = now or utc_now()
    mode = db.get_setting(conn, "notify_mode", "owner")
    counts = {}
    # A sender that died mid-send leaves 'sending' rows; try them again later.
    conn.execute("UPDATE notifications SET status='queued' WHERE status='sending' AND send_after < ?",
                 (_iso(now - timedelta(minutes=2)),))
    due = conn.execute(
        "SELECT n.*, a.tg_user_id, a.can_message, a.is_test, a.handle FROM notifications n "
        "JOIN attendees a ON a.id = n.attendee_id "
        "WHERE n.status='queued' AND n.send_after <= ? ORDER BY n.id LIMIT ?",
        (_iso(now), limit)).fetchall()
    for n in due:
        if n["expires_at"] and n["expires_at"] <= _iso(now):
            outcome = "expired"
        elif not _allowed(mode, n):
            outcome = "suppressed"
        elif not n["tg_user_id"]:
            outcome = "skipped"          # never opened The Yard: no chat to send to
        else:
            # Claim the row first, so two senders never both send it.
            if conn.execute("UPDATE notifications SET status='sending', send_after=? "
                            "WHERE id=? AND status='queued'", (_iso(now), n["id"])).rowcount != 1:
                continue
            try:
                send(n["tg_user_id"], n["text"], n["button_path"])
                outcome = "sent"
            except Blocked as exc:
                conn.execute("UPDATE attendees SET can_message=0 WHERE id=?", (n["attendee_id"],))
                _finish(conn, n["id"], "failed", f"blocked: {exc}"[:300])
                counts["failed"] = counts.get("failed", 0) + 1
                continue
            except Exception as exc:  # noqa: BLE001 - any network error is retried
                attempts = n["attempts"] + 1
                if attempts >= MAX_ATTEMPTS:
                    _finish(conn, n["id"], "failed", str(exc)[:300])
                    counts["failed"] = counts.get("failed", 0) + 1
                else:
                    conn.execute(
                        "UPDATE notifications SET status='queued', attempts=?, last_error=?, send_after=? "
                        "WHERE id=?",
                        (attempts, str(exc)[:300], _iso(now + timedelta(seconds=15 * attempts)), n["id"]))
                    counts["retry"] = counts.get("retry", 0) + 1
                continue
            conn.execute("UPDATE attendees SET can_message=1 WHERE id=? AND can_message=0",
                         (n["attendee_id"],))
        _finish(conn, n["id"], outcome, now=now)
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


def deliver_direct(conn, send, now=None, limit=20):
    """Send queued staff messages (the actor's hint lines). They ignore
    notify_mode: they go to staff, never to attendees."""
    now = now or utc_now()
    counts = {}
    for m in conn.execute("SELECT * FROM direct_messages WHERE status='queued' ORDER BY id LIMIT ?",
                          (limit,)).fetchall():
        if conn.execute("UPDATE direct_messages SET status='sending' WHERE id=? AND status='queued'",
                        (m["id"],)).rowcount != 1:
            continue
        try:
            send(m["chat_id"], m["text"], None, button=False)
            conn.execute("UPDATE direct_messages SET status='sent', sent_at=? WHERE id=?", (_iso(now), m["id"]))
            outcome = "sent"
        except Exception as exc:  # noqa: BLE001 - retried, then given up
            attempts = m["attempts"] + 1
            outcome = "failed" if attempts >= MAX_ATTEMPTS else "retry"
            conn.execute("UPDATE direct_messages SET status=?, attempts=?, last_error=? WHERE id=?",
                         ("failed" if outcome == "failed" else "queued", attempts, str(exc)[:300], m["id"]))
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


def reachable(row):
    """Whether a message to this person can arrive at all.

    Both halves matter and only one of them is obvious. `can_message` starts
    at 1 for everybody on the roster and only drops to 0 after Telegram has
    refused a send, so on its own it means "nothing has gone wrong yet",
    never "this will work". `tg_user_id` is the real test: it is set the first
    time somebody opens The Yard, and without it there is no chat to send to.
    """
    return bool(row["tg_user_id"]) and bool(row["can_message"])


def mode_allows(conn, row):
    """Whether `notify_mode` lets a message to this person out of the outbox.

    Public because a caller that says "sent" needs to know this first: on
    "owner" everything to anybody else is suppressed, and a queued message
    that will be suppressed has not been sent and never will be.
    """
    return _allowed(db.get_setting(conn, "notify_mode", "owner"), row)


# ---------------------------------------------------------------------------
# The one place that talks to Telegram for queued messages
# ---------------------------------------------------------------------------

def web_app_url(go=None):
    base = config.PUBLIC_URL + "/"
    return base + f"?go={go}" if go and go != GO_HOME else base


def open_button(go=None):
    if not config.PUBLIC_URL:
        return None
    label = BUTTON_LABELS.get(go, "Open The Yard")
    return {"inline_keyboard": [[{"text": label, "web_app": {"url": web_app_url(go)}}]]}


def bot_api_send(chat_id, text, go=None, button=True):
    """Send one message, with an Open The Yard button unless `button` is off
    (web_app buttons work in private chats, which is the only place we send)."""
    import requests
    # HTML, so a message can have a heading and labelled lines instead of a
    # paragraph somebody has to read twice on a phone. Everything that comes
    # from a person — names, handles, reasons — goes through `esc()` before
    # it reaches here, because a name with an ampersand in it would otherwise
    # break the whole message rather than just look wrong.
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
               "link_preview_options": {"is_disabled": True}}
    button = open_button(go) if button else None
    if button:
        payload["reply_markup"] = button
    r = requests.post(f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
                      json=payload, timeout=10)
    try:
        desc = r.json().get("description", "")
    except ValueError:
        desc = r.text[:200]
    if r.status_code == 403 or (r.status_code == 400 and "chat not found" in desc.lower()):
        raise Blocked(desc)
    if not r.ok:
        raise RuntimeError(f"{r.status_code} {desc}")
