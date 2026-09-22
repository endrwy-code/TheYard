"""Reading a sign-up file whose columns are not Paperform's — §9 r10-14.

`test_roster_import.py` covers the organiser's real export and only runs where
that file is. This covers the other half: a .csv, a renamed question, columns
in a different order, and the admin matching them up by hand.
"""

import csv

import openpyxl
import pytest

from services import admin as console
from services import roster
from services.claims import ClaimError

HEADERS = ["Submitted At", "Unique", "Name", "Telegram", "Email", "Submission Receipt"]
ROW = ["2026-09-18 10:04:11", "1789457183000", "Ada Lovelace", "@ada_lovelace",
       "ada@example.com", "https://paperform.co/r/abc"]


def write_csv(tmp_path, headers, rows, name="signups.csv", encoding="utf-8"):
    path = tmp_path / name
    with open(path, "w", newline="", encoding=encoding) as fh:
        w = csv.writer(fh)
        w.writerow(headers)
        w.writerows(rows)
    return path


def write_xlsx(tmp_path, headers, rows, sheet=roster.SHEET, name="signups.xlsx"):
    wb = openpyxl.Workbook()
    wb.active.title = sheet
    wb.active.append(headers)
    for r in rows:
        wb.active.append(r)
    path = tmp_path / name
    wb.save(path)
    return path


# ---------------------------------------------------------------------------
# Reading the table
# ---------------------------------------------------------------------------

def test_a_csv_reads_like_the_spreadsheet_does(tmp_path):
    rows = roster.read_export(write_csv(tmp_path, HEADERS, [ROW]))
    assert len(rows) == 1
    r = rows[0]
    assert r["name"] == "Ada Lovelace"
    assert r["handle"] == "ada_lovelace" and r["handle_raw"] == "@ada_lovelace"
    assert r["email"] == "ada@example.com"
    assert r["paperform_id"] == "1789457183000"
    assert r["receipt_url"] == "https://paperform.co/r/abc"


def test_a_csv_saved_by_excel_keeps_its_first_column(tmp_path):
    """Excel writes a BOM; without utf-8-sig it sticks to "Submitted At" and
    that column silently stops matching."""
    path = write_csv(tmp_path, HEADERS, [ROW], encoding="utf-8-sig")
    headers, _ = roster.read_table(path)
    assert headers[0] == "Submitted At"
    assert roster.read_export(path)[0]["name"] == "Ada Lovelace"


def test_blank_rows_are_skipped_in_a_csv_too(tmp_path):
    path = write_csv(tmp_path, HEADERS, [ROW, ["", "", "", "", "", ""], ROW])
    assert len(roster.read_export(path)) == 2


def test_rows_carry_the_line_number_the_admin_can_see(tmp_path):
    path = write_csv(tmp_path, HEADERS, [ROW, ROW])
    assert [r["row"] for r in roster.read_export(path)] == [2, 3]


def test_a_file_with_no_rows_at_all_is_not_a_crash(tmp_path):
    assert roster.read_export(write_csv(tmp_path, HEADERS, [])) == []


def test_an_xlsx_with_the_wrong_sheet_is_still_rejected(tmp_path):
    path = write_xlsx(tmp_path, HEADERS, [ROW], sheet="Sheet1")
    with pytest.raises(ValueError, match="Registrations"):
        roster.read_export(path)


# ---------------------------------------------------------------------------
# Guessing which column is which
# ---------------------------------------------------------------------------

def test_paperforms_own_names_are_matched_exactly():
    assert roster.guess_mapping(HEADERS) == {
        "submitted_at": "Submitted At", "paperform_id": "Unique", "name": "Name",
        "telegram": "Telegram", "email": "Email", "receipt": "Submission Receipt"}


def test_the_screenshot_question_is_recognised_by_its_own_title():
    m = roster.guess_mapping(["Name", "Telegram", "Upload a screenshot of the payment!"])
    assert m["receipt"] == "Upload a screenshot of the payment!"


