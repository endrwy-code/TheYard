"""Paperform's webhook — one sign-up, applied as it is submitted (§9 r10-14).

`roster.py` is the bulk path: a whole export, previewed, then committed, with
anyone missing from the file swept inactive (rule 12). A webhook is the
opposite shape — one submission, already final, arriving at any moment — so it
applies straight away and never sweeps. One person's sign-up says nothing
about everybody else, and sweeping on it would deactivate the whole list.

It has to be idempotent. Paperform retries anything that is not a 2xx, and the
organiser may still import the same sign-ups from an export afterwards, so the
same submission arriving twice must be a no-op rather than a second person
holding a second pass. Matching is rule 11's: the Paperform ID first, then the
username.

A row that arrives here is a Paperform sign-up like any other, so it is stored
with source 'import' rather than a source of its own. That is deliberate: the
next export will contain it, and rule 12 should then treat it exactly as if it
had come from the file.

The form sends the six fields the export has columns for: Submitted At,
Unique, Name, Telegram, Email, Submission Receipt.
"""

import db
from auth import looks_like_handle, normalise_handle
from services.roster import EMAIL_RE, _paperform_id, _text


class WebhookError(ValueError):
    """A payload that will never work, however many times it is sent.

    Kept apart from a database error on purpose: this one is answered with a
    2xx and an audit row, because Paperform retries a failure and retrying a
    sign-up with no Telegram username never turns into a sign-up with one.
    """


# What the form calls each field, and what else to accept if a field is ever
# renamed. Matching ignores case, spaces, underscores and punctuation, so
# "Submitted At", "submitted_at" and "submittedAt" are all the same key.
FIELDS = {
    "submitted_at": ("Submitted At", "submitted", "created at"),
    "paperform_id": ("Unique", "submission id", "id"),
    "name": ("Name", "full name"),
    "telegram": ("Telegram", "telegram username", "telegram handle", "username"),
    "email": ("Email", "email address"),
    "receipt_url": ("Submission Receipt", "receipt", "submission receipt url"),
}


def _key(label):
    return "".join(ch for ch in str(label or "").lower() if ch.isalnum())


def _scalar(value):
    """Paperform sends a plain value for a text field and a one-item list for
    some others. Anything deeper than that is not one of our six fields."""
    if isinstance(value, list):
        return value[0] if len(value) == 1 and not isinstance(value[0], (dict, list)) else None
    return None if isinstance(value, dict) else value


def _flatten(payload):
    """Every label/value pair in the body, whatever shape Paperform sends.

    Their webhook is not one fixed format — the built-in integration and a
    custom one differ, and `data` has been both a list of fields and an object
    keyed by field id. Rather than bet on one, collect labels and values from
    all of them and let FIELDS decide which ones matter. `data` is read first
    so a form field always beats a top-level key of the same name.
    """
    pairs = {}

    def put(label, value):
        key = _key(label)
        value = _scalar(value)
        if key and value is not None and key not in pairs:
            pairs[key] = value

    data = payload.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                put(item.get("title") or item.get("label") or item.get("key"), item.get("value"))
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                put(value.get("title") or value.get("label") or key, value.get("value"))
            else:
                put(key, value)
    for key, value in payload.items():
        if key != "data":
            put(key, value)
    return pairs


def _pick(pairs, field):
    for alias in FIELDS[field]:
        value = pairs.get(_key(alias))
        if value not in (None, ""):
            return value
    return None


def parse(payload):
    """A webhook body as one row, shaped exactly like `roster.read_export`."""
    if not isinstance(payload, dict):
        raise WebhookError("The webhook body must be a JSON object.")
    pairs = _flatten(payload)
    if not pairs:
        raise WebhookError("The webhook body had no fields in it.")
    handle_raw = _text(_pick(pairs, "telegram"))
    return {
        "row": 1,                       # roster.py counts rows; a webhook has one
        "submitted_at": _text(_pick(pairs, "submitted_at")),
        "paperform_id": _paperform_id(_pick(pairs, "paperform_id")),
        "name": _text(_pick(pairs, "name")),
        "handle_raw": handle_raw,
        "handle": normalise_handle(handle_raw),
        "email": _text(_pick(pairs, "email")),
        "receipt_url": _text(_pick(pairs, "receipt_url")),
    }


def validate(row):
    """The same checks `roster.preview` runs per row, worded for one sign-up."""
    if not row["name"]:
        raise WebhookError("No name in this sign-up.")
    if not row["handle"]:
        raise WebhookError(f'No Telegram username for "{row["name"]}".')
    if not looks_like_handle(row["handle"]):
        raise WebhookError(f'"{row["handle_raw"]}" is not a Telegram username. '
                           "Expected 5-32 letters, digits or underscores.")
    if row["email"] and not EMAIL_RE.match(row["email"]):
        raise WebhookError(f'Invalid email "{row["email"]}" — fix it in Paperform.')


