"""The clock is the game — so the clock gets a test.

`CHANGES_FOR_CLAUDE_CODE.md` §7 is ten rules for anyone who edits this room
later, and four of them are each one careless edit away from silently
destroying it. Silently is the word that matters: none of these failures looks
like a bug when you read the file. The room simply stops working on the night,
and nobody can say why.

The one that matters most is the boxed rule in §2. The eating window is derived
from the call log and the fridge card, both network-true. If any part of it
ever came off a camera stamp instead, correcting the clock would move the
window by the same twenty minutes, the two shifts would cancel, and the whole
puzzle would have no effect at all. A team would do the clock work correctly
and learn nothing from it.

These tests read the real phone file, not a stub.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import phone_template as pt          # noqa: E402

# EVIDENCE_BRIEF.md §4 / CHANGES_FOR_CLAUDE_CODE.md §3. Stamp -> real, in
# minutes past midnight. One hub, one offset, every camera.
OFFSET_MINUTES = 20
STILLS = [
    (1, "HALLWAY", "22:04", "21:44", "Darren leaving"),
    (2, "KITCHEN", "22:08", "21:48", "Jasmine and Kai in the kitchen"),
    (3, "HALLWAY", "22:10", "21:50", "Ethan leaving"),
    (4, "HALLWAY", "22:16", "21:56", "Jasmine leaving"),
    (5, "KITCHEN", "22:22", "22:02", "Natalie alone with the cakes"),
    (6, "HALLWAY", "22:24", "22:04", "Natalie leaving"),
    (7, "HALLWAY", "22:57", "22:37", "the finder arriving"),
]

# The window, from the ~10:30 collapse and the fridge card's 10-20 minute
# reaction. Both sources are network-true; neither is a camera.
WINDOW = ("22:10", "22:20")


def mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


@pytest.fixture(scope="module")
def phone_markup():
    """The real phone's words, decoded the only safe way."""
    _, _, markup = pt.load()
    return markup


# ---------------------------------------------------------------------------
# Rule 1 — the window never touches a camera
# ---------------------------------------------------------------------------

def test_no_camera_stamp_appears_anywhere_on_the_phone(phone_markup):
    """The phone is the network, and the network is true.

    A camera stamp on the phone is the one mistake that cancels the puzzle
    out: correcting the clock would move the window with it and the room's
    whole reveal would do nothing.
    """
    for _, cam, stamp, _, what in STILLS:
        assert stamp not in phone_markup, (
            f"camera stamp {stamp} ({cam}, {what}) is on the phone. "
            "Camera stamps are printed paper only — see the boxed rule in "
            "CHANGES_FOR_CLAUDE_CODE.md §2.")


def test_the_phone_carries_the_two_sources_the_window_is_built_from(phone_markup):
    """Ethan's call is half the window: 9:52 PM for 16m 12s puts Kai on the
    phone, alive and not eating, until 10:08. The collapse is the other half,
    and it comes off the fridge card in the flat."""
    assert "9:52 PM" in phone_markup and "16m 12s" in phone_markup
    for missed in ("10:31 PM", "10:32 PM", "10:33 PM"):
        assert missed in phone_markup


# ---------------------------------------------------------------------------
# Rule 2 — the offset is FAST, and uniform
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n,cam,stamp,real,what", STILLS)
def test_every_still_is_exactly_twenty_minutes_fast(n, cam, stamp, real, what):
    assert mins(stamp) - mins(real) == OFFSET_MINUTES, (
        f"Still {n} ({what}) is {mins(stamp) - mins(real)} minutes out, not "
        f"{OFFSET_MINUTES}. One hub, one number, every camera.")


def test_the_offset_is_fast_never_behind():
    """Direction is the thing people get wrong. The stamp reads *later* than
    the truth, so correcting it always subtracts."""
    for _, _, stamp, real, what in STILLS:
        assert mins(stamp) > mins(real), f"{what}: the stamp must read later than the truth"


# ---------------------------------------------------------------------------
# Rule 3 — no raw stamp may fall after the collapse
# ---------------------------------------------------------------------------

