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


@pytest.fixture()
def night(roster, data_dir):
    """Games generated, a phone file on disk, and a group of four in game 1:
    halves alternate A, B, A, B by booking order."""
    bookings.generate_slots(roster)
    config.PHONE_DIR.mkdir(parents=True, exist_ok=True)
    (config.PHONE_DIR / "the-phone.html").write_text(PHONE_PAGE, encoding="utf-8")
    first = roster.execute("SELECT * FROM slots WHERE room='escape' ORDER BY starts_at").fetchone()
    owner = pid(roster, "bananabelles")
    bookings.book(roster, owner, first["id"], ["heidily", "t_shixuan", "bingkiat"], BEFORE)
    roster.execute("UPDATE attendees SET checked_in_at=? WHERE handle IN "
                   "('bananabelles','heidily','t_shixuan','bingkiat')", (db.utcnow(),))
    return first


def pid(conn, handle):
    return conn.execute("SELECT id FROM attendees WHERE handle=?", (handle,)).fetchone()[0]


def zone(conn, handle):
    return conn.execute("SELECT b.zone FROM escape_bookings b JOIN attendees a ON a.id=b.attendee_id "
                        "WHERE a.handle=? AND b.status='booked'", (handle,)).fetchone()[0]


def desk(conn):
    return next(h for h in ("bananabelles", "heidily", "t_shixuan", "bingkiat") if zone(conn, h) == "B")


def flat(conn):
    return next(h for h in ("bananabelles", "heidily", "t_shixuan", "bingkiat") if zone(conn, h) == "A")


def at(slot, minutes):
    return datetime.fromisoformat(slot["starts_at"]) + timedelta(minutes=minutes)


def code(conn, handle, now):
    return game.phone_access(conn, pid(conn, handle), now)["code"]


# ---------------------------------------------------------------------------
# §9 r21 — every refusal path, and the one way in
# ---------------------------------------------------------------------------

def test_locked_before_the_game_and_halves_stay_hidden(night, roster):
    out = game.phone_access(roster, pid(roster, desk(roster)), at(night, -3))
    assert out["code"] == "NOT_YET" and out["zone"] is None
    assert game.phone_access(roster, pid(roster, "joncjy"), at(night, 1)) == {"code": "NO_BOOKING", "zone": None}


def test_opens_at_the_booked_time_with_nobody_pressing_anything(night, roster):
    """24 Sep: the clock is the whole rule. No Start, no check-in, no half."""
    assert code(roster, desk(roster), at(night, -0.1)) == "NOT_YET"
    out = game.phone_access(roster, pid(roster, desk(roster)), at(night, 2))
    assert out["code"] is None and out["zone"] == "B"
    assert game.phone_file(roster, pid(roster, desk(roster)), at(night, 2)) == PHONE_PAGE


def test_the_flat_group_gets_the_phone_too(night, roster):
    """Everyone in the game has the phone since 22 Sep (STATE.md 130). The
    two groups still decide where people start; they no longer decide who
    holds the phone."""
    assert code(roster, flat(roster), at(night, 2)) is None
    assert game.phone_file(roster, pid(roster, flat(roster)), at(night, 2)) == PHONE_PAGE


def test_nobody_outside_the_game_gets_it(night, roster):
    assert code(roster, "joncjy", at(night, 2)) == "NO_BOOKING"
    with pytest.raises(ClaimError) as e:
        game.phone_file(roster, pid(roster, "joncjy"), at(night, 2))
    assert e.value.code == "NO_BOOKING"


def test_check_in_no_longer_gates_the_phone(night, roster):
    """24 Sep: the booked time is the only condition, so somebody who walked
    past the front desk still gets their phone."""
    h = desk(roster)
    roster.execute("UPDATE attendees SET checked_in_at=NULL WHERE handle=?", (h,))
    assert code(roster, h, at(night, 1)) is None


def test_stays_open_25_minutes_from_the_start(night, roster):
    """A 15-minute game with leeway, so running out of time does not cut
    anyone off mid-thought (the organiser, 22 Sep)."""
    assert db.get_setting(roster, "phone_minutes") == 25
    h = flat(roster)
    assert code(roster, h, at(night, 24.9)) is None
    assert code(roster, h, at(night, 25.1)) == "RELOCKED"
    with pytest.raises(ClaimError) as e:
        game.phone_file(roster, pid(roster, h), at(night, 26))
    assert e.value.code == "RELOCKED"


