# BUILD_SPEC — The Yard

Backend build specification for Claude Code. Section and rule numbers match the
design brief (v2), so references like "§9, rule 24" stay valid.

Stack is fixed: Python, Flask, SQLite, python-telegram-bot, on Windows, reached
through a free tunnel. No stack switch. No paid services required.

Ask the organiser before changing any rule in §3 or §9.

**Current build state is in `STATE.md`** — what is live, what is still mock,
and every decision taken since the handoff. Nothing in §3 or §9 has changed.
P0.1 and P0.2 are live and signed off. P0.3, P0.4 and `bot.py` are built and
awaiting the organiser's test. Dated changes are in `CHANGELOG.md`.
After any major decision, update `STATE.md`, `README.md`, this file,
`RUNBOOK.md` and `context/PROJECT_STATUS.md` in the same pass.

---

## §0. Decisions locked (do not re-ask)

| Question | Answer |
|---|---|
| Event date | Thursday 24 September 2026 |
| Doors | **3:00 PM** (organiser, 22 Sep; was 5:00 PM). Closing 10:00 PM (organiser, 17 Sep) |
| Timezone / payment | Asia/Singapore. Entry $12 ($10 early bird until 20 Sep 23:59), paid outside the app. **The app takes no money** |
| Escape game length | 15 minutes |
| Changeover | 5 minutes |
| Cadence | A new group every 20 minutes |
| First game | 5:30 PM |
| Venue | @ Hub @ L5 Hafary |
| Included in entry | *Since 22 Sep (`STATE.md` 132): a pastry — Mini Tart, Mini Brownie, Mini Cookie or Shiopan, the kind recorded — the first photo strip, and vinyl crafting (once each, tracked; **Vinyl Crafting** since 23 Sep, `STATE.md` 142), plus the escape room, the jamming studio and board games. Everything else has a price: the `price_list` Setting, shown on Help. The canned drink left the pass 19 Sep* |
| Last game | 9:30 PM. *Since 22 Sep, decision 133: games 3:05–9:45 PM, 21 games, 252 seats, so the last one ends with the doors at 10 PM. It was 3:30–9:30 (19 games, 228 seats), and 5:30 PM (13 games, 156 seats) before that* |
| Capacity | **12 players**, 6 per half |
| Phone unlock mode | `gm_start` |
| Require check-in for phone | Yes |
| In-app phone | On by default, GM can switch off |
| Relock | 2 minutes after game end. *Since 22 Sep: the phone stays open **25 minutes from the start** (`phone_minutes`), and the GM's End no longer locks it (`STATE.md` 130)* |
| Hint lines | 4:30, 6:45, 10:30 (of a 15:00 timer) |
| Forced merge | 7:30 |
| Jam slots | **Free.** 30 minutes, **3:00–9:30 PM (14 slots)** since 22 Sep (was 5:00–9:30 PM, 10 slots), one per person, confirmed on booking. Not allowed to overlap your escape game (±5 min walk) |
| Booking cutoff | 5 minutes before start |
| Cancel cutoff | 30 minutes before start |
| Always-allowed handle | `maxi_muslim` (test account, excluded from headcounts) |
| Unverified receipts | Staff may **not** hand over. Admin override with reason only |
| Attendee direction | Direction 1a — paper/poster |
| The Last Guest direction | Direction 1b — monochrome ink |

**Superseded 17–18 Sep by the organiser's source of truth** (see STATE §5,
decisions 58–67): matcha/panini → pastry/drink, jam free, no receipt uploads,
Reviews and Call removed. Where this spec still describes those, STATE wins.

Still open, and carrying visible defaults: meeting point, pastry and photo-strip
stock, GM and actor handles, the finder's name, Paperform webhook
availability, Tailscale non-commercial confirmation. Every one of these is a row in the Settings screen, so the build
does not block on them.

---

## §2. What we're building

The Yard is a one-day event. People sign up on Paperform and upload a payment
screenshot. The entrance fee includes one cookie or pastry and one canned
drink. *(Since 22 Sep, `STATE.md` 132: a pastry of four kinds, the first
photo strip and vinyl crafting; no canned drink.)*

Attendees open a Telegram bot whose Mini App has three areas:

1. **The Last Guest** — book a seat in a 15-minute escape-room game. Groups of
   up to 12, starting every 20 minutes from 3:05 PM (3:30 PM earlier on 22 Sep; 5:30 PM before that). At the door the group
   splits in half; at game time the phone unlocks in-app for the desk half only.
   *Changed 22 Sep (`STATE.md` 130): it unlocks for **everyone in the game**,
   and reaches them only as a bot message with an "Open the phone" button.*
2. **Your pass** — a personal pass (QR + typed code) to collect the cookie
   or pastry and the photo strip, each exactly once.
3. **Jamming studio** — book a free 30-minute slot for your group; it is
   confirmed at once. *Changed 18 Sep: the room is booked the same way as the
   escape room, for up to `jam_capacity` people, all or nothing. It used to be
   one booking per slot. The organiser's reason: an escape game with strangers
   is part of the fun, a jam with strangers is not — so the booker brings
   their own people and the room does not have to fill. A slot belongs to that
   group; nobody else is seated alongside them. `STATE.md` decision 96.*

Staff use a separate console in a normal browser to scan codes, hand over items
once, check people in, run the escape room, verify payments and look anyone up.

### System map

```
Attendee's Telegram
   └─ Mini App (WebView)
        └─ HTTPS tunnel  (Tailscale Funnel on the day; ngrok fallback)
             └─ Flask app.py on the laptop, port 5000
                  └─ SQLite data/app.db  (WAL)

bot.py  ⇄  Telegram servers        long polling, outbound only, no tunnel
bot.py  →  the same SQLite file

Staff phones + laptop browser → the same tunnel → Flask /admin

Paperform → /admin upload (always) or POST /webhooks/paperform (if the plan has it)

Desk devices → the phone file, offline, no connection to any of the above
```

---

## §3. Non-negotiable rules

1. **Access gate.** Only people whose Telegram username is on the sign-up list
   get past the Start screen. The check runs live on every app open **and every
   API call**, not only in the UI. Attendees never type their own username to
   get in — the app reads it from Telegram. `@maxi_muslim` is always allowed,
   even when missing from the list or when the list failed to load.
2. **The server decides.** Identity comes only from Telegram initData verified
   on the server. Reuse the existing `verify_telegram_data()` and add an
   `auth_date` maximum-age check. Never trust `initDataUnsafe`, the device clock
   or hidden buttons for any decision.
3. **Once means once.** Each person collects each item once. The database
   enforces this even when two booths scan the same code in the same second.
4. **Spoiler firewall.** Attendee screens may use only the public premise: Si
   Hong hosted four guests, collapsed at 10:30 PM, the police are fifteen
   minutes out, all four guests say they had already left. The solution, clock
   offset, suspects' secrets, lock code, hint lines and timeline appear only in
   the GM console, for the `gm` and `admin` roles. The phone's evidence photos
   appear only inside the unlocked phone. The phone file is never reachable by
   any URL before its unlock time, or by a player in the other half.
