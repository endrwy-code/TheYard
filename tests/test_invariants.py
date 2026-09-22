"""Invariants that survive ordinary use — the things that go wrong quietly.

These are not "does the button work" tests. Each one is a rule the rest of the
system assumes is always true, checked after the kind of ordinary sequence
that would break it: someone leaves a group, an admin changes their mind about
seat numbers, an old row from a previous version of the item list is still in
the database.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

import pytest

import config
import db
from services import admin as console
from services import bookings, claims, game, people
from test_claims_concurrent import (  # noqa: F401 - fixtures are used by name
    Console, err, roster, secrets_and_limits,
)

NOW = datetime(2026, 9, 17, 4, 0, tzinfo=timezone.utc)
GM = {"role": "gm", "name": "Ryan", "station": "GM"}


@pytest.fixture()
def world(roster):
    bookings.generate_slots(roster)
    return roster


def pid(conn, handle):
    return conn.execute("SELECT id FROM attendees WHERE handle=?", (handle,)).fetchone()[0]


def first_game(conn):
    return conn.execute("SELECT * FROM slots WHERE room='escape' ORDER BY starts_at").fetchone()


# ---------------------------------------------------------------------------
# A schedule change never leaves people stranded silently (§9 r35, decision 77)
# ---------------------------------------------------------------------------

def test_lowering_the_seat_count_names_the_games_that_are_now_over_full(world):
    """Nothing throws a booked person out, so the game just quietly holds more
    people than it seats. The admin has to be told, by name of game."""
    slot = first_game(world)
    bookings.book(world, pid(world, "bananabelles"), slot["id"],
                  ["heidily", "t_shixuan", "bingkiat"], NOW)
    out = console.save_settings(world, {"capacity": 2}, "Max", NOW)
    over = out["schedule"]["escape"]["over"]
    assert len(over) == 1
    assert over[0]["booked"] == 4 and over[0]["capacity"] == 2
    assert any("4 are booked" in w and "Move 2" in w for w in out["warnings"]), out["warnings"]


def test_raising_the_seat_count_warns_about_nothing(world):
    slot = first_game(world)
    bookings.book(world, pid(world, "bananabelles"), slot["id"], ["heidily"], NOW)
    out = console.save_settings(world, {"capacity": 20}, "Max", NOW)
    assert out["schedule"]["escape"]["over"] == []
    assert "warnings" not in out


def test_an_over_full_game_still_refuses_new_bookings(world):
    """The warning is for the admin. The rule itself must still hold."""
    slot = first_game(world)
    bookings.book(world, pid(world, "bananabelles"), slot["id"], ["heidily", "t_shixuan"], NOW)
    console.save_settings(world, {"capacity": 2}, "Max", NOW)
    with pytest.raises(claims.ClaimError) as e:
        bookings.book(world, pid(world, "zhnlun"), slot["id"], [], NOW)
    assert e.value.code in ("SLOT_FULL", "NOT_ENOUGH_SEATS")


# ---------------------------------------------------------------------------
# The low-stock threshold is the organiser's to change (§9 r27)
# ---------------------------------------------------------------------------

def hand_out(conn, handles, item="pastry"):
    """One hand-over each. The once-only index means one per person per item."""
    for h in handles:
        conn.execute("INSERT INTO claims (attendee_id, item, claimed_at, staff_name, station) "
                     "VALUES (?, ?, ?, 'Wei', 'Booth 1')", (pid(conn, h), item, db.utcnow()))


def test_low_stock_threshold_is_a_settings_row_not_a_constant(world):
    """The organiser asked whether they could change this on the Settings
    screen. Before 18 Sep the answer was no — it was a constant in config.py."""
    assert "low_stock_at" in console.settings_view(world)["values"]
    assert db.get_setting(world, "low_stock_at", None) == config.LOW_STOCK_AT


def test_changing_the_threshold_changes_what_the_booth_calls_low(world):
    db.set_setting(world, "pastry_stock", 10, "test")
    hand_out(world, ["heidily", "t_shixuan", "bingkiat"])        # 7 left

    assert claims.stock_for(world, "pastry")["left"] == 7
    assert claims.stock_for(world, "pastry")["low"] is False      # default is 5

    console.save_settings(world, {"low_stock_at": 8}, "Max", NOW)
    assert claims.stock_for(world, "pastry")["low"] is True

    console.save_settings(world, {"low_stock_at": 2}, "Max", NOW)
    assert claims.stock_for(world, "pastry")["low"] is False


def test_an_untracked_item_is_never_low(world):
    """0 stock means "not counted", not "none left"."""
    db.set_setting(world, "photo_stock", 0, "test")
    console.save_settings(world, {"low_stock_at": 999}, "Max", NOW)
    assert claims.stock_for(world, "photo") is None


# ---------------------------------------------------------------------------
# Old data from a previous version of the item list (§9 r24)
# ---------------------------------------------------------------------------

def test_a_claim_under_a_retired_item_key_does_not_break_the_person_page(world):
    """The included items were matcha and panini before 18 Sep. Rows under
    those keys are still in the organiser's database from testing."""
    who = pid(world, "heidily")
    world.execute("INSERT INTO claims (attendee_id, item, claimed_at, staff_name, station) "
                  "VALUES (?, 'matcha', ?, 'Old Staff', 'Booth 1')", (who, db.utcnow()))
    view = people.person(world, who, "admin")
    assert set(view["claims"]) == set(config.ITEM_KEYS)
    assert all(not c["claimed"] for c in view["claims"].values())


