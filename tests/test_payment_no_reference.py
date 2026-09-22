"""Entrance payments without a transaction reference — §9 r14, r25.

The rest of the payment tests run against the organiser's real export, which
means they only run on a machine that has it. This file builds its own people,
so the rule the whole night depends on — a screenshot is enough, a rejection
takes it away — is checked wherever the suite runs.
"""

import pytest

import db
from services import claims, people
from services.claims import ClaimError


def make(conn, handle, *, receipt="https://paperform.co/r/shot.png", status="submitted"):
    now = db.utcnow()
    code = db.new_code(conn, "attendees", "pass_code")
    cur = conn.execute(
        "INSERT INTO attendees (name, handle, handle_raw, source, status, is_test, "
        "payment_status, paperform_receipt_url, pass_code, created_at, updated_at) "
        "VALUES (?,?,?,'import','active',1,?,?,?,?,?)",
        ("Test " + handle, handle, "@" + handle, status, receipt or None, code, now, now))
    return cur.lastrowid


def row(conn, attendee_id):
    return conn.execute("SELECT * FROM attendees WHERE id=?", (attendee_id,)).fetchone()


def can_collect(conn, attendee_id):
    return claims.payment_ok(conn, row(conn, attendee_id))


# ---------------------------------------------------------------------------
# The default: a screenshot is the approval
# ---------------------------------------------------------------------------

def test_a_screenshot_collects_with_nobody_approving_it(conn):
    i = make(conn, "ada_lovelace")
    assert row(conn, i)["payment_status"] == "submitted"
    assert can_collect(conn, i) is True


def test_no_screenshot_does_not_collect(conn):
    i = make(conn, "grace_hopper", receipt=None, status="missing")
    assert can_collect(conn, i) is False


def test_marking_paid_needs_no_reference_and_no_reason(conn):
    i = make(conn, "grace_hopper", receipt=None, status="missing")
    out = people.set_payment(conn, i, verdict="verified", by="Organiser")
    assert out["payment_status"] == "verified"
    assert can_collect(conn, i) is True


def test_rejecting_takes_the_hand_over_away(conn):
    i = make(conn, "ada_lovelace")
    assert can_collect(conn, i) is True
    people.set_payment(conn, i, verdict="rejected", reason="Amount is $5", by="Organiser")
    assert row(conn, i)["payment_status"] == "rejected"
    assert can_collect(conn, i) is False


def test_rejecting_still_needs_a_reason(conn):
    i = make(conn, "ada_lovelace")
    with pytest.raises(ClaimError) as exc:
        people.set_payment(conn, i, verdict="rejected", by="Organiser")
    assert exc.value.code == "VALIDATION_FAILED"
    assert row(conn, i)["payment_status"] == "submitted"


def test_a_settled_payment_must_be_reopened_before_it_changes(conn):
    i = make(conn, "ada_lovelace")
    people.set_payment(conn, i, verdict="rejected", reason="Blurry", by="Organiser")
    with pytest.raises(ClaimError):
        people.set_payment(conn, i, verdict="verified", by="Organiser")
    with pytest.raises(ClaimError):
        people.set_payment(conn, i, verdict="reopen", by="Organiser")
    people.set_payment(conn, i, verdict="reopen", reason="They sent a clearer one", by="Organiser")
    assert row(conn, i)["payment_status"] == "submitted"
    assert can_collect(conn, i) is True


def test_reopening_someone_with_no_screenshot_goes_back_to_missing(conn):
    i = make(conn, "grace_hopper", receipt=None, status="missing")
    people.set_payment(conn, i, verdict="verified", by="Organiser")
    people.set_payment(conn, i, verdict="reopen", reason="Wrong person", by="Organiser")
    assert row(conn, i)["payment_status"] == "missing"
    assert can_collect(conn, i) is False


def test_the_same_screenshot_on_two_people_is_not_refused(conn):
    """Two people can honestly send one screenshot — one paid for both. The
    duplicate warnings on the person page say so; nothing blocks the second."""
    a = make(conn, "ada_lovelace")
    b = make(conn, "grace_hopper")
    people.set_payment(conn, a, verdict="verified", by="Organiser")
    people.set_payment(conn, b, verdict="verified", by="Organiser")
    assert row(conn, a)["payment_status"] == "verified"
    assert row(conn, b)["payment_status"] == "verified"


# ---------------------------------------------------------------------------
# The other two settings still work
# ---------------------------------------------------------------------------

def test_strict_mode_still_needs_a_verdict(conn):
    db.set_setting(conn, "claim_requires", "verified", by="test")
    i = make(conn, "ada_lovelace")
    assert can_collect(conn, i) is False
    people.set_payment(conn, i, verdict="verified", by="Organiser")
    assert can_collect(conn, i) is True


def test_switching_the_check_off_lets_everyone_collect(conn):
    db.set_setting(conn, "claim_requires", "none", by="test")
    for handle, status, receipt in (("ada_lovelace", "submitted", "https://x/1.png"),
                                    ("grace_hopper", "missing", None),
                                    ("joan_clarke", "rejected", "https://x/2.png")):
        assert can_collect(conn, make(conn, handle, receipt=receipt, status=status)) is True


# ---------------------------------------------------------------------------
# What the console is told
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("setting, required", [
    ("submitted", True), ("verified", True), ("none", False)])
def test_the_console_is_told_whether_there_is_anything_to_check(conn, setting, required):
    db.set_setting(conn, "claim_requires", setting, by="test")
    i = make(conn, "ada_lovelace")
    assert people.person(conn, i, "admin")["payment_required"] is required


def test_a_verdict_is_audited_with_who_made_it(conn):
    i = make(conn, "ada_lovelace")
    people.set_payment(conn, i, verdict="rejected", reason="Amount is $5", by="Organiser")
    last = people.last_verdict(conn, i)
    assert last["action"] == "Payment rejected"
    assert last["by"] == "Organiser" and last["reason"] == "Amount is $5"
