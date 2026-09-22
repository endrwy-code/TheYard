"""Bot messages: the outbox, the notify switch, scheduled messages, and the
events that queue them (payments, bookings)."""

from datetime import datetime, timedelta, timezone

import pytest

import config
import db
from conftest import sign
from services import bookings, claims, notify
from test_claims_concurrent import (  # noqa: F401 - fixtures are used by name
    Console, err, person, roster, secrets_and_limits,
)

EVENT = datetime(2026, 9, 24, tzinfo=config.TIMEZONE)


def at(hh, mm):
    return EVENT.replace(hour=hh, minute=mm).astimezone(timezone.utc)


class Sender:
    def __init__(self, fail=None):
        self.sent, self.fail = [], fail

    def __call__(self, chat_id, text, go):
        if self.fail:
            raise self.fail
        self.sent.append((chat_id, text, go))


def pid(conn, handle):
    return conn.execute("SELECT id FROM attendees WHERE handle=?", (handle,)).fetchone()["id"]


def link(conn, handle, tg_id):
    conn.execute("UPDATE attendees SET tg_user_id=? WHERE handle=?", (tg_id, handle))
    return pid(conn, handle)


@pytest.fixture()
def owner(roster, client):
    """@maxi_muslim, created the way it is in real life: by opening the app."""
    client.post("/api/session", headers={"Authorization": "tma " + sign(9, "maxi_muslim", "Max")})
    return pid(roster, "maxi_muslim")


def statuses(conn):
    return [r[0] for r in conn.execute("SELECT status FROM notifications ORDER BY id")]


# ---------------------------------------------------------------------------
# The outbox
# ---------------------------------------------------------------------------

def test_a_dedupe_key_queues_once(roster):
    i = pid(roster, "heidily")
    assert notify.queue(roster, i, "x", "hello", dedupe_key="k1") is True
    assert notify.queue(roster, i, "x", "hello", dedupe_key="k1") is False
    assert notify.queue(roster, i, "x", "hello") and notify.queue(roster, i, "x", "hello")
    assert roster.execute("SELECT COUNT(*) FROM notifications").fetchone()[0] == 3


def test_owner_mode_only_messages_test_accounts(roster, owner):
    assert db.get_setting(roster, "notify_mode") == "owner"      # the safe default
    heidi = link(roster, "heidily", 111)
    notify.queue(roster, heidi, "x", "to a real attendee")
    notify.queue(roster, owner, "x", "to the organiser")
    s = Sender()
    assert notify.deliver(roster, s) == {"suppressed": 1, "sent": 1}
    assert s.sent == [(9, "to the organiser", "home")]
    # Switching on later does not flush the held-back message.
    db.set_setting(roster, "notify_mode", "on")
    assert notify.deliver(roster, s) == {}


def test_on_mode_messages_everyone_and_off_mode_nobody(roster):
    heidi = link(roster, "heidily", 111)
    db.set_setting(roster, "notify_mode", "on")
    notify.queue(roster, heidi, "x", "one")
    s = Sender()
    assert notify.deliver(roster, s) == {"sent": 1}
    db.set_setting(roster, "notify_mode", "off")
    notify.queue(roster, heidi, "x", "two")
    assert notify.deliver(roster, s) == {"suppressed": 1}
    assert len(s.sent) == 1


def test_people_who_never_opened_the_bot_are_skipped(roster):
    db.set_setting(roster, "notify_mode", "on")
    notify.queue(roster, pid(roster, "heidily"), "x", "hello")
    assert notify.deliver(roster, Sender()) == {"skipped": 1}


def test_a_blocked_bot_marks_the_person_unreachable(roster):
    db.set_setting(roster, "notify_mode", "on")
    heidi = link(roster, "heidily", 111)
    notify.queue(roster, heidi, "x", "hello")
    assert notify.deliver(roster, Sender(notify.Blocked("bot was blocked"))) == {"failed": 1}
    row = roster.execute("SELECT * FROM attendees WHERE id=?", (heidi,)).fetchone()
    assert row["can_message"] == 0 and not notify.reachable(row)


