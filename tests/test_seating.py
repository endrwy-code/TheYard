"""The Seating board: who is in which slot, and moving them between slots
(24 Sep). The rule under test throughout is that a move never takes a seat
off anybody else — a slot with no room is refused, never emptied."""

from datetime import datetime, timedelta, timezone

import pytest

import config
import db
from services import admin, bookings
from test_claims_concurrent import (  # noqa: F401 - fixtures are used by name
    Console, err, roster, secrets_and_limits,
)

BEFORE = datetime(2026, 9, 17, 4, 0, tzinfo=timezone.utc)


@pytest.fixture()
def world(roster):
    bookings.generate_slots(roster)
    return roster


def pid(conn, handle):
    return conn.execute("SELECT id FROM attendees WHERE handle=?", (handle,)).fetchone()[0]


def data(r):
    body = r.get_json()
    assert body["ok"], body
    return body["data"]


def games(conn, n=2):
    return conn.execute("SELECT * FROM slots WHERE room='escape' ORDER BY starts_at "
                        "LIMIT ?", (n,)).fetchall()


def jams(conn, n=2):
    return conn.execute("SELECT * FROM slots WHERE room='jam' ORDER BY starts_at "
                        "LIMIT ?", (n,)).fetchall()


def in_slot(conn, table, slot_id):
    live = "('booked','checked_in')" if table == "escape_bookings" else "('confirmed')"
    return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE slot_id=? "  # noqa: S608
                        f"AND status IN {live}", (slot_id,)).fetchone()[0]


# ---------------------------------------------------------------------------
# The board
# ---------------------------------------------------------------------------

def test_the_board_names_who_is_in_each_slot(world):
    g1, _ = games(world)
    j1, _ = jams(world)
    bookings.book(world, pid(world, "heidily"), g1["id"], ["bananabelles"], BEFORE)
    bookings.book_jam(world, pid(world, "joncjy"), j1["id"], "drums", [], BEFORE)
    d = data(Console("admin").get("/admin/api/seating"))

    game = next(g for g in d["escape"] if g["id"] == g1["id"])
    assert [p["handle"] for p in game["people"]] == ["heidily", "bananabelles"]
    # A friend was seated by somebody, and the board says by whom — the front
    # desk is about to split a group and should know it is one.
    assert game["people"][0]["booked_by"] is None
    assert game["people"][1]["booked_by"] == "@heidily"
    assert game["booked"] == 2 and game["capacity"] == 12

    slot = next(j for j in d["jam"] if j["id"] == j1["id"])
    assert [(p["handle"], p["instrument"]) for p in slot["people"]] == [("joncjy", "drums")]
    assert [f["key"] for f in slot["free"]] == ["acoustic", "electric", "keys", "bass"]
    assert d["seats_taken"] == 2 and d["jam_seats_taken"] == 1