def test_the_window_follows_the_booked_time_not_the_gm(night, roster):
    """24 Sep, the other way round from before: a late Start no longer buys
    anybody extra phone time, because the phone never waited for it."""
    game.act(roster, night["id"], "start", GM, at(night, 4))              # a late start
    assert code(roster, desk(roster), at(night, 24.9)) is None
    assert code(roster, desk(roster), at(night, 25.1)) == "RELOCKED"


def test_ending_the_game_does_not_lock_the_phone(night, roster):
    game.act(roster, night["id"], "start", GM, at(night, 0))
    game.act(roster, night["id"], "end", GM, at(night, 15))
    assert code(roster, desk(roster), at(night, 16)) is None
    assert code(roster, desk(roster), at(night, 25.1)) == "RELOCKED"


def test_the_gms_emergency_lock_takes_it_away_and_undoes(night, roster):
    """The one phone control left. It only ever takes the phone away — undo
    puts everybody back to the rule rather than granting anything."""
    h = desk(roster)
    game.act(roster, night["id"], "lock", GM, at(night, 3))
    assert code(roster, h, at(night, 4)) == "PHONE_LOCKED"
    game.act(roster, night["id"], "unlock", GM, at(night, 5))
    assert code(roster, h, at(night, 6)) is None


def test_settings_can_switch_the_in_app_phone_off_for_everyone(night, roster):
    db.set_setting(roster, "in_app_phone", False, by="test")
    assert code(roster, desk(roster), at(night, 1)) == "PHONE_OFF"


def test_named_accounts_can_open_it_whenever_for_testing(night, roster):
    h = desk(roster)
    assert code(roster, h, at(night, -30)) == "NOT_YET"
    db.set_setting(roster, "phone_always_handles", h, by="test")
    assert code(roster, h, at(night, -30)) is None


def test_pausing_and_extending_push_the_relock_back(night, roster):
    game.act(roster, night["id"], "start", GM, at(night, 0))
    game.act(roster, night["id"], "pause", GM, at(night, 5))
    game.act(roster, night["id"], "resume", GM, at(night, 8))        # 3 minutes paused
    game.act(roster, night["id"], "extend", GM, at(night, 9))        # +1 minute
    s = game.state(roster, at(night, 10), night["id"])
    assert s["elapsed_seconds"] == 7 * 60 and s["game_seconds"] == 16 * 60
    # The game moved; the phone did not. Its 25 minutes are the slot's own.
    assert code(roster, desk(roster), at(night, 24.9)) is None
    assert code(roster, desk(roster), at(night, 25.1)) == "RELOCKED"


def test_a_pause_no_longer_holds_the_phone_window_open(night, roster):
    """24 Sep: the window is anchored to the booked time, so a long pause
    cannot stretch it. The ten minutes of slack after a 15-minute game are
    what a pause has to come out of."""
    game.act(roster, night["id"], "start", GM, at(night, 0))
    game.act(roster, night["id"], "pause", GM, at(night, 20))
    assert code(roster, desk(roster), at(night, 24.9)) is None
    assert code(roster, desk(roster), at(night, 25.1)) == "RELOCKED"


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
    assert "his phone is unlocked" in rows[0]["text"]
    # Once each: nothing the GM does afterwards sends it again.
    game.act(roster, night["id"], "start", GM, at(night, 1))
    game.act(roster, night["id"], "end", GM, at(night, 15))
    assert len(phone_rows(roster)) == 4


def test_the_message_names_the_lock_time(night, roster):
    notify.schedule_due(roster, at(night, 0.2))
    lock = at(night, 25).astimezone(config.TIMEZONE)
    want = f"{lock.hour % 12 or 12}:{lock.minute:02d} {'PM' if lock.hour >= 12 else 'AM'}"
    assert f"open until {want}" in phone_rows(roster)[0]["text"]


def test_no_phone_message_while_the_phone_is_off(night, roster):
    db.set_setting(roster, "in_app_phone", False, by="test")
    notify.schedule_due(roster, at(night, 0.2))
    assert phone_rows(roster) == []
    db.set_setting(roster, "in_app_phone", True, by="test")            # switched back on
    notify.schedule_due(roster, at(night, 2))
    assert len(phone_rows(roster)) == 4


def test_a_locked_phone_sends_nothing(night, roster):
    game.act(roster, night["id"], "lock", GM, at(night, -1))
    notify.schedule_due(roster, at(night, 0.2))
    assert phone_rows(roster) == []