def test_network_errors_are_retried_then_given_up(roster):
    db.set_setting(roster, "notify_mode", "on")
    heidi = link(roster, "heidily", 111)
    notify.queue(roster, heidi, "x", "hello")
    now = datetime.now(timezone.utc)
    for n in range(notify.MAX_ATTEMPTS):
        out = notify.deliver(roster, Sender(RuntimeError("timeout")), now=now + timedelta(minutes=n))
        assert out == ({"retry": 1} if n < notify.MAX_ATTEMPTS - 1 else {"failed": 1})
    assert statuses(roster) == ["failed"]
    # A later success is not possible: it gave up.
    assert notify.deliver(roster, Sender(), now=now + timedelta(hours=1)) == {}


def test_a_retry_that_succeeds_is_sent_once(roster):
    db.set_setting(roster, "notify_mode", "on")
    heidi = link(roster, "heidily", 111)
    notify.queue(roster, heidi, "x", "hello")
    now = datetime.now(timezone.utc)
    notify.deliver(roster, Sender(RuntimeError("timeout")), now=now)
    s = Sender()
    assert notify.deliver(roster, s, now=now) == {}                       # not due yet
    assert notify.deliver(roster, s, now=now + timedelta(minutes=1)) == {"sent": 1}
    assert len(s.sent) == 1


def test_stale_messages_expire_instead_of_arriving_late(roster):
    db.set_setting(roster, "notify_mode", "on")
    heidi = link(roster, "heidily", 111)
    now = datetime.now(timezone.utc)
    notify.queue(roster, heidi, "escape_reminder", "starts soon", expires_at=now - timedelta(seconds=1))
    assert notify.deliver(roster, Sender(), now=now) == {"expired": 1}


def test_a_row_claimed_by_another_sender_is_not_sent_twice(roster):
    db.set_setting(roster, "notify_mode", "on")
    heidi = link(roster, "heidily", 111)
    notify.queue(roster, heidi, "x", "hello")
    roster.execute("UPDATE notifications SET status='sending', send_after=?",
                   (notify._iso(datetime.now(timezone.utc)),))
    assert notify.deliver(roster, Sender()) == {}


# ---------------------------------------------------------------------------
# Scheduled messages
# ---------------------------------------------------------------------------

@pytest.fixture()
def booked(roster):
    bookings.generate_slots(roster)
    s = roster.execute("SELECT * FROM slots WHERE room='escape' ORDER BY starts_at LIMIT 1").fetchone()  # 3:05 PM
    bookings.book(roster, pid(roster, "heidily"), s["id"], ["bananabelles"],
                  datetime(2026, 9, 17, tzinfo=timezone.utc))
    roster.execute("DELETE FROM notifications")
    return roster


def test_the_reminder_goes_ten_minutes_before_once(booked):
    assert notify.schedule_due(booked, at(14, 50)) == 0              # too early
    assert notify.schedule_due(booked, at(14, 55)) == 2              # both players
    assert notify.schedule_due(booked, at(14, 56)) == 0              # never twice
    rows = booked.execute("SELECT * FROM notifications WHERE kind='escape_reminder'").fetchall()
    assert "3:05 PM, in 10 mins" in rows[0]["text"]
    assert rows[0]["button_path"] == "ticket"


def test_no_reminder_once_the_game_has_started(booked):
    assert notify.schedule_due(booked, at(15, 6)) == 0


def test_a_late_reminder_says_how_long_is_left(booked):
    assert notify.schedule_due(booked, at(15, 1)) == 2
    assert "in 4 mins" in booked.execute(
        "SELECT text FROM notifications LIMIT 1").fetchone()[0]


def test_cancelled_players_get_no_reminder(booked):
    b = bookings.active_booking(booked, pid(booked, "bananabelles"))
    booked.execute("UPDATE escape_bookings SET status='cancelled' WHERE id=?", (b["id"],))
    assert notify.schedule_due(booked, at(14, 55)) == 1


