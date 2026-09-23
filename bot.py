"""The Yard — bot process (§11). Run it in its own window:

    python bot.py

Long polling, outbound only, so it needs no tunnel. It answers /start, /pass
and /help, keeps the chat's Open The Yard button pointing at PUBLIC_URL, and
every few seconds sends whatever the web process queued (services/notify.py).
No message goes out while this window is closed.

Only one copy may run at a time — Telegram refuses a second poller.
"""

import asyncio
import base64
import io
import logging
import sys

from telegram import (BotCommand, InlineKeyboardButton, InlineKeyboardMarkup,
                      MenuButtonWebApp, Update, WebAppInfo)
from telegram.constants import ChatType
from telegram.error import Conflict
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import auth
import config
import db
from services import claims, notify

TICK_SECONDS = 5

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("bot")

# The gate's reasons (§11), in the bot's own relaxed voice since 22 Sep
# (STATE.md 132). Same meaning as the Mini App's gate; only the tone differs.
GATE_TEXT = {
    "NOT_ON_LIST": ("hmm, we can't find @{handle} on The Yard's sign-up list. signed up with a "
                    "different username? open the app and send it to the front desk"),
    "NO_USERNAME": ("your Telegram account doesn't have a username yet. go to Telegram → Settings → "
                    "Username, pick one, then send /start again"),
    "LINKED_ELSEWHERE": ("that sign-up is already linked to another Telegram account. "
                         "pop by the front desk and we'll sort it out"),
    "GATE_CLOSED": "The Yard is closed now. thanks for coming!",
    "INACTIVE": "you're not on the current sign-up list. the front desk can sort it out",
}


def open_markup(go=None, label="Open The Yard"):
    if not config.PUBLIC_URL:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton(
        label, web_app=WebAppInfo(url=notify.web_app_url(go)))]])


def tg_of(update):
    u = update.effective_user
    return {"user_id": u.id, "username": auth.normalise_handle(u.username),
            "username_raw": u.username or "", "first_name": (u.first_name or "").strip(),
            "allows_write": True, "start_param": None, "auth_date": None}


def resolve(update):
    """(row, None) or (None, refusal text). Runs the same gate as the app."""
    tg = tg_of(update)
    conn = db.connect()
    try:
        try:
            row = auth.resolve_attendee(conn, tg)
        except auth.GateError as exc:
            text = GATE_TEXT.get(exc.code, "pop by the front desk and we'll sort it out")
            return None, text.format(handle=tg["username"] or "")
        # Writing to us is permission to write back (§11 "blocked bots").
        conn.execute("UPDATE attendees SET can_message=1 WHERE id=?", (row["id"],))
        return row, None
    finally:
        conn.close()


def private(update):
    return update.effective_chat and update.effective_chat.type == ChatType.PRIVATE


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not private(update):
        return
    row, refusal = resolve(update)
    if refusal:
        # The app's Start screen is where they send the username they used.
        wants_app = refusal == GATE_TEXT["NOT_ON_LIST"].format(handle=tg_of(update)["username"] or "")
        await update.message.reply_text(refusal, reply_markup=open_markup() if wants_app else None)
        return
    conn = db.connect()
    try:
        s = db.get_settings(conn)
    finally:
        conn.close()
    first = row["tg_first_name"] or (row["name"] or "").split(" ")[0] or "there"
    text = (f"hey {first}, you're on the list for The Yard 🙌\n"
            "📅 Thursday 24 September\n"
            f"🕐 {notify.hhmm_text(s['doors_open'])}–{notify.hhmm_text(s['doors_close'])}\n"
            f"📍 {s['venue']}\n\n"
            "your pass, the escape room and the jamming studio are all in the app\n\n"
            "i'll only message you when something needs you, like a booking, a friend adding you, "
            "your slot starting soon or your payment being checked\n\n"
            "/pass shows your pass even if the app won't load")
    markup = open_markup()
    if markup is None:
        text += "\n\ntap the Open The Yard button next to the message box"
    await update.message.reply_text(text, reply_markup=markup)


