"""The payment gate is off unless somebody asks for it — §9 r25, STATE.md 138.

Every payment gate in the app comes through `claims.payment_ok`, and that
reads one settings row: `claim_requires`. The organiser set it to "none" on
22 Sep, but the *default* said "submitted" until 23 Sep — so a database nobody
had touched came up refusing hand-overs. That is any fresh install, and it is
the server on its first deploy, where the disk starts empty.

These tests are the guard. They assert the shape of a **virgin database**: no
settings edited, nobody verified, and every way through the app open anyway.
If one of them fails, somebody has made payment checking the default again,
and the booth will refuse people on the night.
"""

import pytest

import config
import db
from conftest import sign
from services import claims, notify, people
from test_claims_concurrent import (  # noqa: F401 - fixtures are used by name
    Console, err, roster, secrets_and_limits,
)

PAY_STATES = ("missing", "submitted", "rejected", "verified")


def somebody(conn, handle, status):
    now = db.utcnow()
    code = db.new_code(conn, "attendees", "pass_code")
    cur = conn.execute(
        "INSERT INTO attendees (name, handle, handle_raw, source, status, is_test, "
        "payment_status, pass_code, created_at, updated_at) "
        "VALUES (?,?,?,'import','active',1,?,?,?,?)",
        ("Test " + handle, handle, "@" + handle, status, code, now, now))
    return conn.execute("SELECT * FROM attendees WHERE id=?", (cur.lastrowid,)).fetchone()


# ---------------------------------------------------------------------------
# The setting itself
# ---------------------------------------------------------------------------

def test_the_default_is_no_payment_checking():
    """`config.py` is the starting text for a fresh database, so this is the
    value a new server comes up with."""
    assert config.DEFAULT_SETTINGS["claim_requires"] == "none"


def test_a_virgin_database_is_not_checking_payments(roster):
    assert db.get_setting(roster, "claim_requires") == "none"


def test_a_missing_row_does_not_switch_checking_on(roster):
    """The fallback matters as much as the default: a gate has to be asked
    for, and a row that is not there is not asking."""
    roster.execute("DELETE FROM settings WHERE key='claim_requires'")
    assert claims.payment_ok(roster, somebody(roster, "nobody_checked", "missing")) is True


def test_the_three_modes_still_work_when_asked_for(roster):
    """Nothing here removes the gate — it removes it being the default."""
    wanted = {
        "none": {"missing": True, "submitted": True, "rejected": True, "verified": True},
        "submitted": {"missing": False, "submitted": True, "rejected": False, "verified": True},
        "verified": {"missing": False, "submitted": False, "rejected": False, "verified": True},
    }
    people_rows = {st: somebody(roster, "pay_" + st, st) for st in PAY_STATES}
    for mode, expected in wanted.items():
        db.set_setting(roster, "claim_requires", mode, by="test")
        got = {st: claims.payment_ok(roster, row) for st, row in people_rows.items()}
        assert got == expected, mode


# ---------------------------------------------------------------------------
# Every way through the app, on a virgin database
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", PAY_STATES)
def test_the_booth_hands_over_whatever_the_payment_says(roster, status):
    """The one that costs money on the night: an unverified person collecting."""
    p = somebody(roster, "booth_" + status, status)
    d = Console().lookup(p["pass_code"]).get_json()["data"]
    assert d["payment_ok"] is True and d["can_hand_over"] is True
    assert Console().hand_over(p["pass_code"]).status_code == 200


@pytest.mark.parametrize("status", PAY_STATES)
def test_the_booth_shows_no_payment_warning(roster, status):
    """`can_override` is what puts the amber "Not verified" card and the
    override prompt on the booth screen. There is nothing to override."""
    p = somebody(roster, "card_" + status, status)
    d = Console("admin").lookup(p["pass_code"]).get_json()["data"]
    assert d["can_override"] is False
    assert d.get("payment_status") == status          # still recorded, just not a gate


@pytest.mark.parametrize("status", PAY_STATES)
def test_the_mini_app_tells_nobody_about_their_payment(roster, client, status):
    p = somebody(roster, "app_" + status, status)
    roster.execute("UPDATE attendees SET tg_user_id=? WHERE id=?", (7100 + len(status), p["id"]))
    d = client.get("/api/me", headers={"Authorization": "tma " + sign(7100 + len(status),
                                                                     p["handle"])}).get_json()["data"]
    assert d["payment_ok"] is True
    # Drives the Help question "You haven't seen my payment" and the ticket's
    # payment copy. False means neither appears.
    assert d["event"]["payment_required"] is False


@pytest.mark.parametrize("status", PAY_STATES)
def test_the_person_page_does_not_ask_anybody_to_check(roster, status):
    p = somebody(roster, "page_" + status, status)
    d = people.person(roster, p["id"], "admin")
    assert d["payment_ok"] is True and d["payment_required"] is False


def test_the_last_call_message_reaches_the_unpaid_too(roster):
    """It used to skip anyone `payment_ok` refused, which on a gated database
    is a message silently not sent."""
    db.set_setting(roster, "last_call", True, by="test")
    ids = []
    for st in PAY_STATES:
        p = somebody(roster, "call_" + st, st)
        roster.execute("UPDATE attendees SET tg_user_id=?, can_message=1, checked_in_at=? "
                       "WHERE id=?", (7200 + p["id"], db.utcnow(), p["id"]))
        ids.append(p["id"])
    close = notify.event_local(db.get_setting(roster, "doors_close"))
    mins = int(db.get_setting(roster, "last_call_minutes"))
    notify.schedule_due(roster, close - __import__("datetime").timedelta(minutes=mins - 1))
    got = {r["attendee_id"] for r in
           roster.execute("SELECT attendee_id FROM notifications WHERE kind='last_call'")}
    assert set(ids) <= got


def test_the_bots_pass_message_says_nothing_about_payment(roster):
    """`/pass` used to add "we haven't verified your payment yet, so nothing
    can be handed over. pop by the front desk" — a guest sent to a desk that
    could do nothing about it."""
    for st in PAY_STATES:
        assert claims.payment_ok(roster, somebody(roster, "bot_" + st, st)) is True


def test_the_overview_has_no_payments_to_check_job(roster):
    """With the gate off there is no job to do before the doors, so the
    console does not list one."""
    from datetime import datetime, timezone

    from services import admin
    somebody(roster, "ov_missing", "missing")
    board = admin.overview(roster, datetime(2026, 9, 24, 10, 0, tzinfo=timezone.utc))
    assert all(q["what"] != "Payments to check" for q in board["queue"])