5. **Keep the stack** (above).
6. **Keep traffic small.** Both free tunnels have limits; ngrok free allows
   20,000 HTTP requests and 1 GB out per month and testing counts toward it. So:
   one HTML file per app with inline CSS and JS; libraries from public CDNs at
   pinned versions; no polling more often than every 30 seconds and none while
   the page is hidden; countdowns run on the device, corrected by server time;
   images compressed; every fetch sends `ngrok-skip-browser-warning: 1`.
   Budget: a typical attendee visit is six requests or fewer.
7. **Beginner-proof.** Every instruction for the organiser uses Windows
   PowerShell syntax (`;` not `&&`, `venv\Scripts\activate`), is numbered and
   copy-paste ready, and says what they should see afterwards.

---

## §7. Architecture

### 7.1 Three processes, three PowerShell windows

1. **Web — `app.py` (Flask).** Serves `/` (the Mini App, at the URL BotFather
   already points to), `/admin`, and the JSON API. Use `waitress` on event day.
2. **Bot — `bot.py` (python-telegram-bot, long polling).** Handles `/start`,
   receipt photos, reminders, actor messages, and a sweep that expires stale jam
   holds.
3. **Tunnel.** Tailscale Funnel on event day, ngrok as fallback, to localhost:5000.

Both Python processes share `data/app.db` — SQLite in WAL mode with a busy
timeout. **As built (17 Sep):** Flask does not call the Bot API. It writes a
`notifications` row in the same transaction as the change, and `bot.py` sends
due rows every 5 seconds, with retries, expiry and de-duplication
(`STATE.md` decision 47). `notify_mode` (`owner` / `on` / `off`) decides who
may be messaged. `scripts\start_event.ps1` opens all three windows and asks which
tunnel to use.

### 7.2 File layout (inside `C:\Users\endrw\my-mini-app`)

Keep what exists: `venv\`, `.env` (with `TELEGRAM_TOKEN`), `templates\index.html`,
and `verify_telegram_data()`.

```
app.py             pages + API + admin (web process)
bot.py             Telegram bot (bot process)
manage.py          init-db, import, roster, generate-slots, set-admin-password,
                   set-staff-pin, set-gm-pin, make-secret, backup, void-claim
config.py          loads .env, default settings
db.py              connection, schema, migrations, backups
auth.py            initData verification, admin/staff/gm sessions, CSRF
services\          roster.py, bookings.py, claims.py, phone.py, receipts.py, notify.py
templates\         index.html (Mini App), admin.html (console)
static\            yard-logo.png — the logo both pages load
private\phone\     the fixed phone file (never served as a static file)
private\receipts\  uploaded screenshots (never served as static files)
data\              app.db, backups\
imports\           Paperform exports dropped in
scripts\           start_event.ps1, backup_now.ps1
tests\             pytest suite
requirements.txt, .env.example
```

`static\` was not in the original layout. Both pages need the logo and the demo
QR; one cached request each costs less against the §3 rule 6 budget than
inlining ~91 KB of base64 into every page load. The live pass QR does **not**
live here — it is returned as a data URI inside `GET /api/me`, so a typical
attendee visit still fits in six requests.

One column was added to `attendees` beyond §8: `submitted_at_text`. Paperform's
"Submitted At" has an unknown timezone (§9 rule 10), so it is kept verbatim as
display-only text for the export-back.

One table was added beyond §8 at P0.2: `console_sessions` (see §8). It keeps
console sign-ins server-side, so Sign out really ends a session (§9 rule 33) and
a restart of `app.py` signs nobody out.

### 7.3 `.env` keys

`TELEGRAM_TOKEN` (existing), `FLASK_SECRET_KEY`, `ADMIN_PASSWORD_HASH`,
`STAFF_PIN_HASH`, `GM_PIN_HASH`, `PUBLIC_URL`, `DATA_DIR`,
`ALWAYS_ALLOW_HANDLES=maxi_muslim`, `PAPERFORM_WEBHOOK_SECRET`,
`TIMEZONE=Asia/Singapore`. Everything else lives in the Settings screen.
`manage.py` generates the secret key and hashes the password and PINs.

### 7.4 Hosting

Everything runs on the organiser's laptop, so the database and receipts stay on
their own disk. The only question is which tunnel lets Telegram reach it.

**Event day: Tailscale Funnel, free Personal plan.** Fixed public address
`https://<laptop-name>.<tailnet>.ts.net` with a valid certificate, forwarding to
localhost:5000; no router or firewall changes. Rename the laptop in Tailscale
first (e.g. "theyard"), because the name appears in the address. Caveats for the
RUNBOOK: the Personal plan is meant for non-commercial use and The Yard charges
fees, so confirm before relying on it; Funnel bandwidth caps are unpublished, so
keep traffic small; the app is reachable only while the laptop is on, awake and
online; confirm in testing that attendees reach the app with no warning page.

**Development and fallback: ngrok free** (already set up). One fixed dev domain
per account, and free endpoints no longer time out, so the URL should not need
re-pasting after restarts — the old PROJECT_STATUS notes saying otherwise are
outdated. Attendees see a warning page on first visit; a cookie hides it for 7
days. Monthly limits as in §3 rule 6.

**Switching tunnels:** (1) run the other tunnel, (2) update `PUBLIC_URL`,
(3) restart `bot.py`, which resets the menu button, (4) update the Mini App URL
in BotFather.

**Not suitable:** Render's free tier (filesystem wiped on restart, redeploy or
spin-down, erasing the database and receipts); Cloudflare quick tunnels (new
random address every start, breaking links attendees already have).

---

## §8. Data model

SQLite. Store times in UTC, display in the event timezone. Write partial unique
indexes as `CREATE UNIQUE INDEX … WHERE …`.

