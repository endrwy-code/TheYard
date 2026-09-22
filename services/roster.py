"""Paperform roster import (§9 rules 10-14, §10).

Built against the real export: sheet "Registrations", 17 sign-ups followed by
~1,000 blank formatted rows, Paperform IDs stored as floats, handles all
prefixed with @, some names carrying trailing spaces, three rows with no
receipt link, and the last four columns empty because we fill them in.

Nothing is written until commit().
"""

import json
import re
from datetime import datetime

import openpyxl

import db
from auth import looks_like_handle, normalise_handle

SHEET = "Registrations"
COLUMNS = ["Submitted At", "Unique", "Name", "Telegram", "Email",
           "Submission Receipt", "Checked-in", "Checked in at",
           "Redeemed", "Redemmed At"]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# How each kind of row is described to an admin who hits a clash.
SOURCE_WORDS = {"import": "from an earlier import", "walk_in": "a walk-in",
                "owner": "the organiser's own account"}


def _text(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        # Timezone unknown, so this stays display-only text (rule 10).
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value).strip()


def _paperform_id(value):
    """Excel stores the Unique column as 1789457183000.0 — never a float (rule 10)."""
    if value is None:
        return ""
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return ""
        return str(int(value))
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def read_export(path):
    """Rows from the sheet, blank rows skipped, every text cell trimmed."""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    if SHEET not in wb.sheetnames:
        raise ValueError(
            f'This file has no "{SHEET}" sheet — it has {", ".join(wb.sheetnames)}. '
            "Export the Registrations sheet from Paperform."
        )
    ws = wb[SHEET]
    rows = []
    header = None
    for n, raw in enumerate(ws.iter_rows(values_only=True), start=1):
        if all(c is None or str(c).strip() == "" for c in raw):
            continue                                   # rule 10: skip blank rows
        if header is None:
            header = [_text(c) for c in raw]
            continue
        cell = {header[i]: raw[i] for i in range(min(len(header), len(raw)))}
        rows.append({
            "row": n,
            "submitted_at": _text(cell.get("Submitted At")),
            "paperform_id": _paperform_id(cell.get("Unique")),
            "name": _text(cell.get("Name")),
            "handle_raw": _text(cell.get("Telegram")),
            "handle": normalise_handle(cell.get("Telegram")),
            "email": _text(cell.get("Email")),
            "receipt_url": _text(cell.get("Submission Receipt")),
        })
    wb.close()
    return rows


def preview(conn, rows, file_name):
    """Work out what committing would do. Writes only the import_runs row."""
    problems = []
    seen_handles = {}
    plan = []

    # Rule 11 — match against *everyone*, including the owner override and
    # walk-ins. Leaving them out used to hide a real clash: when the organiser
    # signed up through Paperform, their owner row was invisible here, the row
    # was planned as "new", and the INSERT hit the UNIQUE index on handle. The
    # preview promised a commit the database would always refuse.
    existing_by_pid = {}
    existing_by_handle = {}
    for r in conn.execute("SELECT * FROM attendees"):
        if r["paperform_id"]:
            existing_by_pid[r["paperform_id"]] = r
        if r["handle"]:
            existing_by_handle[r["handle"]] = r

    for r in rows:
        if not r["name"]:
            problems.append({"row": r["row"], "message": "No name in this row."})
            continue
        if not r["handle"]:
            problems.append({"row": r["row"],
                             "message": f'No Telegram username for "{r["name"]}".'})
            continue
        if not looks_like_handle(r["handle"]):
            problems.append({"row": r["row"],
                             "message": f'"{r["handle_raw"]}" is not a Telegram username. '
                                        "Expected 5-32 letters, digits or underscores."})
            continue
        if r["handle"] in seen_handles:
            problems.append({"row": r["row"],
                             "message": f'Duplicate username @{r["handle"]} — also on row '
                                        f'{seen_handles[r["handle"]]}. Only one can be imported.'})
            continue
        seen_handles[r["handle"]] = r["row"]
        if r["email"] and not EMAIL_RE.match(r["email"]):
            problems.append({"row": r["row"],
                             "message": f'Invalid email "{r["email"]}" — fix it in Paperform.'})
            continue

        # Rule 11 — match on Paperform ID first, then on username.
        match = existing_by_pid.get(r["paperform_id"]) if r["paperform_id"] else None
        if match is None:
            match = existing_by_handle.get(r["handle"])

        if match is None:
            plan.append({"action": "new", "row": r})
            continue

        if (match["handle"] != r["handle"] and match["tg_user_id"]):
            problems.append({
                "row": r["row"],
                "message": f'@{match["handle"]} changed to @{r["handle"]}, but that sign-up is '
                           "already linked to a Telegram account. Unlink it first."})
            continue

        changes = {}
        if match["name"] != r["name"]:
            changes["name"] = [match["name"], r["name"]]
        if match["handle"] != r["handle"]:
            changes["handle"] = [match["handle"], r["handle"]]
        if (match["email"] or "") != r["email"]:
            changes["email"] = [match["email"], r["email"]]
        if (match["paperform_receipt_url"] or "") != r["receipt_url"]:
            changes["receipt"] = ["set" if r["receipt_url"] else "cleared"]
        if match["status"] != "active":
            changes["status"] = [match["status"], "active"]

        plan.append({"action": "changed" if changes else "unchanged",
                     "row": r, "id": match["id"], "changes": changes})

    # Rule 12 — anyone in the database but not in this file becomes inactive,
    # but only people who came *from* a Paperform file in the first place. A
    # walk-in added at the door and the owner override are never in the export,
    # so sweeping them would deactivate every walk-in the next time someone
    # re-imported mid-event, and take their pass down with it.
    in_file = {p["row"]["handle"] for p in plan}
    missing = []
    for handle, row in existing_by_handle.items():
        if handle not in in_file and row["status"] == "active" and row["source"] == "import":
            missing.append({"id": row["id"], "name": row["name"], "handle": handle,
                            "source": row["source"]})

    counts = {
        "new": sum(1 for p in plan if p["action"] == "new"),
        "changed": sum(1 for p in plan if p["action"] == "changed"),
        "unchanged": sum(1 for p in plan if p["action"] == "unchanged"),
        "missing": len(missing),
        "no_receipt": sum(1 for p in plan if not p["row"]["receipt_url"]),
    }
    report = {"plan": plan, "missing": missing, "problems": problems}

    cur = conn.execute(
        "INSERT INTO import_runs (at, source, file_name, counts, report) VALUES (?,?,?,?,?)",
        (db.utcnow(), "upload", file_name, json.dumps(counts), json.dumps(report)),
    )
    run_id = cur.lastrowid
    return {"run_id": run_id, "file_name": file_name, "counts": counts,
            "problems": problems, "missing": missing}


