"""The console's remaining screens: Overview, Settings, Audit and backups,
Roster, walk-ins, linking people at the gate, and schedule changes
(§9 rules 12, 22, 32-36, §10).

Every write here is admin-only (app.py decides) and leaves an audit row with
before and after values.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
    # account days early. "At the event" counts only from the moment the doors
    # open on the day, so a rehearsal never counts.
    #
    # Since 24 Sep it counts **two** ways in, either of which is enough: the
    # front desk scanned them, or they redeemed something on their pass. The
    # desk is one person and the counters are three, so a scan was never going
    # to see everybody. `claims.at_the_event` holds the definition.
    doors = claims.doors_bound(conn)
    here = conn.execute(
        "SELECT COUNT(*) FROM attendees a WHERE a.status='active' AND a.is_test=0 "
        f"AND {claims.at_the_event('a')}",  # noqa: S608 - fixed fragment, values bound
        (doors, doors)).fetchone()[0]
    seen = conn.execute(
        "SELECT COUNT(*) FROM attendees a WHERE a.status='active' AND a.is_test=0 "
        f"AND {claims.ever_seen('a')}").fetchone()[0]  # noqa: S608 - fixed fragment
    early = seen - here
    pct = round(100 * here / total) if total else 0
    pct_linked = round(100 * (people["linked"] or 0) / total) if total else 0
    stats = [
        {"label": "Signed up", "value": str(total),
         "sub": f"{people['walk_ins'] or 0} walk-in{'s' if (people['walk_ins'] or 0) != 1 else ''}",
         "tone": "#3C4654"},
        {"label": "Opened the app", "value": str(people["linked"] or 0),
         "sub": f"{pct_linked}% of the list, any time", "tone": "#3C4654"},
        {"label": "At the event", "value": str(here),
         "sub": f"{pct}% of the list · checked in or redeemed, "
                f"from {notify.hhmm_text(s['doors_open'])}"
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
HANDLE_KEYS = ("help_handle", "gm_handle", "actor_handle")
CHOICES = {
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
    # Adding somebody to the escape room's test group is a request to let them
    # in, and the only way in is the bot's message. Send it here rather than
    # leaving them to find `python manage.py phone-test` (23 Sep). Only the
    # handles just added: saving something else on the same screen should not
    # message the whole group again.
    if "phone_always_handles" in changed:
        from services import game
        added = game.always_handles({"phone_always_handles": changed["phone_always_handles"]})
        added -= game.always_handles({"phone_always_handles": current.get("phone_always_handles")})
        if added:
            out["phone_test"] = bookings._run(
                conn, lambda: game.send_phone_to_testers(
                    conn, dict(merged), only=added, actor_name=by))
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
    # Webhook sign-ups arrive one at a time, so they are audit rows rather
    # than import runs — 150 of them would push every real upload off the list
    # above. Count them instead, and count what was refused: a refusal is the
    # only sign that somebody signed up and is not on the list.
    w = conn.execute(
        "SELECT SUM(action='Sign-up from Paperform') took, "
        "SUM(action='Paperform sign-up refused') refused FROM audit_log").fetchone()
    return {"active": c["active"] or 0, "inactive": c["inactive"] or 0, "walk_ins": c["walk_ins"] or 0,
            "webhook": w["took"] or 0, "webhook_refused": w["refused"] or 0,
            "runs": runs}


UPLOAD_KINDS = (".xlsx", ".csv")


def _read_and_preview(conn, path, file_name, mapping, by):
    """Read the saved file with `mapping` (or a guess) and price up the import."""
    try:
        headers, rows = roster.read_table(path)
    except ValueError as exc:
        raise ClaimError("VALIDATION_FAILED", str(exc))
    except Exception:  # noqa: BLE001 - a corrupt file is the admin's to fix
        raise ClaimError("VALIDATION_FAILED", "That file couldn't be read. Export it again.")
    mapping = mapping or roster.guess_mapping(headers)
    try:
        roster.check_mapping(mapping)
    except ValueError as exc:
        # Not an error to bounce back: this is the file the matching exists
        # for, so hand back the columns and let the admin say which is which.
        return roster.unmatched_run(conn, file_name, path, headers, rows, mapping, str(exc))
    mapped = roster.map_rows(headers, rows, mapping)
    out = roster.preview(conn, mapped, file_name, source_path=path, headers=headers,
                         mapping=mapping)
    out["examples"] = roster.first_values(headers, rows)
    db.audit(conn, "admin", "Roster previewed", actor_name=by, entity="import_run",
             entity_id=out["run_id"], details=out["counts"])
    return out


def roster_preview(conn, upload, by, mapping=None):
    if upload is None or not upload.filename:
        raise ClaimError("VALIDATION_FAILED", "Choose the sign-up export.")
    suffix = next((k for k in UPLOAD_KINDS if upload.filename.lower().endswith(k)), None)
    if suffix is None:
        raise ClaimError("VALIDATION_FAILED",
                         "That isn't an .xlsx or .csv file. Export the sheet from Paperform.")
    config.IMPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = config.IMPORTS_DIR / f"upload-{stamp}{suffix}"
    upload.save(path)
    return _read_and_preview(conn, path, upload.filename, _clean_mapping(mapping), by)


def _clean_mapping(mapping):
    """Only the six fields, only real strings — it arrives from the browser."""
    if not isinstance(mapping, dict):
        return None
    out = {}
    for field in roster.FIELDS:
        value = mapping.get(field)
        out[field] = value.strip() if isinstance(value, str) and value.strip() else None
    return out if any(out.values()) else None


def roster_remap(conn, run_id, mapping, by):
    """Price the same upload up again with the columns matched differently."""
    run = conn.execute("SELECT * FROM import_runs WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        raise ClaimError("NOT_FOUND", f"No import run {run_id}.")
    if run["committed_at"]:
        raise ClaimError("VALIDATION_FAILED", "That import was already committed.")
    report = json.loads(run["report"] or "{}")
    path = report.get("source_path")
    if not path or not Path(path).exists():
        raise ClaimError("VALIDATION_FAILED",
                         "The uploaded file is no longer on the server. Upload it again.")
    cleaned = _clean_mapping(mapping)
    if cleaned is None:
        raise ClaimError("VALIDATION_FAILED", "Match at least one column.")
    # The audit only wants the runs that said something; a half-matched
    # attempt on the way to the right answer is noise.
    return _read_and_preview(conn, Path(path), run["file_name"], cleaned, by)


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
# Schedules: block a slot
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


# ---------------------------------------------------------------------------
# Seating: who is in which slot, and moving them between slots
# ---------------------------------------------------------------------------
#
# Schedules counts seats. This names them, because you cannot move somebody
# you cannot see, and until 24 Sep the only way to move anyone was to type a
# time into a box that matched it back as text — "6.45" never found the 6:45
# game, and every game that had started, finished or filled was left off the
# list it offered, so the answer came back as "no open game at that time"
# whatever you typed.
#
# The rule that shapes all of it: **a move never takes a seat off anyone
# else.** A target with no room is refused; nobody is bumped to make space.
# Times are not a reason to refuse — the front desk moves people into games
# that have started and out of games that are over, which is most of what
# this is for.


def _slot_of(conn, slot_id, room, what):
    try:
        slot_id = int(slot_id)
    except (TypeError, ValueError):
        raise ClaimError("VALIDATION_FAILED", f"Pick a {what}.")
    slot = conn.execute("SELECT * FROM slots WHERE id=? AND room=?", (slot_id, room)).fetchone()
    if slot is None:
        raise ClaimError("NOT_FOUND", f"No such {what}.")
    return slot


def _by(row):
    """Who booked this seat, when it was not the person sitting in it."""
    if not row["booked_by_id"] or row["booked_by_id"] == row["attendee_id"]:
        return None
    return "@" + row["owner_handle"] if row["owner_handle"] else row["owner_name"]


def _seat_columns(b):
    """The columns every seat on the board needs, for either table's alias."""
    return (f"{b}.ref_code, {b}.attendee_id, {b}.booked_by_id, a.name, a.handle, "
            "o.handle AS owner_handle, o.name AS owner_name")