def test_a_retired_item_key_does_not_block_a_current_hand_over(world):
    """A stale 'matcha' row must not read as "already had their pastry"."""
    who = pid(world, "heidily")
    world.execute("UPDATE attendees SET payment_status='verified' WHERE id=?", (who,))
    world.execute("INSERT INTO claims (attendee_id, item, claimed_at, staff_name, station) "
                  "VALUES (?, 'matcha', ?, 'Old Staff', 'Booth 1')", (who, db.utcnow()))
    code = world.execute("SELECT pass_code FROM attendees WHERE id=?", (who,)).fetchone()[0]
    claims.claim(world, item="pastry", code=code,
                 actor={"role": "staff", "name": "Wei", "station": "Booth 1"})
    # The pastry is now recorded once, and the stale row is untouched beside it.
    handed = [r["item"] for r in world.execute(
        "SELECT item FROM claims WHERE attendee_id=? AND voided_at IS NULL", (who,))]
    assert sorted(handed) == ["matcha", "pastry"]
    assert claims.active_claim(world, who, "pastry") is not None


# ---------------------------------------------------------------------------
# One person, one game (§9 r15)
# ---------------------------------------------------------------------------

def test_booking_a_second_game_never_leaves_two_live_bookings(world):
    slot = first_game(world)
    other = world.execute(
        "SELECT * FROM slots WHERE room='escape' ORDER BY starts_at LIMIT 1 OFFSET 4").fetchone()
    me = pid(world, "heidily")
    bookings.book(world, me, slot["id"], [], NOW)
    try:
        bookings.book(world, me, other["id"], [], NOW)
    except claims.ClaimError:
        pass
    held = world.execute(
        "SELECT COUNT(*) c FROM escape_bookings WHERE attendee_id=? "
        "AND status IN ('booked','checked_in')", (me,)).fetchone()["c"]
    assert held == 1


# ---------------------------------------------------------------------------
# What the jam room becoming a group booking dragged along with it (18 Sep)
# ---------------------------------------------------------------------------

def jam_slot(conn, n=0):
    return conn.execute("SELECT * FROM slots WHERE room='jam' ORDER BY starts_at "
                        "LIMIT 1 OFFSET ?", (n,)).fetchone()


def queued_kinds(conn):
    """Only messages still due to go out. `notify.withdraw` marks a row
    'withdrawn' rather than deleting it, so the row is still there."""
    return [r["kind"] for r in conn.execute(
        "SELECT kind FROM notifications WHERE status='queued' ORDER BY id")]


