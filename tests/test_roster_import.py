"""Roster import — §17.9 and §9 rules 10-14.

Every test runs against the organiser's real Paperform export, not a fixture
invented to match a description of it.
"""

import pytest

import db
from conftest import EXPORT
from services import roster


@pytest.fixture()
def rows():
    return roster.read_export(EXPORT)


# --- §9 rule 10: reading the file ------------------------------------------

def test_blank_rows_are_skipped(rows):
    """The sheet is 1017 rows: a header, 17 sign-ups, ~1,000 blank ones."""
    assert len(rows) == 17


def test_names_are_trimmed(rows):
    assert all(r["name"] == r["name"].strip() for r in rows)
    assert "Annabelle Koh" in [r["name"] for r in rows]     # stored as 'Annabelle Koh '


def test_paperform_id_is_never_a_float(rows):
    ids = [r["paperform_id"] for r in rows]
    assert all(i.isdigit() for i in ids), ids
    assert "1789457183000" in ids                            # Excel holds 1789457183000.0


def test_handles_are_normalised(rows):
    handles = [r["handle"] for r in rows]
    assert all(not h.startswith("@") for h in handles)
    assert all(h == h.lower() for h in handles)
    assert "mr_rishieparker" in handles                       # '@Mr_RishieParker'
    assert all(r["handle_raw"].startswith("@") for r in rows)  # raw form is kept


def test_submitted_at_is_display_only_text(rows):
    assert all(isinstance(r["submitted_at"], str) for r in rows)
    assert rows[0]["submitted_at"].startswith("2026-09-15")


def test_three_rows_have_no_receipt(rows):
    assert sum(1 for r in rows if not r["receipt_url"]) == 3


