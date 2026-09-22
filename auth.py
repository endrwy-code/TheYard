"""Identity: Telegram initData, the gate, and admin/staff/GM sessions.

The server is the only judge of who someone is (§3 rule 2). initDataUnsafe is
never trusted for any decision.
"""

import hashlib
import hmac
import json
import re
import secrets
import time
from urllib.parse import parse_qsl

from werkzeug.security import check_password_hash, generate_password_hash

import config
import db

HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")


def normalise_handle(raw):
    """§9 rule 1. Trim, drop a leading @, drop t.me links, lowercase.

    Returns '' when there is nothing usable. Validity is checked separately by
    looks_like_handle so the import can flag oddities instead of dropping them.
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    s = re.sub(r"^(https?://)?(www\.)?(t\.me|telegram\.me)/", "", s, flags=re.I)
    s = s.strip().lstrip("@").strip()
    s = s.split("?")[0].split("/")[0]
    return s.lower()


def looks_like_handle(handle):
    return bool(HANDLE_RE.match(handle or ""))


# ---------------------------------------------------------------------------
# Telegram initData
# ---------------------------------------------------------------------------

def verify_telegram_data(init_data: str) -> bool:
    """Telegram's official check, with the §9 rule 8 maximum-age check added.

    The signature half is the original working implementation — unchanged.
    """
    parsed = dict(parse_qsl(init_data))
    received_hash = parsed.pop('hash', None)
    data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", config.TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not received_hash or not hmac.compare_digest(calculated_hash, received_hash):
        return False

    # Added: refuse anything signed more than 24 hours ago (§9 rule 8).
    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except (TypeError, ValueError):
        return False
    if auth_date <= 0:
        return False
    if time.time() - auth_date > config.INITDATA_MAX_AGE_SECONDS:
        return False
    return True


def init_data_age_ok(init_data: str) -> bool:
    """True when the signature is fine but we want to tell expiry apart."""
    parsed = dict(parse_qsl(init_data))
    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except (TypeError, ValueError):
        return False
    return auth_date > 0 and (time.time() - auth_date) <= config.INITDATA_MAX_AGE_SECONDS


def signature_ok(init_data: str) -> bool:
    """The signature half on its own, so INITDATA_EXPIRED can be reported."""
    parsed = dict(parse_qsl(init_data))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return False
    check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret = hmac.new(b"WebAppData", config.TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calc, received_hash)


def parse_init_data(init_data: str):
    """The verified user object. Only ever called after the signature passed."""
    parsed = dict(parse_qsl(init_data))
    user = {}
    if parsed.get("user"):
        try:
            user = json.loads(parsed["user"])
        except ValueError:
            user = {}
    return {
        "user_id": user.get("id"),
        "username": normalise_handle(user.get("username")),
        "username_raw": user.get("username") or "",
        "first_name": (user.get("first_name") or "").strip(),
        # True when this person has let the bot message them.
        "allows_write": bool(user.get("allows_write_to_pm")),
        "start_param": parsed.get("start_param") or None,
        "auth_date": parsed.get("auth_date"),
    }


def read_init_data(headers):
    """Pull initData out of `Authorization: tma <initData>` (§12)."""
    raw = headers.get("Authorization", "")
    if raw.startswith("tma "):
        return raw[4:].strip()
    return ""


# ---------------------------------------------------------------------------
# The gate (§9 rules 1-9)
# ---------------------------------------------------------------------------

class GateError(Exception):
    def __init__(self, code, handle=None):
        super().__init__(code)
        self.code = code
        self.handle = handle


def is_always_allowed(handle):
    return bool(handle) and handle in config.ALWAYS_ALLOW_HANDLES


def record_attempt(conn, tg, outcome, claimed_handle=None):
    conn.execute(
        "INSERT INTO gate_attempts (at, tg_user_id, tg_username, tg_first_name, claimed_handle, outcome) "
        "VALUES (?,?,?,?,?,?)",
        (db.utcnow(), tg.get("user_id"), tg.get("username"), tg.get("first_name"),
         claimed_handle, outcome),
    )


def ensure_owner_row(conn, tg):
    """§9 rule 5 — @maxi_muslim gets in even when the list never loaded."""
    row = conn.execute(
        "SELECT * FROM attendees WHERE handle = ?", (tg["username"],)
    ).fetchone()
    if row:
        return row
    now = db.utcnow()
    code = db.new_code(conn, "attendees", "pass_code")
    conn.execute(
        "INSERT INTO attendees (name, handle, handle_raw, source, status, is_test, "
        "payment_status, pass_code, created_at, updated_at) "
        "VALUES (?,?,?,'owner','active',1,'verified',?,?,?)",
        (tg["first_name"] or tg["username"], tg["username"],
         tg["username_raw"], code, now, now),
    )
    db.audit(conn, "system", "Owner entry created", entity="attendee",
             entity_id=tg["username"], details={"reason": "always-allowed handle"})
    return conn.execute(
        "SELECT * FROM attendees WHERE handle = ?", (tg["username"],)
    ).fetchone()


def resolve_attendee(conn, tg):
    """Decide whether this Telegram user gets in, and link them on first Start.

    Raises GateError with a §12 code on refusal. Returns the attendee row.
    """
    always = is_always_allowed(tg["username"])

    # Rule 9 — the gate switch closes the app to everyone but always-allowed.
    if not db.get_setting(conn, "gate_open", True) and not always:
        record_attempt(conn, tg, "GATE_CLOSED")
        raise GateError("GATE_CLOSED")

    # Rule 2 — an existing link wins, so a username change never locks anyone out.
    linked = None
    if tg["user_id"]:
        linked = conn.execute(
            "SELECT * FROM attendees WHERE tg_user_id = ?", (tg["user_id"],)
        ).fetchone()
    if linked:
        if linked["status"] != "active" and not always:
            record_attempt(conn, tg, "INACTIVE")
            raise GateError("INACTIVE", tg["username"])
        _touch_seen(conn, linked, tg)
        return conn.execute("SELECT * FROM attendees WHERE id = ?", (linked["id"],)).fetchone()

    if always:
        row = ensure_owner_row(conn, tg)
        return _link(conn, row, tg)

    # Rule 4 — no username and no existing link.
    if not tg["username"]:
        record_attempt(conn, tg, "NO_USERNAME")
        raise GateError("NO_USERNAME")

    row = conn.execute(
        "SELECT * FROM attendees WHERE handle = ?", (tg["username"],)
    ).fetchone()
    if row is None:
        record_attempt(conn, tg, "NOT_ON_LIST")
        raise GateError("NOT_ON_LIST", tg["username"])
    if row["status"] != "active":
        record_attempt(conn, tg, "INACTIVE")
        raise GateError("INACTIVE", tg["username"])

    # Rule 3 — that sign-up already belongs to a different Telegram account.
    if row["tg_user_id"] and tg["user_id"] and row["tg_user_id"] != tg["user_id"]:
        record_attempt(conn, tg, "LINKED_ELSEWHERE")
        raise GateError("LINKED_ELSEWHERE", tg["username"])

    return _link(conn, row, tg)


def _link(conn, row, tg):
    """Rule 3 — link on the first successful Start; the ID is the stable key."""
    now = db.utcnow()
    if row["tg_user_id"] is None and tg["user_id"]:
        conn.execute(
            "UPDATE attendees SET tg_user_id=?, tg_first_name=?, tg_username_seen=?, updated_at=? "
            "WHERE id=?",
            (tg["user_id"], tg["first_name"], tg["username_raw"], now, row["id"]),
        )
        db.audit(conn, "system", "Telegram account linked", entity="attendee",
                 entity_id=row["id"],
                 details={"tg_user_id": tg["user_id"], "handle": tg["username"]})
    else:
        _touch_seen(conn, row, tg)
    if not row["pass_code"]:
        conn.execute("UPDATE attendees SET pass_code=? WHERE id=?",
                     (db.new_code(conn, "attendees", "pass_code"), row["id"]))
    return conn.execute("SELECT * FROM attendees WHERE id = ?", (row["id"],)).fetchone()


def _touch_seen(conn, row, tg):
    if row["tg_first_name"] != tg["first_name"] or row["tg_username_seen"] != tg["username_raw"]:
        conn.execute(
            "UPDATE attendees SET tg_first_name=?, tg_username_seen=?, updated_at=? WHERE id=?",
            (tg["first_name"], tg["username_raw"], db.utcnow(), row["id"]),
        )


def claimed_handle_allowed(conn, tg):
    """§9 rule 7 — at most N "I signed up as" requests per person per hour."""
    limit = int(db.get_setting(conn, "claimed_handle_limit", 3))
    since = time.time() - 3600
    rows = conn.execute(
        "SELECT at FROM gate_attempts WHERE tg_user_id = ? AND claimed_handle IS NOT NULL",
        (tg.get("user_id"),),
    ).fetchall()
    recent = 0
    for r in rows:
        try:
            from datetime import datetime
            if datetime.fromisoformat(r["at"]).timestamp() >= since:
                recent += 1
        except ValueError:
            continue
    return recent < limit


# ---------------------------------------------------------------------------
# Console sign-in
# ---------------------------------------------------------------------------

def hash_secret(plain):
    return generate_password_hash(plain)


def _matches(stored, secret):
    if not stored or not secret:
        return False
    try:
        return check_password_hash(stored, secret)
    except ValueError:
        return False


def check_role(role, secret):
    """Constant-time-ish check of the password or PIN for a console role.

    `mobile` takes either phone PIN — the staff PIN or the GM PIN — so no PIN
    stopped working when the two phone sign-ins became one (22 Sep, decision
    126). `staff` and `gm` still check their own PIN alone: bot.py's /actor
    command asks for the GM PIN specifically."""
    if role == "mobile":
        return _matches(config.STAFF_PIN_HASH, secret) or _matches(config.GM_PIN_HASH, secret)
    stored = {
        "admin": config.ADMIN_PASSWORD_HASH,
        "staff": config.STAFF_PIN_HASH,
        "gm": config.GM_PIN_HASH,
    }.get(role, "")
    return _matches(stored, secret)


def new_csrf():
    return secrets.token_urlsafe(32)


# Two front doors since 22 Sep (decision 126): Laptop is the admin password
# and everything; Mobile is a phone PIN and the booth, orders, the game and
# look-ups. The staff and GM sign-ins became Mobile; their old names still
# sign in, as Mobile, so an open page or an old habit does not break.
ROLES = ("admin", "mobile")
ROLE_ALIASES = {"staff": "mobile", "gm": "mobile"}
ROLE_SECRET_KEY = {
    "admin": ("ADMIN_PASSWORD_HASH", "set-admin-password"),
    "mobile": ("STAFF_PIN_HASH", "set-staff-pin"),
}


def normal_role(role):
    """The role a sign-in or a stored session really has."""
    role = str(role or "")
    return ROLE_ALIASES.get(role, role)


def role_configured(role):
    """True when .env holds a hash for this role's password or PIN."""
    if role == "mobile":
        return bool(config.STAFF_PIN_HASH or config.GM_PIN_HASH)
    key = ROLE_SECRET_KEY.get(role, ("", ""))[0]
    return bool(getattr(config, key, ""))


