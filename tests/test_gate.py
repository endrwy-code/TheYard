"""The gate — §17.1, §17.2, §17.3 and §9 rules 1-9."""

import time

import pytest

import auth
import db
from conftest import claimed, import_real_export, session, sign


@pytest.fixture()
def roster(conn):
    import_real_export(conn)
    return conn


# --- §9 rule 1: normalisation ---------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("@Name", "name"), ("name ", "name"), ("  @NAME  ", "name"),
    ("https://t.me/Name", "name"), ("http://t.me/name", "name"),
    ("t.me/Name", "name"), ("telegram.me/Name", "name"),
    ("", ""), (None, ""), ("@Mr_RishieParker", "mr_rishieparker"),
])
def test_handles_normalise(raw, expected):
    assert auth.normalise_handle(raw) == expected


@pytest.mark.parametrize("handle,ok", [
    ("nadiarhm", True), ("mr_rishieparker", True), ("abc", False),
    ("has space", False), ("hyphen-ated", False), ("x" * 33, False),
])
def test_handle_validity(handle, ok):
    assert auth.looks_like_handle(handle) is ok


# --- §17.1 -----------------------------------------------------------------

def test_listed_username_gets_in(roster, client):
    r = session(client, sign(1001, "bananabelles", "Annabelle"))
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"]
    assert body["data"]["profile"]["full_name"] == "Annabelle Koh"
    assert body["data"]["profile"]["pass_code"]


def test_unlisted_friend_is_refused(roster, client):
    r = session(client, sign(1002, "ryanlow", "Ryan"))
    assert r.status_code == 403
    err = r.get_json()["error"]
    assert err["code"] == "NOT_ON_LIST"
    assert err["handle"] == "ryanlow"          # quoted back exactly


def test_no_username_gets_instructions(roster, client):
    r = session(client, sign(1003, None, "Sam"))
    assert r.get_json()["error"]["code"] == "NO_USERNAME"


def test_owner_always_allowed_even_when_not_listed(roster, client, conn):
    r = session(client, sign(1004, "maxi_muslim", "Maximus"))
    assert r.status_code == 200 and r.get_json()["ok"]
    row = conn.execute("SELECT * FROM attendees WHERE handle='maxi_muslim'").fetchone()
    assert row["source"] == "owner"
    assert row["is_test"] == 1                  # §9 r5 — out of headcounts


def test_claimed_handle_lands_on_the_desk_but_admits_nobody(roster, client, conn):
    tg = sign(2001, "someone_else", "Nobody")
    assert session(client, tg).status_code == 403
    assert claimed(client, tg, "@BananaBelles ").status_code == 200

    row = conn.execute(
        "SELECT * FROM gate_attempts WHERE claimed_handle IS NOT NULL ORDER BY id DESC"
    ).fetchone()
    assert row["claimed_handle"] == "bananabelles"     # normalised on the way in

    # Still refused, and the real sign-up is untouched.
    assert session(client, tg).status_code == 403
    target = conn.execute("SELECT * FROM attendees WHERE handle='bananabelles'").fetchone()
    assert target["tg_user_id"] is None


def test_claimed_handle_is_rate_limited(roster, client):
    tg = sign(2002, "nobody_here", "Nobody")
    session(client, tg)
    codes = [claimed(client, tg, "bananabelles").status_code for _ in range(5)]
    assert codes.count(200) == 3                 # §9 r7 — 3 an hour
    assert codes.count(429) == 2


# --- §9 rules 2, 3: linking ------------------------------------------------

def test_links_on_first_start(roster, client, conn):
    session(client, sign(1001, "bananabelles", "Annabelle"))
    row = conn.execute("SELECT * FROM attendees WHERE handle='bananabelles'").fetchone()
    assert row["tg_user_id"] == 1001


def test_second_account_on_the_same_signup_is_refused(roster, client):
    session(client, sign(1001, "bananabelles", "Annabelle"))
    r = session(client, sign(9999, "bananabelles", "Impostor"))
    assert r.get_json()["error"]["code"] == "LINKED_ELSEWHERE"


def test_changed_username_still_gets_in(roster, client):
    session(client, sign(1001, "bananabelles", "Annabelle"))
    r = session(client, sign(1001, "annabelle_renamed", "Annabelle"))
    assert r.status_code == 200 and r.get_json()["ok"]


def test_capitalised_handle_matches(roster, client):
    """§17.3 — listed as '@Mr_RishieParker', opened as the same, still matches."""
    r = session(client, sign(1005, "Mr_RishieParker", "Jayden"))
    assert r.status_code == 200 and r.get_json()["ok"]


def test_inactive_person_is_refused(roster, client, conn):
    conn.execute("UPDATE attendees SET status='inactive' WHERE handle='heidily'")
    r = session(client, sign(1008, "heidily", "Heidi"))
    assert r.get_json()["error"]["code"] == "INACTIVE"


# --- §9 rule 8: initData ---------------------------------------------------

def test_forged_hash_is_refused(roster, client):
    r = session(client, "user=%7B%22id%22%3A1%7D&auth_date=1&hash=deadbeef")
    assert r.get_json()["error"]["code"] == "INITDATA_INVALID"


def test_missing_header_is_refused(roster, client):
    r = session(client, None)
    assert r.get_json()["error"]["code"] == "INITDATA_INVALID"


def test_old_initdata_is_expired(roster, client):
    old = sign(1006, "heidily", "Heidi", auth_date=time.time() - 25 * 3600)
    assert r_code(client, old) == "INITDATA_EXPIRED"


def test_initdata_just_inside_the_window_is_fine(roster, client):
    fresh = sign(1006, "heidily", "Heidi", auth_date=time.time() - 23 * 3600)
    assert session(client, fresh).status_code == 200


def test_wrong_token_is_refused(roster, client):
    other = sign(1007, "heidily", "Heidi", token="999:SOME-OTHER-BOT")
    assert r_code(client, other) == "INITDATA_INVALID"


def r_code(client, init_data):
    return session(client, init_data).get_json()["error"]["code"]


# --- §9 rule 9: the gate switch --------------------------------------------

def test_gate_switch_closes_the_app(roster, client, conn):
    db.set_setting(conn, "gate_open", False, by="test")
    assert r_code(client, sign(1009, "heidily", "Heidi")) == "GATE_CLOSED"


def test_owner_gets_in_while_the_gate_is_closed(roster, client, conn):
    db.set_setting(conn, "gate_open", False, by="test")
    r = session(client, sign(1004, "maxi_muslim", "Maximus"))
    assert r.status_code == 200 and r.get_json()["ok"]


# --- §9 rules 6, 32, 34 ----------------------------------------------------

def test_every_refusal_is_recorded(roster, client, conn):
    session(client, sign(1002, "ryanlow", "Ryan"))
    session(client, sign(1003, None, "Sam"))
    rows = conn.execute("SELECT outcome FROM gate_attempts ORDER BY id").fetchall()
    assert [r["outcome"] for r in rows] == ["NOT_ON_LIST", "NO_USERNAME"]


def test_linking_is_audited(roster, client, conn):
    session(client, sign(1001, "bananabelles", "Annabelle"))
    row = conn.execute(
        "SELECT * FROM audit_log WHERE action='Telegram account linked'").fetchone()
    assert row is not None
    assert row["actor_type"] == "system"


def test_server_time_on_every_response(roster, client):
    good = session(client, sign(1001, "bananabelles", "Annabelle")).get_json()
    bad = session(client, sign(1002, "ryanlow", "Ryan")).get_json()
    assert good["server_time"] and bad["server_time"]
