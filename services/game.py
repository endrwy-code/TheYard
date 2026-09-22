"""The escape room on the night: the GM console and the in-app phone
(§9 rules 16, 21-22).

A game's clock lives in `game_sessions`, one row per slot, created the first
time the GM touches that game. Every figure the console or the Mini App shows
(elapsed, remaining, when the phone relocks) is worked out here from that row
and the server's clock, never on a device.

The phone opens for one person when they have a booking in this game and the
clock has reached their booked time, and for `phone_minutes` after it (§9 r21).
That is the whole rule since 24 Sep: the GM no longer has to allow anything,
and check-in no longer gates it. Two things can still close it — the admin's
in-app phone switch, and the GM's emergency lock for one game — and neither is
something anybody has to press for the phone to work. `phone_always_handles`
lets named Telegram accounts open it at any time, for testing.

Since 22 Sep (STATE.md 130) that is **everyone in the game**, not only the
desk half — the halves still decide where people start — and the way in is a
bot message sent the moment the phone opens, whose button is the only link to
it. The window runs 25 minutes from the start, so the game ending (the GM's
End, or the fifteen minutes running out) does not take the phone away.
"""

import json
import secrets
from datetime import datetime, timedelta, timezone

import config
import db
from services import bookings, claims, notify
from services.claims import ClaimError

ClaimError.STATUS.update({
    "PHONE_LOCKED": 403, "PHONE_OFF": 403, "PHONE_NOT_YOUR_HALF": 403,
    "NOT_YET": 403, "RELOCKED": 403, "NO_BOOKING": 403, "GAME_STATE": 409,
})

EXTEND_SECONDS = 60
ACTIONS = {
    "start": "Game started", "pause": "Game paused", "resume": "Game resumed",
    "extend": "Game extended by a minute", "end": "Game ended",
    # The emergency lock, and undoing it. Neither is needed for the phone to
    # work: the booked time is what opens it (24 Sep).
    "lock": "Phone locked", "unlock": "Phone lock lifted",
}


