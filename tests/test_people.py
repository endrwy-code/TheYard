"""P0.3 — search, the person page, payment verdicts, voids,
the gate-denial list. §9 rules 14, 26, 30, 31-33.

Runs against the real Paperform export and a real WAL file (conftest).
"""

import pytest

import db
from conftest import import_real_export, sign
from services import people
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
    # A screenshot is enough since 24 Sep, so this person is already good.
    assert d["payment_status"] == "submitted" and d["payment_ok"] is True
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
# Payment verdicts — §9 r14. No transaction reference since 24 Sep: a
# screenshot counts on its own, and an admin only marks somebody paid who
# arrived without one, or rejects one that is wrong.
# ---------------------------------------------------------------------------

def test_a_screenshot_needs_no_verdict_at_all(roster, admin):
    i = pid(roster, "heidily")
    code = person(roster, "heidily", "submitted")["pass_code"]
    assert status(roster, "heidily") == "submitted"
    # Nobody has touched it, and the booth can already hand over.
    assert Console().lookup(code).get_json()["data"]["can_hand_over"] is True
    assert admin.get(f"/admin/api/people/{i}").get_json()["data"]["payment"] is None


def test_marking_someone_paid_needs_no_reference_and_no_reason(roster, admin):
    """The person who turned up without a screenshot and paid at the desk.
    Needs the gate on, which since 23 Sep is not the default."""
    db.set_setting(roster, "claim_requires", "submitted", by="test")
    h = roster.execute("SELECT handle FROM attendees WHERE payment_status='missing' "
                       "ORDER BY id LIMIT 1").fetchone()["handle"]
    i = pid(roster, h)
    code = person(roster, h, "missing")["pass_code"]
    assert err(Console().hand_over(code))["code"] == "PAYMENT_NOT_VERIFIED"
    assert pay(admin, i, verdict="verified").status_code == 200
    assert status(roster, h) == "verified"
    assert Console("staff", "Aisha", "Booth 2").lookup(code).get_json()["data"]["can_hand_over"] is True
    page = admin.get(f"/admin/api/people/{i}").get_json()["data"]
    assert page["payment"]["by"] == "Organiser"
    assert any(a["what"].startswith("Payment verified") for a in page["audit"])


def test_the_same_screenshot_on_two_people_is_a_warning_not_a_refusal(roster, admin):
    """§9 r30 layer one still warns; nothing about it blocks a second person,
    because two people can honestly send one screenshot — one paid for both."""
    a, b = pid(roster, "heidily"), pid(roster, "bananabelles")
    assert pay(admin, a, verdict="verified").status_code == 200
    assert pay(admin, b, verdict="verified").status_code == 200
    assert status(roster, "heidily") == "verified" and status(roster, "bananabelles") == "verified"


def test_reject_needs_a_reason_and_blocks_the_booth(roster, admin):
    db.set_setting(roster, "claim_requires", "submitted", by="test")
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
    assert err(pay(admin, i, verdict="verified"))["code"] == "VALIDATION_FAILED"
    assert err(pay(admin, i, verdict="reopen"))["code"] == "VALIDATION_FAILED"
    assert pay(admin, i, verdict="reopen", reason="They sent a clearer one").status_code == 200
    assert status(roster, "heidily") == "submitted"
    assert pay(admin, i, verdict="verified").status_code == 200


def test_reopen_without_a_receipt_goes_back_to_missing(roster, admin):
    h = roster.execute("SELECT handle FROM attendees WHERE payment_status='missing' "
                       "ORDER BY id LIMIT 1").fetchone()["handle"]
    i = pid(roster, h)
    assert pay(admin, i, verdict="verified").status_code == 200
    assert pay(admin, i, verdict="reopen", reason="Wrong person").status_code == 200
    assert status(roster, h) == "missing"


def test_unknown_verdict_is_refused(roster, admin):
    assert err(pay(admin, pid(roster, "heidily"), verdict="approved"))["code"] == "VALIDATION_FAILED"


def test_gm_cannot_change_payments(roster):
    gm = Console("gm", "Ryan", "Escape desk")
    r = pay(gm, pid(roster, "heidily"), verdict="verified")
    assert r.status_code == 403 and status(roster, "heidily") == "submitted"


def test_payment_needs_the_csrf_token(roster, admin):
    r = admin.post(f"/admin/api/people/{pid(roster, 'heidily')}/payment",
                   {"verdict": "verified"}, csrf=False)
    assert r.status_code == 403 and status(roster, "heidily") == "submitted"


def test_reimport_never_undoes_a_verdict(roster, admin):
    """§9 r14 — the roster only lifts missing to submitted."""
    assert pay(admin, pid(roster, "heidily"), verdict="verified").status_code == 200
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


# ---------------------------------------------------------------------------
# Paging the list (24 Sep)
# ---------------------------------------------------------------------------

def _many(conn, n):
    """Enough people to need more than one page."""
    for i in range(n):
        conn.execute(
            "INSERT INTO attendees (name, handle, status, source, created_at, updated_at) "
            "VALUES (?,?,'active','walk_in',?,?)",
            (f"Page Person {i:03d}", f"pageperson{i:03d}", db.utcnow(), db.utcnow()))


def test_the_list_pages_instead_of_stopping_at_fifty(roster):
    """It used to stop at 50 and the rest of the roster could only be reached
    by guessing enough of a name to search for."""
    _many(roster, 120)
    first = people.search(roster, "")
    assert first["page"] == 1 and first["shown"] == people.PAGE_SIZE
    assert first["pages"] == -(-first["total"] // people.PAGE_SIZE)
    assert first["has_next"] and not first["has_prev"]
    assert (first["first"], first["last"]) == (1, 50)

    second = people.search(roster, "", page=2)
    assert second["page"] == 2 and (second["first"], second["last"]) == (51, 100)
    assert second["has_prev"] and second["has_next"]

    # No row appears on two pages, and between them they are the whole list.
    ids1 = [p["id"] for p in first["people"]]
    ids2 = [p["id"] for p in second["people"]]
    assert not set(ids1) & set(ids2)

    last = people.search(roster, "", page=first["pages"])
    assert not last["has_next"] and last["last"] == last["total"]


def test_every_person_is_reachable_by_walking_the_pages(roster):
    _many(roster, 120)
    total = people.search(roster, "")["total"]
    seen, page = [], 1
    while True:
        d = people.search(roster, "", page=page)
        seen += [p["id"] for p in d["people"]]
        if not d["has_next"]:
            break
        page += 1
    assert len(seen) == total == len(set(seen))


def test_a_page_number_out_of_range_lands_on_a_real_page(roster):
    """A stale page left over from a wider search must never answer with an
    empty screen — it lands on the last page instead."""
    _many(roster, 120)
    d = people.search(roster, "", page=999)
    assert d["page"] == d["pages"] and d["people"]
    for bad in (0, -3, "", None, "abc"):
        assert people.search(roster, "", page=bad)["page"] == 1


def test_a_search_that_fits_on_one_page_has_no_pager(roster):
    d = people.search(roster, "heidily")
    assert d["pages"] == 1 and not d["has_next"] and not d["has_prev"]
