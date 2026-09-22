"""Escape-room games, capacity, halves and group booking; the free jamming
studio; time clashes between the two. §17.5, §9 rules 15-20, plus the group
rules decided 17 Sep (STATE.md §5): owner-only edits, add/remove only, lock at
the cutoff.
"""

import threading
from datetime import datetime, timedelta, timezone

import pytest

import config
import db
from conftest import sign
from services import bookings
from services.claims import ClaimError
from test_claims_concurrent import (  # noqa: F401 - fixtures are used by name
    Console, err, roster, secrets_and_limits,
)

TODAY = datetime(2026, 9, 17, 4, 0, tzinfo=timezone.utc)      # a week before


@pytest.fixture(autouse=True)
def clear_friend_limit():
    bookings.FRIEND_FAILS.clear()
    yield
    bookings.FRIEND_FAILS.clear()


@pytest.fixture()
def games(roster):
    bookings.generate_slots(roster)
    return roster


def ids(conn):
    return {r["handle"]: r["id"] for r in conn.execute("SELECT id, handle FROM attendees")}


def slot(conn, n=0):
    return conn.execute("SELECT * FROM slots WHERE room='escape' ORDER BY starts_at "
                        "LIMIT 1 OFFSET ?", (n,)).fetchone()


def starts(s):
    return datetime.fromisoformat(s["starts_at"])


def active(conn, slot_id):
    return conn.execute("SELECT COUNT(*) FROM escape_bookings WHERE slot_id=? "
                        "AND status IN ('booked','checked_in')", (slot_id,)).fetchone()[0]


def queued(conn, kind):
    return conn.execute("SELECT * FROM notifications WHERE kind=?", (kind,)).fetchall()


HANDLES = ["bananabelles", "sharmaineangg", "t_shixuan", "poopoobomber91", "jananabana",
           "bingkiat", "heidily", "j280509", "feliciaandiana", "skibadena", "kaykaykxylene",
           "mr_rishieparker", "softforcotton", "shalalapootpoot967", "aalexiaho", "joncjy", "zhnlun"]


# ---------------------------------------------------------------------------
# The games
# ---------------------------------------------------------------------------

def test_twenty_one_games_from_3_05_to_9_45(games):
    """3–10 PM since 22 Sep (STATE.md 131); games 3:05–9:45 since the same evening
    (STATE.md 133), so the last one ends with the doors."""
    rows = games.execute("SELECT * FROM slots WHERE room='escape' ORDER BY starts_at").fetchall()
    local = [datetime.fromisoformat(r["starts_at"]).astimezone(config.TIMEZONE) for r in rows]
    assert len(rows) == 21
    assert local[0].strftime("%Y-%m-%d %H:%M") == "2026-09-24 15:05"
    assert local[-1].strftime("%H:%M") == "21:45"      # ends 10:00, with the doors
    assert all((b - a) == timedelta(minutes=20) for a, b in zip(local, local[1:]))
    assert all(datetime.fromisoformat(r["ends_at"]) - datetime.fromisoformat(r["starts_at"])
               == timedelta(minutes=15) for r in rows)
    assert sum(r["capacity"] for r in rows) == 252


def test_generating_again_changes_nothing(games):
    done = bookings.generate_slots(games)
    assert done["escape"] == {"new": 0, "removed": 0, "total": 21, "stuck": [], "over": []}
    assert done["jam"] == {"new": 0, "removed": 0, "total": 14, "stuck": [], "over": []}


def test_board_before_the_event(games):
    me = ids(games)["heidily"]
    d = bookings.board(games, me, TODAY)
    assert len(d["slots"]) == 21 and d["my_booking"] is None
    assert all(s["status"] == "open" and s["seats_left"] == 12 for s in d["slots"])
    assert d["max_party"] == 6


# ---------------------------------------------------------------------------
# Capacity — §17.5
# ---------------------------------------------------------------------------

def test_the_13th_person_cannot_book_a_12_seat_game(games):
    p, s = ids(games), slot(games)
    for h in HANDLES[:12]:
        bookings.book(games, p[h], s["id"], [], TODAY)
    with pytest.raises(ClaimError) as e:
        bookings.book(games, p[HANDLES[12]], s["id"], [], TODAY)
    assert e.value.code == "SLOT_FULL"
    assert active(games, s["id"]) == 12


def test_twelve_bookings_split_into_halves_of_six(games):
    p, s = ids(games), slot(games)
    for h in HANDLES[:12]:
        bookings.book(games, p[h], s["id"], [], TODAY)
    board = bookings.admin_board(games, TODAY)["escape"][0]
    assert board["booked"] == 12 and board["half_a"] == 6 and board["half_b"] == 6


def test_a_half_full_game_stays_open_to_others(games):
    p, s = ids(games), slot(games)
    bookings.book(games, p["heidily"], s["id"], ["bananabelles", "t_shixuan"], TODAY)
    d = bookings.board(games, p["joncjy"], TODAY)
    assert d["slots"][0]["status"] == "open" and d["slots"][0]["seats_left"] == 9
    assert bookings.book(games, p["joncjy"], s["id"], [], TODAY)["ref"].startswith("ESC-")