def seating_board(conn, now):
    """Both rooms, slot by slot, with the names in each one."""
    cfg = bookings._settings(conn)
    escape = []
    for sl in bookings._slots(conn, "escape"):
        rows = conn.execute(
            f"SELECT {_seat_columns('b')}, b.status FROM escape_bookings b "  # noqa: S608
            "JOIN attendees a ON a.id = b.attendee_id "
            "LEFT JOIN attendees o ON o.id = b.booked_by_id "
            "WHERE b.slot_id=? AND b.status IN ('booked','checked_in') "
            "ORDER BY b.created_at, b.id", (sl["id"],)).fetchall()
        starts, ends = bookings._dt(sl["starts_at"]), bookings._dt(sl["ends_at"])
        escape.append({
            "id": sl["id"], "starts_at": claims.local_iso(sl["starts_at"]),
            "ends_at": claims.local_iso(sl["ends_at"]),
            "capacity": sl["capacity"], "booked": len(rows),
            "blocked": bool(sl["is_blocked"]), "block_reason": sl["block_reason"],
            "running": starts <= now < ends, "done": now >= ends,
            "closed": starts - timedelta(minutes=cfg["cutoff"]) <= now < starts,
            "people": [{"attendee_id": r["attendee_id"], "name": r["name"],
                        "handle": r["handle"] or "", "ref": r["ref_code"],
                        "checked_in": r["status"] == "checked_in", "booked_by": _by(r)}
                       for r in rows],
        })
    jam = []
    for sl in bookings._slots(conn, "jam"):
        rows = conn.execute(
            f"SELECT {_seat_columns('j')}, j.instrument FROM jam_bookings j "  # noqa: S608
            "JOIN attendees a ON a.id = j.attendee_id "
            "LEFT JOIN attendees o ON o.id = j.booked_by_id "
            "WHERE j.slot_id=? AND j.status='confirmed' "
            "ORDER BY j.created_at, j.id", (sl["id"],)).fetchall()
        starts, ends = bookings._dt(sl["starts_at"]), bookings._dt(sl["ends_at"])
        held = {r["instrument"] for r in rows}
        jam.append({
            "id": sl["id"], "starts_at": claims.local_iso(sl["starts_at"]),
            "ends_at": claims.local_iso(sl["ends_at"]),
            "capacity": sl["capacity"], "booked": len(rows),
            "blocked": bool(sl["is_blocked"]), "block_reason": sl["block_reason"],
            "running": starts <= now < ends, "done": now >= ends,
            # A jam seat is an instrument, so what is free here is what a name
            # dragged in can actually be given.
            "free": [{"key": k, "label": config.INSTRUMENT_LABELS[k]}
                     for k in config.INSTRUMENT_KEYS if k not in held],
            "people": [{"attendee_id": r["attendee_id"], "name": r["name"],
                        "handle": r["handle"] or "", "ref": r["ref_code"],
                        "instrument": r["instrument"] or "",
                        "instrument_label": config.INSTRUMENT_LABELS.get(r["instrument"], ""),
                        "booked_by": _by(r)}
                       for r in rows],
        })
    return {"escape": escape, "jam": jam,
            "instruments": [{"key": k, "label": lab} for k, lab in config.INSTRUMENTS],
            "seats_taken": sum(g["booked"] for g in escape),
            "seats_total": sum(g["capacity"] for g in escape),
            "jam_seats_taken": sum(j["booked"] for j in jam),
            "jam_seats_total": sum(j["capacity"] for j in jam)}


