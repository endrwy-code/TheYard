"""Matcha and panini: order at the counter, message when it's ready.

STATE.md decision 125. The order is placed when the pass is scanned, because
by the time the food is made the person has walked off; one tap then queues
the Telegram message. These are paid extras, not pass items, so an order is
never a claim.
"""

from datetime import datetime, timedelta, timezone

import pytest

import db
from services import notify, orders
from services.claims import ClaimError
from test_claims_concurrent import (  # noqa: F401 - fixtures are used by name
    Console, err, person, roster, secrets_and_limits,
)

NOW = datetime(2026, 9, 24, 11, 0, tzinfo=timezone.utc)
LOFT = {"role": "mobile", "name": "Wei", "station": "Loft"}


def sent_messages(conn, order_id):
    return conn.execute("SELECT * FROM notifications WHERE dedupe_key LIKE ?",
                        (f"order_ready:{order_id}:%",)).fetchall()


def test_an_order_from_a_scanned_pass_joins_the_waiting_list(roster):
    p = person(roster, "bananabelles")
    phone = Console("mobile", "Wei", "Loft")
    r = phone.post("/admin/api/orders", {"code": p["pass_code"], "item": "matcha"})
    o = r.get_json()["data"]
    assert r.status_code == 200 and o["status"] == "waiting" and o["label"] == "Matcha"
    assert o["person"]["id"] == p["id"] and o["station"] == "Loft" and o["ordered_by"] == "Wei"
    board = phone.get("/admin/api/orders").get_json()["data"]
    assert [x["id"] for x in board["open"]] == [o["id"]]
    audit = roster.execute("SELECT * FROM audit_log WHERE action='Matcha ordered'").fetchone()
    assert (audit["actor_type"], audit["actor_name"], audit["station"]) == ("mobile", "Wei", "Loft")


def test_an_order_is_not_a_claim_and_can_be_repeated(roster):
    p = person(roster, "bananabelles", payment="missing")      # paid at Loft, not at the door
    for _ in range(2):
        orders.place(roster, item="panini", actor=LOFT, attendee_id=p["id"])
    assert roster.execute("SELECT COUNT(*) FROM orders WHERE attendee_id=?", (p["id"],)).fetchone()[0] == 2
    assert roster.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0


def test_calling_queues_one_message_and_a_double_tap_sends_nothing_new(roster):
    p = person(roster, "bananabelles")
    o = orders.place(roster, item="matcha", actor=LOFT, attendee_id=p["id"])
    first = orders.call(roster, o["id"], LOFT, now=NOW)
    assert first["status"] == "called" and first["repeat"] is False
    msgs = sent_messages(roster, o["id"])
    assert len(msgs) == 1 and msgs[0]["attendee_id"] == p["id"]
    assert "your order is ready" in msgs[0]["text"] and "Matcha" in msgs[0]["text"]
    assert "please collect the following at Two Goose:" in msgs[0]["text"]
    # A slip of the thumb ten seconds later: no second message.
    again = orders.call(roster, o["id"], LOFT, now=NOW + timedelta(seconds=10))
    assert again["repeat"] is True and len(sent_messages(roster, o["id"])) == 1
    # Calling again after a couple of minutes is on purpose, and does send.
    later = orders.call(roster, o["id"], LOFT, now=NOW + timedelta(minutes=2))
    assert later["calls"] == 2 and len(sent_messages(roster, o["id"])) == 2


def test_the_pickup_place_comes_from_settings(roster):
    """Each item has its own stall since 22 Sep (STATE.md 132)."""
    db.set_setting(roster, "panini_pickup", "the Crib table", by="test")
    db.set_setting(roster, "matcha_pickup", "the green stall", by="test")
    p = person(roster, "bananabelles")
    o = orders.place(roster, item="panini", actor=LOFT, attendee_id=p["id"])
    orders.call(roster, o["id"], LOFT, now=NOW)
    text = sent_messages(roster, o["id"])[0]["text"]
    assert "Panini" in text and "at the Crib table:" in text and "green stall" not in text


def test_collected_and_cancelled_leave_the_list_and_cannot_be_called(roster):
    p = person(roster, "bananabelles")
    a = orders.place(roster, item="matcha", actor=LOFT, attendee_id=p["id"])
    b = orders.place(roster, item="panini", actor=LOFT, attendee_id=p["id"])
    orders.close(roster, a["id"], "collected", LOFT)
    orders.close(roster, b["id"], "cancelled", LOFT)
    board = orders.board(roster)
    assert board["open"] == [] and board["collected"] == {"matcha": 1}
    with pytest.raises(ClaimError) as exc:
        orders.call(roster, a["id"], LOFT, now=NOW)
    assert exc.value.code == "VALIDATION_FAILED"


