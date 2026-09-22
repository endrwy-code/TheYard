"""The Yard — web process.

Serves the Mini App at /, the staff console at /admin, and the JSON API.
Every response carries server_time, because the server is the only clock
(§9 rule 34).
"""

import hmac
import json
import logging
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

from flask import (Flask, Response, g, jsonify, render_template, request,
                   send_file, session)
from werkzeug.exceptions import HTTPException

import auth
import config
import db
from services import admin as console
from services import (bookings, claims, export, game, notify, orders, paperform, people,
                      prices, receipts)

# The app.py window is the only place the organiser can see a crash, and the
# RUNBOOK sends them there by name. Without this, a bare logger prints an
# unlabelled traceback with no time on it, which is hard to match against
# "it broke at about ten past". Timestamps are local, to match their watch.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("yard")

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY or "dev-only-not-for-the-event"

# How long a phone opened through a one-time link may keep fetching its own
# pictures. Longer than a game, so the pictures do not vanish mid-play; short
# enough that the browser cannot be handed to someone else afterwards.
PHONE_ASSET_MINUTES = 25

# §9 rule 33 — the console cookie carries only a random session id.
app.config.update(
    SESSION_COOKIE_NAME="yard_console",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=config.CONSOLE_SESSION_HOURS),
)

# At import, not in __main__ — waitress-serve never runs __main__ (RUNBOOK 16).
config.ensure_dirs()
db.init_db()


def _backup_loop():
    """§9 r36 — a copy every `backup_minutes`, as long as the web app runs."""
    while True:
        time.sleep(60)
        try:
            conn = db.connect()
            try:
                if console.backup_due(conn):
                    db.backup_now(keep=int(db.get_setting(conn, "backup_keep", 36)))
            finally:
                conn.close()
        except Exception:  # noqa: BLE001 - a failed copy must not stop the next one
            log.exception("automatic backup failed")


if os.environ.get("YARD_AUTO_BACKUP", "1") == "1":
    threading.Thread(target=_backup_loop, name="backups", daemon=True).start()

# Keep the name and the import path the project already used.
verify_telegram_data = auth.verify_telegram_data


# ---------------------------------------------------------------------------
# Envelopes (§12)
# ---------------------------------------------------------------------------

def server_time():
    """Now, in the event timezone. The test clock shifts it for testing only."""
    now = datetime.now(config.TIMEZONE)
    offset = getattr(g, "clock_offset", None)
    if offset:
        now = now + offset
    return now.isoformat(timespec="seconds")


def now_utc():
    """The server's 'now' for booking rules, test clock included."""
    now = datetime.now(timezone.utc)
    offset = getattr(g, "clock_offset", None)
    return now + offset if offset else now


def ok(data=None, status=200):
    return jsonify({"ok": True, "data": data or {}, "server_time": server_time()}), status


def fail(code, message="", status=400, **extra):
    error = {"code": code, "message": message}
    error.update({k: v for k, v in extra.items() if v is not None})
    return jsonify({"ok": False, "error": error, "server_time": server_time()}), status


ERROR_STATUS = {
    "INITDATA_INVALID": 401, "INITDATA_EXPIRED": 401,
    "NOT_ON_LIST": 403, "NO_USERNAME": 403, "LINKED_ELSEWHERE": 403,
    "GATE_CLOSED": 403, "INACTIVE": 403, "FORBIDDEN": 403,
    "RATE_LIMITED": 429, "VALIDATION_FAILED": 400,
    "SIGNED_OUT": 401, "NOT_FOUND": 404,
}

MESSAGES = {
    "INITDATA_INVALID": "We can't confirm who you are. Close The Yard and open it again from the bot.",
    "INITDATA_EXPIRED": "This session is more than a day old. Close The Yard and open it again.",
    "NOT_ON_LIST": "That is not on The Yard's sign-up list.",
    "NO_USERNAME": "Your Telegram account has no username.",
    "LINKED_ELSEWHERE": "That sign-up is already linked to another Telegram account.",
    "GATE_CLOSED": "The Yard is closed.",
    "INACTIVE": "You are not on the current sign-up list.",
    "RATE_LIMITED": "Too many tries. Wait a minute and try again.",
}


def gate_fail(code, handle=None):
    return fail(code, MESSAGES.get(code, ""), ERROR_STATUS.get(code, 400), handle=handle)


# ---------------------------------------------------------------------------
# Request plumbing
# ---------------------------------------------------------------------------

@app.before_request
def open_db():
    g.db = db.connect()
    settings = db.get_settings(g.db)
    g.settings = settings
    g.clock_offset = None
    # §9 rule 35 — Test time. The app thinks it is the event day at the
    # chosen minute, and the clock stands there until the slider moves, so a
    # rehearsal before the 24th can open games, close cutoffs and unlock the
    # phone. It used to keep today's date, which could never reach a 24 Sep
    # game (22 Sep, STATE.md 129).
    if settings.get("test_clock"):
        try:
            hh, mm = str(settings.get("test_clock_at", "19:30")).split(":")
            day = datetime.fromisoformat(config.EVENT_DATE)
            fake = datetime(day.year, day.month, day.day, int(hh), int(mm), tzinfo=config.TIMEZONE)
            g.clock_offset = fake - datetime.now(config.TIMEZONE)
        except (ValueError, TypeError):
            g.clock_offset = None