def _digest(token):
    return hashlib.sha256((token or "").encode()).hexdigest()


def _iso_in(seconds):
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).replace(
        microsecond=0).isoformat()


def create_console_session(conn, role, name, station):
    """A new sign-in. Returns the raw session id and CSRF token — the only
    time either exists outside the browser; the table keeps hashes."""
    sid, csrf = secrets.token_urlsafe(32), new_csrf()
    expires_at = _iso_in(config.CONSOLE_SESSION_HOURS * 3600)
    conn.execute(
        "INSERT INTO console_sessions (sid_hash, csrf_hash, role, name, station, "
        "created_at, expires_at) VALUES (?,?,?,?,?,?,?)",
        (_digest(sid), _digest(csrf), role, name, station or None, db.utcnow(), expires_at),
    )
    return {"sid": sid, "csrf_token": csrf, "expires_at": expires_at}


def load_console_session(conn, sid):
    """The live session row for this id, or None if unknown, expired or signed out."""
    if not sid:
        return None
    row = conn.execute(
        "SELECT * FROM console_sessions WHERE sid_hash = ? AND revoked_at IS NULL",
        (_digest(sid),),
    ).fetchone()
    if row is None or row["expires_at"] <= db.utcnow():
        return None
    # A sign-in made before 22 Sep says staff or gm; both are Mobile now.
    session_row = dict(row)
    session_row["role"] = normal_role(session_row["role"])
    return session_row


