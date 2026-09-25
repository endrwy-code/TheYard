"""The payments export — everyone on the list, who has paid and who has not.

Builds its own people rather than importing the organiser's real export, so
it runs wherever the suite runs (the same reason as test_payment_no_reference).
"""

import io

import openpyxl
import pytest

import db
from services import export, people
from test_claims_concurrent import (  # noqa: F401 - fixtures are used by name
    Console, err, secrets_and_limits,
)


def make(conn, handle, *, status="submitted", receipt="https://paperform.co/r/shot.png",
         active=True, is_test=False, source="import", email=None):
    now = db.utcnow()
    code = db.new_code(conn, "attendees", "pass_code")
    cur = conn.execute(
        "INSERT INTO attendees (name, email, handle, handle_raw, source, status, is_test, "
        "payment_status, paperform_receipt_url, pass_code, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("Test " + handle, email, handle, "@" + handle, source,
         "active" if active else "inactive", int(is_test), status, receipt, code, now, now))
    return cur.lastrowid


def sheets(body):
    wb = openpyxl.load_workbook(io.BytesIO(body))
    return {ws.title: list(ws.iter_rows(values_only=True)) for ws in wb.worksheets}


def by_handle(rows):
    return {r[1]: r for r in rows[1:]}


@pytest.fixture()
def the_list(conn):
    make(conn, "ada", email="ada@example.com")                          # screenshot
    grace = make(conn, "grace", status="missing", receipt=None)         # paid at the desk
    people.set_payment(conn, grace, verdict="verified", by="Organiser")
    make(conn, "linus", status="missing", receipt=None, source="walk_in")
    alan = make(conn, "alan")
    people.set_payment(conn, alan, verdict="rejected", reason="Amount is $5", by="Organiser")
    make(conn, "owner", is_test=True)                                  # the test account
    make(conn, "gone", status="missing", receipt=None, active=False)   # dropped by an import
    return conn


def test_everyone_is_split_into_paid_and_not_paid(the_list):
    body, name, _mime = export.build(the_list, "payments")
    assert name.startswith("The_Yard_Payments_") and name.endswith(".xlsx")
    s = sheets(body)
    assert list(s) == ["Everyone", "Not paid", "Paid"]
    for rows in s.values():
        assert list(rows[0]) == export.PAYMENT_COLUMNS
    assert sorted(by_handle(s["Everyone"])) == ["@ada", "@alan", "@grace", "@linus"]
    assert sorted(by_handle(s["Paid"])) == ["@ada", "@grace"]
    assert sorted(by_handle(s["Not paid"])) == ["@alan", "@linus"]


def test_each_row_says_why(the_list):
    rows = by_handle(sheets(export.build(the_list, "payments")[0])["Everyone"])
    col = {c: i for i, c in enumerate(export.PAYMENT_COLUMNS)}
    ada, grace, alan, linus = rows["@ada"], rows["@grace"], rows["@alan"], rows["@linus"]

    assert ada[col["Payment"]] == "Screenshot at sign-up" and ada[col["Email"]] == "ada@example.com"
    assert ada[col["Marked by"]] is None                   # nobody decided a screenshot

    assert grace[col["Payment"]] == "Marked paid" and grace[col["Marked by"]] == "Organiser"
    assert grace[col["Marked at"]]

    assert alan[col["Paid"]] == "No" and alan[col["Payment"]] == "Rejected"
    assert alan[col["Reason"]] == "Amount is $5" and alan[col["Marked by"]] == "Organiser"

    assert linus[col["Payment"]] == "No screenshot" and linus[col["Signed up"]] == "Walk-in"
    assert ada[col["Signed up"]] == "Paperform"


def test_a_reopened_verdict_is_nobodys_verdict(conn):
    i = make(conn, "ada")
    people.set_payment(conn, i, verdict="rejected", reason="Blurry", by="Organiser")
    people.set_payment(conn, i, verdict="reopen", reason="It was fine", by="Organiser")
    row = by_handle(sheets(export.build(conn, "payments")[0])["Everyone"])["@ada"]
    assert row[3:8] == ("Yes", "Screenshot at sign-up", None, None, None)


def test_an_empty_list_still_downloads(conn):
    s = sheets(export.build(conn, "payments")[0])
    assert [len(rows) for rows in s.values()] == [1, 1, 1]   # headers only


def test_the_admin_downloads_it_and_the_audit_log_says_so(the_list):
    r = Console("admin").get("/admin/api/export/payments")
    assert r.status_code == 200 and r.mimetype == export.XLSX
    assert 'attachment; filename="The_Yard_Payments_' in r.headers["Content-Disposition"]
    assert "Not paid" in sheets(r.data)
    assert the_list.execute("SELECT COUNT(*) FROM audit_log WHERE action='Export downloaded' "
                            "AND entity_id='payments'").fetchone()[0] == 1


def test_a_phone_sign_in_cannot_download_it(the_list):
    assert err(Console().get("/admin/api/export/payments"))["code"] == "FORBIDDEN"
