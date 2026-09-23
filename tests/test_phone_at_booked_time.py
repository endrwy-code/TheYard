"""The victim's phone opens at the booked time — §9 r21, 24 Sep.

The rest of the phone tests run against the organiser's real export and so
only run on a machine that has it. This file builds its own game, so the one
rule the room depends on is executed wherever the suite runs:

    a booking in this game, and the clock past the booked time. That is all.

No press, no check-in, no half, and no switch — the one thing that can close
it early is the game master's lock, checked here too, along with the named
accounts that ignore the clock for testing.
"""

from datetime import datetime, timedelta, timezone

import pytest

import config
import db
import manage
from services import game, notify
from services.claims import ClaimError


def make_game(conn, *, at="19:05", handles=("ada_lovelace",)):
    """One escape slot at `at` on the event date, with `handles` booked in."""
    hh, mm = (int(x) for x in at.split(":"))
    day = datetime.fromisoformat(config.EVENT_DATE)
    starts = datetime(day.year, day.month, day.day, hh, mm, tzinfo=config.TIMEZONE)
    ends = starts + timedelta(minutes=int(db.get_setting(conn, "game_minutes", 15)))
    cur = conn.execute(
        "INSERT INTO slots (room, starts_at, ends_at, capacity, price_cents) "
        "VALUES ('escape',?,?,12,0)",
        (starts.astimezone(timezone.utc).isoformat(), ends.astimezone(timezone.utc).isoformat()))
    slot_id = cur.lastrowid
    now = db.utcnow()
    ids = []
    for handle in handles:
        code = db.new_code(conn, "attendees", "pass_code")
        a = conn.execute(
            "INSERT INTO attendees (name, handle, handle_raw, source, status, is_test, "
            "payment_status, pass_code, created_at, updated_at) "
            "VALUES (?,?,?,'import','active',1,'submitted',?,?,?)",
            ("Test " + handle, handle, "@" + handle, code, now, now)).lastrowid
        conn.execute(
            "INSERT INTO escape_bookings (slot_id, attendee_id, booked_by_id, ref_code, zone, "
            "status, created_at) VALUES (?,?,?,?,'A','booked',?)",
            (slot_id, a, a, db.new_code(conn, "escape_bookings", "ref_code"), now))
        ids.append(a)
    return slot_id, starts, (ids[0] if len(ids) == 1 else ids)


def at(starts, minutes):
    return (starts + timedelta(minutes=minutes)).astimezone(timezone.utc)


def code_at(conn, attendee_id, starts, minutes):
    return game.phone_access(conn, attendee_id, at(starts, minutes))["code"]


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------

def test_the_clock_alone_opens_it(conn):
    _, starts, me = make_game(conn)
    assert code_at(conn, me, starts, -1) == "NOT_YET"
    assert code_at(conn, me, starts, 0) is None        # the booked minute itself
    assert code_at(conn, me, starts, 14) is None


def test_nobody_has_to_press_anything(conn):
    """There is no game_sessions row at all here: the GM never touched it."""
    slot_id, starts, me = make_game(conn)
    assert conn.execute("SELECT COUNT(*) FROM game_sessions WHERE slot_id=?",
                        (slot_id,)).fetchone()[0] == 0
    assert code_at(conn, me, starts, 1) is None


def test_it_closes_25_minutes_after_the_booked_time(conn):
    _, starts, me = make_game(conn)
    assert code_at(conn, me, starts, 24) is None
    assert code_at(conn, me, starts, 25) == "RELOCKED"
    assert code_at(conn, me, starts, 40) == "RELOCKED"


def test_check_in_is_not_a_condition_any_more(conn):
    _, starts, me = make_game(conn)
    assert conn.execute("SELECT checked_in_at FROM attendees WHERE id=?",
                        (me,)).fetchone()["checked_in_at"] is None
    assert code_at(conn, me, starts, 1) is None


def test_no_booking_is_still_no_phone(conn):
    _, starts, _ = make_game(conn)
    now = db.utcnow()
    stranger = conn.execute(
        "INSERT INTO attendees (name, handle, handle_raw, source, status, is_test, "
        "payment_status, pass_code, created_at, updated_at) "
        "VALUES ('Nobody','nobody','@nobody','walk_in','active',1,'submitted','AAAA-BBBB',?,?)",
        (now, now)).lastrowid
    assert code_at(conn, stranger, starts, 1) == "NO_BOOKING"