@app.teardown_request
def close_db(exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# §9 rule 33 — who may call what, decided here on the server. The console
# greys out screens too, but that is only a courtesy. Anything not listed is
# admin-only, so an endpoint added later is locked down until it is listed.
# Since 22 Sep (decision 126) there are two sign-ins: Laptop (admin) and
# Mobile. Mobile runs the booth, the orders, the game and look-ups — one phone
# PIN for all of it, the organiser's call — and nothing else.
ANY_CONSOLE = ("admin", "mobile")
ROLE_RULES = [
    ("POST", r"/admin/api/logout", ANY_CONSOLE),
    ("GET", r"/admin/api/session", ANY_CONSOLE),
    ("GET", r"/admin/api/live", ANY_CONSOLE),
    ("GET", r"/admin/api/lookup/.+", ANY_CONSOLE),
    ("POST", r"/admin/api/claims", ANY_CONSOLE),

    ("POST", r"/admin/api/checkins", ANY_CONSOLE),
    ("GET", r"/admin/api/people(/\d+)?", ANY_CONSOLE),
    ("GET", r"/admin/api/orders", ANY_CONSOLE),
    ("POST", r"/admin/api/orders(/\d+/(call|collected|cancel))?", ANY_CONSOLE),
    ("GET", r"/admin/api/gm/.+", ANY_CONSOLE),
    ("POST", r"/admin/api/gm/.+", ANY_CONSOLE),
]
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


def roles_for(method, path):
    for m, pattern, roles in ROLE_RULES:
        if m == method and re.fullmatch(pattern, path):
            return roles
    return ("admin",)


@app.before_request
def console_guard():
    g.console = None
    path = request.path
    if not path.startswith("/admin/api/") or path == "/admin/api/login":
        return None
    row = auth.load_console_session(g.db, session.get("sid"))
    if row is None:
        return fail("SIGNED_OUT", "Your sign-in has ended. Sign in again.", 401)
    if request.method not in SAFE_METHODS and not auth.csrf_ok(
            row, request.headers.get("X-CSRF-Token")):
        # The console fetches a fresh token and retries once (a reload in another tab).
        return fail("STALE_TOKEN", "This page's security token is out of date.", 403)
    if row["role"] not in roles_for(request.method, path):
        return fail("FORBIDDEN", f"Not available to a {row['role']} sign-in.", 403)
    g.console = row
    return None


def actor():
    c = g.console
    return {"role": c["role"], "name": c["name"], "station": c["station"]}


def claim_fail(exc):
    return fail(exc.code, exc.message, exc.status, **exc.extra)


@app.errorhandler(Exception)
def unhandled(exc):
    """Any crash the services did not turn into a ClaimError.

    Without this, Flask answers an API call with an HTML error page. Both
    pages read every answer as JSON, so the parse fails and the operator is
    told "Can't reach The Yard" — a network fault — when the tunnel and the
    server are both fine and the truth is a bug on this line. That cost an
    evening during the roster import on 17 Sep. Answer in JSON, say plainly
    that it is our end, and put the traceback in the app.py window where the
    RUNBOOK tells the organiser to look.
    """
    if isinstance(exc, HTTPException):
        if request.path.startswith(("/api/", "/admin/api/")):
            return fail("HTTP_ERROR", exc.description or exc.name, exc.code or 500)
        return exc.get_response()
    log.exception("unhandled error on %s %s", request.method, request.path)
    if request.path.startswith(("/api/", "/admin/api/")):
        return fail("SERVER_ERROR",
                    "Something broke on our end and nothing was saved. "
                    "The details are in the app.py window.", 500)
    raise exc


@app.errorhandler(404)
def not_found(exc):
    if request.path.startswith(("/api/", "/admin/api/")):
        return fail("NOT_FOUND", "No such endpoint.", 404)
    return exc.get_response()


@app.errorhandler(405)
def wrong_method(exc):
    if request.path.startswith(("/api/", "/admin/api/")):
        return fail("NOT_FOUND", "No such endpoint for that method.", 405)
    return exc.get_response()


def tma_user():
    """Verify initData and return the Telegram user, or raise GateError."""
    raw = auth.read_init_data(request.headers)
    if not raw:
        raise auth.GateError("INITDATA_INVALID")
    if not auth.signature_ok(raw):
        raise auth.GateError("INITDATA_INVALID")
    if not auth.init_data_age_ok(raw):
        raise auth.GateError("INITDATA_EXPIRED")
    return auth.parse_init_data(raw)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/admin")
def admin():
    # §3 rule 4: the GM script lives in private/gm and is only sent to gm and
    # admin sign-ins (GET /admin/api/gm/state), never inside the page.
    return render_template("admin.html")


@app.route("/healthz")
def healthz():
    return ok({"status": "up"})


# ---------------------------------------------------------------------------
# The gate (§12, §9 rules 1-9)
# ---------------------------------------------------------------------------

def profile_of(row):
    return {
        "first_name": row["tg_first_name"] or (row["name"] or "").split(" ")[0],
        "full_name": row["name"],
        "handle": row["handle"],
        "pass_code": row["pass_code"],
    }


def remember_write_access(conn, row, tg):
    """Telegram says whether this person lets the bot message them."""
    if tg.get("allows_write") and not row["can_message"]:
        conn.execute("UPDATE attendees SET can_message=1 WHERE id=?", (row["id"],))


def attendee_or_fail():
    """(row, None) for an allowed Mini App user, or (None, error response)."""
    try:
        tg = tma_user()
        row = auth.resolve_attendee(g.db, tg)
    except auth.GateError as exc:
        return None, gate_fail(exc.code, exc.handle)
    remember_write_access(g.db, row, tg)
    return row, None


@app.route("/api/session", methods=["POST"])
def api_session():
    """Start-screen check. Runs on every app open, and never caches 'allowed'."""
    try:
        tg = tma_user()
    except auth.GateError as exc:
        return gate_fail(exc.code)

    conn = g.db
    try:
        row = auth.resolve_attendee(conn, tg)
    except auth.GateError as exc:
        return gate_fail(exc.code, exc.handle)

    remember_write_access(conn, row, tg)
    return ok({
        "status": "allowed",
        "profile": profile_of(row),
        "payment_status": row["payment_status"],
        "event": event_info(),
    })


def event_info():
    """The event facts the Mini App prints, from Settings — never hard-coded."""
    s = g.settings
    day = datetime.fromisoformat(config.EVENT_DATE)
    return {
        "date": f"{day:%a} {day.day} {day:%b}", "venue": s["venue"], "address": s["venue_address"],
        "entry_fee": s["entry_fee"],
        "paid_extras": s["paid_extras"],
        "opens": notify.hhmm_text(s["doors_open"]), "closes": notify.hhmm_text(s["doors_close"]),
        "first_game": notify.hhmm_text(s["first_game"]), "last_game": notify.hhmm_text(s["last_game"]),
        "capacity": s["capacity"], "meeting_point": s["meeting_point"], "help_handle": s["help_handle"],
        "phone_minutes": s["phone_minutes"],
        "escape_meet": s["escape_meet"], "jam_room": s["jam_room"],
        # Whether payment is checked at all (STATE.md 138). Off, and Help
        # stops telling people to go and show it.
        "payment_required": s["claim_requires"] != "none",
        "prices": prices.parse(s["price_list"]),
        "items": claims.items_view(),
        "instruments": [{"key": k, "label": v} for k, v in config.INSTRUMENTS],
        "shots": available_shots(),
        "floorplan": floorplan_url(),
    }


def floorplan_url():
    """The venue map for the Floorplan screen (22 Sep, STATE.md 132), with the
    same `?v=` as the photographs so a replaced map shows at once."""
    path = config.BASE_DIR / "static" / "floorplan.png"
    return f"/static/floorplan.png?v={int(path.stat().st_mtime)}" if path.exists() else None


# Photographs the Mini App puts at the top of a screen. The page renders one
# only if the file is actually on the laptop, so a missing photograph leaves
# no gap and no broken image — the screen simply reads as it did before.
SHOT_NAMES = ("home", "pass", "esc", "jam", "help")


def available_shots():
    """`?v=` is the file's modified time, so replacing a photograph under the
    same name shows the new one at once instead of whatever Telegram's
    browser kept from last time."""
    found = {}
    for name in SHOT_NAMES:
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            path = config.SHOTS_DIR / f"{name}{ext}"
            if path.exists():
                found[name] = f"/static/shots/{name}{ext}?v={int(path.stat().st_mtime)}"
                break
    return found


@app.route("/api/session/claimed-handle", methods=["POST"])
def api_claimed_handle():
    """"I signed up with a different username." Never admits anyone by itself."""
    try:
        tg = tma_user()
    except auth.GateError as exc:
        return gate_fail(exc.code)

    body = request.get_json(silent=True) or {}
    claimed = auth.normalise_handle(body.get("claimed_handle"))
    if not claimed:
        return fail("VALIDATION_FAILED", "Type the username you signed up with.", 400)

    conn = g.db
    if not auth.claimed_handle_allowed(conn, tg):
        return fail("RATE_LIMITED", MESSAGES["RATE_LIMITED"], 429)

    auth.record_attempt(conn, tg, "CLAIMED_HANDLE", claimed_handle=claimed)
    db.audit(conn, "attendee", "Claimed a different username",
             actor_name=tg.get("username") or str(tg.get("user_id")),
             entity="gate_attempt", entity_id=claimed,
             details={"tg_user_id": tg.get("user_id"), "claimed": claimed})
    return ok({"sent": True})


# ---------------------------------------------------------------------------
# The pass (§12 GET /api/me)
# ---------------------------------------------------------------------------

@app.route("/api/me")
def api_me():
    """Home, the pass, claims and payment status. The gate runs again here —
    every API call, not only the Start screen (§3 rule 1)."""
    row, error = attendee_or_fail()
    if error:
        return error

    conn = g.db
    row = conn.execute("SELECT * FROM attendees WHERE id=?", (row["id"],)).fetchone()
    return ok({
        "profile": profile_of(row),
        "payment_status": row["payment_status"],
        "payment_ok": claims.payment_ok(conn, row),
        # A data URI, not an image URL: one request fewer per visit (§3 rule 6).
        "pass_qr": claims.pass_qr_data_uri(row["pass_code"]),
        "checked_in_at": claims.local_iso(row["checked_in_at"]),
        "claims": claims.claims_for(conn, row["id"]),
        "escape_booking": bookings.my_view(conn, row["id"], now_utc()),
        "jam_bookings": bookings.my_jam(conn, row["id"], now_utc()),
        "event": event_info(),
        # Whether the bot can reach this person (reminders, group changes).
        "can_message": notify.reachable(row),
    })


@app.route("/api/me/messages", methods=["POST"])
def api_allow_messages():
    """The Mini App asked Telegram for write access and the person said yes.
    If that turns out to be wrong, the first failed send turns it off again."""
    row, error = attendee_or_fail()
    if error:
        return error
    body = request.get_json(silent=True) or {}
    if body.get("allowed"):
        g.db.execute("UPDATE attendees SET can_message=1 WHERE id=?", (row["id"],))
    return ok({"can_message": bool(body.get("allowed")) and bool(row["tg_user_id"])})


# ---------------------------------------------------------------------------
# Escape-room booking and groups (§9 rules 15-16, P0.4)
# ---------------------------------------------------------------------------

def _attendee_run(fn):
    row, error = attendee_or_fail()
    if error:
        return error
    try:
        return ok(fn(row))
    except claims.ClaimError as exc:
        return claim_fail(exc)


def _handles(body, key):
    value = body.get(key) or []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise claims.ClaimError("VALIDATION_FAILED", "Send usernames as a list.")
    return [str(v) for v in value][:20]


@app.route("/api/escape/slots")
def api_escape_slots():
    return _attendee_run(lambda row: bookings.board(g.db, row["id"], now_utc()))


@app.route("/api/escape/bookings", methods=["POST"])
def api_escape_book():
    body = request.get_json(silent=True) or {}
    return _attendee_run(lambda row: bookings.book(
        g.db, row["id"], body.get("slot_id"), _handles(body, "friends"), now_utc()))


@app.route("/api/escape/group", methods=["POST"])
def api_escape_group_add():
    body = request.get_json(silent=True) or {}
    return _attendee_run(lambda row: bookings.add_friends(
        g.db, row["id"], _handles(body, "add"), now_utc()))


@app.route("/api/escape/group/<handle>", methods=["DELETE"])
def api_escape_group_remove(handle):
    return _attendee_run(lambda row: bookings.remove_friend(g.db, row["id"], handle, now_utc()))


@app.route("/api/escape/bookings/<ref>", methods=["DELETE"])
def api_escape_cancel(ref):
    return _attendee_run(lambda row: bookings.cancel(g.db, row["id"], ref, now_utc()))


@app.route("/api/jam/slots")
def api_jam_slots():
    return _attendee_run(lambda row: bookings.jam_board(g.db, row["id"], now_utc()))


@app.route("/api/jam/bookings", methods=["POST"])
def api_jam_book():
    """Take an instrument in a jam slot, and bring whoever you like (19 Sep).

    `friends` is a list of {handle, instrument}: everyone in a booking names
    the instrument they will play, because the instrument is the thing being
    claimed.
    """
    body = request.get_json(silent=True) or {}
    return _attendee_run(lambda row: bookings.book_jam(
        g.db, row["id"], body.get("slot_id"), body.get("instrument"),
        body.get("friends") or [], now_utc()))


@app.route("/api/jam/bookings/<ref>/group", methods=["POST"])
def api_jam_add_friends(ref):
    body = request.get_json(silent=True) or {}
    return _attendee_run(lambda row: bookings.add_jam_friends(
        g.db, row["id"], ref, body.get("players") or [], now_utc()))


@app.route("/api/jam/bookings/<ref>/group/<handle>", methods=["DELETE"])
def api_jam_remove_friend(ref, handle):
    return _attendee_run(lambda row: bookings.remove_jam_friend(
        g.db, row["id"], ref, handle, now_utc()))


@app.route("/api/jam/bookings/<ref>/leave", methods=["POST"])
def api_jam_leave(ref):
    """Someone who was added gives up their own seat, without cancelling the
    group around them."""
    return _attendee_run(lambda row: bookings.leave_jam(g.db, row["id"], ref, now_utc()))


@app.route("/api/jam/bookings/<ref>", methods=["DELETE"])
def api_jam_cancel(ref):
    return _attendee_run(lambda row: bookings.cancel_jam(g.db, row["id"], ref, now_utc()))


@app.route("/api/escape/phone/status")
def api_phone_status():
    return _attendee_run(lambda row: game.phone_access(g.db, row["id"], now_utc()))


def _no_store(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/api/escape/phone")
def api_phone():
    """The phone file, only while §9 r21 holds for this person."""
    row, error = attendee_or_fail()
    if error:
        return _no_store(error[0]), error[1]
    try:
        page = game.phone_file(g.db, row["id"], now_utc())
    except claims.ClaimError as exc:
        resp, status = claim_fail(exc)
        return _no_store(resp), status
    return _no_store(Response(page, mimetype="text/html"))


@app.route("/api/escape/assets/<name>")
def api_phone_image(name):
    """A picture inside the phone.

    The phone asks for these as `assets/<name>`, and it is served at
    `/api/escape/phone`, so they arrive here. Same rule as the phone itself
    (§9 r21) — these are the evidence, and §3 rule 4 says the evidence never
    reaches an attendee screen.
    """
    row, error = attendee_or_fail()
    if error:
        return _no_store(error[0]), error[1]
    try:
        body = game.phone_image(g.db, row["id"], name, now_utc())
    except claims.ClaimError as exc:
        resp, status = claim_fail(exc)
        return _no_store(resp), status
    return _no_store(Response(body, mimetype="image/jpeg"))


@app.route("/p/<token>/assets/<name>")
def phone_ticket_image(token, name):
    """The same pictures, for a phone opened through a one-time link.

    The ticket was already spent to open the page, so it cannot be checked
    again here. Redeeming one instead leaves a short-lived marker in the
    browser session, and that is what these are served against.
    """
    until = session.get("phone_assets_until")
    if not until or datetime.fromisoformat(until) <= datetime.now(timezone.utc):
        return _no_store(fail("PHONE_LOCKED", "That link has expired.", 403)[0]), 403
    if name not in game.PHONE_IMAGES:
        return _no_store(fail("NOT_FOUND", "No such picture.", 404)[0]), 404
    return _no_store(Response(game.phone_image_bytes(name), mimetype="image/jpeg"))


@app.route("/api/escape/phone/link", methods=["POST"])
def api_phone_link():
    """§9 r23 — hand out a one-time link to the full-page phone.

    Issued only when rule 21 already holds for this person, so it grants
    nothing the in-app phone would not have shown them anyway.
    """
    return _attendee_run(lambda row: game.issue_phone_ticket(g.db, row["id"], now_utc()))


@app.route("/p/<token>/")
def phone_ticket(token):
    """Spend a one-time link.

    Deliberately outside `/api/`: this opens in the phone's real browser,
    where there is no Telegram and therefore no initData to verify. The token
    is the whole credential, which is why it lasts ninety seconds, works once,
    and is re-checked against rule 21 as it is spent.

    The trailing slash matters. The phone asks for its pictures as
    `assets/<name>`, and a browser resolves that against the directory part of
    the address — so this has to look like a folder, or they would resolve to
    `/p/assets/<name>` with no token in sight. Flask redirects `/p/<token>` to
    this before the view runs, so a link without the slash still works and the
    ticket is still only spent once.
    """
    try:
        page = game.redeem_phone_ticket(g.db, token, now_utc())
    except claims.ClaimError as exc:
        resp, status = claim_fail(exc)
        return _no_store(resp), status
    # The ticket is gone now, so the pictures need their own short-lived
    # permission. One game's length, and no longer.
    session["phone_assets_until"] = (
        datetime.now(timezone.utc) + timedelta(minutes=PHONE_ASSET_MINUTES)).isoformat()
    return _no_store(Response(page, mimetype="text/html"))

# ---------------------------------------------------------------------------
# Console sign-in (§9 rule 33)
# ---------------------------------------------------------------------------

def client_key():
    """Who is knocking. Behind the tunnel every request arrives from localhost,
    so use the address the tunnel appended — the last X-Forwarded-For entry."""
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[-1].strip() if fwd else (request.remote_addr or "?")


@app.route("/admin/api/login", methods=["POST"])
def admin_login():
    if not request.is_json:
        return fail("VALIDATION_FAILED", "Send the sign-in as JSON.", 400)
    body = request.get_json(silent=True) or {}
    role = auth.normal_role(body.get("role"))
    if role not in auth.ROLES:
        return fail("VALIDATION_FAILED", "Pick Mobile or Laptop.", 400)

    secret = str(body.get("password" if role == "admin" else "pin") or "")
    name = " ".join(str(body.get("name") or "").split())[:40]
    station = " ".join(str(body.get("station") or "").split())[:40]
    if role == "admin":
        name = name or "Organiser"
        station = ""
    else:
        if not name:
            return fail("VALIDATION_FAILED", "Your name is required — it goes on every hand-over.", 400)
        if not station:
            return fail("VALIDATION_FAILED", "Say where you are — for example Booth 1, Loft or Escape room.", 400)

    who = client_key()
    if not auth.signin_allowed(role, who):
        return fail("RATE_LIMITED", "Too many tries. Wait a few minutes.", 429)
    if not auth.role_configured(role):
        key, cmd = auth.ROLE_SECRET_KEY[role]
        what = "admin password" if role == "admin" else "phone PIN"
        return fail("FORBIDDEN", f"No {what} is set on this laptop yet. Run: python manage.py {cmd}", 403)
    conn = g.db
    if not auth.check_role(role, secret):
        auth.signin_failed(role, who)
        db.audit(conn, role, "Console sign-in refused", actor_name=name, station=station or None,
                 details={"role": role})
        return fail("FORBIDDEN", "That did not match.", 403)

    auth.revoke_console_session(conn, session.get("sid"))
    created = auth.create_console_session(conn, role, name, station)
    session.clear()
    session.permanent = True
    session["sid"] = created["sid"]
    db.audit(conn, role, "Console sign-in", actor_name=name, station=station or None,
             details={"role": role, "expires_at": created["expires_at"]})
    return ok(console_view(role, name, station, created["csrf_token"], created["expires_at"]))


def console_view(role, name, station, csrf_token, expires_at):
    s = g.settings
    return {
        "role": role, "name": name, "station": station or "",
        "csrf_token": csrf_token,
        "expires_at": claims.local_iso(expires_at),
        "test_clock": bool(s["test_clock"]),
        "test_clock_at": s["test_clock_at"],
        "event_date": config.EVENT_DATE,
        "items": claims.items_view(),
    }


@app.route("/admin/api/session")
def admin_session():
    """A reloaded page picks its sign-in back up instead of asking again."""
    c = g.console
    return ok(console_view(c["role"], c["name"], c["station"],
                           auth.rotate_csrf(g.db, c), c["expires_at"]))


@app.route("/admin/api/logout", methods=["POST"])
def admin_logout():
    c = g.console
    auth.revoke_console_session(g.db, session.get("sid"))
    session.clear()
    db.audit(g.db, c["role"], "Console sign-out", actor_name=c["name"], station=c["station"])
    return ok({"signed_out": True})


# ---------------------------------------------------------------------------
# Booth: lookup, hand-over, check-in (§9 rules 20, 24-28)
# ---------------------------------------------------------------------------

def lookup_limit():
    """(key, limit) for this console session's lookup budget."""
    return g.console["id"], int(g.settings.get("lookup_rate_limit") or 30)


@app.route("/admin/api/lookup/<path:code>")
def admin_lookup(code):
    key, limit = lookup_limit()
    # §9 rule 28 — every lookup counts, so guessing codes is slow.
    if not auth.CODE_LOOKUPS.take(key, limit, auth.LOOKUP_WINDOW):
        return fail("RATE_LIMITED", "Slow down — too many lookups. Wait a minute.", 429)
    try:
        data = claims.lookup(g.db, code, g.console["role"])
    except claims.ClaimError as exc:
        return claim_fail(exc)
    data["person"]["escape"] = bookings.lookup_view(g.db, data["person"]["id"])
    return ok(data)


def _target(body):
    """A pass code, or an attendee id from the person page."""
    code = body.get("code")
    attendee_id = body.get("attendee_id")
    if attendee_id is not None:
        try:
            return None, int(attendee_id)
        except (TypeError, ValueError):
            raise claims.ClaimError("VALIDATION_FAILED", "attendee_id must be a number.")
    if not code:
        raise claims.ClaimError("VALIDATION_FAILED", "Scan or type a pass code first.")
    return code, None


def _guarded(fn):
    """Run a booth write; a code that resolves to nobody counts against the
    lookup limit, so the write endpoints can't be used to guess codes."""
    key, limit = lookup_limit()
    if not auth.CODE_LOOKUPS.allowed(key, limit, auth.LOOKUP_WINDOW):
        return fail("RATE_LIMITED", "Slow down — too many lookups. Wait a minute.", 429)
    try:
        return ok(fn())
    except claims.ClaimError as exc:
        if exc.code in ("UNKNOWN_CODE", "NOT_A_YARD_CODE"):
            auth.CODE_LOOKUPS.hit(key, auth.LOOKUP_WINDOW)
        return claim_fail(exc)


@app.route("/admin/api/claims", methods=["POST"])
def admin_claim():
    body = request.get_json(silent=True) or {}

    def run():
        code, attendee_id = _target(body)
        # Staff name and station come from the session, never from the body.
        return claims.claim(g.db, item=str(body.get("item") or ""), actor=actor(),
                            code=code, attendee_id=attendee_id,
                            variant=body.get("variant"),
                            override_reason=body.get("override_reason"))
    return _guarded(run)


@app.route("/admin/api/slots")
def admin_slots():
    return ok(bookings.admin_board(g.db, now_utc()))


@app.route("/admin/api/checkins", methods=["POST"])
def admin_checkin():
    body = request.get_json(silent=True) or {}

    def run():
        code, attendee_id = _target(body)
        return claims.check_in(g.db, actor=actor(), code=code, attendee_id=attendee_id,
                               kind=str(body.get("kind") or "event"))
    return _guarded(run)


# ---------------------------------------------------------------------------
# Orders: matcha and panini, and the message that says it's ready (decision 125)
# ---------------------------------------------------------------------------

@app.route("/admin/api/orders")
def admin_orders():
    return _run(lambda: orders.board(g.db))


@app.route("/admin/api/orders", methods=["POST"])
def admin_place_order():
    body = request.get_json(silent=True) or {}

    def run():
        code, attendee_id = _target(body)
        return orders.place(g.db, item=str(body.get("item") or ""), actor=actor(),
                            code=code, attendee_id=attendee_id)
    # Same guard as a hand-over, so the order button can't be used to guess codes.
    return _guarded(run)


@app.route("/admin/api/orders/<int:order_id>/<action>", methods=["POST"])
def admin_order_action(order_id, action):
    if action == "call":
        return _run(lambda: orders.call(g.db, order_id, actor()))
    if action in ("collected", "cancel"):
        how = "collected" if action == "collected" else "cancelled"
        return _run(lambda: orders.close(g.db, order_id, how, actor()))
    return fail("NOT_FOUND", "No such action.", 404)


# ---------------------------------------------------------------------------
# Search, the person page, payments, voids (§9 rules 14, 26, 30-33)
# ---------------------------------------------------------------------------

def _run(fn):
    try:
        return ok(fn())
    except claims.ClaimError as exc:
        return claim_fail(exc)
    except sqlite3.IntegrityError as exc:
        # A rule the database enforces that the service did not check first.
        # Never a network problem, and nothing was written: every writer runs
        # inside a transaction that rolls back. Name the constraint, because
        # it is the one clue that says which rule was broken.
        log.exception("integrity error on %s %s", request.method, request.path)
        return fail("CONFLICT",
                    "The database refused that change, so nothing was saved. "
                    f"({exc}) The app.py window has the details.", 409)


@app.route("/admin/api/people")
def admin_people():
    return _run(lambda: people.search(g.db, request.args.get("q", "")))


@app.route("/admin/api/people/<int:attendee_id>")
def admin_person(attendee_id):
    return _run(lambda: people.person(g.db, attendee_id, g.console["role"]))


@app.route("/admin/api/people/<int:attendee_id>/payment", methods=["POST"])
def admin_payment(attendee_id):
    body = request.get_json(silent=True) or {}
    return _run(lambda: people.set_payment(
        g.db, attendee_id, verdict=str(body.get("verdict") or ""),
        txn_ref=body.get("txn_ref"), reason=body.get("reason"), by=g.console["name"]))


@app.route("/admin/api/claims/<int:claim_id>/void", methods=["POST"])
def admin_void_claim(claim_id):
    body = request.get_json(silent=True) or {}
    return _run(lambda: people.void_claim(g.db, claim_id, reason=body.get("reason"),
                                          by=g.console["name"]))


@app.route("/admin/api/gate-attempts")
def admin_gate_attempts():
    return _run(lambda: {"attempts": people.gate_denials(g.db)})


# ---------------------------------------------------------------------------
# Live updates for the console
# ---------------------------------------------------------------------------

LIVE_TICK_SECONDS = 1.0


def _change_marker(conn):
    """Every write leaves an audit row (§9 r32), so the newest id says whether
    anything changed. The bot's sends are added for the Overview's counts."""
    return conn.execute(
        "SELECT (SELECT COALESCE(MAX(id), 0) FROM audit_log), "
        "(SELECT COUNT(*) FROM notifications WHERE status IN ('sent','failed'))").fetchone()[:]


@app.route("/admin/api/live")
def admin_live():
    """Server-sent events: one long request that says "something changed"
    within a second. It costs one request per connection instead of one per
    poll (§3 r6), and closes after a few minutes; the browser reconnects."""
    sid = session.get("sid")

    def stream():
        conn = db.connect()
        try:
            yield "retry: 3000\n\n"
            last, quiet, opened = None, 0.0, time.monotonic()
            while time.monotonic() - opened < config.LIVE_STREAM_SECONDS:
                if auth.load_console_session(conn, sid) is None:
                    yield "event: signed_out\ndata: {}\n\n"
                    return
                marker = _change_marker(conn)
                if marker != last:
                    last, quiet = marker, 0.0
                    yield f"data: {json.dumps({'v': list(marker)})}\n\n"
                elif quiet >= 15:
                    quiet = 0.0
                    yield ": still here\n\n"
                time.sleep(LIVE_TICK_SECONDS)
                quiet += LIVE_TICK_SECONDS
        finally:
            conn.close()

    resp = Response(stream(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


# ---------------------------------------------------------------------------
# Overview, Settings, Audit, backups, exports (admin)
# ---------------------------------------------------------------------------

@app.route("/admin/api/overview")
def admin_overview():
    return _run(lambda: console.overview(g.db, now_utc()))


@app.route("/admin/api/settings")
def admin_settings():
    return _run(lambda: console.settings_view(g.db))


@app.route("/admin/api/settings", methods=["PUT"])
def admin_settings_save():
    body = request.get_json(silent=True)
    return _run(lambda: console.save_settings(g.db, body, g.console["name"], now_utc()))


@app.route("/admin/api/audit")
def admin_audit():
    a = request.args
    return _run(lambda: console.audit_view(g.db, a.get("actor"), a.get("action"), a.get("search")))


@app.route("/admin/api/backup", methods=["POST"])
def admin_backup():
    return _run(lambda: console.backup(g.db, g.console["name"]))


@app.route("/admin/api/receipts/archive", methods=["POST"])
def admin_receipts_archive():
    """Take our own copy of every Paperform screenshot we can still reach.

    Slow by nature — one download per person — but it is pressed by hand,
    before the event, not on the day. Nothing is deleted and it is safe to
    press twice: anyone already copied is skipped.
    """
    body = request.get_json(silent=True) or {}
    return _run(lambda: receipts.archive(
        g.db, g.console["name"], redo=bool(body.get("redo"))))


@app.route("/admin/api/receipts/status")
def admin_receipts_status():
    return _run(lambda: receipts.status(g.db))


@app.route("/admin/api/receipts/<int:attendee_id>/file")
def admin_receipt_file(attendee_id):
    """§9 r31 — a saved receipt is served only to a signed-in admin, and the
    name on disk is random, so the URL cannot be guessed from the outside."""
    try:
        path = receipts.file_for(g.db, attendee_id)
    except claims.ClaimError as exc:
        return claim_fail(exc)
    resp = send_file(path, conditional=False)
    return _no_store(resp)


@app.route("/admin/api/export/<kind>")
def admin_export(kind):
    if kind not in export.KINDS:
        return fail("NOT_FOUND", "No such export.", 404)
    body, name, mime = export.build(g.db, kind)
    db.audit(g.db, "admin", "Export downloaded", actor_name=g.console["name"], entity="export", entity_id=kind)
    resp = Response(body, mimetype=mime)
    disposition = "inline" if kind == "fallback" else "attachment"
    resp.headers["Content-Disposition"] = f'{disposition}; filename="{name}"'
    return _no_store(resp)


# ---------------------------------------------------------------------------
# Roster, walk-ins, the gate list, unlinking (admin)
# ---------------------------------------------------------------------------

@app.route("/admin/api/roster")
def admin_roster():
    return _run(lambda: console.roster_view(g.db))


@app.route("/admin/api/roster/preview", methods=["POST"])
def admin_roster_preview():
    return _run(lambda: console.roster_preview(g.db, request.files.get("file"), g.console["name"]))


@app.route("/admin/api/roster/commit/<int:run_id>", methods=["POST"])
def admin_roster_commit(run_id):
    return _run(lambda: console.roster_commit(g.db, run_id, g.console["name"]))


# ---------------------------------------------------------------------------
# Paperform's webhook (§9 r10-14). The one public write in the app: Paperform
# calls it, not a signed-in person, so `console_guard` never sees it — it
# guards /admin/api/ only — and everything that protects it is right here.
# ---------------------------------------------------------------------------

WEBHOOK_WINDOW = 60
WEBHOOK_PER_WINDOW = 60          # a busy minute of sign-ups, and no more
WEBHOOK_MAX_BYTES = 64 * 1024
WEBHOOK_HITS = auth.RateLimiter()


@app.route("/paperform/webhook", methods=["POST"])
def paperform_webhook():
    """One sign-up, live from Paperform, into the roster.

    Open on purpose (22 Sep): the form sends no signature, so there is nothing
    to check it against. Standing in for that are the switch on the Settings
    screen, the rate limit and size cap below, and an audit row for every
    arrival — accepted or refused — so anything odd is visible on the night.
    Fill in PAPERFORM_WEBHOOK_SECRET and it is enforced as well.
    """
    if not g.settings.get("paperform_webhook", True):
        # Switched off deliberately. 2xx, or Paperform retries it all day.
        return ok({"ignored": "The Paperform webhook is switched off."})
    secret = config.PAPERFORM_WEBHOOK_SECRET
    if secret and not hmac.compare_digest(request.headers.get("X-Paperform-Secret", ""), secret):
        return fail("FORBIDDEN", "Wrong or missing webhook secret.", 403)
    if not WEBHOOK_HITS.take("paperform", WEBHOOK_PER_WINDOW, WEBHOOK_WINDOW):
        return fail("RATE_LIMITED", "Too many webhook calls.", 429)
    if (request.content_length or 0) > WEBHOOK_MAX_BYTES:
        return fail("VALIDATION_FAILED", "That payload is too big.", 413)

    payload = request.get_json(silent=True)
    try:
        result = paperform.receive(g.db, payload)
    except sqlite3.Error:
        # The one case worth a retry: the database was busy or locked. Paperform
        # resends anything that is not a 2xx, and by then it will not be.
        log.exception("paperform webhook: database error")
        return fail("SERVER_ERROR", "Could not write that sign-up. Send it again.", 503)
    return ok(result)


@app.route("/admin/api/people", methods=["POST"])
def admin_walk_in():
    body = request.get_json(silent=True) or {}
    return _run(lambda: console.add_walk_in(g.db, body, g.console["name"]))


@app.route("/admin/api/people/<int:attendee_id>/unlink", methods=["POST"])
def admin_unlink(attendee_id):
    body = request.get_json(silent=True) or {}
    return _run(lambda: console.unlink(g.db, attendee_id, body.get("reason"), g.console["name"]))


@app.route("/admin/api/gate-attempts/<int:attempt_id>/resolve", methods=["POST"])
def admin_resolve_attempt(attempt_id):
    body = request.get_json(silent=True) or {}
    return _run(lambda: console.resolve_attempt(g.db, attempt_id, body, g.console["name"]))


# ---------------------------------------------------------------------------
# Schedules and the GM console
# ---------------------------------------------------------------------------

@app.route("/admin/api/slots/<int:slot_id>/block", methods=["POST"])
def admin_block(slot_id):
    body = request.get_json(silent=True) or {}
    return _run(lambda: console.block_slot(g.db, slot_id, body.get("blocked"), body.get("reason"),
                                           g.console["name"]))


@app.route("/admin/api/escape/move", methods=["POST"])
def admin_move():
    body = request.get_json(silent=True) or {}
    return _run(lambda: console.move_person(g.db, body.get("attendee_id"), body.get("slot_id"),
                                            body.get("reason"), g.console["name"], now_utc()))


@app.route("/admin/api/gm/state")
def admin_gm_state():
    return _run(lambda: game.state(g.db, now_utc(), request.args.get("slot_id")))


@app.route("/admin/api/gm/<int:slot_id>/halves", methods=["POST"])
def admin_gm_halves(slot_id):
    body = request.get_json(silent=True) or {}
    return _run(lambda: game.halves(g.db, slot_id, actor(), swap_attendee_id=body.get("swap_attendee_id"),
                                    rebalance=bool(body.get("rebalance"))))


@app.route("/admin/api/gm/<int:slot_id>/cues/<key>", methods=["POST"])
def admin_gm_cue(slot_id, key):
    return _run(lambda: game.send_cue(g.db, slot_id, key, actor(), now_utc()))


@app.route("/admin/api/gm/<int:slot_id>/<action>", methods=["POST"])
def admin_gm_action(slot_id, action):
    return _run(lambda: game.act(g.db, slot_id, action, actor(), now_utc()))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
