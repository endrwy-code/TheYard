"""Record real API answers for the Node render check."""
import os, sys, json, tempfile
from pathlib import Path
# The project this script sits in, wherever it is checked out.
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ["TELEGRAM_TOKEN"] = "123456:TEST-TOKEN-FOR-THE-GATE"
os.environ["ALWAYS_ALLOW_HANDLES"] = "maxi_muslim"
os.environ["FLASK_SECRET_KEY"] = "test-only"
os.environ["YARD_AUTO_BACKUP"] = "0"

import config
tmp = Path(tempfile.mkdtemp())
config.DATA_DIR = tmp; config.DB_PATH = tmp / "app.db"; config.BACKUP_DIR = tmp / "b"
config.IMPORTS_DIR = tmp / "i"; config.PHONE_DIR = tmp / "p"; config.RECEIPTS_DIR = tmp / "r"
config.SHOTS_DIR = tmp / "shots"
config.TELEGRAM_TOKEN = "123456:TEST-TOKEN-FOR-THE-GATE"
config.ALWAYS_ALLOW_HANDLES = {"maxi_muslim"}

import db
db.init_db()
conn = db.connect()
from services import roster, bookings
rows = roster.read_export(ROOT / "context" / "The_Yard_Sign_Up_Responses.xlsx")
pv = roster.preview(conn, rows, "x.xlsx"); roster.commit(conn, pv["run_id"])
bookings.generate_slots(conn)
conn.execute("UPDATE attendees SET payment_status='verified'")
conn.commit()

from conftest import sign
import app as webapp
webapp.app.config["TESTING"] = True
c = webapp.app.test_client()
H = {"Authorization": "tma " + sign(2001, "heidily", "Heidi")}

def get(path):
    r = c.get(path, headers=H)
    body = r.get_json()
    assert body and body.get("ok"), (path, body)
    return body["data"]

def post(path, payload):
    r = c.post(path, headers=H, json=payload)
    body = r.get_json()
    assert body and body.get("ok"), (path, body)
    return body["data"]

session = post("/api/session", {})
esc = get("/api/escape/slots")
post("/api/escape/bookings", {"slot_id": esc["slots"][3]["id"], "friends": ["joncjy"]})
jam = get("/api/jam/slots")
# A late slot, so it cannot clash with the escape game booked above — the
# server refuses a clash for every member, which is the point.
post("/api/jam/bookings", {"slot_id": jam["slots"][8]["id"], "instrument": "bass",
                           "friends": [{"handle": "joncjy", "instrument": "drums"}]})
out = {
    "session": session,
    "me": get("/api/me"),
    "esc": get("/api/escape/slots"),
    "jam": get("/api/jam/slots"),
    "phone": get("/api/escape/phone/status"),
}
dest = Path(sys.argv[1])
dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
print("recorded ->", dest)
print("  jam slots:", len(out["jam"]["slots"]), "instruments:", len(out["jam"]["instruments"]))
print("  my jam:", out["me"]["jam_bookings"][0]["instrument_label"])
print("  items:", [i["key"] for i in out["me"]["event"]["items"]])