def test_a_sheet_with_the_wrong_name_is_rejected(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.title = "Sheet1"
    path = tmp_path / "wrong.xlsx"
    wb.save(path)
    with pytest.raises(ValueError, match="Registrations"):
        roster.read_export(path)


# --- §9 rules 11-14: preview and commit ------------------------------------

def test_preview_writes_nothing(conn, rows):
    roster.preview(conn, rows, "x.xlsx")
    assert conn.execute("SELECT COUNT(*) c FROM attendees").fetchone()["c"] == 0


def test_commit_writes_everyone(conn, rows):
    p = roster.preview(conn, rows, "x.xlsx")
    assert p["counts"] == {"new": 17, "changed": 0, "unchanged": 0,
                           "missing": 0, "no_receipt": 3}
    assert not p["problems"]
    roster.commit(conn, p["run_id"])
    assert conn.execute("SELECT COUNT(*) c FROM attendees").fetchone()["c"] == 17


def test_receipt_link_sets_submitted_never_verified(conn, rows):
    p = roster.preview(conn, rows, "x.xlsx")
    roster.commit(conn, p["run_id"])
    counts = {r["payment_status"]: r["c"] for r in conn.execute(
        "SELECT payment_status, COUNT(*) c FROM attendees GROUP BY 1")}
    assert counts == {"submitted": 14, "missing": 3}
    assert "verified" not in counts               # §9 r14 — only an admin verifies


def test_everyone_gets_a_unique_unambiguous_pass_code(conn, rows):
    p = roster.preview(conn, rows, "x.xlsx")
    roster.commit(conn, p["run_id"])
    codes = [r["pass_code"] for r in conn.execute("SELECT pass_code FROM attendees")]
    assert len(set(codes)) == 17 and all(codes)
    assert not any(set(c.replace("-", "")) & set("01OIL") for c in codes)


def test_reimport_is_idempotent(conn, rows):
    p = roster.preview(conn, rows, "x.xlsx")
    roster.commit(conn, p["run_id"])
    again = roster.preview(conn, roster.read_export(EXPORT), "x.xlsx")
    assert again["counts"]["new"] == 0
    assert again["counts"]["changed"] == 0
    assert again["counts"]["missing"] == 0
    assert again["counts"]["unchanged"] == 17


def test_missing_person_goes_inactive_and_keeps_their_history(conn, rows):
    p = roster.preview(conn, rows, "x.xlsx")
    roster.commit(conn, p["run_id"])
    person = conn.execute("SELECT * FROM attendees WHERE handle='bingkiat'").fetchone()
    conn.execute(
        "INSERT INTO claims (attendee_id, item, claimed_at, staff_name, station) "
        "VALUES (?, 'pastry', '2026-09-24T12:00:00+00:00', 'Wei', 'Booth 1')",
        (person["id"],))

    fewer = [r for r in rows if r["handle"] != "bingkiat"]
    p2 = roster.preview(conn, fewer, "fewer.xlsx")
    assert p2["counts"]["missing"] == 1
    roster.commit(conn, p2["run_id"])

    still = conn.execute("SELECT * FROM attendees WHERE handle='bingkiat'").fetchone()
    assert still is not None                       # never deleted
    assert still["status"] == "inactive"
    kept = conn.execute("SELECT COUNT(*) c FROM claims WHERE attendee_id=?",
                        (person["id"],)).fetchone()["c"]
    assert kept == 1                               # their claims stay


def test_a_changed_name_is_reported_as_changed(conn, rows):
    p = roster.preview(conn, rows, "x.xlsx")
    roster.commit(conn, p["run_id"])
    edited = [dict(r) for r in rows]
    edited[0]["name"] = "Annabelle Koh-Tan"
    p2 = roster.preview(conn, edited, "edited.xlsx")
    assert p2["counts"]["changed"] == 1
    assert not p2["problems"]


# --- §9 rule 13: problems block the commit ---------------------------------

def test_duplicate_username_is_a_problem(conn, rows):
    dupe = [dict(r) for r in rows]
    dupe[1]["handle"] = dupe[0]["handle"]
    dupe[1]["paperform_id"] = "999"
    p = roster.preview(conn, dupe, "dupe.xlsx")
    assert any("Duplicate username" in x["message"] for x in p["problems"])


def test_invalid_username_is_a_problem(conn, rows):
    bad = [dict(r) for r in rows]
    bad[0]["handle"] = "no"
    bad[0]["handle_raw"] = "no"
    p = roster.preview(conn, bad, "bad.xlsx")
    assert any("not a Telegram username" in x["message"] for x in p["problems"])


def test_invalid_email_is_a_problem(conn, rows):
    bad = [dict(r) for r in rows]
    bad[0]["email"] = "clara@@mail"
    p = roster.preview(conn, bad, "bad.xlsx")
    assert any("Invalid email" in x["message"] for x in p["problems"])


def test_changed_handle_on_a_linked_person_is_a_problem(conn, rows):
    p = roster.preview(conn, rows, "x.xlsx")
    roster.commit(conn, p["run_id"])
    conn.execute("UPDATE attendees SET tg_user_id=5512847 WHERE handle='bananabelles'")
    renamed = [dict(r) for r in rows]
    renamed[0]["handle"] = "annabelle_new"
    p2 = roster.preview(conn, renamed, "renamed.xlsx")
    assert any("already linked" in x["message"] for x in p2["problems"])


def test_commit_refuses_a_preview_with_problems(conn, rows):
    bad = [dict(r) for r in rows]
    bad[0]["email"] = "not-an-email"
    p = roster.preview(conn, bad, "bad.xlsx")
    with pytest.raises(ValueError, match="problems"):
        roster.commit(conn, p["run_id"])
    assert conn.execute("SELECT COUNT(*) c FROM attendees").fetchone()["c"] == 0


def test_a_run_cannot_be_committed_twice(conn, rows):
    p = roster.preview(conn, rows, "x.xlsx")
    roster.commit(conn, p["run_id"])
    with pytest.raises(ValueError, match="already committed"):
        roster.commit(conn, p["run_id"])


# --- §9 rule 32 ------------------------------------------------------------

def test_commit_is_audited(conn, rows):
    p = roster.preview(conn, rows, "x.xlsx")
    roster.commit(conn, p["run_id"], actor="Maximus")
    row = conn.execute(
        "SELECT * FROM audit_log WHERE action='Roster committed'").fetchone()
    assert row is not None and row["actor_name"] == "Maximus"


# --- Regression: the organiser signing up through Paperform (17 Sep) --------
#
# The owner override row was hidden from the preview's match map, so when the
# organiser filled in their own Paperform, preview planned them as "new" and
# commit hit the UNIQUE index on attendees.handle. The import rolled back and
# the console reported it as "Can't reach The Yard".

def test_owner_signing_up_matches_instead_of_duplicating(conn, rows):
    """The owner row is matched on username, not planned as a new person."""
    conn.execute(
        "INSERT INTO attendees (name, handle, handle_raw, source, status, payment_status, "
        "pass_code, tg_user_id, created_at, updated_at) "
        "VALUES ('Max', ?, ?, 'owner', 'active', 'missing', 'OWNER1', 5904397555, ?, ?)",
        (rows[0]["handle"], rows[0]["handle_raw"], db.utcnow(), db.utcnow()))
    p = roster.preview(conn, rows, "signed-up.xlsx")
    assert p["problems"] == []
    assert not any(x["action"] == "new" and x["row"]["handle"] == rows[0]["handle"]
                   for x in _plan(conn, p))
    roster.commit(conn, p["run_id"])
    held = conn.execute("SELECT source, status, tg_user_id FROM attendees WHERE handle=?",
                        (rows[0]["handle"],)).fetchall()
    assert len(held) == 1                      # one row, not two
    assert held[0]["source"] == "owner"        # still the override
    assert held[0]["tg_user_id"] == 5904397555  # still linked


def test_owner_absent_from_the_file_is_not_deactivated(conn, rows):
    """Rule 12 sweeps imported people only. The override is never in the export."""
    conn.execute(
        "INSERT INTO attendees (name, handle, handle_raw, source, status, payment_status, "
        "pass_code, created_at, updated_at) "
        "VALUES ('Max', 'maxi_muslim', '@maxi_muslim', 'owner', 'active', 'missing', "
        "'OWNER1', ?, ?)", (db.utcnow(), db.utcnow()))
    p = roster.preview(conn, rows, "x.xlsx")
    assert "maxi_muslim" not in [m["handle"] for m in p["missing"]]
    roster.commit(conn, p["run_id"])
    assert conn.execute("SELECT status FROM attendees WHERE handle='maxi_muslim'"
                        ).fetchone()["status"] == "active"


def test_a_walk_in_is_not_deactivated_by_a_later_import(conn, rows):
    """A walk-in added at the door is never in a Paperform export. Sweeping
    them would take their pass down mid-event."""
    p = roster.preview(conn, rows, "x.xlsx")
    roster.commit(conn, p["run_id"])
    conn.execute(
        "INSERT INTO attendees (name, handle, handle_raw, source, status, payment_status, "
        "pass_code, created_at, updated_at) "
        "VALUES ('Door Guest', 'doorguest1', '@doorguest1', 'walk_in', 'active', "
        "'verified', 'WALK01', ?, ?)", (db.utcnow(), db.utcnow()))
    p2 = roster.preview(conn, rows, "again.xlsx")
    assert "doorguest1" not in [m["handle"] for m in p2["missing"]]
    roster.commit(conn, p2["run_id"])
    assert conn.execute("SELECT status FROM attendees WHERE handle='doorguest1'"
                        ).fetchone()["status"] == "active"


def test_commit_names_a_clash_created_after_the_preview(conn, rows):
    """Preview at 10:00, walk-in added at 10:05, commit at 10:10: the plan is
    stale. Say whose name clashes instead of raising a bare SQLite error."""
    p = roster.preview(conn, rows, "x.xlsx")
    conn.execute(
        "INSERT INTO attendees (name, handle, handle_raw, source, status, payment_status, "
        "pass_code, created_at, updated_at) "
        "VALUES ('Door Guest', ?, ?, 'walk_in', 'active', 'verified', 'WALK01', ?, ?)",
        (rows[0]["handle"], rows[0]["handle_raw"], db.utcnow(), db.utcnow()))
    with pytest.raises(ValueError, match="already on the list as Door Guest"):
        roster.commit(conn, p["run_id"])
    # Rolled back: the walk-in is the only row with that handle.
    assert conn.execute("SELECT COUNT(*) c FROM attendees WHERE handle=?",
                        (rows[0]["handle"],)).fetchone()["c"] == 1


def _plan(conn, preview_out):
    import json as _json
    row = conn.execute("SELECT report FROM import_runs WHERE id=?",
                       (preview_out["run_id"],)).fetchone()
    return _json.loads(row["report"])["plan"]
