"""The console's remaining screens: Overview, Settings, Audit and backups,
Roster, walk-ins, linking people at the gate, and schedule changes
(§9 rules 12, 22, 32-36, §10).

Every write here is admin-only (app.py decides) and leaves an audit row with
before and after values.
"""

import json
import re
from datetime import datetime, timedelta, timezone

import config
import db
from auth import looks_like_handle, normalise_handle
from services import bookings, claims, notify, receipts, roster
from services.claims import ClaimError
from services.people import _day_clock, get_attendee

ClaimError.STATUS.update({"HANDLE_TAKEN": 409, "LINKED_ELSEWHERE": 409})


def _clean(text, limit=300):
    return " ".join(str(text or "").split())[:limit]


def _reason(text):
    reason = _clean(text)
    if not reason:
        raise ClaimError("VALIDATION_FAILED", "A reason is required.")
    return reason


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

def overview(conn, now):
    s = db.get_settings(conn)
    people = conn.execute(
        "SELECT COUNT(*) total, SUM(source='walk_in') walk_ins, SUM(checked_in_at IS NOT NULL) inside, "
        "SUM(tg_user_id IS NOT NULL) linked, "
        "SUM(payment_status='verified') verified, SUM(payment_status='submitted') pending, "
        "SUM(payment_status='missing') missing, SUM(payment_status='rejected') rejected "
        "FROM attendees WHERE status='active' AND is_test=0").fetchone()
    total = people["total"] or 0
    # Two different things, counted separately (23 Sep, STATE.md 135).
    # Opening the app is not being in the room: people link their Telegram
    # account days early. "At the event" counts only check-ins made from the
    # moment the doors open on the day, so a rehearsal check-in never counts.
    doors = notify.event_local(s["doors_open"])
    here = conn.execute(
        "SELECT COUNT(*) FROM attendees WHERE status='active' AND is_test=0 AND checked_in_at >= ?",
        (notify._iso(doors),)).fetchone()[0]
    early = (people["inside"] or 0) - here
    pct = round(100 * here / total) if total else 0
    pct_linked = round(100 * (people["linked"] or 0) / total) if total else 0
    stats = [
        {"label": "Signed up", "value": str(total),
         "sub": f"{people['walk_ins'] or 0} walk-in{'s' if (people['walk_ins'] or 0) != 1 else ''}",
         "tone": "#3C4654"},
        {"label": "Opened the app", "value": str(people["linked"] or 0),
         "sub": f"{pct_linked}% of the list, any time", "tone": "#3C4654"},
        {"label": "At the event", "value": str(here),
         "sub": f"{pct}% of the list · checked in from {notify.hhmm_text(s['doors_open'])}"
                + (f" · {early} before that, not counted" if early else ""),
         "tone": "#3C4654"},
        # With the payment check off (STATE.md 138) these are still worth
        # seeing, but none of them is a job to do before the doors.
        {"label": "Payments verified", "value": str(people["verified"] or 0),
         "sub": (f"{people['pending'] or 0} unchecked, {people['missing'] or 0} with no receipt "
                 "· not needed to collect" if s["claim_requires"] == "none"
                 else f"{people['pending'] or 0} to check, {people['missing'] or 0} missing"),
         "tone": "#3C4654" if s["claim_requires"] == "none"
                 else ("#A8231B" if (people["pending"] or people["missing"]) else "#1F7A4C")},
    ]
    for key, label in config.ITEMS:
        used = conn.execute(
            "SELECT COUNT(*) FROM claims c JOIN attendees a ON a.id=c.attendee_id "
            "WHERE c.item=? AND c.voided_at IS NULL AND a.is_test=0", (key,)).fetchone()[0]
        stock = claims.stock_for(conn, key)
        sub = f"{stock['left']} left in stock" if stock else "stock not counted"
        # The pastry comes in kinds: say which are going, so whoever restocks
        # the counter knows what to bring out (22 Sep, STATE.md 132).
        kinds = config.ITEM_CHOICES.get(key)
        if kinds:
            by = dict(conn.execute(
                "SELECT c.variant, COUNT(*) FROM claims c JOIN attendees a ON a.id=c.attendee_id "
                "WHERE c.item=? AND c.voided_at IS NULL AND a.is_test=0 GROUP BY c.variant", (key,)).fetchall())
            sub = ", ".join(f"{kl.split()[-1]} {by.get(k, 0)}" for k, kl in kinds) + " · " + sub
        stats.append({"label": label, "value": f"{used}/{people['verified'] or 0}", "sub": sub,
                      "tone": "#A8231B" if stock and stock["low"] else "#3C4654"})
    board = bookings.admin_board(conn, now)
    stats.append({"label": "Escape seats", "value": str(board["seats_taken"]),
                  "sub": f"of {board['seats_total']} tonight", "tone": "#3C4654"})
    # Slots booked, and how many people that is. The room takes a group since
    # 18 Sep, so "3 of 10 booked" no longer says how many are in the building.
    jam_taken = sum(1 for j in board["jam"] if j["status"] == "booked")
    heads = board.get("jam_seats_taken", 0)
    stats.append({"label": "Jam slots", "value": str(jam_taken),
                  "sub": f"of {len(board['jam'])} booked"
                         + (f" · {heads} jamming" if heads else ""),
                  "tone": "#3C4654"})

    refused = conn.execute("SELECT COUNT(*) FROM gate_attempts WHERE resolved_at IS NULL "
                           "AND claimed_handle IS NULL").fetchone()[0]
    requests = conn.execute("SELECT COUNT(*) FROM gate_attempts WHERE resolved_at IS NULL "
                            "AND claimed_handle IS NOT NULL").fetchone()[0]
    thin = sum(1 for gm in board["escape"]
               if not (gm["done"] or gm["running"] or gm["blocked"]) and gm["booked"] * 2 < gm["capacity"])
    failed = conn.execute("SELECT COUNT(*) FROM notifications WHERE status='failed'").fetchone()[0]
    queue = [
        {"what": "Refused at the gate", "count": refused, "tone": "#A8231B" if refused else "#E4E0D6",
         "screen": "person"},
        {"what": "“Signed up as” requests", "count": requests,
         "tone": "#AE7338" if requests else "#E4E0D6", "screen": "person"},
        # Only a job while payment is a gate.
        *([] if s["claim_requires"] == "none" else
          [{"what": "Payments to check", "count": people["pending"] or 0,
            "tone": "#AE7338" if people["pending"] else "#E4E0D6", "screen": "person"}]),
        {"what": "Games under half full", "count": thin, "tone": "#E4E0D6", "screen": "schedules"},
        {"what": "Bot messages that failed", "count": failed,
         "tone": "#A8231B" if failed else "#E4E0D6", "screen": "audit"},
    ]
    return {
        "stats": stats,
        "bars": [{"starts_at": gm["starts_at"], "taken": gm["booked"], "capacity": gm["capacity"],
                  "running": gm["running"]} for gm in board["escape"]],
        "queue": queue,
        "capacity": board["escape"][0]["capacity"] if board["escape"] else int(s["capacity"]),
        "seats_total": board["seats_total"],
        "test_clock": bool(s["test_clock"]),
        "notify_mode": s["notify_mode"],
    }


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