async def cmd_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """§11 — works even when the Mini App won't load; no tunnel involved."""
    if not private(update):
        return
    row, refusal = resolve(update)
    if refusal:
        await update.message.reply_text(refusal)
        return
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM attendees WHERE id=?", (row["id"],)).fetchone()
        items = claims.claims_for(conn, row["id"])
        paid = claims.payment_ok(conn, row)
    finally:
        conn.close()
    png = base64.b64decode(claims.pass_qr_data_uri(row["pass_code"]).split(",", 1)[1])
    lines = [f"🎟 your Yard Pass: {row['pass_code']}", ""]
    for item in claims.ITEMS:
        c = items[item]
        kind = f" ({c['variant_label']})" if c["claimed"] and c.get("variant_label") else ""
        lines.append(f"{claims.label(item)}: " + (f"collected {claims.clock(c['at'])}{kind}"
                                                  if c["claimed"] else "ready"))
    if not paid:
        lines += ["", "we haven't verified your payment yet, so nothing can be handed over. "
                      "pop by the front desk"]
    lines += ["", "turn your brightness up when you scan"]
    await update.message.reply_photo(photo=io.BytesIO(png), caption="\n".join(lines),
                                     reply_markup=open_markup(notify.GO_FOOD))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not private(update):
        return
    conn = db.connect()
    try:
        helper = db.get_setting(conn, "help_handle", "maxi_muslim")
        meet = db.get_setting(conn, "meeting_point", "the front desk")
    finally:
        conn.close()
    await update.message.reply_text(
        "🙋 need a hand?\n"
        f"📍 {meet}\n"
        f"💬 @{helper}\n\n"
        "/pass – your pass, even if the app won't load\n"
        "/start – the Open The Yard button")


async def cmd_actor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/actor <GM PIN> — this chat gets the hint lines the GM sends (§11)."""
    if not private(update):
        return
    pin = " ".join(context.args or []).strip()
    # The PIN is in the chat history now; delete it where Telegram allows.
    try:
        await update.message.delete()
    except Exception:  # noqa: BLE001 - private chats may refuse; not important
        pass
    if not pin or not auth.check_role("gm", pin):
        await update.effective_chat.send_message("that isn't the GM PIN. send: /actor <GM PIN>")
        return
    conn = db.connect()
    try:
        db.set_setting(conn, "actor_chat_id", update.effective_chat.id, by="bot")
        db.audit(conn, "system", "Actor chat registered", actor_name=tg_of(update)["username"] or "unknown",
                 entity="setting", entity_id="actor_chat_id")
    finally:
        conn.close()
    await update.effective_chat.send_message(
        "🎭 you're the actor for The Last Guest\n"
        "hint lines from the game master land here the moment they send them. "
        "send /actor again from another phone to move them there")


async def on_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not private(update) or not update.message:
        return
    if update.message.photo or update.message.document:
        await update.message.reply_text(
            "i can't take receipts here. show your payment at the front desk")
        return
    await update.message.reply_text("try /pass for your pass, or /help",
                                     reply_markup=open_markup())


# ---------------------------------------------------------------------------
# The outbox
# ---------------------------------------------------------------------------

def run_outbox():
    conn = db.connect()
    try:
        queued = notify.schedule_due(conn)
        sent = notify.deliver(conn, notify.bot_api_send)
        staff = notify.deliver_direct(conn, notify.bot_api_send)
    finally:
        conn.close()
    if queued or sent or staff:
        log.info("outbox: %d scheduled, %s, actor %s", queued, sent or "nothing due", staff or "nothing")


async def tick(context: ContextTypes.DEFAULT_TYPE):
    try:
        await asyncio.to_thread(run_outbox)
    except Exception:  # noqa: BLE001 - one bad tick must not stop the bot
        log.exception("outbox tick failed; trying again in %ss", TICK_SECONDS)


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, Conflict):
        log.error("Another bot.py is already running for this bot. Close the other window.")
        return
    log.exception("Error while handling an update", exc_info=context.error)


async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "Open The Yard"),
        BotCommand("pass", "Show my pass"),
        BotCommand("help", "Get help"),
    ])
    if config.PUBLIC_URL:
        await application.bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
            text="Open The Yard", web_app=WebAppInfo(url=notify.web_app_url())))
        log.info("Menu button points at %s", config.PUBLIC_URL)
    else:
        log.warning("PUBLIC_URL is not set in .env — messages go out without an Open button.")
    conn = db.connect()
    try:
        mode = db.get_setting(conn, "notify_mode", "owner")
    finally:
        conn.close()
    log.info("Messages: %s", {
        "owner": "TEST MODE — only always-allowed accounts and the test group get messages "
                 "(python manage.py notify on to switch everyone on)",
        "on": "on for everyone",
        "off": "OFF — nothing is sent",
    }.get(mode, mode))
    print("Bot started, polling", flush=True)


def main():
    if not config.TELEGRAM_TOKEN:
        print("TELEGRAM_TOKEN is missing from .env. Nothing started.")
        return 1
    db.init_db()
    app = (Application.builder().token(config.TELEGRAM_TOKEN)
           .post_init(post_init).build())
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("pass", cmd_pass))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("actor", cmd_actor))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, on_other))
    app.add_error_handler(on_error)
    app.job_queue.run_repeating(tick, interval=TICK_SECONDS, first=2)
    app.run_polling(allowed_updates=["message"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
