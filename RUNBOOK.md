# RUNBOOK — The Yard

Your step-by-step guide. Everything here uses Windows PowerShell.

This project isn't one piece of code. It's several systems working together:
your terminal windows, Flask, the bot, the tunnel, BotFather, Telegram and the
desk devices. So this guide explains how they connect, not just what to type.

**Every step is laid out the same way:** the goal, why it matters, the exact
commands, what you should see, and what to do if you see something else.

Where a step can fail in several ways, screenshot the **whole window** and send
it with the step number. Menu labels in BotFather, Tailscale and phone settings
change over time, so this guide describes what to look for rather than exact
button names.

---

## Phase 1 — How it fits together

**Goal.** Understand the shape of the thing before you touch it.

You run **three windows** on event day:

| Window | Command | What it does |
|---|---|---|
| Web | `waitress-serve …` | The app itself. Serves the Mini App, `/admin` and the API |
| Bot | `python bot.py` | Talks to Telegram: `/start`, `/pass`, photos, reminders, actor lines |
| Tunnel | `tailscale funnel 5000` | Gives your laptop a public HTTPS address so Telegram can reach it |

**In plain words:**

- **Flask** is the web server. It's the Python program that answers when a
  browser or Telegram asks for a page.
- **SQLite** is the database: one file, `data\app.db`, holding everyone and
  everything. Because it's a single file, backing it up is copying a file.
- **The bot** is a separate program. It uses *long polling* — it phones Telegram
  and asks "anything new?" It only makes outgoing calls, so it needs no tunnel
  and no public address.
- **The tunnel** (Tailscale Funnel, or ngrok as a fallback) gives your laptop a
  public `https://` address that forwards to `localhost:5000`. Telegram requires
  HTTPS and can't reach `localhost`.
- **BotFather** is Telegram's bot for managing bots. It's where you tell
  Telegram which URL your Mini App lives at.
- **initData** is a signed blob Telegram puts in the page when it opens your
  Mini App. It says who the user is. The server checks the signature with your
  bot token, which is why nobody can fake being someone else.
- **venv** is the folder holding this project's own copy of Python's packages,
  so they don't clash with anything else on your machine. You must *activate* it
  in each new PowerShell window.
- **`.env`** holds secrets: the bot token, the secret key, the password hashes.
  It never goes anywhere public.

**Where things live** — inside `C:\Users\endrw\my-mini-app`:

```
app.py             the web process
bot.py             the bot process: /start, /pass, /help, /actor, and the messages
manage.py          one-off commands you run by hand
config.py          reads .env and holds the default settings
db.py              the database: tables, backups, the audit log
auth.py            who someone is: Telegram checks and console sign-in
services\          the working parts, one file per area — roster, claims, people,
                   bookings, game, admin, export, receipts, notify
templates\         index.html (the Mini App), admin.html (the console)
static\            the logo and the demo QR the two pages load
private\phone\     the escape-room phone file
private\phone\assets\  its pictures — see the README in there
private\gm\        the GM's script: hint lines and the changeover list. SPOILERS
private\receipts\  our own copies of the Paperform payment screenshots
data\app.db        the database
data\backups\      automatic copies
imports\           Paperform exports you drop in
scripts\           start_event.ps1, check_pages.mjs
tests\             the automatic checks — run them with: python -m pytest tests -q
```

**Two guides sit beside this one.** `TESTPLAN.md` is the single list of what to
test and in what order. `HOW_IT_WORKS.md` explains the five layers and which
one an error message is really about — read it when a symptom is not in
Phase 18's table.

**What is built so far** is always listed in `STATE.md` in the project folder.
Read that if you ever lose track of which parts are real and which are still
showing demo data.

**Why the desk devices run on their own.** The phone prop must never fail. If it
went through the app, it would depend on your laptop, the tunnel and the venue's
signal all working at once. So the desk devices hold their own copy of the phone
file and play it offline. The in-app phone is a bonus view for the desk half,
and the GM can switch it off at any time without affecting the game.
**Since 22 Sep** it goes to everyone in the game, and only as a message from
the bot with an **📱 Open the phone** button — so it needs `bot.py` running
and Settings → Who gets messages → **Everyone**. It stays open 25 minutes
from the start. The GM screen marks anyone the message can't reach; hand
them the desk handset.

---

## Phase 2 — Save a copy first

**Goal.** Have something to go back to.

**Why.** You're about to add a lot of files to a project that already works.

```powershell
cd C:\Users\endrw
Copy-Item -Recurse -Force .\my-mini-app .\my-mini-app-backup-before-theyard
```

**You should see** no output, and a new folder `my-mini-app-backup-before-theyard`.

**If you see** "Access is denied" — close VS Code and any PowerShell window
sitting inside the folder, then try again.

---

## Phase 3 — Install the packages

**Already done.** The packages are installed in your venv and pinned in
`requirements.txt`. Run this phase again only if you rebuild the venv or move
to another machine.

**Goal.** Get the new libraries into the venv you already have.

**Why.** The app needs a few things beyond Flask: Excel reading, image hashing,
QR generation and a production web server.

```powershell
cd C:\Users\endrw\my-mini-app
venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install flask "python-telegram-bot[job-queue]" python-dotenv openpyxl pillow waitress requests "qrcode[pil]" pytest
python -m pip freeze > requirements.txt
```

**You should see** `(venv)` at the start of your prompt, then a run of
"Successfully installed …" lines, then a new `requirements.txt` in the folder.

**If you see** "python is not recognized" — you're not in the project folder, or
the activate line didn't run. Run the first two lines again on their own.

**If you see** an execution-policy error on `activate`, run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

## Phase 4 — Add the new files

**Goal.** Put the handoff into place and fill in your secrets.

**Why.** These files are the app. `.env` is what makes it yours.