CLOCK_KEYS = ("doors_open", "doors_close", "first_game", "last_game", "jam_first", "jam_last",
              "test_clock_at", "doors_message_at")
CUE_KEYS = ("hint_1", "hint_2", "hint_3", "forced_merge")
HANDLE_KEYS = ("help_handle", "gm_handle", "actor_handle")
CHOICES = {
    "phone_unlock_mode": ("gm_start", "clock"),
    "claim_requires": ("verified", "submitted", "none"),
    "notify_mode": notify.MODES,
}
MINIMUM = {"capacity": 1, "game_minutes": 1, "phone_minutes": 1, "jam_slot_minutes": 5, "jam_per_person": 1,
           "jam_capacity": 1,
           "max_party": 1, "backup_minutes": 1, "backup_keep": 1, "reminder_minutes": 1,
           "lookup_rate_limit": 1, "claimed_handle_limit": 1, "friend_fail_limit": 1}
# Settings that hold several lines, and how long each may be.
LONG_TEXT = {"price_list": 4000}
CLOCK_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
CUE_RE = re.compile(r"^\d{1,2}:[0-5]\d$")


def settings_view(conn):
    s = db.get_settings(conn)
    values = {k: v for k, v in s.items() if k not in config.INTERNAL_SETTINGS}
    values["always_allow"] = ", ".join(sorted(config.ALWAYS_ALLOW_HANDLES))
    return {
        "values": values,
        "placeholders": [k for k in config.PLACEHOLDER_SETTINGS if not str(s.get(k) or "").strip()],
        "readonly": ["always_allow"],
        # One "collected at" row per made-to-order item. The console builds
        # them from this list rather than naming the items itself.
        "order_items": [{"key": k, "label": label} for k, label, _ in config.ORDER_ITEMS],
    }