def _iso(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _dt(iso):
    return datetime.fromisoformat(iso) if iso else None


def _local(dt):
    return claims.local_iso(_iso(dt)) if dt else None


def script():
    """(cues, reset checklist) from the private script file."""
    try:
        data = json.loads(config.GM_SCRIPT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return data.get("cues") or [], data.get("reset") or []


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
    """Where a game is. `started` is None until it starts (the GM's Start,
    or the scheduled time in 'clock' mode)."""
    game_seconds = int(settings["game_minutes"]) * 60 + (sess["extended_seconds"] if sess else 0)
    started = _dt(sess["started_at"]) if sess else None
    paused_total = sess["paused_seconds"] if sess else 0
    paused_at = _dt(sess["paused_at"]) if sess else None
    ended = _dt(sess["ended_at"]) if sess else None

    if started is None:
        elapsed = 0
        end = _dt(slot["starts_at"]) + timedelta(seconds=game_seconds)
    else:
        stop = ended or paused_at or now
        elapsed = max(0, int((stop - started).total_seconds()) - paused_total)
        if ended:
            end = ended
        elif paused_at:
            end = now + timedelta(seconds=max(0, game_seconds - elapsed))
        else:
            end = started + timedelta(seconds=game_seconds + paused_total)
    # The phone's window belongs to the booked slot, not to the GM's clock
    # (24 Sep): it opens at the booked time and closes `phone_minutes` later,
    # whatever Start, Pause and Extend are doing. A 15-minute game inside a
    # 25-minute window already carries ten minutes of slack.
    relock_at = _dt(slot["starts_at"]) + timedelta(minutes=int(settings["phone_minutes"]))
    return {
        "started": started, "ended": ended, "paused": paused_at is not None,
        "elapsed": elapsed, "game_seconds": game_seconds,
        "remaining": max(0, game_seconds - elapsed),
        "end": end,
        "relock_at": relock_at,
    }


def _phone_state(slot, sess, t, settings, now):
    """(open, why-not code, begun) for the game as a whole.

    `begun` is what the halves hang on: it is the booked time arriving, not
    anybody pressing anything.
    """
    begun = now >= _dt(slot["starts_at"])
    if not begun:
        return False, "NOT_YET", False
    if now >= t["relock_at"]:
        return False, "RELOCKED", True
    if not settings["in_app_phone"]:
        return False, "PHONE_OFF", True
    if sess and sess["phone_locked_at"]:
        return False, "PHONE_LOCKED", True
    return True, None, True


# ---------------------------------------------------------------------------
# The in-app phone (§9 r21)
# ---------------------------------------------------------------------------

def always_allowed(conn, attendee_id, settings=None):
    """Named accounts that may open the phone whenever they like.

    For testing the room before the doors open, so nobody has to fake the
    clock or hold a booking. Deliberately a list of handles rather than a
    switch: "everyone" would hand the solution to the queue.
    """
    settings = settings if settings is not None else db.get_settings(conn)
    wanted = {h.strip().lstrip("@").lower()
              for h in str(settings.get("phone_always_handles") or "").split(",") if h.strip()}
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
            return {"code": None, "zone": None, "always": True}
        return {"code": "NO_BOOKING", "zone": None}
    slot = _slot(conn, b["slot_id"])
    sess = _session(conn, slot["id"])
    t = timing(slot, sess, settings, now)
    out = {
        "game_starts_at": claims.local_iso(slot["starts_at"]),
        "game_ends_at": _local(t["end"]),
        "lock_at": _local(t["relock_at"]),
        "zone": None,
    }
    is_open, code, begun = _phone_state(slot, sess, t, settings, now)
    if begun:
        out["zone"] = b["zone"]         # halves are revealed once the game is on
    if not is_open:
        # A test account gets in anyway, and is told that is why.
        if always_allowed(conn, attendee_id, settings):
            return dict(out, code=None, always=True, zone=b["zone"])
        return dict(out, code=code)
    # No half check since 22 Sep: everyone in the game has the phone. No
    # check-in check since 24 Sep: the booked time is the whole rule.
    return dict(out, code=None)


PHONE_MESSAGES = {
    "NO_BOOKING": "Book a game first.",
    "NOT_YET": "The phone opens at your booked time.",
    "RELOCKED": "Time's up, so the phone is locked again.",
    "PHONE_OFF": "This game uses the handset at the desk.",
    "PHONE_LOCKED": "The game master has locked the phone for this game.",
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


def _phone_html():
    path = config.PHONE_DIR / "the-phone.html"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        raise ClaimError("PHONE_OFF", "The phone file isn't on this laptop. Use the desk devices.")


# The pictures the phone asks for by name. Four camera stills and Ryan's bank
# screenshot carry the story; filler-01..17 are the ordinary camera-roll shots
# that make the gallery look like a real phone rather than a folder of clues.
# The phone builds the filler names in JavaScript, so the list is rebuilt here
# rather than read out of the file.
STORY_IMAGES = ("cam-01-kitchen-2215.jpg", "cam-02-hallway-2220.jpg",
                "cam-03-hallway-2223.jpg", "cam-04-kitchen-2227.jpg",
                "ethan-bank-screenshot.jpg")
FILLER_IMAGES = tuple(f"filler-{n:02d}.jpg" for n in range(1, 18))
PHONE_IMAGES = STORY_IMAGES + FILLER_IMAGES

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
    return _phone_html()


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
        raise ClaimError("PHONE_LOCKED" if access["code"] in ("RELOCKED", "NO_BOOKING")
                         else access["code"], PHONE_MESSAGES.get(access["code"], ""))
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
        raise ClaimError("PHONE_LOCKED" if access["code"] in ("RELOCKED", "NO_BOOKING")
                         else access["code"], PHONE_MESSAGES.get(access["code"], ""))
    db.audit(conn, "attendee", "Phone link used", entity="attendee", entity_id=row["attendee_id"])
    return _phone_html()


# ---------------------------------------------------------------------------
# The GM console
# ---------------------------------------------------------------------------

def _games(conn, settings, now):
    out = []
    for n, sl in enumerate(bookings._slots(conn, "escape"), start=1):
        sess = _session(conn, sl["id"])
        t = timing(sl, sess, settings, now)
        if sl["is_blocked"]:
            state = "blocked"
        elif t["ended"]:
            state = "ended"
        elif t["started"]:
            state = "running"
        elif now >= t["end"] + timedelta(minutes=int(settings["changeover_minutes"])):
            state = "missed"
        else:
            state = "upcoming"
        out.append({"id": sl["id"], "number": n, "starts_at": claims.local_iso(sl["starts_at"]),
                    "state": state, "booked": bookings._taken(conn, sl["id"])})
    return out


def current_game(games):
    """The running game, else the next one still to play, else the last."""
    for state in ("running", "upcoming"):
        for gm in games:
            if gm["state"] == state:
                return gm
    return games[-1] if games else None


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
        "SELECT b.id AS booking_id, b.attendee_id, b.zone, b.status, a.name, a.handle, a.checked_in_at, "
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
    halves = {"A": [], "B": []}
    for r in rows:
        halves[r["zone"] if r["zone"] in halves else "A"].append({
            "id": r["attendee_id"], "name": r["name"], "handle": r["handle"],
            "in": bool(r["checked_in_at"]) or r["status"] == "checked_in",
            "phone_msg": _phone_msg(sent.get(f"phone:{r['booking_id']}"), r)})

    cues, reset = script()
    done = set()
    if sess:
        done = {r["hint_key"] for r in conn.execute(
            "SELECT hint_key FROM hint_sends WHERE session_id=?", (sess["id"],))}
    return {
        "slot_id": slot["id"], "game_number": pick["number"], "games_total": len(games),
        "games": games,
        "starts_at": claims.local_iso(slot["starts_at"]),
        "started": t["started"] is not None, "paused": t["paused"], "ended": t["ended"] is not None,
        "elapsed_seconds": t["elapsed"], "game_seconds": t["game_seconds"],
        "remaining_seconds": t["remaining"],
        "ends_at": _local(t["end"]), "relock_at": _local(t["relock_at"]),
        "halves_locked_at": claims.local_iso(sess["halves_locked_at"]) if sess else None,
        "phone_open": phone_open,
        "phone_locked": bool(sess and sess["phone_locked_at"]),
        "in_app_phone": bool(settings["in_app_phone"]),
        "booked": len(rows), "checked_in": sum(p["in"] for side in halves.values() for p in side),
        "halves": halves,
        "cues": [{"key": c["key"], "at": str(settings.get(c.get("time_setting"), "")),
                  "line": c.get("line", ""), "action": c.get("action", "Send"),
                  "sent": c["key"] in done} for c in cues],
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
        running = sess["started_at"] and not sess["ended_at"]
        if action == "start":
            if sess["started_at"]:
                raise ClaimError("GAME_STATE", "This game has already started.")
            sets = {"started_at": stamp, "halves_locked_at": stamp, "gm_name": actor["name"]}
        elif action == "pause":
            if not running or sess["paused_at"]:
                raise ClaimError("GAME_STATE", "Only a running game can be paused.")
            sets = {"paused_at": stamp}
        elif action == "resume":
            if not sess["paused_at"]:
                raise ClaimError("GAME_STATE", "This game isn't paused.")
            gap = int((now - _dt(sess["paused_at"])).total_seconds())
            sets = {"paused_at": None, "paused_seconds": sess["paused_seconds"] + max(0, gap)}
        elif action == "extend":
            if sess["ended_at"]:
                raise ClaimError("GAME_STATE", "This game has ended.")
            sets = {"extended_seconds": sess["extended_seconds"] + EXTEND_SECONDS}
        elif action == "end":
            if not running:
                raise ClaimError("GAME_STATE", "Only a running game can be ended.")
            # The phone is not locked here any more: it stays open to the end
            # of its window, so the clock running out does not cut anyone off
            # (22 Sep, STATE.md 130). Lock phone still locks it at once.
            sets = {"ended_at": stamp, "finish_seconds": t["elapsed"]}
            if sess["paused_at"]:
                gap = int((now - _dt(sess["paused_at"])).total_seconds())
                sets.update(paused_at=None, paused_seconds=sess["paused_seconds"] + max(0, gap))
        elif action == "lock":
            sets = {"phone_locked_at": stamp}
        elif action == "unlock":
            # Lifts the lock rather than granting anything: back to the rule.
            sets = {"phone_locked_at": None}
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


def halves(conn, slot_id, actor, *, swap_attendee_id=None, rebalance=False):
    """Swap one player's half, or even the halves out. Logged every time;
    after the game starts only gm and admin sign-ins reach this (§9 r22)."""
    slot = _slot(conn, slot_id)
    sess = _session(conn, slot["id"])
    locked = bool(sess and sess["halves_locked_at"])

    def run():
        rows = conn.execute(
            "SELECT b.id, b.attendee_id, b.zone, a.handle FROM escape_bookings b "
            "JOIN attendees a ON a.id=b.attendee_id "
            "WHERE b.slot_id=? AND b.status IN ('booked','checked_in') ORDER BY b.created_at, b.id",
            (slot["id"],)).fetchall()
        moved = []
        if rebalance:
            # Use the same rule the booking side uses, so the GM's button and
            # the automatic split cannot disagree: friends who booked together
            # stay together where the game can still be played from both
            # rooms (organiser's instruction, 18 Sep). Doing this by hand here
            # once meant "even out the halves" quietly undid the grouping.
            before = {r["id"]: r["zone"] for r in rows}
            bookings._assign_halves(conn, slot["id"], force=True)
            for r in rows:
                now_zone = conn.execute("SELECT zone FROM escape_bookings WHERE id=?",
                                        (r["id"],)).fetchone()["zone"]
                if now_zone != before[r["id"]]:
                    conn.execute("UPDATE escape_bookings SET zone_changed_by=? WHERE id=?",
                                 (actor["name"], r["id"]))
                    moved.append({"handle": r["handle"], "to": now_zone})
            action = "Halves re-balanced"
        else:
            try:
                target = int(swap_attendee_id)
            except (TypeError, ValueError):
                raise ClaimError("VALIDATION_FAILED", "Pick a player.")
            r = next((x for x in rows if x["attendee_id"] == target), None)
            if r is None:
                raise ClaimError("NOT_FOUND", "That player isn't in this game.")
            to = "A" if r["zone"] == "B" else "B"
            conn.execute("UPDATE escape_bookings SET zone=?, zone_changed_by=? WHERE id=?",
                         (to, actor["name"], r["id"]))
            moved.append({"handle": r["handle"], "from": r["zone"], "to": to})
            action = "Half swapped"
        db.audit(conn, actor["role"], action, actor_name=actor["name"], station=actor.get("station"),
                 entity="slot", entity_id=slot["id"],
                 details={"game": claims.clock(slot["starts_at"]), "moved": moved, "after_start": locked})
        return {"moved": moved}

    return bookings._run(conn, run)


def send_cue(conn, slot_id, key, actor, now):
    """Mark a script cue done; hint lines also go to the actor's Telegram."""
    slot = _slot(conn, slot_id)
    cue = next((c for c in script()[0] if c["key"] == key), None)
    if cue is None:
        raise ClaimError("NOT_FOUND", "No such cue in the script.")
    actor_chat = int(db.get_setting(conn, "actor_chat_id", 0) or 0)
    wants_actor = cue.get("action", "Send") == "Send"

    def run():
        sess = _ensure_session(conn, slot["id"])
        if conn.execute("SELECT 1 FROM hint_sends WHERE session_id=? AND hint_key=?",
                        (sess["id"], key)).fetchone():
            raise ClaimError("GAME_STATE", "Already done for this game.")
        conn.execute("INSERT INTO hint_sends (session_id, hint_key, sent_at, sent_by) VALUES (?,?,?,?)",
                     (sess["id"], key, _iso(now), actor["name"]))
        delivered = bool(wants_actor and actor_chat)
        if delivered:
            conn.execute("INSERT INTO direct_messages (chat_id, text, created_at) VALUES (?,?,?)",
                         (actor_chat, f"🎭 game at {claims.clock(slot['starts_at'])}\n"
                                      f"{notify.esc(cue.get('line', ''))}",
                          _iso(now)))
        db.audit(conn, actor["role"], "Hint sent" if wants_actor else "Forced merge called",
                 actor_name=actor["name"], station=actor.get("station"), entity="slot",
                 entity_id=slot["id"], details={"cue": key, "to_actor": delivered})
        return {"to_actor": delivered}

    return bookings._run(conn, run)
