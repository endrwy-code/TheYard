"""P0.3 — search, the person page, payment verdicts, voids,
the gate-denial list. §9 rules 14, 26, 30 (transaction reference), 31-33.

Runs against the real Paperform export and a real WAL file (conftest).
"""

import threading

import pytest

import db
from conftest import import_real_export, sign
from services import claims, people
from test_claims_concurrent import (  # noqa: F401 - fixtures are used by name
    Console, err, person, roster, secrets_and_limits,
)

FUTURE = "https://paperform.co/file/s3.amazonaws.com/x/IMG_1.jpeg?expires=4102444800&signature=a"
PAST = "https://paperform.co/file/s3.amazonaws.com/x/IMG_2.png?expires=946684800&signature=b"


def pid(conn, handle):
    return conn.execute("SELECT id FROM attendees WHERE handle=?", (handle,)).fetchone()["id"]


def status(conn, handle):
    return conn.execute("SELECT payment_status FROM attendees WHERE handle=?",
                        (handle,)).fetchone()["payment_status"]


def pay(console, attendee_id, **body):
    return console.post(f"/admin/api/people/{attendee_id}/payment", body)


@pytest.fixture()
def admin(roster):
    return Console("admin")


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def test_empty_search_lists_everyone(roster, admin):
    d = admin.get("/admin/api/people").get_json()["data"]
    assert d["total"] == 17 and len(d["people"]) == 17
    assert {"id", "name", "handle", "tag"} <= set(d["people"][0])


@pytest.mark.parametrize("q", ["annabelle", "KOH", "@BananaBelles", "t.me/bananabelles", "banana"])
def test_search_by_name_or_username(roster, admin, q):
    d = admin.get("/admin/api/people?q=" + q).get_json()["data"]
    assert "bananabelles" in [p["handle"] for p in d["people"]]


def test_search_by_pass_code_in_any_shape(roster, admin):
    code = person(roster, "heidily", "submitted")["pass_code"]
    for q in (code, code.replace("-", ""), code.lower().replace("-", " ")):
        d = admin.get("/admin/api/people?q=" + q).get_json()["data"]
        assert [p["handle"] for p in d["people"]] == ["heidily"], q


def test_search_by_email(roster, admin):
    email = roster.execute("SELECT email FROM attendees WHERE handle='heidily'").fetchone()["email"]
    assert email
    d = admin.get("/admin/api/people?q=" + email.upper()).get_json()["data"]
    assert [p["handle"] for p in d["people"]] == ["heidily"]


def test_search_treats_wildcards_literally(roster, admin):
    assert admin.get("/admin/api/people?q=%25").get_json()["data"]["total"] == 0
    # "_" is a real character in usernames, so it matches only those that have one.
    found = admin.get("/admin/api/people?q=_").get_json()["data"]["people"]
    assert found and all("_" in (p["handle"] + p["name"]) for p in found)
    assert len(found) < 17


def test_staff_can_search_and_open_a_person(roster):
    wei = Console()
    assert wei.get("/admin/api/people?q=heidily").status_code == 200
    r = wei.get(f"/admin/api/people/{pid(roster, 'heidily')}")
    assert r.status_code == 200


def test_list_tags(roster, admin):
    tags = {p["handle"]: p["tag"] for p in admin.get("/admin/api/people").get_json()["data"]["people"]}
    assert tags["heidily"] == "pending · never opened"
    missing = [h for h, t in tags.items() if t.startswith("no receipt")]
    assert len(missing) == 3


# ---------------------------------------------------------------------------
# The person page
# ---------------------------------------------------------------------------

def test_person_page_shape(roster, admin):
    d = admin.get(f"/admin/api/people/{pid(roster, 'heidily')}").get_json()["data"]
    assert d["handle"] == "heidily"
    assert d["payment_status"] == "submitted" and d["payment_ok"] is False
    assert d["pass_qr"].startswith("data:image/png;base64,")
    assert d["claims"] == {"pastry": {"claimed": False}, "photo": {"claimed": False}, "vinyl": {"claimed": False}}
    assert d["bookings"] == [] and d["payment"] is None
    assert d["receipt"]["source"].startswith("Paperform receipt")


def test_unknown_person_is_not_found(roster, admin):
    r = admin.get("/admin/api/people/99999")
    assert r.status_code == 404 and err(r)["code"] == "NOT_FOUND"


def test_receipt_links_are_admin_only(roster, admin):
    roster.execute("UPDATE attendees SET paperform_receipt_url=? WHERE handle='heidily'", (FUTURE,))
    i = pid(roster, "heidily")
    a = admin.get(f"/admin/api/people/{i}").get_json()["data"]["receipt"]
    assert a["link"] == FUTURE and a["url"] == FUTURE and a["expired"] is False
    s = Console().get(f"/admin/api/people/{i}").get_json()["data"]["receipt"]
    assert s["link"] is None and s["url"] is None


