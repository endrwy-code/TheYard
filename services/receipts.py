"""Receipt archiving and the duplicate checks (§9 rules 29-31).

Why this exists
---------------
The 17 sign-ups arrive from Paperform with their payment screenshot behind a
**signed link that expires exactly 7 days after that person submitted**. The
first of the current batch dies 22 Sep 15:26 and the last 23 Sep 17:42 — both
before the event on the 24th. After that the person page has nothing to show
an admin, and a payment that has not been verified by then cannot be verified
at all without going back to Paperform's own dashboard.

So we take our own copy while the links still work. Once a copy is on the
laptop it does not expire, it is served only to a signed-in admin (§9 r31),
and it survives the tunnel, Paperform's plan and the wifi.

Having local bytes also makes §9 rule 30's first two layers possible, which
were dropped when in-app uploads were removed:

* **Exact copy** — SHA-256 of the stored bytes. The same fingerprint against
  two people is one screenshot submitted twice.
* **Look-alike** — a difference hash, which survives re-saving, resizing and
  re-screenshotting. Payment screens from one bank genuinely look alike, so
  the threshold is strict and the result only ever *warns*.

Neither layer rejects anything. The transaction reference is still the layer
that proves a payment counts once (§9 r30, last bullet); these two put a
"look at this" in front of an admin, and the admin decides.
"""

import hashlib
import io
import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse

import config
import db
from services.claims import ClaimError

# `people` imports this module for the person page, so importing it back at
# module level would be a cycle. These two helpers are read inside functions
# instead, which runs long after both modules are loaded.

# How close two difference hashes may be before we call them look-alikes.
# Strict on purpose: bank screenshots share a layout, and a false "duplicate"
# next to someone's name is worse than a missed one, because an admin who
# stops trusting the warning stops reading it.
LOOKALIKE_DISTANCE = 6

MAX_BYTES = 10 * 1024 * 1024
FETCH_TIMEOUT = 20

# What a payment screenshot is allowed to be. Anything else is refused rather
# than stored, because we re-serve these bytes to a browser later.
IMAGE_TYPES = {"JPEG": ".jpg", "PNG": ".png", "GIF": ".gif", "WEBP": ".webp", "BMP": ".bmp"}
PDF_MAGIC = b"%PDF-"


# ---------------------------------------------------------------------------
# Fingerprints
# ---------------------------------------------------------------------------

def sha256_of(raw):
    return hashlib.sha256(raw).hexdigest()


def dhash(raw):
    """A 64-bit difference hash, as hex. None if the bytes are not an image.

    Rows of 9 greyscale pixels give 8 comparisons each: bit set when a pixel
    is brighter than the one to its right. It describes the *shape* of an
    image, so it survives the re-saving and rescaling a screenshot goes
    through on its way through a phone, a form and a download.
    """
    try:
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as im:
            small = im.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            px = small.tobytes()                   # 72 greyscale values, row by row
        bits = 0
        for row in range(8):
            for col in range(8):
                left = px[row * 9 + col]
                right = px[row * 9 + col + 1]
                bits = (bits << 1) | (1 if left > right else 0)
    except Exception:  # noqa: BLE001 - a PDF or a corrupt file simply has no dhash
        return None
    # An image with no internal contrast — a blank or solid-colour picture —
    # produces all zeros or all ones, and would then "look like" every other
    # blank image on the list. That is a false accusation against a real
    # attendee, so such an image is treated as having no usable fingerprint.
    if bits in (0, (1 << 64) - 1):
        return None
    return f"{bits:016x}"


def distance(a, b):
    """Hamming distance between two dhash strings, or None if either is missing."""
    if not a or not b:
        return None
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Taking the copy
# ---------------------------------------------------------------------------

