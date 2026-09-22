"""The pass, booth hand-over and check-in — §17.4, §9 rules 20 and 24-33.

Every test runs against a real temporary SQLite *file* (conftest), so WAL mode
and the busy timeout are exercised the way they will be on the night.
"""

import base64
import io
import json
import sqlite3
import threading

import pytest
from werkzeug.security import generate_password_hash

import auth
import config
import db
from conftest import import_real_export, sign
from services import claims

PIN = "4821"
GM_PIN = "9051"
PASSWORD = "correct-horse-battery"


def fast_hash(secret):
    return generate_password_hash(secret, method="pbkdf2:sha256:1000")


@pytest.fixture(autouse=True)
def secrets_and_limits(monkeypatch):
    monkeypatch.setattr(config, "STAFF_PIN_HASH", fast_hash(PIN))
    monkeypatch.setattr(config, "GM_PIN_HASH", fast_hash(GM_PIN))
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", fast_hash(PASSWORD))
    auth.reset_rate_limits()
    claims.pass_qr_data_uri.cache_clear()
    yield
    auth.reset_rate_limits()


@pytest.fixture()
def roster(conn):
    import_real_export(conn)
    return conn


def person(conn, handle, payment="verified"):
    conn.execute("UPDATE attendees SET payment_status=? WHERE handle=?", (payment, handle))
    return conn.execute("SELECT * FROM attendees WHERE handle=?", (handle,)).fetchone()


def qr(code):
    return "YARD:" + code.replace("-", "")


WEI = {"role": "staff", "name": "Wei", "station": "Booth 1"}
AISHA = {"role": "staff", "name": "Aisha", "station": "Booth 2"}
ADMIN = {"role": "admin", "name": "Organiser", "station": None}


# ---------------------------------------------------------------------------
# Console helpers
# ---------------------------------------------------------------------------

def new_client():
    import app as webapp
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


def login(client, role="staff", name="Wei", station="Booth 1", secret=None):
    body = {"role": role}
    if role == "admin":
        body["password"] = PASSWORD if secret is None else secret
    else:
        body.update(pin=(PIN if role == "staff" else GM_PIN) if secret is None else secret,
                    name=name, station=station)
    return client.post("/admin/api/login", json=body)


class Console:
    """A signed-in browser: cookie in the client, CSRF token in hand."""

    def __init__(self, role="staff", name="Wei", station="Booth 1"):
        self.client = new_client()
        r = login(self.client, role, name, station)
        assert r.status_code == 200, r.get_json()
        self.csrf = r.get_json()["data"]["csrf_token"]

    def get(self, path):
        return self.client.get(path)

    def post(self, path, body=None, csrf=True):
        headers = {"X-CSRF-Token": self.csrf} if csrf else {}
        return self.client.post(path, json=body or {}, headers=headers)

    def lookup(self, code):
        return self.get("/admin/api/lookup/" + code)

    def hand_over(self, code, item="pastry", **extra):
        return self.post("/admin/api/claims", {"code": code, "item": item, **extra})

    def check_in(self, code):
        return self.post("/admin/api/checkins", {"code": code, "kind": "event"})


def err(r):
    return r.get_json()["error"]


# ---------------------------------------------------------------------------
# §17.4 — the race. Once means once.
# ---------------------------------------------------------------------------

def test_database_is_a_wal_file_not_memory(conn):
    assert config.DB_PATH.exists()
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000


def test_the_unique_index_itself_refuses_a_second_claim(roster):
    p = person(roster, "bananabelles")
    ins = ("INSERT INTO claims (attendee_id, item, claimed_at, staff_name, station) "
           "VALUES (?, 'pastry', ?, 'x', 'y')")
    roster.execute(ins, (p["id"], db.utcnow()))
    with pytest.raises(sqlite3.IntegrityError):
        roster.execute(ins, (p["id"], db.utcnow()))


def race(pass_code, actors, item="pastry"):
    """Every actor claims the same item at the same instant, each on its own
    connection and thread. Returns [(actor, result-or-ClaimError)]."""
    barrier = threading.Barrier(len(actors))
    results = []
    lock = threading.Lock()

    def run(who):
        c = db.connect()
        try:
            barrier.wait()
            try:
                out = claims.claim(c, item=item, actor=who, code=pass_code)
            except claims.ClaimError as exc:
                out = exc
            with lock:
                results.append((who, out))
        finally:
            c.close()

    threads = [threading.Thread(target=run, args=(a,)) for a in actors]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert len(results) == len(actors), "a thread hung"
    return results