def test_each_booking_opens_on_its_own_time(conn):
    _, early, a = make_game(conn, at="19:05", handles=("ada_lovelace",))
    _, late, b = make_game(conn, at="19:25", handles=("grace_hopper",))
    # Early game running: the later booking is not open yet.
    assert code_at(conn, a, early, 1) is None
    assert game.phone_access(conn, b, at(early, 1))["code"] == "NOT_YET"
    # The earlier one closes on its own 25 minutes, and only then.
    assert game.phone_access(conn, a, at(early, 24))["code"] is None
    assert game.phone_access(conn, a, at(early, 25))["code"] == "RELOCKED"
    assert code_at(conn, b, late, 1) is None


def test_the_windows_of_consecutive_games_overlap(conn):
    """Games are 20 minutes apart and the window is 25, so the group before
    still has their phone for the first five minutes of the next game. Pinned
    deliberately: it is the price of the ten minutes of slack after a game,
    and the only way to close it is a shorter window."""
    _, early, a = make_game(conn, at="19:05", handles=("ada_lovelace",))
    _, late, b = make_game(conn, at="19:25", handles=("grace_hopper",))
    both_open = at(late, 1)                       # 19:26
    assert game.phone_access(conn, a, both_open)["code"] is None
    assert game.phone_access(conn, b, both_open)["code"] is None


# ---------------------------------------------------------------------------
# The two things that can still close it
# ---------------------------------------------------------------------------

def test_the_gm_can_lock_it_for_one_game_and_undo_that(conn):
    slot_id, starts, me = make_game(conn)
    actor = {"role": "gm", "name": "Ryan", "station": "Escape desk"}
    game.act(conn, slot_id, "lock", actor, at(starts, 2))
    assert code_at(conn, me, starts, 3) == "PHONE_LOCKED"
    game.act(conn, slot_id, "unlock", actor, at(starts, 4))
    assert code_at(conn, me, starts, 5) is None


def test_the_gm_clock_only_ever_gives_the_phone_more_time(conn):
    """Pause and End drive the countdown. Neither takes the phone away, and
    a pause hands its own length back to the window (23 Sep)."""
    slot_id, starts, me = make_game(conn)
    actor = {"role": "gm", "name": "Ryan", "station": "Escape desk"}
    game.act(conn, slot_id, "pause", actor, at(starts, 2))
    assert code_at(conn, me, starts, 3) is None          # paused: phone unaffected
    game.act(conn, slot_id, "resume", actor, at(starts, 4))
    game.act(conn, slot_id, "end", actor, at(starts, 5))
    assert code_at(conn, me, starts, 6) is None          # ended: still theirs
    # Two minutes paused, so the window closes two minutes later than usual.
    assert code_at(conn, me, starts, 26) is None
    assert code_at(conn, me, starts, 28) == "RELOCKED"


# ---------------------------------------------------------------------------
# The testing allowlist
# ---------------------------------------------------------------------------

def test_a_named_account_ignores_the_clock(conn):
    _, starts, me = make_game(conn)
    assert code_at(conn, me, starts, -30) == "NOT_YET"
    db.set_setting(conn, "phone_always_handles", "ada_lovelace", by="test")
    out = game.phone_access(conn, me, at(starts, -30))
    assert out["code"] is None and out["always"] is True


def test_a_named_account_needs_no_booking_at_all(conn):
    _, starts, _ = make_game(conn)
    now = db.utcnow()
    tester = conn.execute(
        "INSERT INTO attendees (name, handle, handle_raw, source, status, is_test, "
        "payment_status, pass_code, created_at, updated_at) "
        "VALUES ('Tester','tester','@tester','walk_in','active',1,'submitted','CCCC-DDDD',?,?)",
        (now, now)).lastrowid
    assert code_at(conn, tester, starts, 1) == "NO_BOOKING"
    db.set_setting(conn, "phone_always_handles", " @Tester , someone_else ", by="test")
    assert code_at(conn, tester, starts, 1) is None      # @ and case and spaces all forgiven


def test_an_empty_list_lets_nobody_through(conn):
    _, starts, me = make_game(conn)
    db.set_setting(conn, "phone_always_handles", "", by="test")
    assert code_at(conn, me, starts, -30) == "NOT_YET"


def test_a_named_account_still_gets_in_when_the_gm_has_locked_it(conn):
    """Testing has to work while the room is mid-reset."""
    slot_id, starts, me = make_game(conn)
    game.act(conn, slot_id, "lock", {"role": "gm", "name": "Ryan", "station": "desk"},
                   at(starts, 1))
    assert code_at(conn, me, starts, 2) == "PHONE_LOCKED"
    db.set_setting(conn, "phone_always_handles", "ada_lovelace", by="test")
    assert code_at(conn, me, starts, 2) is None


# ---------------------------------------------------------------------------
# What the player is told
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", ["NO_BOOKING", "NOT_YET", "RELOCKED", "PHONE_OFF", "PHONE_LOCKED"])
def test_every_refusal_has_words_for_it(code):
    assert game.PHONE_MESSAGES.get(code)


