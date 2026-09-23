"""The escape room on the night: the GM console and the in-app phone
(§9 rules 16, 21-22).

A game's clock lives in `game_sessions`, one row per slot, created the first
time the GM touches that game. Every figure the console or the Mini App shows
(elapsed, remaining, when the phone relocks) is worked out here from that row
and the server's clock, never on a device.

The phone opens for one person when they have a booking in this game and the
clock has reached their booked time, and for `phone_minutes` after it (§9 r21).
That is the whole rule: nobody allows anything, check-in does not gate it, and
there is no switch anywhere that can have been left off. The one thing that
closes it early is the game master's lock, which exists for the night
something goes wrong and is never set otherwise. `phone_always_handles` lets
named Telegram accounts open it at any time, for testing.

Everyone in the game gets it (22 Sep, STATE.md 130). The way in is a bot
message sent the moment the phone opens, and a button on the escape screen
that appears only while the phone is genuinely open to that person.

Nobody starts a game either (23 Sep). The booked time starts it and the slot
is the fact; what a game master has instead is Pause, a minute either way, and
End — and pausing moves the phone's window with it, so sorting something out
never costs a group their phone.
"""

import json
import re
import secrets
from datetime import datetime, timedelta, timezone

import config
import db
from services import bookings, claims, notify
from services.claims import ClaimError

ClaimError.STATUS.update({
    "PHONE_LOCKED": 403, "PHONE_OFF": 403,
    "NOT_YET": 403, "RELOCKED": 403, "NO_BOOKING": 403, "GAME_STATE": 409,
})

EXTEND_SECONDS = 60
ACTIONS = {
    # No Start (23 Sep). The booked time starts the game; a press was one more
    # thing to remember, and forgetting it held up the room. Pause is the
    # adjustment for when something happens, and it moves the phone's window
    # with it so pausing never costs a group their phone.
    "pause": "Game paused", "resume": "Game resumed",
    "extend": "Game extended by a minute", "shorten": "Game shortened by a minute",
    "end": "Game ended",
    # The emergency lock, and undoing it. Neither is needed for the phone to
    # work: the booked time is what opens it, and nothing shuts it early
    # unless a game master reaches for this.
    "lock": "Phone locked", "unlock": "Phone lock lifted",
}