def test_two_threads_same_claim_exactly_one_wins(roster):
    """§17.4 — two booths, same pass, same second."""
    rows = [person(roster, h) for h in
            ("bananabelles", "heidily", "mr_rishieparker", "nadiarhm")
            if roster.execute("SELECT 1 FROM attendees WHERE handle=?", (h,)).fetchone()]
    assert rows, "no roster rows to race on"
    for p in rows:
        for item in claims.ITEMS:
            results = race(p["pass_code"], [WEI, AISHA], item)
            wins = [(w, r) for w, r in results if isinstance(r, dict)]
            losses = [(w, r) for w, r in results if isinstance(r, claims.ClaimError)]
            assert len(wins) == 1, f"both went green for {p['handle']} {item}"
            assert len(losses) == 1
            winner, won = wins[0]
            _, lost = losses[0]
            assert lost.code == "ALREADY_CLAIMED"
            # The loser is told who won, when, and where (§9 r24).
            c = lost.extra["claim"]
            assert c["item"] == item
            assert c["at"] == won["at"]
            assert c["staff"] == winner["name"] == won["staff"]
            assert c["station"] == winner["station"] == won["station"]
            assert winner["station"] in lost.message and winner["name"] in lost.message

            active = roster.execute(
                "SELECT COUNT(*) FROM claims WHERE attendee_id=? AND item=? AND voided_at IS NULL",
                (p["id"], item)).fetchone()[0]
            assert active == 1


def test_eight_booths_at_once_still_one_claim(roster):
    p = person(roster, "bananabelles")
    actors = [{"role": "staff", "name": f"Vol{i}", "station": f"Booth {i}"} for i in range(8)]
    results = race(p["pass_code"], actors)
    assert sum(isinstance(r, dict) for _, r in results) == 1
    assert all(r.code == "ALREADY_CLAIMED" for _, r in results if not isinstance(r, dict))