def test_an_expired_paperform_link_is_flagged_not_offered(roster, admin):
    roster.execute("UPDATE attendees SET paperform_receipt_url=? WHERE handle='heidily'", (PAST,))
    rc = admin.get(f"/admin/api/people/{pid(roster, 'heidily')}").get_json()["data"]["receipt"]
    assert rc["expired"] is True and rc["link"] is None and rc["url"] is None
    assert "re-import" in rc["note"]


def test_the_real_exports_links_expire_before_the_event(roster):
    """Recorded in STATE.md open question 8 — each link dies 7 days after its
    submission, so on 22-23 Sep."""
    from datetime import datetime, timezone
    doors = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)
    urls = [r[0] for r in roster.execute(
        "SELECT paperform_receipt_url FROM attendees WHERE paperform_receipt_url IS NOT NULL")]
    assert urls and all(people.link_expires_at(u) < doors for u in urls)


# ---------------------------------------------------------------------------
# Payment verdicts — §9 r14 and the transaction-reference layer of r30
# ---------------------------------------------------------------------------

def test_verify_with_a_reference_lets_the_booth_hand_over(roster, admin):
    i = pid(roster, "heidily")
    code = person(roster, "heidily", "submitted")["pass_code"]
    assert Console().lookup(code).get_json()["data"]["can_hand_over"] is False
    r = pay(admin, i, verdict="verified", txn_ref=" ab 12 34 ")
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["data"]["payment"]["txn_ref"] == "AB1234"
    assert status(roster, "heidily") == "verified"
    assert Console("staff", "Aisha", "Booth 2").lookup(code).get_json()["data"]["can_hand_over"] is True
    page = admin.get(f"/admin/api/people/{i}").get_json()["data"]
    assert page["payment"]["by"] == "Organiser"
    assert any("Payment verified — ref AB1234" in a["what"] for a in page["audit"])


def test_a_reference_proves_one_payment_only(roster, admin):
    assert pay(admin, pid(roster, "heidily"), verdict="verified", txn_ref="8842119").status_code == 200
    r = pay(admin, pid(roster, "bananabelles"), verdict="verified", txn_ref="  8842 119")
    assert r.status_code == 409
    e = err(r)
    assert e["code"] == "DUPLICATE_TXN_REF" and "@heidily" in e["message"]
    assert status(roster, "bananabelles") == "submitted"
    # Nothing half-written: still exactly one receipt row carries the reference.
    assert roster.execute("SELECT COUNT(*) FROM receipts WHERE txn_ref='8842119'").fetchone()[0] == 1
    assert roster.execute(
        "SELECT COUNT(*) FROM audit_log WHERE action LIKE 'Payment verify refused%'").fetchone()[0] == 1


