"""Configuration. Secrets come from .env; everything else is a Settings row."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _handles(raw):
    out = set()
    for part in (raw or "").split(","):
        part = part.strip().lstrip("@").lower()
        if part:
            out.add(part)
    return out


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "").strip()
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
STAFF_PIN_HASH = os.getenv("STAFF_PIN_HASH", "").strip()
GM_PIN_HASH = os.getenv("GM_PIN_HASH", "").strip()
PUBLIC_URL = os.getenv("PUBLIC_URL", "").strip().rstrip("/")
PAPERFORM_WEBHOOK_SECRET = os.getenv("PAPERFORM_WEBHOOK_SECRET", "").strip()
ALWAYS_ALLOW_HANDLES = _handles(os.getenv("ALWAYS_ALLOW_HANDLES", "maxi_muslim"))

TIMEZONE_NAME = os.getenv("TIMEZONE", "Asia/Singapore").strip() or "Asia/Singapore"
TIMEZONE = ZoneInfo(TIMEZONE_NAME)

DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
DB_PATH = DATA_DIR / "app.db"
BACKUP_DIR = DATA_DIR / "backups"
IMPORTS_DIR = BASE_DIR / "imports"
PHONE_DIR = BASE_DIR / "private" / "phone"
# Our own copies of the Paperform payment screenshots. The links Paperform
# signs expire 7 days after each sign-up — before the event — so the copies
# here are what an admin actually verifies against on the day (§9 r29, r31).
RECEIPTS_DIR = BASE_DIR / "private" / "receipts"
# Photographs for the top of each Mini App screen. Public (they are the
# event's own pictures, not the escape room's evidence — those live in
# private\phone\assets and never reach an attendee screen, §3 r4).
SHOTS_DIR = BASE_DIR / "static" / "shots"

# §9 rule 8. Telegram signs initData with auth_date; anything older is refused.
INITDATA_MAX_AGE_SECONDS = 24 * 60 * 60

# Codes use an unambiguous alphabet — no 0, O, 1, I or L (§9 rule 20).
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
QR_PREFIX = "YARD:"

# §9 rule 33. A console sign-in lasts one event day, then asks again.
CONSOLE_SESSION_HOURS = 12

# §9 rule 27. Remaining stock at or below this shows as "low" at the booth.
# This is only the starting value: it is a Settings row (`low_stock_at`), so
# the organiser can change it on the night without touching a file.
LOW_STOCK_AT = 5

EVENT_DATE = "2026-09-24"

# What the pass hands over, once each, at the counter (§9 r24).
# The apps read this list from the server; add a line to add an item.
#
# The canned drink was dropped on 19 Sep at the organiser's instruction. It is
# not included with entry at all any more, so it is not on this list and not
# in the "included with entry" copy either. Drinks are sold at Loft, which is
# what `paid_extras` already says.
#
# Labels are names of things, so they take title case (22 Sep, STATE.md
# decision 123). Bot sentences lower-case them where they fall mid-sentence.
#
# Since 22 Sep (evening, STATE.md 132) the pass holds three things: one
# pastry of the person's choosing, their first photo strip, and vinyl crafting.
ITEMS = (
    ("pastry", "Pastry"),
    ("photo", "Photo Strip"),
    ("vinyl", "Vinyl Crafting"),
)
ITEM_KEYS = tuple(key for key, _ in ITEMS)
ITEM_LABELS = dict(ITEMS)

# An item that comes in kinds. The pass still gives one pastry; the counter
# taps which one went, so the claim records it (claims.variant) and the
# console can show what is running out.
ITEM_CHOICES = {
    "pastry": (("tart", "Mini Tart"), ("cookie", "Mini Cookie"),
               ("shiopan", "Shiopan")),
}
# One line under an item on the pass, when the name alone doesn't say it.
ITEM_NOTES = {
    "pastry": "Tart or cookie",
    "photo": "Your first strip",
}

# Made to order, so the counter messages people when it's ready (22 Sep,
# decision 125). Not pass items: paid for at the stall, and anyone may order
# as many as they like. (key, label, emoji for the message.) Where each is
# collected is its own Settings row, `<key>_pickup`, because they are made
# at different stalls.
ORDER_ITEMS = (
    ("matcha", "Matcha", "\U0001f375"),
    ("panini", "Panini", "\U0001f96a"),
)
ORDER_ITEM_KEYS = tuple(key for key, _, _ in ORDER_ITEMS)
ORDER_ITEM_LABELS = {key: label for key, label, _ in ORDER_ITEMS}
ORDER_ITEM_EMOJI = {key: emoji for key, _, emoji in ORDER_ITEMS}

# The jamming studio is booked by instrument (19 Sep). Five seats in the room,
# one per instrument, so a slot holds five players and the people in it do not
# have to know each other — the instrument is what is actually scarce.
INSTRUMENTS = (
    ("acoustic", "Acoustic Guitar"),
    ("electric", "Electric Guitar"),
    ("keys", "Keyboard"),
    ("drums", "Drums"),
    ("bass", "Bass"),
)
INSTRUMENT_KEYS = tuple(key for key, _ in INSTRUMENTS)
INSTRUMENT_LABELS = dict(INSTRUMENTS)

# What costs money, from the organiser's list of 22 Sep. Only things with a
# price: what the pass covers, the escape room, the jam room and board games
# are free and listed as included instead. Edited on the Settings screen; this
# is only the starting text.
PRICE_LIST = """\
Activities:
Extra Photo Strip: $2 each
Leather Journal Making: $25-35
Silk Printing: $5 a print
Studding: $0.50 to $3 an item