# ---------------------------------------------------------------------------
# One move
# ---------------------------------------------------------------------------
#
# `check_room` is on for a move made on its own and off inside a batch, where
# the room has already been counted against the evening as it will be once
# every move is saved. It is the only difference between the two: a batch
# still refuses a blocked slot, a clash, or a seat somebody already holds.

def _escape_move(conn, person, slot_id, reason, by, now, check_room=True):
    """Move one escape seat. No transaction of its own, so a batch can hold one."""
    b = bookings.active_booking(conn, person["id"])
    if b is None:
        raise ClaimError("NO_BOOKING", f"{person['name']} has no escape game to move.")
    target = _slot_of(conn, slot_id, "escape", "game")
    if target["id"] == b["slot_id"]:
        raise ClaimError("VALIDATION_FAILED", f"{person['name']} is already in that game.")
    if target["is_blocked"]:
        raise ClaimError("SLOT_BLOCKED",
                         f"The {claims.clock(target['starts_at'])} game is blocked. Unblock it first.")
    taken = bookings._taken(conn, target["id"])
    if check_room and taken >= target["capacity"]:
        raise ClaimError("SLOT_FULL",
                         f"The {claims.clock(target['starts_at'])} game is full — "
                         f"{taken} of {target['capacity']} seats are taken. Nobody was moved.",
                         seats_left=0)
    if bookings._escape_clashes(conn, person["id"], target):
        raise ClaimError("TIME_CONFLICT",
                         f"The {claims.clock(target['starts_at'])} game runs over "
                         f"{person['name']}'s jam slot. Move the jam slot first.")
    conn.execute("UPDATE escape_bookings SET slot_id=?, reminder_sent_at=NULL WHERE id=?",
                 (target["id"], b["id"]))
    told = _tell_them_moved(
        conn, person, "moved",
        notify.text_moved(b["starts_at"], target["starts_at"], notify.place(conn, "escape")),
        notify.GO_TICKET, target, now)
    db.audit(conn, "admin", "Escape booking moved", actor_name=by, entity="attendee",
             entity_id=person["id"],
             details={"ref": b["ref_code"], "reason": reason,
                      "before": {"game": claims.clock(b["starts_at"])},
                      "after": {"game": claims.clock(target["starts_at"])}})
    return {"room": "escape", "who": notify.who(person), "ref": b["ref_code"],
            "from": claims.clock(b["starts_at"]), "to": claims.clock(target["starts_at"]),
            "told": told, "moved_to": claims.local_iso(target["starts_at"])}