@pytest.mark.parametrize("minutes, want", [(-1, "NOT_YET"), (30, "RELOCKED")])
def test_the_page_itself_refuses_with_the_reason_not_a_catch_all(conn, minutes, want):
    """PHONE_LOCKED means the GM locked this game, so the other refusals have
    to say what they actually are — otherwise "locked" sends a player to the
    game master when all they have to do is wait."""
    _, starts, me = make_game(conn)
    with pytest.raises(ClaimError) as exc:
        game.phone_file(conn, me, at(starts, minutes))
    assert exc.value.code == want
    with pytest.raises(ClaimError) as exc:
        game.phone_image(conn, me, "cam-01-kitchen-2215.jpg", at(starts, minutes))
    assert exc.value.code == want


def test_there_are_no_halves_to_hide(conn):
    """The split went on 23 Sep: everyone in the game gets the phone and
    nobody is told to stand anywhere in particular."""
    _, starts, me = make_game(conn)
    assert "zone" not in game.phone_access(conn, me, at(starts, 1))


# ---------------------------------------------------------------------------
# Handing the phone to the test group  (manage.py phone-test)
# ---------------------------------------------------------------------------

def test_the_test_group_is_read_the_way_people_type_it():
    got = game.always_handles({"phone_always_handles": " @Ada_Lovelace , grace_hopper ,, "})
    assert got == {"ada_lovelace", "grace_hopper"}
    assert game.always_handles({"phone_always_handles": ""}) == set()
    assert game.always_handles({}) == set()


def queued(conn):
    return conn.execute("SELECT * FROM notifications WHERE kind='phone_open'").fetchall()


def test_phone_test_sends_to_the_group_and_nobody_else(conn):
    _, _, me = make_game(conn)                      # booked, but not a tester
    now = db.utcnow()
    tester = conn.execute(
        "INSERT INTO attendees (name,handle,handle_raw,source,status,is_test,payment_status,"
        "pass_code,tg_user_id,can_message,created_at,updated_at) VALUES "
        "('T','tester','@tester','walk_in','active',1,'missing','TTTT-TTTT',9909999,1,?,?)",
        (now, now)).lastrowid
    db.set_setting(conn, "phone_always_handles", "@Tester, not_on_the_roster", by="test")
    conn.commit()

    assert manage.cmd_phone_test([]) == 0
    rows = queued(conn)
    assert [r["attendee_id"] for r in rows] == [tester]      # not the booked player
    assert rows[0]["button_path"] == "phone"
    assert "testing" in rows[0]["text"]
    assert "open until" not in rows[0]["text"]               # a tester has no clock
    assert me is not None


def test_phone_test_can_be_run_again(conn):
    now = db.utcnow()
    conn.execute("INSERT INTO attendees (name,handle,handle_raw,source,status,is_test,"
                 "payment_status,pass_code,created_at,updated_at) VALUES ('T','tester','@tester',"
                 "'walk_in','active',1,'missing','TTTT-TTTT',?,?)", (now, now))
    db.set_setting(conn, "phone_always_handles", "tester", by="test")
    conn.commit()
    manage.cmd_phone_test([])
    manage.cmd_phone_test([])
    assert len(queued(conn)) == 2          # testing twice should send twice


def test_phone_test_says_so_when_the_group_is_empty(conn):
    db.set_setting(conn, "phone_always_handles", "", by="test")
    conn.commit()
    assert manage.cmd_phone_test([]) == 1
    assert queued(conn) == []


def test_a_tester_opening_it_is_never_told_it_is_locked(conn):
    """What the message's button lands on. No booking, no game running, and
    it still has to open — otherwise the message is a dead end."""
    now = db.utcnow()
    tester = conn.execute(
        "INSERT INTO attendees (name,handle,handle_raw,source,status,is_test,payment_status,"
        "pass_code,created_at,updated_at) VALUES ('T','tester','@tester','walk_in','active',1,"
        "'missing','TTTT-TTTT',?,?)", (now, now)).lastrowid
    db.set_setting(conn, "phone_always_handles", "tester", by="test")
    out = game.phone_access(conn, tester, datetime.now(timezone.utc))
    assert out["code"] is None and out["always"] is True
    assert "lock_at" not in out            # nothing for the card to count down to
    # And the page itself serves them, which is what the button lands on.
    (config.PHONE_DIR / "the-phone.html").write_text("<html>the phone</html>", encoding="utf-8")
    assert game.phone_file(conn, tester, datetime.now(timezone.utc))


_TESTER_N = [0]