def test_the_doors_message_goes_out_on_the_day_in_real_time(roster):
    """At 1 PM, two hours before the 3 PM doors (22 Sep, STATE.md 131)."""
    link(roster, "heidily", 111)
    assert notify.schedule_due(roster, at(12, 59)) == 0
    assert notify.schedule_due(roster, at(13, 30)) == 1              # only linked people
    assert notify.schedule_due(roster, at(13, 31)) == 0
    assert notify.schedule_due(roster, at(15, 1)) == 0               # doors already open
    text = roster.execute("SELECT text FROM notifications").fetchone()[0]
    assert "🕐 3:00 PM–10:00 PM\n📍 The Hub @ Hafary Gallery L5" in text
    # The chill voice (22 Sep, STATE.md 132): no "paid at the front desk" line.
    assert "front desk" not in text


def test_the_doors_message_has_its_own_switch(roster):
    link(roster, "heidily", 111)
    db.set_setting(roster, "doors_message", False)
    assert notify.schedule_due(roster, at(13, 30)) == 0


def test_test_time_never_sends_the_event_day_messages(roster):
    """A rehearsal must not tell the whole list the doors are open."""
    link(roster, "heidily", 111)
    db.set_setting(roster, "test_clock", True)
    assert notify.schedule_due(roster, at(13, 30)) == 0


def test_event_day_messages_never_fire_on_another_day(roster):
    link(roster, "heidily", 111)
    assert notify.schedule_due(roster, at(15, 30) - timedelta(days=1)) == 0


def test_last_call_has_its_own_switch(roster):
    link(roster, "heidily", 111)
    roster.execute("UPDATE attendees SET payment_status='verified', checked_in_at=? WHERE handle='heidily'",
                   (db.utcnow(),))
    db.set_setting(roster, "last_call", False)
    assert notify.schedule_due(roster, at(21, 30)) == 0
    db.set_setting(roster, "last_call", True)
    assert notify.schedule_due(roster, at(21, 30)) == 1


def test_last_call_only_for_people_with_something_left(roster):
    for h, tg in (("heidily", 111), ("bananabelles", 112), ("t_shixuan", 113)):
        link(roster, h, tg)
        roster.execute("UPDATE attendees SET payment_status='verified', checked_in_at=? "
                       "WHERE handle=?", (db.utcnow(), h))
    roster.execute("UPDATE attendees SET payment_status='submitted' WHERE handle='t_shixuan'")
    wei = Console()
    code = roster.execute("SELECT pass_code FROM attendees WHERE handle='bananabelles'").fetchone()[0]
    for item in claims.ITEMS:
        wei.hand_over(code, item)
    assert notify.schedule_due(roster, at(21, 29)) == 0
    assert notify.schedule_due(roster, at(21, 30)) == 1              # Heidi only
    row = roster.execute("SELECT * FROM notifications WHERE kind='last_call'").fetchone()
    assert row["attendee_id"] == pid(roster, "heidily")
    assert "pastry, photo strip and vinyl making" in row["text"] and "10:00 PM" in row["text"]
    assert notify.schedule_due(roster, at(22, 0)) == 0               # closed


# ---------------------------------------------------------------------------
# What queues messages
# ---------------------------------------------------------------------------

def kinds(conn):
    return [r[0] for r in conn.execute("SELECT kind FROM notifications ORDER BY id")]


def test_no_verdict_ever_messages_the_person(roster):
    """24 Sep. Telegram is a push: being told out of nowhere that a payment
    was refused reads as an accusation, and being told it was accepted is
    news to nobody — they are at the front desk when it happens. The verdict
    lives on their page and in the audit trail instead."""
    admin = Console("admin")
    i = pid(roster, "heidily")
    assert admin.post(f"/admin/api/people/{i}/payment", {"verdict": "verified"}).status_code == 200
    admin.post(f"/admin/api/people/{i}/payment", {"verdict": "reopen", "reason": "typo"})
    admin.post(f"/admin/api/people/{i}/payment", {"verdict": "rejected", "reason": "Amount is $5"})
    assert kinds(roster) == []
    # It is still recorded where the staff need it.
    assert roster.execute(
        "SELECT COUNT(*) FROM audit_log WHERE action LIKE 'Payment %'").fetchone()[0] == 3