def test_two_phones_over_http(roster):
    """The RUNBOOK Phase 13 rehearsal, end to end through the API."""
    p = person(roster, "bananabelles")
    phones = [Console("staff", "Wei", "Booth 1"), Console("staff", "Aisha", "Booth 2")]
    for ph in phones:
        assert ph.lookup(qr(p["pass_code"])).get_json()["data"]["can_hand_over"]

    barrier = threading.Barrier(2)
    out = [None, None]

    def tap(i):
        barrier.wait()
        out[i] = phones[i].hand_over(p["pass_code"])

    threads = [threading.Thread(target=tap, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    codes = sorted(r.status_code for r in out)
    assert codes == [200, 409], [r.get_json() for r in out]
    green = next(r for r in out if r.status_code == 200).get_json()["data"]
    red = next(r for r in out if r.status_code == 409).get_json()["error"]
    assert red["code"] == "ALREADY_CLAIMED"
    assert red["claim"]["staff"] == green["staff"]
    assert red["claim"]["station"] == green["station"]
    assert red["claim"]["at"] == green["at"]
    assert red["message"].startswith("Pastry already collected at ")
    assert f"({green['station']}, {green['staff']})" in red["message"]


def test_staff_and_station_come_from_the_session_not_the_body(roster):
    p = person(roster, "bananabelles")
    wei = Console("staff", "Wei", "Booth 1")
    r = wei.hand_over(p["pass_code"], staff="Mallory", station="Nowhere")
    assert r.get_json()["data"]["staff"] == "Wei"
    row = roster.execute("SELECT * FROM claims WHERE attendee_id=?", (p["id"],)).fetchone()
    assert (row["staff_name"], row["station"]) == ("Wei", "Booth 1")


def test_a_voided_claim_can_be_collected_again(roster):
    p = person(roster, "bananabelles")
    claims.claim(roster, item="pastry", actor=WEI, code=p["pass_code"])
    with pytest.raises(claims.ClaimError):
        claims.void_claim(roster, attendee_id=p["id"], item="pastry", reason=" ", by="x")
    claims.void_claim(roster, attendee_id=p["id"], item="pastry", reason="rehearsal", by="manage.py")
    again = claims.claim(roster, item="pastry", actor=AISHA, code=p["pass_code"])
    assert again["staff"] == "Aisha"
    assert roster.execute("SELECT COUNT(*) FROM claims WHERE attendee_id=?",
                          (p["id"],)).fetchone()[0] == 2        # the void is soft


# ---------------------------------------------------------------------------
# §9 rule 25 — payment, and the admin override
# ---------------------------------------------------------------------------

def test_unverified_payment_is_refused(roster):
    """Strict mode, which is no longer the default: every person needs a
    verdict on their page before the booth may hand anything over."""
    db.set_setting(roster, "claim_requires", "verified", by="test")
    p = person(roster, "bananabelles", "submitted")
    r = Console().hand_over(p["pass_code"])
    assert r.status_code == 403
    assert err(r)["code"] == "PAYMENT_NOT_VERIFIED"
    assert err(r)["payment_status"] == "submitted"
    assert roster.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0


def test_lookup_says_unpaid_and_offers_no_hand_over(roster):
    db.set_setting(roster, "claim_requires", "verified", by="test")
    p = person(roster, "bananabelles", "submitted")
    d = Console().lookup(p["pass_code"]).get_json()["data"]
    assert d["payment_ok"] is False
    assert d["can_hand_over"] is False
    assert d["can_override"] is False            # staff never get the override


def test_a_screenshot_is_enough_without_anybody_approving_it(roster):
    """The default since 24 Sep: the screenshot counts the moment it arrives,
    and the only thing that takes a hand-over away is a rejection."""
    p = person(roster, "bananabelles", "submitted")
    assert Console().lookup(p["pass_code"]).get_json()["data"]["can_hand_over"] is True
    assert Console().hand_over(p["pass_code"]).status_code == 200
    # Nobody without one, though: they pay at the desk and get marked paid.
    q = person(roster, "t_shixuan", "missing")
    assert err(Console().hand_over(q["pass_code"]))["code"] == "PAYMENT_NOT_VERIFIED"


def test_setting_can_relax_to_submitted(roster):
    db.set_setting(roster, "claim_requires", "submitted", by="test")
    p = person(roster, "bananabelles", "submitted")
    assert Console().hand_over(p["pass_code"]).status_code == 200
    q = person(roster, "heidily", "rejected")
    assert err(Console("staff", "Aisha", "Booth 2").hand_over(q["pass_code"]))["code"] \
        == "PAYMENT_NOT_VERIFIED"


def test_the_payment_check_can_be_switched_off_entirely(roster):
    """23 Sep (STATE.md 138). With 150 receipts unchecked the day before, the
    organiser chose to stop checking payments at all: anyone on the list
    collects. Not an override — there is nothing to override."""
    db.set_setting(roster, "claim_requires", "none", by="test")
    for handle, status in (("bananabelles", "submitted"), ("heidily", "missing"),
                           ("t_shixuan", "rejected")):
        p = person(roster, handle, status)
        d = Console().lookup(p["pass_code"]).get_json()["data"]
        assert d["payment_ok"] is True and d["can_hand_over"] is True
        assert d["can_override"] is False            # nothing is being overridden
        assert Console().hand_over(p["pass_code"]).status_code == 200
    # Nothing was logged as an override, and no reason was ever asked for.
    rows = roster.execute("SELECT action FROM audit_log WHERE action LIKE '%handed over%'").fetchall()
    assert rows and not any("override" in r["action"] for r in rows)
    # Somebody off the list is still refused: that check is not about money.
    roster.execute("UPDATE attendees SET status='inactive' WHERE handle='joncjy'")
    gone = roster.execute("SELECT pass_code FROM attendees WHERE handle='joncjy'").fetchone()[0]
    assert err(Console().hand_over(gone))["code"] == "INACTIVE"


def test_switching_the_check_off_does_not_hide_the_receipts(roster):
    """The screenshots are still there to look at — the organiser asked for
    both: no verifying, but still able to see them."""
    db.set_setting(roster, "claim_requires", "none", by="test")
    # Whoever the real export gave a payment screenshot to.
    who = roster.execute("SELECT * FROM attendees WHERE paperform_receipt_url IS NOT NULL "
                         "LIMIT 1").fetchone()
    roster.execute("UPDATE attendees SET payment_status='submitted' WHERE id=?", (who["id"],))
    d = Console("admin").get(f"/admin/api/people/{who['id']}").get_json()["data"]
    assert d["payment_status"] == "submitted"            # still on the record
    # The console is told there is no checking to do, so it drops the verdict
    # workflow rather than showing "Waiting on you" about nothing.
    assert d["payment_required"] is False
    db.set_setting(roster, "claim_requires", "verified", by="test")
    assert Console("admin").get(f"/admin/api/people/{who['id']}"
                                ).get_json()["data"]["payment_required"] is True
    db.set_setting(roster, "claim_requires", "none", by="test")
    # Still presented to an admin — a live link, our saved copy, or an
    # honest "this link has expired"; never quietly dropped.
    assert d["receipt"]["source"] != "No receipt"
    assert d["receipt"]["url"] or d["receipt"]["expired"]
    # Staff still never see it; that rule is untouched (§9 r31).
    assert Console().get(f"/admin/api/people/{who['id']}").get_json()["data"]["receipt"]["url"] is None


def test_admin_override_needs_a_reason_and_is_logged(roster):
    p = person(roster, "bananabelles", "missing")
    admin = Console("admin")
    assert admin.lookup(p["pass_code"]).get_json()["data"]["can_override"] is True

    assert err(admin.hand_over(p["pass_code"]))["code"] == "PAYMENT_NOT_VERIFIED"
    assert err(admin.hand_over(p["pass_code"], override_reason="   "))["code"] \
        == "PAYMENT_NOT_VERIFIED"

    r = admin.hand_over(p["pass_code"], override_reason="Paid cash at the door")
    assert r.status_code == 200
    assert r.get_json()["data"]["override"] is True

    row = roster.execute(
        "SELECT * FROM audit_log WHERE action LIKE 'Pastry handed over%'").fetchone()
    assert row["actor_type"] == "admin"
    assert row["actor_name"] == "Organiser"
    details = json.loads(row["details"])
    assert details["override"] is True
    assert details["reason"] == "Paid cash at the door"
    assert details["blocked_by"] == ["payment missing"]


def test_staff_cannot_override(roster):
    p = person(roster, "bananabelles", "missing")
    r = Console().hand_over(p["pass_code"], override_reason="trust me")
    assert r.status_code == 403
    assert err(r)["code"] == "FORBIDDEN"


def test_inactive_person_is_refused(roster):
    p = person(roster, "bananabelles")
    roster.execute("UPDATE attendees SET status='inactive' WHERE id=?", (p["id"],))
    staff = Console()
    assert staff.lookup(p["pass_code"]).get_json()["data"]["code"] == "INACTIVE"
    assert err(staff.hand_over(p["pass_code"]))["code"] == "INACTIVE"
    assert err(staff.check_in(p["pass_code"]))["code"] == "INACTIVE"


# ---------------------------------------------------------------------------
# §9 rule 20 — codes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [
    "https://example.com/promo", "hello", "4006381333931", "YAR:ABCDEFGH", "ABC",
])
def test_random_qr_is_not_a_yard_code(roster, raw):
    r = Console().lookup(raw)
    assert r.status_code == 400
    assert err(r)["code"] == "NOT_A_YARD_CODE"