```
attendees       id, paperform_id UNIQUE NULL, name, email, handle UNIQUE (normalised), handle_raw,
                tg_user_id UNIQUE NULL, tg_first_name, tg_username_seen, can_message,
                source (import|webhook|walk_in|owner), status (active|inactive), is_test,
                payment_status (missing|submitted|verified|rejected), paperform_receipt_url,
                pass_code UNIQUE, checked_in_at, checked_in_by, notes, created_at, updated_at

claims          id, attendee_id, item (pastry|photo — config.ITEMS), variant, claimed_at, staff_name, station,
                voided_at, voided_by, void_reason
                UNIQUE (attendee_id, item) WHERE voided_at IS NULL

slots           id, room (escape|jam), starts_at, ends_at, capacity, price_cents,
                is_blocked, block_reason
                UNIQUE (room, starts_at)
                (escape: ends_at is the end of the 15-minute game; changeover follows it)

escape_bookings id, slot_id, attendee_id, booked_by_id, ref_code UNIQUE, zone (A|B),
                zone_changed_by, status (booked|checked_in|cancelled|no_show), created_at,
                cancelled_at, checked_in_at, reminder_sent_at
                UNIQUE (attendee_id) WHERE status IN (booked, checked_in)

jam_bookings    id, slot_id, attendee_id, ref_code UNIQUE, party_size, price_cents (snapshot),
                status (held|pending_review|confirmed|rejected|expired|cancelled),
                hold_expires_at, reviewed_by, reviewed_at, reject_reason, created_at,
                reminder_sent_at
                UNIQUE (slot_id) WHERE status IN (held, pending_review, confirmed)

receipts        id, attendee_id, purpose (entrance|jam), jam_booking_id NULL, file_name,
                sha256, phash, txn_ref NULL, txn_ref_skip_reason, possible_duplicate_of NULL,
                source (mini_app|bot|admin|paperform), uploaded_at
                INDEX (sha256), INDEX (phash)
                UNIQUE (txn_ref) WHERE txn_ref IS NOT NULL

game_sessions   id, slot_id UNIQUE, started_at, halves_locked_at, paused_seconds, extended_seconds,
                ended_at, phone_unlocked_at, phone_locked_at, in_app_phone (on|off),
                result (escaped|timed_out), finish_seconds, gm_name
                -- 23 Sep (STATE.md 140): halves_locked_at and in_app_phone are
                -- dead columns. Nothing reads or writes them. They stay because
                -- dropping a column from a live SQLite the night before an
                -- event buys nothing. escape_bookings.zone and .zone_changed_by
                -- are dead for the same reason.

hint_sends      id, session_id, hint_key, sent_at, sent_by

one_time_links  id, token_hash UNIQUE, attendee_id, purpose (phone), expires_at, used_at

gate_attempts   id, at, tg_user_id, tg_username, tg_first_name, claimed_handle, outcome,
                resolved_by, resolved_at

audit_log       id, at, actor_type (admin|staff|gm|system|attendee|bot|webhook), actor_name,
                station, action, entity, entity_id, details (JSON)

settings        key PRIMARY KEY, value (JSON), updated_at, updated_by

import_runs     id, at, source (upload|webhook), file_name, counts (JSON), report (JSON),
                committed_at

console_sessions  (added at P0.2)  id, sid_hash UNIQUE, csrf_hash, role (admin|staff|gm),
                name, station, created_at, expires_at, revoked_at
                (only SHA-256 hashes of the session id and CSRF token are stored)

notifications   (added 17 Sep)  id, attendee_id, kind, dedupe_key UNIQUE, text, button_path,
                created_at, send_after, expires_at,
                status (queued|sending|sent|suppressed|skipped|expired|failed),
                attempts, sent_at, last_error
```

`escape_bookings.booked_by_id` is the person who added that player; the
booker's own row points at themselves. It is what decides who may edit a
group.

---

## §9. Data validation and integrity rules

### Identity and access

1. **Normalise usernames everywhere** (import, search, the gate, friend lists,
   every username box): trim; drop a leading `@`; drop `t.me/` or
   `https://t.me/`; lowercase. Telegram usernames are usually 5–32 letters,
   digits and underscores — flag anything else in the import preview rather than
   silently rejecting it.