def test_two_groups_racing_for_the_last_seats(games):
    """Ten taken, two groups of two at the same instant: exactly one fits."""
    p, s = ids(games), slot(games)
    for h in HANDLES[:10]:
        bookings.book(games, p[h], s["id"], [], TODAY)
    barrier = threading.Barrier(2)
    results = []

    def run(owner, friend):
        c = db.connect()
        try:
            barrier.wait()
            bookings.book(c, p[owner], s["id"], [friend], TODAY)
            results.append("ok")
        except ClaimError as exc:
            results.append(exc.code)
        finally:
            c.close()

    threads = [threading.Thread(target=run, args=a)
               for a in (("mr_rishieparker", "softforcotton"), ("aalexiaho", "joncjy"))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["SLOT_FULL", "ok"]
    assert active(games, s["id"]) == 12


def test_the_same_friend_in_two_groups_at_once(games):
    p = ids(games)
    barrier = threading.Barrier(2)
    results = []

    def run(owner, n):
        c = db.connect()
        try:
            barrier.wait()
            bookings.book(c, p[owner], slot(c, n)["id"], ["heidily"], TODAY)
            results.append("ok")
        except ClaimError as exc:
            results.append(exc.code)
        finally:
            c.close()

    threads = [threading.Thread(target=run, args=a) for a in (("joncjy", 0), ("zhnlun", 1))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["FRIEND_ALREADY_BOOKED", "ok"]
    assert games.execute("SELECT COUNT(*) FROM escape_bookings WHERE attendee_id=? "
                         "AND status='booked'", (p["heidily"],)).fetchone()[0] == 1


# ---------------------------------------------------------------------------
# Groups — all or nothing (§9 r16)
# ---------------------------------------------------------------------------

def test_one_ineligible_friend_books_nobody(games):
    p, s = ids(games), slot(games)
    games.execute("UPDATE attendees SET status='inactive' WHERE handle='joncjy'")
    for bad in (["bananabelles", "ryanlow"], ["bananabelles", "@JonCJY"]):
        with pytest.raises(ClaimError) as e:
            bookings.book(games, p["heidily"], s["id"], bad, TODAY)
        assert e.value.code == "FRIEND_NOT_ELIGIBLE"
    assert e.value.extra["handles"] == ["joncjy"]
    assert active(games, s["id"]) == 0


def test_a_friend_already_in_a_game_books_nobody(games):
    p = ids(games)
    bookings.book(games, p["bananabelles"], slot(games, 3)["id"], [], TODAY)
    with pytest.raises(ClaimError) as e:
        bookings.book(games, p["heidily"], slot(games)["id"], ["t_shixuan", "bananabelles"], TODAY)
    assert e.value.code == "FRIEND_ALREADY_BOOKED" and e.value.extra["handles"] == ["bananabelles"]
    assert active(games, slot(games)["id"]) == 0


def test_a_group_bigger_than_the_seats_left_books_nobody(games):
    p, s = ids(games), slot(games)
    for h in HANDLES[:10]:
        bookings.book(games, p[h], s["id"], [], TODAY)
    with pytest.raises(ClaimError) as e:
        bookings.book(games, p["aalexiaho"], s["id"], ["joncjy", "zhnlun"], TODAY)
    assert e.value.code == "SLOT_FULL" and e.value.extra["seats_left"] == 2
    assert active(games, s["id"]) == 10


def test_group_size_is_capped(games):
    p, s = ids(games), slot(games)
    with pytest.raises(ClaimError) as e:
        bookings.book(games, p["heidily"], s["id"], HANDLES[:6], TODAY)      # 7 with the owner
    assert e.value.code == "LIMIT_REACHED"
    assert bookings.book(games, p["heidily"], s["id"], HANDLES[:5], TODAY)["friends"] == HANDLES[:5]


def test_usernames_are_normalised_and_deduplicated(games):
    p, s = ids(games), slot(games)
    done = bookings.book(games, p["heidily"], s["id"],
                         ["@BananaBelles ", "t.me/bananabelles", "heidily", "  "], TODAY)
    assert done["friends"] == ["bananabelles"]
    assert active(games, s["id"]) == 2


def test_booking_twice_is_refused(games):
    p = ids(games)
    bookings.book(games, p["heidily"], slot(games)["id"], [], TODAY)
    with pytest.raises(ClaimError) as e:
        bookings.book(games, p["heidily"], slot(games, 1)["id"], [], TODAY)
    assert e.value.code == "ALREADY_BOOKED"


def test_probing_the_list_is_rate_limited(games):
    p, s = ids(games), slot(games)
    db.set_setting(games, "friend_fail_limit", 3, by="test")
    codes = []
    for n in range(4):
        try:
            bookings.book(games, p["heidily"], s["id"], [f"nobody_{n}x"], TODAY)
        except ClaimError as exc:
            codes.append(exc.code)
    assert codes == ["FRIEND_NOT_ELIGIBLE"] * 3 + ["RATE_LIMITED"]


# ---------------------------------------------------------------------------
# Who may change a group
# ---------------------------------------------------------------------------

def test_the_owner_sees_and_edits_the_group(games):
    p, s = ids(games), slot(games)
    bookings.book(games, p["heidily"], s["id"], ["bananabelles"], TODAY)
    v = bookings.my_view(games, p["heidily"], TODAY)
    assert v["i_am_owner"] and v["can_add"] and v["can_leave"]
    assert [(g["handle"], g["owner"], g["removable"]) for g in v["group"]] == [
        ("heidily", True, False), ("bananabelles", False, True)]
    assert v["zone"] is None                         # halves stay hidden until the game
    bookings.add_friends(games, p["heidily"], ["t_shixuan"], TODAY)
    assert active(games, s["id"]) == 3


def test_a_friend_cannot_add_or_remove_anyone(games):
    p, s = ids(games), slot(games)
    bookings.book(games, p["heidily"], s["id"], ["bananabelles", "t_shixuan"], TODAY)
    v = bookings.my_view(games, p["bananabelles"], TODAY)
    assert not v["i_am_owner"] and not v["can_add"]
    assert v["booked_by"]["handle"] == "heidily"
    assert not any(g["removable"] for g in v["group"])
    with pytest.raises(ClaimError) as e:
        bookings.add_friends(games, p["bananabelles"], ["joncjy"], TODAY)
    assert e.value.code == "FORBIDDEN"
    with pytest.raises(ClaimError) as e:
        bookings.remove_friend(games, p["bananabelles"], "t_shixuan", TODAY)
    assert e.value.code == "FORBIDDEN"
    assert active(games, s["id"]) == 3


def test_the_owner_cannot_remove_another_groups_player(games):
    p, s = ids(games), slot(games)
    bookings.book(games, p["heidily"], s["id"], ["bananabelles"], TODAY)
    bookings.book(games, p["joncjy"], s["id"], ["zhnlun"], TODAY)
    with pytest.raises(ClaimError) as e:
        bookings.remove_friend(games, p["heidily"], "zhnlun", TODAY)
    assert e.value.code == "FORBIDDEN"


def test_removing_a_friend_frees_the_seat_and_tells_them(games):
    p, s = ids(games), slot(games)
    bookings.book(games, p["heidily"], s["id"], ["bananabelles"], TODAY)
    games.execute("UPDATE notifications SET status='sent'")      # they were told
    bookings.remove_friend(games, p["heidily"], "@BananaBelles", TODAY)
    assert active(games, s["id"]) == 1
    msg = queued(games, "friend_removed")
    assert len(msg) == 1 and msg[0]["attendee_id"] == p["bananabelles"]
    assert "@heidily" in msg[0]["text"]
    # They are free to book their own game straight away.
    assert bookings.book(games, p["bananabelles"], slot(games, 2)["id"], [], TODAY)


def test_friends_are_told_they_were_added(games):
    p, s = ids(games), slot(games)
    bookings.book(games, p["heidily"], s["id"], ["bananabelles", "t_shixuan"], TODAY)
    msgs = queued(games, "friend_added")
    assert sorted(m["attendee_id"] for m in msgs) == sorted([p["bananabelles"], p["t_shixuan"]])
    # Structured since 19 Sep: a heading, labelled facts, then one line of
    # what to do. The booker's name is a labelled fact, not buried in prose.
    assert "you're in for The Last Guest" in msgs[0]["text"]
    assert "booked by @heidily" in msgs[0]["text"] and "7:25 PM" not in msgs[0]["text"]
    assert "3:05 PM" in msgs[0]["text"] and "leave this game, until 3:00 PM" in msgs[0]["text"]
    assert "the escape room entrance" in msgs[0]["text"]            # where to gather
    assert msgs[0]["button_path"] == "ticket"
    receipt = queued(games, "escape_booked")         # the booker gets a receipt
    assert len(receipt) == 1 and receipt[0]["attendee_id"] == p["heidily"]
    assert "who's in:" in receipt[0]["text"]
    # One name a line, in the relaxed voice (22 Sep, STATE.md 132).
    for who in ("you", "@bananabelles", "@t_shixuan"):
        assert f"\n{who}\n" in receipt[0]["text"], who


def test_a_friend_can_leave_and_the_owner_hears(games):
    p, s = ids(games), slot(games)
    bookings.book(games, p["heidily"], s["id"], ["bananabelles"], TODAY)
    ref = bookings.active_booking(games, p["bananabelles"])["ref_code"]
    # 20 minutes before: inside the owner's 30-minute cancel cutoff, but a
    # friend who didn't choose this game may still leave.
    late = starts(s) - timedelta(minutes=20)
    assert bookings.cancel(games, p["bananabelles"], ref, late) == {"cancelled": True, "left": True}
    msg = queued(games, "member_left")
    assert len(msg) == 1 and msg[0]["attendee_id"] == p["heidily"]
    own = bookings.active_booking(games, p["heidily"])["ref_code"]
    with pytest.raises(ClaimError) as e:
        bookings.cancel(games, p["heidily"], own, late)
    assert e.value.code == "SLOT_CLOSED"


def test_the_owner_leaving_keeps_their_friends_booked(games):
    p, s = ids(games), slot(games)
    bookings.book(games, p["heidily"], s["id"], ["bananabelles"], TODAY)
    own = bookings.active_booking(games, p["heidily"])["ref_code"]
    bookings.cancel(games, p["heidily"], own, TODAY)
    assert active(games, s["id"]) == 1
    v = bookings.my_view(games, p["bananabelles"], TODAY)
    assert [g["handle"] for g in v["group"]] == ["bananabelles"]


def test_you_can_only_cancel_your_own_booking(games):
    p, s = ids(games), slot(games)
    bookings.book(games, p["heidily"], s["id"], ["bananabelles"], TODAY)
    theirs = bookings.active_booking(games, p["bananabelles"])["ref_code"]
    with pytest.raises(ClaimError) as e:
        bookings.cancel(games, p["heidily"], theirs, TODAY)
    assert e.value.code == "NO_BOOKING"


def test_edits_lock_at_the_booking_cutoff(games):
    p, s = ids(games), slot(games)
    bookings.book(games, p["heidily"], s["id"], ["bananabelles"], TODAY)
    locked = starts(s) - timedelta(minutes=4)
    v = bookings.my_view(games, p["heidily"], locked)
    assert not v["can_add"] and not v["can_leave"] and not any(g["removable"] for g in v["group"])
    assert v["locked"] and not bookings.my_view(games, p["heidily"], TODAY)["locked"]
    for fn in (lambda: bookings.add_friends(games, p["heidily"], ["t_shixuan"], locked),
               lambda: bookings.remove_friend(games, p["heidily"], "bananabelles", locked),
               lambda: bookings.book(games, p["joncjy"], s["id"], [], locked)):
        with pytest.raises(ClaimError) as e:
            fn()
        assert e.value.code == "SLOT_CLOSED"
    with pytest.raises(ClaimError) as e:
        bookings.book(games, p["joncjy"], s["id"], [], starts(s) + timedelta(minutes=1))
    assert e.value.code == "SLOT_STARTED"


def test_halves_show_once_the_game_starts(games):
    p, s = ids(games), slot(games)
    bookings.book(games, p["heidily"], s["id"], ["bananabelles"], TODAY)
    during = starts(s) + timedelta(minutes=1)
    zones = {bookings.my_view(games, p[h], during)["zone"] for h in ("heidily", "bananabelles")}
    assert zones == {"A", "B"}


def test_a_blocked_game_cannot_be_booked(games):
    p, s = ids(games), slot(games)
    games.execute("UPDATE slots SET is_blocked=1 WHERE id=?", (s["id"],))
    with pytest.raises(ClaimError) as e:
        bookings.book(games, p["heidily"], s["id"], [], TODAY)
    assert e.value.code == "SLOT_BLOCKED"
    assert bookings.board(games, p["heidily"], TODAY)["slots"][0]["status"] == "blocked"


def test_every_change_is_audited(games):
    p, s = ids(games), slot(games)
    bookings.book(games, p["heidily"], s["id"], ["bananabelles"], TODAY)
    bookings.remove_friend(games, p["heidily"], "bananabelles", TODAY)
    actions = [r[0] for r in games.execute("SELECT action FROM audit_log ORDER BY id")]
    for a in ("Escape game booked", "Added to an escape game", "Removed from an escape game"):
        assert a in actions


# ---------------------------------------------------------------------------
# Through the Mini App API
# ---------------------------------------------------------------------------

def tma(init):
    return {"Authorization": "tma " + init}


def test_booking_through_the_api(games, client):
    heidi = tma(sign(2001, "heidily", "Heidi"))
    anna = tma(sign(2002, "bananabelles", "Anna"))
    client.post("/api/session", headers=anna)          # Anna opened the app once
    s = slot(games)

    d = client.get("/api/escape/slots", headers=heidi).get_json()["data"]
    assert len(d["slots"]) == 21 and d["slots"][0]["starts_at"].endswith("+08:00")

    r = client.post("/api/escape/bookings", headers=heidi,
                    json={"slot_id": s["id"], "friends": ["bananabelles", "nobody_here"]})
    assert r.status_code == 409 and err(r)["code"] == "FRIEND_NOT_ELIGIBLE"

    r = client.post("/api/escape/bookings", headers=heidi,
                    json={"slot_id": s["id"], "friends": ["bananabelles"]})
    assert r.status_code == 200, r.get_json()

    me = client.get("/api/me", headers=heidi).get_json()["data"]
    eb = me["escape_booking"]
    assert eb["i_am_owner"] and [g["handle"] for g in eb["group"]] == ["heidily", "bananabelles"]
    assert eb["group"][1]["reachable"] is True          # Anna has opened the app
    theirs = client.get("/api/me", headers=anna).get_json()["data"]["escape_booking"]
    assert theirs["booked_by"]["handle"] == "heidily" and theirs["can_leave"]

    assert client.post("/api/escape/group", headers=anna,
                       json={"add": ["t_shixuan"]}).status_code == 403
    assert client.post("/api/escape/group", headers=heidi,
                       json={"add": ["t_shixuan"]}).status_code == 200
    t = client.get("/api/me", headers=heidi).get_json()["data"]["escape_booking"]["group"][2]
    assert t["handle"] == "t_shixuan" and t["reachable"] is False     # never opened the app

    assert client.delete("/api/escape/group/t_shixuan", headers=heidi).status_code == 200
    r = client.delete(f"/api/escape/bookings/{theirs['ref']}", headers=anna)
    assert r.get_json()["data"] == {"cancelled": True, "left": True}
    assert client.get("/api/me", headers=anna).get_json()["data"]["escape_booking"] is None


def test_someone_off_the_list_cannot_book(games, client):
    r = client.post("/api/escape/bookings", headers=tma(sign(3001, "ryanlow", "Ryan")),
                    json={"slot_id": slot(games)["id"]})
    assert r.status_code == 403 and err(r)["code"] == "NOT_ON_LIST"


def test_bad_friend_lists_are_refused(games, client):
    r = client.post("/api/escape/bookings", headers=tma(sign(2001, "heidily")),
                    json={"slot_id": slot(games)["id"], "friends": {"a": 1}})
    assert err(r)["code"] == "VALIDATION_FAILED"


def test_the_booth_sees_the_half(games):
    p, s = ids(games), slot(games)
    bookings.book(games, p["heidily"], s["id"], [], TODAY)
    code = games.execute("SELECT pass_code FROM attendees WHERE handle='heidily'").fetchone()[0]
    esc = Console().lookup(code).get_json()["data"]["person"]["escape"]
    assert esc["zone"] in ("A", "B") and esc["ref"].startswith("ESC-")


def test_the_console_schedule_is_real(games):
    p, s = ids(games), slot(games)
    bookings.book(games, p["heidily"], s["id"], ["bananabelles"], TODAY)
    d = Console("admin").get("/admin/api/slots").get_json()["data"]
    assert d["seats_total"] == 252 and d["seats_taken"] == 2 and d["escape"][0]["booked"] == 2
    assert len(d["jam"]) == 14 and d["jam"][0]["status"] == "open"
    assert Console().get("/admin/api/slots").status_code == 403


def test_the_person_page_shows_who_booked_them(games):
    p, s = ids(games), slot(games)
    bookings.book(games, p["heidily"], s["id"], ["bananabelles"], TODAY)
    d = Console("admin").get(f"/admin/api/people/{p['bananabelles']}").get_json()["data"]
    assert d["bookings"][0]["kind"] == "escape" and d["bookings"][0]["booked_by"] == "@heidily"


def test_write_access_is_remembered(games, client):
    games.execute("UPDATE attendees SET can_message=0 WHERE handle='heidily'")
    h = tma(sign(2001, "heidily"))
    assert client.get("/api/me", headers=h).get_json()["data"]["can_message"] is False
    client.post("/api/me/messages", headers=h, json={"allowed": True})
    assert client.get("/api/me", headers=h).get_json()["data"]["can_message"] is True


# ---------------------------------------------------------------------------
# Regenerating the schedule when Settings change
# ---------------------------------------------------------------------------

def test_a_shorter_evening_removes_unbooked_games(games):
    db.set_setting(games, "last_game", "21:25", by="test")
    done = bookings.generate_slots(games)["escape"]
    assert done["removed"] == 1 and done["total"] == 20 and done["stuck"] == []


def test_a_booked_game_is_never_removed(games):
    p, last = ids(games), slot(games, 20)                 # 9:45 PM
    bookings.book(games, p["heidily"], last["id"], [], TODAY)
    db.set_setting(games, "last_game", "21:25", by="test")
    done = bookings.generate_slots(games)["escape"]
    assert done["removed"] == 0 and done["stuck"] == ["9:45 PM"] and done["total"] == 21


def test_a_game_booked_once_is_retired_not_deleted(games):
    p, last = ids(games), slot(games, 20)
    ref = bookings.book(games, p["heidily"], last["id"], [], TODAY)["ref"]
    bookings.cancel(games, p["heidily"], ref, TODAY)
    db.set_setting(games, "last_game", "21:25", by="test")
    assert bookings.generate_slots(games)["escape"]["removed"] == 1
    assert len(bookings.board(games, p["heidily"], TODAY)["slots"]) == 20
    # And it comes back if the evening is extended again.
    db.set_setting(games, "last_game", "21:45", by="test")
    bookings.generate_slots(games)
    assert len(bookings.board(games, p["heidily"], TODAY)["slots"]) == 21


# ---------------------------------------------------------------------------
# The jamming studio - free, and booked by instrument since 19 Sep.
#
# It has been three things. One booking held the whole room; then a group
# held it; now each of the five instruments is booked separately and anyone
# may join a room somebody else started. The instrument is what is actually
# scarce - there is one bass - so that is what a booking claims.
# ---------------------------------------------------------------------------

def jam(conn, n=0):
    return conn.execute("SELECT * FROM slots WHERE room='jam' ORDER BY starts_at LIMIT 1 OFFSET ?",
                        (n,)).fetchone()


def jam_seats(conn, slot_id):
    return conn.execute("SELECT COUNT(*) c FROM jam_bookings WHERE slot_id=? AND status='confirmed'",
                        (slot_id,)).fetchone()["c"]


def player(handle, instrument):
    return {"handle": handle, "instrument": instrument}


def test_fourteen_jam_slots_from_3_to_9_30(games):
    rows = games.execute("SELECT * FROM slots WHERE room='jam' ORDER BY starts_at").fetchall()
    local = [datetime.fromisoformat(r["starts_at"]).astimezone(config.TIMEZONE).strftime("%H:%M") for r in rows]
    assert local[0] == "15:00" and local[-1] == "21:30" and len(rows) == 14
    assert all(r["price_cents"] == 0 for r in rows)
    assert all(r["capacity"] == len(config.INSTRUMENTS) for r in rows)


def test_booking_one_instrument(games):
    p = ids(games)
    done = bookings.book_jam(games, p["heidily"], jam(games)["id"], "bass", [], TODAY)
    assert done["ref"].startswith("JAM-")
    mine = bookings.my_jam(games, p["heidily"], TODAY)[0]
    assert mine["instrument"] == "bass" and mine["instrument_label"] == "Bass"
    assert mine["i_am_owner"] and [g["handle"] for g in mine["line_up"]] == ["heidily"]
    board = bookings.jam_board(games, p["heidily"], TODAY)
    assert board["slots"][0]["status"] == "mine"
    assert board["slots"][0]["mine_instrument"] == "bass"
    assert "bass" not in board["slots"][0]["free"]
    assert len(board["slots"][0]["free"]) == 4
    assert len(queued(games, "jam_booked")) == 1


def test_a_stranger_can_take_another_instrument_in_the_same_slot(games):
    """The point of the 19 Sep change: the room is shared, the instrument is
    not. Five people who do not know each other is a jam."""
    p = ids(games)
    bookings.book_jam(games, p["heidily"], jam(games)["id"], "bass", [], TODAY)
    assert bookings.book_jam(games, p["joncjy"], jam(games)["id"], "drums", [], TODAY)
    assert jam_seats(games, jam(games)["id"]) == 2
    board = bookings.jam_board(games, p["zhnlun"], TODAY)
    assert board["slots"][0]["status"] == "open"
    assert set(board["slots"][0]["free"]) == {"acoustic", "electric", "keys"}


def test_two_people_cannot_take_the_same_instrument(games):
    p = ids(games)
    bookings.book_jam(games, p["heidily"], jam(games)["id"], "drums", [], TODAY)
    with pytest.raises(ClaimError) as e:
        bookings.book_jam(games, p["joncjy"], jam(games)["id"], "drums", [], TODAY)
    assert e.value.code == "INSTRUMENT_TAKEN"
    assert "drums" in e.value.extra["instruments"]
    assert jam_seats(games, jam(games)["id"]) == 1


def test_booking_instruments_for_friends(games):
    p = ids(games)
    done = bookings.book_jam(games, p["heidily"], jam(games)["id"], "bass",
                             [player("joncjy", "drums"), player("bingkiat", "keys")], TODAY)
    assert done["friends"] == ["joncjy", "bingkiat"]
    assert jam_seats(games, jam(games)["id"]) == 3
    assert len(queued(games, "jam_friend_added")) == 2
    theirs = bookings.my_jam(games, p["joncjy"], TODAY)[0]
    assert theirs["instrument"] == "drums" and theirs["i_am_owner"] is False
    assert theirs["booked_by"]["handle"] == "heidily"
    # The line-up is the whole room, so everyone can see who is on what.
    assert {g["handle"]: g["instrument"] for g in theirs["line_up"]} == {
        "heidily": "bass", "joncjy": "drums", "bingkiat": "keys"}


def test_a_jam_group_is_all_or_nothing(games):
    p = ids(games)
    with pytest.raises(ClaimError) as e:
        bookings.book_jam(games, p["heidily"], jam(games)["id"], "bass",
                          [player("joncjy", "drums"), player("notarealperson", "keys")], TODAY)
    assert e.value.code == "FRIEND_NOT_ELIGIBLE"
    assert jam_seats(games, jam(games)["id"]) == 0


def test_two_of_your_friends_cannot_share_an_instrument(games):
    p = ids(games)
    with pytest.raises(ClaimError) as e:
        bookings.book_jam(games, p["heidily"], jam(games)["id"], "bass",
                          [player("joncjy", "drums"), player("bingkiat", "drums")], TODAY)
    assert e.value.code == "VALIDATION_FAILED"
    assert jam_seats(games, jam(games)["id"]) == 0


def test_you_cannot_take_an_instrument_a_friend_is_taking(games):
    p = ids(games)
    with pytest.raises(ClaimError) as e:
        bookings.book_jam(games, p["heidily"], jam(games)["id"], "drums",
                          [player("joncjy", "drums")], TODAY)
    assert e.value.code == "VALIDATION_FAILED"
    assert jam_seats(games, jam(games)["id"]) == 0


def test_a_made_up_instrument_is_refused(games):
    p = ids(games)
    for bad in ("triangle", "", None):
        with pytest.raises(ClaimError) as e:
            bookings.book_jam(games, p["heidily"], jam(games)["id"], bad, [], TODAY)
        assert e.value.code == "VALIDATION_FAILED"


def test_the_room_fills_at_five(games):
    p = ids(games)
    for h, i in zip(HANDLES, [k for k, _ in config.INSTRUMENTS]):
        bookings.book_jam(games, p[h], jam(games)["id"], i, [], TODAY)
    assert jam_seats(games, jam(games)["id"]) == 5
    assert bookings.jam_board(games, p["joncjy"], TODAY)["slots"][0]["free"] == []
    with pytest.raises(ClaimError) as e:
        bookings.book_jam(games, p["joncjy"], jam(games)["id"], "bass", [], TODAY)
    assert e.value.code in ("INSTRUMENT_TAKEN", "SLOT_FULL")


def test_adding_and_removing_people_after_booking(games):
    p = ids(games)
    ref = bookings.book_jam(games, p["heidily"], jam(games)["id"], "bass",
                            [player("joncjy", "drums")], TODAY)["ref"]
    bookings.add_jam_friends(games, p["heidily"], ref, [player("bingkiat", "keys")], TODAY)
    assert jam_seats(games, jam(games)["id"]) == 3
    bookings.remove_jam_friend(games, p["heidily"], ref, "joncjy", TODAY)
    assert jam_seats(games, jam(games)["id"]) == 2
    assert bookings.my_jam(games, p["joncjy"], TODAY) == []
    # The drums are free again, and the app says so.
    assert "drums" in bookings.jam_board(games, p["zhnlun"], TODAY)["slots"][0]["free"]


def test_you_cannot_add_someone_on_a_taken_instrument(games):
    p = ids(games)
    ref = bookings.book_jam(games, p["heidily"], jam(games)["id"], "bass", [], TODAY)["ref"]
    bookings.book_jam(games, p["zhnlun"], jam(games)["id"], "drums", [], TODAY)
    with pytest.raises(ClaimError) as e:
        bookings.add_jam_friends(games, p["heidily"], ref, [player("joncjy", "drums")], TODAY)
    assert e.value.code == "INSTRUMENT_TAKEN"


def test_only_the_booker_can_change_the_group(games):
    p = ids(games)
    bookings.book_jam(games, p["heidily"], jam(games)["id"], "bass",
                      [player("joncjy", "drums")], TODAY)
    theirs = bookings.my_jam(games, p["joncjy"], TODAY)[0]["ref"]
    with pytest.raises(ClaimError) as e:
        bookings.add_jam_friends(games, p["joncjy"], theirs, [player("bingkiat", "keys")], TODAY)
    assert e.value.code == "FORBIDDEN"


def test_someone_added_can_leave_without_cancelling_the_group(games):
    p = ids(games)
    bookings.book_jam(games, p["heidily"], jam(games)["id"], "bass",
                      [player("joncjy", "drums")], TODAY)
    theirs = bookings.my_jam(games, p["joncjy"], TODAY)[0]["ref"]
    bookings.leave_jam(games, p["joncjy"], theirs, TODAY)
    assert jam_seats(games, jam(games)["id"]) == 1
    assert bookings.my_jam(games, p["heidily"], TODAY)


def test_the_booker_cancelling_takes_the_people_they_brought(games):
    p = ids(games)
    ref = bookings.book_jam(games, p["heidily"], jam(games)["id"], "bass",
                            [player("joncjy", "drums")], TODAY)["ref"]
    # Somebody unrelated is in the room too, and must be left alone.
    bookings.book_jam(games, p["zhnlun"], jam(games)["id"], "keys", [], TODAY)
    out = bookings.cancel_jam(games, p["heidily"], ref, TODAY)
    assert out["cancelled"] and out["seats"] == 2
    assert jam_seats(games, jam(games)["id"]) == 1
    assert bookings.my_jam(games, p["zhnlun"], TODAY)


def test_someone_added_cannot_cancel_the_group(games):
    p = ids(games)
    bookings.book_jam(games, p["heidily"], jam(games)["id"], "bass",
                      [player("joncjy", "drums")], TODAY)
    theirs = bookings.my_jam(games, p["joncjy"], TODAY)[0]["ref"]
    with pytest.raises(ClaimError) as e:
        bookings.cancel_jam(games, p["joncjy"], theirs, TODAY)
    assert e.value.code == "FORBIDDEN"
    assert jam_seats(games, jam(games)["id"]) == 2


def test_two_people_racing_for_the_last_drum_kit(games):
    p, s = ids(games), jam(games)
    barrier = threading.Barrier(2)
    results = []

    def run(h):
        c = db.connect()
        try:
            barrier.wait()
            bookings.book_jam(c, p[h], s["id"], "drums", [], TODAY)
            results.append("ok")
        except ClaimError as exc:
            results.append(exc.code)
        finally:
            c.close()

    threads = [threading.Thread(target=run, args=(h,)) for h in ("heidily", "joncjy")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("ok") == 1, results
    assert jam_seats(games, s["id"]) == 1


def test_one_jam_slot_each_by_default(games):
    p = ids(games)
    bookings.book_jam(games, p["heidily"], jam(games, 0)["id"], "bass", [], TODAY)
    with pytest.raises(ClaimError) as e:
        bookings.book_jam(games, p["heidily"], jam(games, 3)["id"], "bass", [], TODAY)
    assert e.value.code == "LIMIT_REACHED"


def test_a_friend_who_already_has_a_slot_cannot_be_added(games):
    p = ids(games)
    bookings.book_jam(games, p["joncjy"], jam(games, 0)["id"], "bass", [], TODAY)
    with pytest.raises(ClaimError) as e:
        bookings.book_jam(games, p["heidily"], jam(games, 3)["id"], "bass",
                          [player("joncjy", "drums")], TODAY)
    assert e.value.code == "LIMIT_REACHED"
    assert "joncjy" in e.value.extra["handles"]
    assert jam_seats(games, jam(games, 3)["id"]) == 0


def test_cancelling_a_jam_slot_frees_the_instrument(games):
    p = ids(games)
    ref = bookings.book_jam(games, p["heidily"], jam(games)["id"], "bass", [], TODAY)["ref"]
    assert bookings.cancel_jam(games, p["heidily"], ref, TODAY)["cancelled"] is True
    assert bookings.book_jam(games, p["joncjy"], jam(games)["id"], "bass", [], TODAY)
    with pytest.raises(ClaimError) as e:
        bookings.cancel_jam(games, p["heidily"], ref, TODAY)
    assert e.value.code == "NO_BOOKING"


def test_a_started_jam_slot_cannot_be_booked_or_cancelled(games):
    p, s = ids(games), jam(games)
    ref = bookings.book_jam(games, p["heidily"], s["id"], "bass", [], TODAY)["ref"]
    later = starts(s) + timedelta(minutes=1)
    with pytest.raises(ClaimError) as e:
        bookings.cancel_jam(games, p["heidily"], ref, later)
    assert e.value.code == "SLOT_STARTED"
    with pytest.raises(ClaimError) as e:
        bookings.book_jam(games, p["joncjy"], jam(games, 1)["id"], "bass", [],
                          starts(jam(games, 1)) - timedelta(minutes=2))
    assert e.value.code == "SLOT_CLOSED"


# ---------------------------------------------------------------------------
# No overlaps (§9 r18), counting 5 minutes to walk
# ---------------------------------------------------------------------------

def test_a_jam_slot_cannot_overlap_your_game(games):
    p = ids(games)
    bookings.book(games, p["heidily"], slot(games, 2)["id"], [], TODAY)         # 3:45-4:00 PM
    with pytest.raises(ClaimError) as e:
        bookings.book_jam(games, p["heidily"], jam(games, 1)["id"], "bass", [], TODAY)  # 3:30-4:00 PM
    assert e.value.code == "TIME_CONFLICT"
    with pytest.raises(ClaimError) as e:
        bookings.book_jam(games, p["heidily"], jam(games, 2)["id"], "bass", [], TODAY)  # 4:00-4:30: walk needed
    assert e.value.code == "TIME_CONFLICT"
    assert bookings.book_jam(games, p["heidily"], jam(games, 3)["id"], "bass", [], TODAY)  # 4:30 PM is fine


def test_a_game_cannot_overlap_your_jam_slot_or_a_friends(games):
    p = ids(games)
    bookings.book_jam(games, p["heidily"], jam(games, 1)["id"], "bass", [], TODAY)      # 3:30-4:00 PM, and the 3:45 game
    with pytest.raises(ClaimError) as e:
        bookings.book(games, p["heidily"], slot(games, 2)["id"], [], TODAY)
    assert e.value.code == "TIME_CONFLICT"
    with pytest.raises(ClaimError) as e:
        bookings.book(games, p["joncjy"], slot(games, 2)["id"], ["heidily"], TODAY)
    assert e.value.code == "TIME_CONFLICT" and e.value.extra["handles"] == ["heidily"]
    assert active(games, slot(games, 2)["id"]) == 0


def test_the_jam_room_through_the_api(games, client):
    heidi = tma(sign(2001, "heidily", "Heidi"))
    d = client.get("/api/jam/slots", headers=heidi).get_json()["data"]
    assert len(d["slots"]) == 14 and d["per_person_limit"] == 1
    assert [i["key"] for i in d["instruments"]] == list(config.INSTRUMENT_KEYS)
    assert len(d["slots"][0]["free"]) == 5
    r = client.post("/api/jam/bookings", headers=heidi,
                    json={"slot_id": d["slots"][4]["id"], "instrument": "keys"})
    assert r.status_code == 200, r.get_json()
    me = client.get("/api/me", headers=heidi).get_json()["data"]
    assert me["jam_bookings"][0]["ref"] == r.get_json()["data"]["ref"]
    assert me["jam_bookings"][0]["instrument_label"] == "Keyboard"
    # An instrument nobody named is refused before anything is written.
    bad = client.post("/api/jam/bookings", headers=heidi,
                      json={"slot_id": d["slots"][6]["id"], "instrument": "kazoo"})
    assert bad.status_code == 400 and bad.get_json()["error"]["code"] == "VALIDATION_FAILED"
    assert client.delete(f"/api/jam/bookings/{me['jam_bookings'][0]['ref']}", headers=heidi).status_code == 200
    assert client.get("/api/me", headers=heidi).get_json()["data"]["jam_bookings"] == []


def test_the_app_gets_the_event_facts_from_settings(games, client):
    d = client.get("/api/me", headers=tma(sign(2001, "heidily"))).get_json()["data"]["event"]
    assert d["venue"] == "The Hub @ Hafary Gallery L5" and d["opens"] == "3:00 PM" and d["closes"] == "10:00 PM"
    assert d["address"] == "105 Eunos Ave 3, Singapore 409836"
    assert d["last_game"] == "9:45 PM" and d["entry_fee"].startswith("$12")
    # The pass: one pastry (of four kinds), the first photo strip, vinyl
    # making (22 Sep, STATE.md 132). Places and prices come from Settings too.
    assert [i["key"] for i in d["items"]] == ["pastry", "photo", "vinyl"]
    assert [c["key"] for c in d["items"][0]["choices"]] == ["tart", "brownie", "cookie", "shiopan"]
    assert d["escape_meet"] == "the escape room entrance" and d["jam_room"] == "Heaven 2"
    # Whether Help tells people to go and show their payment (STATE.md 138).
    assert d["payment_required"] is True
    db.set_setting(games, "claim_requires", "none", by="test")
    d2 = client.get("/api/me", headers=tma(sign(2001, "heidily"))).get_json()["data"]["event"]
    assert d2["payment_required"] is False
    assert d["prices"][0]["title"] == "Activities"
    assert {"name": "Mini Tart", "price": "$2.50"} in d["prices"][1]["rows"]


def test_admin_quietly_cancels_a_test_group(games):
    p = ids(games)
    bookings.book(games, p["maxi_muslim"] if "maxi_muslim" in p else p["heidily"],
                  slot(games)["id"], ["bananabelles", "t_shixuan"], TODAY)
    owner = "maxi_muslim" if "maxi_muslim" in p else "heidily"
    gone = bookings.cancel_group_as_admin(games, owner, "manage.py", TODAY)
    assert sorted(gone) == sorted(["@" + owner, "@bananabelles", "@t_shixuan"])
    assert active(games, slot(games)["id"]) == 0
    statuses = {r[0]: r[1] for r in games.execute("SELECT kind, status FROM notifications")}
    assert statuses == {"friend_added": "withdrawn", "escape_booked": "withdrawn"}