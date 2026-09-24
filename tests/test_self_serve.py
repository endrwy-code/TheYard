"""Self-serve check-in: the iPad turned round at the door (24 Sep).

Two things are new on the server. `POST /admin/api/unlock` is how a staff
member gets back out of self-serve without signing the device in again, and
`POST /admin/api/checkins` now answers with the payment state, so the screen
can tell somebody to see the front desk without a second, rate-limited call.

Everything the guest actually sees is drawn in the browser and is not covered
here; the RUNBOOK has the organiser walk an iPad through it.
"""

import pytest

import auth
import config
import db
from conftest import import_real_export
from test_claims_concurrent import (
    ADMIN, PASSWORD, PIN, Console, fast_hash, login, new_client, person, qr,
)


@pytest.fixture(autouse=True)
def secrets_and_limits(monkeypatch):
    monkeypatch.setattr(config, "STAFF_PIN_HASH", fast_hash(PIN))
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", fast_hash(PASSWORD))
    auth.reset_rate_limits()
    yield
    auth.reset_rate_limits()


@pytest.fixture()
def roster(conn):
    import_real_export(conn)
    return conn


def err(r):
    return r.get_json()["error"]


# ---------------------------------------------------------------------------
# Getting back out
# ---------------------------------------------------------------------------

def test_the_phone_pin_unlocks_a_self_serve_ipad(roster):
    c = Console("staff")
    r = c.post("/admin/api/unlock", {"secret": PIN})
    assert r.status_code == 200 and r.get_json()["data"]["unlocked"] is True


def test_the_admin_password_unlocks_a_laptop_running_self_serve(roster):
    c = Console("admin", name="Organiser", station=None)
    assert c.post("/admin/api/unlock", {"secret": PASSWORD}).status_code == 200


def test_a_wrong_secret_does_not_unlock(roster):
    c = Console("staff")
    r = c.post("/admin/api/unlock", {"secret": "0000"})
    assert r.status_code == 403 and err(r)["code"] == "FORBIDDEN"


def test_the_other_doors_secret_does_not_unlock_a_phone_sign_in(roster):
    """The device is signed in on Mobile, so the admin password is not its
    secret. Otherwise self-serve would have two ways out where the console
    itself has one."""
    c = Console("staff")
    assert c.post("/admin/api/unlock", {"secret": PASSWORD}).status_code == 403


def test_unlocking_leaves_the_sign_in_exactly_where_it_was(roster):
    """The point of a separate endpoint. Logging in again would work, but it
    would rotate the session and write a sign-in nobody made into the log."""
    client = new_client()
    before = login(client, "staff", "Wei", "Booth 1").get_json()["data"]
    token = before["csrf_token"]
    r = client.post("/admin/api/unlock", json={"secret": PIN},
                    headers={"X-CSRF-Token": token})
    assert r.status_code == 200
    # Same cookie, same role, same station, still able to work — and one
    # sign-in in the log, the real one.
    after = client.get("/admin/api/session").get_json()["data"]
    assert after["role"] == before["role"] and after["station"] == before["station"]
    assert client.post("/admin/api/checkins", json={"code": "nope"},
                       headers={"X-CSRF-Token": after["csrf_token"]}).status_code != 403
    signins = roster.execute(
        "SELECT COUNT(*) n FROM audit_log WHERE action='Console sign-in'").fetchone()["n"]
    assert signins == 1


def test_a_refused_unlock_is_in_the_audit_log(roster):
    c = Console("staff")
    c.post("/admin/api/unlock", {"secret": "0000"})
    rows = [r["action"] for r in roster.execute("SELECT action FROM audit_log")]
    assert "Self-serve unlock refused" in rows


def test_guessing_pins_at_an_unattended_ipad_gets_rate_limited(roster):
    """An iPad on a stand is exactly where somebody would sit and work through
    four-digit PINs, so the unlock shares the sign-in's counter."""
    c = Console("staff")
    codes = set()
    for _ in range(40):
        r = c.post("/admin/api/unlock", {"secret": "0000"})
        codes.add(err(r)["code"])
        if err(r)["code"] == "RATE_LIMITED":
            break
    assert "RATE_LIMITED" in codes
    # And the real PIN is refused too while the limit is on: no walking in
    # behind a burst of guesses.
    assert err(c.post("/admin/api/unlock", {"secret": PIN}))["code"] == "RATE_LIMITED"