def test_matching_ignores_case_spacing_and_punctuation():
    m = roster.guess_mapping(["full_name", "TELEGRAM HANDLE", "E-Mail"])
    assert (m["name"], m["telegram"], m["email"]) == ("full_name", "TELEGRAM HANDLE", "E-Mail")


def test_a_column_is_only_claimed_once():
    """"Handle" could be a Telegram username or nothing; it must not end up
    feeding two fields at the same time."""
    m = roster.guess_mapping(["Name", "Telegram", "handle"])
    assert m["telegram"] == "Telegram"
    assert list(m.values()).count("handle") == 0


def test_an_unrecognisable_column_is_left_unmatched():
    m = roster.guess_mapping(["Name", "Telegram", "Shoe size"])
    assert m["email"] is None and m["receipt"] is None


def test_column_order_does_not_matter(tmp_path):
    headers = list(reversed(HEADERS))
    path = write_csv(tmp_path, headers, [list(reversed(ROW))])
    assert roster.read_export(path)[0]["handle"] == "ada_lovelace"


# ---------------------------------------------------------------------------
# Matching them by hand
# ---------------------------------------------------------------------------

def test_a_file_nobody_can_guess_is_refused_by_name(tmp_path):
    path = write_csv(tmp_path, ["a", "b", "c"], [["x", "y", "z"]])
    with pytest.raises(ValueError) as exc:
        roster.read_export(path)
    assert "Name" in str(exc.value) and "Telegram" in str(exc.value)


def test_a_hand_made_mapping_reads_a_file_with_no_usable_headers(tmp_path):
    path = write_csv(tmp_path, ["a", "b", "c"], [["Ada Lovelace", "@ada_lovelace", "ada@x.co"]])
    rows = roster.read_export(path, {"name": "a", "telegram": "b", "email": "c",
                                     "submitted_at": None, "paperform_id": None,
                                     "receipt": None})
    assert rows[0]["name"] == "Ada Lovelace"
    assert rows[0]["handle"] == "ada_lovelace"
    assert rows[0]["email"] == "ada@x.co"
    assert rows[0]["receipt_url"] == ""      # not in the file, so not invented


def test_a_mapping_naming_a_column_that_is_not_there_just_leaves_it_empty(tmp_path):
    path = write_csv(tmp_path, ["a", "b"], [["Ada Lovelace", "@ada_lovelace"]])
    rows = roster.read_export(path, {"name": "a", "telegram": "b", "email": "nope",
                                     "submitted_at": None, "paperform_id": None,
                                     "receipt": None})
    assert rows[0]["email"] == ""


@pytest.mark.parametrize("mapping", [
    {"name": "a"},                                    # no Telegram column
    {"telegram": "b"},                                # no Name column
    {},
])
def test_a_mapping_without_a_name_or_a_username_is_refused(mapping):
    with pytest.raises(ValueError, match="nobody to add"):
        roster.check_mapping(mapping)


# ---------------------------------------------------------------------------
# Through the console
# ---------------------------------------------------------------------------

class Upload:
    """Stands in for the werkzeug FileStorage the route hands over."""

    def __init__(self, path):
        self.filename = path.name
        self._path = path

    def save(self, dest):
        dest.write_bytes(self._path.read_bytes())


def test_the_console_previews_a_csv_and_says_what_it_matched(conn, tmp_path):
    out = console.roster_preview(conn, Upload(write_csv(tmp_path, HEADERS, [ROW])), "Tester")
    assert out["counts"]["new"] == 1
    assert out["headers"] == HEADERS
    assert out["mapping"]["telegram"] == "Telegram"
    assert [f["key"] for f in out["fields"]] == list(roster.FIELDS)
    assert out["sample"][0]["name"] == "Ada Lovelace"


def test_the_console_refuses_a_format_it_cannot_read(conn, tmp_path):
    path = tmp_path / "signups.pdf"
    path.write_bytes(b"%PDF-1.4")
    with pytest.raises(ClaimError) as exc:
        console.roster_preview(conn, Upload(path), "Tester")
    assert ".xlsx or .csv" in exc.value.message


