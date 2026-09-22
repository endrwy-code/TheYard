"""P0.5 — the in-app phone (§9 r21, §17.7) and the GM console (§9 r16, r22)."""

from datetime import datetime, timedelta, timezone  # noqa: F401 - used below

import pytest

import config
import db
from conftest import sign
from services import bookings, game, notify
from services.claims import ClaimError
from test_claims_concurrent import (  # noqa: F401 - fixtures are used by name
    Console, err, roster, secrets_and_limits,
)

GM = {"role": "gm", "name": "Ryan", "station": "GM"}
BEFORE = datetime(2026, 9, 17, 4, 0, tzinfo=timezone.utc)
PHONE_PAGE = "<html><body>the phone</body></html>"
GROUP = ("bananabelles", "heidily", "t_shixuan", "bingkiat")


@pytest.fixture()
def night(roster, data_dir):
    """Games generated, a phone file on disk, and a group of four in game 1."""
    bookings.generate_slots(roster)
    config.PHONE_DIR.mkdir(parents=True, exist_ok=True)
    (config.PHONE_DIR / "the-phone.html").write_text(PHONE_PAGE, encoding="utf-8")
    first = roster.execute("SELECT * FROM slots WHERE room='escape' ORDER BY starts_at").fetchone()
    owner = pid(roster, "bananabelles")
    bookings.book(roster, owner, first["id"], list(GROUP[1:]), BEFORE)
    roster.execute("UPDATE attendees SET checked_in_at=? WHERE handle IN "
                   "('bananabelles','heidily','t_shixuan','bingkiat')", (db.utcnow(),))
    return first


def pid(conn, handle):
    return conn.execute("SELECT id FROM attendees WHERE handle=?", (handle,)).fetchone()[0]


def at(slot, minutes):
    return datetime.fromisoformat(slot["starts_at"]) + timedelta(minutes=minutes)


def code(conn, handle, now):
    return game.phone_access(conn, pid(conn, handle), now)["code"]


# ---------------------------------------------------------------------------
# §9 r21 — every refusal path, and the ways in
# ---------------------------------------------------------------------------

def test_nothing_before_the_booked_time(night, roster):
    assert code(roster, GROUP[0], at(night, -3)) == "NOT_YET"
    assert game.phone_access(roster, pid(roster, "joncjy"), at(night, 1)) == {"code": "NO_BOOKING"}


def test_opens_at_the_booked_time_with_nobody_pressing_anything(night, roster):
    """The clock is the whole rule. No Start, no check-in, no switch."""
    assert code(roster, GROUP[0], at(night, -0.1)) == "NOT_YET"
    out = game.phone_access(roster, pid(roster, GROUP[0]), at(night, 2))
    assert out["code"] is None
    assert game.phone_file(roster, pid(roster, GROUP[0]), at(night, 2)) == PHONE_PAGE


def test_everyone_in_the_game_gets_it(night, roster):
    """Everyone in the game has the phone since 22 Sep (STATE.md 130), and
    since 23 Sep there are no halves left to be on either."""
    for h in GROUP:
        assert code(roster, h, at(night, 2)) is None
        assert game.phone_file(roster, pid(roster, h), at(night, 2)) == PHONE_PAGE


def test_nobody_outside_the_game_gets_it(night, roster):
    assert code(roster, "joncjy", at(night, 2)) == "NO_BOOKING"
    with pytest.raises(ClaimError) as e:
        game.phone_file(roster, pid(roster, "joncjy"), at(night, 2))
    assert e.value.code == "NO_BOOKING"


def test_check_in_no_longer_gates_the_phone(night, roster):
    """23 Sep: the booked time is the only condition, so somebody who walked
    past the front desk still gets their phone."""
    roster.execute("UPDATE attendees SET checked_in_at=NULL WHERE handle=?", (GROUP[0],))
    assert code(roster, GROUP[0], at(night, 1)) is None