@pytest.mark.parametrize("raw", [
    "ZZZZ-ZZZZ",          # right shape, nobody has it
    "YARD:ZZZZZZZZ",
    "YARD:12",            # a Yard payload, but mangled
    "7K3O-Q9XT",          # O is not in the alphabet — a typo
])
def test_unknown_code(roster, raw):
    r = Console().lookup(raw)
    assert r.status_code == 404
    assert err(r)["code"] == "UNKNOWN_CODE"


def test_every_way_of_writing_a_code_finds_the_person(roster):
    p = person(roster, "bananabelles")
    code = p["pass_code"]
    staff = Console()
    for raw in (code, code.lower(), qr(code), qr(code).lower(),
                code.replace("-", " "), code.replace("-", "")):
        r = staff.lookup(raw)
        assert r.status_code == 200, raw
        assert r.get_json()["data"]["person"]["handle"] == "bananabelles"


def test_unknown_code_on_hand_over(roster):
    r = Console().hand_over("ZZZZ-ZZZZ")
    assert err(r)["code"] == "UNKNOWN_CODE"
    assert err(Console("staff", "Aisha", "Booth 2").hand_over("not a pass"))["code"] \
        == "NOT_A_YARD_CODE"


def test_pass_codes_use_the_unambiguous_alphabet(roster):
    for (code,) in roster.execute("SELECT pass_code FROM attendees"):
        body = code.replace("-", "")
        assert len(body) == 8
        assert not set(body) & set("01OIL")


