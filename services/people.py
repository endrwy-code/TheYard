"""P0.3 — admin search, the person page, entrance payments, voids, the
gate-denial list (§9 rules 14, 26, 30-33).

Payment verdicts are admin-only (§9 r14). The transaction reference is
stored on the person's entrance `receipts` row, and the partial unique index
`receipts_txn` refuses a reference that already proved another payment — the
layer that makes each payment count once (§9 r30). As with claims, there is no
"already used?" check before the write; the index decides.
"""

import json
import re
import sqlite3
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import config
import db
from auth import normalise_handle
from services import bookings, claims, notify, receipts
from services.claims import ClaimError

SEARCH_LIMIT = 50
AUDIT_LIMIT = 25
VERDICTS = ("verified", "rejected", "reopen")
PAYMENT_ACTIONS = ("Payment verified", "Payment rejected", "Payment reopened")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic")


def _like(s):
    return "%" + s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _day_clock(utc_iso):
    """'17 Sep · 7:14 PM' in the event timezone."""
    d = datetime.fromisoformat(utc_iso).astimezone(config.TIMEZONE)
    return f"{d.day} {d.strftime('%b')} · {claims.clock(utc_iso)}"


def get_attendee(conn, attendee_id):
    row = conn.execute("SELECT * FROM attendees WHERE id = ?", (attendee_id,)).fetchone()
    if row is None:
        raise ClaimError("NOT_FOUND", "Nobody with that id.")
    return row


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

PAY_TAG = {"verified": "verified", "submitted": "pending",
           "rejected": "rejected", "missing": "no receipt"}


def list_tag(row):
    parts = [PAY_TAG.get(row["payment_status"], row["payment_status"])]
    if row["status"] != "active":
        parts.insert(0, "inactive")
    if row["is_test"]:
        parts.insert(0, "owner · test")
    if row["tg_user_id"] is None:
        parts.append("never opened")
    return " · ".join(parts)


def search(conn, q):
    """Name, username, email, pass code or booking ref. Empty q lists everyone."""
    q = " ".join(str(q or "").split())[:80]
    where, args = "1=1", []
    if q:
        terms = ["name LIKE ? ESCAPE '\\'", "email LIKE ? ESCAPE '\\'"]
        args = [_like(q), _like(q)]
        handle = normalise_handle(q)
        if handle:
            terms.append("handle LIKE ? ESCAPE '\\'")
            args.append(_like(handle))
        try:
            code = claims.parse_code(q)
        except ClaimError:
            code = None
        if code:
            terms.append("pass_code = ?")
            args.append(code)
        ref = q.upper()
        terms.append("id IN (SELECT attendee_id FROM escape_bookings WHERE ref_code = ?)")
        terms.append("id IN (SELECT attendee_id FROM jam_bookings WHERE ref_code = ?)")
        args += [ref, ref]
        where = "(" + " OR ".join(terms) + ")"
    total = conn.execute(f"SELECT COUNT(*) FROM attendees WHERE {where}", args).fetchone()[0]  # noqa: S608
    rows = conn.execute(
        f"SELECT * FROM attendees WHERE {where} "  # noqa: S608 - fixed fragments, values bound
        "ORDER BY status = 'active' DESC, name COLLATE NOCASE LIMIT ?",
        args + [SEARCH_LIMIT],
    ).fetchall()
    return {
        "query": q,
        "total": total,
        "shown": len(rows),
        "people": [{"id": r["id"], "name": r["name"], "handle": r["handle"],
                    "tag": list_tag(r)} for r in rows],
    }


# ---------------------------------------------------------------------------
# The person page
# ---------------------------------------------------------------------------

def link_expires_at(url):
    """Paperform receipt links are signed and carry `expires=<unix time>`."""
    try:
        raw = parse_qs(urlparse(url).query).get("expires", [None])[0]
        return datetime.fromtimestamp(int(raw), timezone.utc) if raw else None
    except (TypeError, ValueError, OSError):
        return None


def entrance_receipt(conn, attendee_id):
    """The row that carries this person's transaction reference, if any."""
    return conn.execute(
        "SELECT * FROM receipts WHERE attendee_id=? AND purpose='entrance' ORDER BY id DESC LIMIT 1",
        (attendee_id,)).fetchone()