def test_stays_open_25_minutes_from_the_booked_time(night, roster):
    """A 15-minute game with leeway, so running out of time does not cut
    anyone off mid-thought (the organiser, 22 Sep)."""
    assert db.get_setting(roster, "phone_minutes") == 25
    assert code(roster, GROUP[1], at(night, 24.9)) is None
    assert code(roster, GROUP[1], at(night, 25.1)) == "RELOCKED"
    with pytest.raises(ClaimError) as e:
        game.phone_file(roster, pid(roster, GROUP[1]), at(night, 26))
    assert e.value.code == "RELOCKED"


def test_ending_the_game_does_not_close_the_phone(night, roster):
    game.act(roster, night["id"], "end", GM, at(night, 15))
    assert code(roster, GROUP[0], at(night, 16)) is None
    assert code(roster, GROUP[0], at(night, 25.1)) == "RELOCKED"


def test_the_gms_lock_takes_it_away_and_undoes(night, roster):
    """The one phone control left, and it is never set by anything but a
    game master's hand. Undo puts everybody back to the rule rather than
    granting anything."""
    game.act(roster, night["id"], "lock", GM, at(night, 3))
    assert code(roster, GROUP[0], at(night, 4)) == "PHONE_LOCKED"
    game.act(roster, night["id"], "unlock", GM, at(night, 5))
    assert code(roster, GROUP[0], at(night, 6)) is None


def test_there_is_no_switch_that_can_turn_the_phone_off(night, roster):
    """23 Sep: `in_app_phone` is gone. It was an admin switch that answered a
    player at their booked minute with "this game uses the handset at the
    desk", and the desk could do nothing about it."""
    assert "in_app_phone" not in config.DEFAULT_SETTINGS
    # Even a row left behind in an older database cannot refuse anybody now.
    db.set_setting(roster, "in_app_phone", False, by="test")
    assert code(roster, GROUP[0], at(night, 1)) is None
    # And seeding drops it, so it does not linger on the Settings screen.
    db.seed_settings(roster)
    assert db.get_settings(roster).get("in_app_phone") is None


def test_named_accounts_can_open_it_whenever_for_testing(night, roster):
    assert code(roster, GROUP[0], at(night, -30)) == "NOT_YET"
    db.set_setting(roster, "phone_always_handles", GROUP[0], by="test")
    assert code(roster, GROUP[0], at(night, -30)) is None


def test_pausing_holds_the_phone_open_for_as_long_as_the_pause(night, roster):
    """23 Sep. Pausing is what a game master does when something happens in
    the room, and it must never be the reason the group loses the phone —
    which is exactly what a window anchored to the booked time did."""
    game.act(roster, night["id"], "pause", GM, at(night, 5))
    game.act(roster, night["id"], "resume", GM, at(night, 8))        # 3 minutes paused
    game.act(roster, night["id"], "extend", GM, at(night, 9))        # +1 minute
    s = game.state(roster, at(night, 10), night["id"])
    assert s["elapsed_seconds"] == 7 * 60 and s["game_seconds"] == 16 * 60
    # 25 + 3 paused + 1 extended
    assert code(roster, GROUP[0], at(night, 28.9)) is None
    assert code(roster, GROUP[0], at(night, 29.1)) == "RELOCKED"


def test_a_minute_can_come_off_as_well_as_on(night, roster):
    game.act(roster, night["id"], "shorten", GM, at(night, 2))
    assert game.state(roster, at(night, 3), night["id"])["game_seconds"] == 14 * 60
    game.act(roster, night["id"], "extend", GM, at(night, 4))
    assert game.state(roster, at(night, 5), night["id"])["game_seconds"] == 15 * 60


def test_a_minute_off_never_ends_a_game_by_arithmetic(night, roster):
    """Shorten cannot take the clock below what has already been played."""
    for _ in range(30):
        game.act(roster, night["id"], "shorten", GM, at(night, 10))
    assert game.state(roster, at(night, 10), night["id"])["game_seconds"] >= 10 * 60