def _coerce(key, value):
    default = config.DEFAULT_SETTINGS[key]
    if isinstance(default, bool):
        if not isinstance(value, bool):
            raise ClaimError("VALIDATION_FAILED", f"{key} must be on or off.")
        return value
    if isinstance(default, int):
        try:
            n = int(value)
        except (TypeError, ValueError):
            raise ClaimError("VALIDATION_FAILED", f"{key} must be a whole number.")
        if n < MINIMUM.get(key, 0) or n > 100000:
            raise ClaimError("VALIDATION_FAILED", f"{key} must be at least {MINIMUM.get(key, 0)}.")
        return n
    if key in LONG_TEXT:
        # Several lines, kept as lines: the price list is a list.
        lines = [" ".join(line.split()) for line in str(value or "").splitlines()]
        return "\n".join(lines).strip()[:LONG_TEXT[key]]
    text = _clean(value, 200)
    if key in CLOCK_KEYS:
        m = CLOCK_RE.match(text)
        if not m:
            raise ClaimError("VALIDATION_FAILED", f"{key} must be a time like 17:30.")
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    if key in CUE_KEYS and not CUE_RE.match(text):
        raise ClaimError("VALIDATION_FAILED", f"{key} must be minutes:seconds, like 4:30.")
    if key in CHOICES and text not in CHOICES[key]:
        raise ClaimError("VALIDATION_FAILED", f"{key} must be one of: {', '.join(CHOICES[key])}.")
    if key in HANDLE_KEYS:
        return normalise_handle(text)
    return text


def save_settings(conn, changes, by, now):
    if not isinstance(changes, dict) or not changes:
        raise ClaimError("VALIDATION_FAILED", "Nothing to save.")
    editable = set(config.DEFAULT_SETTINGS) - set(config.INTERNAL_SETTINGS)
    unknown = [k for k in changes if k not in editable]
    if unknown:
        raise ClaimError("VALIDATION_FAILED", "These can't be changed here: " + ", ".join(unknown))
    current = db.get_settings(conn)
    new = {k: _coerce(k, v) for k, v in changes.items()}
    merged = dict(current, **new)
    for a, b, what in (("doors_open", "doors_close", "Doors must open before they close."),
                       ("first_game", "last_game", "The first game must be before the last."),
                       ("jam_first", "jam_last", "The first jam slot must be before the last.")):
        if merged[a] > merged[b]:
            raise ClaimError("VALIDATION_FAILED", what)
    changed = {k: v for k, v in new.items() if v != current.get(k)}

    def run():
        for k, v in changed.items():
            db.set_setting(conn, k, v, by=by)
            db.audit(conn, "admin", "Setting changed", actor_name=by, entity="setting", entity_id=k,
                     details={"before": current.get(k), "after": v})
        return None

    bookings._run(conn, run)
    out = {"saved": len(changed)}
    if any(k in config.SCHEDULE_SETTINGS for k in changed):
        report = bookings.generate_slots(conn)
        out["schedule"] = report
        # Two ways a schedule change can leave people in a bad place, and
        # neither shows up anywhere else. A stranded time keeps its bookings
        # but is gone from the schedule; an over-full game holds more people
        # than it now seats. Both are the admin's to sort out by moving
        # people, so name the games rather than burying it in a count.
        warnings = []
        for room, label in (("escape", "game"), ("jam", "jam slot")):
            r = report.get(room) or {}
            for o in r.get("over", []):
                warnings.append(f"The {o['at']} {label} now seats {o['capacity']} "
                                f"but {o['booked']} are booked. Move "
                                f"{o['booked'] - o['capacity']} of them.")
            if r.get("stuck"):
                warnings.append(f"Still booked, so kept off the new schedule: "
                                f"{', '.join(r['stuck'])}. Move those people, then save again.")
        if warnings:
            out["warnings"] = warnings
    return out