Pastries:
Mini Tart: $2.50
Mini Cookie: $2.50-4

Shiopan and Panini:
Shiopan: $2.20
Panini: $5 a slice

MUTED. Gelato:
Premium Flavours: $6
Classic Flavours: $5
Waffle Bites: $2.50

Matcha and Hojicha:
Matcha or Hojicha Latte: $5
Strawberry Matcha Latte: $6
Cookie Butter or Banana Pudding Matcha Latte: $8

Canned Drinks:
Coke, Sprite, Ice Lemon Tea, Green Tea or Water: $1 a can"""

# Defaults for every Settings row (the organiser's source of truth, 17 Sep).
# A row nobody has edited follows these when they change (db.init_db).
DEFAULT_SETTINGS = {
    # The clock: Real time, or Test time — the app thinks it is EVENT_DATE at
    # test_clock_at, for everyone. One switch since 22 Sep (STATE.md 129); it
    # replaced "event-day mode", whose only jobs were to force this off and to
    # allow the two event-day messages, which now have switches of their own.
    "test_clock": False,
    "test_clock_at": "19:30",
    # 3–10 PM since 22 Sep (STATE.md 131); the rooms open with the doors.
    "doors_open": "15:00",
    "doors_close": "22:00",
    "venue": "Hafary Gallery L5",
    "venue_address": "105 Eunos Ave 3, Singapore 409836",
    "entry_fee": "$12 ($10 early bird until 20 Sep, 11:59 PM)",
    "meeting_point": "the front desk",
    "paid_extras": "Food and drinks, leather journal making, silk printing, studding and extra photo strips",
    # Where each made-to-order item is collected, named in its "ready"
    # message. Two rows since 22 Sep (STATE.md 132): they are different
    # stalls. Matcha is Two Goose's (the floorplan, and "2 goose matcha" on
    # the chalkboard in the pass photograph); panini is the Shiopan Paninis
    # stall on the floorplan.
    "matcha_pickup": "Two Goose",
    "panini_pickup": "Shiopan Paninis",
    # Where players gather for The Last Guest, and the jamming studio's own
    # name. Shown on the tickets and in the bot's messages.
    "escape_meet": "the escape room entrance",
    "jam_room": "Heaven 2",
    # The price list on Help. One line each: "Name: $price". A line with no
    # price is a heading. The organiser's own source of truth, 22 Sep.
    "price_list": PRICE_LIST,
    "help_handle": "maxi_muslim",
    "capacity": 12,
    "game_minutes": 15,
    "changeover_minutes": 5,
    # 3:05 to 9:45 since 22 Sep (STATE.md 133): 21 games, the last ending at
    # 10 PM with the doors, where 3:30-9:30 left the last 15 minutes unused.
    "first_game": "15:05",
    "last_game": "21:45",
    # Telegram handles that may open the victim's phone at any time, booking
    # or no booking: for testing the room before the doors open. Comma
    # separated, no @. Empty on the night — it hands out the whole solution.
    "phone_always_handles": "",
    # How long the phone stays open, from the booked time. A 15-minute game
    # with leeway, so running out of time doesn't cut anyone off (22 Sep,
    # STATE.md 130). Pausing or extending the game moves the end of it too.
    "phone_minutes": 25,
    "booking_cutoff_minutes": 5,
    "cancel_cutoff_minutes": 30,
    "gm_handle": "",
    "actor_handle": "",
    "finder_name": "",
    # The jamming studio is free: book a slot and it is yours.
    "jam_first": "15:00",
    "jam_last": "21:30",
    "jam_slot_minutes": 30,
    "jam_per_person": 1,
    # One seat per instrument, taken from INSTRUMENTS so the two cannot drift
    # apart. Booking by instrument (19 Sep) replaced booking the whole room:
    # the instrument is what is actually scarce, and five strangers sharing a
    # room each on their own instrument is a jam, not an awkward silence.
    "jam_capacity": len(INSTRUMENTS),
    "pastry_stock": 0,               # 0 = not counted
    "photo_stock": 0,
    "vinyl_stock": 0,
    "low_stock_at": LOW_STOCK_AT,    # "low" at the booth at or below this
    "block_at_zero": False,
    # A screenshot at sign-up is enough to collect (24 Sep): there is no
    # reference to read off it any more, so it counts the moment it arrives and
    # an admin only steps in to reject a bad one or to mark somebody paid who
    # turned up without one. "verified" and "none" still work; this is the
    # middle setting, and the one the night runs on.
    # Not checked at all, which is how the event runs (23 Sep, STATE.md 138).
    # This was "submitted" until 23 Sep, and that was a trap: every payment
    # gate in the app reads this one row, so a database nobody has touched —
    # a fresh install, or Render on its first deploy with an empty disk —
    # came up refusing hand-overs, showing an amber "Not verified" card at
    # the booth and telling guests by bot to go to a front desk that could do
    # nothing about it. The strict modes are still one tap away in Settings.
    "claim_requires": "none",
    # Paperform's webhook writes a sign-up straight into the roster as it is
    # submitted. It takes no secret (22 Sep), so this switch is how the
    # organiser closes it — from the Settings screen, with no deploy.
    "paperform_webhook": True,
    "gate_open": True,
    "claimed_handle_limit": 3,
    "lookup_rate_limit": 30,
    "backup_minutes": 10,
    "backup_keep": 36,
    "notify_mode": "owner",          # owner (test accounts only) | on | off
    "max_party": 6,                  # a booker plus the friends they add
    "reminder_minutes": 10,          # before an escape game or jam slot
    "doors_message": True,           # "The Yard is on today", 24 Sep, real time only
    "doors_message_at": "13:00",     # two hours before doors, as it was at 5 PM
    "last_call": True,               # uncollected items, 24 Sep, real time only
    "last_call_minutes": 30,         # before doors_close
    "friend_fail_limit": 10,         # failed friend adds per person per 10 min
    # Set by bot.py when the actor sends /actor <GM PIN>; not shown in Settings.
    "actor_chat_id": 0,
}

# Settings people fill in by hand: amber on the Settings screen while empty.
PLACEHOLDER_SETTINGS = ("gm_handle", "actor_handle", "finder_name")
# Settings the console never shows or edits.
INTERNAL_SETTINGS = ("actor_chat_id",)
# Changing one of these rebuilds the game and jam timetables.
SCHEDULE_SETTINGS = ("capacity", "game_minutes", "changeover_minutes", "first_game", "last_game",
                     "jam_first", "jam_last", "jam_slot_minutes", "jam_capacity")

# The GM's script (hint lines, the changeover checklist). Spoilers: served
# only to gm and admin sign-ins, never shipped inside a page.
GM_SCRIPT = BASE_DIR / "private" / "gm" / "script.json"

# How long one live-update connection from the console stays open before the
# browser reconnects (it does so by itself).
LIVE_STREAM_SECONDS = 240


def ensure_dirs():
    for d in (DATA_DIR, BACKUP_DIR, IMPORTS_DIR, PHONE_DIR, RECEIPTS_DIR, SHOTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
