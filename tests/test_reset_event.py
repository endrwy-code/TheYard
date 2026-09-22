"""`manage.py reset-event` — wipe a rehearsal, keep the event.

The command exists for the gap between testing the room and opening the doors.
What it must never do is take the roster with it, so most of this file is
about what survives.
"""

from datetime import datetime, timezone

import config
import db
import manage


def rehearsal(conn):
    """A database with a run on it: bookings, a hand-over, a game, verdicts."""
    now = db.utcnow()
    day = datetime.fromisoformat(config.EVENT_DATE)
    starts = datetime(day.year, day.month, day.day, 19, 5,
                      tzinfo=config.TIMEZONE).astimezone(timezone.utc).isoformat()
    slot = conn.execute(
        "INSERT INTO slots (room, starts_at, ends_at, capacity, price_cents) "
        "VALUES ('escape',?,?,12,0)", (starts, starts)).lastrowid
    people = {}
    for handle, shot in (("ada_lovelace", "https://x/a.png"), ("grace_hopper", None)):
        code = db.new_code(conn, "attendees", "pass_code")
        people[handle] = conn.execute(
            "INSERT INTO attendees (name,handle,handle_raw,source,status,is_test,payment_status,"
            "paperform_receipt_url,pass_code,tg_user_id,checked_in_at,checked_in_by,"
            "created_at,updated_at) VALUES (?,?,?,'import','active',1,'submitted',?,?,?,?,'Wei',?,?)",
            ("Test " + handle, handle, "@" + handle, shot, code,
             9000 + len(people), now, now, now)).lastrowid
    conn.execute("INSERT INTO escape_bookings (slot_id,attendee_id,booked_by_id,ref_code,zone,"
                 "status,created_at) VALUES (?,?,?,?,'A','booked',?)",
                 (slot, people["ada_lovelace"], people["ada_lovelace"],
                  db.new_code(conn, "escape_bookings", "ref_code"), now))
    conn.execute("INSERT INTO game_sessions (slot_id, started_at) VALUES (?,?)", (slot, now))
    conn.execute("INSERT INTO notifications (attendee_id,kind,text,status,created_at,send_after) "
                 "VALUES (?,'escape_reminder','x','queued',?,?)",
                 (people["ada_lovelace"], now, now))
    conn.execute("UPDATE attendees SET payment_status='rejected' WHERE id=?",
                 (people["ada_lovelace"],))
    conn.execute("UPDATE attendees SET payment_status='verified' WHERE id=?",
                 (people["grace_hopper"],))
    conn.execute("UPDATE slots SET is_blocked=1, block_reason='testing' WHERE id=?", (slot,))
    db.set_setting(conn, "test_clock", True, by="test")
    conn.commit()
    return people


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608


def run(conn):
    """The command reopens the database itself, so commit and stand back."""
    conn.commit()
    assert manage.cmd_reset_event(["--yes"]) == 0


# ---------------------------------------------------------------------------
# What goes
# ---------------------------------------------------------------------------

def test_every_trace_of_the_run_goes(conn):
    rehearsal(conn)
    assert count(conn, "escape_bookings") == 1 and count(conn, "game_sessions") == 1
    run(conn)
    for table, _ in manage.NIGHT_TABLES:
        assert count(conn, table) == 0, table


def test_check_ins_go(conn):
    rehearsal(conn)
    run(conn)
    assert conn.execute("SELECT COUNT(*) FROM attendees WHERE checked_in_at IS NOT NULL "
                        "OR checked_in_by IS NOT NULL").fetchone()[0] == 0


def test_a_verdict_goes_back_to_what_the_sign_up_said(conn):
    """Not to 'verified' and not to 'missing' for everybody — to whatever
    their own screenshot says, which is what reopening a verdict does."""
    rehearsal(conn)
    run(conn)
    rows = {r["handle"]: r["payment_status"] for r in
            conn.execute("SELECT handle, payment_status FROM attendees")}
    assert rows["ada_lovelace"] == "submitted"     # had a screenshot, was rejected
    assert rows["grace_hopper"] == "missing"       # had none, was marked paid