def _default_fetch(url):
    """Download the bytes behind a Paperform link. Kept separate so tests can
    pass their own fetcher and never touch the network."""
    import requests
    with requests.get(url, timeout=FETCH_TIMEOUT, stream=True) as r:
        r.raise_for_status()
        declared = r.headers.get("Content-Length")
        if declared and int(declared) > MAX_BYTES:
            raise ValueError(f"The file is larger than {MAX_BYTES // 1024 // 1024} MB.")
        raw = b""
        for chunk in r.iter_content(64 * 1024):
            raw += chunk
            if len(raw) > MAX_BYTES:
                raise ValueError(f"The file is larger than {MAX_BYTES // 1024 // 1024} MB.")
        return raw


def _store(raw):
    """Check the bytes really are a screenshot, strip hidden metadata, and
    write them under a random name (§9 r29). Returns (file_name, bytes kept).

    The re-save is what strips EXIF — location, device, the lot — and it also
    guarantees the file we serve back is something Pillow could read, rather
    than whatever arrived claiming to be an image.
    """
    config.RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    if raw[:5] == PDF_MAGIC:
        name = f"{secrets.token_hex(16)}.pdf"
        (config.RECEIPTS_DIR / name).write_bytes(raw)
        return name, raw
    try:
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as im:
            fmt = (im.format or "").upper()
            if fmt not in IMAGE_TYPES:
                raise ValueError(f"{fmt or 'That file'} isn't an image we can store.")
            im.load()
            # A new image built from the pixels alone: EXIF, GPS, the device
            # name and any comment stay behind with the original (§9 r29).
            clean = Image.new(im.mode, im.size)
            clean.paste(im)
            out = io.BytesIO()
            clean.save(out, format="PNG" if fmt in ("GIF", "BMP", "WEBP") else fmt)
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 - a corrupt download is not a crash
        raise ValueError("That file isn't a readable image.") from exc
    kept = out.getvalue()
    name = f"{secrets.token_hex(16)}{'.png' if fmt in ('GIF', 'BMP', 'WEBP') else IMAGE_TYPES[fmt]}"
    (config.RECEIPTS_DIR / name).write_bytes(kept)
    return name, kept


def archived_row(conn, attendee_id):
    """This person's saved copy, if we have one and the file is still there."""
    row = conn.execute(
        "SELECT * FROM receipts WHERE attendee_id=? AND purpose='archive' "
        "ORDER BY id DESC LIMIT 1", (attendee_id,)).fetchone()
    if row is None or not row["file_name"]:
        return None
    if not (config.RECEIPTS_DIR / row["file_name"]).exists():
        return None
    return row


def archive(conn, by, fetch=None, only_id=None, redo=False):
    """Save a copy of every Paperform receipt we can still reach.

    Safe to run as often as you like: someone already archived is skipped
    unless `redo` is set. Every person is handled on their own, so one dead
    link cannot stop the rest — which matters, because the links die one by
    one over two days rather than all at once.
    """
    from services.people import link_expires_at

    fetch = fetch or _default_fetch
    sql = ("SELECT id, name, handle, paperform_receipt_url, submitted_at_text FROM attendees "
           "WHERE paperform_receipt_url IS NOT NULL AND paperform_receipt_url != ''")
    args = []
    if only_id:
        sql += " AND id = ?"
        args.append(int(only_id))
    people = conn.execute(sql + " ORDER BY id", args).fetchall()

    saved, skipped, failed = [], [], []
    now = db.utcnow()
    for p in people:
        if not redo and archived_row(conn, p["id"]):
            skipped.append({"handle": p["handle"], "why": "already saved"})
            continue
        expires = link_expires_at(p["paperform_receipt_url"])
        if expires and expires <= datetime.now(timezone.utc):
            failed.append({"handle": p["handle"], "name": p["name"],
                           "why": "the Paperform link expired before we copied it"})
            continue
        try:
            raw = fetch(p["paperform_receipt_url"])
            file_name, kept = _store(raw)
        except Exception as exc:  # noqa: BLE001 - report it against the person, carry on
            failed.append({"handle": p["handle"], "name": p["name"], "why": str(exc) or type(exc).__name__})
            continue
        conn.execute(
            "INSERT INTO receipts (attendee_id, purpose, file_name, sha256, phash, source, uploaded_at) "
            "VALUES (?, 'archive', ?, ?, ?, 'paperform', ?)",
            (p["id"], file_name, sha256_of(kept), dhash(kept), now))
        saved.append({"handle": p["handle"], "name": p["name"], "file": file_name})

    db.audit(conn, "admin", "Receipt copies saved", actor_name=by, entity="receipt",
             details={"saved": len(saved), "skipped": len(skipped), "failed": len(failed)})
    return {"saved": saved, "skipped": skipped, "failed": failed,
            "counts": {"saved": len(saved), "skipped": len(skipped), "failed": len(failed)}}