def _iso(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _dt(iso):
    return datetime.fromisoformat(iso) if iso else None


def _local(dt):
    return claims.local_iso(_iso(dt)) if dt else None


def script():
    """(hints, reset checklist) from the private hint file.

    It used to be a script: cues with times against them, which turned the
    game master into someone keeping up with a schedule. It is a list now,
    and the game master gives a hint when the room needs one (23 Sep).
    """
    try:
        data = json.loads(config.GM_SCRIPT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return data.get("hints") or [], data.get("reset") or []


def _slot(conn, slot_id):
    try:
        slot_id = int(slot_id)
    except (TypeError, ValueError):
        raise ClaimError("NOT_FOUND", "No such game.")
    row = conn.execute("SELECT * FROM slots WHERE id=? AND room='escape'", (slot_id,)).fetchone()
    if row is None:
        raise ClaimError("NOT_FOUND", "No such game.")
    return row


def _session(conn, slot_id):
    return conn.execute("SELECT * FROM game_sessions WHERE slot_id=?", (slot_id,)).fetchone()


# ---------------------------------------------------------------------------
# The clock
# ---------------------------------------------------------------------------

def timing(slot, sess, settings, now):
    """Where a game is.

    Nobody starts a game any more (23 Sep). The booked time starts it: the
    slot is the fact, and a press was one more thing to remember in a dim
    room. `started` is therefore the booked time once it has come, or
    whatever `started_at` the session already holds — Pause and End stamp it,
    so a row that has been touched keeps saying what it always said.
    """
    game_seconds = int(settings["game_minutes"]) * 60 + (sess["extended_seconds"] if sess else 0)
    paused_total = sess["paused_seconds"] if sess else 0
    paused_at = _dt(sess["paused_at"]) if sess else None
    ended = _dt(sess["ended_at"]) if sess else None
    starts_at = _dt(slot["starts_at"])

    started = _dt(sess["started_at"]) if sess and sess["started_at"] else None
    if started is None and now >= starts_at:
        started = starts_at

    if started is None:
        elapsed = 0
        end = starts_at + timedelta(seconds=game_seconds)
    else:
        stop = ended or paused_at or now
        elapsed = max(0, int((stop - started).total_seconds()) - paused_total)
        if ended:
            end = ended
        elif paused_at:
            end = now + timedelta(seconds=max(0, game_seconds - elapsed))
        else:
            end = started + timedelta(seconds=game_seconds + paused_total)
    # The phone's window belongs to the booked slot: it opens at the booked
    # time and closes `phone_minutes` later. A 15-minute game inside a
    # 25-minute window already carries ten minutes of slack — but a game that
    # was paused or extended has spent some of that slack on the clock, so the
    # window follows it. Pausing to sort something out must never be the
    # reason a group loses the phone (23 Sep).
    relock_at = (starts_at + timedelta(minutes=int(settings["phone_minutes"]))
                 + timedelta(seconds=paused_total + (sess["extended_seconds"] if sess else 0)))
    return {
        "started": started, "ended": ended, "paused": paused_at is not None,
        "elapsed": elapsed, "game_seconds": game_seconds,
        "remaining": max(0, game_seconds - elapsed),
        "end": end,
        "relock_at": relock_at,
    }


def _phone_state(slot, sess, t, settings, now):
    """(open, why-not code, begun) for the game as a whole.

    Two things close the phone and that is all: the booked time not having
    come, and the window having run out. Nothing closes it by itself in
    between — no press to wait for, no switch to have left off. The third
    case is the game master reaching for the lock, which is there for the
    night something goes wrong and is never set otherwise (23 Sep).
    """
    begun = now >= _dt(slot["starts_at"])
    if not begun:
        return False, "NOT_YET", False
    if now >= t["relock_at"]:
        return False, "RELOCKED", True
    if sess and sess["phone_locked_at"]:
        return False, "PHONE_LOCKED", True
    return True, None, True


# ---------------------------------------------------------------------------
# The in-app phone (§9 r21)
# ---------------------------------------------------------------------------

def always_handles(settings):
    """The test group: Telegram handles from Settings, tidied."""
    return {h.strip().lstrip("@").lower()
            for h in str(settings.get("phone_always_handles") or "").split(",") if h.strip()}


def always_allowed(conn, attendee_id, settings=None):
    """Named accounts that may open the phone whenever they like.

    For testing the room before the doors open, so nobody has to fake the
    clock or hold a booking. Deliberately a list of handles rather than a
    switch: "everyone" would hand the solution to the queue.
    """
    settings = settings if settings is not None else db.get_settings(conn)
    wanted = always_handles(settings)
    if not wanted:
        return False
    row = conn.execute("SELECT handle FROM attendees WHERE id=?", (attendee_id,)).fetchone()
    return row is not None and (row["handle"] or "").lower() in wanted


def phone_access(conn, attendee_id, now):
    """What the Mini App's phone card shows. `code` is None when it opens."""
    settings = db.get_settings(conn)
    b = bookings.active_booking(conn, attendee_id)
    if b is None:
        # No booking is still no phone, unless this is one of the test accounts.
        if always_allowed(conn, attendee_id, settings):
            return {"code": None, "always": True}
        return {"code": "NO_BOOKING"}
    slot = _slot(conn, b["slot_id"])
    sess = _session(conn, slot["id"])
    t = timing(slot, sess, settings, now)
    out = {
        "game_starts_at": claims.local_iso(slot["starts_at"]),
        "game_ends_at": _local(t["end"]),
        "lock_at": _local(t["relock_at"]),
    }
    is_open, code, _begun = _phone_state(slot, sess, t, settings, now)
    if not is_open:
        # A test account gets in anyway, and is told that is why.
        if always_allowed(conn, attendee_id, settings):
            return dict(out, code=None, always=True)
        return dict(out, code=code)
    # Everyone in the game has the phone (22 Sep), and the booked time is the
    # whole rule (23 Sep): no half to be on, nothing to check in for.
    return dict(out, code=None)


PHONE_MESSAGES = {
    "NO_BOOKING": "Book a game first.",
    "NOT_YET": "Kai Chen's phone opens at your booked time.",
    "RELOCKED": "Time's up, so Kai Chen's phone has closed.",
    # PHONE_OFF now means one thing only, and it is a fault: the phone's file
    # is not on this laptop. It used to double as an admin switch, which is
    # what sent players to a desk that could not help them (23 Sep).
    "PHONE_OFF": "Kai Chen's phone is missing from the server. Tell the front desk.",
    "PHONE_LOCKED": "The game master has locked Kai Chen's phone for this game.",
}


# ---------------------------------------------------------------------------
# The phone arrives as a bot message (22 Sep, STATE.md 130)
# ---------------------------------------------------------------------------

def _send_phone(conn, slot, settings, now):
    """Message the phone to everyone in this game, if its phone is open.

    Once per booking — the dedupe key — so it is safe to call after every GM
    press and every few seconds from bot.py: each person gets exactly one.
    `now` may be test time; the outbox runs on the real clock, so the message
    is stamped with the real time and expires after the real time left.
    """
    sess = _session(conn, slot["id"])
    t = timing(slot, sess, settings, now)
    is_open, _, _ = _phone_state(slot, sess, t, settings, now)
    left = t["relock_at"] - now
    if not is_open or left.total_seconds() <= 0:
        return 0
    real_now = notify.utc_now()
    text = notify.text_phone(_iso(t["relock_at"]))
    added = 0
    for b in conn.execute(
            "SELECT id, attendee_id FROM escape_bookings WHERE slot_id=? "
            "AND status IN ('booked','checked_in')", (slot["id"],)).fetchall():
        added += notify.queue(conn, b["attendee_id"], "phone_open", text, go=notify.GO_PHONE,
                              dedupe_key=f"phone:{b['id']}", expires_at=real_now + left, now=real_now)
    return added


def send_phone_for_started_games(conn, now):
    """'At the booked time' mode: the clock opens the phone, so bot.py calls
    this every few seconds (through notify.schedule_due)."""
    settings = db.get_settings(conn)
    # Wide enough for pauses and extra minutes; _send_phone decides.
    since = now - timedelta(minutes=int(settings["phone_minutes"]) + 60)
    added = 0
    for sl in conn.execute(
            "SELECT * FROM slots WHERE room='escape' AND is_blocked=0 AND starts_at <= ? AND starts_at > ?",
            (_iso(now), _iso(since))).fetchall():
        added += _send_phone(conn, sl, settings, now)
    return added


def send_phone_to_testers(conn, settings=None, *, only=None, actor="system", actor_name=None):
    """Hand the phone to the test group — the one in Settings, or a subset.

    The test group needs no booking and no game: the message's button opens
    the phone for them the same way it does for a player, which is the point.
    It tests the way in, not just the phone.

    `only` narrows it to particular handles, which is what saving Settings
    passes: the people who were just added, rather than everyone on the list
    all over again.

    There is deliberately no dedupe key. `utcnow()` has only seconds in it, so
    a key built from it would silently swallow a second run in the same
    second — and running this twice in a row is exactly what testing looks
    like.

    The four lists it returns are the four things that can happen, and the
    caller has to say all of them. Until 23 Sep it returned "sent" for anybody
    on the roster, and `unreachable` was built from `can_message` alone — a
    column that starts at 1 for all 170 people. So the console said *"Sent Kai
    Chen's phone to @them"* about somebody who had never opened The Yard, and
    about everybody at all while **Who gets messages** was on testing. Both are
    the ordinary case, and neither was visible anywhere.
    """
    settings = settings if settings is not None else db.get_settings(conn)
    wanted = always_handles(settings)
    if only is not None:
        wanted &= {h.strip().lstrip("@").lower() for h in only if str(h).strip()}
    if not wanted:
        return {"sent": [], "missing": [], "unreachable": []}
    rows = conn.execute(
        f"SELECT id, name, handle, tg_user_id, can_message, is_test FROM attendees "  # noqa: S608
        f"WHERE handle IN ({','.join('?' * len(wanted))})",
        tuple(sorted(wanted))).fetchall()
    found = {r["handle"] for r in rows}
    text = notify.text_phone_test()
    # Queued for everybody found, including the ones below that will not go
    # out: the outbox is the record of what happened, and "suppressed" or
    # "skipped" against a name is worth more than no row at all.
    for r in rows:
        notify.queue(conn, r["id"], "phone_open", text, go=notify.GO_PHONE)

    # Never opened The Yard, or Telegram has refused us: there is no chat.
    unreachable = sorted(r["handle"] for r in rows if not notify.reachable(r))
    # Reachable, but "Who gets messages" will suppress it on its way out.
    held = sorted(r["handle"] for r in rows
                  if notify.reachable(r) and not notify.mode_allows(conn, r))
    going = sorted(found - set(unreachable) - set(held))
    db.audit(conn, "system", "Phone sent to the test group", actor_name=actor_name or actor,
             details={"handles": sorted(found), "going": going,
                      "held": held, "unreachable": unreachable})
    return {
        # Queued and nothing is standing in its way.
        "sent": going,
        # On the list but not on the roster: nothing can be sent until
        # somebody adds them.
        "missing": sorted(wanted - found),
        # On the roster, but they have never opened The Yard, so Telegram will
        # not let the bot message them. They must send it /start first.
        "unreachable": unreachable,
        # Reachable, but Who gets messages is on testing (or Nobody), so the
        # outbox will suppress it. The one the console never mentioned.
        "held": held,
    }


def _phone_msg(status, person):
    """What the GM sees next to each player: did the phone reach them?"""
    if status is None:
        return None                 # the phone hasn't opened for this game yet
    if status == "sent":
        return "sent"
    if status == "suppressed":
        return "held"               # Who gets messages is on testing, or Nobody
    if status in ("queued", "sending"):
        return "waiting" if notify.reachable(person) else "unreachable"
    return "unreachable"            # never opened The Yard, blocked us, or bot.py was off


# The man who found him is in the group chat, and his last message — "leaving
# now. home in 15" at 10:22 PM — is one of the three independent routes to the
# camera offset (EVIDENCE_BRIEF.md §2.1). His name is a Settings row, and the
# phone is a static file with no templating step, so the markup carries a token
# and this is where it becomes a name.
#
# Nobody has to fill the row in. Left empty he is an unsaved number, which is
# what an unnamed contact looks like on a real phone, so the thread reads
# correctly either way and Settings can be filled in on the night.
FINDER_TOKEN = "__FINDER__"
FINDER_UNSAVED = "+65 8712 3390"


def _finder_name(conn):
    """The finder as the phone should show him. Quotes and angle brackets are
    stripped because this lands inside a JavaScript string in the markup."""
    try:
        name = (db.get_setting(conn, "finder_name") or "").strip()
    except Exception:
        name = ""
    name = re.sub(r"[\"'\\<>]", "", name)[:24].strip()
    return name or FINDER_UNSAVED


def _phone_html(conn=None):
    path = config.PHONE_DIR / "the-phone.html"
    try:
        html = path.read_text(encoding="utf-8")
    except OSError:
        raise ClaimError("PHONE_OFF", "The phone file isn't deployed. Use the desk devices.")
    return html.replace(FINDER_TOKEN, _finder_name(conn) if conn is not None else FINDER_UNSAVED)


# The pictures the phone asks for by name. Since the 23 Sep rewrite
# (ESCAPE_ROOM_PLAN.md Tier B) there is exactly one: Ethan's bank screenshot,
# which carries the motive and sits inside the Messages thread with him.
#
# The four camera stills and the seventeen filler camera-roll shots are gone.
# The Photos app was removed from the phone, and the seven stills and two bin
# photographs are now printed paper at the desk, so no code knows about them.
# Keep this list in step with the phone file: tests/test_phone_links.py reads
# the real markup and fails if the two ever drift apart.
STORY_IMAGES = ("ethan-bank-screenshot.jpg",)

# The four suspects' contact photos, added 23 Sep. They are not evidence and
# nothing in the puzzle turns on them — they are there because a phone whose
# contacts are coloured circles with letters in them does not read as a real
# person's phone, and the room is asking players to believe it is one. A
# missing one falls back to the initial, so the phone is never broken by one
# not being here; that is why they are separate from STORY_IMAGES, which have
# no fallback and without which the game has no motive on it.
FACE_IMAGES = ("face-natalie.jpg", "face-ethan.jpg",
               "face-darren.jpg", "face-jasmine.jpg")
PHONE_IMAGES = STORY_IMAGES + FACE_IMAGES

# A flat grey tile, so a picture nobody has supplied yet leaves a gap in the
# gallery instead of a browser's broken-image icon. 1x1 JPEG, scaled by CSS.
MISSING_TILE = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300"
    "0806060706050806070707090908" + "0a" * 34 + "ffc00011080001000103012200"
    "021101031101ffc4001f0000010501010101010100000000000000000102030405060708090a0b"
    "ffc400b5100002010303020403050504040000017d01020300041105122131410613516107"
    "227114328191a1082342b1c11552d1f02433627282090a161718191a25262728292a3435363738"
    "393a434445464748494a535455565758595a636465666768696a737475767778797a8384858687"
    "88898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9ca"
    "d2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda000c03010002110311"
    "003f00fbfea28a2800a28a2800a28a2803ffd9")


def phone_image(conn, attendee_id, name, now):
    """One of the phone's pictures — behind the same rule as the phone itself.

    §3 rule 4 is the spoiler firewall: these *are* the evidence. Serving them
    on a looser check than the page that shows them would be a hole straight
    through it, so this runs the same `phone_access` and refuses identically.

    A picture nobody has supplied yet is answered with a plain tile rather
    than a 404, so the organiser can test the whole game before the
    photographs exist.
    """
    if name not in PHONE_IMAGES:
        raise ClaimError("NOT_FOUND", "No such picture.")
    access = phone_access(conn, attendee_id, now)
    if access["code"]:
        raise ClaimError(access["code"], PHONE_MESSAGES.get(access["code"], ""))
    return phone_image_bytes(name)


def phone_image_bytes(name):
    """The file, or the grey tile when it is not there yet."""
    path = config.PHONE_DIR / "assets" / name
    try:
        return path.read_bytes()
    except OSError:
        return MISSING_TILE


def images_present():
    """Which pictures are on the laptop — for `manage.py phone-images`."""
    here = config.PHONE_DIR / "assets"
    return {n: (here / n).exists() for n in PHONE_IMAGES}


def phone_file(conn, attendee_id, now):
    """The phone page itself, only when phone_access says so."""
    access = phone_access(conn, attendee_id, now)
    code = access["code"]
    if code:
        raise ClaimError(code, PHONE_MESSAGES.get(code, ""))
    return _phone_html(conn)


# ---------------------------------------------------------------------------
# §9 r23 — one-time links for the full-page fallback
# ---------------------------------------------------------------------------

# About a minute: long enough to tap through from Telegram to the browser,
# short enough that a link forwarded to a friend in the flat half is dead on
# arrival. It is a fallback, not a second way in.
TICKET_SECONDS = 90


def issue_phone_ticket(conn, attendee_id, now):
    """A single-use link to the phone, issued only when rule 21 already holds.

    The check is deliberately the same `phone_access` the in-app phone uses,
    so there is exactly one place that decides who may see the phone. A ticket
    is not a second permission: it is a way to carry the permission you
    already have into the browser, once.
    """
    access = phone_access(conn, attendee_id, now)
    if access["code"]:
        # The real reason, not a flattened one. The browser fallback used to
        # answer PHONE_LOCKED for "not yet" and "no booking", so the same
        # situation was described one way in the app and another through the
        # link. One rule, one vocabulary (23 Sep).
        raise ClaimError(access["code"], PHONE_MESSAGES.get(access["code"], ""))
    b = bookings.active_booking(conn, attendee_id)
    token = secrets.token_urlsafe(24)
    expires = now + timedelta(seconds=TICKET_SECONDS)
    conn.execute(
        "INSERT INTO phone_tickets (token, attendee_id, slot_id, issued_at, expires_at) "
        "VALUES (?,?,?,?,?)",
        (token, attendee_id, b["slot_id"] if b else None, now.isoformat(), expires.isoformat()))
    db.audit(conn, "attendee", "Phone link issued", entity="attendee", entity_id=attendee_id)
    # The trailing slash is not cosmetic: the phone's pictures are relative,
    # and without it the browser resolves them above the token. See app.py.
    base = (config.PUBLIC_URL or "").rstrip("/")
    return {"url": f"{base}/p/{token}/", "path": f"/p/{token}/",
            "expires_at": claims.local_iso(expires.isoformat()),
            "seconds": TICKET_SECONDS}


def redeem_phone_ticket(conn, token, now):
    """Spend a ticket and return the phone. Works exactly once.

    The spend is a conditional UPDATE rather than a read-then-write, so two
    taps arriving together cannot both win: SQLite settles it and the loser
    sees the same "already used" as anyone else.
    """
    row = conn.execute("SELECT * FROM phone_tickets WHERE token = ?", (token or "",)).fetchone()
    if row is None:
        raise ClaimError("PHONE_LOCKED", "That link isn't valid. Open the phone from The Yard.")
    if row["used_at"]:
        raise ClaimError("PHONE_LOCKED", "That link has already been used. Open the phone from The Yard.")
    if datetime.fromisoformat(row["expires_at"]) <= now:
        raise ClaimError("PHONE_LOCKED", "That link has expired. Open the phone from The Yard.")
    spent = conn.execute(
        "UPDATE phone_tickets SET used_at = ? WHERE token = ? AND used_at IS NULL",
        (now.isoformat(), token))
    if spent.rowcount != 1:
        raise ClaimError("PHONE_LOCKED", "That link has already been used. Open the phone from The Yard.")
    # Rule 21 is re-checked at the moment of use, not only at the moment of
    # issue: if the GM locked the phone or ended the game in the last minute,
    # the link must not still open it.
    access = phone_access(conn, row["attendee_id"], now)
    if access["code"]:
        # The real reason, not a flattened one. The browser fallback used to
        # answer PHONE_LOCKED for "not yet" and "no booking", so the same
        # situation was described one way in the app and another through the
        # link. One rule, one vocabulary (23 Sep).
        raise ClaimError(access["code"], PHONE_MESSAGES.get(access["code"], ""))
    db.audit(conn, "attendee", "Phone link used", entity="attendee", entity_id=row["attendee_id"])
    return _phone_html(conn)


# ---------------------------------------------------------------------------
# The GM console
# ---------------------------------------------------------------------------

def _games(conn, settings, now):
    out = []
    for n, sl in enumerate(bookings._slots(conn, "escape"), start=1):
        sess = _session(conn, sl["id"])
        t = timing(sl, sess, settings, now)
        # Four words, and the console uses these same four everywhere it
        # says what a game is doing. "Missed" is gone with Start (23 Sep):
        # nothing has to be pressed, so nothing can be missed. A game whose
        # time has come is in progress, and it says so.
        if sl["is_blocked"]:
            state = "blocked"
        elif t["ended"] or now >= t["relock_at"]:
            state = "finished"
        elif t["started"]:
            state = "in_progress"
        else:
            state = "upcoming"
        out.append({"id": sl["id"], "number": n, "starts_at": claims.local_iso(sl["starts_at"]),
                    "state": state, "booked": bookings._taken(conn, sl["id"])})
    return out


def current_game(games):
    """The game happening now, else the next one still to play, else the last."""
    for state in ("in_progress", "upcoming"):
        for gm in games:
            if gm["state"] == state:
                return gm
    return games[-1] if games else None


def _next_game_at(games, pick):
    """When the game after this one starts.

    During a changeover this is the only figure a game master wants, and
    working it out from a list of twenty-one times in a dim room is not a
    reasonable thing to ask of anybody.
    """
    after = [gm for gm in games if gm["number"] > pick["number"] and gm["state"] != "blocked"]
    return after[0]["starts_at"] if after else None


def state(conn, now, slot_id=None):
    settings = db.get_settings(conn)
    games = _games(conn, settings, now)
    if not games:
        raise ClaimError("NOT_FOUND", "No games yet. Run: python manage.py generate-slots")
    pick = next((gm for gm in games if str(gm["id"]) == str(slot_id)), None) if slot_id else None
    pick = pick or current_game(games)
    slot = _slot(conn, pick["id"])
    sess = _session(conn, slot["id"])
    t = timing(slot, sess, settings, now)
    phone_open, _, _ = _phone_state(slot, sess, t, settings, now)

    rows = conn.execute(
        "SELECT b.id AS booking_id, b.attendee_id, b.status, a.name, a.handle, a.checked_in_at, "
        "a.tg_user_id, a.can_message "
        "FROM escape_bookings b JOIN attendees a ON a.id=b.attendee_id "
        "WHERE b.slot_id=? AND b.status IN ('booked','checked_in') ORDER BY b.created_at, b.id",
        (slot["id"],)).fetchall()
    sent = {}
    if rows:
        keys = [f"phone:{r['booking_id']}" for r in rows]
        sent = {n["dedupe_key"]: n["status"] for n in conn.execute(
            f"SELECT dedupe_key, status FROM notifications WHERE dedupe_key IN ({','.join('?' * len(keys))})",  # noqa: S608
            keys)}
    # Who is in the room, in the order they booked. This replaced the halves
    # on 23 Sep: the split had nothing left to decide once everyone got the
    # phone, and what a game master actually wants at the door is the list of
    # names about to walk through it.
    people = [{
        "id": r["attendee_id"], "name": r["name"], "handle": r["handle"],
        "in": bool(r["checked_in_at"]) or r["status"] == "checked_in",
        "phone_msg": _phone_msg(sent.get(f"phone:{r['booking_id']}"), r)} for r in rows]

    hints, reset = script()
    done = {}
    if sess:
        done = {r["hint_key"]: claims.local_iso(r["sent_at"]) for r in conn.execute(
            "SELECT hint_key, sent_at FROM hint_sends WHERE session_id=?", (sess["id"],))}
    return {
        "slot_id": slot["id"], "game_number": pick["number"], "games_total": len(games),
        "games": games,
        "starts_at": claims.local_iso(slot["starts_at"]),
        "state": pick["state"],
        "started": t["started"] is not None, "paused": t["paused"], "ended": t["ended"] is not None,
        "elapsed_seconds": t["elapsed"], "game_seconds": t["game_seconds"],
        "remaining_seconds": t["remaining"],
        "ends_at": _local(t["end"]), "relock_at": _local(t["relock_at"]),
        "next_game_at": _next_game_at(games, pick),
        "phone_open": phone_open,
        "phone_locked": bool(sess and sess["phone_locked_at"]),
        "booked": len(rows), "checked_in": sum(p["in"] for p in people),
        "people": people,
        "hints": [{"key": h["key"], "title": h.get("title", ""), "line": h.get("line", ""),
                   "optional": bool(h.get("optional")),
                   "given": h["key"] in done, "given_at": done.get(h["key"])} for h in hints],
        "reset": reset,
        "changeover_minutes": int(settings["changeover_minutes"]),
        "actor_ready": bool(settings.get("actor_chat_id")),
    }


def _ensure_session(conn, slot_id):
    conn.execute("INSERT OR IGNORE INTO game_sessions (slot_id) VALUES (?)", (slot_id,))
    return _session(conn, slot_id)


def act(conn, slot_id, action, actor, now):
    """One GM button. Every press is in the audit log under the GM's name."""
    if action not in ACTIONS:
        raise ClaimError("VALIDATION_FAILED", "Unknown action.")
    settings = db.get_settings(conn)
    slot = _slot(conn, slot_id)
    stamp = _iso(now)

    def run():
        sess = _ensure_session(conn, slot["id"])
        t = timing(slot, sess, settings, now)
        sets = {}
        # The booked time is what runs a game, so "running" asks the clock,
        # not the row. The row is caught up below: the first press writes the
        # booked time into started_at, so a session anyone has touched says on
        # its own what timing() would have worked out anyway.
        running = t["started"] is not None and not sess["ended_at"]
        if running and not sess["started_at"]:
            sets = {"started_at": _iso(t["started"]), "gm_name": actor["name"]}
        if action == "pause":
            if not running or sess["paused_at"]:
                raise ClaimError("GAME_STATE", "Only a game that has begun can be paused.")
            sets["paused_at"] = stamp
        elif action == "resume":
            if not sess["paused_at"]:
                raise ClaimError("GAME_STATE", "This game isn't paused.")
            gap = int((now - _dt(sess["paused_at"])).total_seconds())
            sets.update(paused_at=None, paused_seconds=sess["paused_seconds"] + max(0, gap))
        elif action == "extend":
            if sess["ended_at"]:
                raise ClaimError("GAME_STATE", "This game has ended.")
            sets["extended_seconds"] = sess["extended_seconds"] + EXTEND_SECONDS
        elif action == "shorten":
            if sess["ended_at"]:
                raise ClaimError("GAME_STATE", "This game has ended.")
            # Never below the elapsed time: taking a minute off a game that
            # has already run longer than that would end it by arithmetic.
            floor = t["elapsed"] - int(settings["game_minutes"]) * 60
            sets["extended_seconds"] = max(floor, sess["extended_seconds"] - EXTEND_SECONDS)
        elif action == "end":
            if not running:
                raise ClaimError("GAME_STATE", "Only a game that has begun can be ended.")
            # The phone is not locked here: it stays open to the end of its
            # window, so the clock running out does not cut anyone off
            # (22 Sep, STATE.md 130). Lock the phone still locks it at once.
            sets.update(ended_at=stamp, finish_seconds=t["elapsed"])
            if sess["paused_at"]:
                gap = int((now - _dt(sess["paused_at"])).total_seconds())
                sets.update(paused_at=None, paused_seconds=sess["paused_seconds"] + max(0, gap))
        elif action == "lock":
            sets["phone_locked_at"] = stamp
        elif action == "unlock":
            # Lifts the lock rather than granting anything: back to the rule.
            sets["phone_locked_at"] = None
        conn.execute(
            f"UPDATE game_sessions SET {', '.join(k + '=?' for k in sets)} WHERE id=?",  # noqa: S608
            (*sets.values(), sess["id"]))
        db.audit(conn, actor["role"], ACTIONS[action], actor_name=actor["name"], station=actor.get("station"),
                 entity="slot", entity_id=slot["id"],
                 details={"game": claims.clock(slot["starts_at"]), "booked": bookings._taken(conn, slot["id"]),
                          "before": {k: sess[k] for k in sets}, "after": sets})
        # If this press left the phone open (Start, Unlock, switching it back
        # on), everyone in the game gets it now — once each, however many
        # presses follow.
        return {"done": action, "phone_sent": _send_phone(conn, slot, settings, now)}

    return bookings._run(conn, run)


def give_hint(conn, slot_id, key, actor, now):
    """Record that a hint was given; it also goes to the actor's Telegram.

    Once per game: a hint given twice is a hint the room did not need, and
    the button says so rather than sending it again.
    """
    slot = _slot(conn, slot_id)
    hint = next((h for h in script()[0] if h["key"] == key), None)
    if hint is None:
        raise ClaimError("NOT_FOUND", "No such hint.")
    actor_chat = int(db.get_setting(conn, "actor_chat_id", 0) or 0)

    def run():
        sess = _ensure_session(conn, slot["id"])
        if conn.execute("SELECT 1 FROM hint_sends WHERE session_id=? AND hint_key=?",
                        (sess["id"], key)).fetchone():
            raise ClaimError("GAME_STATE", "That hint has already been given.")
        conn.execute("INSERT INTO hint_sends (session_id, hint_key, sent_at, sent_by) VALUES (?,?,?,?)",
                     (sess["id"], key, _iso(now), actor["name"]))
        delivered = bool(actor_chat)
        if delivered:
            conn.execute("INSERT INTO direct_messages (chat_id, text, created_at) VALUES (?,?,?)",
                         (actor_chat, f"🎭 game at {claims.clock(slot['starts_at'])}\n"
                                      f"{notify.esc(hint.get('line', ''))}",
                          _iso(now)))
        db.audit(conn, actor["role"], "Hint given", actor_name=actor["name"],
                 station=actor.get("station"), entity="slot", entity_id=slot["id"],
                 details={"hint": key, "to_actor": delivered})
        return {"to_actor": delivered}

    return bookings._run(conn, run)
