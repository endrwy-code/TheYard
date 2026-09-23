# Project status — the organiser's environment

**For build status — what is live, what is still mock, what is next — read
`STATE.md` in the project root.** Dated changes and known bugs are in
`CHANGELOG.md`. This file covers the machine, the accounts and the working
style, not the code.

This file was rewritten after P0.1 (the gate) went live. The version before it
described a much earlier prototype and several of its claims are no longer
true; the corrections are noted at the bottom so nobody acts on the old ones.

## What this project is

A Telegram Mini App for The Yard, a one-day event on Thursday 24 September 2026
in Singapore, backed by Python and Flask on the organiser's own laptop. There
are two front-ends: the Mini App attendees open inside Telegram, and a staff
console that volunteers open in a normal browser. `BUILD_SPEC.md` is the
specification; `RUNBOOK.md` is the operating guide.

## Environment

- **OS**: Windows 11, PowerShell. Not Bash — use `;` not `&&`, and
  `venv\Scripts\activate` not `source venv/bin/activate`.
- **Editor**: VS Code.
- **Project folder**: `C:\Users\endrw\my-mini-app`. **Git is installed and in
  use** (2.55, checked 23 Sep) — the earlier note that it was not is out of
  date. The project is a GitHub repository and the app is deployed from it;
  `.gitignore` keeps `.env`, the database, the Paperform exports, the saved
  receipts and the printed escape-room props out of it.
- **Python**: virtual environment at `venv\`, activated per window.
- **Every new PowerShell window opens in `C:\Users\endrw`.** On 17 Sep
  `bot.py` and `manage.py notify-test` were run from there with the system
  Python, so nothing ran. Instructions must always start with
  `cd C:\Users\endrw\my-mini-app` and `venv\Scripts\activate`. Four windows are
  normal while testing: app, ngrok, bot, and one for commands.
- PowerShell script execution was blocked by default and was fixed once with
  `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`.

## Accounts and services already set up

1. **Telegram bot** created via @BotFather. The token lives in `.env` as
   `TELEGRAM_TOKEN` — that exact key name is fixed and must not be renamed.
   **Since 22 Sep the bot is `@The_YardBot`** (id 8164503586), a new bot, not
   a new token for the old one. The old bot, `@TheYard_Timeslots_bot` (id
   8831231555), is retired: its token is kept as a comment in `.env` only so
   its settings can still be changed. The Mini App now signs people in against
   the new bot, so opening it from the old bot says "We can't confirm who you
   are". When the switch happened, 5 people had opened the app; they have to
   open `@The_YardBot` once before it can message them.
2. **The Mini App** is registered with BotFather and points at the current
   tunnel URL. Changing tunnel means four steps in order: run the tunnel,
   update `PUBLIC_URL` in `.env`, restart `bot.py`, update the URL in BotFather.
3. **ngrok** installed via `winget install ngrok.ngrok` and authenticated with a
   free account. Used for development. Fixed dev domain:
   `https://moonlight-dwelling-footpad.ngrok-free.dev`. The bot
   (`@The_YardBot` since 22 Sep) gets its **Open The Yard** menu button from
   `bot.py`, which sets it to `PUBLIC_URL` every time it starts. On 22 Sep,
   before its first start, the new bot's menu button was still Telegram's
   default. ngrok must be running for the Mini App to open. `RUNBOOK` Phase 18
   has the check-in-order list.
4. **Tailscale Funnel** is the event-day plan and is not set up yet
   (`RUNBOOK` Phase 14). Confirm the non-commercial question first.
5. **Packages** are installed in the venv and pinned in `requirements.txt`:
   Flask, python-telegram-bot, python-dotenv, openpyxl, pillow, waitress,
   requests, qrcode, pytest.