2. **A person is allowed in when any of these is true:** their normalised
   username matches an active roster entry; their Telegram user ID is already
   linked to an active entry (so a later username change doesn't lock them out);
   their username is in `ALWAYS_ALLOW_HANDLES`.
3. **Link on the first successful Start.** Link the roster entry to the Telegram
   user ID, which is stable. If that entry is already linked to a different ID,
   deny with `LINKED_ELSEWHERE` — this stops someone who later takes over a
   recycled username.
4. **No username:** deny with instructions, unless their ID is already linked.
5. **`@maxi_muslim`** is always allowed. If not on the roster, create an entry
   with source `owner` and `is_test` on (excluded from headcounts by default).
6. **Every refusal** is recorded in `gate_attempts` for the front desk, with any
   username the person says they signed up with.
7. **A username typed on the Start screen never admits or links anyone by
   itself.** Anyone could type someone else's username, so an admin checks who
   the person is and links them. At most 3 such requests per person per hour.
8. **initData:** verify the signature on every request; reject when `auth_date`
   is older than 24 hours.
9. **Gate switch:** a Settings switch closes the app to everyone except
   always-allowed usernames.

### Roster import (Paperform export, sheet "Registrations")

Columns: Submitted At, Unique, Name, Telegram, Email, Submission Receipt,
Checked-in, Checked in at, Redeemed, Redemmed At (sic). The current export has
17 real sign-ups then ~1,000 blank formatted rows. The last four columns are
empty — our system becomes the source of truth for them and exports them back
filled in.

10. **Reading the file:** skip fully blank rows; trim every text cell; read
    "Unique" as an integer string, never a float (Excel stores it as
    `1789457183000.0`); keep "Submitted At" as display-only text, because its
    timezone is unknown.
11. **Matching:** match on Paperform ID first, then on username. Re-importing
    the same file must change nothing (idempotent).
12. **Missing people:** a person missing from a newer file becomes inactive and
    is never deleted. Their bookings and claims stay, flagged for a decision.
    *Scoped 18 Sep to people who came **from** an import (`source='import'`).
    A walk-in added at the door and the organiser's own owner row are never in
    a Paperform export, so they cannot be "missing" from one; sweeping them
    would have deactivated every walk-in on the first re-import during the
    event. `STATE.md` decision 82.*
13. **Problems in the preview:** duplicate usernames within one file; invalid
    usernames; invalid emails; a changed username on an already linked person.
    Nothing is written until Commit.
14. **Payment status:** a receipt link sets `payment_status` to `submitted`.
    Only an admin can set `verified` or `rejected`.

Known quirks to handle silently: every handle starts with `@`, one has capital
letters, some names have trailing spaces, 3 rows have no receipt link.

### Bookings (all checked on the server, inside one transaction)

15. Only allowed, active people can book or be added as friends.
16. **Escape room:** one active booking per person; seats counted in the same
    transaction so a game never exceeds capacity; no booking for games that have
    started or are within the booking cutoff; friends are all-or-nothing and the
    group must fit; each new player goes into the smaller half.
17. **Jam room:** one active booking per slot, at most N per person; before
    inserting a hold, expire stale holds on that slot in the same transaction
    (otherwise the unique index still blocks it); availability treats expired
    holds as free.
18. **No overlaps.** A person's escape game counts from 5 minutes before it
    starts until it ends. No jam booking may overlap that, including the 5-minute
    walking buffer.
19. The price is copied onto the jam booking when made, so later price changes
    don't affect it.
20. **Reference and pass codes:** an unambiguous alphabet (no 0, O, 1, I, L);
    random, never sequential, unique; a namespaced QR payload
    (`YARD:7K3MQ9XT`) so a random QR gives a clear `NOT_A_YARD_CODE`.

### The phone

21. **`/api/escape/phone` serves the file only when all of these are true:** the
    person has a booking for the game in progress; the in-app phone is on; the
    game has started (by clock or by GM, per the mode) and hasn't passed its
    relock time; the person is in the desk half; the person is checked in.
    Otherwise return `PHONE_LOCKED`, `PHONE_OFF`, `PHONE_NOT_YOUR_HALF` or
    `NOT_CHECKED_IN`. Send `Cache-Control: no-store`.
    *Changed 22 Sep at the organiser's instruction (`STATE.md` decision 130):
    **the desk-half condition is removed** — everyone booked in the game gets
    the phone; the halves still decide where people start. The relock time is
    **`phone_minutes` (25) after the start**, pushed back by pauses and the
    GM's extra minutes; the GM's End no longer locks it, the GM's Lock still
    does. `PHONE_NOT_YOUR_HALF` is no longer returned. **The only way to the
    phone is a bot message** sent to every player the moment the phone opens
    (the GM's Start in `gm_start` mode, the booked time in `clock` mode), whose
    "📱 Open the phone" button opens the Mini App at `?go=phone`. Nothing in
    the Mini App links there; the server's check above is still the lock.*
    *Changed 23 Sep (`STATE.md` decision 140): **the booked time is the whole
    rule.** There is no `gm_start` mode and no `clock` mode, because there is
    no Start — a game begins at its booked minute. **The check-in condition
    is removed** too: somebody who walked past the front desk still gets their
    phone. The relock time is `phone_minutes` after the **booked time**, plus
    whatever has been paused or added, so a pause never costs a group the
    phone. `PHONE_OFF` no longer means an admin switched the phone off — the
    `in_app_phone` setting is gone — and now means one thing, a fault: the
    phone's file is not on this laptop. What is left: `NOT_YET`, `NO_BOOKING`,
    `RELOCKED`, `PHONE_LOCKED` (the GM's hand, never anything automatic) and
    `PHONE_OFF`. The button reads "📱 Open Kai Chen's phone" (`STATE.md`
    142).*
22. ~~**Halves lock when the game starts.** After that only the GM can swap
    someone, and every swap is logged.~~ *Withdrawn 23 Sep (`STATE.md`
    decision 140): **there are no halves.** Since 22 Sep everyone in the game
    had the phone, which left the split deciding only where two groups stood,
    and the app never enforced that. `_assign_halves`, `_zone`, `game.halves`,
    the `/halves` route and the A/B columns on four screens are gone. The GM
    card lists who is in this game instead.*
23. **One-time links** for the full-page fallback work once, expire after about
    a minute, and are only issued when rule 21 passes. *Built 18 Sep:
    `POST /api/escape/phone/link` issues one; `GET /p/{token}` spends it. 90
    seconds, single use, and rule 21 is checked again **as it is spent**, so
    locking the phone reaches a link already in someone's hand. It lives
    outside `/api/` because it opens in the phone's real browser, where there
    is no initData — the token is the whole credential, which is why it is
    short-lived.*

### Claims and check-ins

24. A claim is a single INSERT protected by the unique index. A duplicate-key
    error becomes `ALREADY_CLAIMED`, returned with the original time, staff and
    station.
25. Claims require `payment_status = verified`; a setting can relax this to
    `submitted`. Admin overrides need a reason and are logged.
26. Only admins can void a claim, and a reason is required. Voids are soft — the
    row stays.
27. **Optional stock** per item and variant: warn when low, block at zero if the
    setting says so.
28. Code lookups are rate-limited per staff session (e.g. 30 a minute) to stop
    guessing.

### Receipts and the duplicate check

> **As built, 18 Sep.** In-app receipt uploads were dropped on 18 Sep
> (`STATE.md` decision 60): people without a verified payment go to the front
> desk. Rules 29–31 therefore apply to the copies we take of **Paperform's own
> screenshots**, not to anything an attendee uploads. The links Paperform signs
> expire 7 days after each sign-up — all of them before the event — so
> `services/receipts.py` downloads each one, re-saves it to strip metadata,
> stores it under a random name in `private\receipts`, and serves it only to a
> signed-in admin. That restored rules 30's first two layers, which had no
> bytes to work on once uploads went. See `STATE.md` decision 85.

29. **Uploads:** images only, at most 5 MB after on-device compression. The
    server checks the file really is an image, strips hidden metadata, and
    re-saves it under a random name in `private\receipts`.
30. **Three layers. They warn but never reject on their own; the admin decides.**
    - **Exact copy** — SHA-256 of the uploaded bytes. The same fingerprint on
      another person or booking raises `DUPLICATE_RECEIPT`.
    - **Look-alike** — a difference hash computed with Pillow (no extra
      library), which survives re-saving, resizing and re-screenshotting. A
      close match shows "possible duplicate" with both images side by side.
      Payment screens from the same bank look alike, so keep the threshold strict.
    - **Transaction reference** — to approve, the admin types the reference from
      the screenshot. The database refuses a reference already used for another
      payment (`DUPLICATE_TXN_REF`). This is the layer that actually proves each
      payment counts once. If a screenshot shows no reference, the admin can
      skip the box with a reason.
    - **Paperform receipts** are fingerprinted too when an admin opens them, if
      the link lets the server download the image — so a sign-up screenshot
      reused for a jam booking is caught.
31. Receipt files are served only to signed-in admins, never reachable by
    guessing a URL.

### Admin, time and safety

32. Every write goes to `audit_log` with who, station, when, and before/after values.
33. **Access control:** phone sign-ins can't change payments, settings or
    exports; admin sign-in is rate-limited and sessions expire; cookies are
    HttpOnly and Secure; state-changing requests need a CSRF token.
    *Changed 22 Sep at the organiser's request (`STATE.md` decision 126): the
    staff and GM sign-ins became one **Mobile** sign-in, which does open the GM
    console. The organiser was asked about the solution being visible to every
    phone PIN holder and chose it. Everything else here stands.*
34. **The server clock is the only clock.** Every response includes
    `server_time`, and the app corrects countdowns with it.
35. **The test clock** affects only the server's notion of "now", shows a banner
    everywhere in `/admin`, and can't be on while event-day mode is on.
    *Changed 22 Sep at the organiser's request (`STATE.md` decision 129):
    event-day mode is gone. Settings has one **Clock** switch, **Real time /
    Test time**, and a minute slider. Test time makes "now" the **event day**
    at that minute (it used to be today at that minute), for every request,
    and it stands still until the slider moves. The banner stays. The
    doors-open and last-call messages each have their own switch and are
    never sent in test time.*

### Resilience

36. **Backups:** WAL mode with a busy timeout. An automatic backup copy every 10
    minutes into `data\backups`, keeping the last 36, plus a "Back up now" button.
37. **Outages:** keep the printable fallback list and a documented paper
    process; after an outage, admins can enter paper claims with the real time;
    the desk devices keep the escape room running without the server.
38. **After the event:** export, then delete receipts and any personal data no
    longer needed.

---

## §10. Keeping the roster up to date

Build in this order:

1. **Upload (must-have, always works).** Export from Paperform, upload in
   `/admin`, as often as wanted. Preview shows new, changed, unchanged, missing
   from this file, and problems. Nothing is written until Commit.
2. **Walk-ins (must-have).** Added by hand in `/admin` on the day, marked paid
   once the payment has been seen.
3. **Webhook (optional).** Paperform webhooks exist only on certain plans. If
   available: Paperform POSTs each submission as JSON to `/webhooks/paperform`;
   protect it with a secret custom header; answer fast, because Paperform waits
   only about 10 seconds; upsert by Paperform ID and log it; use Paperform's
   "Test" button. Submissions made while the laptop is off are missed, so the
   upload path stays the safety net.

The import copes with `name`, `@name`, `@Name ` and t.me links, so the sign-up
form does not need to change.

---

## §11. Bot behaviour (`bot.py`)

- **`/start`** — If allowed: greet by name, show an "Open The Yard" button, and
  set that chat's menu button to the Mini App. That button must be an
  **inline-keyboard web-app button**, never a reply-keyboard one: Telegram sends
  no user data to a Mini App opened from a reply-keyboard button, so the gate
  would refuse everyone. Do not copy bot examples built around `sendData` —
  they use the reply keyboard. The menu button and BotFather's direct link do
  send user data. If not allowed: explain why, in the same wording as the gate,
  and log the attempt. The Mini App's own gate stays the real lock.
- **`/pass`** — sends the person's pass as a QR image with the code. Works even
  if the Mini App won't load, because it doesn't go through the tunnel.
- **Photos** — saved as receipts and attached to that person's pending jam
  booking, or else to their entrance payment. The bot replies with what it did.
- **Reminders** — 10 minutes before an escape game or jam slot; on jam approval
  or rejection; optionally when their phone unlocks (desk half only).
  *Since 22 Sep the phone message is not optional: it is the only way to the
  phone, it goes to everyone in the game, and its button reads "📱 Open the
  phone" (`notify.text_phone`, `STATE.md` 130).*
- **As built (17 Sep):** `/start`, `/pass`, `/help`; reminders; group
  changes; payment verdicts; the booth's Call; doors-open and last call on
  event day. The full list, and what is deliberately *not* sent, is
  `STATE.md` decision 49. Photo receipts and `/actor` are not built yet.
- **`/actor <PIN>`** — registers the actor's chat to receive hint lines.
- **`/help`** — the organiser contact.
- **Blocked bots** — if a message fails because someone blocked the bot, mark
  them not messageable. Ask for write access from the Mini App when missing.

---

## §12. API contract

Every response is JSON in one of two shapes:

```json
{ "ok": true,  "data": { }, "server_time": "2026-09-24T17:30:00+08:00" }
{ "ok": false, "error": { "code": "SLOT_FULL", "message": "…" }, "server_time": "…" }
```

The UI maps error codes to copy.

### Mini App endpoints — header `Authorization: tma <initData>`

| Method and path | Purpose |
|---|---|
| POST /api/session | Start-screen check; returns status, profile and the settings the UI needs |
| POST /api/session/claimed-handle | "Signed up with a different username?" request. Works for refused people with valid initData; rate-limited (§9 r7) |
| GET /api/me | Home, pass, claims, payment status, bookings, phone state |
| GET /api/escape/slots | Escape game board |
| POST /api/escape/bookings | Book, with optional friends |
| DELETE /api/escape/bookings/{ref} | Cancel |
| GET /api/escape/phone/status | Lock state, the person's half once revealed, unlock_at, lock_at |
| GET /api/escape/phone | The phone file, only when §9 r21 passes; `Cache-Control: no-store` |
| POST /api/escape/phone/link | One-time link for the full-page fallback (§9 r23) |
| GET /phone/{token} | The phone as a full page, once |
| GET /api/jam/slots | Jam slot board |
| POST /api/jam/bookings | Book a free jam slot for a group, all or nothing (confirmed at once) |
| POST /api/jam/bookings/{ref}/group | The booker adds more people |
| DELETE /api/jam/bookings/{ref}/group/{handle} | The booker removes someone they added |
| POST /api/jam/bookings/{ref}/leave | Someone added gives up their own seat |
| DELETE /api/jam/bookings/{ref} | Cancel before it starts |

### Admin endpoints — session cookie plus CSRF header

| Method and path | Purpose |
|---|---|
| POST /admin/api/login, /admin/api/logout | Laptop: admin password. Mobile: phone PIN (staff or GM) + name + where you are |
| GET /admin/api/overview | Dashboard numbers |
| GET /admin/api/people, GET /admin/api/people/{id} | Search and person page |
| POST /admin/api/people, PATCH /admin/api/people/{id} | Walk-in; edits (reason required) |
| POST /admin/api/people/{id}/payment, POST /admin/api/payments/bulk-verify | Verify or reject |
| POST /admin/api/people/{id}/unlink | Unlink a Telegram account |
| GET /admin/api/lookup/{code} | Booth lookup |
| POST /admin/api/claims, POST /admin/api/claims/{id}/void | Hand over; void |
| POST /admin/api/checkins | Event, escape or jam check-in |
| GET /admin/api/slots, POST /admin/api/slots/{id}/block, POST /admin/api/escape/move | Schedules |
| GET /admin/api/gm/state | GM console state (gm and admin only) |
| ~~POST /admin/api/gm/{slot_id}/halves~~ | *Gone 23 Sep — there are no halves* |
| POST /admin/api/gm/{slot_id}/{action} | pause, resume, shorten, extend, end, lock, unlock *(23 Sep: no start, no phone-on/phone-off)* |
| POST /admin/api/gm/{slot_id}/hints/{key} | Give a hint — sends the line to the actor *(23 Sep: was `…/cues/{key}`)* |
| POST /admin/api/gm/phone-test | Send Kai Chen's phone to the Test group *(23 Sep, `STATE.md` 141)* |
| POST /admin/api/roster/preview, POST /admin/api/roster/commit/{run_id} | Import |
| GET /admin/api/gate-attempts, POST /admin/api/gate-attempts/{id}/resolve | Front desk |
| GET, PUT /admin/api/settings | Settings |
| GET /admin/api/audit, GET /admin/api/export/{kind} | Audit log and exports |
| POST /webhooks/paperform | Paperform webhook (secret header) |

### Added since the handoff

These were needed by screens the brief described but never drew. Recorded here
and in `STATE.md` §5.

| Method and path | Purpose |
|---|---|
| GET /healthz | Liveness check for the tunnel windows |
| POST /admin/api/backup | The "Back up now" button the RUNBOOK promises (§9 r36) |
| GET /admin/api/roster | Roster screen summary: active, inactive, walk-ins, past import runs |
| GET /admin/api/session | Resume the console sign-in after a reload; rotates the CSRF token |
| GET /admin/api/orders | The matcha/panini waiting list, with what happened to each "ready" message (22 Sep, decision 125) |
| POST /admin/api/orders | Place an order from a pass code or attendee id; not a claim, so never once-only |
| POST /admin/api/orders/{id}/call | Queue the "your matcha is ready" message; a second tap within a minute sends nothing new |
| POST /admin/api/orders/{id}/collected, /cancel | Take it off the waiting list |

### Shapes fixed at P0.2

- **`GET /api/me`** → `profile`, `payment_status`, `payment_ok` (whether the
  booth may hand over, after the `claim_requires` setting), `pass_qr` (a PNG
  **data URI** encoding `YARD:<code without hyphen>`, never a separate request),
  `checked_in_at`, `items:[{key, label}]`, `claims.{pastry,photo}` (keys from `config.ITEMS`) (`{claimed:false}` or
  `{claimed:true, id, at, staff, station, variant}`), `escape_booking` (null
  until P0.4), `jam_bookings` (`[]` until P0.6). The gate runs on this call too.
- **`POST /admin/api/login`** — JSON only. Body `{role, password}` for admin, or
  `{role, pin, name, station}` for staff and gm (station is required for
  staff). Returns `{role, name, station, csrf_token, expires_at,
  test_clock, test_clock_at, event_date, items}` (since 22 Sep; it carried
  `event_day_mode` before) and sets the `yard_console` cookie (HttpOnly,
  Secure, SameSite=Lax, 12 hours). Every other admin call that changes
  anything sends the token as `X-CSRF-Token`.
- **Roles on the server** (since 22 Sep, decision 126): two, `admin` (Laptop)
  and `mobile`. Mobile may call session, logout, live, lookup, claims,
  checkins, `GET` people, `/admin/api/gm/*` and the orders endpoints.
  Everything else under `/admin/api/` is admin-only, including endpoints not
  built yet. A sign-in sent as `staff` or `gm`, and a stored session with
  either name, is treated as `mobile`; Mobile accepts the staff PIN or the GM
  PIN.
- **`GET /admin/api/lookup/{code}`** → `code` (`null` or `INACTIVE`),
  `pass_code`, `person`, `payment_status`, `payment_ok`, `claims`,
  `can_hand_over`, `can_override` (admin only, when something blocks),
  `items`, `stock.{pastry,photo}` (`null` when untracked, else `{total, left, low,
  blocks_at_zero}`). Accepts `YARD:7K3MQ9XT`, `7K3M-Q9XT`, `7k3m q9xt`.
- **`POST /admin/api/claims`** — body `{code | attendee_id, item, variant?,
  override_reason?}`. Staff name and station come from the session, never the
  body. Success → `{id, item, variant, at, staff, station, override, person,
  stock}`. `ALREADY_CLAIMED` is HTTP 409 with
  `error.claim = {item, id, at, staff, station, variant}` and a message like
  "Photo strip already collected at 7:14 PM (Booth 1, Wei)."
- **`POST /admin/api/checkins`** — body `{code | attendee_id, kind:'event'}` →
  `{checked_in_at, checked_in_by, already, person}`. A second check-in returns
  `already: true` with the first one's time and name.

### Shapes fixed at P0.3

- **`GET /admin/api/people?q=`** → `{query, total, shown, people:[{id, name,
  handle, tag}]}`. `q` matches name, email, username (normalised), pass code
  in any shape, or a booking ref. At most 50 are returned, active people first.
  Any console role.
- **`GET /admin/api/people/{id}`** → `id, name, handle, tg_user_id,
  tg_first_name, paperform_id, status, is_test, source, pass_code, pass_qr
  (data URI), payment_status, payment_ok, payment` (the latest verdict:
  `{action, by, at, txn_ref, skip_reason, reason}` or null), `checked_in_at,
  checked_in_by, claims, bookings` (`[]` until P0.4/P0.6), `items`, `receipt` (`{source,
  url, link, expired, note}` — the Paperform screenshot, the only receipt; `url` and
  `link` are null for staff and gm, and for an expired Paperform link), and
  `audit` (the latest 25 rows for that person, `{at, what, who}`). Unknown id →
  `NOT_FOUND` 404.
- **`POST /admin/api/people/{id}/payment`** — admin only. Body `{verdict:
  verified | rejected | reopen, txn_ref?, reason?}`. `verified` needs a
  `txn_ref` of 4+ characters (stored upper-case, spaces removed) or a
  `reason` for having none. `rejected` and `reopen` need a `reason`.
  Verified/rejected only from `submitted` or `missing`; `reopen` only from
  `verified` or `rejected`, and it releases the reference. A reused reference
  → `DUPLICATE_TXN_REF` 409, with `error.first` naming where it was used.
  Success → `{payment_status, payment}`.
- **`POST /admin/api/claims/{id}/void`** — admin only. Body `{reason}`.
  → `{id, voided_at}`. Unknown id → `NOT_FOUND`; already voided →
  `VALIDATION_FAILED`.
- **`GET /admin/api/gate-attempts`** — admin only → `{attempts:[{id, at,
  tg_username, tg_first_name, outcome, claimed_handle}]}`, unresolved, newest
  first. Resolving is P1.

### Shapes fixed at P0.4 and with bot.py (17 Sep)

- **`GET /api/escape/slots`** → `{capacity, booking_cutoff_minutes,
  cancel_cutoff_minutes, max_party, my_booking:{ref, slot_id, zone}|null,
  slots:[{id, starts_at, ends_at, seats_left, status}]}`. `status` is
  `open | full | closed | started | blocked`.
- **`POST /api/escape/bookings`** — `{slot_id, friends:[usernames]}`. Books
  the caller plus every friend, or nobody. → `{ref, slot_id, zone:null,
  friends}`. `FRIEND_NOT_ELIGIBLE` and `FRIEND_ALREADY_BOOKED` carry
  `error.handles`; `SLOT_FULL` carries `error.seats_left`. All booking
  refusals are HTTP 409, except `NO_BOOKING` (404).
- **`POST /api/escape/group`** — `{add:[usernames]}`, owner only, until the
  booking cutoff. **`DELETE /api/escape/group/{username}`** — owner removes
  someone they added, until the cutoff.
- **`DELETE /api/escape/bookings/{ref}`** — your own seat. → `{cancelled,
  left}`. The owner may cancel until the cancel cutoff (30 min); someone
  added by a friend may leave until the booking cutoff (5 min).
- **`GET /api/me` → `escape_booking`** = `{ref, slot_id, starts_at, ends_at,
  status, zone` (null until the game starts)`, booked_by:{name, handle, me},
  i_am_owner, can_add, can_leave, locked, edit_until, leave_until, max_party,
  group:[{name, handle, me, owner, removable, reachable}]}`. `GET /api/me`
  also returns `can_message`.
- **`POST /api/me/messages`** — `{allowed:true}` after Telegram's write-access
  prompt.
- **`GET /admin/api/slots`** — admin and gm → `{escape:[{id, starts_at,
  ends_at, capacity, booked, checked_in, half_a, half_b, blocked, running,
  done, closed}], jam:[{id, starts_at, ends_at, blocked, status: open|booked|past,
  who, ref}], seats_taken, seats_total}`.
- **New settings:** `notify_mode` (owner), `max_party` (6),
  `reminder_minutes` (10), `doors_message_at` (15:00), `last_call_minutes`
  (30), `friend_fail_limit` (10).

### Shapes fixed 18 Sep (the organiser's source of truth)

- **`POST /api/session`** (admitted) also returns `event: {venue, entry_fee,
  opens, closes, first_game, last_game, capacity, meeting_point, help_handle,
  items}`. The Mini App prints these; nothing is hard-coded.
- **`GET /api/jam/slots`** → `{per_person_limit, mine, slots:[{id, starts_at,
  ends_at, status}]}`; `status` is `open | taken | mine | closed | started |
  blocked`.
- **`POST /api/jam/bookings`** — `{slot_id}` → `{ref, slot_id, starts_at,
  ends_at}`. Refusals: `LIMIT_REACHED`, `TIME_CONFLICT` (overlaps your escape
  game, ±5 min to walk), `SLOT_FULL`. **`DELETE /api/jam/bookings/{ref}`** →
  `{cancelled}`, until the slot starts.
- **`GET /api/me` → `jam_bookings`** = `[{ref, slot_id, starts_at, ends_at,
  status, can_cancel}]`. Booking an escape game that clashes with your jam
  slot is `TIME_CONFLICT` too.
- **`GET /admin/api/session`** — any console role → the same body as login,
  with a new `csrf_token`. The older token then gets `STALE_TOKEN` (403).
- **Settings added:** `venue`, `entry_fee`, `jam_first`, `jam_last`,
  `pastry_stock`, `photo_stock` (`drink_stock` went with the drink on 19 Sep),
`jam_capacity`, `low_stock_at`. **Removed:** jam price and hold, jam hours and
  instruments, PayNow, refund policy, matcha/panini flavours and stock, booths,
  staff names. Untouched (`updated_by='system'`) rows follow the code.

### Error codes

- **Session and identity:** `INITDATA_INVALID`, `INITDATA_EXPIRED`, `NOT_ON_LIST`,
  `NO_USERNAME`, `LINKED_ELSEWHERE`, `GATE_CLOSED`, `INACTIVE`
- **Bookings:** `SLOT_FULL`, `SLOT_CLOSED`, `SLOT_STARTED`, `SLOT_BLOCKED`,
  `ALREADY_BOOKED`, `TIME_CONFLICT`, `LIMIT_REACHED`, `NO_BOOKING`,
  `FRIEND_NOT_ELIGIBLE`, `FRIEND_ALREADY_BOOKED`
- **Phone:** `PHONE_LOCKED`, `PHONE_OFF`, `NOT_YET`, `NO_BOOKING`,
  `RELOCKED`, `LINK_USED`. *`PHONE_NOT_YOUR_HALF` has not been returned since
  22 Sep, and `HALVES_LOCKED` and `NOT_CHECKED_IN` since 23 Sep — there are
  no halves, and check-in no longer gates the phone (`STATE.md` 140).*
- **Claims:** `PAYMENT_NOT_VERIFIED`, `ALREADY_CLAIMED`, `OUT_OF_STOCK`,
  `UNKNOWN_CODE`, `NOT_A_YARD_CODE`
- **Payments:** `DUPLICATE_TXN_REF` (receipt uploads were removed 18 Sep)
- **General:** `RATE_LIMITED`, `FORBIDDEN`, `VALIDATION_FAILED`
- **Added at P0.2:** `SIGNED_OUT` (401 — no console session, or it expired;
  the console returns to its sign-in screen) and `NOT_FOUND` (JSON 404/405 for
  an unknown `/api/` or `/admin/api/` path)
- **Added 18 Sep:** `STALE_TOKEN` (403 — another tab took a newer CSRF token)

HTTP status for the claim codes: `NOT_A_YARD_CODE` 400, `UNKNOWN_CODE` 404,
`PAYMENT_NOT_VERIFIED` 403, `INACTIVE` 403, `ALREADY_CLAIMED` 409,
`OUT_OF_STOCK` 409. `DUPLICATE_TXN_REF` is 409.

Every code above is already rendered in context in the prototypes' states
gallery. Keep the API contract and the front-end in sync: if a code changes,
change both.

---

## §14. Front-end code shape (already delivered)

- `templates/index.html` and `templates/admin.html`, each one file with inline
  CSS and JS.
- One data layer at the top of each file with `MODE = 'mock' | 'live'`. Mock
  responses follow §12 exactly — same shapes, same error codes. Live mode calls
  the real endpoints with the headers from §3 and §5.
- The UI never makes decisions the server owns (capacity, eligibility,
  unlock time). It renders what the server says.
- Device storage is used only for harmless preferences, never for access or claims.

Switch `MODE` to `'live'` as each endpoint lands. Do not restyle the templates —
they are the approved design.

**As built**, each file carries `MODE` *and* a `LIVE` map with one flag per
endpoint. Anything flagged `false` falls back to its mock fixture even while
`MODE` is `'live'`, so endpoints go live one at a time without a branch. The
demo controls from the prototypes (persona, clock, role, scan and review
simulators) survive as a floating panel that is never rendered in live mode.
`STATE.md` §3 lists which flags are currently on. Both files are now
`MODE = 'live'`. The console's GM demo fixtures (hint lines, reset checklist)
sit inside a Jinja `{% if show_mock_spoilers %}` block that `app.py` never
turns on, so `/admin` never ships them (§3 rule 4).

The console gained four screens the prototypes never drew — **Schedules,
Roster, Settings and Audit** — and **one shared top bar on every screen**,
both at the organiser's direct instruction after reviewing the first pass. The
Mini App's back button uses a real history stack rather than a fixed parent
map, so it returns where the person came from. Reasoning for all three is in
`STATE.md` §5.

**The 21 Sep UI pass** (organiser-directed, `STATE.md` decisions 115–121)
restyled the Mini App on purpose, so "do not restyle" above now means "do not
restyle without the organiser". What changed, with no endpoint or response
shape touched: the Up next card opens Your bookings and grows into it (View
Transitions, with a fallback); a free escape time opens its own booking page;
both rooms list people as one numbered box each; the small print under screens
is gone (deadlines are one line, computed from `edit_until` / `leave_until`);
every escape screen is dark to its edges; and a button audit fixed five places
where Back or a button landed somewhere odd. The UI still decides nothing the
server owns — the "You already have a game" message on the board is the
server's own `ALREADY_BOOKED` wording, said before the tap rather than after.

---

## Priorities (build in order; each tier works end to end before the next starts)

Live status for each item is tracked in `STATE.md` §2.

**P0 — required for the event**
1. The gate, with roster import and the `@maxi_muslim` override — **done,
   tested in Telegram**
2. The pass and booth hand-over (once-only), plus event check-in — **done,
   signed off 17 Sep**
3. Admin search and the person page, with receipts and payment status —
   **built 17 Sep, tested by the organiser (Phase 13b)**
4. Escape-room booking with capacity ~~and halves~~ — **built 17 Sep, with
   group booking; the halves went 23 Sep**
5. Phone lock and unlock ~~, with the half rule~~ — **built 18 Sep**, including
   the one-time full-page links of rule 23; **23 Sep: the booked time is the
   whole rule, and the only lock left is the GM's**
6. Jam booking — free, confirmed at once (payments dropped 18 Sep) — **built**
7. The audit log — **built**
8. Backups — **built**, automatic inside `app.py`
9. The RUNBOOK, including Tailscale Funnel and the desk devices — **RUNBOOK
   current; the tunnel and desk devices are the organiser's to set up**

**P1**
- Bot reminders, `/pass` and photo receipts — **built**
- The GM console with hint sending — **built**
- Walk-ins, gate-denial linking and "signed up as" requests — **built**
- Export in the sheet's layout — **built**
- The exact and look-alike duplicate checks — **built 18 Sep**, against the
  archived Paperform screenshots rather than in-app uploads, which were
  dropped. See §9 r30 and `STATE.md` decision 85
- Stock counts — **built**
- The Paperform webhook — **not built.** It needs a Paperform plan the
  organiser may not have, and §10's upload path is the safety net either way

**P2 — deliberately not started**
- Stats charts
- Printables (beyond the offline fallback list, which is built)
- An escape-time leaderboard (no spoilers)

Nothing in P2 affects whether the night runs, and the event is on 24 Sep. The
remaining risk is testing on real devices, not building.

Have the organiser test each tier in Telegram before starting the next. **Since
every tier is now built, that rule is spent**: the testing that is left is
`TESTPLAN.md`, split into a part the organiser can do alone and a part that
needs a group.

---

## §17. Acceptance tests

Run before the event. The test clock is on for testing only.

1. **The gate:** a listed username gets in; an unlisted friend is refused; an
   account with no username gets instructions; `@maxi_muslim` gets in without
   being listed; a refused person who types the username they signed up with
   lands on the front-desk list and still isn't let in until an admin links them.
2. Opening the app from the bot's inline button, the menu button and the direct
   link all pass the gate.
3. The same person, listed as `@Name` and as `name `, still matches.
4. Two phones hand over the same photo strip at the same moment. Exactly one
   succeeds; the other shows "already collected" with the first one's time.
5. **Escape booking:** the 13th person can't book a 12-seat game; a group
   booking with one ineligible friend books nobody; twelve bookings fill a
   game. *(23 Sep: they no longer split into halves of six — there are no
   halves.)*
6. Games start at 3:05, 3:25, 3:45 PM and so on to 9:45 PM (since 22 Sep,
   `STATE.md` 133), each with a 15:00 timer, and the hint times match Settings.
7. **`/api/escape/phone`, called directly:** refuses before the game; works for a
   checked-in desk-half player during the game; refuses a flat-half player during
   the game; refuses after the relock time; refuses everyone when the GM switches
   the in-app phone off. *Since 23 Sep: works for **everyone booked** in the
   game, checked in or not; refuses anyone not in it; the GM's Lock is the only
   lock. Since 22 Sep: open until 25 minutes after
   the start, even after End; and the GM's Start sends each player one "Open the
   phone" message.*
8. **Jam and receipts.** *Rewritten 18 Sep: jam holds and payments are gone —
   the room is free and booked as a group — and receipts are Paperform's,
   copied to the laptop, rather than uploaded.* A jam group is booked whole or
   not at all; another group cannot take seats in a slot somebody already
   holds; every member's escape game is checked for a clash, not just the
   booker's; the same screenshot on two people raises the exact-duplicate
   warning; a re-saved copy raises the look-alike warning; a transaction
   reference that's already used is refused.
9. Re-importing the same export changes nothing. Removing a row makes that
   person inactive without deleting their bookings or claims.
10. Every hand-over, void, verification, half swap and setting change appears in
    the audit log, with who and when.
11. The export reproduces the original sheet layout, with the check-in and
    redeemed columns filled.
12. Stopping and restarting `app.py` mid-test loses nothing, and backups are
    being written.
13. A typical attendee visit makes six requests or fewer (check in the ngrok
    inspector during development).
14. **The phone file** on a desk device with wifi off: plays a whole game; the
    clock photo zooms legibly; the call log shows Ryan's 10:06 PM call.
15. **Before the event:** Settings → Clock reads **Real time** (event-day mode
    no longer exists, decision 129); the Tailscale address works from mobile
    data.

### pytest plan (`tests\`)

| File | Covers |
|---|---|
| `test_gate.py` | §17.1, §17.2, §17.3; §9 r1–r9 including `LINKED_ELSEWHERE` and the rate limit on claimed handles |
| `test_claims_concurrent.py` | §17.4 — two threads INSERT the same claim; assert exactly one success and one `ALREADY_CLAIMED` carrying the first row's time, staff and station. **Written (P0.2)**; also covers §9 r20, r24–r28, r32–r33 and `GET /api/me` |
| `test_escape_capacity.py` | §17.5 — concurrent bookings against a 12-seat game never exceed capacity; all-or-nothing friend groups; **and §17.8, the jam room as a group booking** |
| `test_phone_and_gm.py` | §17.7 — all five refusal paths of §9 r21; the GM console; §9 r16 and r22 |
| `test_phone_links.py` | §9 r23 — one-time link single use, expiry, re-check on spend; the phone's pictures |
| `test_invariants.py` | The grouping rule after a removal *(the halves went 23 Sep)*; over-full games after a seat change; retired item keys; the jam room's knock-on messages |
| `test_receipts.py` | §9 r29–r30 — sha256 exact match, dhash threshold on a re-saved copy, `DUPLICATE_TXN_REF`, non-image rejection, metadata stripping |
| `test_roster_import.py` | §17.9 — idempotent re-import, float Paperform IDs, `@Name ` normalisation, blank-row skipping, inactive-on-missing |
| `test_admin_screens.py` | §17.10 and §17.11 — every console screen, settings validation, the audit log, exports in Paperform's layout |
| `test_error_reporting.py` | Every failure answers in JSON, never an HTML error page |

*Written 18 Sep: this table used to name `test_halves.py`, `test_phone_access.py`,
`test_jam_holds.py`, `test_export.py`, `test_audit.py` and `test_time.py`. Those
areas are covered, inside the files above rather than under those names. Jam
"holds" no longer exist at all — the room is free and booked as a group.*

Use a temporary SQLite file per test (not `:memory:`) so WAL and busy-timeout
behaviour is exercised for real.