def _jam_seat_of(conn, person, ref):
    """The jam seat a move is about. Somebody may hold more than one, so the
    ref says which; one seat needs no ref."""
    held = bookings.jam_bookings_of(conn, person["id"])
    if not held:
        raise ClaimError("NO_BOOKING", f"{person['name']} has no jam slot to move.")
    ref = _clean(ref, 12).upper()
    if ref:
        seat = next((r for r in held if r["ref_code"].upper() == ref), None)
        if seat is None:
            raise ClaimError("NOT_FOUND", f"{person['name']} has no jam slot {ref}.")
        return seat
    if len(held) > 1:
        raise ClaimError("VALIDATION_FAILED",
                         f"{person['name']} holds {len(held)} jam slots. Say which one.")
    return held[0]


def _jam_move(conn, person, ref, slot_id, instrument, reason, by, now, check_room=True):
    """Move one jam seat, on the instrument it is given."""
    seat = _jam_seat_of(conn, person, ref)
    target = _slot_of(conn, slot_id, "jam", "slot")
    if target["id"] == seat["slot_id"]:
        raise ClaimError("VALIDATION_FAILED", f"{person['name']} is already in that slot.")
    if target["is_blocked"]:
        raise ClaimError("SLOT_BLOCKED",
                         f"The {claims.clock(target['starts_at'])} slot is blocked. Unblock it first.")
    want = _instrument_for(person, instrument or seat["instrument"])
    seated = bookings._jam_seats(conn, target["id"])
    if any(r["attendee_id"] == person["id"] for r in seated):
        raise ClaimError("ALREADY_BOOKED",
                         f"{person['name']} already has a seat in the "
                         f"{claims.clock(target['starts_at'])} slot.")
    if check_room:
        free = [k for k in config.INSTRUMENT_KEYS if not any(r["instrument"] == k for r in seated)]
        if len(seated) >= target["capacity"]:
            raise ClaimError("SLOT_FULL",
                             f"The {claims.clock(target['starts_at'])} slot is full — "
                             f"{len(seated)} of {target['capacity']} seats are taken. "
                             "Nobody was moved.", seats_left=0)
        if want not in free:
            # Somebody else is on it. Naming what is free there is the whole
            # answer — taking it off them to make the move work is not.
            raise ClaimError("INSTRUMENT_TAKEN",
                             f"Someone already has the "
                             f"{config.INSTRUMENT_LABELS[want].lower()} in the "
                             f"{claims.clock(target['starts_at'])} slot. "
                             + _free_sentence(free) + " Nobody was moved.",
                             instruments=[want], free=free)
    game = bookings._busy_escape(conn, person["id"])
    if game and bookings._overlaps(game[0], game[1], bookings._dt(target["starts_at"]),
                                   bookings._dt(target["ends_at"])):
        raise ClaimError("TIME_CONFLICT",
                         f"The {claims.clock(target['starts_at'])} slot runs over "
                         f"{person['name']}'s escape game. Move the game first.")
    conn.execute("UPDATE jam_bookings SET slot_id=?, instrument=?, reminder_sent_at=NULL WHERE id=?",
                 (target["id"], want, seat["id"]))
    told = _tell_them_moved(
        conn, person, "jam_moved",
        notify.text_jam_moved(seat["starts_at"], target["starts_at"], target["ends_at"],
                              want, notify.place(conn, "jam")),
        notify.GO_BOOKINGS, target, now)
    db.audit(conn, "admin", "Jam booking moved", actor_name=by, entity="attendee",
             entity_id=person["id"],
             details={"ref": seat["ref_code"], "reason": reason,
                      "before": {"slot": claims.clock(seat["starts_at"]),
                                 "instrument": seat["instrument"]},
                      "after": {"slot": claims.clock(target["starts_at"]), "instrument": want}})
    return {"room": "jam", "who": notify.who(person), "ref": seat["ref_code"],
            "from": claims.clock(seat["starts_at"]), "to": claims.clock(target["starts_at"]),
            "instrument": want, "instrument_label": config.INSTRUMENT_LABELS[want],
            "told": told, "moved_to": claims.local_iso(target["starts_at"])}