1. Copy the handoff files into `C:\Users\endrw\my-mini-app`, keeping the folder
   structure. Your existing `templates\index.html` gets replaced — that's
   expected, and Phase 2 has your copy.
2. Create the folders that must exist but start empty:

```powershell
New-Item -ItemType Directory -Force data, data\backups, imports, private\receipts, private\phone
```

3. Copy `.env.example` to `.env`, then open `.env` in VS Code:

```powershell
Copy-Item .env.example .env
code .env
```

4. Keep the `TELEGRAM_TOKEN` line you already have. Then generate the rest:

```powershell
python manage.py make-secret
python manage.py set-admin-password
python manage.py set-staff-pin
python manage.py set-gm-pin
```

Each command prints a line to paste into `.env`, or writes it for you and says so.

**You should see** an `.env` with `TELEGRAM_TOKEN`, `FLASK_SECRET_KEY`,
`ADMIN_PASSWORD_HASH`, `STAFF_PIN_HASH`, `GM_PIN_HASH`, `PUBLIC_URL`,
`ALWAYS_ALLOW_HANDLES=maxi_muslim` and `TIMEZONE=Asia/Singapore` filled in.

**The console needs these before anyone can sign in.** Until a password or PIN
is set, the sign-in screen refuses that role and tells you which command to
run. Each command asks you to type the secret twice and shows nothing while
you type — that is normal. After running them, restart `app.py` so it reads the
new `.env`.

**Since 22 Sep there are two sign-ins: Mobile and Laptop.** Laptop is the admin
password and everything. Mobile is a phone PIN and the booth, orders, the game
and looking someone up. **Either the staff PIN or the GM PIN works on Mobile**,
and both open the same screens, **the game's solution included** — you chose
one phone PIN for everything (`STATE.md` decision 126). So only give a phone
PIN to people you are happy to see the solution.

**If you see** "No such file or directory: .env.example" — the handoff files
didn't land in the project root. Check you didn't copy a folder *containing* the
files instead of the files themselves.

---

## Phase 5 — Create the database

**Goal.** Make `data\app.db` exist, with all the tables.

```powershell
python manage.py init-db
Get-ChildItem data
```

**You should see** "Database created" (or "already up to date"), then `app.db`
listed with a size of a few hundred KB.

**If you see** "database is locked" — something else has the file open. Close
any other PowerShell window running the app, then retry.

---

## Phase 6 — Import the roster

**Goal.** Get your 17 sign-ups into the database.

**Why.** This list *is* the gate. Nobody gets into the app unless they're on it.

1. Export from Paperform and put the file in `imports\`.
2. Then:

```powershell
python manage.py import imports\The_Yard_Sign_Up_Responses.xlsx
```

**You should see** `Read 17 sign-ups from ...`, then a preview line reading
**17 new, 0 changed, 0 unchanged, 0 missing, 3 without a receipt**, and no
problems. The ~1,000 blank rows are skipped silently.

3. It asks you to confirm. Type `yes`.

**You should see** "Committed: 17 people."

Re-running it afterwards says "Nothing to change" — re-importing the same file
is always safe. To skip the question (for example inside a script), add `--yes`
to the end of the command.

To see who is on the list at any point:

```powershell
python manage.py roster
```

**If the count is wrong** — if it says 1,017, blank-row skipping failed; send me
the output. If it says 0, the sheet name isn't "Registrations".

**If it lists problems** — duplicate or invalid usernames, or invalid emails —
nothing has been written. Fix them in Paperform, re-export, and run it again.
Re-importing the same file is safe and changes nothing.

---

## Phase 7 — Generate the games and the jam slots

**Goal.** Fill the escape-room board. (Already done on 17 Sep. Running it
again is harmless: it never makes duplicates.)

```powershell
python manage.py generate-slots
```

**You should see** "Escape games: 21 in total (…)", "Jam slots: 14 in total
(…)", and "Settings say escape games 3:05 PM-9:45 PM and jam slots 3:00
PM-9:30 PM." Running it again changes nothing. (Since 22 Sep: doors 3–10 PM,
and games 3:05–9:45 so the last one ends with the doors — `STATE.md` 133.)

**If you see** "Still booked, so kept: …" — someone is booked on a game that no
longer fits the times. Cancel or move them, then run it again.

**If the counts are wrong** — restart `app.py` first (it updates the Settings
on start), then run it again. The times come from Settings: game 15 minutes,
changeover 5, first game 3:05 PM, last 9:45 PM, capacity 12; jam 3:00 to
9:30 PM, 30 minutes (the last jam slot ends at 10:00).

---

## Phase 8 — Run the app locally

**Goal.** See `/admin` in your own browser before Telegram is involved.

```powershell
python app.py
```

Leave this window running. In **Chrome or Edge** open
<http://localhost:5000/admin> and sign in with the admin password from Phase 4.
(The sign-in cookie is marked secure. Chrome and Edge accept that on
`localhost`; some other browsers don't. On phones you always use the `https://`
tunnel address, where every browser works.)

**You should see** the console with the Overview screen open.

**While the console is still being built,** sign-in, **Booth mode** and
**People** are real: a wrong password is refused, hand-overs, check-ins and
payment verdicts are written to the database, and People shows your real
sign-ups, and **Schedules** shows the real games and jam slots. Refreshing
the page keeps you signed in. **Every other screen is real too** now —
Overview, GM, Roster, Settings and Audit all read your own data; nothing in
the console is a demo any more (`STATE.md` §3). Overview's top line reads
"N signed up, N opened the app, N at the event": opening the app is anyone who
has linked their Telegram account, at any time, while **at the event** counts
people from 3 PM on the 24th only, and counts them **two ways** — the front
desk scanned them, **or** they redeemed something on their pass. Either one is
enough and both together still count the person once (23 Sep, `STATE.md` 135;
24 Sep, 152). The third way in is the **Mark here** button beside each name on
**People**, for somebody who has collected nothing and whose pass will not
scan.