# ---------------------------------------------------------------------------
# The phone arrives as a bot message (STATE.md 130)
# ---------------------------------------------------------------------------

def phone_rows(conn):
    return conn.execute("SELECT * FROM notifications WHERE kind='phone_open' ORDER BY id").fetchall()


def test_the_booked_time_messages_the_phone_to_everyone_in_it(night, roster):
    notify.schedule_due(roster, at(night, 0.2))
    rows = phone_rows(roster)
    assert len(rows) == 4
    assert {r["button_path"] for r in rows} == {notify.GO_PHONE}
    assert "kai chen's phone is open" in rows[0]["text"]
    # Once each: nothing the GM does afterwards sends it again.
    game.act(roster, night["id"], "pause", GM, at(night, 1))
    game.act(roster, night["id"], "end", GM, at(night, 15))
    assert len(phone_rows(roster)) == 4


def test_the_message_names_the_lock_time(night, roster):
    notify.schedule_due(roster, at(night, 0.2))
    lock = at(night, 25).astimezone(config.TIMEZONE)
    want = f"{lock.hour % 12 or 12}:{lock.minute:02d} {'PM' if lock.hour >= 12 else 'AM'}"
    assert f"open until {want}" in phone_rows(roster)[0]["text"]


def test_a_locked_phone_sends_nothing(night, roster):
    game.act(roster, night["id"], "lock", GM, at(night, -1))
    notify.schedule_due(roster, at(night, 0.2))
    assert phone_rows(roster) == []


def test_the_message_expires_when_the_phone_closes_on_the_real_clock(night, roster):
    """The game's times may be test time; the outbox runs on the real clock.
    So the expiry is "25 minutes from now, really", never a fake timestamp
    that could already be in the past for bot.py."""
    notify.schedule_due(roster, at(night, 0.2))
    r = phone_rows(roster)[0]
    left = datetime.fromisoformat(r["expires_at"]) - datetime.fromisoformat(r["send_after"])
    assert timedelta(minutes=24, seconds=40) <= left <= timedelta(minutes=25, seconds=10)
    assert abs(datetime.fromisoformat(r["send_after"]) - datetime.now(timezone.utc)) < timedelta(minutes=1)


def test_the_phone_is_messaged_at_the_booked_time(night, roster):
    notify.schedule_due(roster, at(night, -1))
    assert phone_rows(roster) == []
    notify.schedule_due(roster, at(night, 0.2))
    assert len(phone_rows(roster)) == 4
    notify.schedule_due(roster, at(night, 3))
    assert len(phone_rows(roster)) == 4                                 # once each
    notify.schedule_due(roster, at(night, 26))                          # long over: nothing new either