# ---------------------------------------------------------------------------
# Audit and backups
# ---------------------------------------------------------------------------

AUDIT_LIMIT = 300
HIDDEN_DETAILS = {"before", "after", "pass_code", "claim_id", "tg_user_id", "slot_id", "expires_at",
                  "first_claim_id", "role"}


def _value(v):
    if isinstance(v, list):
        return ", ".join(_value(x) for x in v)
    if isinstance(v, dict):
        return " ".join(f"{k} {_value(x)}" for k, x in v.items())
    return "—" if v is None or v == "" else str(v)


def _details(raw):
    try:
        d = json.loads(raw or "{}")
    except ValueError:
        return str(raw or "")
    if not isinstance(d, dict):
        return _value(d)
    parts = [f"{k.replace('_', ' ')}: {_value(v)}" for k, v in d.items()
             if k not in HIDDEN_DETAILS and v not in (None, "", [], False)]
    before, after = d.get("before"), d.get("after")
    if isinstance(before, dict) and isinstance(after, dict):
        parts += [f"{k.replace('_', ' ')}: {_value(before.get(k))} → {_value(after.get(k))}"
                  for k in after if before.get(k) != after.get(k)]
    elif "before" in d and not isinstance(before, dict):
        parts.append(f"{_value(before)} → {_value(after)}")
    return " · ".join(parts)


def audit_view(conn, actor=None, action=None, search=None):
    where, args = ["1=1"], []
    if actor:
        where.append("COALESCE(actor_name, actor_type) = ?")
        args.append(actor)
    if action:
        where.append("action = ?")
        args.append(action)
    search = _clean(search, 80)
    if search:
        like = "%" + search.replace("%", "") + "%"
        handle = normalise_handle(search)
        ids = [str(r["id"]) for r in conn.execute(
            "SELECT id FROM attendees WHERE name LIKE ? OR handle LIKE ? OR pass_code LIKE ?",
            (like, "%" + handle + "%" if handle else like, like))]
        terms = ["action LIKE ?", "details LIKE ?", "entity_id LIKE ?", "actor_name LIKE ?"]
        args += [like] * 4
        if ids:
            terms.append(f"(entity='attendee' AND entity_id IN ({','.join('?' * len(ids))}))")
            args += ids
        where.append("(" + " OR ".join(terms) + ")")
    clause = " AND ".join(where)
    total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    rows = conn.execute(f"SELECT * FROM audit_log WHERE {clause} ORDER BY id DESC LIMIT ?",  # noqa: S608
                        (*args, AUDIT_LIMIT)).fetchall()
    handles = {str(r["id"]): r["handle"] or r["name"] for r in conn.execute("SELECT id, handle, name FROM attendees")}
    slots = {str(r["id"]): claims.clock(r["starts_at"]) for r in conn.execute("SELECT id, starts_at FROM slots")}

    def entity(r):
        if r["entity"] == "attendee":
            h = handles.get(r["entity_id"] or "", r["entity_id"])
            return "@" + h if h and not str(h).startswith("@") and " " not in str(h) else h
        if r["entity"] == "slot":
            return "game " + slots.get(r["entity_id"] or "", "?")
        return " ".join(x for x in (r["entity"], r["entity_id"]) if x)

    return {
        "total": total,
        "shown": len(rows),
        "entries": [{"id": r["id"], "at": _day_clock(r["at"]),
                     "actor": r["actor_name"] or r["actor_type"], "station": r["station"] or "",
                     "action": r["action"], "entity": entity(r), "details": _details(r["details"])}
                    for r in rows],
        "actors": [r[0] for r in conn.execute(
            "SELECT DISTINCT COALESCE(actor_name, actor_type) FROM audit_log ORDER BY 1")],
        "actions": [r[0] for r in conn.execute("SELECT DISTINCT action FROM audit_log ORDER BY 1")],
        "backup": backup_info(conn),
        # The exports tab also carries the receipt-copy card, because the
        # Paperform links expire before the event and this is the screen the
        # organiser opens when thinking about "saving things off the laptop".
        "receipts": receipts.status(conn),
    }