def test_unlock_needs_a_signed_in_console(roster):
    client = new_client()
    r = client.post("/admin/api/unlock", json={"secret": PIN})
    assert r.status_code == 401 and err(r)["code"] == "SIGNED_OUT"


def test_unlock_needs_the_csrf_token(roster):
    c = Console("staff")
    r = c.post("/admin/api/unlock", {"secret": PIN}, csrf=False)
    assert r.status_code == 403 and err(r)["code"] == "STALE_TOKEN"


# ---------------------------------------------------------------------------
# What the guest is told
# ---------------------------------------------------------------------------

def test_check_in_says_whether_they_have_paid(roster):
    """Without this the screen needs a lookup as well as a check-in for every
    guest, and the lookup limit is 30 a minute — a queue would hit it."""
    db.set_setting(roster, "claim_requires", "verified")
    p = person(roster, "bananabelles", payment="verified")
    r = Console("staff").check_in(qr(p["pass_code"]))
    d = r.get_json()["data"]
    assert d["payment_ok"] is True and d["payment_status"] == "verified"
    assert d["already"] is False


def test_somebody_unverified_is_checked_in_and_flagged(roster):
    """The organiser's call (24 Sep): the record of who walked through the door
    should not wait on the front desk keeping up. The screen sends them to the
    desk; the check-in still happens."""
    db.set_setting(roster, "claim_requires", "verified")
    p = person(roster, "bananabelles", payment="submitted")
    d = Console("staff").check_in(qr(p["pass_code"])).get_json()["data"]
    assert d["payment_ok"] is False and d["payment_status"] == "submitted"
    assert d["checked_in_at"]
    row = roster.execute("SELECT checked_in_at FROM attendees WHERE id=?", (p["id"],)).fetchone()
    assert row["checked_in_at"] is not None


def test_the_gate_being_off_means_everybody_reads_as_paid(roster):
    """"none" is how the night actually runs, so this is the common case."""
    p = person(roster, "bananabelles", payment="submitted")
    d = Console("staff").check_in(qr(p["pass_code"])).get_json()["data"]
    assert d["payment_ok"] is True


def test_a_pass_left_in_front_of_the_camera_changes_nothing(roster):
    """The screen stops repeats itself, but the server is the thing that must
    not double-count them."""
    p = person(roster, "bananabelles")
    c = Console("staff")
    first = c.check_in(qr(p["pass_code"])).get_json()["data"]
    second = c.check_in(qr(p["pass_code"])).get_json()["data"]
    assert first["already"] is False and second["already"] is True
    assert second["checked_in_at"] == first["checked_in_at"]
    assert second["payment_ok"] is True          # still enough to draw the screen
    logged = roster.execute(
        "SELECT COUNT(*) n FROM audit_log WHERE action='Event check-in'").fetchone()["n"]
    assert logged == 1


def test_the_only_name_the_screen_can_show_is_the_persons_own(roster):
    """Self-serve prints a first name off this. Nothing else about anybody
    comes back from a check-in — no handle history, no other guests."""
    p = person(roster, "bananabelles")
    d = Console("staff").check_in(qr(p["pass_code"])).get_json()["data"]
    assert set(d["person"]) == {"id", "name", "handle"}


def test_a_name_off_the_current_roster_is_refused(roster):
    """Which the screen turns into "please see a staff member" — it never says
    why, in front of the people behind them."""
    roster.execute("UPDATE attendees SET status='inactive' WHERE handle='bananabelles'")
    p = roster.execute("SELECT * FROM attendees WHERE handle='bananabelles'").fetchone()
    r = Console("staff").check_in(qr(p["pass_code"]))
    assert err(r)["code"] == "INACTIVE"


def test_self_serve_cannot_hand_anything_over_without_a_pass(roster):
    """The screen shows no hand-over buttons, but the rule that matters is the
    server's: a claim still needs a code and still goes in the log by name."""
    c = Console("staff")
    r = c.post("/admin/api/claims", {"item": "pastry"})
    assert err(r)["code"] == "VALIDATION_FAILED"