def _tester(conn, handle="tester"):
    """A tester the bot can actually reach.

    `tg_user_id` is the part that is easy to forget and impossible to work
    around: it is set the first time somebody opens The Yard, and without it
    there is no Telegram chat to send to. Not `is_test`: somebody added to the
    test group in Settings is an ordinary attendee, and until 23 Sep a helper
    that marked them a test account hid that testing mode suppressed them.
    """
    now = db.utcnow()
    _TESTER_N[0] += 1
    return conn.execute(
        "INSERT INTO attendees (name,handle,handle_raw,source,status,is_test,payment_status,"
        "pass_code,tg_user_id,can_message,created_at,updated_at) VALUES ('T',?,?,'walk_in','active',0,"
        "'missing',?,?,1,?,?)",
        (handle, "@" + handle, f"TST{_TESTER_N[0]}-TTTT", 9_900_000 + _TESTER_N[0],
         now, now)).lastrowid


def test_adding_somebody_to_the_test_group_messages_them(conn):
    """23 Sep. Adding a tester is a request to let them in, and the only way
    in is the message. Leaving them to find a PowerShell command was the
    difference between a setting and a working test."""
    from services import admin
    who = _tester(conn)
    conn.commit()
    out = admin.save_settings(conn, {"phone_always_handles": "tester"}, "Maximus",
                              datetime.now(timezone.utc))
    assert out["phone_test"]["sent"] == ["tester"]
    rows = queued(conn)
    assert [r["attendee_id"] for r in rows] == [who]
    assert rows[0]["button_path"] == "phone" and "testing" in rows[0]["text"]


def test_only_the_handles_just_added_are_messaged(conn):
    """Saving something else on the same screen must not message the whole
    group all over again."""
    from services import admin
    first, second = _tester(conn, "tester"), _tester(conn, "tester_two")
    conn.commit()
    admin.save_settings(conn, {"phone_always_handles": "tester"}, "Maximus",
                        datetime.now(timezone.utc))
    out = admin.save_settings(conn, {"phone_always_handles": "tester, tester_two"}, "Maximus",
                              datetime.now(timezone.utc))
    assert out["phone_test"]["sent"] == ["tester_two"]
    assert [r["attendee_id"] for r in queued(conn)] == [first, second]
    # Saving an unrelated row sends nothing at all.
    out = admin.save_settings(conn, {"meeting_point": "the front desk again"}, "Maximus",
                              datetime.now(timezone.utc))
    assert "phone_test" not in out
    assert len(queued(conn)) == 2


def test_the_save_names_anybody_it_could_not_reach(conn):
    """Silence there looks like it worked, and it has not.

    23 Sep: `unreachable` used to be built from `can_message` alone, which
    starts at 1 for everybody on the roster — so the save reported "sent"
    about somebody who had never opened The Yard, which is 164 of the 170
    people on this roster. It is `notify.reachable` now: a chat to send to,
    and Telegram not having refused us.
    """
    from services import admin
    _tester(conn, "blocked_us")
    conn.execute("UPDATE attendees SET can_message=0 WHERE handle='blocked_us'")
    _tester(conn, "never_opened")
    conn.execute("UPDATE attendees SET tg_user_id=NULL WHERE handle='never_opened'")
    _tester(conn, "fine")
    conn.commit()
    out = admin.save_settings(
        conn, {"phone_always_handles": "blocked_us, never_opened, fine, ghost"},
        "Maximus", datetime.now(timezone.utc))
    assert out["phone_test"] == {
        "sent": ["fine"],
        "missing": ["ghost"],
        "unreachable": ["blocked_us", "never_opened"],
        "held": [],
    }


def test_testing_mode_lets_the_test_group_through(conn):
    """The test group is who testing mode is for.

    Until 23 Sep "owner" let out only the owner and `is_test` accounts, and
    nobody added in Settings is either. So the save said "held", and the only
    remedy on offer was switching messages on for all 170 people. Only
    Nobody holds a tester's message now.
    """
    from services import admin
    _tester(conn, "ordinary")
    conn.commit()
    assert db.get_setting(conn, "notify_mode") == "owner"
    out = admin.save_settings(conn, {"phone_always_handles": "ordinary"}, "Maximus",
                              datetime.now(timezone.utc))
    assert out["phone_test"] == {"sent": ["ordinary"], "missing": [],
                                "unreachable": [], "held": []}

    # And the outbox agrees: it goes, while everybody else is still held back.
    notify.queue(conn, _tester(conn, "not_in_the_group"), "x", "to a real attendee")
    sent = []
    assert notify.deliver(conn, lambda chat, text, go: sent.append(text)) == {
        "sent": 1, "suppressed": 1}
    assert sent == [notify.text_phone_test()]

    # Nobody means nobody, test group included, and the save says so.
    db.set_setting(conn, "notify_mode", "off", by="test")
    again = game.send_phone_to_testers(conn, only=["ordinary"])
    assert again["held"] == ["ordinary"] and again["sent"] == []