def apply(conn, row, actor="paperform"):
    """Insert or update the one sign-up in `row`. Idempotent: sending the same
    submission again reports 'unchanged' and writes nothing."""
    validate(row)
    now = db.utcnow()
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Rule 11 — the Paperform ID first, then the username.
        match = None
        if row["paperform_id"]:
            match = conn.execute("SELECT * FROM attendees WHERE paperform_id = ?",
                                 (row["paperform_id"],)).fetchone()
        if match is None:
            match = conn.execute("SELECT * FROM attendees WHERE handle = ?",
                                 (row["handle"],)).fetchone()

        if match is None:
            code = db.new_code(conn, "attendees", "pass_code")
            cur = conn.execute(
                "INSERT INTO attendees (paperform_id, name, email, handle, handle_raw, "
                "source, status, payment_status, paperform_receipt_url, submitted_at_text, "
                "pass_code, created_at, updated_at) "
                "VALUES (?,?,?,?,?,'import','active',?,?,?,?,?,?)",
                (row["paperform_id"] or None, row["name"], row["email"], row["handle"],
                 row["handle_raw"],
                 # Rule 14 — a receipt link means submitted, never verified.
                 "submitted" if row["receipt_url"] else "missing",
                 row["receipt_url"] or None, row["submitted_at"], code, now, now),
            )
            db.audit(conn, "system", "Sign-up from Paperform", actor_name=actor,
                     entity="attendee", entity_id=cur.lastrowid,
                     details={"handle": row["handle"], "action": "new"})
            conn.execute("COMMIT")
            return {"action": "new", "id": cur.lastrowid, "handle": row["handle"]}

        # Rule 11 again — a username that moved onto a sign-up somebody has
        # already opened the app with is an admin's problem, never a silent
        # overwrite that would take their pass off them.
        if match["handle"] != row["handle"] and match["tg_user_id"]:
            raise WebhookError(
                f'@{match["handle"]} changed to @{row["handle"]}, but that sign-up is '
                "already linked to a Telegram account. Unlink it in the console first.")
        # The Paperform ID matched one person and the username belongs to
        # another: the UPDATE below would break the unique index on handle and
        # roll back with a bare SQLite error. Name it instead.
        if match["handle"] != row["handle"]:
            other = conn.execute("SELECT name FROM attendees WHERE handle = ? AND id != ?",
                                 (row["handle"], match["id"])).fetchone()
            if other:
                raise WebhookError(
                    f'@{row["handle"]} is already on the list as {other["name"]}. '
                    "Sort the two sign-ups out in the console.")

        changes = {}
        if match["name"] != row["name"]:
            changes["name"] = [match["name"], row["name"]]
        if match["handle"] != row["handle"]:
            changes["handle"] = [match["handle"], row["handle"]]
        if (match["email"] or "") != row["email"]:
            changes["email"] = [match["email"], row["email"]]
        if (match["paperform_receipt_url"] or "") != row["receipt_url"]:
            changes["receipt"] = ["set" if row["receipt_url"] else "cleared"]
        if match["status"] != "active":
            changes["status"] = [match["status"], "active"]

        if not changes:
            conn.execute("COMMIT")
            return {"action": "unchanged", "id": match["id"], "handle": row["handle"]}

        conn.execute(
            "UPDATE attendees SET paperform_id=COALESCE(?, paperform_id), name=?, "
            "email=?, handle=?, handle_raw=?, paperform_receipt_url=?, "
            "submitted_at_text=?, status='active', updated_at=? WHERE id=?",
            (row["paperform_id"] or None, row["name"], row["email"], row["handle"],
             row["handle_raw"], row["receipt_url"] or None, row["submitted_at"],
             now, match["id"]),
        )
        # Rule 14 — only lift 'missing' to 'submitted', never talk back over a
        # verdict an admin already made at the front desk.
        conn.execute(
            "UPDATE attendees SET payment_status='submitted' "
            "WHERE id=? AND payment_status='missing' AND ? != ''",
            (match["id"], row["receipt_url"]),
        )
        db.audit(conn, "system", "Sign-up from Paperform", actor_name=actor,
                 entity="attendee", entity_id=match["id"],
                 details={"handle": row["handle"], "action": "changed", "changes": changes})
        conn.execute("COMMIT")
        return {"action": "changed", "id": match["id"], "handle": row["handle"],
                "changes": changes}
    except Exception:
        conn.execute("ROLLBACK")
        raise


def receive(conn, payload, actor="paperform"):
    """Parse and apply one webhook body, recording either way.

    A refusal is audited rather than raised past here, because the caller
    answers Paperform with a 2xx for it: nothing about resending a sign-up
    with no username makes it have one, and a retry loop would bury the real
    arrivals. The Roster screen counts both.
    """
    try:
        row = parse(payload)
        result = apply(conn, row, actor=actor)
    except WebhookError as exc:
        db.audit(conn, "system", "Paperform sign-up refused", actor_name=actor,
                 details={"problem": str(exc)})
        return {"refused": str(exc)}
    return result