def test_two_admins_racing_on_one_reference(roster):
    """The unique index decides, even in the same instant."""
    handles = ["heidily", "bananabelles", "mr_rishieparker", "sharmaineangg"]
    ids = [pid(roster, h) for h in handles]
    barrier = threading.Barrier(len(ids))
    results = []

    def run(i):
        c = db.connect()
        try:
            barrier.wait()
            people.set_payment(c, i, verdict="verified", txn_ref="RACE-1", by="admin")
            results.append("ok")
        except claims.ClaimError as exc:
            results.append(exc.code)
        finally:
            c.close()

    threads = [threading.Thread(target=run, args=(i,)) for i in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["DUPLICATE_TXN_REF"] * 3 + ["ok"]
    verified = [h for h in handles if status(roster, h) == "verified"]
    assert len(verified) == 1


def test_verify_without_a_reference_needs_a_reason(roster, admin):
    i = pid(roster, "heidily")
    assert err(pay(admin, i, verdict="verified"))["code"] == "VALIDATION_FAILED"
    assert err(pay(admin, i, verdict="verified", txn_ref="ab"))["code"] == "VALIDATION_FAILED"
    r = pay(admin, i, verdict="verified", reason="Cropped above the reference")
    assert r.status_code == 200
    assert r.get_json()["data"]["payment"]["skip_reason"] == "Cropped above the reference"
    # Skipped references are NULL, and NULLs never clash.
    assert pay(admin, pid(roster, "bananabelles"), verdict="verified",
               reason="No reference shown").status_code == 200


def test_reject_needs_a_reason_and_blocks_the_booth(roster, admin):
    i = pid(roster, "heidily")
    assert err(pay(admin, i, verdict="rejected"))["code"] == "VALIDATION_FAILED"
    assert pay(admin, i, verdict="rejected", reason="Amount is $5").status_code == 200
    assert status(roster, "heidily") == "rejected"
    code = person(roster, "heidily", "rejected")["pass_code"]
    assert err(Console().hand_over(code))["code"] == "PAYMENT_NOT_VERIFIED"
    page = admin.get(f"/admin/api/people/{i}").get_json()["data"]
    assert page["payment"]["reason"] == "Amount is $5"


def test_a_verdict_must_be_reopened_before_it_changes(roster, admin):
    i = pid(roster, "heidily")
    assert pay(admin, i, verdict="rejected", reason="Blurry").status_code == 200
    assert err(pay(admin, i, verdict="verified", txn_ref="REF-9"))["code"] == "VALIDATION_FAILED"
    assert err(pay(admin, i, verdict="reopen"))["code"] == "VALIDATION_FAILED"
    assert pay(admin, i, verdict="reopen", reason="They sent a clearer one").status_code == 200
    assert status(roster, "heidily") == "submitted"
    assert pay(admin, i, verdict="verified", txn_ref="REF-9").status_code == 200


def test_reopening_frees_a_mistyped_reference(roster, admin):
    a, b = pid(roster, "heidily"), pid(roster, "bananabelles")
    assert pay(admin, a, verdict="verified", txn_ref="TYPO-77").status_code == 200
    assert pay(admin, b, verdict="verified", txn_ref="TYPO-77").status_code == 409
    assert pay(admin, a, verdict="reopen", reason="Typed Annabelle's ref by mistake").status_code == 200
    assert pay(admin, b, verdict="verified", txn_ref="TYPO-77").status_code == 200


def test_reopen_without_a_receipt_goes_back_to_missing(roster, admin):
    h = roster.execute("SELECT handle FROM attendees WHERE payment_status='missing' "
                       "ORDER BY id LIMIT 1").fetchone()["handle"]
    i = pid(roster, h)
    assert pay(admin, i, verdict="verified", txn_ref="SEEN-AT-DESK").status_code == 200
    assert pay(admin, i, verdict="reopen", reason="Wrong person").status_code == 200
    assert status(roster, h) == "missing"


def test_unknown_verdict_is_refused(roster, admin):
    assert err(pay(admin, pid(roster, "heidily"), verdict="approved"))["code"] == "VALIDATION_FAILED"


def test_gm_cannot_change_payments(roster):
    gm = Console("gm", "Ryan", "Escape desk")
    r = pay(gm, pid(roster, "heidily"), verdict="verified", txn_ref="GM-1")
    assert r.status_code == 403 and status(roster, "heidily") == "submitted"


def test_payment_needs_the_csrf_token(roster, admin):
    r = admin.post(f"/admin/api/people/{pid(roster, 'heidily')}/payment",
                   {"verdict": "verified", "txn_ref": "NOCSRF"}, csrf=False)
    assert r.status_code == 403 and status(roster, "heidily") == "submitted"


def test_reimport_never_undoes_a_verdict(roster, admin):
    """§9 r14 — the roster only lifts missing to submitted."""
    assert pay(admin, pid(roster, "heidily"), verdict="verified", txn_ref="KEEP-1").status_code == 200
    assert pay(admin, pid(roster, "bananabelles"), verdict="rejected", reason="x").status_code == 200
    import_real_export(roster)
    assert status(roster, "heidily") == "verified"
    assert status(roster, "bananabelles") == "rejected"


# ---------------------------------------------------------------------------
# Voids — §9 r26
# ---------------------------------------------------------------------------

def test_admin_voids_a_claim_by_id(roster, admin):
    code = person(roster, "heidily")["pass_code"]
    claim_id = Console().hand_over(code, "photo").get_json()["data"]["id"]
    path = f"/admin/api/claims/{claim_id}/void"
    assert err(admin.post(path, {"reason": "  "}))["code"] == "VALIDATION_FAILED"
    r = admin.post(path, {"reason": "Dropped it"})
    assert r.status_code == 200, r.get_json()
    row = roster.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
    assert row["voided_by"] == "Organiser" and row["void_reason"] == "Dropped it"
    assert err(admin.post(path, {"reason": "again"}))["code"] == "VALIDATION_FAILED"
    # They can collect it again.
    assert Console().hand_over(code, "photo").status_code == 200
    page = admin.get(f"/admin/api/people/{pid(roster, 'heidily')}").get_json()["data"]
    assert any("Photo Strip claim voided — Dropped it" in a["what"] for a in page["audit"])


def test_void_of_an_unknown_claim(roster, admin):
    r = admin.post("/admin/api/claims/99999/void", {"reason": "x"})
    assert r.status_code == 404 and err(r)["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Gate denials on the People screen
# ---------------------------------------------------------------------------

def test_admin_sees_who_was_refused(roster, admin, client):
    client.post("/api/session", headers={"Authorization": "tma " + sign(777, "ryanlow", "Ryan")})
    d = admin.get("/admin/api/gate-attempts").get_json()["data"]["attempts"]
    assert d[0]["tg_username"] == "ryanlow" and d[0]["outcome"] == "NOT_ON_LIST"
    assert Console().get("/admin/api/gate-attempts").status_code == 403