# ---------------------------------------------------------------------------
# §9 rule 27 — stock
# ---------------------------------------------------------------------------

def test_stock_blocks_at_zero_when_the_setting_says_so(roster):
    db.set_setting(roster, "pastry_stock", 1, by="test")
    db.set_setting(roster, "block_at_zero", True, by="test")
    a, b = person(roster, "bananabelles"), person(roster, "heidily")
    first = claims.claim(roster, item="pastry", actor=WEI, code=a["pass_code"])
    assert first["stock"] == {"total": 1, "left": 0, "low": True, "blocks_at_zero": True}
    with pytest.raises(claims.ClaimError) as exc:
        claims.claim(roster, item="pastry", actor=WEI, code=b["pass_code"])
    assert exc.value.code == "OUT_OF_STOCK"


def test_stock_only_warns_when_blocking_is_off(roster):
    db.set_setting(roster, "pastry_stock", 1, by="test")
    a, b = person(roster, "bananabelles"), person(roster, "heidily")
    claims.claim(roster, item="pastry", actor=WEI, code=a["pass_code"])
    second = claims.claim(roster, item="pastry", actor=WEI, code=b["pass_code"])
    assert second["stock"]["left"] == 0 and second["stock"]["low"] is True


def test_no_stock_set_means_untracked(roster):
    a = person(roster, "bananabelles")
    assert claims.claim(roster, item="photo", actor=WEI, code=a["pass_code"])["stock"] is None


# ---------------------------------------------------------------------------
# Check-in, and §9 rule 32 — the audit trail
# ---------------------------------------------------------------------------

def test_check_in_happens_once(roster):
    p = person(roster, "bananabelles")
    door = Console("staff", "Aisha", "Door")
    first = door.check_in(qr(p["pass_code"])).get_json()["data"]
    assert first["already"] is False
    assert first["checked_in_by"] == "Aisha · Door"

    again = Console("staff", "Wei", "Booth 1").check_in(p["pass_code"]).get_json()["data"]
    assert again["already"] is True
    assert again["checked_in_at"] == first["checked_in_at"]
    assert again["checked_in_by"] == "Aisha · Door"
    assert roster.execute(
        "SELECT COUNT(*) FROM audit_log WHERE action='Event check-in'").fetchone()[0] == 1


def test_escape_and_jam_check_in_wait_for_their_tiers(roster):
    p = person(roster, "bananabelles")
    r = Console().post("/admin/api/checkins", {"code": p["pass_code"], "kind": "escape"})
    assert err(r)["code"] == "VALIDATION_FAILED"


def test_every_hand_over_and_check_in_is_audited_with_actor_and_station(roster):
    p = person(roster, "bananabelles")
    Console("staff", "Wei", "Booth 1").hand_over(p["pass_code"], "pastry")
    Console("gm", "Ryan", "Escape desk").hand_over(p["pass_code"], "photo")
    Console("staff", "Aisha", "Door").check_in(p["pass_code"])
    Console("staff", "Tom", "Booth 2").hand_over(p["pass_code"], "pastry")   # loses

    rows = {r["action"]: r for r in roster.execute("SELECT * FROM audit_log")}
    # Staff and GM sign-ins are both Mobile since 22 Sep (decision 126).
    expect = {
        "Pastry handed over": ("mobile", "Wei", "Booth 1"),
        "Photo Strip handed over": ("mobile", "Ryan", "Escape desk"),
        "Event check-in": ("mobile", "Aisha", "Door"),
        "Pastry hand-over refused — already collected": ("mobile", "Tom", "Booth 2"),
    }
    for action, (kind, name, station) in expect.items():
        row = rows[action]
        assert (row["actor_type"], row["actor_name"], row["station"]) == (kind, name, station)
        assert row["entity"] == "attendee" and row["entity_id"] == str(p["id"])
        assert row["at"]
    assert "after" in json.loads(rows["Pastry handed over"]["details"])
    assert "before" in json.loads(rows["Event check-in"]["details"])


def test_sign_in_and_out_are_audited(roster):
    c = Console("staff", "Wei", "Booth 1")
    c.post("/admin/api/logout")
    actions = [r["action"] for r in roster.execute(
        "SELECT action FROM audit_log WHERE actor_name='Wei' ORDER BY id")]
    assert actions == ["Console sign-in", "Console sign-out"]