def _tell_them_moved(conn, person, kind, text, go, target, now):
    """Queue the "you have been moved" message, and say whether it will go.

    It expires at the **end** of the slot they have been moved into, not the
    start. Expiring at the start is what every other message does, because a
    reminder for a game that has begun is noise — but a move is not a
    reminder. The front desk's commonest move is into the game running right
    now, and an expiry on the start time meant `deliver` marked that message
    "expired" before it ever sent: the one person who needed telling was the
    one never told. Past the end there is genuinely nothing to say, so that
    is where it stops.
    """
    ends = datetime.fromisoformat(target["ends_at"])
    notify.queue(conn, person["id"], kind, text, go=go, expires_at=ends, now=now)
    return ends > now


def _free_sentence(free):
    if not free:
        return "Nothing is free there."
    return "Free there: " + ", ".join(config.INSTRUMENT_LABELS[k].lower() for k in free) + "."


def _instrument_for(person, raw):
    """A seat booked before 19 Sep has no instrument on it, and a move has to
    name one rather than carry the blank across."""
    if not raw:
        raise ClaimError("VALIDATION_FAILED",
                         f"{person['name']}'s jam seat has no instrument on it. "
                         "Pick one for them.")
    return bookings._instrument(raw)


def move_person(conn, attendee_id, slot_id, reason, by, now):
    """Move one person's escape seat to another game, and tell them."""
    person = get_attendee(conn, attendee_id)
    reason = _clean(reason) or "moved by the front desk"
    return bookings._run(conn, lambda: _escape_move(conn, person, slot_id, reason, by, now))


def move_jam_person(conn, attendee_id, ref, slot_id, instrument, reason, by, now):
    """Move one person's jam seat to another slot, and tell them."""
    person = get_attendee(conn, attendee_id)
    reason = _clean(reason) or "moved by the front desk"
    return bookings._run(
        conn, lambda: _jam_move(conn, person, ref, slot_id, instrument, reason, by, now))


# ---------------------------------------------------------------------------
# A screenful of moves, saved together
# ---------------------------------------------------------------------------

MOVE_LIMIT = 60


def apply_moves(conn, moves, reason, by, now):
    """Save the moves staged on the Seating board — all of them, or none.

    Saved together because they are planned together. Applied one at a time,
    two people swapping games would fail on whichever went first: the game it
    is going to is full until the other one has left it. So the room is
    counted against the evening **as it will be once the whole batch is
    saved**, not as it stands now, and one `BEGIN IMMEDIATE` around the lot
    means a refusal leaves the evening exactly as it was.

    What is asked is only ever "is there room" — never "who can I take out to
    make room". Nobody is removed by a move.
    """
    if not isinstance(moves, list) or not moves:
        raise ClaimError("VALIDATION_FAILED", "Nothing to save.")
    if len(moves) > MOVE_LIMIT:
        raise ClaimError("VALIDATION_FAILED", f"Too many moves at once — the limit is {MOVE_LIMIT}.")
    reason = _clean(reason) or "moved on the Seating board"

    def run():
        # Read inside the transaction: on a live console the board on screen
        # is a few seconds old, and the moves have to be checked against the
        # evening as it is at the moment they are saved.
        plan = [_read_move(conn, m) for m in moves]
        seen = set()
        for m in plan:
            key = (m["room"], m["seat"]["id"])
            if key in seen:
                raise ClaimError("VALIDATION_FAILED",
                                 f"{m['person']['name']} is on the board twice. Undo one of them.")
            seen.add(key)
        _room_afterwards(conn, plan)
        # Jam rows move in two passes. One slot holds each instrument once, so
        # a pair swapping the drums would collide halfway through. Parking the
        # instrument — NULL, which the unique index lets repeat — and handing
        # it back as each row lands keeps every state in between legal.
        for m in plan:
            if m["room"] == "jam":
                conn.execute("UPDATE jam_bookings SET instrument=NULL WHERE id=?", (m["seat"]["id"],))
        done = []
        for m in plan:
            if m["room"] == "escape":
                done.append(_escape_move(conn, m["person"], m["slot_id"], reason, by, now,
                                         check_room=False))
            else:
                done.append(_jam_move(conn, m["person"], m["seat"]["ref_code"], m["slot_id"],
                                      m["instrument"], reason, by, now, check_room=False))
        db.audit(conn, "admin", "Seating saved", actor_name=by, entity="slots",
                 details={"reason": reason, "moves": [
                     {"who": d["who"], "room": d["room"], "from": d["from"], "to": d["to"]}
                     for d in done]})
        return done

    return {"moves": bookings._run(conn, run)}