**If you see** "No admin password is set on this laptop yet" — run
`python manage.py set-admin-password` (Phase 4), then restart `app.py`.

**If you see** "port 5000 already in use":

```powershell
Get-NetTCPConnection -LocalPort 5000 | Select-Object -ExpandProperty OwningProcess
Stop-Process -Id <the number it printed>
```

**If you see** ModuleNotFoundError — the venv isn't active in this window. Run
`venv\Scripts\activate` and try again.

---

## Phase 9 — Start ngrok for development

**Goal.** Give today's testing a public address.

**Why.** Telegram will not open `localhost`.

Open a **second** PowerShell window:

```powershell
ngrok http 5000
```

**You should see** a `Forwarding` line with your fixed dev domain,
`https://moonlight-dwelling-footpad.ngrok-free.dev` (checked 17 Sep; it is the
address the bot's **Open App** button uses). Copy it.

**If the Forwarding line shows a different address**, stop ngrok (Ctrl+C) and
ask for your domain by name:

```powershell
ngrok http --url=moonlight-dwelling-footpad.ngrok-free.dev 5000
```

**Keep this window open all the time you are testing.** Closing it, or the
laptop sleeping, takes the Mini App offline even though `app.py` is still
running.

1. Open that URL once in your own browser and click through ngrok's warning
   page. A cookie hides it for 7 days.
2. Put the same URL in `.env` as `PUBLIC_URL`, then restart `app.py`
   (Ctrl+C in the first window, then `python app.py`).
3. Keep <http://127.0.0.1:4040> open in a tab — it's ngrok's request inspector.
   You'll use it in Phase 12 to count requests.

**If you see** "ERR_NGROK_108" — another ngrok session is already running.
Close the other window, or run `taskkill /IM ngrok.exe /F`.

---

## Phase 10 — Point Telegram at it

**Goal.** Make the bot open *this* app.

1. In Telegram, message **@BotFather** → the Mini Apps / Web App area for your
   bot → edit the app's URL → paste the ngrok URL. Labels move around; look for
   the option about the app's link or URL.
2. `bot.py` sets the chat menu button itself when it starts, so you don't set
   that by hand.
3. When you test `/start` in Phase 11, check the "Open The Yard" button is an
   **inline** button attached under the message — not a button in the keyboard
   area at the bottom of the screen.

**Why that matters.** Telegram sends no user data to a Mini App opened from a
keyboard-area button, so the gate would refuse everyone, including you. If that
happens, this is the first thing to check.

---

## Phase 11 — Run the bot

**Built 17 Sep.** The bot answers `/start`, `/pass` and `/help`, and sends the
messages the app queues (booking confirmations, reminders, group changes,
payment verdicts, doors open, last call). **It must be running for any message
to go out.** If it isn't, `/start` gets no reply and messages wait.

Open a **third** PowerShell window (app and ngrok stay in theirs). **Always
type all three lines**, even if the window seems to be in the right place —
a new window starts in `C:\Users\endrw`, and the bot only runs from the
project folder with `(venv)` at the start of the line:

```powershell
cd C:\Users\endrw\my-mini-app
venv\Scripts\activate
python bot.py
```

**You should see** "Menu button points at https://moonlight-…", a
"Messages: TEST MODE…" line, then "Bot started, polling". Leave it open.

**Messages start in test mode.** Only `@maxi_muslim` (and other always-allowed
accounts) get messages; everyone else's are held back and never sent later.
When you are ready for real attendees to get them:

```powershell
python manage.py notify on
```

`python manage.py notify owner` goes back to test mode, and `notify off`
stops all messages. The bot picks the change up by itself.

In Telegram, send `/start` to your bot.

**You should see** "Hi … — you're on the list for The Yard" and an
**Open The Yard** button under the message. Tap it: the Start gate appears,
and you're let through as `@maxi_muslim`. `/pass` sends your pass as a picture.

**If you see** `can't open file 'C:\Users\endrw\bot.py'` or
`No module named 'telegram'` — you skipped the `cd` or the `activate` line.
Type all three lines again.

**If you see** "Unauthorized" in the bot window — the token in `.env` is wrong
or has a stray space.

**If you see** "Another bot.py is already running" — close the other bot
window. Only one can run.

**To see what the bot has sent:**

```powershell
python manage.py outbox
```

It lists the last 20 messages and what happened to each (sent, held back,
never opened the bot, and so on).

**If the app loads but refuses you** — see the troubleshooting table, row
"everyone refused at Start".

---

## Phase 12 — Test everything in Telegram

Work through the acceptance checklist in BUILD_SPEC §17, in order. You need a
friend's Telegram account for the "not on the list" case.

For the timing tests, Settings → **Clock** → **Test time**, then slide to the
minute you want and Save. The app then thinks it is **Thu 24 Sep** at that
minute, and stays there until you move the slider (since 22 Sep; it used to
keep today's date). You'll see a loud banner on every admin screen while it's
on — that's deliberate. **Every attendee who opens the app sees the test time
too**, so keep it short and put the Clock back to **Real time** when you
finish.

**Watch the ngrok inspector** while you do one ordinary attendee visit: open the
app, check the pass, book a game. It should make **six requests or fewer**.

---

## Phase 13 — Booth rehearsal (the P0.2 test)

**Goal.** Prove the once-only rule with real hands and real phones.

**Why.** Two booths can scan the same pass in the same second. The database
must let exactly one of them hand over, and tell the other one who did.

**You need:** the laptop, two phones (yours and a helper's), and ngrok running
(Phase 9). Only `@maxi_muslim` has a verified payment so far, so every
hand-over test uses *your own* pass. The 17 imported people show as "Not
verified" until payments are reviewed. That is the rule working as it should.

**A. Set the password and PINs (once)**

1. In the PowerShell window running `app.py`, press **Ctrl+C** to stop it.
2. Run these one at a time. Each asks you to type the secret twice; nothing
   shows on screen while you type:

```powershell
cd C:\Users\endrw\my-mini-app
venv\Scripts\activate
python manage.py set-admin-password
python manage.py set-staff-pin
python manage.py set-gm-pin
```

**You should see**, after each one, a line like
"The staff PIN saved to C:\Users\endrw\my-mini-app\.env as a hash."

**If you see** "Too short" — the admin password needs 8 or more characters, a
PIN needs 4 or more. Run that command again.

3. Check the automatic tests still pass, then start the app again:

```powershell
python -m pytest tests -q
python app.py
```

**You should see** `408 passed`, then Flask's "Running on
http://127.0.0.1:5000". Leave that window running.

**If you see** anything other than `408 passed` — stop, and screenshot the
whole window.

**B. Your pass in Telegram**

4. On your phone, open The Yard in Telegram and tap **Start**, then
   **Your pass**.

**You should see** a real QR code (no longer the demo picture), your pass code
under it (like `7K3M-Q9XT`), and three things marked **Ready**: **Pastry**
(with "Tart or cookie" under it since 23 Sep), **Photo Strip** and
**Vinyl Crafting**.

**If you see** "Payment not verified yet" — payment checking has been switched
back on (Settings → **Hand-over needs payment**), and this account has not been
verified. Since 22 Sep it is set to **Not needed** and nobody sees that line
(`STATE.md` 138).

5. Write your pass code down. You can also see it on the laptop:

```powershell
python manage.py roster
```

It is the last column on the `@maxi_muslim` row.

**C. Two booths**

6. On **phone A**, open a normal browser (Chrome or Safari, not Telegram) and
   go to your ngrok address followed by `/admin`, for example
   `https://your-name.ngrok-free.app/admin`. Click through ngrok's warning page
   if it appears.
7. Tap **Mobile** (a phone opens on it already). Enter the phone PIN, then
   **Sign in**. Since 23 Sep that is the whole sign-in — the name and
   "where you are" boxes are gone, because filling two boxes on a counter
   phone every shift was the friction.

**You should see** Booth mode, with **Mobile** at the top, and only four
tabs: **Booth, Orders, Game, People**.

**If you see** "That did not match" — the PIN is wrong. After 5 wrong tries it
makes you wait 5 minutes.

8. On **phone B**, do the same. Nothing distinguishes the two phones now, which
   is the trade: hand-overs are logged with their time and the role, but no
   longer with a volunteer's name.
9. On both phones, type your pass code into the box and tap **Look up**.
   (Or point the camera at the QR on your own phone. If the viewfinder says
   "Type the code below" or "Scanning failed", use the box below instead — it
   always works, and a scan fills that same box anyway.)

**You should see** on both: a green **Valid** card, your name, three buttons
under "Hand over a pastry" — **Mini Tart, Mini Cookie, Shiopan** (the brownie
went on 23 Sep) — and a big **Hand over photo strip** and **Hand over vinyl
crafting** button. Tapping a pastry kind hands the pastry over and records
which one. The
camera stops after one read, and it stays off
until you tap **Scan next** or tap the full-screen result.

**Check that a scan reads only once:** scan the QR, then keep it in front of
the camera for 10 seconds. In the `app.py` window you should see **one**
`GET /admin/api/lookup/...` line for that scan, not a new one every second.
**If you see** new lookup lines while the QR stays in view — stop and tell me.
If the viewfinder says "Tap Scan next to scan again", the lookup didn't get
through (too many lookups, or no connection). Tap **Scan next** to try again.

10. Count down, and both tap **Hand over photo strip** at the same moment.

**You should see** one phone go **full-screen green** ("Photo strip handed
over", with the time, station and name). The other goes **full-screen red**:
"Photo strip already collected", then "at 7:14 PM (Booth 1, Wei)", naming
whoever won.

**If both go green — stop and tell me.** That means the once-only rule
failed. Don't carry on testing.

11. In Telegram, close The Yard, open it again, and go to **Your pass**.

**You should see** Photo strip marked **collected**, with the time, the booth and the
name of whoever won.

**D. Run it again**

12. To put the photo strip back so you can repeat step 10:

```powershell
python manage.py void-claim maxi_muslim photo "booth rehearsal"
```

**You should see** "Voided photo for @maxi_muslim (…). They can collect it
again." The claim isn't deleted — it's marked void, and the audit log keeps it.

**If you see** a "nothing to void" message — nothing has been handed over yet, so
there's nothing to undo.

**E. The other cases**

13. Tap the red or green screen to clear it, then try each of these on one
    phone:

| Do this | You should see |
|---|---|
| Type `ZZZZ-ZZZZ` → Look up | Slate card: **Unknown code** — "probably a typo" |
| Point the camera at any other QR (a product, a website) | Slate card: **Not a Yard code** |
| Type the pass code of an imported person (from `python manage.py roster`) → Look up | Green **Valid** card with the hand-over buttons. *(Since 22 Sep payment is not checked at all — `STATE.md` 138. Set **Settings → Hand-over needs payment** back to **Verified** and this reads amber **Not verified**, with no hand-over button.)* |
| Look up your own pass → **Check in** | Green: **Checked in**, with the time and "Wei · Booth 1" |
| Tap **Check in** again | Slate: **Already checked in**, showing the first time and name |
| Open **People**, find somebody who has collected nothing, tap **Mark here** beside their name | The button turns into a green **Here**. Overview's **At the event** goes up by one |
| Hand that same person a pastry on **Booth**, then look at **People** again | Still **Here**, and **At the event** has **not** gone up again — both ways in count the person once |
| Find somebody nobody has scanned who has already collected something | Already **Here**, with no button to press. Hovering it says which way they counted, and when |
| Look at the top bar on a Mobile sign-in | Only **Booth, Orders, Game, People** — Settings and the rest are Laptop only |
| Tap **Sign out** | Back to the sign-in screen |

14. On the laptop, sign in on **Laptop**, open **Booth**, and look up an
    imported person's pass.

**You should see** the green **Valid** card and the hand-over buttons: since
22 Sep payment is not a gate (`STATE.md` 138), so there is nothing to
override. *(With **Hand-over needs payment** set back to **Verified**, this is
the amber **Not verified** card with **Override — hand over …** buttons.
Tapping one asks for a reason; with a reason it hands over and records your
reason in the log. Undo it afterwards with `void-claim`, using that person's
username — step 12.)*

Searching for someone whose phone died is rehearsed in Phase 13b.

---

## Phase 13b — People and payments (the P0.3 test)

**Goal.** Find anyone in seconds, check their payment against the screenshot,
and prove a reference can't be used twice.

> **Since 22 September, none of the verifying in this phase is needed.**
> Payments are not checked at all (`STATE.md` 138): the booth hands over to
> anyone on the list, and the person page has no Verify, Reject or reference
> box — only the screenshot, to look at if you want. **145 of 152 screenshots
> are saved on this laptop**, so they open with no Paperform and no wifi.
> The rest of this phase still describes finding people, which you will use,
> and it is what you would follow if you ever set **Settings → Hand-over needs
> payment** back to **Verified**.

**Why (when payment is checked).** The booth refuses anyone whose payment
isn't verified, so the payments you verify here stay verified.

**The receipt links have expired.** Each one stopped working exactly 7 days
after that person signed up — the first on 22 September at 3:26 PM. That is
why copies were saved on 22 September; the 7 whose links had already died are
named in `CHANGELOG.md` and exist only in Paperform's own dashboard.

**A. Restart with the new code**

1. In the PowerShell window running `app.py`, press **Ctrl+C**. Then:

```powershell
cd C:\Users\endrw\my-mini-app
venv\Scripts\activate
python -m pytest tests -q
python app.py
```

**You should see** `408 passed`, then "Running on http://127.0.0.1:5000".

**If you see** anything other than `408 passed` — stop, and screenshot the
whole window.

**B. Search (laptop, Chrome or Edge)**

2. Open <http://localhost:5000/admin>, sign in as **Admin**, and click
   **People** in the top bar.

**You should see** your real sign-ups on the left, 18 people with you, and
the first one open in the middle. Nobody called "Nadia Rahim" (that was demo
data). Each row says `pending`, `verified` or `no receipt`, plus
`never opened` if they haven't opened the app yet.

3. Click the search box and type part of someone's name. Wait half a second.

**You should see** the list shrink to the people who match, and the box keeps
your typing. Clear it and try a username with `@`, then your own pass code.
Each finds the right person.

**C. Verify a real payment**

4. Click someone marked `pending`, then click the **Open** tile under
   "Entrance payment".

**You should see** their Paperform screenshot in a new tab.

**If you see** "The Paperform link has expired" — find that person's
screenshot in Paperform's own dashboard, or try a fresh export and re-import
(Phase 6).

5. Find the transaction reference on the screenshot. Type it into
   **Transaction reference** and click **Verify payment**.

**You should see** the card turn green: "Verified by Organiser at … against
reference …". The Audit trail below gets a "Payment verified — ref …" line,
and their row on the left now says `verified`.

**If there is no reference on the screenshot** — click **No reference on it**
and type why, for example "cropped above the reference". The card says
"Verified without a reference".

**D. The same reference twice**

6. Click a *different* `pending` person. Type the **same reference** you just
   used, and click **Verify payment**.

**You should see** a red message: "Reference … already proved @…'s entrance
payment. The database refuses it." Their card stays amber.

**If their card turns green — stop and tell me.** That means the reference
check failed. Don't verify anyone else.

7. Clear the box. Verify this person properly from their own screenshot, or
   leave them for later.

**E. Change a verdict**

8. Go back to the person from step 5 and click **Change verdict — reason
   required**. Type a reason, such as "practice".

**You should see** the card go back to amber ("Waiting on you"), with the
reason in the Audit trail. Their reference is released, so you can type it
again. Verify them again (step 5).

**F. Booth, then undo from the person page**

9. On a phone, sign in on **Mobile** (Phase 13, step 7) and type the pass code
   of the person you verified. It is under "Pass" on the right of their person
   page.

**You should see** a green **Valid** card — they're verified now.

10. Under "Hand over a pastry", tap **Mini Tart**. Then on the laptop, open
    that person again (or wait — the page refreshes itself every 30 seconds).

**You should see** under Claims: "Pastry — Mini Tart, [time] · Booth 1 · Wei",
and a red **Void pastry — reason required** button.

11. Click it and type "rehearsal".

**You should see** "Voided — they can collect it again", and Pastry
back to "not collected". (On Overview, the Pastry card counts each kind, so
you can see which ones are going.)

**G. What staff see**

12. On the phone, still signed in as Staff, tap **People** and search for
    someone.

**You should see** their page, but no Verify buttons ("Only an admin can
verify or reject"), and no "Refused at the gate" panel. Tapping the receipt
tile says "Only an admin can open receipts."

**Built 18 Sep:** Link / Dismiss on the gate list, and Unlink Telegram
account. If someone signed up with the wrong username, **Link** ties their
Telegram account to the right person and clears every refusal from that
account at once — no Paperform edit and no re-import needed. It refuses if
either side is already linked to somebody else, which is the check that stops
two people sharing one pass.

---

## Phase 13c / 13d — Testing: see TESTPLAN.md

The step-by-step testing detail that used to live here has moved to
**`TESTPLAN.md`** in the project root, so there is one list to keep correct
rather than two that drift apart.

It is split by what each test needs, not by when you do it:

- **Part A — you, one phone, about 30 minutes.** The gate, your pass, the
  booth scanner and its once-only rule, booking, the jam room, the bot, the
  GM console, the phone, the receipt copies, Settings.
  Everything that can be proved alone. **Run this first.**
- **Part B — the crowd, about 90 minutes.** Group booking all-or-nothing,
  the actor, two phones in one game, two booths racing for one pass. Book it for **21 or 22 September**, so there
  is a clear day afterwards to fix what it finds.

Part A exists because a broken tunnel or a broken Telegram sign-in stops
*everything* in Part B, and finding that out with eight people waiting wastes
their evening as well as yours.

**After the 21 Sep UI pass**, Part A step 28b checks the Up next card growing
into Your bookings, and 28c is a table of every button and where it should
land. Do both on your own phone before Part B, so the crowd tests the screens
as they will be on the night.

**Before the day:** run `python manage.py notify on` once testing is done —
until you do, no real attendee gets any message at all.

### One thing here has a hard deadline: 22 September, 3:26 PM

Paperform signs each payment-screenshot link to expire **seven days after that
person signed up**. Every link in the current export dies between 22 Sep 15:26
and 23 Sep 17:42 — before the event. After that, a payment you have not already
verified cannot be checked from the person page at all.

Take your own copies while the links still work:

```powershell
cd C:\Users\endrw\my-mini-app
venv\Scripts\activate
python manage.py fetch-receipts
```

**You should see** "Saved 14, skipped 0, failed 0", then "Every receipt now has
a copy on this laptop."

**If you see** any `FAILED @handle` lines, those files are still in Paperform's
own dashboard — only the links we were handed have expired. Open them there.

The console does the same thing: **Audit → Exports & backups → Save receipt
copies**, on a card that shows the exact deadline and how many are left.

Once copied, the person page shows "Saved copy" instead of the Paperform link,
and it keeps working on the day with no tunnel and no Paperform.

---

## Phase 14 — Set up Tailscale Funnel for event day

Do this once, before the day.

**Why.** Funnel gives you a fixed public address with a proper certificate and
no warning page, and it doesn't have ngrok's monthly request limit.

1. Install Tailscale for Windows and sign in.
2. **Rename the laptop** in the Tailscale admin console — to `theyard`, for
   example. The name becomes part of your public address, so do it before you
   paste that address anywhere.
3. Enable HTTPS certificates and Funnel for your tailnet when Tailscale prompts
   you. It walks you through it the first time you run the next command.

```powershell
tailscale funnel 5000
```

**You should see** a line like
`https://theyard.tailXXXX.ts.net` and "Available on the internet".

4. Switch over: put that URL in `.env` as `PUBLIC_URL`, restart `bot.py`, and
   update the Mini App URL in BotFather. Four steps, always in that order.
5. **Test from a phone on mobile data with wifi off.** This is the real test —
   on wifi you might be reaching your laptop locally and not through Funnel at all.

**You should see** the Start gate, with no warning page in front of it.

**Before relying on it,** confirm with me whether The Yard counts as
non-commercial use. The Personal plan is meant for non-commercial use, and we
charge an entrance fee (the app itself takes no money). If the answer is no, we use ngrok on
the day and accept the warning page.

**If the address doesn't load** — Funnel isn't enabled for the tailnet, the
laptop is asleep, or Tailscale is signed out. Check in that order.

---

## Phase 15 — Prepare the desk devices

**Goal.** The escape room works with no laptop, no wifi and no server.

1. Copy `private\phone\the-phone.html` onto each desk device. Email it to
   yourself, or use a cable — anything that leaves a real file on the device.
2. Open it **with wifi off** on every device type you might use, and play
   through a whole game.
   - **iPhone/iPad:** Files → the file → it opens in a browser view. Reliable.
   - **Android:** Files → Open with → Chrome. Usually fine; on some phones you
     need a file-manager app that offers "open in browser".
   - **Laptop:** double-click. Always works.
   - Honest note: Android is the fiddly one. If a device won't open a local HTML
     file, use a different device rather than fighting it.
3. Zoom the kitchen photo and check the wall clock is legible.
4. Lock the device to the phone file: **Guided Access** on iOS (Settings →
   Accessibility), **screen pinning** on Android (Settings → Security). Look for
   the feature that stops people leaving the current app.
5. Turn auto-lock off and keep chargers attached.
6. Print the backup screenshots, put them in an envelope, seal it, and leave it
   at the desk.
7. **Practise the reset.** The phone file has a built-in reset — see the GM card
   for where it is. Do it until it takes you five seconds, because you'll be
   doing it thirteen times with a group watching.

---

## Phase 16 — Event-day setup

1. Use `waitress`, not the development server:

```powershell
waitress-serve --listen=127.0.0.1:5000 app:app
```

2. Or let the script do all three windows for you:

```powershell
.\scripts\start_event.ps1
```

It asks which tunnel to use.

3. Set the laptop to never sleep while plugged in (Settings → Power), and check
   the clock is synced (Settings → Time & language → Sync now).
4. Charger in. Phone hotspot ready as a backup connection.
5. Check `data\backups` is filling up — a new copy every 10 minutes.
6. Print the offline fallback list from `/admin` → Exports.
7. Settings → **Clock** must read **Real time** (red banner gone). Under Bot
   messages, **"The Yard is on today" message** and **Last call** should be
   **On**. (Event-day mode no longer exists — since 22 Sep those two messages
   have their own switches.)

---

## Phase 17 — Event-day runbook

**The day before**
- Final Paperform export, imported and committed.
- Every payment verified on People (before 22 Sep, 3 PM — the receipt links
  expire).
- Desk devices charged, pinned, and tested offline.
- Envelope of printed screenshots sealed at the desk.
- Fallback list printed.

**Two hours before**
- Three windows up via `start_event.ps1`.
- Open the public URL on your own phone on mobile data.
- Staff and the GM signed in on their own phones — the phone PIN and nothing else.
- Test one hand-over on yourself and void it
  (`python manage.py void-claim maxi_muslim photo "pre-event test"`).

**During — what to watch**
- **Overview**, refreshing itself: seats per game, each included item
  collected, payments pending, and a queue of anything needing attention.
  Built 18 Sep. The top bar shows a green **LIVE** while it is streaming
  changes; without it the screen still refreshes every 30 seconds.
- **The front desk.** Unverified payments, food, DIY and the photobooth are all
  paid there, never in the app.
- **The tunnel window.** If it stops, the app goes dark; restart it and the
  address stays the same.
- **Gate denials** on the People page. Walk-ups and typos land there — link or
  add them.

**After**
- Export the Registrations sheet, bookings and claims.
- "Back up now", then copy `data\` somewhere off the laptop.
- Stop all three windows.
- Delete the receipts and anything personal you no longer need.

---

## Phase 18 — Troubleshooting

| What you see | What it means | What to do |
|---|---|---|
| **Mini App doesn't open on the phone**, or shows an error or blank page | Nearly always the tunnel is off: ngrok isn't running, so Telegram's link leads nowhere (`ERR_NGROK_3200`, "endpoint offline") | Work through "Mini App won't open — check in this order" below this table |
| **"Something went wrong at our end"**, or "The Yard answered with an error (HTTP 500)" | **Not** a network fault. The server was reached and crashed; nothing was saved | Read the `app.py` window — the crash is printed there with a timestamp and the real reason on the last line. `HOW_IT_WORKS.md` §3 explains how to read it |
| **"The database refused that change, so nothing was saved"** (409) | Two records clashed — the same username, the same transaction reference — and the database stopped it. Nothing was half-written | The message names the constraint. Usually someone exists twice, or a reference was already used |
| **The roster preview looks right but Commit fails** | Someone in the file already exists under a different kind of record — most often you, because you filled in your own Paperform | Preview the file again and commit that. Fixed 18 Sep; the message now names who clashes |
| **A game shows more people booked than it seats** | Someone lowered the seat count in Settings after those people had booked. Nobody is thrown out automatically | Settings names the game when you save. Move the extra people on the Schedules screen |
| Blank white screen in Telegram | The page errored, or the tunnel is down | Open the public URL in a normal browser. If it loads there, turn on Telegram's Mini App inspecting (last row of this table) |
| **Everyone refused at Start**, including you | The app was opened from a keyboard-area button, so Telegram sent no user data — or the bot token is wrong | Check the `/start` button is an inline button (Phase 10.3). Then check `TELEGRAM_TOKEN` has no stray spaces |
| ngrok warning page | Normal on the first visit | Click through once; a cookie hides it for 7 days. Gone entirely on Tailscale |
| Tailscale address won't load | Funnel not enabled, laptop asleep, or Tailscale signed out | Check in that order. Run `tailscale status` |
| `INITDATA_INVALID` | Wrong bot token, an expired session, or the code used `initDataUnsafe` | Confirm the token matches the bot BotFather points at. Close and reopen the app |
| `INITDATA_EXPIRED` | The session is more than 24 hours old | Close and reopen the app |
| PowerShell execution-policy error | Scripts are blocked | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| `ModuleNotFoundError` | The venv isn't active in this window | `venv\Scripts\activate` |
| Port 5000 already in use | An old `app.py` is still running | `Get-NetTCPConnection -LocalPort 5000` then `Stop-Process -Id <pid>` |
| "database is locked" | Two processes wrote at once, or a stale lock | It should retry by itself. If it persists, stop all three windows and start again |
| "No phone PIN is set on this laptop yet" (or admin password) | That password or PIN was never set in `.env` | Run the command the message names (Phase 13, step 2), then restart `app.py` |
| **A "ready" call on the Orders screen says "Test mode — message not sent"** | Bot messages are still in test mode, so only test accounts get them | Before the event: `python manage.py notify on`. Until then, call their name |
| **A "ready" call says "Can't message them — call their name"** | That person never opened The Yard, or never tapped Allow, so the bot has no way to reach them | Call their name out. Nothing is wrong with the app |
| **The Orders list doesn't change on the matcha machine's phone** | That phone is in the middle of a scan (the camera is open); the list waits until the scan is done | Tap **Done** or **Back to the list** |
| Still "not set yet" after you ran the command and restarted — or changes don't show up at all | **An old `app.py` is still running** in another window or in the background. Windows lets two copies share port 5000 without an error, and the old copy never re-reads `.env` | Run `netstat -ano \| Select-String ":5000"`. More than one `LISTENING` line means an old copy is running. Close every PowerShell window running `app.py`, run `Get-Process python \| Stop-Process`, then start `python app.py` once, in one window |
| "That did not match" at console sign-in | Wrong password or PIN, or you picked the wrong tab (Staff vs GM) | Check the tab. After 5 wrong tries from one phone, it makes you wait 5 minutes |
| "Too many tries. Wait a few minutes." | The sign-in limit (5 wrong tries per phone per 5 minutes) | Wait 5 minutes. Restarting `app.py` also clears it |
| "Your sign-in has ended. Sign in again." | The console sign-in is 12 hours old, or someone pressed Sign out | Sign in again with the phone PIN |
| "Slow down — too many lookups" | More than 30 lookups in a minute from one sign-in | Wait a minute. The limit is the `lookup_rate_limit` setting |
| Both booths went green for the same item | The once-only rule failed | **Stop.** Screenshot both phones and send them |
| The console asks you to sign in again after you reload the page | Normal — a reload forgets the sign-in in that tab | Sign in again with the phone PIN |
| Booth camera won't open | Cameras need HTTPS and permission | Use the public HTTPS URL, not `localhost`. Then allow the camera when asked. The typed code box always works as a fallback |
| BotFather still points at an old URL | You changed tunnels and skipped a step | The four steps in order: run the tunnel, update `PUBLIC_URL`, restart `bot.py`, update BotFather |
| ngrok monthly limit reached | 20,000 requests or 1 GB out, testing included | Switch to Tailscale Funnel (Phase 14) |
| You need to see the error inside Telegram | Mini Apps can be inspected, but the setting is hidden | In Telegram Desktop, open Settings and tap the version number several times until a debug menu appears, then enable inspecting web views. Then right-click inside the Mini App → Inspect |
| **Tapping Up next: the card stutters, flashes or lands in the wrong place** | The grow animation added 21 Sep (`STATE.md` decision 121) is misbehaving on that phone | Turn it off: open `templates\index.html` in VS Code, press Ctrl+F, search `const MORPH = true`, change `true` to `false`, save, then close and reopen the Mini App. Up next still opens Your bookings, with the ordinary short slide. Nothing else changes |
| **On an older iPhone, Up next just slides instead of growing** | Normal. The grow needs iOS 18 or later; older phones get the ordinary slide | Nothing to do |
| **Players say the escape-room phone never arrived** | Since 22 Sep the phone comes only as a bot message, and since 23 Sep it goes out at the **booked time** with nobody pressing anything. Either `bot.py` isn't running, messages aren't set to Everyone, or that person never opened the bot | GM screen: each name says **Phone sent**, **Can't reach — desk handset** or **Not sent (test mode)**. Test mode → Settings → Who gets messages → **Everyone**. `bot.py` window closed → start it. Can't reach → hand them the desk handset, or let them share with their group |
| **"Open Kai Chen's phone" opens a screen saying Not yet** | The booked time hasn't come round. Since 23 Sep that is the whole rule — **there is no Start to press** | Wait for the booked minute; the same button then works. If it says **Locked**, a game master has locked it: GM screen → **Unlock the phone** |
| **The phone says "Time's up" before the group is done** | It stays open 25 minutes from the **booked time**, plus whatever the GM has paused or added | Settings → Escape room → **Phone stays open** — raise it and Save. It applies at once. Mid-game, **Pause** also holds it open for as long as the pause, and **+1 min** adds a minute to both |
| **Your code changes go live the moment you save a file**, or `app.py` restarts by itself | `python app.py` runs in development mode, which reloads itself whenever a `.py` file changes. A half-finished save can stop it | Don't edit code while people are using it. On the night the RUNBOOK's `start_event.ps1` uses waitress, which never reloads |

### Mini App won't open — check in this order

The chain is: **Telegram button → ngrok address → ngrok on your laptop →
`app.py` on port 5000.** The Mini App works only if every link is up. Check
from the laptop end outwards, in a PowerShell window in the project folder.

1. **Is `app.py` running?**

   ```powershell
   Invoke-RestMethod http://127.0.0.1:5000/healthz
   ```

   **You should see** `status : up` inside `data`. **If you see** "Unable to
   connect", start it: `venv\Scripts\activate`, then `python app.py`.

2. **Is ngrok running?**

   ```powershell
   Get-Process ngrok
   ```

   **You should see** one `ngrok` line. **If you see** "Cannot find a process",
   start it in its own window (Phase 9).

3. **Does the public address reach your laptop?** In a phone or laptop
   browser, open
   `https://moonlight-dwelling-footpad.ngrok-free.dev/healthz`.

   **You should see** `"status": "up"`. **If you see** `ERR_NGROK_3200` or
   "endpoint is offline", ngrok isn't running under that address: go back to
   step 2, and check its Forwarding line matches. **If you see** `ERR_NGROK_8012`
   or a "bad gateway" page, ngrok is up but `app.py` isn't: go back to step 1.

4. **Does the bot's button point at that address?**

   ```powershell
   $t = ((Get-Content .env | Where-Object { $_ -match '^TELEGRAM_TOKEN' }) -split '=',2)[1].Trim()
   (Invoke-RestMethod "https://api.telegram.org/bot$t/getChatMenuButton").result.web_app.url
   ```

   **You should see** `https://moonlight-dwelling-footpad.ngrok-free.dev/`.
   **If you see** a different address, update it in @BotFather (Phase 10).
   This only shows the chat's **Open App** button. The URL set in BotFather's
   Mini App settings (the one used by the bot's profile link) can only be
   checked in BotFather.

5. **Reopen it properly on the phone.** Fully close the Mini App (swipe it
   away, not just minimise), then open it again from the bot's **Open App**
   button. Telegram keeps a failed page open until you close it.

**When a step fails in a way that isn't in this table:** screenshot the whole
PowerShell window, including the command you ran, and send it with the phase
number.

---

## Daily start and stop card

Print this.

**Start**

```powershell
cd C:\Users\endrw\my-mini-app
.\scripts\start_event.ps1
```

Then: pick the tunnel when asked → check all three windows say they're running →
open the public URL on your phone on mobile data → check `/admin` Overview loads.

**Stop**

1. `/admin` → Exports → download all three exports.
2. `/admin` → "Back up now".
3. Ctrl+C in each of the three windows, bot first, tunnel last.
4. Copy `data\` to a USB stick or your cloud drive.

**If something breaks mid-event**

1. Is the tunnel window still running? Restart it — the address doesn't change.
2. Is `app.py` still running? Restart it — nothing is lost.
3. Booths keep going on the printed fallback list; enter the claims afterwards
   with their real times.
4. The escape room never stops. The desk devices don't need any of this.