def rotate_csrf(conn, session_row):
    """A fresh CSRF token for a page that was reloaded. Only this origin can
    read the response (no CORS), so handing it out on a GET is safe."""
    csrf = new_csrf()
    conn.execute("UPDATE console_sessions SET csrf_hash=? WHERE id=?",
                 (_digest(csrf), session_row["id"]))
    return csrf


def revoke_console_session(conn, sid):
    if sid:
        conn.execute(
            "UPDATE console_sessions SET revoked_at=? WHERE sid_hash=? AND revoked_at IS NULL",
            (db.utcnow(), _digest(sid)),
        )


def csrf_ok(session_row, token):
    return bool(token) and hmac.compare_digest(session_row["csrf_hash"], _digest(token))


# ---------------------------------------------------------------------------
# Rate limits (§9 rules 28, 33). In memory: a restart clears them, which is
# harmless — they only exist to make guessing slow.
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self):
        import threading
        self._lock = threading.Lock()
        self._hits = {}

    def _recent(self, key, window, now):
        hits = [t for t in self._hits.get(key, []) if now - t < window]
        self._hits[key] = hits
        return hits

    def allowed(self, key, limit, window):
        """True while fewer than `limit` hits landed in the last `window` seconds."""
        with self._lock:
            return len(self._recent(key, window, time.time())) < limit

    def hit(self, key, window):
        with self._lock:
            now = time.time()
            self._recent(key, window, now).append(now)

    def take(self, key, limit, window):
        """Record a hit if there is room. False means the limit is reached."""
        with self._lock:
            now = time.time()
            hits = self._recent(key, window, now)
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def clear(self):
        with self._lock:
            self._hits.clear()


SIGNIN_FAILURES = RateLimiter()
CODE_LOOKUPS = RateLimiter()

SIGNIN_WINDOW = 5 * 60
SIGNIN_PER_CLIENT = 5      # wrong passwords/PINs from one device per window
SIGNIN_PER_ROLE = 30       # from everyone together — keeps a 4-digit PIN slow to guess
LOOKUP_WINDOW = 60


def signin_allowed(role, client):
    return (SIGNIN_FAILURES.allowed(("client", role, client), SIGNIN_PER_CLIENT, SIGNIN_WINDOW)
            and SIGNIN_FAILURES.allowed(("role", role), SIGNIN_PER_ROLE, SIGNIN_WINDOW))


def signin_failed(role, client):
    SIGNIN_FAILURES.hit(("client", role, client), SIGNIN_WINDOW)
    SIGNIN_FAILURES.hit(("role", role), SIGNIN_WINDOW)


def reset_rate_limits():
    SIGNIN_FAILURES.clear()
    CODE_LOOKUPS.clear()
