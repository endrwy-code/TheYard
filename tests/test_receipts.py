"""Receipt archiving and the duplicate warnings (§9 rules 29-31).

Nothing here touches the network: `archive()` takes its fetcher as an
argument precisely so these tests can hand it bytes.
"""

import io
import time
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

import config
import db
from conftest import EXPORT, TEST_NOW
from services import receipts, roster
from services.claims import ClaimError
from test_claims_concurrent import (  # noqa: F401 - fixtures are used by name
    Console, err, secrets_and_limits,
)


class _Before(datetime):
    """The receipts module's clock, pinned to conftest.TEST_NOW (17 Sep)."""

    @classmethod
    def now(cls, tz=None):
        return TEST_NOW if tz is None else TEST_NOW.astimezone(tz)


@pytest.fixture(autouse=True)
def before_the_links_expire(monkeypatch):
    """The real export's Paperform links expire 22-23 Sep, and `archive()`
    refuses a dead one, so on the real clock every test here started failing
    at 15:26 on 22 Sep. Pin it, the way conftest.TEST_NOW pins the API's
    (STATE.md decision 90). A test that wants a dead link builds one before
    TEST_NOW."""
    monkeypatch.setattr(receipts, "datetime", _Before)


def png(colour=0, size=(60, 40), noise=0):
    """A picture with structure in it, the way a real screenshot has.

    A flat colour has no internal contrast, so its difference hash is empty by
    design (see `receipts.dhash`) and it can never look like anything. Bank
    screenshots have rows of text and a logo, so these stand-ins get bands.
    `nudge` shifts the colours a shade without changing the shape: a re-saved
    copy of the same screenshot.
    """
    im = Image.new("RGB", size, (245, 245, 245))
    px = im.load()
    for y in range(size[1]):
        for x in range(size[0]):
            band = ((x * 3 + y * 7 + colour * 11) // 5) % 4
            px[x, y] = (30 + band * 55 + noise, 40 + band * 50, 60 + band * 45)
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def with_exif():
    """A JPEG carrying a comment, to prove the re-save strips metadata."""
    im = Image.open(io.BytesIO(png())).convert("RGB")
    out = io.BytesIO()
    im.save(out, format="JPEG", comment=b"taken at home, 1.35N 103.8E")
    return out.getvalue()


@pytest.fixture()
def people(conn):
    rows = roster.read_export(EXPORT)
    p = roster.preview(conn, rows, "x.xlsx")
    roster.commit(conn, p["run_id"])
    return conn


def ids_with_links(conn):
    return [r["id"] for r in conn.execute(
        "SELECT id FROM attendees WHERE paperform_receipt_url IS NOT NULL "
        "AND paperform_receipt_url != '' ORDER BY id")]


# --- taking the copy -------------------------------------------------------

def test_every_reachable_receipt_is_saved(people):
    """The real export has 17 sign-ups, 14 of them with a receipt link."""
    out = receipts.archive(people, "Max", fetch=lambda url: png())
    assert out["counts"]["saved"] == 14
    assert out["counts"]["failed"] == 0
    assert len(list(config.RECEIPTS_DIR.iterdir())) == 14


def test_a_second_run_changes_nothing(people):
    receipts.archive(people, "Max", fetch=lambda url: png())
    out = receipts.archive(people, "Max", fetch=lambda url: png())
    assert out["counts"]["saved"] == 0
    assert out["counts"]["skipped"] == 14


def test_one_dead_link_does_not_stop_the_rest(people):
    calls = {"n": 0}

    def flaky(url):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("403 Forbidden")
        return png()

    out = receipts.archive(people, "Max", fetch=flaky)
    assert out["counts"]["saved"] == 13
    assert out["counts"]["failed"] == 1
    assert "403" in out["failed"][0]["why"]


def test_an_expired_link_is_reported_not_fetched(people):
    """Paperform links carry `expires=`. Past it, do not even try."""
    dead = int((TEST_NOW - timedelta(days=1)).timestamp())
    first = ids_with_links(people)[0]
    people.execute("UPDATE attendees SET paperform_receipt_url=? WHERE id=?",
                   (f"https://paperform.example/r.png?expires={dead}", first))

    def refuse(url):
        raise AssertionError("an expired link must not be fetched")

    out = receipts.archive(people, "Max",
                           fetch=lambda url: refuse(url) if "expires" in url else png())
    assert any("expired" in f["why"] for f in out["failed"])


def test_a_file_that_is_not_an_image_is_refused(people):
    out = receipts.archive(people, "Max", fetch=lambda url: b"this is not a picture")
    assert out["counts"]["saved"] == 0
    assert out["counts"]["failed"] == 14
    assert "readable image" in out["failed"][0]["why"]


def test_hidden_metadata_is_stripped(people):
    """§9 r29 — the bytes we keep carry no EXIF from the attendee's phone."""
    receipts.archive(people, "Max", fetch=lambda url: with_exif())
    row = receipts.archived_row(people, ids_with_links(people)[0])
    kept = (config.RECEIPTS_DIR / row["file_name"]).read_bytes()
    assert b"1.35N" not in kept
    with Image.open(io.BytesIO(kept)) as im:
        assert not im.info.get("comment")


def test_the_name_on_disk_is_random(people):
    receipts.archive(people, "Max", fetch=lambda url: png())
    names = [p.name for p in config.RECEIPTS_DIR.iterdir()]
    # No attendee name, handle or id appears in any filename (§9 r31).
    for r in people.execute("SELECT id, name, handle FROM attendees"):
        assert not any(r["handle"] in n for n in names)
    assert all(len(n.split(".")[0]) == 32 for n in names)


def test_archiving_is_audited(people):
    receipts.archive(people, "Maximus", fetch=lambda url: png())
    row = people.execute(
        "SELECT * FROM audit_log WHERE action='Receipt copies saved'").fetchone()
    assert row is not None and row["actor_name"] == "Maximus"


# --- the two warning layers (§9 r30) ---------------------------------------

def test_the_same_screenshot_twice_is_an_exact_duplicate(people):
    ids = ids_with_links(people)[:2]
    receipts.archive(people, "Max", fetch=lambda url: png(), only_id=ids[0])
    receipts.archive(people, "Max", fetch=lambda url: png(), only_id=ids[1])
    out = receipts.duplicates_for(people, ids[0])
    assert [d["id"] for d in out["exact"]] == [ids[1]]


def test_a_re_saved_screenshot_is_a_look_alike_not_an_exact_match(people):
    """One pixel differs, so the bytes differ, but the picture is the same."""
    ids = ids_with_links(people)[:2]
    receipts.archive(people, "Max", fetch=lambda url: png(), only_id=ids[0])
    receipts.archive(people, "Max", fetch=lambda url: png(noise=4), only_id=ids[1])
    out = receipts.duplicates_for(people, ids[0])
    assert out["exact"] == []
    assert [d["id"] for d in out["similar"]] == [ids[1]]


def test_two_different_screenshots_are_not_flagged(people):
    ids = ids_with_links(people)[:2]
    receipts.archive(people, "Max", fetch=lambda url: png(colour=1), only_id=ids[0])
    receipts.archive(people, "Max",
                     fetch=lambda url: png(colour=9, size=(80, 20)), only_id=ids[1])
    out = receipts.duplicates_for(people, ids[0])
    assert out["exact"] == [] and out["similar"] == []


def test_a_blank_image_never_looks_like_anything(people):
    """A flat picture has no structure to compare, so it must not be matched
    against every other flat picture on the list."""
    blank = Image.new("RGB", (50, 50), (255, 255, 255))
    buf = io.BytesIO(); blank.save(buf, format="PNG")
    ids = ids_with_links(people)[:2]
    for i in ids:
        receipts.archive(people, "Max", fetch=lambda url: buf.getvalue(), only_id=i)
    out = receipts.duplicates_for(people, ids[0])
    assert out["similar"] == []
    # The bytes are identical, though, so the exact layer still catches it.
    assert [d["id"] for d in out["exact"]] == [ids[1]]


def test_a_warning_never_changes_a_payment(people):
    """§9 r30 — the layers warn; the admin decides. Nothing is auto-rejected."""
    ids = ids_with_links(people)[:2]
    receipts.archive(people, "Max", fetch=lambda url: png(), only_id=ids[0])
    receipts.archive(people, "Max", fetch=lambda url: png(), only_id=ids[1])
    for i in ids:
        assert people.execute("SELECT payment_status FROM attendees WHERE id=?",
                              (i,)).fetchone()[0] == "submitted"


# --- what the person page and the console show -----------------------------

def test_the_person_page_prefers_our_copy_over_the_link(people):
    from services import people as people_svc
    pid = ids_with_links(people)[0]
    before = people_svc.person(people, pid, "admin")["receipt"]
    assert before["saved"] is False and before["source"].startswith("Paperform")

    receipts.archive(people, "Max", fetch=lambda url: png(), only_id=pid)
    after = people_svc.person(people, pid, "admin")["receipt"]
    assert after["saved"] is True
    assert after["url"] == f"/admin/api/receipts/{pid}/file"
    assert after["expired"] is False


def test_an_expired_link_with_a_saved_copy_still_shows(people):
    """The whole point: after 22 Sep the link is dead and the copy is not."""
    from services import people as people_svc
    pid = ids_with_links(people)[0]
    receipts.archive(people, "Max", fetch=lambda url: png(), only_id=pid)
    dead = int((TEST_NOW - timedelta(days=1)).timestamp())
    people.execute("UPDATE attendees SET paperform_receipt_url=? WHERE id=?",
                   (f"https://paperform.example/r.png?expires={dead}", pid))
    view = people_svc.person(people, pid, "admin")["receipt"]
    assert view["saved"] is True and view["expired"] is False and view["url"]


def test_staff_never_see_a_receipt_or_a_duplicate_warning(people):
    from services import people as people_svc
    pid = ids_with_links(people)[0]
    receipts.archive(people, "Max", fetch=lambda url: png(), only_id=pid)
    view = people_svc.person(people, pid, "staff")
    assert view["receipt"]["url"] is None and view["receipt"]["link"] is None
    assert view["duplicates"] == {"exact": [], "similar": []}


def test_status_counts_what_is_left_and_when_it_dies(people):
    s = receipts.status(people)
    assert s["with_links"] == 14 and s["saved"] == 0 and s["not_saved"] == 14
    assert s["next_expiry"]                       # the real export's soonest link
    receipts.archive(people, "Max", fetch=lambda url: png())
    s2 = receipts.status(people)
    assert s2["saved"] == 14 and s2["not_saved"] == 0 and s2["next_expiry"] is None


# --- serving the file (§9 r31) ---------------------------------------------

def test_only_an_admin_can_open_a_saved_receipt(people, secrets_and_limits):
    pid = ids_with_links(people)[0]
    receipts.archive(people, "Max", fetch=lambda url: png(), only_id=pid)
    assert Console("admin").get(f"/admin/api/receipts/{pid}/file").status_code == 200
    for role in ("staff", "gm"):
        r = Console(role).get(f"/admin/api/receipts/{pid}/file")
        assert r.status_code == 403, role
        assert err(r)["code"] == "FORBIDDEN"


def test_a_signed_out_browser_cannot_open_one(people, secrets_and_limits):
    import app as webapp
    pid = ids_with_links(people)[0]
    receipts.archive(people, "Max", fetch=lambda url: png(), only_id=pid)
    r = webapp.app.test_client().get(f"/admin/api/receipts/{pid}/file")
    assert r.status_code == 401


def test_asking_for_a_receipt_we_never_saved_says_so(people, secrets_and_limits):
    pid = ids_with_links(people)[0]
    r = Console("admin").get(f"/admin/api/receipts/{pid}/file")
    assert r.status_code == 404 and err(r)["code"] == "NOT_FOUND"


def test_a_saved_receipt_is_never_cached(people, secrets_and_limits):
    pid = ids_with_links(people)[0]
    receipts.archive(people, "Max", fetch=lambda url: png(), only_id=pid)
    r = Console("admin").get(f"/admin/api/receipts/{pid}/file")
    assert "no-store" in r.headers.get("Cache-Control", "")