def test_a_file_nobody_can_guess_still_reaches_the_matching(conn, tmp_path):
    """The one file the matching exists for must not be bounced before it."""
    path = write_csv(tmp_path, ["who", "tg", "mail"],
                     [["Ada Lovelace", "@ada_lovelace", "ada@x.co"]])
    out = console.roster_preview(conn, Upload(path), "Tester")
    assert out["needs_mapping"] is True
    assert out["counts"] is None
    assert "Name" in out["message"] and "Telegram" in out["message"]
    assert out["headers"] == ["who", "tg", "mail"]
    # Each column carries its first real value, so the admin can tell them apart.
    assert out["examples"] == {"who": "Ada Lovelace", "tg": "@ada_lovelace", "mail": "ada@x.co"}

    done = console.roster_remap(conn, out["run_id"],
                                {"name": "who", "telegram": "tg", "email": "mail"}, "Tester")
    assert done["needs_mapping"] is False
    assert done["counts"]["new"] == 1
    roster.commit(conn, done["run_id"], actor="Tester")
    row = conn.execute("SELECT * FROM attendees WHERE handle='ada_lovelace'").fetchone()
    assert row["name"] == "Ada Lovelace" and row["email"] == "ada@x.co"


def test_an_empty_column_shows_no_example(conn, tmp_path):
    path = write_csv(tmp_path, ["Name", "Telegram", "Nothing"],
                     [["Ada Lovelace", "@ada_lovelace", ""]])
    out = console.roster_preview(conn, Upload(path), "Tester")
    assert "Nothing" not in out["examples"]


def test_a_guessable_file_can_still_be_rematched(conn, tmp_path):
    path = write_csv(tmp_path, HEADERS + ["Nickname"], [ROW + ["Countess"]])
    first = console.roster_preview(conn, Upload(path), "Tester")
    assert first["mapping"]["name"] == "Name"
    again = console.roster_remap(conn, first["run_id"],
                                 dict(first["mapping"], name="Nickname"), "Tester")
    assert again["mapping"]["name"] == "Nickname"
    assert again["sample"][0]["name"] == "Countess"
    assert again["run_id"] != first["run_id"]      # a new run, the old one untouched


def test_rematching_a_committed_import_is_refused(conn, tmp_path):
    out = console.roster_preview(conn, Upload(write_csv(tmp_path, HEADERS, [ROW])), "Tester")
    roster.commit(conn, out["run_id"], actor="Tester")
    with pytest.raises(ClaimError) as exc:
        console.roster_remap(conn, out["run_id"], out["mapping"], "Tester")
    assert "already committed" in exc.value.message


def test_a_thin_file_matches_the_same_person_and_keeps_what_it_does_not_carry(conn, tmp_path):
    """The trap in hand-matching: a two-column .csv must not blank the email
    and the payment screenshot of everybody it touches."""
    full = write_csv(tmp_path, HEADERS, [ROW], name="full.csv")
    first = console.roster_preview(conn, Upload(full), "Tester")
    roster.commit(conn, first["run_id"], actor="Tester")

    thin = write_csv(tmp_path, ["who", "tg"], [["Ada, Countess", "@ada_lovelace"]], name="thin.csv")
    second = console.roster_preview(conn, Upload(thin), "Tester",
                                    mapping={"name": "who", "telegram": "tg"})
    assert second["counts"]["new"] == 0           # matched on username, not a new person
    assert second["counts"]["changed"] == 1       # the name really did change
    roster.commit(conn, second["run_id"], actor="Tester")

    row = conn.execute("SELECT * FROM attendees WHERE handle='ada_lovelace'").fetchone()
    assert row["name"] == "Ada, Countess"                      # what the file said
    assert row["email"] == "ada@example.com"                   # what it never mentioned
    assert row["paperform_receipt_url"] == "https://paperform.co/r/abc"
    assert row["payment_status"] == "submitted"