def receipt_view(conn, row, is_admin):
    """The payment screenshot. Admin-only (§9 r31).

    Our own saved copy is preferred over the Paperform link whenever we have
    one, because Paperform's links are signed to expire 7 days after the
    sign-up — every current one dies before the event. A saved copy is served
    from this laptop, so it keeps working on the day with no tunnel, no
    Paperform plan and no wifi.
    """
    url = row["paperform_receipt_url"]
    saved = receipts.archived_row(conn, row["id"]) if is_admin else None
    when = f" · {row['submitted_at_text'][:10]}" if row["submitted_at_text"] else ""
    if not url and saved is None:
        return {"source": "No receipt", "url": None, "link": None, "expired": False,
                "saved": False, "note": "They signed up without a screenshot."}
    expires = link_expires_at(url) if url else None
    expired = bool(expires and expires <= datetime.now(timezone.utc))
    if saved is not None:
        ours = f"/admin/api/receipts/{row['id']}/file"
        return {
            "source": "Saved copy" + when, "url": ours, "link": ours,
            "expired": False, "saved": True,
            "note": "Our own copy, taken while the Paperform link still worked. "
                    "The reference check below is what makes each payment count once.",
        }
    is_image = urlparse(url).path.lower().endswith(IMAGE_EXT)
    return {
        "source": "Paperform receipt" + when,
        "url": url if is_admin and is_image and not expired else None,
        "link": url if is_admin and not expired else None,
        "expired": expired,
        "saved": False,
        "note": ("The Paperform link has expired and no copy was saved in time. "
                 "Look in Paperform's dashboard, or try a fresh export and re-import.") if expired
        else "No copy saved yet — press Save receipt copies on the Audit screen "
             "before this link expires. The reference check below is what makes "
             "each payment count once.",
    }


def last_verdict(conn, attendee_id):
    r = conn.execute(
        "SELECT * FROM audit_log WHERE entity='attendee' AND entity_id=? "
        f"AND action IN ({','.join('?' * len(PAYMENT_ACTIONS))}) ORDER BY id DESC LIMIT 1",
        (str(attendee_id), *PAYMENT_ACTIONS),
    ).fetchone()
    if r is None:
        return None
    d = json.loads(r["details"] or "{}")
    return {"action": r["action"], "by": r["actor_name"], "at": claims.local_iso(r["at"]),
            "txn_ref": d.get("txn_ref"), "skip_reason": d.get("skip_reason"),
            "reason": d.get("reason")}


def _audit_line(r):
    d = json.loads(r["details"] or "{}")
    what = r["action"]
    if d.get("txn_ref"):
        what += f" — ref {d['txn_ref']}"
    if d.get("skip_reason"):
        what += f" — no reference: {d['skip_reason']}"
    if d.get("reason"):
        what += f" — {d['reason']}"
    who = " · ".join(x for x in (r["station"], r["actor_name"]) if x) or r["actor_type"]
    return {"at": _day_clock(r["at"]), "what": what, "who": who}


def audit_for(conn, row):
    # The owner entry is logged under its handle, everything else under the id.
    ids = [str(row["id"])] + ([row["handle"]] if row["handle"] else [])
    rows = conn.execute(
        f"SELECT * FROM audit_log WHERE entity='attendee' AND entity_id IN ({','.join('?' * len(ids))}) "
        "ORDER BY id DESC LIMIT ?", (*ids, AUDIT_LIMIT)).fetchall()
    return [_audit_line(r) for r in rows]


def person(conn, attendee_id, role):
    row = get_attendee(conn, attendee_id)
    is_admin = role == "admin"
    return {
        "id": row["id"], "name": row["name"], "handle": row["handle"],
        "tg_user_id": row["tg_user_id"], "tg_first_name": row["tg_first_name"],
        "paperform_id": row["paperform_id"] or "—",
        "status": row["status"], "is_test": bool(row["is_test"]), "source": row["source"],
        "pass_code": row["pass_code"],
        "pass_qr": claims.pass_qr_data_uri(row["pass_code"]) if row["pass_code"] else None,
        "payment_status": row["payment_status"],
        "payment_ok": claims.payment_ok(conn, row),
        # Whether anyone is meant to check payments at all (STATE.md 138).
        # With it off, the console shows the screenshot and drops the whole
        # verdict workflow — there is no step to do.
        "payment_required": db.get_setting(conn, "claim_requires", "verified") != "none",
        "payment": last_verdict(conn, row["id"]),
        "checked_in_at": claims.local_iso(row["checked_in_at"]),
        "checked_in_by": row["checked_in_by"],
        "items": claims.items_view(),
        "claims": claims.claims_for(conn, row["id"]),
        "bookings": bookings.person_bookings(conn, row["id"]),
        "receipt": receipt_view(conn, row, is_admin),
        # §9 r30, layers one and two. Warnings only, and admin-only: staff
        # never see another attendee's payment business.
        "duplicates": receipts.duplicates_for(conn, row["id"]) if is_admin
        else {"exact": [], "similar": []},
        "audit": audit_for(conn, row),
    }


# ---------------------------------------------------------------------------
# Payment verdicts (§9 rules 14 and 30)
# ---------------------------------------------------------------------------

def normalise_ref(raw):
    return re.sub(r"\s+", "", str(raw or "")).upper()[:64]


def _ref_owner(conn, ref):
    r = conn.execute(
        "SELECT a.handle, a.name FROM receipts r JOIN attendees a ON a.id = r.attendee_id "
        "WHERE r.txn_ref = ?", (ref,)).fetchone()
    if r is None:
        return None
    return ("@" + r["handle"] if r["handle"] else r["name"]) + "'s entrance payment"


