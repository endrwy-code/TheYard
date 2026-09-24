"""Shared test setup.

Each test gets its own SQLite *file* (never :memory:) so WAL mode and the busy
timeout behave the way they will on the night (BUILD_SPEC §17).
"""

import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Must be set before config is imported; load_dotenv does not override these.
TEST_TOKEN = "123456:TEST-TOKEN-FOR-THE-GATE"
os.environ["TELEGRAM_TOKEN"] = TEST_TOKEN
os.environ["ALWAYS_ALLOW_HANDLES"] = "maxi_muslim"
os.environ["FLASK_SECRET_KEY"] = "test-only"
os.environ["YARD_AUTO_BACKUP"] = "0"

import config  # noqa: E402
import db  # noqa: E402

EXPORT = ROOT / "context" / "The_Yard_Sign_Up_Responses.xlsx"

# The suite's "now" for anything that goes through the web API.
#
# The timetable is generated on config.EVENT_DATE, so tests that book through
# the API used to depend on the laptop's real clock still being before the
# event: every one of them would start failing on 25 Sep with SLOT_STARTED.
# That is the worst possible false alarm, because the RUNBOOK has the
# organiser run this suite on the morning of the event and stop if it is not
# green. Pinning the clock here makes the result mean the same thing on any
# day. A test that wants a different moment monkeypatches `app.now_utc`
# itself, and doing so still works.
TEST_NOW = datetime(2026, 9, 17, 4, 0, tzinfo=timezone.utc)


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "app.db")
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(config, "PHONE_DIR", tmp_path / "phone")
    monkeypatch.setattr(config, "IMPORTS_DIR", tmp_path / "imports")
    monkeypatch.setattr(config, "RECEIPTS_DIR", tmp_path / "receipts")
    monkeypatch.setattr(config, "TELEGRAM_TOKEN", TEST_TOKEN)
    monkeypatch.setattr(config, "ALWAYS_ALLOW_HANDLES", {"maxi_muslim"})
    db.init_db()
    return tmp_path


@pytest.fixture()
def conn(data_dir):
    c = db.connect()
    yield c
    c.close()


@pytest.fixture(autouse=True)
def pinned_clock(monkeypatch):
    """See TEST_NOW: the API's clock is pinned so the suite means the same
    thing before, during and after the event.

    Autouse, not part of the `client` fixture, because most console tests
    build their own test client (`Console`) and so never went through it.
    Those kept the laptop's real clock, which is fine until the laptop's
    clock reaches the event — on 24 Sep the 3 PM jam slot started reading
    back as "past" and the suite went red on the one morning the RUNBOOK
    has the organiser run it. A test that wants a different moment still
    monkeypatches `app.now_utc` itself, and doing so still wins.
    """
    import app as webapp
    monkeypatch.setattr(webapp, "now_utc", lambda: TEST_NOW)


@pytest.fixture()
def client(data_dir, pinned_clock):
    import app as webapp
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


def sign(user_id, username, first_name="Test", auth_date=None, start_param=None,
         token=TEST_TOKEN):
    """Build a correctly signed initData blob, the way Telegram does."""
    user = {"id": user_id, "first_name": first_name}
    if username:
        user["username"] = username
    fields = {
        "user": json.dumps(user, separators=(",", ":")),
        "auth_date": str(int(auth_date or time.time())),
        "query_id": "AAA",
    }
    if start_param:
        fields["start_param"] = start_param
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def session(client, init_data, body=None):
    headers = {"Authorization": "tma " + init_data} if init_data else {}
    return client.post("/api/session", headers=headers, json=body or {})


def claimed(client, init_data, handle):
    return client.post("/api/session/claimed-handle",
                       headers={"Authorization": "tma " + init_data},
                       json={"claimed_handle": handle})


def import_real_export(conn, actor="test"):
    """Import the real Paperform file and return the preview result."""
    from services import roster
    rows = roster.read_export(EXPORT)
    preview = roster.preview(conn, rows, EXPORT.name)
    roster.commit(conn, preview["run_id"], actor=actor)
    return preview
