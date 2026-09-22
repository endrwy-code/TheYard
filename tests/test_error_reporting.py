"""Every failure answers in JSON, and says whose fault it is.

Both pages read every answer with `res.json()`. Anything that is not JSON —
Flask's HTML error page, a proxy's error page — makes that parse throw, and
the page can only report it as a network fault. On 17 Sep that turned a
one-line database error during the roster import into "Can't reach The Yard",
and sent the organiser looking at the tunnel while app.py sat there with the
real answer in its window.

So: an API route must never answer with HTML, whatever goes wrong inside it.
"""

import pytest

import app as webapp
from test_claims_concurrent import (  # noqa: F401 - fixtures are used by name
    Console, err, roster, secrets_and_limits,
)
from services import admin as console


@pytest.fixture()
def crashing(monkeypatch):
    """Flask re-raises inside a test client unless we ask it not to, which is
    the whole behaviour under test here."""
    monkeypatch.setitem(webapp.app.config, "PROPAGATE_EXCEPTIONS", False)
    return monkeypatch


def test_an_unhandled_crash_answers_in_json(roster, crashing):
    def boom(*a, **k):
        raise RuntimeError("something nobody predicted")
    crashing.setattr(console, "roster_view", boom)

    r = Console("admin").get("/admin/api/roster")
    assert r.status_code == 500
    assert r.mimetype == "application/json"          # never text/html
    body = r.get_json()
    assert body["ok"] is False
    assert body["error"]["code"] == "SERVER_ERROR"
    assert "nothing was saved" in body["error"]["message"].lower()


def test_a_database_rule_break_is_a_conflict_not_a_crash(roster, crashing):
    import sqlite3

    def boom(*a, **k):
        raise sqlite3.IntegrityError("UNIQUE constraint failed: attendees.handle")
    crashing.setattr(console, "roster_view", boom)

    r = Console("admin").get("/admin/api/roster")
    assert r.status_code == 409
    body = r.get_json()
    assert body["error"]["code"] == "CONFLICT"
    # The constraint name is the one clue to which rule was broken.
    assert "attendees.handle" in body["error"]["message"]


def test_a_crash_on_the_mini_app_api_also_answers_in_json(roster, crashing):
    from services import people

    def boom(*a, **k):
        raise RuntimeError("nope")
    crashing.setattr(people, "search", boom)

    r = Console("admin").get("/admin/api/people?q=a")
    assert r.status_code == 500
    assert r.mimetype == "application/json"
    assert r.get_json()["error"]["code"] == "SERVER_ERROR"


def test_an_unknown_endpoint_still_answers_in_json(roster):
    r = Console("admin").get("/admin/api/no-such-thing")
    assert r.status_code == 404
    assert r.mimetype == "application/json"
    assert r.get_json()["error"]["code"] == "NOT_FOUND"


def test_a_page_route_is_not_turned_into_json(roster):
    """Only /api/ and /admin/api/ answer in JSON. A missing page is a page."""
    r = webapp.app.test_client().get("/no-such-page")
    assert r.status_code == 404
    assert r.mimetype != "application/json"