def test_the_button_says_open_kai_chens_phone(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_URL", "https://yard.example")
    phone = notify.open_button(notify.GO_PHONE)["inline_keyboard"][0][0]
    assert phone["text"] == "\U0001f4f1 Open Kai Chen's phone"
    assert phone["web_app"]["url"] == "https://yard.example/?go=phone"
    assert notify.open_button(notify.GO_TICKET)["inline_keyboard"][0][0]["text"] == "Open The Yard"


def test_the_gm_sees_who_got_the_phone(night, roster):
    db.set_setting(roster, "notify_mode", "on", by="test")
    roster.execute("UPDATE attendees SET tg_user_id=900, can_message=1 WHERE handle=?", (GROUP[0],))
    s = game.state(roster, at(night, -1), night["id"])
    assert {p["phone_msg"] for p in s["people"]} == {None}               # not yet
    notify.schedule_due(roster, at(night, 0.2))
    s = game.state(roster, at(night, 1), night["id"])
    got = {p["handle"]: p["phone_msg"] for p in s["people"]}
    assert got[GROUP[0]] == "waiting"
    # The other three never opened The Yard, so no message can reach them:
    # the GM hands them the desk handset instead of waiting.
    assert {h: v for h, v in got.items() if h != GROUP[0]} == {
        h: "unreachable" for h in got if h != GROUP[0]}
    notify.deliver(roster, lambda chat, text, go: None)
    s = game.state(roster, at(night, 2), night["id"])
    assert {p["handle"]: p["phone_msg"] for p in s["people"]}[GROUP[0]] == "sent"


def test_in_test_mode_the_gm_is_told_the_message_was_held(night, roster):
    roster.execute("UPDATE attendees SET tg_user_id=900, can_message=1 WHERE handle=?", (GROUP[0],))
    notify.schedule_due(roster, at(night, 0.2))
    notify.deliver(roster, lambda chat, text, go: None)                 # notify_mode is "owner"
    s = game.state(roster, at(night, 2), night["id"])
    assert {p["handle"]: p["phone_msg"] for p in s["people"]}[GROUP[0]] == "held"


def test_the_phone_endpoint_serves_the_file_with_no_store(night, roster, client, monkeypatch):
    import app as webapp
    h = GROUP[0]
    roster.execute("UPDATE attendees SET tg_user_id=900 WHERE handle=?", (h,))
    auth = {"Authorization": "tma " + sign(900, h)}
    monkeypatch.setattr(webapp, "now_utc", lambda: at(night, 2))
    r = client.get("/api/escape/phone", headers=auth)
    assert r.status_code == 200 and r.get_data(as_text=True) == PHONE_PAGE
    assert r.headers["Cache-Control"] == "no-store"
    status = client.get("/api/escape/phone/status", headers=auth).get_json()["data"]
    assert status["code"] is None
    game.act(roster, night["id"], "lock", GM, at(night, 1.5))
    r = client.get("/api/escape/phone", headers=auth)
    assert r.status_code == 403 and err(r)["code"] == "PHONE_LOCKED"
    assert r.headers["Cache-Control"] == "no-store"


def test_the_phone_endpoint_runs_the_gate(night, client):
    r = client.get("/api/escape/phone")
    assert err(r)["code"] == "INITDATA_INVALID"


# ---------------------------------------------------------------------------
# The GM console
# ---------------------------------------------------------------------------

def test_state_follows_the_next_game_and_hides_nothing_from_the_gm(night, roster):
    s = game.state(roster, at(night, -30))
    assert s["slot_id"] == night["id"] and s["game_number"] == 1 and s["games_total"] == 21
    assert s["booked"] == 4 and s["checked_in"] == 4
    assert len(s["people"]) == 4
    assert [h["key"] for h in s["hints"]] == ["hint1", "hint2", "hint3", "motive", "method"]
    assert [h["optional"] for h in s["hints"]] == [False, False, False, True, True]
    assert "at" not in s["hints"][0] and s["reset"]
    assert s["state"] == "upcoming" and not s["started"] and s["remaining_seconds"] == 15 * 60


def test_a_game_in_progress_says_so_rather_than_ended(night, roster):
    """The console used to call a game that was happening 'ended', because
    nobody had pressed a Start that no longer exists (23 Sep)."""
    assert game.state(roster, at(night, -1), night["id"])["state"] == "upcoming"
    assert game.state(roster, at(night, 5), night["id"])["state"] == "in_progress"
    assert game.state(roster, at(night, 30), night["id"])["state"] == "finished"


def test_the_console_knows_when_the_next_game_starts(night, roster):
    s = game.state(roster, at(night, 5), night["id"])
    assert s["next_game_at"] and s["next_game_at"] != s["starts_at"]


def test_a_game_in_progress_is_the_current_one_until_it_ends(night, roster):
    later = at(night, 40)                                  # past the second game's start
    game.act(roster, night["id"], "end", GM, at(night, 16))
    assert game.state(roster, later)["slot_id"] != night["id"]


def test_pausing_before_the_booked_time_is_refused(night, roster):
    with pytest.raises(ClaimError) as e:
        game.act(roster, night["id"], "pause", GM, at(night, -1))
    assert e.value.code == "GAME_STATE"


def test_there_is_no_start_to_press(night, roster):
    """23 Sep. Forgetting Start held the room up while the clock said zero."""
    assert "start" not in game.ACTIONS
    with pytest.raises(ClaimError) as e:
        game.act(roster, night["id"], "start", GM, at(night, 1))
    assert e.value.code == "VALIDATION_FAILED"


def test_the_first_press_writes_the_booked_time_into_the_session(night, roster):
    """So a row anybody has touched says on its own what the clock would
    have worked out anyway."""
    game.act(roster, night["id"], "pause", GM, at(night, 4))
    row = roster.execute("SELECT started_at, gm_name FROM game_sessions WHERE slot_id=?",
                         (night["id"],)).fetchone()
    assert row["started_at"] == night["starts_at"] and row["gm_name"] == "Ryan"


def test_every_gm_press_is_logged(night, roster):
    game.act(roster, night["id"], "pause", GM, at(night, 1))
    row = roster.execute("SELECT * FROM audit_log WHERE action='Game paused'").fetchone()
    assert (row["actor_name"], row["entity"], row["entity_id"]) == ("Ryan", "slot", str(night["id"]))


def test_a_hint_goes_to_the_actor_once(night, roster):
    db.set_setting(roster, "actor_chat_id", 5550, by="bot")
    assert game.give_hint(roster, night["id"], "hint1", GM, at(night, 5)) == {"to_actor": True}
    with pytest.raises(ClaimError):
        game.give_hint(roster, night["id"], "hint1", GM, at(night, 5))
    assert game.give_hint(roster, night["id"], "hint3", GM, at(night, 8)) == {"to_actor": True}
    msgs = roster.execute("SELECT * FROM direct_messages").fetchall()
    assert len(msgs) == 2 and msgs[0]["chat_id"] == 5550
    given = [h["given"] for h in game.state(roster, at(night, 9), night["id"])["hints"]]
    assert given == [True, False, True, False, False]

    sent = []
    counts = notify.deliver_direct(roster, lambda chat, text, go, button=True: sent.append((chat, button)))
    assert counts == {"sent": 2} and sent == [(5550, False), (5550, False)]


def test_a_hint_says_when_it_was_given(night, roster):
    game.give_hint(roster, night["id"], "hint2", GM, at(night, 6))
    hint = next(h for h in game.state(roster, at(night, 7), night["id"])["hints"] if h["key"] == "hint2")
    assert hint["given"] and hint["given_at"]


def test_a_hint_without_an_actor_is_still_recorded(night, roster):
    assert game.give_hint(roster, night["id"], "hint2", GM, at(night, 5)) == {"to_actor": False}
    assert roster.execute("SELECT COUNT(*) FROM direct_messages").fetchone()[0] == 0


def test_the_actor_chat_survives_a_restart(night, roster):
    db.set_setting(roster, "actor_chat_id", 5550, by="bot")
    db.seed_settings(roster)
    assert db.get_setting(roster, "actor_chat_id") == 5550


def test_the_gm_console_over_http(night, roster, monkeypatch):
    import app as webapp
    monkeypatch.setattr(webapp, "now_utc", lambda: at(night, 2))
    gm = Console("gm", "Ryan", "GM")
    s = gm.get("/admin/api/gm/state").get_json()["data"]
    assert s["slot_id"] == night["id"]
    assert gm.post(f"/admin/api/gm/{night['id']}/pause").status_code == 200
    assert gm.post(f"/admin/api/gm/{night['id']}/resume").status_code == 200
    assert gm.post(f"/admin/api/gm/{night['id']}/hints/hint1").status_code == 200
    assert err(gm.post(f"/admin/api/gm/{night['id']}/dance"))["code"] == "VALIDATION_FAILED"
    # One phone PIN since 22 Sep (STATE.md decision 126): any phone sign-in
    # runs the game, not only one made with the GM PIN.
    booth_phone = Console()
    assert booth_phone.post(f"/admin/api/gm/{night['id']}/end").status_code == 200