def set_payment(conn, attendee_id, *, verdict, txn_ref=None, reason=None, by):
    """Verify, reject, or reopen one person's entrance payment."""
    if verdict not in VERDICTS:
        raise ClaimError("VALIDATION_FAILED", "Verdict must be verified, rejected or reopen.")
    row = get_attendee(conn, attendee_id)
    ref = normalise_ref(txn_ref)
    reason = " ".join(str(reason or "").split())[:300]
    current = row["payment_status"]

    if verdict in ("verified", "rejected") and current not in ("submitted", "missing"):
        raise ClaimError("VALIDATION_FAILED",
                         f"This payment is already {current}. Use Change verdict first.")
    if verdict == "reopen" and current not in ("verified", "rejected"):
        raise ClaimError("VALIDATION_FAILED", "There is no verdict to change.")
    if verdict == "verified":
        if ref and len(ref) < 4:
            raise ClaimError("VALIDATION_FAILED", "That reference is too short.")
        if not ref and not reason:
            raise ClaimError("VALIDATION_FAILED",
                             "Type the reference, or say why the screenshot has none.")
    elif not reason:
        raise ClaimError("VALIDATION_FAILED", "A reason is required.")

    rec = entrance_receipt(conn, row["id"])
    new = {"verified": "verified", "rejected": "rejected",
           "reopen": "submitted" if row["paperform_receipt_url"] else "missing"}[verdict]
    now = db.utcnow()
    details = {"verdict": verdict, "before": {"payment_status": current},
               "after": {"payment_status": new}}

    conn.execute("BEGIN IMMEDIATE")
    try:
        if verdict == "verified":
            skip = None if ref else reason
            details.update(txn_ref=ref or None, skip_reason=skip)
            if rec is None:
                conn.execute(
                    "INSERT INTO receipts (attendee_id, purpose, source, uploaded_at, txn_ref, "
                    "txn_ref_skip_reason) VALUES (?, 'entrance', ?, ?, ?, ?)",
                    (row["id"], "paperform" if row["paperform_receipt_url"] else "admin",
                     now, ref or None, skip))
            else:
                conn.execute("UPDATE receipts SET txn_ref=?, txn_ref_skip_reason=? WHERE id=?",
                             (ref or None, skip, rec["id"]))
        elif verdict == "reopen":
            old = rec["txn_ref"] if rec is not None else None
            details.update(reason=reason, released_txn_ref=old)
            # Changing the verdict frees the reference, so a mistyped one can be fixed.
            conn.execute("UPDATE receipts SET txn_ref=NULL, txn_ref_skip_reason=NULL "
                         "WHERE attendee_id=? AND purpose='entrance'", (row["id"],))
        else:
            details.update(reason=reason)

        cur = conn.execute(
            "UPDATE attendees SET payment_status=?, updated_at=? WHERE id=? AND payment_status=?",
            (new, now, row["id"], current))
        if cur.rowcount != 1:
            raise ClaimError("VALIDATION_FAILED",
                             "Someone else changed this payment just now. Reload and look again.")
        action = {"verified": "Payment verified", "rejected": "Payment rejected",
                  "reopen": "Payment reopened"}[verdict]
        db.audit(conn, "admin", action, actor_name=by, entity="attendee",
                 entity_id=row["id"], details=details)
        # Only the two verdicts change what the person does next. A reopen is
        # the admin's own business until they decide again.
        if verdict == "verified":
            notify.queue(conn, row["id"], "payment_verified", notify.text_payment_verified(),
                         go=notify.GO_FOOD)
        elif verdict == "rejected":
            notify.queue(conn, row["id"], "payment_rejected",
                         notify.text_payment_rejected(reason), go=notify.GO_HOME)
        conn.execute("COMMIT")
    except sqlite3.IntegrityError:
        conn.execute("ROLLBACK")
        first = _ref_owner(conn, ref)
        db.audit(conn, "admin", "Payment verify refused — reference already used", actor_name=by,
                 entity="attendee", entity_id=row["id"], details={"txn_ref": ref, "first": first})
        raise ClaimError("DUPLICATE_TXN_REF",
                         f"Reference {ref} already proved {first or 'another payment'}. "
                         "The database refuses it.", first=first)
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"payment_status": new, "payment": last_verdict(conn, row["id"])}


# ---------------------------------------------------------------------------
# Voids, gate denials
# ---------------------------------------------------------------------------

def void_claim(conn, claim_id, *, reason, by):
    c = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if c is None:
        raise ClaimError("NOT_FOUND", "No such claim.")
    if c["voided_at"]:
        raise ClaimError("VALIDATION_FAILED", "That claim is already voided.")
    return claims.void_claim(conn, attendee_id=c["attendee_id"], item=c["item"],
                             reason=reason, by=by)


def gate_denials(conn, limit=50):
    rows = conn.execute(
        "SELECT * FROM gate_attempts WHERE resolved_at IS NULL ORDER BY id DESC LIMIT ?",
        (limit,)).fetchall()
    return [{"id": r["id"], "at": _day_clock(r["at"]), "tg_username": r["tg_username"] or "",
             "tg_first_name": r["tg_first_name"] or "", "outcome": r["outcome"],
             "claimed_handle": r["claimed_handle"] or ""} for r in rows]