# ---------------------------------------------------------------------------
# The two warning layers (§9 r30)
# ---------------------------------------------------------------------------

def duplicates_for(conn, attendee_id):
    """Who else submitted this same screenshot, or one that looks like it.

    Warns only. The answer goes on the person page beside the payment buttons
    so that an admin sees it *before* they press Verify, not after.
    """
    mine = archived_row(conn, attendee_id)
    if mine is None:
        return {"exact": [], "similar": []}
    rows = conn.execute(
        "SELECT r.id, r.sha256, r.phash, r.attendee_id, a.name, a.handle, a.payment_status "
        "FROM receipts r JOIN attendees a ON a.id = r.attendee_id "
        "WHERE r.purpose='archive' AND r.attendee_id != ?", (attendee_id,)).fetchall()
    exact, similar = [], []
    for r in rows:
        if mine["sha256"] and r["sha256"] == mine["sha256"]:
            exact.append({"id": r["attendee_id"], "name": r["name"], "handle": r["handle"],
                          "payment_status": r["payment_status"]})
            continue
        d = distance(mine["phash"], r["phash"])
        if d is not None and d <= LOOKALIKE_DISTANCE:
            similar.append({"id": r["attendee_id"], "name": r["name"], "handle": r["handle"],
                            "payment_status": r["payment_status"], "distance": d})
    similar.sort(key=lambda x: x["distance"])
    return {"exact": exact, "similar": similar}


# ---------------------------------------------------------------------------
# What the console shows
# ---------------------------------------------------------------------------

def status(conn):
    """Numbers for the Audit screen's exports tab, and the warning that drives
    the organiser to press the button before 22 Sep."""
    from services.people import _day_clock, link_expires_at

    rows = conn.execute(
        "SELECT id, paperform_receipt_url FROM attendees "
        "WHERE paperform_receipt_url IS NOT NULL AND paperform_receipt_url != ''").fetchall()
    have = {r["attendee_id"] for r in conn.execute(
        "SELECT DISTINCT attendee_id FROM receipts WHERE purpose='archive'")}
    now = datetime.now(timezone.utc)
    soonest, expired, missing = None, 0, 0
    for r in rows:
        if r["id"] in have:
            continue
        missing += 1
        when = link_expires_at(r["paperform_receipt_url"])
        if when and when <= now:
            expired += 1
        elif when and (soonest is None or when < soonest):
            soonest = when
    return {
        "with_links": len(rows),
        "saved": len([r for r in rows if r["id"] in have]),
        "not_saved": missing,
        "already_expired": expired,
        # The deadline, in the organiser's own words and timezone: the moment
        # the first un-copied receipt becomes unreachable.
        "next_expiry": _day_clock(soonest.isoformat()) if soonest else None,
    }


def file_for(conn, attendee_id):
    """The path to serve, admin-only (§9 r31). Raises if there is no copy."""
    row = archived_row(conn, attendee_id)
    if row is None:
        raise ClaimError("NOT_FOUND", "There is no saved copy of that receipt.")
    return config.RECEIPTS_DIR / row["file_name"]