def test_the_counter_is_told_what_happened_to_the_message(roster):
    p = person(roster, "bananabelles")
    o = orders.place(roster, item="matcha", actor=LOFT, attendee_id=p["id"])
    orders.call(roster, o["id"], LOFT, now=NOW)
    assert orders.board(roster)["open"][0]["message"] == "sending"

    # Test mode (the default until `notify on`): held back, and it says so.
    notify.deliver(roster, lambda *a, **k: None, now=NOW + timedelta(seconds=5))
    assert orders.board(roster)["open"][0]["message"] == "test_mode"
    assert orders.board(roster)["test_mode"] is True

    # Messages on, but they never opened The Yard: nobody to send it to.
    db.set_setting(roster, "notify_mode", "on", by="test")
    orders.call(roster, o["id"], LOFT, now=NOW + timedelta(minutes=2))
    notify.deliver(roster, lambda *a, **k: None, now=NOW + timedelta(minutes=2, seconds=5))
    view = orders.board(roster)["open"][0]
    assert view["message"] == "cannot_message" and view["person"]["reachable"] is False

    # Someone who can be messaged gets it.
    roster.execute("UPDATE attendees SET tg_user_id=777, can_message=1 WHERE id=?", (p["id"],))
    got = []
    orders.call(roster, o["id"], LOFT, now=NOW + timedelta(minutes=4))
    notify.deliver(roster, lambda chat, text, go, **k: got.append((chat, text)),
                   now=NOW + timedelta(minutes=4, seconds=5))
    assert got and got[0][0] == 777 and "your order is ready" in got[0][1]
    assert orders.board(roster)["open"][0]["message"] == "sent"


def test_orders_refuse_the_wrong_item_and_people_not_on_the_list(roster):
    p = person(roster, "bananabelles")
    with pytest.raises(ClaimError) as exc:
        orders.place(roster, item="pastry", actor=LOFT, attendee_id=p["id"])
    assert exc.value.code == "VALIDATION_FAILED"
    roster.execute("UPDATE attendees SET status='inactive' WHERE id=?", (p["id"],))
    with pytest.raises(ClaimError) as exc:
        orders.place(roster, item="matcha", actor=LOFT, attendee_id=p["id"])
    assert exc.value.code == "INACTIVE"


def test_ordering_needs_a_sign_in_and_the_csrf_token(roster):
    import app as webapp
    webapp.app.config["TESTING"] = True
    anon = webapp.app.test_client()
    assert anon.get("/admin/api/orders").status_code == 401
    p = person(roster, "bananabelles")
    phone = Console()
    r = phone.post("/admin/api/orders", {"code": p["pass_code"], "item": "matcha"}, csrf=False)
    assert r.status_code == 403 and roster.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0


def test_guessing_codes_through_the_order_button_counts_against_the_limit(roster):
    db.set_setting(roster, "lookup_rate_limit", 2, by="test")
    phone = Console()
    for code in ("ZZZZ-ZZZZ", "YYYY-YYYY"):
        assert err(phone.post("/admin/api/orders", {"code": code, "item": "matcha"}))["code"] == "UNKNOWN_CODE"
    p = person(roster, "bananabelles")
    assert err(phone.post("/admin/api/orders", {"code": p["pass_code"], "item": "matcha"}))["code"] \
        == "RATE_LIMITED"


def test_the_call_and_close_buttons_work_over_http(roster):
    p = person(roster, "bananabelles")
    phone = Console("mobile", "Wei", "Loft")
    o = phone.post("/admin/api/orders", {"code": p["pass_code"], "item": "panini"}).get_json()["data"]
    called = phone.post(f"/admin/api/orders/{o['id']}/call").get_json()["data"]
    assert called["status"] == "called" and called["calls"] == 1
    done = phone.post(f"/admin/api/orders/{o['id']}/collected").get_json()["data"]
    assert done["status"] == "collected"
    # Not on the phone's list, so the server's rule for anything unlisted —
    # admin only — answers before the route does.
    assert err(phone.post(f"/admin/api/orders/{o['id']}/dance"))["code"] == "FORBIDDEN"
    assert err(Console("admin").post(f"/admin/api/orders/{o['id']}/dance"))["code"] == "NOT_FOUND"