def commit(conn, run_id, actor="admin"):
    """Apply a preview. Idempotent: re-importing the same file changes nothing."""
    run = conn.execute("SELECT * FROM import_runs WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        raise ValueError(f"No import run {run_id}.")
    if run["committed_at"]:
        raise ValueError(f"Import run {run_id} was already committed.")
    report = json.loads(run["report"])
    if report["problems"]:
        raise ValueError("This file still has problems. Nothing was written.")

    now = db.utcnow()
    written = 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        for item in report["plan"]:
            r = item["row"]
            if item["action"] == "new":
                # The plan was worked out when the file was previewed. If someone
                # was added by hand in between (a walk-in at the door), that row
                # now exists and the INSERT below would fail the UNIQUE index on
                # handle, rolling back the whole import with a bare SQLite error.
                # Say so in words instead, and name the person.
                clash = conn.execute(
                    "SELECT name, source FROM attendees WHERE handle = ?", (r["handle"],)).fetchone()
                if clash:
                    raise ValueError(
                        f'@{r["handle"]} is already on the list as {clash["name"]} '
                        f'({SOURCE_WORDS.get(clash["source"], clash["source"])}). '
                        "Nothing was written. Preview the file again and commit that.")
                code = db.new_code(conn, "attendees", "pass_code")
                conn.execute(
                    "INSERT INTO attendees (paperform_id, name, email, handle, handle_raw, "
                    "source, status, payment_status, paperform_receipt_url, submitted_at_text, "
                    "pass_code, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,'import','active',?,?,?,?,?,?)",
                    (r["paperform_id"] or None, r["name"], r["email"], r["handle"],
                     r["handle_raw"],
                     # Rule 14 — a receipt link means submitted, never verified.
                     "submitted" if r["receipt_url"] else "missing",
                     r["receipt_url"] or None, r["submitted_at"], code, now, now),
                )
                written += 1
            elif item["action"] == "changed":
                conn.execute(
                    "UPDATE attendees SET paperform_id=COALESCE(?, paperform_id), name=?, "
                    "email=?, handle=?, handle_raw=?, paperform_receipt_url=?, "
                    "submitted_at_text=?, status='active', updated_at=? WHERE id=?",
                    (r["paperform_id"] or None, r["name"], r["email"], r["handle"],
                     r["handle_raw"], r["receipt_url"] or None, r["submitted_at"],
                     now, item["id"]),
                )
                # Rule 14 again — only lift 'missing' to 'submitted', never downgrade
                # a verdict an admin already made.
                conn.execute(
                    "UPDATE attendees SET payment_status='submitted' "
                    "WHERE id=? AND payment_status='missing' AND ? != ''",
                    (item["id"], r["receipt_url"]),
                )
                written += 1
                db.audit(conn, "admin", "Roster row updated", actor_name=actor,
                         entity="attendee", entity_id=item["id"],
                         details=item["changes"])

        for m in report["missing"]:
            # Rule 12 — inactive, never deleted. Bookings and claims stay.
            conn.execute("UPDATE attendees SET status='inactive', updated_at=? WHERE id=?",
                         (now, m["id"]))
            db.audit(conn, "admin", "Missing from import — marked inactive",
                     actor_name=actor, entity="attendee", entity_id=m["id"],
                     details={"handle": m["handle"]})

        conn.execute("UPDATE import_runs SET committed_at=? WHERE id=?", (now, run_id))
        db.audit(conn, "admin", "Roster committed", actor_name=actor,
                 entity="import_run", entity_id=run_id,
                 details=json.loads(run["counts"]))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return {"committed": written, "inactive": len(report["missing"])}