def _read_move(conn, raw):
    """One staged move, read off the wire, with the seat it is about."""
    if not isinstance(raw, dict):
        raise ClaimError("VALIDATION_FAILED", "That is not a move.")
    room = str(raw.get("room") or "escape").strip().lower()
    if room not in ("escape", "jam"):
        raise ClaimError("VALIDATION_FAILED", "A move is either escape or jam.")
    person = get_attendee(conn, raw.get("attendee_id"))
    slot = _slot_of(conn, raw.get("slot_id"), room, "game" if room == "escape" else "slot")
    if room == "escape":
        seat = bookings.active_booking(conn, person["id"])
        if seat is None:
            raise ClaimError("NO_BOOKING", f"{person['name']} has no escape game to move.")
        instrument = None
    else:
        seat = _jam_seat_of(conn, person, raw.get("ref"))
        # Settled here, before anything is parked, so the second pass has an
        # instrument to hand back.
        instrument = _instrument_for(person, raw.get("instrument") or seat["instrument"])
    return {"room": room, "person": person, "seat": seat, "slot_id": slot["id"],
            "instrument": instrument}


def _room_afterwards(conn, plan):
    """Would every slot the batch touches still fit, once all of it is saved?

    Counting a slot as it stands now is what makes a swap impossible, and a
    swap is the front desk's most ordinary request.
    """
    for room, table, live in (("escape", "escape_bookings", "('booked','checked_in')"),
                              ("jam", "jam_bookings", "('confirmed')")):
        mine = [m for m in plan if m["room"] == room]
        for slot_id in {m["slot_id"] for m in mine} | {m["seat"]["slot_id"] for m in mine}:
            slot = conn.execute("SELECT * FROM slots WHERE id=?", (slot_id,)).fetchone()
            held = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE slot_id=? "  # noqa: S608
                                f"AND status IN {live}", (slot_id,)).fetchone()[0]
            leaving = sum(1 for m in mine if m["seat"]["slot_id"] == slot_id)
            arriving = sum(1 for m in mine if m["slot_id"] == slot_id)
            after = held - leaving + arriving
            if after > slot["capacity"]:
                raise ClaimError(
                    "SLOT_FULL",
                    f"The {claims.clock(slot['starts_at'])} "
                    f"{'game' if room == 'escape' else 'slot'} would hold {after} people with "
                    f"{slot['capacity']} seats. Nothing was saved.",
                    seats_left=max(0, slot["capacity"] - (held - leaving)))
    # The same question for the instruments: two people cannot arrive in one
    # slot on the same one, and neither can an arrival and somebody staying.
    moving = {m["seat"]["id"] for m in plan if m["room"] == "jam"}
    for slot_id in {m["slot_id"] for m in plan if m["room"] == "jam"}:
        slot = conn.execute("SELECT * FROM slots WHERE id=?", (slot_id,)).fetchone()
        after = {row["instrument"]: row["attendee_id"]
                 for row in bookings._jam_seats(conn, slot_id) if row["id"] not in moving}
        for m in plan:
            if m["room"] != "jam" or m["slot_id"] != slot_id:
                continue
            want = m["instrument"]
            if want in after:
                free = [k for k in config.INSTRUMENT_KEYS if k not in after]
                raise ClaimError(
                    "INSTRUMENT_TAKEN",
                    f"Two people would be on the {config.INSTRUMENT_LABELS[want].lower()} in the "
                    f"{claims.clock(slot['starts_at'])} slot. "
                    + _free_sentence(free) + " Nothing was saved.",
                    instruments=[want], free=free)
            after[want] = m["person"]["id"]