def test_blocks_and_the_test_clock_go(conn):
    rehearsal(conn)
    run(conn)
    assert conn.execute("SELECT COUNT(*) FROM slots WHERE is_blocked=1").fetchone()[0] == 0
    assert db.get_setting(conn, "test_clock") is False


def test_a_receipt_an_admin_typed_goes_but_a_real_one_stays(conn):
    people = rehearsal(conn)
    now = db.utcnow()
    conn.execute("INSERT INTO receipts (attendee_id,purpose,source,uploaded_at) "
                 "VALUES (?,'entrance','admin',?)", (people["grace_hopper"], now))
    conn.execute("INSERT INTO receipts (attendee_id,purpose,source,file_name,uploaded_at) "
                 "VALUES (?,'entrance','paperform','shot.png',?)", (people["ada_lovelace"], now))
    run(conn)
    left = conn.execute("SELECT source, file_name FROM receipts").fetchall()
    assert len(left) == 1 and left[0]["file_name"] == "shot.png"


# ---------------------------------------------------------------------------
# What stays — the half that matters
# ---------------------------------------------------------------------------

def test_the_roster_survives_untouched(conn):
    people = rehearsal(conn)
    codes = {r["handle"]: r["pass_code"] for r in
             conn.execute("SELECT handle, pass_code FROM attendees")}
    run(conn)
    assert count(conn, "attendees") == len(people)
    after = {r["handle"]: r["pass_code"] for r in
             conn.execute("SELECT handle, pass_code FROM attendees")}
    assert after == codes            # the codes people already have still work


def test_telegram_links_survive(conn):
    """The same people are coming. Making everybody link again at the door is
    the one thing a reset must not cause."""
    rehearsal(conn)
    run(conn)
    assert conn.execute("SELECT COUNT(*) FROM attendees WHERE tg_user_id IS NOT NULL"
                        ).fetchone()[0] == 2


def test_settings_survive(conn):
    rehearsal(conn)
    db.set_setting(conn, "jam_room", "Heaven 3", by="test")
    run(conn)
    assert db.get_setting(conn, "jam_room") == "Heaven 3"


def test_the_audit_log_survives_and_records_the_reset(conn):
    rehearsal(conn)
    before = count(conn, "audit_log")
    run(conn)
    assert count(conn, "audit_log") > before
    row = conn.execute("SELECT * FROM audit_log WHERE action='Event reset'").fetchone()
    assert row is not None
    import json
    d = json.loads(row["details"])
    assert d["removed"]["escape_bookings"] == 1 and d["check_ins"] == 2 and d["verdicts"] == 2


def test_the_timetable_is_rebuilt_empty(conn):
    rehearsal(conn)
    run(conn)
    total = conn.execute("SELECT COUNT(*) FROM slots WHERE room='escape'").fetchone()[0]
    assert total > 1                                  # the schedule, not the one test slot
    assert count(conn, "escape_bookings") == 0


def test_it_backs_up_before_it_deletes(conn):
    rehearsal(conn)
    run(conn)
    backups = list(config.BACKUP_DIR.glob("*.db"))
    assert backups, "a reset with no backup behind it is unrecoverable"


def test_running_it_on_a_clean_database_is_harmless(conn):
    conn.commit()
    assert manage.cmd_reset_event(["--yes"]) == 0
    assert manage.cmd_reset_event(["--yes"]) == 0


def test_without_the_word_nothing_is_touched(conn, monkeypatch):
    rehearsal(conn)
    monkeypatch.setattr("builtins.input", lambda *a: "yes")     # not RESET
    conn.commit()
    assert manage.cmd_reset_event([]) == 1
    assert count(conn, "escape_bookings") == 1
    assert db.get_setting(conn, "test_clock") is True
