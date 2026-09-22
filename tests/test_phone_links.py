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
    GM, PHONE_PAGE, at, desk, flat, night, pid,
)


def token_for(conn, handle, when):
    return game.issue_phone_ticket(conn, pid(conn, handle), when)


# --- issuing ---------------------------------------------------------------

def test_a_desk_player_in_a_started_game_gets_a_link(night, roster):
    game.act(roster, night["id"], "start", GM, at(night, 0))
    out = token_for(roster, desk(roster), at(night, 2))
    assert out["path"].startswith("/p/")
    assert len(out["path"]) > 24                  # a real token, not a guessable id
    assert out["seconds"] == game.TICKET_SECONDS


def test_the_flat_group_gets_one_too(night, roster):
    """Everyone in the game has the phone since 22 Sep (STATE.md 130)."""
    game.act(roster, night["id"], "start", GM, at(night, 0))
    assert token_for(roster, flat(roster), at(night, 2))["path"].startswith("/p/")


def test_someone_not_in_the_game_cannot_get_one(night, roster):
    """The same refusal as the in-app phone: one rule, decided in one place."""
    game.act(roster, night["id"], "start", GM, at(night, 0))
    with pytest.raises(ClaimError) as e:
        token_for(roster, "joncjy", at(night, 2))
    assert e.value.code == "PHONE_LOCKED"


def test_no_link_before_the_game_starts(night, roster):
    with pytest.raises(ClaimError) as e:
        token_for(roster, desk(roster), at(night, -3))
    assert e.value.code == "PHONE_LOCKED"


def test_no_link_once_it_has_relocked(night, roster):
    game.act(roster, night["id"], "start", GM, at(night, 0))
    with pytest.raises(ClaimError) as e:
        token_for(roster, desk(roster), at(night, 25.1))
    assert e.value.code == "PHONE_LOCKED"


# --- spending --------------------------------------------------------------

def test_the_link_opens_the_phone(night, roster):
    game.act(roster, night["id"], "start", GM, at(night, 0))
    t = token_for(roster, desk(roster), at(night, 2))["path"].strip("/").rsplit("/", 1)[1]
    assert game.redeem_phone_ticket(roster, t, at(night, 2)) == PHONE_PAGE


def test_it_works_exactly_once(night, roster):
    game.act(roster, night["id"], "start", GM, at(night, 0))
    t = token_for(roster, desk(roster), at(night, 2))["path"].strip("/").rsplit("/", 1)[1]
    game.redeem_phone_ticket(roster, t, at(night, 2))
    with pytest.raises(ClaimError) as e:
        game.redeem_phone_ticket(roster, t, at(night, 3))
    assert "already been used" in e.value.message


def test_it_expires(night, roster):
    game.act(roster, night["id"], "start", GM, at(night, 0))
    when = at(night, 2)
    t = token_for(roster, desk(roster), when)["path"].strip("/").rsplit("/", 1)[1]
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


def test_a_link_stops_working_if_the_phone_is_switched_off(night, roster):
    """Rule 21 is re-checked as the link is spent, not only when it is made.
    Otherwise switching the phone off would not reach a link already issued."""
    game.act(roster, night["id"], "start", GM, at(night, 0))
    t = token_for(roster, desk(roster), at(night, 2))["path"].strip("/").rsplit("/", 1)[1]
    db.set_setting(roster, "in_app_phone", False, by="test")
    with pytest.raises(ClaimError) as e:
        game.redeem_phone_ticket(roster, t, at(night, 3))
    assert e.value.code == "PHONE_OFF"
    # It was spent anyway, so it cannot be retried once the phone comes back.
    assert roster.execute("SELECT used_at FROM phone_tickets WHERE token=?",
                          (t,)).fetchone()["used_at"] is not None


def test_a_link_stops_working_once_the_gm_locks_the_phone(night, roster):
    """The GM's End no longer locks the phone (the 25 minutes run on); the
    GM's Lock phone does, and it reaches a link already in someone's hand."""
    game.act(roster, night["id"], "start", GM, at(night, 0))
    t = token_for(roster, desk(roster), at(night, 2))["path"].strip("/").rsplit("/", 1)[1]
    game.act(roster, night["id"], "lock", GM, at(night, 3))
    with pytest.raises(ClaimError) as e:
        game.redeem_phone_ticket(roster, t, at(night, 3.5))
    assert e.value.code == "PHONE_LOCKED"