def mark_sent(conn, kind):
    conn.execute("UPDATE notifications SET status='sent', sent_at=? WHERE kind=?",
                 (db.utcnow(), kind))


def test_the_booker_gets_a_receipt_naming_the_group(world):
    """The old message said only "booked". With a group it has to say who,
    because that message is the one they can find again later."""
    bookings.book_jam(world, pid(world, "bananabelles"), jam_slot(world)["id"], "bass", [{"handle": "heidily", "instrument": "electric"}, {"handle": "t_shixuan", "instrument": "keys"}], NOW)
    row = world.execute("SELECT * FROM notifications WHERE kind='jam_booked'").fetchone()
    assert "@heidily" in row["text"] and "@t_shixuan" in row["text"]
    assert "line-up:" in row["text"]
    assert "Heaven 2" in row["text"]                   # the room's own name


def test_everyone_added_is_told_and_told_how_to_leave(world):
    bookings.book_jam(world, pid(world, "bananabelles"), jam_slot(world)["id"], "bass", [{"handle": "heidily", "instrument": "electric"}], NOW)
    row = world.execute("SELECT * FROM notifications WHERE kind='jam_friend_added'").fetchone()
    assert row is not None
    assert "jamming studio" in row["text"].lower()
    assert "leave" in row["text"].lower()


def test_removing_someone_who_was_never_told_sends_nothing(world):
    """The message is still queued, so withdraw it rather than following
    "you're booked" with "actually you're not"."""
    ref = bookings.book_jam(world, pid(world, "bananabelles"), jam_slot(world)["id"], "bass", [{"handle": "heidily", "instrument": "electric"}], NOW)["ref"]
    bookings.remove_jam_friend(world, pid(world, "bananabelles"), ref, "heidily", NOW)
    assert "jam_friend_added" not in queued_kinds(world)
    assert "jam_removed" not in queued_kinds(world)


def test_removing_someone_already_told_does_send_one(world):
    ref = bookings.book_jam(world, pid(world, "bananabelles"), jam_slot(world)["id"], "bass", [{"handle": "heidily", "instrument": "electric"}], NOW)["ref"]
    mark_sent(world, "jam_friend_added")
    bookings.remove_jam_friend(world, pid(world, "bananabelles"), ref, "heidily", NOW)
    assert "jam_removed" in queued_kinds(world)


def test_the_booker_hears_when_somebody_leaves(world):
    bookings.book_jam(world, pid(world, "bananabelles"), jam_slot(world)["id"], "bass", [{"handle": "heidily", "instrument": "electric"}], NOW)
    theirs = bookings.my_jam(world, pid(world, "heidily"), NOW)[0]["ref"]
    bookings.leave_jam(world, pid(world, "heidily"), theirs, NOW)
    row = world.execute("SELECT * FROM notifications WHERE kind='jam_friend_left'").fetchone()
    assert row is not None and row["attendee_id"] == pid(world, "bananabelles")


def test_cancelling_tells_the_group_it_is_off_not_that_they_were_removed(world):
    """Two different things happened to them, so they read differently."""
    ref = bookings.book_jam(world, pid(world, "bananabelles"), jam_slot(world)["id"], "bass", [{"handle": "heidily", "instrument": "electric"}], NOW)["ref"]
    mark_sent(world, "jam_friend_added")
    bookings.cancel_jam(world, pid(world, "bananabelles"), ref, NOW)
    row = world.execute("SELECT * FROM notifications WHERE kind='jam_cancelled'").fetchone()
    assert row is not None and "cancelled" in row["text"].lower()
    assert "jam_removed" not in queued_kinds(world)


def test_a_jam_group_cannot_clash_with_any_members_game(world):
    """The clash check has to run for every friend, not just the booker. A
    friend's own escape game is something only the server knows about."""
    slot = first_game(world)
    bookings.book(world, pid(world, "heidily"), slot["id"], [], NOW)   # 3:05-3:20 PM
    with pytest.raises(claims.ClaimError) as e:
        bookings.book_jam(world, pid(world, "bananabelles"), jam_slot(world, 0)["id"], "bass", [{"handle": "heidily", "instrument": "electric"}], NOW)                            # 3:00-3:30 PM
    assert e.value.code == "TIME_CONFLICT"
    assert "heidily" in e.value.extra["handles"]


