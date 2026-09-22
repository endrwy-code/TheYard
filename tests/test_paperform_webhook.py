"""Paperform's webhook — §9 r10-14, the live half of the roster.

Nothing here touches the real export: a webhook carries one sign-up, and the
point of these tests is that one sign-up behaves exactly like one row of the
file, including the rules that stop it taking someone's pass away.
"""

import json

import pytest

import config
import db
from services import paperform


# The six fields the form sends, in Paperform's own list shape.
def body(name="Ada Lovelace", telegram="@ada_lovelace", email="ada@example.com",
         unique="1789457183000.0", submitted="2026-09-18 10:04:11",
         receipt="https://paperform.co/r/abc123"):
    fields = [("Submitted At", submitted), ("Unique", unique), ("Name", name),
              ("Telegram", telegram), ("Email", email), ("Submission Receipt", receipt)]
    return {"id": "sub_1", "form_id": "theyard",
            "data": [{"key": f"k{i}", "title": t, "value": v}
                     for i, (t, v) in enumerate(fields)]}


# The screenshot question, as the form actually titles it, in the shapes a
# file upload arrives in.
SHOT = "Upload a screenshot of the payment!"


def with_shot(value):
    payload = body(receipt="")
    payload["data"] = [f for f in payload["data"] if f["title"] != "Submission Receipt"]
    payload["data"].append({"key": "shot", "title": SHOT, "value": value})
    return payload


def post(client, payload, **kwargs):
    return client.post("/paperform/webhook", json=payload, **kwargs)


def one(conn, handle):
    return conn.execute("SELECT * FROM attendees WHERE handle = ?", (handle,)).fetchone()


# ---------------------------------------------------------------------------
# Reading whatever shape arrives
# ---------------------------------------------------------------------------

def test_the_six_fields_are_read_from_paperforms_list_shape():
    row = paperform.parse(body())
    assert row["name"] == "Ada Lovelace"
    assert row["handle"] == "ada_lovelace"          # the @ is dropped, case folded
    assert row["handle_raw"] == "@ada_lovelace"
    assert row["email"] == "ada@example.com"
    assert row["paperform_id"] == "1789457183000"   # never a float (rule 10)
    assert row["submitted_at"] == "2026-09-18 10:04:11"
    assert row["receipt_url"] == "https://paperform.co/r/abc123"


def test_an_object_keyed_by_field_id_reads_the_same():
    payload = {"data": {"abc": {"title": "Name", "value": "Ada Lovelace"},
                        "def": {"title": "Telegram", "value": "@ada_lovelace"},
                        "ghi": {"title": "Email", "value": "ada@example.com"}}}
    row = paperform.parse(payload)
    assert (row["name"], row["handle"], row["email"]) == \
           ("Ada Lovelace", "ada_lovelace", "ada@example.com")


def test_a_flat_object_reads_the_same():
    row = paperform.parse({"Name": "Ada Lovelace", "Telegram": "ada_lovelace",
                           "Email": "ada@example.com", "Unique": "42"})
    assert (row["name"], row["handle"], row["paperform_id"]) == ("Ada Lovelace", "ada_lovelace", "42")


def test_labels_match_however_they_are_punctuated():
    row = paperform.parse({"submitted_at": "x", "NAME": "Ada Lovelace",
                           "telegram": "ada_lovelace"})
    assert row["name"] == "Ada Lovelace" and row["submitted_at"] == "x"


def test_a_form_field_beats_a_top_level_key_of_the_same_name():
    payload = body(name="From the form")
    payload["Name"] = "From the envelope"
    assert paperform.parse(payload)["name"] == "From the form"


def test_a_body_that_is_not_an_object_is_refused():
    with pytest.raises(paperform.WebhookError):
        paperform.parse([1, 2, 3])


@pytest.mark.parametrize("value", [
    "https://paperform.co/r/shot.png",                              # a bare URL
    ["https://paperform.co/r/shot.png"],                            # a one-file list
    {"url": "https://paperform.co/r/shot.png", "name": "pay.png"},  # a file object
    [{"url": "https://paperform.co/r/shot.png"}],                   # a list of one
    {"value": "https://paperform.co/r/shot.png"},                   # nested once more
])
def test_the_payment_screenshot_survives_every_shape_it_arrives_in(value):
    """It is the one field that is a file, and losing it loses the proof."""
    assert paperform.parse(with_shot(value))["receipt_url"] == "https://paperform.co/r/shot.png"


def test_the_screenshot_decides_the_payment_status(conn):
    paperform.receive(conn, with_shot({"url": "https://paperform.co/r/shot.png"}))
    row = one(conn, "ada_lovelace")
    assert row["paperform_receipt_url"] == "https://paperform.co/r/shot.png"
    assert row["payment_status"] == "submitted"


def test_a_field_too_deep_to_read_is_dropped_rather_than_guessed():
    assert paperform.parse(with_shot({"meta": {"nested": "x"}}))["receipt_url"] == ""


# ---------------------------------------------------------------------------
# Writing the sign-up
# ---------------------------------------------------------------------------

def test_a_sign_up_lands_on_the_list_with_a_pass(conn):
    out = paperform.receive(conn, body())
    assert out["action"] == "new"
    row = one(conn, "ada_lovelace")
    assert row["name"] == "Ada Lovelace"
    assert row["source"] == "import"          # the next export will hold it too
    assert row["status"] == "active"
    assert row["pass_code"]                   # they can be looked up at the booth
    assert row["payment_status"] == "submitted"   # rule 14: a receipt, not a verdict


def test_no_receipt_means_the_payment_is_missing_not_submitted(conn):
    paperform.receive(conn, body(receipt=""))
    assert one(conn, "ada_lovelace")["payment_status"] == "missing"


