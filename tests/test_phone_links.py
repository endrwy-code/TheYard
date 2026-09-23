"""§9 rule 23 — one-time links for the full-page phone.

The in-app phone is an iframe inside Telegram's webview. A webview can refuse
to play audio or hold fullscreen, and there is no telling which handset will
misbehave until someone is standing in the room with it. This is the way out:
a link that opens the same phone in the real browser.

It is a fallback, never a second door. It is issued only when rule 21 already
holds, it is spent once, it dies after ninety seconds, and rule 21 is checked
again as it is spent — so a link forwarded to someone outside the game is
worthless.
"""

from datetime import timedelta

import pytest

import db
from services import game
from services.claims import ClaimError
from test_claims_concurrent import (  # noqa: F401 - fixtures are used by name
    Console, err, roster, secrets_and_limits,
)
from test_phone_and_gm import (  # noqa: F401 - fixtures are used by name
    GM, GROUP, PHONE_PAGE, at, night, pid,
)


def token_for(conn, handle, when):
    return game.issue_phone_ticket(conn, pid(conn, handle), when)


# --- issuing ---------------------------------------------------------------

def test_a_player_whose_time_has_come_gets_a_link(night, roster):
    out = token_for(roster, GROUP[0], at(night, 2))
    assert out["path"].startswith("/p/")
    assert len(out["path"]) > 24                  # a real token, not a guessable id
    assert out["seconds"] == game.TICKET_SECONDS


def test_everyone_in_the_game_gets_one(night, roster):
    """Everyone in the game has the phone since 22 Sep (STATE.md 130)."""
    for h in GROUP:
        assert token_for(roster, h, at(night, 2))["path"].startswith("/p/")


def test_someone_not_in_the_game_cannot_get_one(night, roster):
    """The same refusal as the in-app phone: one rule, decided in one place."""
    with pytest.raises(ClaimError) as e:
        token_for(roster, "joncjy", at(night, 2))
    assert e.value.code == "NO_BOOKING"


def test_no_link_before_the_booked_time(night, roster):
    with pytest.raises(ClaimError) as e:
        token_for(roster, GROUP[0], at(night, -3))
    assert e.value.code == "NOT_YET"


def test_no_link_once_it_has_relocked(night, roster):
    with pytest.raises(ClaimError) as e:
        token_for(roster, GROUP[0], at(night, 25.1))
    assert e.value.code == "RELOCKED"


# --- spending --------------------------------------------------------------

def test_the_link_opens_the_phone(night, roster):
    t = token_for(roster, GROUP[0], at(night, 2))["path"].strip("/").rsplit("/", 1)[1]
    assert game.redeem_phone_ticket(roster, t, at(night, 2)) == PHONE_PAGE


def test_it_works_exactly_once(night, roster):
    t = token_for(roster, GROUP[0], at(night, 2))["path"].strip("/").rsplit("/", 1)[1]
    game.redeem_phone_ticket(roster, t, at(night, 2))
    with pytest.raises(ClaimError) as e:
        game.redeem_phone_ticket(roster, t, at(night, 3))
    assert "already been used" in e.value.message


def test_it_expires(night, roster):
    when = at(night, 2)
    t = token_for(roster, GROUP[0], when)["path"].strip("/").rsplit("/", 1)[1]
    late = when + timedelta(seconds=game.TICKET_SECONDS + 1)
    with pytest.raises(ClaimError) as e:
        game.redeem_phone_ticket(roster, t, late)
    assert "expired" in e.value.message


def test_a_made_up_token_opens_nothing(night, roster):
    with pytest.raises(ClaimError) as e:
        game.redeem_phone_ticket(roster, "not-a-real-token", at(night, 2))
    assert e.value.code == "PHONE_LOCKED"


def test_an_empty_token_opens_nothing(night, roster):
    for bad in ("", None):
        with pytest.raises(ClaimError):
            game.redeem_phone_ticket(roster, bad, at(night, 2))


def test_a_link_stops_working_once_the_gm_locks_the_phone(night, roster):
    """The GM's End does not close the phone (the 25 minutes run on); the
    GM's Lock does, and it reaches a link already in someone's hand.

    It is spent anyway, so it cannot be retried once the lock comes off."""
    t = token_for(roster, GROUP[0], at(night, 2))["path"].strip("/").rsplit("/", 1)[1]
    game.act(roster, night["id"], "lock", GM, at(night, 2.5))
    with pytest.raises(ClaimError) as e:
        game.redeem_phone_ticket(roster, t, at(night, 3))
    assert e.value.code == "PHONE_LOCKED"
    assert roster.execute("SELECT used_at FROM phone_tickets WHERE token=?",
                          (t,)).fetchone()["used_at"] is not None


def test_two_taps_at_once_only_one_wins(night, roster):
    """The spend is a conditional UPDATE, so a double-tap cannot open two."""
    t = token_for(roster, GROUP[0], at(night, 2))["path"].strip("/").rsplit("/", 1)[1]
    wins = losses = 0
    for _ in range(2):
        try:
            game.redeem_phone_ticket(roster, t, at(night, 2))
            wins += 1
        except ClaimError:
            losses += 1
    assert (wins, losses) == (1, 1)


# --- through the web layer -------------------------------------------------