def _size(n):
    return f"{n / 1_048_576:.1f} MB" if n >= 1_048_576 else f"{max(1, n // 1024)} KB"


def backup_info(conn):
    copies = sorted(config.BACKUP_DIR.glob("app-*.db"))
    last = None
    if copies:
        stamp = datetime.fromtimestamp(copies[-1].stat().st_mtime, timezone.utc)
        last = _day_clock(stamp.replace(microsecond=0).isoformat())
    size = config.DB_PATH.stat().st_size if config.DB_PATH.exists() else 0
    return {"last_at": last or "never", "every_minutes": int(db.get_setting(conn, "backup_minutes", 10)),
            "keep": int(db.get_setting(conn, "backup_keep", 36)), "count": len(copies),
            "db_size": _size(size)}


def backup_due(conn, now=None):
    """True when the newest copy is older than the backup interval."""
    now = now or datetime.now(timezone.utc)
    copies = sorted(config.BACKUP_DIR.glob("app-*.db"))
    if not copies:
        return True
    newest = datetime.fromtimestamp(copies[-1].stat().st_mtime, timezone.utc)
    return now - newest >= timedelta(minutes=int(db.get_setting(conn, "backup_minutes", 10)))


def backup(conn, by):
    target = db.backup_now(keep=int(db.get_setting(conn, "backup_keep", 36)))
    db.audit(conn, "admin", "Backup made", actor_name=by, entity="backup", entity_id=target.name)
    return {"file": target.name, **backup_info(conn)}


# ---------------------------------------------------------------------------
# Roster, walk-ins
# ---------------------------------------------------------------------------

def roster_view(conn):
    c = conn.execute(
        "SELECT SUM(status='active' AND is_test=0) active, SUM(status!='active') inactive, "
        "SUM(source='walk_in' AND status='active') walk_ins FROM attendees").fetchone()
    runs = []
    for r in conn.execute("SELECT * FROM import_runs WHERE committed_at IS NOT NULL ORDER BY id DESC LIMIT 10"):
        counts = json.loads(r["counts"] or "{}")
        runs.append({"at": _day_clock(r["committed_at"]), "file_name": r["file_name"] or "—",
                     "summary": f"{counts.get('new', 0)} new, {counts.get('changed', 0)} changed, "
                                f"{counts.get('missing', 0)} missing"})
    return {"active": c["active"] or 0, "inactive": c["inactive"] or 0, "walk_ins": c["walk_ins"] or 0,
            "runs": runs}


def roster_preview(conn, upload, by):
    if upload is None or not upload.filename:
        raise ClaimError("VALIDATION_FAILED", "Choose the Paperform .xlsx export.")
    if not upload.filename.lower().endswith(".xlsx"):
        raise ClaimError("VALIDATION_FAILED", "That isn't an .xlsx file. Export the sheet from Paperform.")
    config.IMPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = config.IMPORTS_DIR / f"upload-{stamp}.xlsx"
    upload.save(path)
    try:
        rows = roster.read_export(path)
    except ValueError as exc:
        raise ClaimError("VALIDATION_FAILED", str(exc))
    except Exception:  # noqa: BLE001 - a corrupt file is the admin's to fix
        raise ClaimError("VALIDATION_FAILED", "That file couldn't be read. Export it from Paperform again.")
    out = roster.preview(conn, rows, upload.filename)
    db.audit(conn, "admin", "Roster previewed", actor_name=by, entity="import_run",
             entity_id=out["run_id"], details=out["counts"])
    return out


def roster_commit(conn, run_id, by):
    try:
        return roster.commit(conn, int(run_id), actor=by)
    except (TypeError, ValueError) as exc:
        raise ClaimError("VALIDATION_FAILED", str(exc) or "No such import.")