def test_the_message_expires_when_the_phone_locks_on_the_real_clock(night, roster):
    """The game's times may be test time; the outbox runs on the real clock.
    So the expiry is "25 minutes from now, really", never a fake timestamp
    that could already be in the past for bot.py."""
    notify.schedule_due(roster, at(night, 0.2))
    r = phone_rows(roster)[0]
    left = datetime.fromisoformat(r["expires_at"]) - datetime.fromisoformat(r["send_after"])
    assert timedelta(minutes=24, seconds=50) <= left <= timedelta(minutes=25, seconds=10)
    assert abs(datetime.fromisoformat(r["send_after"]) - datetime.now(timezone.utc)) < timedelta(minutes=1)


def test_the_phone_is_messaged_at_the_booked_time(night, roster):
    notify.schedule_due(roster, at(night, -1))
    assert phone_rows(roster) == []
    notify.schedule_due(roster, at(night, 0.2))
    assert len(phone_rows(roster)) == 4
    notify.schedule_due(roster, at(night, 3))
    assert len(phone_rows(roster)) == 4                                 # once each
    notify.schedule_due(roster, at(night, 26))                          # long over: nothing new either


def test_the_button_says_open_the_phone(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_URL", "https://yard.example")
    phone = notify.open_button(notify.GO_PHONE)["inline_keyboard"][0][0]
    assert phone["text"] == "\U0001f4f1 Open the phone"
    assert phone["web_app"]["url"] == "https://yard.example/?go=phone"
    assert notify.open_button(notify.GO_TICKET)["inline_keyboard"][0][0]["text"] == "Open The Yard"


def test_the_gm_sees_who_got_the_phone(night, roster):
    db.set_setting(roster, "notify_mode", "on", by="test")
    roster.execute("UPDATE attendees SET tg_user_id=900, can_message=1 WHERE handle=?", (desk(roster),))
    s = game.state(roster, at(night, -1), night["id"])
    assert {p["phone_msg"] for side in s["halves"].values() for p in side} == {None}   # not yet
    game.act(roster, night["id"], "start", GM, at(night, 0))
    s = game.state(roster, at(night, 1), night["id"])
    got = {p["handle"]: p["phone_msg"] for side in s["halves"].values() for p in side}
    assert got[desk(roster)] == "waiting"
    # The other three never opened The Yard, so no message can reach them:
    # the GM hands them the desk handset instead of waiting.
    assert {h: v for h, v in got.items() if h != desk(roster)} == {
        h: "unreachable" for h in got if h != desk(roster)}
    notify.deliver(roster, lambda chat, text, go: None)
    s = game.state(roster, at(night, 2), night["id"])
    got = {p["handle"]: p["phone_msg"] for side in s["halves"].values() for p in side}
    assert got[desk(roster)] == "sent"


def test_in_test_mode_the_gm_is_told_the_message_was_held(night, roster):
    roster.execute("UPDATE attendees SET tg_user_id=900, can_message=1 WHERE handle=?", (desk(roster),))
    game.act(roster, night["id"], "start", GM, at(night, 0))
    notify.deliver(roster, lambda chat, text, go: None)                 # notify_mode is "owner"
    s = game.state(roster, at(night, 2), night["id"])
    got = {p["handle"]: p["phone_msg"] for side in s["halves"].values() for p in side}
    assert got[desk(roster)] == "held"


def test_the_phone_endpoint_serves_the_file_with_no_store(night, roster, client, monkeypatch):
    import app as webapp
    game.act(roster, night["id"], "start", GM, at(night, 0))
    h = desk(roster)
    roster.execute("UPDATE attendees SET tg_user_id=900 WHERE handle=?", (h,))
    auth = {"Authorization": "tma " + sign(900, h)}
    monkeypatch.setattr(webapp, "now_utc", lambda: at(night, 2))
    r = client.get("/api/escape/phone", headers=auth)
    assert r.status_code == 200 and r.get_data(as_text=True) == PHONE_PAGE
    assert r.headers["Cache-Control"] == "no-store"
    status = client.get("/api/escape/phone/status", headers=auth).get_json()["data"]
    assert status["code"] is None and status["zone"] == "B"
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
    assert len(s["halves"]["A"]) == 2 and len(s["halves"]["B"]) == 2
    assert [c["key"] for c in s["cues"]] == ["hint1", "hint2", "merge", "hint3"]
    assert s["cues"][0]["at"] == "4:30" and s["reset"]
    assert not s["started"] and s["remaining_seconds"] == 15 * 60


def test_a_running_game_is_the_current_one_until_it_ends(night, roster):
    game.act(roster, night["id"], "start", GM, at(night, 3))
    later = at(night, 40)                                  # past the second game's start
    assert game.state(roster, later)["slot_id"] == night["id"]
    game.act(roster, night["id"], "end", GM, later)
    assert game.state(roster, later)["slot_id"] != night["id"]


def test_starting_twice_and_pausing_a_stopped_game_are_refused(night, roster):
    with pytest.raises(ClaimError) as e:
        game.act(roster, night["id"], "pause", GM, at(night, 0))
    assert e.value.code == "GAME_STATE"
    game.act(roster, night["id"], "start", GM, at(night, 0))
    with pytest.raises(ClaimError):
        game.act(roster, night["id"], "start", GM, at(night, 1))


def test_every_gm_press_is_logged(night, roster):
    game.act(roster, night["id"], "start", GM, at(night, 0))
    row = roster.execute("SELECT * FROM audit_log WHERE action='Game started'").fetchone()
    assert (row["actor_name"], row["entity"], row["entity_id"]) == ("Ryan", "slot", str(night["id"]))


def test_swapping_a_half_after_the_start_is_logged(night, roster):
    game.act(roster, night["id"], "start", GM, at(night, 0))
    h = flat(roster)
    game.halves(roster, night["id"], GM, swap_attendee_id=pid(roster, h))
    assert zone(roster, h) == "B"
    row = roster.execute("SELECT * FROM audit_log WHERE action='Half swapped'").fetchone()
    assert '"after_start": true' in row["details"] and h in row["details"]


def test_rebalance_evens_the_halves(night, roster):
    roster.execute("UPDATE escape_bookings SET zone='A'")
    game.halves(roster, night["id"], GM, rebalance=True)
    zones = [r[0] for r in roster.execute("SELECT zone FROM escape_bookings WHERE status='booked'")]
    assert sorted(zones) == ["A", "A", "B", "B"]


def test_a_hint_goes_to_the_actor_once(night, roster):
    db.set_setting(roster, "actor_chat_id", 5550, by="bot")
    game.act(roster, night["id"], "start", GM, at(night, 0))
    assert game.send_cue(roster, night["id"], "hint1", GM, at(night, 5)) == {"to_actor": True}
    with pytest.raises(ClaimError):
        game.send_cue(roster, night["id"], "hint1", GM, at(night, 5))
    assert game.send_cue(roster, night["id"], "merge", GM, at(night, 8)) == {"to_actor": False}
    msgs = roster.execute("SELECT * FROM direct_messages").fetchall()
    assert len(msgs) == 1 and msgs[0]["chat_id"] == 5550
    assert [c["sent"] for c in game.state(roster, at(night, 9), night["id"])["cues"]] == [True, False, True, False]

    sent = []
    counts = notify.deliver_direct(roster, lambda chat, text, go, button=True: sent.append((chat, button)))
    assert counts == {"sent": 1} and sent == [(5550, False)]


def test_a_hint_without_an_actor_is_still_recorded(night, roster):
    assert game.send_cue(roster, night["id"], "hint2", GM, at(night, 5)) == {"to_actor": False}
    assert roster.execute("SELECT COUNT(*) FROM direct_messages").fetchone()[0] == 0


def test_the_actor_chat_survives_a_restart(night, roster):
    db.set_setting(roster, "actor_chat_id", 5550, by="bot")
    db.seed_settings(roster)
    assert db.get_setting(roster, "actor_chat_id") == 5550


def test_the_gm_console_over_http(night, roster, monkeypatch):
    import app as webapp
    monkeypatch.setattr(webapp, "now_utc", lambda: at(night, -2))
    gm = Console("gm", "Ryan", "GM")
    s = gm.get("/admin/api/gm/state").get_json()["data"]
    assert s["slot_id"] == night["id"]
    assert gm.post(f"/admin/api/gm/{night['id']}/start").status_code == 200
    swap = s["halves"]["A"][0]["id"]
    assert gm.post(f"/admin/api/gm/{night['id']}/halves", {"swap_attendee_id": swap}).status_code == 200
    assert gm.post(f"/admin/api/gm/{night['id']}/cues/hint1").status_code == 200
    assert err(gm.post(f"/admin/api/gm/{night['id']}/dance"))["code"] == "VALIDATION_FAILED"
    # One phone PIN since 22 Sep (STATE.md decision 126): any phone sign-in
    # runs the game, not only one made with the GM PIN.
    booth_phone = Console()
    assert booth_phone.post(f"/admin/api/gm/{night['id']}/end").status_code == 200