def test_no_raw_stamp_falls_after_the_collapse():
    """Rule 3. A raw stamp after 10:30 would have somebody walking past a man
    collapsing, and the trap would point at the wrong person for the wrong
    reason. The finder at 22:57 is the deliberate exception — he is the one
    who *does* arrive after it, and his statement says so."""
    for n, _, stamp, _, what in STILLS:
        if n == 7:
            continue
        assert mins(stamp) <= mins("22:30"), (
            f"Still {n} ({what}) stamps at {stamp}, after the collapse.")


# ---------------------------------------------------------------------------
# Rule 4 — a uniform shift cannot reorder anyone
# ---------------------------------------------------------------------------

def test_correcting_the_clock_never_reorders_anybody():
    """The reveal is never "the order changes" — it is always "the window
    moves relative to the people". A uniform shift preserves order, and this
    is what says so if somebody ever gives one camera its own number."""
    raw = [mins(s) for _, _, s, _, _ in STILLS]
    corrected = [mins(r) for _, _, _, r, _ in STILLS]
    assert raw == sorted(raw) and corrected == sorted(corrected)
    assert [b - a for a, b in zip(raw, raw[1:])] == \
           [b - a for a, b in zip(corrected, corrected[1:])]


# ---------------------------------------------------------------------------
# The flip itself — what the room is for
# ---------------------------------------------------------------------------

def test_read_raw_the_stamps_frame_jasmine():
    """The trap. Raw, Jasmine's exit lands inside the eating window and every
    team goes for her."""
    jasmine_out = mins("22:16")
    assert mins(WINDOW[0]) <= jasmine_out <= mins(WINDOW[1])


def test_corrected_the_flat_is_empty_before_he_could_have_eaten():
    """The answer. Natalie is out at 10:04, the earliest he can have eaten is
    10:10, and nobody is in the flat in between — so it was left for him.

    Rule 7 asks for a five-minute margin here. Close that gap and a player can
    argue she was still in the room when he ate, which puts the murder back in
    the room and undoes the whole rewrite.
    """
    natalie_out = mins("22:04")                     # Still 6, corrected
    assert natalie_out < mins(WINDOW[0])
    assert mins(WINDOW[0]) - natalie_out >= 5


def test_natalie_is_the_last_person_alone_with_the_cakes():
    corrected = {what: mins(real) for _, _, _, real, what in STILLS}
    exits = {w: t for w, t in corrected.items() if "leaving" in w}
    assert max(exits, key=exits.get) == "Natalie leaving"


def test_the_answer_time_is_the_swap_not_the_death():
    """10:02 is Still 5 corrected — the minute Natalie is alone in the
    kitchen. It is only obtainable by correcting a camera stamp, which is what
    makes the clock work compulsory rather than optional. The lock code is
    that time with the colon taken out."""
    still5_real = next(r for n, _, _, r, _ in STILLS if n == 5)
    assert still5_real == "22:02"
    h, m = still5_real.split(":")
    assert f"{int(h) % 12 or 12}{m}" == "1002"      # 22:02 -> 10:02 PM -> 1002


# ---------------------------------------------------------------------------
# Rule 6 — no document names the killer
# ---------------------------------------------------------------------------

def test_the_phone_never_hands_over_natalie_without_the_clock(phone_markup):
    """Her 6:47 PM "passed your bakery" is the only tie between her and the
    walnut cake, and it reads as a sister being nice until the 6:42 PM cash
    receipt in bin photo B is found. Nothing on the phone may shortcut that."""
    assert "passed your bakery. couldnt resist" in phone_markup
    assert "was it good? x" in phone_markup
    for giveaway in ("walnut", "Walnut", "WALNUT", "epipen", "EpiPen", "swap"):
        assert giveaway not in phone_markup, (
            f"{giveaway!r} is on the phone — it skips the clock (rule 6).")


# ---------------------------------------------------------------------------
# Rule 8 — the GM console must never leave the lock code lying about
# ---------------------------------------------------------------------------

def test_the_reset_list_scrambles_the_lock_and_never_says_the_old_code():
    import json

    import config
    data = json.loads(config.GM_SCRIPT.read_text(encoding="utf-8"))
    reset = " ".join(data["reset"])
    assert "1002" in reset and "scramble" in reset.lower()
    assert "1012" not in reset, "1012 was the old answer — it is not the code any more."