def test_hand_overs_and_check_ins_send_nothing(roster):
    p = person(roster, "heidily")
    wei = Console()
    wei.hand_over(p["pass_code"], "pastry")
    wei.check_in(p["pass_code"])
    assert kinds(roster) == []


def test_no_message_leaks_the_solution():
    """§3 r4 — bot copy is attendee-facing."""
    now = db.utcnow()
    texts = [notify.text_booked(now, "ESC-1", []), notify.text_jam_booked(now, now, "JAM-1"),
             notify.text_friend_added("@a", now, now), notify.text_friend_removed("@a", now),
             notify.text_member_left("@a", now), notify.text_reminder(now, 10),
             notify.text_jam_reminder(now, 10),
             notify.text_doors("5:00 PM", "10:00 PM", "X"),
             notify.text_last_call(["pastry"], "10:00 PM")]
    for t in texts:
        for word in ("lock code", "0000", "solution", "clock offset", "hint"):
            assert word not in t.lower()


def test_the_booth_call_endpoint_is_gone(roster):
    """Pastries and canned drinks are grab-and-go; there is nothing to call."""
    admin = Console("admin")
    assert err(admin.post("/admin/api/claims/call", {"code": "ZZZZ-ZZZZ"}))["code"] == "NOT_FOUND"
    # Staff are refused before routing, as with any unlisted console path.
    assert err(Console().post("/admin/api/claims/call", {"code": "ZZZZ-ZZZZ"}))["code"] == "FORBIDDEN"


def test_the_jam_reminder_goes_too(roster):
    bookings.generate_slots(roster)
    s = roster.execute("SELECT * FROM slots WHERE room='jam' ORDER BY starts_at LIMIT 1").fetchone()  # 3 PM
    # A group now, so the reminder has to reach the friend as well as the booker.
    bookings.book_jam(roster, pid(roster, "heidily"), s["id"], "bass", [{"handle": "joncjy", "instrument": "electric"}],
                      datetime(2026, 9, 17, tzinfo=timezone.utc))
    roster.execute("DELETE FROM notifications")
    # Two seats, so two reminders: everyone in the room needs telling, not
    # just whoever pressed the button.
    assert notify.schedule_due(roster, at(14, 50)) == 2
    assert notify.schedule_due(roster, at(14, 51)) == 0
    rows = roster.execute("SELECT * FROM notifications ORDER BY id").fetchall()
    assert {r["kind"] for r in rows} == {"jam_reminder"}
    assert all("3:00 PM" in r["text"] and r["button_path"] == "bookings" for r in rows)
    assert len({r["attendee_id"] for r in rows}) == 2


def test_cancelling_withdraws_the_unsent_added_message(roster):
    bookings.generate_slots(roster)
    s = roster.execute("SELECT * FROM slots WHERE room='escape' ORDER BY starts_at LIMIT 1").fetchone()
    today = datetime(2026, 9, 17, tzinfo=timezone.utc)
    bookings.book(roster, pid(roster, "heidily"), s["id"], ["bananabelles"], today)
    bookings.remove_friend(roster, pid(roster, "heidily"), "bananabelles", today)
    rows = {r["kind"]: r["status"] for r in roster.execute("SELECT kind, status FROM notifications")}
    # Never told they were added, so not told they were removed either.
    assert rows["friend_added"] == "withdrawn" and "friend_removed" not in rows
    # Once the first message has gone, a removal is worth telling.
    bookings.add_friends(roster, pid(roster, "heidily"), ["bananabelles"], today)
    roster.execute("UPDATE notifications SET status='sent' WHERE status='queued' AND kind='friend_added'")
    bookings.remove_friend(roster, pid(roster, "heidily"), "bananabelles", today)
    assert roster.execute("SELECT COUNT(*) FROM notifications WHERE kind='friend_removed'").fetchone()[0] == 1