def test_the_link_route_needs_no_telegram_and_is_never_cached(
        night, roster, client, monkeypatch):
    """The point of the fallback is that it opens outside Telegram, where
    there is no initData to check. The token is the whole credential."""
    when = at(night, 2)
    monkeypatch.setattr("app.now_utc", lambda: when)
    t = token_for(roster, GROUP[0], when)["path"].strip("/").rsplit("/", 1)[1]
    r = client.get(f"/p/{t}/")
    assert r.status_code == 200
    assert PHONE_PAGE in r.get_data(as_text=True)
    assert "no-store" in r.headers.get("Cache-Control", "")


def test_a_link_without_the_trailing_slash_redirects_rather_than_spending(
        night, roster, client, monkeypatch):
    """The slash is what makes the phone's `assets/...` resolve under the
    token. A link typed or copied without it must still work, and the
    redirect must not burn the single use on the way."""
    when = at(night, 2)
    monkeypatch.setattr("app.now_utc", lambda: when)
    t = token_for(roster, GROUP[0], when)["path"].strip("/").rsplit("/", 1)[1]
    r = client.get(f"/p/{t}")
    assert r.status_code in (301, 308)
    assert roster.execute("SELECT used_at FROM phone_tickets WHERE token=?",
                          (t,)).fetchone()["used_at"] is None
    assert client.get(f"/p/{t}/").status_code == 200


def test_a_spent_link_refuses_over_http(night, roster, client, monkeypatch):
    when = at(night, 2)
    monkeypatch.setattr("app.now_utc", lambda: when)
    t = token_for(roster, GROUP[0], when)["path"].strip("/").rsplit("/", 1)[1]
    client.get(f"/p/{t}/")
    r = client.get(f"/p/{t}/")
    assert r.status_code == 403
    assert r.get_json()["error"]["code"] == "PHONE_LOCKED"


# --- the pictures (§3 r4, the spoiler firewall) ----------------------------

def test_the_phone_pictures_follow_the_same_rule_as_the_phone(night, roster):
    """These *are* the evidence. Serving them on a looser check than the page
    that shows them would be a hole straight through §3 rule 4."""
    name = game.STORY_IMAGES[0]
    assert game.phone_image(roster, pid(roster, GROUP[0]), name, at(night, 2))
    assert game.phone_image(roster, pid(roster, GROUP[1]), name, at(night, 2))
    with pytest.raises(ClaimError) as e:
        game.phone_image(roster, pid(roster, "joncjy"), name, at(night, 2))   # not in the game
    assert e.value.code == "NO_BOOKING"
    with pytest.raises(ClaimError) as e:
        game.phone_image(roster, pid(roster, GROUP[0]), name, at(night, 25.1))
    assert e.value.code == "RELOCKED"


def test_a_picture_that_is_not_on_the_list_is_refused(night, roster):
    """No path traversal, and no serving whatever happens to be in the folder."""
    who = pid(roster, GROUP[0])
    for bad in ("../../.env", "the-phone.html", "anything.jpg", "../app.db"):
        with pytest.raises(ClaimError) as e:
            game.phone_image(roster, who, bad, at(night, 2))
        assert e.value.code == "NOT_FOUND", bad


def test_a_missing_picture_is_a_grey_tile_not_a_broken_image(night, roster):
    """The bank screenshot does not exist yet. The organiser still has to be
    able to play the whole game through while waiting for it."""
    body = game.phone_image(roster, pid(roster, GROUP[0]),
                            game.STORY_IMAGES[0], at(night, 2))
    assert body.startswith(b"\xff\xd8\xff")          # a real JPEG
    assert body == game.MISSING_TILE


def test_the_picture_list_matches_the_real_phone_file():
    """The real phone, not the stub the other tests use.

    `PHONE_IMAGES` is a list kept by hand. Since the 23 Sep rewrite the phone
    asks for exactly one picture, Ethan's bank screenshot, and this is what
    says so if the phone file is ever rebuilt naming something else — otherwise
    the motive would quietly go grey on the night with nothing to explain it.
    """
    import re
    from pathlib import Path
    real = Path(__file__).resolve().parent.parent / "private" / "phone" / "the-phone.html"
    if not real.exists():                      # a fresh clone without the file
        import pytest as _p
        _p.skip("the real phone file is not in this checkout")
    page = real.read_text(encoding="utf-8")
    named = set(re.findall(r"assets/([A-Za-z0-9_\-]+\.jpg)", page))
    assert named, "no asset names found — has the phone file been rebuilt?"
    assert named <= set(game.PHONE_IMAGES), named - set(game.PHONE_IMAGES)
    # The four stills and the bank screenshot are the ones with no fallback.
    assert set(game.STORY_IMAGES) <= named


# --- the audit trail (§9 r32) ----------------------------------------------

def test_issuing_and_using_are_both_logged(night, roster):
    t = token_for(roster, GROUP[0], at(night, 2))["path"].strip("/").rsplit("/", 1)[1]
    game.redeem_phone_ticket(roster, t, at(night, 2))
    actions = [r["action"] for r in roster.execute(
        "SELECT action FROM audit_log WHERE action LIKE 'Phone link%' ORDER BY id")]
    assert actions == ["Phone link issued", "Phone link used"]