def test_the_board_is_admin_only(world):
    assert err(Console("mobile", "", "").get("/admin/api/seating"))["code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# Escape moves
# ---------------------------------------------------------------------------

def test_a_game_that_is_over_can_still_be_moved_out_of(world, monkeypatch):
    """The organiser's case. Their 3:05 has been and gone and they never
    turned up; put them in a later one, or in one that is running now.

    The clock is wound past the end of both games first, because that is the
    state the old control could not cope with: a finished game was left off
    the list it offered, so no time you typed was ever found."""
    import app as webapp
    g1, g2 = games(world)
    h = pid(world, "heidily")
    bookings.book(world, h, g1["id"], [], BEFORE)
    late = datetime.fromisoformat(g2["ends_at"]) + timedelta(hours=2)
    monkeypatch.setattr(webapp, "now_utc", lambda: late)
    d = data(Console("admin").post("/admin/api/seating/moves",
                                   {"moves": [{"room": "escape", "attendee_id": h,
                                               "slot_id": g2["id"]}],
                                    "reason": "never turned up"}))
    assert d["moves"][0]["from"] == "3:05 PM" and d["moves"][0]["to"] == "3:25 PM"
    assert bookings.active_booking(world, h)["slot_id"] == g2["id"]
    # And the board still lists a game that is over, with the people in it.
    board = data(Console("admin").get("/admin/api/seating"))
    done = next(g for g in board["escape"] if g["id"] == g2["id"])
    assert done["done"] and [p["handle"] for p in done["people"]] == ["heidily"]


def test_a_full_game_is_refused_and_says_how_full(world):
    g1, g2 = games(world)
    world.execute("UPDATE slots SET capacity=1 WHERE id=?", (g2["id"],))
    h, b = pid(world, "heidily"), pid(world, "bananabelles")
    bookings.book(world, h, g1["id"], [], BEFORE)
    bookings.book(world, b, g2["id"], [], BEFORE)
    e = err(Console("admin").post("/admin/api/seating/moves",
                                  {"moves": [{"room": "escape", "attendee_id": h,
                                              "slot_id": g2["id"]}]}))
    assert e["code"] == "SLOT_FULL"
    assert "would hold 2 people with 1 seat" in e["message"]
    # The point of the refusal: the person already in it is still in it.
    assert bookings.active_booking(world, b)["slot_id"] == g2["id"]
    assert bookings.active_booking(world, h)["slot_id"] == g1["id"]


def test_two_people_in_full_games_can_swap(world):
    """Saved one at a time this is impossible — each game is full until the
    other person leaves it. Saved together it is just a swap."""
    g1, g2 = games(world)
    world.execute("UPDATE slots SET capacity=1 WHERE id IN (?,?)", (g1["id"], g2["id"]))
    h, b = pid(world, "heidily"), pid(world, "bananabelles")
    bookings.book(world, h, g1["id"], [], BEFORE)
    bookings.book(world, b, g2["id"], [], BEFORE)
    d = data(Console("admin").post("/admin/api/seating/moves", {"moves": [
        {"room": "escape", "attendee_id": h, "slot_id": g2["id"]},
        {"room": "escape", "attendee_id": b, "slot_id": g1["id"]},
    ]}))
    assert len(d["moves"]) == 2
    assert bookings.active_booking(world, h)["slot_id"] == g2["id"]
    assert bookings.active_booking(world, b)["slot_id"] == g1["id"]
    assert in_slot(world, "escape_bookings", g1["id"]) == 1


def test_one_bad_move_saves_none_of_them(world):
    g1, g2, g3 = games(world, 3)
    world.execute("UPDATE slots SET is_blocked=1, block_reason='actor ill' WHERE id=?", (g3["id"],))
    h, b = pid(world, "heidily"), pid(world, "bananabelles")
    bookings.book(world, h, g1["id"], [], BEFORE)
    bookings.book(world, b, g1["id"], [], BEFORE)
    e = err(Console("admin").post("/admin/api/seating/moves", {"moves": [
        {"room": "escape", "attendee_id": h, "slot_id": g2["id"]},     # fine on its own
        {"room": "escape", "attendee_id": b, "slot_id": g3["id"]},     # blocked
    ]}))
    assert e["code"] == "SLOT_BLOCKED"
    assert bookings.active_booking(world, h)["slot_id"] == g1["id"]
    assert bookings.active_booking(world, b)["slot_id"] == g1["id"]


def test_moving_someone_twice_on_one_save_is_refused(world):
    g1, g2, g3 = games(world, 3)
    h = pid(world, "heidily")
    bookings.book(world, h, g1["id"], [], BEFORE)
    e = err(Console("admin").post("/admin/api/seating/moves", {"moves": [
        {"room": "escape", "attendee_id": h, "slot_id": g2["id"]},
        {"room": "escape", "attendee_id": h, "slot_id": g3["id"]},
    ]}))
    assert e["code"] == "VALIDATION_FAILED" and "twice" in e["message"]
    assert bookings.active_booking(world, h)["slot_id"] == g1["id"]


def test_a_saved_move_tells_them_and_is_in_the_log(world):
    g1, g2 = games(world)
    h = pid(world, "heidily")
    bookings.book(world, h, g1["id"], [], BEFORE)
    Console("admin").post("/admin/api/seating/moves",
                          {"moves": [{"room": "escape", "attendee_id": h, "slot_id": g2["id"]}],
                           "reason": "asked to come later"})
    assert world.execute("SELECT COUNT(*) FROM notifications WHERE kind='moved'").fetchone()[0] == 1
    what = [r["action"] for r in world.execute("SELECT action FROM audit_log")]
    assert "Escape booking moved" in what and "Seating saved" in what


# ---------------------------------------------------------------------------
# Jam moves
# ---------------------------------------------------------------------------

def test_a_jam_seat_moves_and_keeps_its_instrument(world):
    j1, j2 = jams(world)
    h = pid(world, "heidily")
    bookings.book_jam(world, h, j1["id"], "bass", [], BEFORE)
    d = data(Console("admin").post("/admin/api/seating/moves",
                                   {"moves": [{"room": "jam", "attendee_id": h,
                                               "slot_id": j2["id"]}]}))
    assert d["moves"][0]["instrument"] == "bass"
    mine = bookings.jam_bookings_of(world, h)[0]
    assert mine["slot_id"] == j2["id"] and mine["instrument"] == "bass"
    assert world.execute(
        "SELECT COUNT(*) FROM notifications WHERE kind='jam_moved'").fetchone()[0] == 1


def test_an_instrument_someone_else_has_is_not_taken_off_them(world):
    j1, j2 = jams(world)
    h, b = pid(world, "heidily"), pid(world, "bananabelles")
    bookings.book_jam(world, h, j1["id"], "drums", [], BEFORE)
    bookings.book_jam(world, b, j2["id"], "drums", [], BEFORE)
    e = err(Console("admin").post("/admin/api/seating/moves",
                                  {"moves": [{"room": "jam", "attendee_id": h,
                                              "slot_id": j2["id"]}]}))
    assert e["code"] == "INSTRUMENT_TAKEN"
    assert "Free there: acoustic guitar" in e["message"]
    assert e["free"] == ["acoustic", "electric", "keys", "bass"]
    # Nobody lost a drum kit over it.
    assert bookings.jam_bookings_of(world, b)[0]["instrument"] == "drums"
    assert bookings.jam_bookings_of(world, h)[0]["slot_id"] == j1["id"]


def test_the_move_can_put_them_on_a_different_instrument(world):
    j1, j2 = jams(world)
    h, b = pid(world, "heidily"), pid(world, "bananabelles")
    bookings.book_jam(world, h, j1["id"], "drums", [], BEFORE)
    bookings.book_jam(world, b, j2["id"], "drums", [], BEFORE)
    d = data(Console("admin").post("/admin/api/seating/moves",
                                   {"moves": [{"room": "jam", "attendee_id": h,
                                               "slot_id": j2["id"], "instrument": "keys"}]}))
    assert d["moves"][0]["instrument_label"] == "Keyboard"
    assert bookings.jam_bookings_of(world, h)[0]["instrument"] == "keys"
    assert bookings.jam_bookings_of(world, b)[0]["instrument"] == "drums"


def test_two_drummers_can_swap_slots(world):
    """Both hold the drums, in different slots. Every state in between has
    two drum kits in one room, which the unique index would refuse, so the
    instrument is parked while the rows move."""
    j1, j2 = jams(world)
    h, b = pid(world, "heidily"), pid(world, "bananabelles")
    bookings.book_jam(world, h, j1["id"], "drums", [], BEFORE)
    bookings.book_jam(world, b, j2["id"], "drums", [], BEFORE)
    d = data(Console("admin").post("/admin/api/seating/moves", {"moves": [
        {"room": "jam", "attendee_id": h, "slot_id": j2["id"]},
        {"room": "jam", "attendee_id": b, "slot_id": j1["id"]},
    ]}))
    assert len(d["moves"]) == 2
    assert bookings.jam_bookings_of(world, h)[0]["slot_id"] == j2["id"]
    assert bookings.jam_bookings_of(world, b)[0]["slot_id"] == j1["id"]
    assert all(r["instrument"] == "drums" for r in
               world.execute("SELECT instrument FROM jam_bookings WHERE status='confirmed'"))


def test_two_arrivals_cannot_bring_the_same_instrument(world):
    j1, j2, j3 = jams(world, 3)
    h, b = pid(world, "heidily"), pid(world, "bananabelles")
    bookings.book_jam(world, h, j1["id"], "keys", [], BEFORE)
    bookings.book_jam(world, b, j2["id"], "keys", [], BEFORE)
    e = err(Console("admin").post("/admin/api/seating/moves", {"moves": [
        {"room": "jam", "attendee_id": h, "slot_id": j3["id"]},
        {"room": "jam", "attendee_id": b, "slot_id": j3["id"]},
    ]}))
    assert e["code"] == "INSTRUMENT_TAKEN" and "Nothing was saved" in e["message"]
    assert bookings.jam_bookings_of(world, h)[0]["slot_id"] == j1["id"]
    assert bookings.jam_bookings_of(world, b)[0]["slot_id"] == j2["id"]


def test_a_jam_slot_over_someones_game_is_refused(world):
    """§9 r18 still holds when the front desk does the moving, walking time
    and all — the person cannot be in two rooms at once."""
    h = pid(world, "heidily")
    g = games(world, 1)[0]
    bookings.book(world, h, g["id"], [], BEFORE)
    clash = world.execute(
        "SELECT * FROM slots WHERE room='jam' AND starts_at < ? AND ends_at > ? LIMIT 1",
        (g["ends_at"], g["starts_at"])).fetchone()
    free = world.execute(
        "SELECT * FROM slots WHERE room='jam' AND starts_at > ? ORDER BY starts_at LIMIT 1",
        (g["ends_at"],)).fetchone()
    bookings.book_jam(world, h, free["id"], "bass", [], BEFORE)
    e = err(Console("admin").post("/admin/api/seating/moves",
                                  {"moves": [{"room": "jam", "attendee_id": h,
                                              "slot_id": clash["id"]}]}))
    assert e["code"] == "TIME_CONFLICT"
    assert bookings.jam_bookings_of(world, h)[0]["slot_id"] == free["id"]


def test_which_jam_slot_is_named_when_somebody_holds_two(world):
    j1, j2, j3 = jams(world, 3)
    h = pid(world, "heidily")
    world.execute("UPDATE settings SET value='2' WHERE key='jam_per_person'")
    bookings.book_jam(world, h, j1["id"], "bass", [], BEFORE)
    second = bookings.book_jam(world, h, j2["id"], "keys", [], BEFORE)
    a = Console("admin")
    assert err(a.post("/admin/api/seating/moves",
                      {"moves": [{"room": "jam", "attendee_id": h,
                                  "slot_id": j3["id"]}]}))["code"] == "VALIDATION_FAILED"
    data(a.post("/admin/api/seating/moves",
                {"moves": [{"room": "jam", "attendee_id": h, "slot_id": j3["id"],
                            "ref": second["ref"]}]}))
    held = {r["ref_code"]: r["slot_id"] for r in bookings.jam_bookings_of(world, h)}
    assert held[second["ref"]] == j3["id"]


# ---------------------------------------------------------------------------
# The single-move endpoints the board's twin controls use
# ---------------------------------------------------------------------------

def test_one_escape_move_on_its_own_still_works(world):
    g1, g2 = games(world)
    h = pid(world, "heidily")
    bookings.book(world, h, g1["id"], [], BEFORE)
    d = data(Console("admin").post("/admin/api/escape/move",
                                   {"attendee_id": h, "slot_id": g2["id"], "reason": "late"}))
    assert d["moved_to"].startswith("2026-09-24T15:25")


def test_one_jam_move_on_its_own_still_works(world):
    j1, j2 = jams(world)
    h = pid(world, "heidily")
    bookings.book_jam(world, h, j1["id"], "acoustic", [], BEFORE)
    d = data(Console("admin").post("/admin/api/jam/move",
                                   {"attendee_id": h, "slot_id": j2["id"], "reason": "asked"}))
    assert d["instrument"] == "acoustic"
    assert bookings.jam_bookings_of(world, h)[0]["slot_id"] == j2["id"]


def test_a_seat_with_no_instrument_on_it_has_to_be_given_one(world):
    """Jam seats booked before 19 Sep have no instrument. A move names one
    rather than carrying the blank into a room that seats by instrument."""
    j1, j2 = jams(world)
    h = pid(world, "heidily")
    bookings.book_jam(world, h, j1["id"], "bass", [], BEFORE)
    world.execute("UPDATE jam_bookings SET instrument=NULL WHERE attendee_id=?", (h,))
    a = Console("admin")
    assert err(a.post("/admin/api/jam/move",
                      {"attendee_id": h, "slot_id": j2["id"]}))["code"] == "VALIDATION_FAILED"
    d = data(a.post("/admin/api/jam/move",
                    {"attendee_id": h, "slot_id": j2["id"], "instrument": "keys"}))
    assert d["instrument"] == "keys"


def test_nothing_to_save_is_refused(world):
    a = Console("admin")
    assert err(a.post("/admin/api/seating/moves", {"moves": []}))["code"] == "VALIDATION_FAILED"
    assert err(a.post("/admin/api/seating/moves",
                      {"moves": [{"room": "polo", "attendee_id": 1, "slot_id": 1}]}
                      ))["code"] == "VALIDATION_FAILED"
    too_many = [{"room": "escape", "attendee_id": 1, "slot_id": 1}] * (admin.MOVE_LIMIT + 1)
    assert err(a.post("/admin/api/seating/moves",
                      {"moves": too_many}))["code"] == "VALIDATION_FAILED"


def test_the_board_leaves_out_retired_times(world):
    """A time taken out of the schedule that somebody once booked is retired,
    not deleted. Schedules hides those and so does this, or the front desk
    would be dragging people into a game that is not running."""
    g1 = games(world, 1)[0]
    world.execute("UPDATE slots SET is_blocked=1, block_reason=? WHERE id=?",
                  (bookings.RETIRED, g1["id"]))
    d = data(Console("admin").get("/admin/api/seating"))
    assert g1["id"] not in [g["id"] for g in d["escape"]]
    assert config.INSTRUMENT_KEYS == ("acoustic", "electric", "keys", "drums", "bass")


# ---------------------------------------------------------------------------
# Telling the person
# ---------------------------------------------------------------------------

def test_a_move_into_a_game_that_is_on_now_still_reaches_them(world, monkeypatch):
    """The message expires at the **end** of the game they are moved into, not
    its start. Expiring at the start is right for a reminder and wrong here:
    the commonest move of the night is into the game running now, and an
    expiry on the start time had `deliver` drop that message as stale before
    it ever went — leaving the one person who needed telling untold."""
    import app as webapp
    from services import notify
    g1, g2 = games(world)
    h = pid(world, "heidily")
    bookings.book(world, h, g1["id"], [], BEFORE)
    mid = datetime.fromisoformat(g2["starts_at"]) + timedelta(minutes=2)   # it has begun
    monkeypatch.setattr(webapp, "now_utc", lambda: mid)
    d = data(Console("admin").post("/admin/api/seating/moves",
                                   {"moves": [{"room": "escape", "attendee_id": h,
                                               "slot_id": g2["id"]}]}))
    assert d["moves"][0]["told"] is True
    world.execute("UPDATE attendees SET tg_user_id=99, can_message=1 WHERE id=?", (h,))
    db.set_setting(world, "notify_mode", "on", by="test")
    sent = []
    counts = notify.deliver(world, lambda chat, text, go: sent.append(text), now=mid)
    assert counts.get("expired") is None
    assert [t for t in sent if "your game has moved" in t]


def test_a_move_into_a_game_that_is_over_says_nobody_was_told(world, monkeypatch):
    import app as webapp
    g1, g2 = games(world)
    h = pid(world, "heidily")
    bookings.book(world, h, g1["id"], [], BEFORE)
    late = datetime.fromisoformat(g2["ends_at"]) + timedelta(hours=1)
    monkeypatch.setattr(webapp, "now_utc", lambda: late)
    d = data(Console("admin").post("/admin/api/seating/moves",
                                   {"moves": [{"room": "escape", "attendee_id": h,
                                               "slot_id": g2["id"]}]}))
    # The move is done either way — it is the message that has nothing to say.
    assert d["moves"][0]["told"] is False
    assert bookings.active_booking(world, h)["slot_id"] == g2["id"]
