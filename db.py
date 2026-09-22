"""SQLite: connection, schema, settings and the audit log.

One file, WAL mode, a busy timeout so the web process and the bot can both
write. Times are stored as UTC ISO strings and displayed in the event zone.
"""

import json
import secrets
import sqlite3
from datetime import datetime, timezone

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS attendees (
    id                    INTEGER PRIMARY KEY,
    paperform_id          TEXT UNIQUE,
    name                  TEXT NOT NULL,
    email                 TEXT,
    handle                TEXT UNIQUE,
    handle_raw            TEXT,
    tg_user_id            INTEGER UNIQUE,
    tg_first_name         TEXT,
    tg_username_seen      TEXT,
    can_message           INTEGER NOT NULL DEFAULT 1,
    source                TEXT NOT NULL DEFAULT 'import',
    status                TEXT NOT NULL DEFAULT 'active',
    is_test               INTEGER NOT NULL DEFAULT 0,
    payment_status        TEXT NOT NULL DEFAULT 'missing',
    paperform_receipt_url TEXT,
    submitted_at_text     TEXT,
    pass_code             TEXT UNIQUE,
    checked_in_at         TEXT,
    checked_in_by         TEXT,
    notes                 TEXT,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    id           INTEGER PRIMARY KEY,
    attendee_id  INTEGER NOT NULL REFERENCES attendees(id),
    item         TEXT NOT NULL,
    variant      TEXT,
    claimed_at   TEXT NOT NULL,
    staff_name   TEXT,
    station      TEXT,
    voided_at    TEXT,
    voided_by    TEXT,
    void_reason  TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS claims_once
    ON claims (attendee_id, item) WHERE voided_at IS NULL;

CREATE TABLE IF NOT EXISTS slots (
    id            INTEGER PRIMARY KEY,
    room          TEXT NOT NULL,
    starts_at     TEXT NOT NULL,
    ends_at       TEXT NOT NULL,
    capacity      INTEGER NOT NULL,
    price_cents   INTEGER NOT NULL DEFAULT 0,
    is_blocked    INTEGER NOT NULL DEFAULT 0,
    block_reason  TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS slots_unique ON slots (room, starts_at);

CREATE TABLE IF NOT EXISTS escape_bookings (
    id               INTEGER PRIMARY KEY,
    slot_id          INTEGER NOT NULL REFERENCES slots(id),
    attendee_id      INTEGER NOT NULL REFERENCES attendees(id),
    booked_by_id     INTEGER REFERENCES attendees(id),
    ref_code         TEXT UNIQUE NOT NULL,
    zone             TEXT,
    zone_changed_by  TEXT,
    status           TEXT NOT NULL DEFAULT 'booked',
    created_at       TEXT NOT NULL,
    cancelled_at     TEXT,
    checked_in_at    TEXT,
    reminder_sent_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS escape_one_per_person
    ON escape_bookings (attendee_id) WHERE status IN ('booked', 'checked_in');

-- One row per person per booking, exactly like escape_bookings, because the
-- jam room is booked as a group too (organiser's instruction, 18 Sep). A
-- room full of strangers is fine for an escape game and awkward for a jam, so
-- the booker brings their own people.
CREATE TABLE IF NOT EXISTS jam_bookings (
    id               INTEGER PRIMARY KEY,
    slot_id          INTEGER NOT NULL REFERENCES slots(id),
    attendee_id      INTEGER NOT NULL REFERENCES attendees(id),
    booked_by_id     INTEGER REFERENCES attendees(id),
    instrument       TEXT,
    ref_code         TEXT UNIQUE NOT NULL,
    party_size       INTEGER NOT NULL DEFAULT 1,
    price_cents      INTEGER NOT NULL,
    status           TEXT NOT NULL DEFAULT 'held',
    hold_expires_at  TEXT,
    reviewed_by      TEXT,
    reviewed_at      TEXT,
    reject_reason    TEXT,
    created_at       TEXT NOT NULL,
    cancelled_at     TEXT,
    reminder_sent_at TEXT
);
-- One person cannot hold two seats in the same slot.
CREATE UNIQUE INDEX IF NOT EXISTS jam_one_seat_each
    ON jam_bookings (slot_id, attendee_id) WHERE status = 'confirmed';

CREATE TABLE IF NOT EXISTS receipts (
    id                   INTEGER PRIMARY KEY,
    attendee_id          INTEGER REFERENCES attendees(id),
    purpose              TEXT NOT NULL,
    jam_booking_id       INTEGER REFERENCES jam_bookings(id),
    file_name            TEXT,
    sha256               TEXT,
    phash                TEXT,
    txn_ref              TEXT,
    txn_ref_skip_reason  TEXT,
    possible_duplicate_of INTEGER REFERENCES receipts(id),
    source               TEXT NOT NULL,
    uploaded_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS receipts_sha ON receipts (sha256);
CREATE INDEX IF NOT EXISTS receipts_phash ON receipts (phash);
CREATE UNIQUE INDEX IF NOT EXISTS receipts_txn
    ON receipts (txn_ref) WHERE txn_ref IS NOT NULL;

-- §9 r23 — one-time links for the full-page phone. Telegram's in-app browser
-- is a webview, and a webview can refuse to play the phone's audio or hold
-- fullscreen. This is the escape hatch: a link that opens the phone in the
-- real browser, works once, and dies after about a minute, so a screenshot of
-- it in a group chat is worth nothing.
CREATE TABLE IF NOT EXISTS phone_tickets (
    id          INTEGER PRIMARY KEY,
    token       TEXT UNIQUE NOT NULL,
    attendee_id INTEGER NOT NULL REFERENCES attendees(id),
    slot_id     INTEGER REFERENCES slots(id),
    issued_at   TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    used_at     TEXT
);
CREATE INDEX IF NOT EXISTS phone_tickets_who ON phone_tickets (attendee_id);

CREATE TABLE IF NOT EXISTS game_sessions (
    id                INTEGER PRIMARY KEY,
    slot_id           INTEGER UNIQUE NOT NULL REFERENCES slots(id),
    started_at        TEXT,
    halves_locked_at  TEXT,
    paused_seconds    INTEGER NOT NULL DEFAULT 0,
    extended_seconds  INTEGER NOT NULL DEFAULT 0,
    ended_at          TEXT,
    phone_unlocked_at TEXT,
    phone_locked_at   TEXT,
    in_app_phone      TEXT NOT NULL DEFAULT 'on',
    result            TEXT,
    finish_seconds    INTEGER,
    gm_name           TEXT
);

CREATE TABLE IF NOT EXISTS hint_sends (
    id         INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES game_sessions(id),
    hint_key   TEXT NOT NULL,
    sent_at    TEXT NOT NULL,
    sent_by    TEXT
);

CREATE TABLE IF NOT EXISTS one_time_links (
    id          INTEGER PRIMARY KEY,
    token_hash  TEXT UNIQUE NOT NULL,
    attendee_id INTEGER NOT NULL REFERENCES attendees(id),
    purpose     TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    used_at     TEXT
);

CREATE TABLE IF NOT EXISTS gate_attempts (
    id             INTEGER PRIMARY KEY,
    at             TEXT NOT NULL,
    tg_user_id     INTEGER,
    tg_username    TEXT,
    tg_first_name  TEXT,
    claimed_handle TEXT,
    outcome        TEXT NOT NULL,
    resolved_by    TEXT,
    resolved_at    TEXT
);
CREATE INDEX IF NOT EXISTS gate_attempts_at ON gate_attempts (at);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY,
    at         TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_name TEXT,
    station    TEXT,
    action     TEXT NOT NULL,
    entity     TEXT,
    entity_id  TEXT,
    details    TEXT
);
CREATE INDEX IF NOT EXISTS audit_at ON audit_log (at);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT,
    updated_by TEXT
);

-- Console sign-ins (§9 rule 33). Beyond §8: kept server-side so Sign out
-- really ends a session and a restart of app.py does not sign anyone out.
-- Only hashes of the session id and CSRF token are stored.
CREATE TABLE IF NOT EXISTS console_sessions (
    id           INTEGER PRIMARY KEY,
    sid_hash     TEXT UNIQUE NOT NULL,
    csrf_hash    TEXT NOT NULL,
    role         TEXT NOT NULL,
    name         TEXT NOT NULL,
    station      TEXT,
    created_at   TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    revoked_at   TEXT
);

-- Bot messages waiting to go out (beyond §8, added 17 Sep). The web process
-- writes a row in the same transaction as the change that caused it; bot.py
-- sends it. dedupe_key stops the same message being queued twice.
CREATE TABLE IF NOT EXISTS notifications (
    id           INTEGER PRIMARY KEY,
    attendee_id  INTEGER NOT NULL REFERENCES attendees(id),
    kind         TEXT NOT NULL,
    dedupe_key   TEXT UNIQUE,
    text         TEXT NOT NULL,
    button_path  TEXT,
    created_at   TEXT NOT NULL,
    send_after   TEXT NOT NULL,
    expires_at   TEXT,
    status       TEXT NOT NULL DEFAULT 'queued',
    attempts     INTEGER NOT NULL DEFAULT 0,
    sent_at      TEXT,
    last_error   TEXT
);
CREATE INDEX IF NOT EXISTS notifications_due ON notifications (status, send_after);

-- Made-to-order matcha and panini (22 Sep, decision 125). A row per order,
-- placed when the pass is scanned at the counter and called when it's made.
-- Not a claim: paid extras, so nothing here is once-only.
CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY,
    attendee_id  INTEGER NOT NULL REFERENCES attendees(id),
    item         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'waiting',   -- waiting | called | collected | cancelled
    ordered_at   TEXT NOT NULL,
    ordered_by   TEXT,
    station      TEXT,
    called_at    TEXT,
    called_by    TEXT,
    calls        INTEGER NOT NULL DEFAULT 0,
    closed_at    TEXT,
    closed_by    TEXT
);
CREATE INDEX IF NOT EXISTS orders_open ON orders (status, ordered_at);

-- Messages to a staff chat rather than an attendee (the actor's hint lines).
-- bot.py sends them, like notifications.
CREATE TABLE IF NOT EXISTS direct_messages (
    id          INTEGER PRIMARY KEY,
    chat_id     INTEGER NOT NULL,
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'queued',
    attempts    INTEGER NOT NULL DEFAULT 0,
    sent_at     TEXT,
    last_error  TEXT
);

CREATE TABLE IF NOT EXISTS import_runs (
    id           INTEGER PRIMARY KEY,
    at           TEXT NOT NULL,
    source       TEXT NOT NULL,
    file_name    TEXT,
    counts       TEXT,
    report       TEXT,
    committed_at TEXT
);
"""


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect():
    conn = sqlite3.connect(config.DB_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    config.ensure_dirs()
    existed = config.DB_PATH.exists()
    conn = connect()
    try:
        # Before the schema, so an index a rule outgrew cannot survive and
        # keep enforcing the old rule against the new code.
        for name in DROPPED_INDEXES:
            conn.execute(f"DROP INDEX IF EXISTS {name}")  # noqa: S608 - fixed list above
        conn.executescript(SCHEMA)
        migrate(conn)
        conn.executescript(LATE_INDEXES)
        seed_settings(conn)
    finally:
        conn.close()
    return existed


# Columns added after a database already existed: (table, column, definition).
ADDED_COLUMNS = (
    ("game_sessions", "paused_at", "TEXT"),
    # Jam became a group booking on 18 Sep; these mirror escape_bookings.
    ("jam_bookings", "booked_by_id", "INTEGER REFERENCES attendees(id)"),
    ("jam_bookings", "cancelled_at", "TEXT"),
    # And on 19 Sep each seat became an instrument.
    ("jam_bookings", "instrument", "TEXT"),
)

# Indexes a rule outgrew. Dropped before the schema runs, so the new one can
# take over. `jam_one_per_slot` held the whole jam room for one booking; the
# room is now booked one instrument at a time.
DROPPED_INDEXES = ("jam_one_per_slot",)

# Indexes over columns that ADDED_COLUMNS puts there, so they cannot live in
# SCHEMA: on a database that already exists, SCHEMA runs before the migration
# and the column is not there yet. These run after it instead.
LATE_INDEXES = """
-- One instrument cannot be played by two people at once. This is the index
-- that decides a race for the last drum kit, the same way
-- `escape_one_per_person` decides a race for the last seat: the database
-- says no, rather than two requests both passing a check.
CREATE UNIQUE INDEX IF NOT EXISTS jam_one_player_per_instrument
    ON jam_bookings (slot_id, instrument) WHERE status = 'confirmed';
"""


def migrate(conn):
    """Add columns that newer code needs to an older database file."""
    for table, column, definition in ADDED_COLUMNS:
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}  # noqa: S608
        if column not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")  # noqa: S608


def seed_settings(conn):
    """Make the settings table match config.DEFAULT_SETTINGS.

    A missing key is added. A row nobody has edited (updated_by 'system')
    follows the default when the default changes. A value a person set is
    never touched. Keys the code no longer has are removed.
    """
    rows = {r["key"]: r for r in conn.execute("SELECT key, value, updated_by FROM settings")}
    now = utcnow()
    for key, value in config.DEFAULT_SETTINGS.items():
        row = rows.get(key)
        if row is None:
            conn.execute(
                "INSERT INTO settings (key, value, updated_at, updated_by) VALUES (?,?,?,?)",
                (key, json.dumps(value), now, "system"),
            )
        elif row["updated_by"] == "system" and row["value"] != json.dumps(value):
            conn.execute("UPDATE settings SET value=?, updated_at=? WHERE key=?",
                         (json.dumps(value), now, key))
    for key in set(rows) - set(config.DEFAULT_SETTINGS):
        conn.execute("DELETE FROM settings WHERE key=?", (key,))


def get_settings(conn):
    out = dict(config.DEFAULT_SETTINGS)
    for row in conn.execute("SELECT key, value FROM settings"):
        try:
            out[row["key"]] = json.loads(row["value"])
        except (ValueError, TypeError):
            out[row["key"]] = row["value"]
    return out


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return config.DEFAULT_SETTINGS.get(key, default)
    try:
        return json.loads(row["value"])
    except (ValueError, TypeError):
        return row["value"]


def set_setting(conn, key, value, by="admin"):
    conn.execute(
        "INSERT INTO settings (key, value, updated_at, updated_by) VALUES (?,?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
        "updated_at=excluded.updated_at, updated_by=excluded.updated_by",
        (key, json.dumps(value), utcnow(), by),
    )


def audit(conn, actor_type, action, actor_name=None, station=None,
          entity=None, entity_id=None, details=None):
    """§9 rule 32 — every write leaves a row with who, where and when."""
    conn.execute(
        "INSERT INTO audit_log (at, actor_type, actor_name, station, action, entity, entity_id, details) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (utcnow(), actor_type, actor_name, station, action, entity,
         str(entity_id) if entity_id is not None else None,
         json.dumps(details) if details is not None else None),
    )


def new_code(conn, table, column, length=8, group=None):
    """A random, never sequential, unique code in the unambiguous alphabet."""
    alphabet = config.CODE_ALPHABET
    for _ in range(200):
        body = "".join(secrets.choice(alphabet) for _ in range(length))
        code = f"{group}-{body}" if group else f"{body[:4]}-{body[4:]}"
        row = conn.execute(
            f"SELECT 1 FROM {table} WHERE {column} = ?", (code,)  # noqa: S608 - fixed names
        ).fetchone()
        if row is None:
            return code
    raise RuntimeError("could not find a free code")


def backup_now(keep=None):
    """A consistent copy via SQLite's own backup API, not a file copy."""
    config.ensure_dirs()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = config.BACKUP_DIR / f"app-{stamp}.db"
    src = connect()
    try:
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    if keep:
        copies = sorted(config.BACKUP_DIR.glob("app-*.db"))
        for old in copies[:-keep]:
            old.unlink(missing_ok=True)
    return target


__all__ = [
    "SCHEMA", "utcnow", "connect", "init_db", "migrate", "seed_settings", "get_settings",
    "get_setting", "set_setting", "audit", "new_code", "backup_now",
]