# ---------------------------------------------------------------------------
# §9 rule 33 — sign-in, sessions, CSRF, roles
# ---------------------------------------------------------------------------

def test_cookie_is_httponly_secure_and_samesite(roster):
    r = login(new_client())
    cookie = r.headers["Set-Cookie"]
    assert "yard_console=" in cookie
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=Lax" in cookie


def test_wrong_pin_is_refused(roster):
    r = login(new_client(), secret="0000")
    assert r.status_code == 403 and err(r)["code"] == "FORBIDDEN"


def test_either_phone_pin_signs_in_on_the_phone(roster):
    """One phone PIN (decision 126), but neither old PIN stopped working."""
    for pin in (PIN, GM_PIN):
        r = login(new_client(), role="mobile", name="Wei", station="Booth 1", secret=pin)
        assert r.status_code == 200 and r.get_json()["data"]["role"] == "mobile"


def test_the_old_sign_in_names_are_mobile_now(roster):
    for old in ("staff", "gm"):
        r = login(new_client(), role=old, name="Wei", station="Booth 1", secret=PIN)
        assert r.get_json()["data"]["role"] == "mobile", old


def test_a_phone_pin_is_not_the_laptop_password(roster):
    assert err(login(new_client(), role="admin", secret=PIN))["code"] == "FORBIDDEN"
    assert err(login(new_client(), role="mobile", secret=PASSWORD))["code"] == "FORBIDDEN"


def test_a_session_from_before_the_change_signs_in_as_mobile(roster):
    c = Console()
    roster.execute("UPDATE console_sessions SET role='gm'")
    assert c.get("/admin/api/session").get_json()["data"]["role"] == "mobile"


def test_staff_need_a_name_and_a_station(roster):
    assert err(login(new_client(), name=" "))["code"] == "VALIDATION_FAILED"
    assert err(login(new_client(), station=""))["code"] == "VALIDATION_FAILED"