def add_walk_in(conn, body, by):
    name = _clean(body.get("name"), 80)
    handle = normalise_handle(body.get("handle"))
    email = _clean(body.get("email"), 120)
    if not name or not handle:
        raise ClaimError("VALIDATION_FAILED", "A name and a Telegram username are both needed.")
    if not looks_like_handle(handle):
        raise ClaimError("VALIDATION_FAILED", f"@{handle} isn't a Telegram username (5-32 letters, digits or _).")
    taken = conn.execute("SELECT name, status FROM attendees WHERE handle=?", (handle,)).fetchone()
    if taken:
        raise ClaimError("HANDLE_TAKEN", f"@{handle} is already on the list as {taken['name']}"
                                         + (" (inactive)." if taken["status"] != "active" else "."))
    now = db.utcnow()

    def run():
        code = db.new_code(conn, "attendees", "pass_code")
        cur = conn.execute(
            "INSERT INTO attendees (name, email, handle, handle_raw, source, status, payment_status, "
            "pass_code, created_at, updated_at) VALUES (?,?,?,?,'walk_in','active','missing',?,?,?)",
            (name, email or None, handle, "@" + handle, code, now, now))
        db.audit(conn, "admin", "Walk-in added", actor_name=by, entity="attendee", entity_id=cur.lastrowid,
                 details={"name": name, "handle": handle})
        return {"id": cur.lastrowid, "name": name, "handle": handle, "pass_code": code}

    return bookings._run(conn, run)


# ---------------------------------------------------------------------------
# The gate list: link or dismiss; unlink (§9 rules 3, 7)
# ---------------------------------------------------------------------------

def resolve_attempt(conn, attempt_id, body, by):
    how = body.get("action")
    a = conn.execute("SELECT * FROM gate_attempts WHERE id=?", (attempt_id,)).fetchone()
    if a is None:
        raise ClaimError("NOT_FOUND", "No such entry.")
    if a["resolved_at"]:
        raise ClaimError("VALIDATION_FAILED", "Someone already dealt with this one.")
    if how not in ("link", "dismiss"):
        raise ClaimError("VALIDATION_FAILED", "Link or dismiss.")
    now = db.utcnow()

    def run():
        details = {"outcome": a["outcome"], "tg_username": a["tg_username"], "claimed": a["claimed_handle"]}
        if how == "link":
            person = get_attendee(conn, body.get("attendee_id"))
            if not a["tg_user_id"]:
                raise ClaimError("VALIDATION_FAILED", "That attempt has no Telegram account to link.")
            if person["tg_user_id"] and person["tg_user_id"] != a["tg_user_id"]:
                raise ClaimError("LINKED_ELSEWHERE", f"{person['name']} is already linked to another "
                                                     "Telegram account. Unlink it first.")
            other = conn.execute("SELECT name FROM attendees WHERE tg_user_id=? AND id!=?",
                                 (a["tg_user_id"], person["id"])).fetchone()
            if other:
                raise ClaimError("LINKED_ELSEWHERE", f"That Telegram account already belongs to {other['name']}.")
            conn.execute("UPDATE attendees SET tg_user_id=?, tg_first_name=COALESCE(tg_first_name, ?), "
                         "status='active', updated_at=? WHERE id=?",
                         (a["tg_user_id"], a["tg_first_name"], now, person["id"]))
            details["linked_to"] = person["id"]
            db.audit(conn, "admin", "Telegram account linked by admin", actor_name=by, entity="attendee",
                     entity_id=person["id"], details=details)
        else:
            db.audit(conn, "admin", "Gate refusal dismissed", actor_name=by, entity="gate_attempt",
                     entity_id=attempt_id, details=details)
        # Every open entry from the same Telegram account is dealt with at once.
        if a["tg_user_id"]:
            conn.execute("UPDATE gate_attempts SET resolved_by=?, resolved_at=? "
                         "WHERE tg_user_id=? AND resolved_at IS NULL", (by, now, a["tg_user_id"]))
        else:
            conn.execute("UPDATE gate_attempts SET resolved_by=?, resolved_at=? WHERE id=?", (by, now, attempt_id))
        return {"resolved": how}

    return bookings._run(conn, run)