def test_the_admin_cleanup_command_clears_jam_seats_too(world):
    """`manage.py cancel-group` after a test. Clearing only the escape game
    would leave half the test behind for somebody to find on the night."""
    owner = pid(world, "bananabelles")
    bookings.book(world, owner, first_game(world)["id"], ["heidily"], NOW)
    bookings.book_jam(world, owner, jam_slot(world, 4)["id"], "bass", [{"handle": "t_shixuan", "instrument": "electric"}], NOW)
    out = bookings.cancel_group_as_admin(world, "bananabelles", "Max", NOW)
    assert any("(jam)" in x for x in out)
    assert world.execute("SELECT COUNT(*) c FROM jam_bookings WHERE status='confirmed'"
                         ).fetchone()["c"] == 0
    assert world.execute("SELECT COUNT(*) c FROM escape_bookings WHERE status='booked'"
                         ).fetchone()["c"] == 0


def test_the_jam_export_says_who_booked_the_slot(world):
    """Without it a slot reads as several unrelated people."""
    from services import export
    bookings.book_jam(world, pid(world, "bananabelles"), jam_slot(world)["id"], "bass", [{"handle": "heidily", "instrument": "electric"}], NOW)
    body, name, mime = export.build(world, "bookings")
    import io, openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(body))
    sheet = wb["Jamming studio"]
    header = [c.value for c in sheet[1]]
    assert "Booked by" in header
    col = header.index("Booked by")
    owners = {sheet.cell(row=r, column=col + 1).value for r in range(2, sheet.max_row + 1)}
    assert owners == {"@bananabelles"}


def test_the_schedules_screen_shows_how_full_a_jam_slot_is(world):
    bookings.book_jam(world, pid(world, "bananabelles"), jam_slot(world)["id"], "bass", [{"handle": "heidily", "instrument": "electric"}, {"handle": "t_shixuan", "instrument": "keys"}], NOW)
    board = bookings.admin_board(world, NOW)
    row = next(j for j in board["jam"] if j["booked"])
    assert row["booked"] == 3 and row["capacity"] == len(config.INSTRUMENTS)
    assert row["who"] == "@bananabelles"
    assert set(row["party"]) == {"@bananabelles", "@heidily", "@t_shixuan"}
    assert board["jam_seats_taken"] == 3


# ---------------------------------------------------------------------------
# What the 19 Sep round of changes has to keep true
# ---------------------------------------------------------------------------

def test_the_pass_covers_a_pastry_the_photo_strip_and_vinyl_making(world):
    """The canned drink left the pass at the organiser's instruction (19 Sep);
    vinyl making joined it on 22 Sep (STATE.md 132). The pastry is still one
    item, whichever of its four kinds is taken."""
    assert list(config.ITEM_KEYS) == ["pastry", "photo", "vinyl"]
    who = pid(world, "heidily")
    assert set(people.person(world, who, "admin")["claims"]) == {"pastry", "photo", "vinyl"}


def test_the_pastry_is_one_claim_whichever_kind(world):
    """Four kinds, one pastry: a second one of a different kind is still a
    second pastry. The kind is recorded, and a made-up kind is refused
    before anything is written."""
    world.execute("UPDATE attendees SET payment_status='verified' WHERE handle='heidily'")
    who = pid(world, "heidily")
    actor = {"role": "mobile", "name": "Wei", "station": "Booth 1"}
    with pytest.raises(claims.ClaimError) as e:
        claims.claim(world, item="pastry", actor=actor, attendee_id=who, variant="croissant")
    assert e.value.code == "VALIDATION_FAILED"
    got = claims.claim(world, item="pastry", actor=actor, attendee_id=who, variant="shiopan")
    assert got["variant_label"] == "Shiopan"
    with pytest.raises(claims.ClaimError) as e:
        claims.claim(world, item="pastry", actor=actor, attendee_id=who, variant="tart")
    assert e.value.code == "ALREADY_CLAIMED"
    assert claims.claims_for(world, who)["pastry"]["variant_label"] == "Shiopan"
    # A kind only means something for an item that has kinds.
    with pytest.raises(claims.ClaimError) as e:
        claims.claim(world, item="photo", actor=actor, attendee_id=who, variant="tart")
    assert e.value.code == "VALIDATION_FAILED"