def test_the_same_submission_twice_makes_one_person(conn):
    first = paperform.receive(conn, body())
    second = paperform.receive(conn, body())
    assert first["action"] == "new" and second["action"] == "unchanged"
    assert conn.execute("SELECT COUNT(*) FROM attendees").fetchone()[0] == 1


def test_the_pass_code_survives_a_resend(conn):
    paperform.receive(conn, body())
    code = one(conn, "ada_lovelace")["pass_code"]
    paperform.receive(conn, body())
    assert one(conn, "ada_lovelace")["pass_code"] == code


def test_an_edited_submission_updates_the_same_person(conn):
    paperform.receive(conn, body())
    out = paperform.receive(conn, body(name="Ada King"))
    assert out["action"] == "changed"
    assert one(conn, "ada_lovelace")["name"] == "Ada King"
    assert conn.execute("SELECT COUNT(*) FROM attendees").fetchone()[0] == 1


def test_a_changed_username_follows_the_paperform_id(conn):
    paperform.receive(conn, body())
    paperform.receive(conn, body(telegram="@ada_king"))
    assert one(conn, "ada_lovelace") is None
    assert one(conn, "ada_king")["name"] == "Ada Lovelace"


def test_a_verdict_an_admin_made_is_never_talked_back_over(conn):
    """Rule 14 — 'missing' may be lifted to 'submitted', never the reverse."""
    paperform.receive(conn, body())
    conn.execute("UPDATE attendees SET payment_status='verified' WHERE handle='ada_lovelace'")
    paperform.receive(conn, body(name="Ada King"))
    assert one(conn, "ada_lovelace")["payment_status"] == "verified"


def test_a_sign_up_that_came_back_is_made_active_again(conn):
    paperform.receive(conn, body())
    conn.execute("UPDATE attendees SET status='inactive' WHERE handle='ada_lovelace'")
    paperform.receive(conn, body())
    assert one(conn, "ada_lovelace")["status"] == "active"


# ---------------------------------------------------------------------------
# What it refuses
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("payload, says", [
    (body(name=""), "No name"),
    (body(telegram=""), "No Telegram username"),
    (body(telegram="@no"), "not a Telegram username"),
    (body(email="not-an-email"), "Invalid email"),
])
def test_a_row_that_could_never_work_is_refused_and_written_nowhere(conn, payload, says):
    out = paperform.receive(conn, payload)
    assert says in out["refused"]
    assert conn.execute("SELECT COUNT(*) FROM attendees").fetchone()[0] == 0


def test_a_refusal_leaves_a_trail(conn):
    paperform.receive(conn, body(telegram=""))
    row = conn.execute("SELECT * FROM audit_log WHERE action='Paperform sign-up refused'").fetchone()
    assert row is not None and "No Telegram username" in json.loads(row["details"])["problem"]


def test_it_will_not_take_a_pass_off_someone_already_in_the_app(conn):
    """Rule 11 — a username moving onto a linked sign-up is an admin's call."""
    paperform.receive(conn, body())
    conn.execute("UPDATE attendees SET tg_user_id=999 WHERE handle='ada_lovelace'")
    out = paperform.receive(conn, body(telegram="@ada_king"))
    assert "already linked to a Telegram account" in out["refused"]
    assert one(conn, "ada_lovelace")["tg_user_id"] == 999


def test_a_username_that_belongs_to_somebody_else_is_named_not_crashed(conn):
    paperform.receive(conn, body())
    paperform.receive(conn, body(name="Grace Hopper", telegram="@grace_hopper", unique="2"))
    out = paperform.receive(conn, body(telegram="@grace_hopper"))
    assert "already on the list as Grace Hopper" in out["refused"]
    assert one(conn, "ada_lovelace") is not None


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------

def test_the_endpoint_takes_a_sign_up_with_no_secret_and_no_sign_in(client, conn):
    r = post(client, body())
    assert r.status_code == 200 and r.get_json()["data"]["action"] == "new"
    assert one(conn, "ada_lovelace") is not None


def test_a_refused_sign_up_still_answers_2xx(client, conn):
    """Paperform retries anything else, and no retry adds a missing username."""
    r = post(client, body(telegram=""))
    assert r.status_code == 200
    assert "No Telegram username" in r.get_json()["data"]["refused"]


def test_the_switch_on_the_settings_screen_closes_it(client, conn):
    db.set_setting(conn, "paperform_webhook", False)
    r = post(client, body())
    assert r.status_code == 200 and "switched off" in r.get_json()["data"]["ignored"]
    assert conn.execute("SELECT COUNT(*) FROM attendees").fetchone()[0] == 0


def test_a_secret_is_enforced_only_once_one_is_set(client, conn, monkeypatch):
    monkeypatch.setattr(config, "PAPERFORM_WEBHOOK_SECRET", "s3cret")
    assert post(client, body()).status_code == 403
    r = post(client, body(), headers={"X-Paperform-Secret": "s3cret"})
    assert r.status_code == 200 and one(conn, "ada_lovelace") is not None


def test_an_oversized_payload_is_refused_before_it_is_parsed(client, conn):
    r = post(client, {"data": [{"title": "Name", "value": "x" * 70000}]})
    assert r.status_code == 413
    assert conn.execute("SELECT COUNT(*) FROM attendees").fetchone()[0] == 0


def test_the_roster_screen_counts_what_arrived_live(client, conn):
    from services import admin as console
    post(client, body())
    post(client, body(telegram=""))
    view = console.roster_view(conn)
    assert view["webhook"] == 1 and view["webhook_refused"] == 1