def test_two_taps_at_once_only_one_wins(night, roster):
    """The spend is a conditional UPDATE, so a double-tap cannot open two."""
    game.act(roster, night["id"], "start", GM, at(night, 0))
    t = token_for(roster, desk(roster), at(night, 2))["path"].strip("/").rsplit("/", 1)[1]
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
    game.act(roster, night["id"], "start", GM, at(night, 0))
    when = at(night, 2)
    monkeypatch.setattr("app.now_utc", lambda: when)
    t = token_for(roster, desk(roster), when)["path"].strip("/").rsplit("/", 1)[1]
    r = client.get(f"/p/{t}/")
    assert r.status_code == 200
    assert PHONE_PAGE in r.get_data(as_text=True)
    assert "no-store" in r.headers.get("Cache-Control", "")


def test_a_link_without_the_trailing_slash_redirects_rather_than_spending(
        night, roster, client, monkeypatch):
    """The slash is what makes the phone's `assets/...` resolve under the
    token. A link typed or copied without it must still work, and the
    redirect must not burn the single use on the way."""
    game.act(roster, night["id"], "start", GM, at(night, 0))
    when = at(night, 2)
    monkeypatch.setattr("app.now_utc", lambda: when)
    t = token_for(roster, desk(roster), when)["path"].strip("/").rsplit("/", 1)[1]
    r = client.get(f"/p/{t}")
    assert r.status_code in (301, 308)
    assert roster.execute("SELECT used_at FROM phone_tickets WHERE token=?",
                          (t,)).fetchone()["used_at"] is None
    assert client.get(f"/p/{t}/").status_code == 200


def test_a_spent_link_refuses_over_http(night, roster, client, monkeypatch):
    game.act(roster, night["id"], "start", GM, at(night, 0))
    when = at(night, 2)
    monkeypatch.setattr("app.now_utc", lambda: when)
    t = token_for(roster, desk(roster), when)["path"].strip("/").rsplit("/", 1)[1]
    client.get(f"/p/{t}/")
    r = client.get(f"/p/{t}/")
    assert r.status_code == 403
    assert r.get_json()["error"]["code"] == "PHONE_LOCKED"


# --- the pictures (§3 r4, the spoiler firewall) ----------------------------

def test_the_phone_pictures_follow_the_same_rule_as_the_phone(night, roster):
    """These *are* the evidence. Serving them on a looser check than the page
    that shows them would be a hole straight through §3 rule 4."""
    game.act(roster, night["id"], "start", GM, at(night, 0))
    name = game.STORY_IMAGES[0]
    assert game.phone_image(roster, pid(roster, desk(roster)), name, at(night, 2))
    assert game.phone_image(roster, pid(roster, flat(roster)), name, at(night, 2))
    with pytest.raises(ClaimError) as e:
        game.phone_image(roster, pid(roster, "joncjy"), name, at(night, 2))   # not in the game
    assert e.value.code == "PHONE_LOCKED"
    with pytest.raises(ClaimError) as e:
        game.phone_image(roster, pid(roster, desk(roster)), name, at(night, 25.1))
    assert e.value.code == "PHONE_LOCKED"


def test_a_picture_that_is_not_on_the_list_is_refused(night, roster):
    """No path traversal, and no serving whatever happens to be in the folder."""
    game.act(roster, night["id"], "start", GM, at(night, 0))
    who = pid(roster, desk(roster))
    for bad in ("../../.env", "the-phone.html", "anything.jpg", "../app.db"):
        with pytest.raises(ClaimError) as e:
            game.phone_image(roster, who, bad, at(night, 2))
        assert e.value.code == "NOT_FOUND", bad


def test_a_missing_picture_is_a_grey_tile_not_a_broken_image(night, roster):
    """The five photographs do not exist yet. The organiser still has to be
    able to play the whole game through while waiting for them."""
    game.act(roster, night["id"], "start", GM, at(night, 0))
    body = game.phone_image(roster, pid(roster, desk(roster)),
                            game.STORY_IMAGES[0], at(night, 2))
    assert body.startswith(b"\xff\xd8\xff")          # a real JPEG
    assert body == game.MISSING_TILE


def test_the_picture_list_matches_the_real_phone_file():
    """The real phone, not the stub the other tests use.

    `PHONE_IMAGES` is a list kept by hand, because the phone builds seventeen
    of the names in JavaScript rather than writing them out. If the phone file
    is ever rebuilt with different names, this is what says so — otherwise the
    gallery would quietly go grey on the night with nothing to explain it.
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
    game.act(roster, night["id"], "start", GM, at(night, 0))
    t = token_for(roster, desk(roster), at(night, 2))["path"].strip("/").rsplit("/", 1)[1]
    game.redeem_phone_ticket(roster, t, at(night, 2))
    actions = [r["action"] for r in roster.execute(
        "SELECT action FROM audit_log WHERE action LIKE 'Phone link%' ORDER BY id")]
    assert actions == ["Phone link issued", "Phone link used"]