def test_the_price_list_reads_the_organisers_own_format(world):
    """The list is typed on the Settings screen the way the organiser wrote
    it on 22 Sep: bullets, a missing colon, a heading with nothing under it.
    Saving must keep it as lines, or it arrives as one long paragraph."""
    from services import admin, prices
    raw = "Pastries:\n• Mini Tarts: $2.50\n• Mini Cookies $2.5\n\nIce Cream Waffle:\nUji Matcha: $6\nSoon:\n"
    admin.save_settings(world, {"price_list": raw}, "Max", datetime.now(timezone.utc))
    kept = db.get_setting(world, "price_list")
    assert kept.splitlines()[:2] == ["Pastries:", "• Mini Tarts: $2.50"]
    assert prices.parse(kept) == [
        {"title": "Pastries", "rows": [{"name": "Mini Tarts", "price": "$2.50"},
                                       {"name": "Mini Cookies", "price": "$2.5"}]},
        {"title": "Ice Cream Waffle", "rows": [{"name": "Uji Matcha", "price": "$6"}]},
    ]
    # The starting list parses into the six groups the organiser sent.
    assert [s["title"] for s in prices.parse(config.PRICE_LIST)] == [
        "Activities", "Pastries", "Shiopan and Panini", "Ice Cream Waffle", "Matcha and Hojicha", "Canned Drinks"]


def test_a_drink_can_no_longer_be_claimed_against_a_pass(world):
    world.execute("UPDATE attendees SET payment_status='verified' WHERE handle='heidily'")
    code = world.execute("SELECT pass_code FROM attendees WHERE handle='heidily'").fetchone()[0]
    with pytest.raises(claims.ClaimError):
        claims.claim(world, item="drink", code=code,
                     actor={"role": "staff", "name": "Wei", "station": "Booth 1"})


def test_the_five_instruments_are_offered_and_nothing_else(world):
    board = bookings.jam_board(world, pid(world, "heidily"), NOW)
    assert [i["key"] for i in board["instruments"]] == list(config.INSTRUMENT_KEYS)
    assert len(board["instruments"]) == 5
    assert board["capacity"] == 5
    assert board["slots"][0]["free"] == list(config.INSTRUMENT_KEYS)


def test_the_board_says_which_instruments_are_left(world):
    """The Mini App draws `free` directly, so it has to be the truth."""
    slot = jam_slot(world)
    bookings.book_jam(world, pid(world, "bananabelles"), slot["id"], "drums", [], NOW)
    board = bookings.jam_board(world, pid(world, "heidily"), NOW)
    row = next(s for s in board["slots"] if s["id"] == slot["id"])
    assert "drums" not in row["free"] and len(row["free"]) == 4
    assert row["status"] == "open"          # not "taken" — others may still join
    mine = bookings.jam_board(world, pid(world, "bananabelles"), NOW)
    assert next(s for s in mine["slots"] if s["id"] == slot["id"])["mine_instrument"] == "drums"


def test_my_jam_shows_the_whole_room_not_just_my_group(world):
    """Anyone can join a slot, so "who else is in there, and on what" is the
    thing somebody wants before they turn up."""
    slot = jam_slot(world)
    bookings.book_jam(world, pid(world, "bananabelles"), slot["id"], "bass", [], NOW)
    bookings.book_jam(world, pid(world, "heidily"), slot["id"], "keys", [], NOW)
    mine = bookings.my_jam(world, pid(world, "heidily"), NOW)[0]
    assert {g["handle"]: g["instrument"] for g in mine["line_up"]} == {
        "bananabelles": "bass", "heidily": "keys"}
    # Somebody else's seat is not mine to remove.
    assert all(not g["mine_to_remove"] for g in mine["line_up"])
    assert {f["key"] for f in mine["free"]} == {"acoustic", "electric", "drums"}