6. **Paperform** — the sign-up form. Its export's receipt links are signed
   and expire exactly 7 days after each submission, so the current ones die
   on 22–23 Sep 2026, before the event. It is not known whether a fresh export
   gives fresh links (`STATE.md` open question 8).

   **Since 18 Sep there is a lasting fix:** `python manage.py fetch-receipts`
   (or **Save receipt copies** on the console's Audit screen) downloads each
   screenshot onto the laptop, where it does not expire. **It must be run
   before 22 Sep 15:26** — nothing can copy a link that has already died.
   Until it is run, verifying every payment before that time is the fallback.
   **As of 22 Sep 15:36 it had not been run:** the list is now 152 people
   with links, none saved, 3 already dead, the next dying at 17:06 that day
   and the rest over the following days (7 days after each sign-up). Run it
   now, and again after every new import.

## `.env`

Holds (checked 17 Sep 2026): `TELEGRAM_TOKEN`, `FLASK_SECRET_KEY`,
`ADMIN_PASSWORD_HASH`, `STAFF_PIN_HASH`, `GM_PIN_HASH` and `PUBLIC_URL`.
Console sign-in refuses any role whose hash is missing. To change one, run
`python manage.py set-admin-password`, `set-staff-pin`, `set-gm-pin`; they
write the hash into `.env` for you. Then restart `app.py`. `PUBLIC_URL` is
set since 17 Sep to the ngrok address (`python manage.py set-public-url
<address>` changes it; then restart app.py and bot.py). `bot.py` uses it for
the Open The Yard buttons and the menu button. Never commit `.env` anywhere
public.

**Three windows now, not two:** `app.py`, ngrok, and `python bot.py`. No
bot message goes out unless the bot window is open — and since 22 Sep that
includes the escape-room phone itself. Messages start in test
mode (only `@maxi_muslim`); `python manage.py notify on` switches them on for
everyone.

**Watch for duplicate servers.** On 17 Sep, sign-in kept saying "not set yet"
after the hashes were written. An `app.py` started at 03:17 was still
listening on port 5000 alongside the new one (Windows allows this without the
"port in use" error). That old copy had read `.env` before the hashes existed.
When a change seems to have no effect, check
`netstat -ano | Select-String ":5000"` for more than one `LISTENING` line
first.

**`python app.py` reloads itself whenever a `.py` file is saved** (it runs
Flask's development mode, `debug=True`; templates are re-read too). Found on
22 Sep: an agent's edit to `config.py` went live in the organiser's running
app within seconds and seeded new settings into the real database. So an
agent must not edit code while the organiser's `app.py` is serving people —
ask them to close it first, as they did on 22 Sep — and a half-finished save
can stop it outright. On the night, `scripts\start_event.ps1` runs waitress,
which never reloads. **Test time is global**: while Settings → Clock is on
Test time, every attendee sees the 24th at that minute.

**Since 22 Sep the escape-room phone reaches players only through `bot.py`**
(a message with an "Open the phone" button). The bot window is no longer
optional during a game.

## Browsers

The console's sign-in cookie is marked secure. Use Chrome or Edge for
`http://localhost:5000/admin` on the laptop. On phones, always use the
`https://` tunnel address. QR scanning in Booth mode needs Chrome on Android;
on an iPhone, volunteers type the code.

**The console has two sign-ins since 22 Sep: Mobile and Laptop.** Laptop is
the admin password. Mobile takes **either** the staff PIN or the GM PIN, and
both open the same phone screens — Booth, Orders, the game (solution included)
and People. The organiser chose one phone PIN for all of it (`STATE.md`
decision 126), so a phone PIN should only go to people it's fine to show the
solution to. `bot.py`'s `/actor` command still asks for the GM PIN specifically.

**Microsoft Edge doubles as a test browser** (since 21 Sep).
`scripts\tap_through.mjs` and `scripts\motion_frames.mjs` drive the installed
Edge headlessly over its DevTools port to tap through the Mini App and capture
the Up next animation frame by frame. Node on this laptop is **v20**, which
only has `WebSocket` behind a flag, so they run as
`node --experimental-websocket scripts\<name>.mjs`. Headless Edge will not go
narrower than about 500px, so its screenshots are a wide phone, not a real one.

## How the organiser works, and what they need from you

The organiser is **not a developer** and is learning as they go. Every
instruction written for them must be:

1. **Numbered**, one action per step.
2. **Copy-paste ready**, in PowerShell syntax, with nothing to substitute.
3. **Followed by what they should see**, plus what to do if they see something
   else.

Expect screenshots of terminal output when something fails. Diagnose from the
actual error text rather than assuming the step ran as described.

Two files exist specifically for them, and are worth keeping current:
`TESTPLAN.md` (the one testing list, split into a part they can do alone and a
part needing a group) and `HOW_IT_WORKS.md` (the five layers, and which layer
each error message is actually about). A third, `DEPLOY.md`, is not for them:
it is for the friend who is hosting the app on a real server instead of the
laptop and its tunnel (22 Sep, `STATE.md` 134). The code lives in a **private**
GitHub repository; `.gitignore` keeps `.env`, the database, the Paperform
exports and the saved receipts out of it. The second was written after an evening
was lost to a crash that the console reported as a network failure — the
organiser could not tell the two apart, and nothing in the docs helped them.

## Corrections to the previous version of this file

The earlier status file is superseded. Three of its statements were wrong or are
now out of date, and acting on them would waste time:

- It said free ngrok sessions expire after about two hours and hand out a new
  random URL each restart, so BotFather needs re-pasting constantly. **No
  longer true.** Free accounts get one fixed dev domain and endpoints no longer
  time out, so the URL should survive restarts. This is also noted in
  `BUILD_SPEC.md` §7.4.
- It named **Render** as the permanent hosting plan. **This was rejected on
  22 Sep and then reversed — the app runs on Render now** (23 Sep), built from
  GitHub. The reason for the original rejection has not gone away and is worth
  keeping in view: Render's free tier wipes the filesystem on restart, redeploy
  or spin-down, which erases the database and every uploaded receipt unless a
  persistent disk is attached. **Check that before the event, not after.**
  `render.yaml` and `DEPLOY.md` are the files that say how it is set up, and
  `ESCAPE_ROOM_PLAN.md` section 1e lists two things about the live setup that
  only the organiser can confirm.
- It described `/api/save` and a planned `database.py` with `save_response()`.
  **Gone.** That was scaffolding from the first prototype. The real schema is
  `BUILD_SPEC.md` §8, implemented in `db.py`; `database.py` is an empty leftover
  and can be deleted.