def unlink(conn, attendee_id, reason, by):
    person = get_attendee(conn, attendee_id)
    reason = _reason(reason)
    if not person["tg_user_id"]:
        raise ClaimError("VALIDATION_FAILED", "This person isn't linked to a Telegram account.")

    def run():
        conn.execute("UPDATE attendees SET tg_user_id=NULL, updated_at=? WHERE id=?", (db.utcnow(), person["id"]))
        db.audit(conn, "admin", "Telegram account unlinked", actor_name=by, entity="attendee",
                 entity_id=person["id"], details={"reason": reason,
                                                  "before": {"tg_user_id": person["tg_user_id"]},
                                                  "after": {"tg_user_id": None}})
        return {"unlinked": True}

    return bookings._run(conn, run)


# ---------------------------------------------------------------------------
# Schedules: block a slot, move a person
# ---------------------------------------------------------------------------

def block_slot(conn, slot_id, blocked, reason, by):
    slot = conn.execute("SELECT * FROM slots WHERE id=?", (slot_id,)).fetchone()
    if slot is None:
        raise ClaimError("NOT_FOUND", "No such slot.")
    blocked = bool(blocked)
    if blocked:
        reason = _reason(reason)
    table = "escape_bookings" if slot["room"] == "escape" else "jam_bookings"
    live = "('booked','checked_in')" if slot["room"] == "escape" else "('confirmed')"

    def run():
        conn.execute("UPDATE slots SET is_blocked=?, block_reason=? WHERE id=?",
                     (int(blocked), reason if blocked else None, slot["id"]))
        still = [("@" + r["handle"]) if r["handle"] else r["name"] for r in conn.execute(
            f"SELECT a.handle, a.name FROM {table} b JOIN attendees a ON a.id=b.attendee_id "  # noqa: S608
            f"WHERE b.slot_id=? AND b.status IN {live}", (slot["id"],))]
        db.audit(conn, "admin", ("Slot blocked" if blocked else "Slot unblocked"), actor_name=by,
                 entity="slot", entity_id=slot["id"],
                 details={"room": slot["room"], "time": claims.clock(slot["starts_at"]),
                          "reason": reason if blocked else None, "still_booked": still})
        return {"blocked": blocked, "still_booked": still}

    return bookings._run(conn, run)


def move_person(conn, attendee_id, slot_id, reason, by, now):
    """Move one person's escape seat to another game. The half is worked out
    again for the new game, and the person is told."""
    person = get_attendee(conn, attendee_id)
    reason = _clean(reason) or "moved by the front desk"

    def run():
        b = bookings.active_booking(conn, person["id"])
        if b is None:
            raise ClaimError("NO_BOOKING", f"{person['name']} has no escape game to move.")
        target = conn.execute("SELECT * FROM slots WHERE id=? AND room='escape'", (slot_id,)).fetchone()
        if target is None:
            raise ClaimError("NOT_FOUND", "No such game.")
        if target["id"] == b["slot_id"]:
            raise ClaimError("VALIDATION_FAILED", "They're already in that game.")
        if target["is_blocked"]:
            raise ClaimError("SLOT_BLOCKED", "That game is blocked.")
        if bookings._taken(conn, target["id"]) >= target["capacity"]:
            raise ClaimError("SLOT_FULL", "That game is full.")
        if bookings._escape_clashes(conn, person["id"], target):
            raise ClaimError("TIME_CONFLICT", f"That game clashes with {person['name']}'s jam slot.")
        zone = bookings._zone(conn, target["id"])
        conn.execute("UPDATE escape_bookings SET slot_id=?, zone=?, zone_changed_by=?, reminder_sent_at=NULL "
                     "WHERE id=?", (target["id"], zone, by, b["id"]))
        notify.queue(conn, person["id"], "moved",
                     notify.text_moved(b["starts_at"], target["starts_at"], notify.place(conn, "escape")),
                     go=notify.GO_TICKET, expires_at=datetime.fromisoformat(target["starts_at"]), now=now)
        db.audit(conn, "admin", "Escape booking moved", actor_name=by, entity="attendee",
                 entity_id=person["id"],
                 details={"ref": b["ref_code"], "reason": reason,
                          "before": {"game": claims.clock(b["starts_at"])},
                          "after": {"game": claims.clock(target["starts_at"]), "half": zone}})
        return {"moved_to": claims.local_iso(target["starts_at"]), "zone": zone}

    return bookings._run(conn, run)