def test_every_bot_message_is_structured_and_escaped(world):
    """Headed, with labelled lines, and HTML-safe: a name with an ampersand
    in it must not break the whole message."""
    from services import notify
    samples = [
        notify.text_booked("2026-09-24T12:10:00+00:00", "ESC-1", ["@a"]),
        notify.text_jam_booked("2026-09-24T12:00:00+00:00", "2026-09-24T12:30:00+00:00",
                               "JAM-1", [("a", "bass")]),
        notify.text_jam_friend_added("@b", "2026-09-24T12:00:00+00:00",
                                     "2026-09-24T12:30:00+00:00", "drums"),
        notify.text_reminder("2026-09-24T12:10:00+00:00", 10),
        notify.text_moved("2026-09-24T12:10:00+00:00", "2026-09-24T12:30:00+00:00"),
    ]
    for text in samples:
        assert text.startswith("<b>"), text[:40]
        assert "\n\n" in text                       # a heading, then a block
        assert text.count("<b>") == text.count("</b>")
        # The relaxed voice (22 Sep, STATE.md 132): no shouted headings, no
        # "free with entry".
        heading = text.split("</b>")[0]
        assert heading == heading.lower() or "The " in heading, heading
        assert "free with entry" not in text.lower()
    # A hostile name is escaped, not passed through.
    out = notify.text_friend_removed("<b>Max & Co</b>", "2026-09-24T12:10:00+00:00")
    assert "&lt;b&gt;Max &amp; Co" in out
    assert out.count("<b>") == 1                    # only the heading's own tag


# ---------------------------------------------------------------------------
# The Mini App's motion rule — DESIGN.md §7, STATE.md decision 113.
#
# This is not a database invariant, but it belongs with them. It is a rule the
# app was found to have broken three separate times, each time shipping a page
# that went blank between screens, and no other check here can catch it:
# pytest never runs the page's JavaScript, and render_views.mjs only builds
# markup. It is, however, perfectly checkable as text.
#
# The rule: nothing that holds content may start at opacity:0. A screen is
# rebuilt with innerHTML, so its animation cannot begin until the browser has
# parsed and laid the new markup out. Every frame before that is painted at
# whatever the animation's `from` says — and if that is opacity:0, those
# frames are a blank page. Moving with transform has no such failure mode: the
# element is fully opaque throughout, just offset.
# ---------------------------------------------------------------------------

PAGE = Path(__file__).resolve().parent.parent / "templates" / "index.html"

# The only things allowed to fade, because each one is an overlay that
# genuinely arrives and leaves, or a pseudo-element that holds no content.
# Adding to this list is a deliberate act; that is the point of it.
MAY_FADE = ("#toast", "#stamp", ".phone-open::after")


def _page_css():
    text = PAGE.read_text(encoding="utf-8")
    m = re.search(r"<style>(.*?)</style>", text, re.S)
    assert m, "the Mini App has no <style> block"
    return m.group(1)


def _block_at(css, start):
    """The {...} beginning at `start`, counting nested braces."""
    depth = 0
    for i in range(start, len(css)):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[start:i + 1]
    raise AssertionError("unbalanced braces in the Mini App's CSS")


def _keyframes(css):
    return {m.group(1): _block_at(css, m.end())
            for m in re.finditer(r"@keyframes\s+([A-Za-z0-9_-]+)\s*(?=\{)", css)}


def _rules(css):
    """(selector, body) for each ordinary rule. Good enough for a guard."""
    for m in re.finditer(r"(?:^|\n)([^{}\n]+)\{([^{}]*)\}", css):
        selector = m.group(1).strip()
        if selector.startswith("@") or selector.endswith("*/"):
            continue
        yield selector, m.group(2)