def test_missing_hash_says_which_command_to_run(roster, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", "")
    r = login(new_client(), role="admin")
    assert err(r)["code"] == "FORBIDDEN"
    assert "python manage.py set-admin-password" in err(r)["message"]


def test_sign_in_is_rate_limited(roster):
    client = new_client()
    codes = [login(client, role="admin", secret="wrong").status_code for _ in range(5)]
    assert codes == [403] * 5
    r = login(client, role="admin")                  # right password, too late
    assert r.status_code == 429 and err(r)["code"] == "RATE_LIMITED"


def test_sign_in_limit_is_per_device(roster):
    def from_ip(ip, secret=None):
        return new_client().post("/admin/api/login",
                                 json={"role": "admin", "password": secret or PASSWORD},
                                 headers={"X-Forwarded-For": f"1.2.3.4, {ip}"})
    for _ in range(5):
        from_ip("10.0.0.1", "wrong")
    assert from_ip("10.0.0.1").status_code == 429
    assert from_ip("10.0.0.2").status_code == 200


def test_login_must_be_json(roster):
    r = new_client().post("/admin/api/login", data={"role": "admin", "password": PASSWORD})
    assert err(r)["code"] == "VALIDATION_FAILED"


def test_no_session_means_signed_out(roster):
    r = new_client().get("/admin/api/lookup/ZZZZ-ZZZZ")
    assert r.status_code == 401 and err(r)["code"] == "SIGNED_OUT"


def test_state_changes_need_the_csrf_token(roster):
    p = person(roster, "bananabelles")
    c = Console()
    r = c.post("/admin/api/claims", {"code": p["pass_code"], "item": "pastry"}, csrf=False)
    assert r.status_code == 403 and err(r)["code"] == "STALE_TOKEN"
    c.csrf = "not-the-token"
    assert c.hand_over(p["pass_code"]).status_code == 403
    assert roster.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0


def test_sign_out_really_ends_the_session(roster):
    c = Console()
    assert c.post("/admin/api/logout").status_code == 200
    assert err(c.lookup("ZZZZ-ZZZZ"))["code"] == "SIGNED_OUT"


def test_sessions_expire(roster):
    c = Console()
    roster.execute("UPDATE console_sessions SET expires_at='2000-01-01T00:00:00+00:00'")
    assert err(c.lookup("ZZZZ-ZZZZ"))["code"] == "SIGNED_OUT"


def test_signing_in_again_replaces_the_old_session(roster):
    c = Console()
    login(c.client, name="Wei", station="Booth 3")
    live = roster.execute(
        "SELECT COUNT(*) FROM console_sessions WHERE revoked_at IS NULL").fetchone()[0]
    assert live == 1


def test_only_hashes_are_stored(roster):
    c = Console()
    cookie = c.client.get_cookie("yard_console").value
    row = roster.execute("SELECT * FROM console_sessions").fetchone()
    assert c.csrf not in (row["csrf_hash"], row["sid_hash"])
    assert c.csrf not in cookie


@pytest.mark.parametrize("method,path", [
    ("GET", "/admin/api/settings"),
    ("PUT", "/admin/api/settings"),
    ("POST", "/admin/api/people/1/payment"),
    ("POST", "/admin/api/payments/bulk-verify"),
    ("GET", "/admin/api/export/claims"),
    ("GET", "/admin/api/audit"),
    ("POST", "/admin/api/claims/1/void"),
    ("GET", "/admin/api/receipts/1/file"),
    ("GET", "/admin/api/overview"),
    ("POST", "/admin/api/backup"),
    ("POST", "/admin/api/people"),
    ("GET", "/admin/api/roster"),
])
def test_phones_are_refused_laptop_work_on_the_server(roster, method, path):
    """§9 r33 — enforced on the server, including endpoints not built yet.
    The game moved to the phone on 22 Sep (decision 126); these did not."""
    c = Console()
    r = c.client.open(path, method=method, json={}, headers={"X-CSRF-Token": c.csrf})
    assert r.status_code == 403, path
    assert err(r)["code"] == "FORBIDDEN"


def test_a_phone_reaches_the_game_and_the_orders_but_not_settings(roster):
    from services import bookings
    bookings.generate_slots(roster)
    phone = Console("mobile", "Ryan", "Escape desk")
    assert phone.get("/admin/api/gm/state").status_code == 200
    assert phone.get("/admin/api/orders").status_code == 200
    assert err(phone.get("/admin/api/settings"))["code"] == "FORBIDDEN"


def test_admin_passes_the_role_check_everywhere(roster):
    admin = Console("admin")
    assert admin.get("/admin/api/settings").status_code == 200
    # An admin path that doesn't exist is a plain NOT_FOUND, not FORBIDDEN.
    assert err(admin.get("/admin/api/nothing-here"))["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# §9 rule 28 — lookup rate limit
# ---------------------------------------------------------------------------

def test_lookups_are_rate_limited_per_session(roster):
    db.set_setting(roster, "lookup_rate_limit", 3, by="test")
    p = person(roster, "bananabelles")
    wei = Console()
    codes = [wei.lookup(p["pass_code"]).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert err(wei.lookup(p["pass_code"]))["code"] == "RATE_LIMITED"
    # Another volunteer's session has its own budget.
    assert Console("staff", "Aisha", "Booth 2").lookup(p["pass_code"]).status_code == 200


def test_guessing_through_the_hand_over_endpoint_counts_too(roster):
    db.set_setting(roster, "lookup_rate_limit", 2, by="test")
    p = person(roster, "bananabelles")
    wei = Console()
    assert err(wei.hand_over("ZZZZ-ZZZZ"))["code"] == "UNKNOWN_CODE"
    assert err(wei.hand_over("YYYY-YYYY"))["code"] == "UNKNOWN_CODE"
    assert err(wei.hand_over(p["pass_code"]))["code"] == "RATE_LIMITED"


def test_a_busy_booth_is_not_limited_by_its_hand_overs(roster):
    db.set_setting(roster, "lookup_rate_limit", 2, by="test")
    wei = Console()
    for h in ("bananabelles", "heidily", "mr_rishieparker"):
        p = person(roster, h)
        assert wei.hand_over(p["pass_code"]).status_code == 200


# ---------------------------------------------------------------------------
# GET /api/me — the pass in the Mini App
# ---------------------------------------------------------------------------

def me(client, init_data):
    return client.get("/api/me", headers={"Authorization": "tma " + init_data})


def test_me_returns_the_pass_qr_inline(roster, client):
    from PIL import Image
    person(roster, "bananabelles")
    r = me(client, sign(1001, "bananabelles", "Annabelle"))
    assert r.status_code == 200
    d = r.get_json()["data"]
    assert d["profile"]["full_name"] == "Annabelle Koh"
    assert d["payment_ok"] is True
    assert d["pass_qr"].startswith("data:image/png;base64,")
    img = Image.open(io.BytesIO(base64.b64decode(d["pass_qr"].split(",", 1)[1])))
    assert img.format == "PNG" and img.size[0] == img.size[1]
    assert d["claims"] == {"pastry": {"claimed": False}, "photo": {"claimed": False}, "vinyl": {"claimed": False}}
    assert d["escape_booking"] is None and d["jam_bookings"] == []
    assert r.get_json()["server_time"]


def test_qr_payload_is_namespaced():
    assert claims.qr_payload("7K3M-Q9XT") == "YARD:7K3MQ9XT"
    assert claims.parse_code(claims.qr_payload("7K3M-Q9XT")) == "7K3M-Q9XT"


def test_me_shows_a_hand_over_as_punched(roster, client):
    p = person(roster, "bananabelles")
    claims.claim(roster, item="photo", actor=WEI, code=p["pass_code"])
    d = me(client, sign(1001, "bananabelles", "Annabelle")).get_json()["data"]
    assert d["claims"]["pastry"] == {"claimed": False}
    assert d["claims"]["photo"]["claimed"] is True
    assert d["claims"]["photo"]["staff"] == "Wei"
    assert d["claims"]["photo"]["station"] == "Booth 1"
    assert d["claims"]["photo"]["at"].endswith("+08:00")


def test_me_reports_unverified_payment(roster, client):
    db.set_setting(roster, "claim_requires", "verified", by="test")
    person(roster, "bananabelles", "submitted")
    d = me(client, sign(1001, "bananabelles", "Annabelle")).get_json()["data"]
    assert d["payment_status"] == "submitted" and d["payment_ok"] is False


def test_me_runs_the_gate_on_every_call(roster, client):
    assert err(me(client, sign(1002, "ryanlow", "Ryan")))["code"] == "NOT_ON_LIST"
    assert err(client.get("/api/me"))["code"] == "INITDATA_INVALID"
    tg = sign(1001, "bananabelles", "Annabelle")
    assert me(client, tg).status_code == 200
    roster.execute("UPDATE attendees SET status='inactive' WHERE handle='bananabelles'")
    assert err(me(client, tg))["code"] == "INACTIVE"


# ---------------------------------------------------------------------------
# §3 rule 4 — the console page itself carries no spoilers
# ---------------------------------------------------------------------------

def test_admin_page_ships_no_hint_lines(roster, client):
    html = client.get("/admin").get_data(as_text=True)
    for spoiler in ("fifteen out", "Ask about the kitchen", "Give us something", "set it to 0000"):
        assert spoiler not in html
    assert "resumeSession();" in html            # the real page, not an error page
    for gone in ("Call matcha", "SCREENS.reviews", "renderDemo", "matcha"):
        assert gone not in html


def test_unknown_api_path_is_json(roster, client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and err(r)["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Picking a sign-in back up after a reload; settings that follow the code
# ---------------------------------------------------------------------------

def test_a_reloaded_console_keeps_its_sign_in(roster):
    c = Console()
    old = c.csrf
    r = c.get("/admin/api/session")
    d = r.get_json()["data"]
    assert r.status_code == 200 and d["name"] == "Wei" and d["station"] == "Booth 1"
    assert [i["key"] for i in d["items"]] == ["pastry", "photo", "vinyl"]
    c.csrf = d["csrf_token"]
    p = person(roster, "bananabelles")
    assert c.hand_over(p["pass_code"]).status_code == 200
    # The old page's token is now stale; the console fetches a new one and retries.
    c.csrf = old
    assert err(c.hand_over(p["pass_code"], "photo"))["code"] == "STALE_TOKEN"


def test_no_session_cannot_resume(roster):
    assert err(new_client().get("/admin/api/session"))["code"] == "SIGNED_OUT"


def test_untouched_settings_follow_the_code_and_edited_ones_stay(roster):
    roster.execute("UPDATE settings SET value='\"22:30\"' WHERE key='doors_close'")          # old default
    db.set_setting(roster, "venue", "Somewhere else", by="admin")                           # a person's edit
    roster.execute("INSERT INTO settings (key, value, updated_by) VALUES ('paynow_name', '\"x\"', 'system')")
    db.seed_settings(roster)
    s = db.get_settings(roster)
    assert s["doors_close"] == "22:00" and s["venue"] == "Somewhere else"
    assert roster.execute("SELECT COUNT(*) FROM settings WHERE key='paynow_name'").fetchone()[0] == 0