def test_screen_transition_moves_but_never_fades():
    """A transition between screens may slide. It may not fade."""
    css = _page_css()
    frames = _keyframes(css)
    used = [(sel, m.group(1))
            for sel, body in _rules(css) if ".scroll.fwd" in sel or ".scroll.back" in sel
            for m in re.finditer(r"animation:\s*([A-Za-z0-9_-]+)", body)]
    # Having no transition at all is a valid answer and passes.
    for selector, name in used:
        assert name in frames, f"`{selector}` uses @keyframes {name}, which does not exist"
        assert "opacity" not in frames[name], (
            f"`{selector}` animates @keyframes {name}, which changes opacity.\n"
            "A screen cannot animate until the browser has laid out the markup "
            "it was just handed, so the frames before that would be painted "
            "blank. Move it with transform instead (DESIGN.md §7)."
        )


def test_the_screen_root_does_not_animate_in():
    """`.view` is the root element of every screen. It fades nothing."""
    css = _page_css()
    frames = _keyframes(css)
    for selector, body in _rules(css):
        if not re.search(r"(?<![\w-])\.view(?![\w-])", selector):
            continue
        for m in re.finditer(r"animation:\s*([A-Za-z0-9_-]+)", body):
            assert "opacity" not in frames.get(m.group(1), ""), (
                f"`{selector}` animates @keyframes {m.group(1)}, which changes "
                "opacity. .view is the root of every screen, so this fades the "
                "whole page — photographs, buttons and the pass QR — up from "
                "nothing on every navigation. This exact rule was the flash "
                "the organiser reported three times (DESIGN.md §7)."
            )


def test_only_overlays_are_allowed_to_fade():
    """Any new fade-in has to be a deliberate addition to MAY_FADE."""
    css = _page_css()
    fading = {name for name, body in _keyframes(css).items() if "opacity" in body}
    offenders = [
        f"{selector}  →  @keyframes {m.group(1)}"
        for selector, body in _rules(css)
        for m in re.finditer(r"animation:\s*([A-Za-z0-9_-]+)", body)
        if m.group(1) in fading and not any(ok in selector for ok in MAY_FADE)
    ]
    assert not offenders, (
        "These fade content in, and content must never start invisible:\n  "
        + "\n  ".join(offenders)
        + "\n\nIf one of them really is an overlay rather than content, add its "
          "selector to MAY_FADE above and say why."
    )


def test_the_card_morph_never_fades():
    """The Up next card grows into Your bookings (STATE.md decision 121).

    It is a View Transition: the browser animates pictures of screens it has
    already drawn, so it cannot paint the blank frame of decision 113. But the
    browser's own default for those pictures is a cross-fade — opacity — so
    this holds the morph to the same rule as everything else: whatever its
    pseudo-elements animate must not touch opacity, and the page's two
    pictures (old and new root) must have their animation set here, for both
    directions, so the browser's fade never runs on the whole screen.
    """
    css = _page_css()
    frames = _keyframes(css)
    vt = [(sel, body) for sel, body in _rules(css) if "::view-transition" in sel]
    assert vt, "the card morph's CSS is missing from the Mini App"
    for selector, body in vt:
        assert "opacity" not in body, (
            f"`{selector}` sets opacity. The morph moves and reveals; it never "
            "fades (DESIGN.md §7)."
        )
        for m in re.finditer(r"animation:\s*([A-Za-z0-9_-]+)", body):
            name = m.group(1)
            if name == "none":
                continue
            assert name in frames, f"`{selector}` uses @keyframes {name}, which does not exist"
            assert "opacity" not in frames[name], (
                f"`{selector}` animates @keyframes {name}, which changes opacity. "
                "Reveal with visibility and move with transform instead."
            )
    for direction in ("open", "close"):
        for side in ("old", "new"):
            want = f'html[data-morph="{direction}"]::view-transition-{side}(root)'
            assert any(sel == want and "animation:" in body for sel, body in vt), (
                f"{want} does not set its animation, so the browser would "
                "cross-fade the whole page on the way "
                + ("in" if direction == "open" else "out") + "."
            )
