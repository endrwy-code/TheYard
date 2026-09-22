# Claude Design brief: The Yard — Telegram Mini App, booth scanner and admin console (v2)

Attached with this brief (names may differ slightly after upload):
- `PROJECT_STATUS.md`, `The_Last_Guest_20min (2).pptx`, `Si_Hong_Phone (1).html` and `The_Yard_Sign_Up_Responses.xlsx`;
- The Yard's e-invites and posters;
- the photos for the phone file: the four camera stills, Ryan's bank screenshot, and any other images the phone uses.

If anything on this list is missing, tell me before you start.

---

## 0. Your role and how we'll work

You are the lead product designer, front-end engineer and systems architect for this project. I'm the organiser, not a developer. I work on Windows with PowerShell and VS Code, and I follow numbered, copy-paste steps.

You own six deliverables:

1. **The experience.** Every screen and state for:
   - attendees, inside Telegram;
   - booth staff, the game master and admins, in a normal browser.
2. **Production-shaped front-end prototypes.** They must work and drop into my existing Flask project, not be redrawn later.
3. **A fixed phone file** for the escape room (§1).
4. **The rules the backend must follow:** the architecture, the data-integrity rules and the API contract.
5. **A beginner-proof build-and-run guide** for my exact setup (the RUNBOOK, §16).
6. **A Claude Code handoff bundle.** It must be complete enough that the Flask backend and the Telegram bot can be built without asking me architecture questions.

Work in the rounds in §15 and stop for my review after each one. §1 lists decisions I've already made, so don't ask me about them again.

Before you start Round 1, reply with four things:
- your understanding of the project, in at most 10 bullets;
- a short brand read of the e-invites and posters: colours (with hex values), type, textures, imagery and tone of voice, and how you'll carry them into the app;
- your recommended defaults for the open questions in §18 (ask me only the ones that block Round 1, five at most);
- any contradictions you spot beyond the ones listed in §1.

---

## 1. The attached files and how to use each

### PROJECT_STATUS.md

The handoff from my previous agent. It is the source of truth for my environment and for what already works.

Already done:
- bot created in BotFather, token in `.env` as `TELEGRAM_TOKEN`;
- Flask `app.py` serving `templates/index.html`;
- a working `verify_telegram_data()` initData check;
- ngrok installed and authenticated;
- the Mini App registered with BotFather (`/newapp`);
- a successful end-to-end test.

Not done yet: database, admin panel, multiple pages, hosting.

Don't redo finished steps. Two of its hosting notes are now outdated (§7.4).

### The_Last_Guest_20min (2).pptx

The escape-room design doc, and **the source of truth for the story and the puzzles**. Where the phone file disagrees with it, the deck wins.

I've changed two of its numbers: the game lasts **15 minutes, not 20**, and the reset takes **5 minutes, not 4** (§5.3).

Use it for:
- the story, mood and visual cues of The Last Guest section;
- the game-master (GM) console script: the timer, the dispatcher hint lines, the forced merge and the reset checklist, all scaled to 15 minutes (fix 7 below).

It contains the full solution, so its content is for the GM and admins only (§3, spoiler firewall).

### Si_Hong_Phone (1).html

The in-game phone: one self-contained bundled page with Messages, Phone (Recents) and Photos with pinch-zoom. It already carries its own copy of React and is built to run from a local file, which the deck requires.

- Keep its look and behaviour exactly.
- Make only the content fixes below, embed the photos, and export it again as one self-contained file that still works offline.
- If rebuilding is the only way to change it, rebuild it faithfully and show me the old and new side by side before replacing it.
- The Mini App then serves it behind the time lock (§5.3).

### The_Yard_Sign_Up_Responses.xlsx

A Paperform export, sheet "Registrations".

- **Columns:** Submitted At, Unique, Name, Telegram, Email, Submission Receipt (a link to the payment screenshot they uploaded), Checked-in, Checked in at, Redeemed, Redemmed At (sic).
- **Contents:** the current export has 17 real sign-ups, then about 1,000 blank formatted rows.
- **Data quirks:**
  - every handle starts with "@", and one has capital letters;
  - some names have trailing spaces;
  - 3 rows have no receipt link;
  - "Unique" is Paperform's submission ID, a 13-digit number that Excel stores as a float (1789457183000.0).
- **The last four columns are empty.** Our system becomes the source of truth for them and exports them back filled in.
- **Privacy:** the sheet has real names and emails. Use its structure, but put fictional people on the canvas, because designs can be shared. The one real handle you may show is @maxi_muslim.

### The Yard's e-invites and posters

My brand reference. Take The Yard's look from them: colour, type, texture, imagery and tone of voice (§13).

### The phone's photos

- Embed them in the phone file, compressed to about 1600 px on the long edge, with the wall clock still legible under pinch-zoom.
- They are game evidence. They never appear anywhere except inside the unlocked phone: not in the teaser, not as tab images, and not on any staff screen (§3, rule 4).

### Fixes and decisions

List the phone fixes for my approval in Round 1, then deliver the fixed phone file in Round 2.

1. **Escape-room timing (decided).**
   - Each game lasts 15 minutes, followed by a 5-minute changeover (the deck's reset, plus splitting the next group at the door).
   - So a new group starts every 20 minutes from 5:30 PM: 5:30, 5:50, 6:10, 6:30 PM and so on. I'll confirm the last game (§18).
   - Capacity is the deck's 10 players, five per half. I said 12 earlier, so ask me to confirm.
2. **The wall clock (decided: the deck).**
   - The clock is in the kitchen still stamped 10:27 PM (`cam-04-kitchen-2227.jpg`). It reads 10:12, exactly 15 minutes behind the stamp.
   - The phone currently marks the 10:15 PM kitchen still as the clock photo. Move that flag.
   - The deck calls this photo "still #2", but it's the fourth still in time order. Ask me whether Photos should show it second or keep time order.
   - Check the actual photos. If the clock isn't clearly visible in that still, tell me. Don't fake it.
3. **Ryan's alibi (decided: the deck).**
   - The call log must show Ryan's call at 10:06 PM lasting 18:14, as well as the 10:33 PM emergency call. The phone's log has no Ryan call yet.
   - Keep his chat messages that fit: 10:05 "stepping out" and 10:24 "20 minutes of my life gone".
4. **Whose phone it is (decided: the deck).**
   - The phone belongs to the man who found Si Hong. He hands it over already unlocked, which is why he says "take my phone".
   - On screen, never call it "Si Hong's phone". Use "The phone" until I give you the finder's name (§18).
   - Check that every chat and call makes sense from the finder's point of view, and propose minimal wording fixes for my approval.
   - The deck leaves one gap. It calls Ryan's call "outgoing", but it can only appear on the finder's phone if Ryan called the finder. Propose the simplest fix and ask me.
5. **Timeline check.**
   - The deck's timeline board (slide 11) says the 10:20 PM hallway still shows Abel stepping out to take a call.
   - Check that the phone's photos, chats and call log agree with the deck's slides on the suspects, the phone, the puzzles and the timeline board.
   - List every mismatch, each with a proposed fix.
6. **The deck's phone rule.** The deck says to run the phone as a local file on a dedicated device at the desk:
   - no wifi and no server;
   - locked in with Guided Access (iOS) or screen pinning (Android);
   - a second device;
   - a sealed envelope of printed screenshots in case a device dies.

   My in-app phone makes the one prop that must never fail depend on a server, a tunnel and the venue's signal. So:
   - the desk devices stay the main way to play;
   - the in-app phone is an extra view for the desk half of each group (§5.3);
   - the GM can switch the in-app phone off at any time without affecting the game.
7. **Timings scaled to 15 minutes.**
   - The deck's dispatcher lines at minutes 6, 9 and 14 move to 4:30, 6:45 and 10:30.
   - The forced merge moves from minute 10 to 7:30.
   - These are editable defaults. Show the deck's whole timing table scaled the same way on the GM card, for my approval.
   - The fiction changes too: the actor's "they said twenty minutes" and "twenty minutes out" in the teaser both become fifteen.
8. **Minor polish.** The phone mixes UK numbers and London places with a Paya Lebar weather widget. Ask me which setting is canon.

---

## 2. What we're building

The Yard is a one-day event. People sign up on Paperform and upload their payment screenshot. The entrance fee includes one matcha and one panini. Assume Singapore time and PayNow unless I say otherwise.

Attendees open a Telegram bot whose Mini App has three areas:

1. **The Last Guest.**
   - Book a seat in a 15-minute escape-room game. A new group starts every 20 minutes from 5:30 PM, with up to 10 players each.
   - At the door, each group splits in half. At game time, the phone unlocks inside the app for the desk half only (§5.3).
2. **Food & Drinks.** A personal pass (a QR plus a typed code) to collect the matcha and the panini, each exactly once.
3. **Jam Room.** Book a 30-minute jamming slot for $10: pay, upload the screenshot, and an admin approves it.

Staff use a separate web console in a normal browser (not Telegram) to:
- scan or type pass codes;
- hand over items exactly once;
- check people in;
- run the escape room;
- review payments;
- look anyone up by Telegram username.

Put this system map on the canvas as a diagram:

- Attendee's Telegram → Mini App (WebView) → HTTPS tunnel (Tailscale Funnel on the day; ngrok as the fallback) → Flask `app.py` on my laptop (port 5000) → SQLite `data/app.db`.
- `bot.py` ⇄ Telegram servers. It uses long polling, outbound only, so it needs no tunnel. It writes to the same SQLite file.
- Staff phones and my laptop browser → the same tunnel → Flask `/admin`.
- Paperform → Flask, either as an export I upload in `/admin` (always) or by webhook (if my plan has it).
- The desk devices run the phone file offline, with no connection to any of this.

---

## 3. Non-negotiable rules

1. **Access gate.**
   - Only people whose Telegram username is on the sign-up list get past the Start screen.
   - The check runs live on every app open and on every API call, not only in the UI.
   - Attendees never type their own username to get in. The app reads it from Telegram.
   - **@maxi_muslim is always allowed**, even when missing from the list or when the list failed to load.
2. **The server decides.**
   - Identity comes only from Telegram initData verified on the server. Reuse `verify_telegram_data()` and add a maximum-age check on `auth_date`.
   - Never trust `initDataUnsafe`, the device clock or hidden buttons for any decision.
3. **Once means once.** Each person collects each item once. The database enforces this even when two booths scan the same code in the same second.
4. **Spoiler firewall.**
   - Attendee screens may use only the public premise: Si Hong hosted four guests, collapsed at 10:30 PM, the police are fifteen minutes out, and all four guests say they had already left.
   - These appear only in the GM console, for the gm and admin roles: the solution, the clock offset, the suspects' secrets, the lock code, the hint lines and the timeline.
   - The phone's evidence photos appear only inside the unlocked phone.
   - The phone file is never reachable by any URL before its unlock time, or by a player in the other half.
5. **Keep my stack.**
   - Python, Flask, SQLite and python-telegram-bot, on Windows, reached through a free tunnel (§7.4).
   - No stack switch, and no paid services required. Flag optional paid upgrades separately.
6. **Keep traffic small.** Both free tunnels have limits. Tailscale Funnel has bandwidth caps that Tailscale doesn't publish. The ngrok fallback allows 20,000 HTTP requests and 1 GB of data out per month, and my testing counts toward that. So:
   - one HTML file per app, with inline CSS and JS;
   - libraries from public CDNs, at pinned versions;
   - no polling more often than every 30 seconds, and none while the page is hidden;
   - countdowns run on the device, corrected with the server's time;
   - images compressed;
   - every fetch sends the header `ngrok-skip-browser-warning: 1` (the ngrok fallback needs it, and it's harmless otherwise).
7. **Beginner-proof.** Every instruction for me:
   - uses Windows PowerShell syntax (`;` not `&&`, `venv\Scripts\activate`);
   - is numbered and copy-paste ready;
   - says what I should see afterwards.

---

## 4. Who uses it, and what the day is like

- **Attendees:** on phones, inside Telegram, often in a queue, in light or dark theme, with patchy signal.
- **Booth volunteers:** one phone, one hand busy, bright light, a queue. They need an unmistakable result in under a second.
- **The GM and one actor:** per the deck, the GM splits each group at the door, runs the timer and sends the actor the dispatcher lines to read out.
- **Admin (me):** on a laptop, searching people, verifying payments, fixing mistakes and watching numbers.

Everything runs from my laptop on the day (§7.4). Plan for a laptop restart mid-event without losing anything.

---

## 5. The Mini App (inside Telegram)

Build it as one HTML file with view switching (no page reloads).

Use the Telegram Web App SDK:
- `ready()` and `expand()` on load;
- `themeParams` and `colorScheme` for light and dark;
- `BackButton` for navigation;
- `MainButton` for each screen's primary action;
- `HapticFeedback` for success and error;
- `disableVerticalSwipes()` while the phone is open;
- the safe-area insets.

Other requirements:
- Send the raw initData on every call as `Authorization: tma <initData>`.
- Refetch when the app returns to the foreground.
- Include a small Telegram shim so the prototype runs on your canvas outside Telegram.

**Username boxes.** Build one reusable component and use it everywhere anyone types a Telegram username, in the Mini App and in the admin console:
- a fixed "@" sits in front of the box and can't be deleted, so people type only the username;
- autocapitalise, autocorrect and spellcheck are off;
- a pasted "@name" or t.me link is cleaned up automatically;
- a gentle hint appears when the text doesn't look like a username (5–32 letters, digits and underscores), but the server makes the decision.

### 5.1 Start screen (the gate)

The event identity and one "Start" button. On tap, show a checking state, then one of these outcomes:

- **Allowed:** go to Home.
- **Not on the list:**
  - say "We can't find @username on The Yard's sign-up list", showing the exact username Telegram gave us;
  - offer a "Check again" button;
  - add "Signed up with a different username?" with a username box. The person types the username they used on the sign-up form, and it goes to the front-desk list (§6.3). It never lets anyone in by itself. Confirm with "Sent to the front desk. Show them this screen, or tap Check again in a minute."
- **No username:** explain how to set one (Telegram Settings → Username), then offer "Check again".
- **Username linked to a different Telegram account:** "Please see the front desk."
- **Closed:** show the message from Settings.
- **Can't reach The Yard:** a retry state. A network failure is never shown as "denied".

Re-check every time the app opens. Never cache "allowed" on the device.

### 5.2 Home

- A greeting by first name.
- The three areas.
- A "Next up" card for the soonest booking, with a live countdown.
- A banner when the entrance receipt is missing or rejected, with an upload action.

### 5.3 The Last Guest

**Teaser.** Built only from the public premise (§3, rule 4).

**Game board** for the evening:
- start times are the hero: 5:30, 5:50, 6:10 PM and so on;
- each game shows its seats left ("7 of 10");
- states: open, almost full, full, booking closed, past, blocked;
- your own game stands out.

**Booking flow:**
1. Pick a game.
2. Optionally add friends by typing their usernames (the @ is already there). Each friend must be on the list and not already booked, and the whole group books or nobody does.
3. Confirm.
4. See a ticket with:
   - a reference code (ESC-XXXX);
   - the time and where to meet;
   - "Arrive 5 minutes early. The game master splits your group at the door."

People can cancel until the cutoff.

**The phone card.** Never call it "Si Hong's phone" (§1, fix 4). It has these states:
- **No booking:** "Book a game. At game time, half of your group gets the phone."
- **Before the game:** a locked-phone visual, a countdown ("Game starts 5:50 PM") and "Your half is decided at the door."
- **During the game, desk half:** "Open the phone".
  - It loads from `/api/escape/phone`, only at this point.
  - It shows full screen in an iframe created from a Blob URL.
  - Telegram's BackButton returns to The Yard, so nothing overlaps the phone's own interface.
  - Test on iOS and Android Telegram. If the Blob iframe fails, fall back to a full-page load through a one-time link (§12).
- **During the game, flat half:** "You're working the flat. The phone is with the other half, so you'll need each other." Show no phone and no countdown to one.
- **In-app phone switched off by the GM:** "The phone is at the desk."
- **After the game:** locked again ("Case closed"), which protects later groups.

**The split (decided).** One half of each group gets the phone in the app, and the other half never does. This follows the deck's two zones.
- Zone B (the desk) gets the phone. Zone A (the flat) doesn't.
- At booking, each person goes into whichever half is smaller, so the halves stay even. Players learn their half at the door.
- At check-in, the GM sees each player's half in large type, can tap to swap anyone, and can press "Re-balance" when people don't show up.
- The halves lock when the game starts.

**Unlock rules (in Settings):**
- `phone_unlock_mode` has two values:
  - `scheduled`: unlocks at the game's start time;
  - `gm_start`: unlocks when the GM presses Start for that group, so a group running late can't open it early. Recommend this one for the day.
- `require_checkin`: default on. Only checked-in players in the desk half can open the phone.
- `in_app_phone_enabled`: default on. The GM can switch it off mid-event, and the desk devices carry on.
- `relock_minutes_after_end`: default 2.

**Room settings and defaults:**

| Setting | Default |
|---|---|
| `game_minutes` | 15 (decided) |
| `changeover_minutes` | 5 (decided) |
| `first_game` | 5:30 PM (decided) |
| `last_game` | ask me |
| `capacity` | 10 (the deck's number; confirm with me) |
| `hint_times` | 4:30, 6:45, 10:30 |
| `merge_time` | 7:30 |
| `booking_cutoff_minutes` | 5 |
| `cancel_cutoff_minutes` | 30 |

Settings shows the schedule these produce, for example "12 games from 5:30 to 9:10 PM, 120 seats".

### 5.4 Food & Drinks (the pass)

- **The pass is the hero:**
  - a large QR, always dark on white (even in dark mode), with a generous quiet zone;
  - the same code as text, grouped for reading aloud (for example 7K3M-Q9XT);
  - a nudge to turn brightness up.
- **Two "punch" spots, Matcha and Panini.** Each is either ready, or visibly punched with the time it was collected.
- **If payment isn't verified:**
  - say exactly what's missing and offer a receipt upload, which goes to admin review;
  - the QR still shows so staff can find the person, but staff will see the payment warning.
- **Item variants (flavours), if any,** are chosen at the booth, not in advance, unless I say otherwise.

### 5.5 Jam Room

**Slot board.**
- 30-minute slots at $10 each, one booking per slot.
- States: open, held, pending, booked, past, blocked.
- Other people's bookings show only as "Booked", never who booked them.

**Booking flow:**
1. Pick a slot. It's held for 10 minutes, with a visible countdown.
2. See the payment details from Settings, with copy buttons:
   - PayNow name, and number or UEN;
   - the amount;
   - the reference, which is the booking code JAM-XXXX;
   - an optional PayNow QR image.
3. Upload the screenshot. The device compresses it to a JPEG of at most 1600 px.
4. See "Waiting for approval".
5. The admin approves or rejects (with a reason), and the bot messages the person either way.

**Fallback:** "Can't upload? Send the screenshot to the bot in chat." The bot attaches it to their pending booking.

**Limits:**
- at most 2 jam slots per person (a setting);
- no overlap with the person's escape-room game, counted from 5 minutes before it starts until it ends, plus a 5-minute walking buffer (a setting);
- show the cancellation rules, and a note that refunds are handled manually.

### 5.6 My bookings and help

All bookings and the pass in one list, plus a "Need help?" contact from Settings.

---

## 6. Admin console (a separate page at /admin, not in Telegram)

Responsive: desktop for me, phone for booth staff and the GM.

There are three roles:
- **admin:** everything;
- **staff:** look up people, hand over items and check people in;
- **gm:** staff rights plus the GM console (§6.6).

Admins sign in with a password. Staff and the GM sign in with a PIN plus their name and station, so the audit log reads "Booth 2 – Aisha". The GM has a separate PIN, because the GM console shows the solution and booth volunteers may have friends still waiting to play.

### 6.1 Booth mode (the most important staff screen)

**Inputs:**
- a camera scanner (html5-qrcode or similar, from a CDN);
- a large code box that also accepts Bluetooth or USB barcode scanners (it submits on Enter);
- search by username or name, for people whose phone died.

Codes are case-insensitive and ignore spaces and dashes.

**Result cards** must be readable at arm's length:
- **Valid and paid:**
  - shows name, @username, Telegram first name and entrance check-in status;
  - shows one large button per uncollected item ("Hand over matcha");
  - after the tap: a full-screen green confirmation with haptics and sound, then straight back to scanning.
- **Already collected:** full-screen red, "Matcha already collected at 3:12 PM (Booth 1, Wei)", and no button.
- **Payment not verified:** amber. Staff can't hand over; an admin can override with a reason.
- **Unknown code, not a Yard code, or inactive person:** a clear message and the next step.

Never use colour alone; always pair an icon with words.

The same result card also offers:
- event check-in, which fills the sheet's Checked-in column;
- escape-room check-in for the current or next game, showing the player's half in large type ("A — the flat" or "B — the desk");
- jam-room check-in.

### 6.2 Overview

Shows:
- signed up;
- checked in;
- payments verified, pending and missing;
- matcha and panini collected out of total (per variant, and stock left if set);
- escape seats booked per game;
- jam slots booked;
- reviews waiting.

Refresh every 30 to 60 seconds, only while the page is visible.

### 6.3 People

**Search** by:
- username (with or without @, any case, partial match);
- name;
- email;
- pass code or booking code.

**Filters:** payment status, missing receipt, never opened the app, collected or not, checked in or not, inactive.

**The person page shows:**
- identity: name, username, linked Telegram name and ID, Paperform ID, and submission time;
- receipts:
  - the Paperform receipt, previewed when the link loads as an image, otherwise an "Open receipt" button;
  - any receipts uploaded through the app or the bot;
- payment status, with Verify and Reject (a reason is required);
- their pass QR, for people whose phone died;
- claims with time, staff and station, plus Void (admin only, reason required);
- bookings, with check-in and, for the escape room, their half;
- notes;
- the audit trail;
- "Unlink Telegram account" (admin only, reason required);
- username editing (in a username box), to fix typos.

**Gate denials** also live on this page: a live list of people who tried to get in and were refused. Each row shows:
- the username Telegram gave us;
- the username they say they signed up with, if they sent one (§5.1);
- their Telegram name;
- the time.

Each row offers one-tap actions:
- "Link to an existing sign-up", for typos and changed usernames. The admin checks who the person is first (for example, name and email).
- "Add as walk-in".

**Bulk verify:** a grid of receipts to review quickly before the event.

### 6.4 Payment reviews

A queue of jam-room receipts and late entrance receipts. Each item shows:
- the image;
- the amount expected;
- the reference code;
- the booking details;
- a duplicate warning when the same or a look-alike image was already used elsewhere, with both images side by side (§9, rule 30);
- a "Transaction reference" box. Approving requires it, or a "No reference on this screenshot" choice with a reason;
- Approve, or Reject with a reason.

### 6.5 Schedules

- **The escape-room board:** a roster per game, with halves and check-in, moving a person to another game, and blocking a game.
- **The jam board:** status, receipt, and approval.

Changing slot settings must never silently drop bookings. Show which bookings are affected and block the change until they're resolved.

### 6.6 Game-master console (gm and admin only)

- The current group and the next group.
- **The split:** each player's half and check-in state, with tap to swap and "Re-balance".
- **A large 15:00 timer,** with start, pause, +1 minute and end. Start locks the halves. In `gm_start` mode, it also unlocks the phone for the desk half.
- **The phone state,** with "Unlock now", "Lock now" and "In-app phone on/off".
- **The hint schedule:**
  - the lines at 4:30, 6:45 and 10:30, and the merge at 7:30 (§1, fix 7);
  - a "Send to actor" button per line, which the bot delivers to the actor's Telegram;
  - a "sent at" mark once sent.
- **The result:** escaped (with time) or timed out.
- **The deck's reset checklist** for the 5-minute changeover. It includes putting the desk devices' phone back to its home screen. The phone file has a built-in reset, so find it and say where it is.

### 6.7 Roster and sync

1. Upload the latest Paperform export.
2. Review the preview: new, changed, unchanged, missing from this file, and problems.
3. Commit.

The page also shows when the last import ran and the webhook status (§10). Walk-ins are added here too.

### 6.8 Settings

- Event date and hours.
- Both rooms' slot settings.
- Prices.
- PayNow details.
- Cutoffs and limits.
- Item variants and stock.
- Phone options: unlock mode, the split, check-in requirement and the in-app phone switch.
- Always-allowed usernames, in username boxes (default: maxi_muslim).
- Gate open or closed, with a message.
- The actor's username.
- The organiser contact.
- Whether the staff and GM PINs are set. They're set through `manage.py`, and their values are never shown.
- A test clock (§17), which shows a loud banner on every admin screen while it's on.
- An **event-day mode**, which forces the test clock off and hides demo data.

### 6.9 Audit log and exports

A filterable log of every change.

Exports:
- **The Registrations sheet** in its original column layout, with Checked-in, Checked in at, Redeemed (the items collected) and Redemmed At (their times) filled in.
- **Bookings** as CSV.
- **Claims** as CSV.
- **A printable offline fallback list** (name, username, code, items), so booths can keep going on paper if the server goes down, then reconcile.

---

## 7. Architecture

### 7.1 Three processes, three PowerShell windows

1. **Web: `app.py` (Flask).**
   - Serves `/` (the Mini App, at the same URL BotFather already points to), `/admin`, and the JSON API.
   - Use `waitress` on event day; it runs on Windows.
2. **Bot: `bot.py` (python-telegram-bot, long polling).** It handles:
   - `/start`;
   - receipt photos;
   - reminders;
   - actor messages;
   - a sweep that expires stale jam holds.
3. **Tunnel:** Tailscale Funnel on event day, or ngrok as the fallback, forwarding to localhost:5000.

Both Python processes share `data/app.db`, which is SQLite in WAL mode with a busy timeout. Flask sends instant notifications by calling the Telegram Bot API over HTTPS directly.

Provide `scripts\start_event.ps1` to open all three windows. It asks which tunnel to use.

### 7.2 Target file layout (inside C:\Users\endrw\my-mini-app)

Keep what exists: `venv\`, `.env` (with `TELEGRAM_TOKEN`), `templates\index.html`, and `verify_telegram_data()`.

Suggested layout (flatten it if that's simpler for me):

```
app.py             pages + API + admin (web process)
bot.py             Telegram bot (bot process)
manage.py          one-off commands: init-db, import, generate-slots, set-admin-password,
                   set-staff-pin, set-gm-pin, make-secret, backup
config.py          loads .env, default settings
db.py              connection, schema, migrations, backups
auth.py            initData verification, admin/staff/gm sessions, CSRF
services\          roster.py, bookings.py, claims.py, phone.py, receipts.py, notify.py
templates\         index.html (Mini App), admin.html (console)
private\phone\     the fixed phone file (never served as a static file)
private\receipts\  uploaded screenshots (never served as static files)
data\              app.db, backups\
imports\           Paperform exports I drop in
scripts\           start_event.ps1, backup_now.ps1
tests\             pytest suite
requirements.txt, .env.example
```

### 7.3 Settings in .env

These keys live in `.env`:
- `TELEGRAM_TOKEN` (existing)
- `FLASK_SECRET_KEY`
- `ADMIN_PASSWORD_HASH`
- `STAFF_PIN_HASH`
- `GM_PIN_HASH`
- `PUBLIC_URL`
- `DATA_DIR`
- `ALWAYS_ALLOW_HANDLES=maxi_muslim`
- `PAPERFORM_WEBHOOK_SECRET`
- `TIMEZONE=Asia/Singapore`

Everything else lives in the Settings screen.

Ship a `.env.example` with comments. The `manage.py` commands generate the secret key and hash the password and PINs.

### 7.4 Hosting (decided: free, easy, and run from my laptop)

Everything runs on my laptop, so the database and the receipts stay on my own disk. The only question is which tunnel lets Telegram reach it.

**Event day: Tailscale Funnel, on Tailscale's free Personal plan.**
- It gives my laptop a fixed public address like `https://<laptop-name>.<tailnet-name>.ts.net`, with a valid HTTPS certificate, forwarding to localhost:5000. No router or firewall changes are needed.
- Rename the laptop in Tailscale first (for example, to "theyard"), because its name appears in the address.
- Caveats, which go in the RUNBOOK:
  - **Non-commercial use.** The Personal plan is meant for non-commercial use. The Yard charges an entrance fee and $10 jam slots, so ask me to confirm the event qualifies before we rely on it.
  - **Bandwidth.** Funnel traffic has bandwidth caps that Tailscale doesn't publish, so keep traffic small (§3, rule 6).
  - **Laptop.** The app is only reachable while the laptop is on, awake and online.
  - **Warning pages.** Confirm in testing that attendees reach the app directly, with no warning page.

**Development and fallback: ngrok free (already set up).**
- It gives each account one fixed dev domain, and free endpoints no longer time out, so the URL shouldn't need re-pasting after restarts. The old notes say otherwise.
- Attendees see an ngrok warning page on their first visit. A cookie hides it for 7 days.
- Its monthly limits are in §3, rule 6.

**Switching tunnels** takes four steps:
1. Run the other tunnel.
2. Update `PUBLIC_URL`.
3. Restart `bot.py`, which resets the menu button.
4. Update the Mini App URL in BotFather.

The RUNBOOK covers both directions.

**Not suitable:**
- **Render's free tier.** Its filesystem is wiped on every restart, redeploy or spin-down, which would erase the database and the receipts.
- **Cloudflare quick tunnels.** They get a new random address on every start, which breaks every link attendees already have.

Suggest paid upgrades (a paid ngrok plan, or a host with a persistent disk) only if I ask.

---

## 8. Data model

A SQLite sketch. Store times in UTC and display them in the event timezone. Write the partial unique indexes as `CREATE UNIQUE INDEX … WHERE …`.

```
attendees       id, paperform_id UNIQUE NULL, name, email, handle UNIQUE (normalised), handle_raw,
                tg_user_id UNIQUE NULL, tg_first_name, tg_username_seen, can_message,
                source (import|webhook|walk_in|owner), status (active|inactive), is_test,
                payment_status (missing|submitted|verified|rejected), paperform_receipt_url,
                pass_code UNIQUE, checked_in_at, checked_in_by, notes, created_at, updated_at

claims          id, attendee_id, item (matcha|panini), variant, claimed_at, staff_name, station,
                voided_at, voided_by, void_reason
                UNIQUE (attendee_id, item) WHERE voided_at IS NULL

slots           id, room (escape|jam), starts_at, ends_at, capacity, price_cents,
                is_blocked, block_reason
                UNIQUE (room, starts_at)
                (escape: ends_at is the end of the 15-minute game; the changeover follows it)

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

hint_sends      id, session_id, hint_key, sent_at, sent_by

one_time_links  id, token_hash UNIQUE, attendee_id, purpose (phone), expires_at, used_at

gate_attempts   id, at, tg_user_id, tg_username, tg_first_name, claimed_handle, outcome,
                resolved_by, resolved_at

audit_log       id, at, actor_type (admin|staff|gm|system|attendee|bot|webhook), actor_name,
                station, action, entity, entity_id, details (JSON)

settings        key PRIMARY KEY, value (JSON), updated_at, updated_by

import_runs     id, at, source (upload|webhook), file_name, counts (JSON), report (JSON),
                committed_at
```

---

## 9. Data validation and integrity rules

### Identity and access

1. **Normalise usernames everywhere** (import, search, the gate, friend lists and every username box):
   - trim;
   - drop a leading "@";
   - drop "t.me/" or "https://t.me/";
   - lowercase.

   Telegram usernames are usually 5–32 letters, digits and underscores. Flag anything else in the import preview rather than silently rejecting it.
2. **A person is allowed in when any of these is true:**
   - their normalised username matches an active roster entry;
   - their Telegram user ID is already linked to an active entry (so changing their username later doesn't lock them out);
   - their username is in `ALWAYS_ALLOW_HANDLES`.
3. **Link on the first successful Start.**
   - Link the roster entry to the person's Telegram user ID, which is stable, unlike usernames.
   - If that entry is already linked to a different ID, deny with "linked elsewhere". This stops someone who later takes over a recycled username.
4. **No username:** deny with instructions, unless their ID is already linked.
5. **@maxi_muslim** is always allowed. If not on the roster, create an entry with source "owner" and `is_test` on (excluded from headcounts by default).
6. **Every refusal** is recorded in `gate_attempts` for the front desk (§6.3), along with any username the person says they signed up with.
7. **A username typed on the Start screen never admits or links anyone by itself.** Anyone could type someone else's username, so an admin checks who the person is and links them. Allow at most 3 such requests per person per hour.
8. **initData:** verify the signature on every request, and reject it when `auth_date` is older than 24 hours.
9. **Gate switch:** a switch in Settings can close the app to everyone except always-allowed usernames.

### Roster import

10. **Reading the file:**
    - skip fully blank rows;
    - trim every text cell;
    - read "Unique" as an integer string, never a float;
    - keep Submitted At as display-only text, because its timezone is unknown.
11. **Matching:** match rows on the Paperform ID first, then on username. Re-importing the same file must change nothing (the import is idempotent).
12. **Missing people:** a person missing from a newer file becomes inactive and is never deleted. Their bookings and claims stay, flagged for my decision.
13. **Problems in the preview:**
    - duplicate usernames within one file;
    - invalid usernames;
    - invalid emails;
    - a changed username on an already linked person.

    Nothing is written until I press Commit.
14. **Payment status:** a receipt link sets `payment_status` to submitted. Only an admin can set verified or rejected.

### Bookings

All of these are checked on the server, inside one transaction.

15. Only allowed, active people can book or be added as friends.
16. **Escape room:**
    - one active booking per person;
    - seats are counted within the same transaction, so a game never exceeds capacity;
    - no booking for games that have started or are within the booking cutoff;
    - friends are all-or-nothing, and the group must fit;
    - each new player goes into the smaller half.
17. **Jam room:**
    - one active booking per slot, and at most N per person;
    - before inserting a hold, expire stale holds on that slot in the same transaction (otherwise the unique index still blocks it);
    - availability also treats expired holds as free.
18. **No overlaps.** A person's escape-room game counts from 5 minutes before it starts until it ends. No jam booking may overlap that, including the walking buffer.
19. The price is copied onto the jam booking when it's made, so later price changes don't affect it.
20. **Reference and pass codes:**
    - use an unambiguous alphabet (no 0, O, 1, I or L);
    - are random (never sequential) and unique;
    - use a namespaced QR payload (for example `YARD:7K3MQ9XT`), so a random QR gives a clear "not a Yard code".

### The phone

21. **`/api/escape/phone` serves the file only when all of these are true:**
    - the person has a booking for the game in progress;
    - the in-app phone is on;
    - the game has started (by the clock or by the GM, depending on the mode) and hasn't passed its relock time;
    - the person is in the desk half (when the split is on);
    - the person is checked in (when required).

    Otherwise it returns PHONE_LOCKED, PHONE_OFF, PHONE_NOT_YOUR_HALF or NOT_CHECKED_IN.
22. **Halves lock when the game starts.** After that, only the GM can swap someone, and every swap is logged.
23. **One-time links** for the full-page fallback work once, expire after about a minute, and are only issued when rule 21 passes.

### Claims and check-ins

24. A claim is a single INSERT protected by the unique index. A duplicate-key error becomes ALREADY_CLAIMED, returned with the original time, staff and station.
25. Claims require `payment_status` verified; a setting can relax this to submitted. Admin overrides need a reason and are logged.
26. Only admins can void a claim, and a reason is required. Voids are soft: the row stays.
27. **Optional stock** per item and variant: warn when low, and block at zero if the setting says so.
28. Code lookups are limited per staff session (for example, 30 a minute) to stop guessing.

### Receipts and the duplicate check

29. **Uploads:**
    - images only, at most 5 MB after on-device compression;
    - the server checks the file really is an image, strips hidden metadata, and re-saves it under a random name in `private\receipts`.
30. **The duplicate check has three layers.** It warns but never rejects on its own; the admin decides.
    - **Exact copy.** A SHA-256 fingerprint of the uploaded bytes. The same fingerprint on another person or booking raises DUPLICATE_RECEIPT.
    - **Look-alike.** A perceptual fingerprint (a difference hash computed with Pillow, no extra library) that survives re-saving, resizing and re-screenshotting.
      - A close match on another person or booking shows "possible duplicate", with both images side by side.
      - Payment screens from the same bank look alike, so keep the match threshold strict.
    - **Transaction reference.** To approve a payment, the admin types the reference number shown on the screenshot.
      - The database refuses a reference already used for another payment (DUPLICATE_TXN_REF). This is the layer that actually proves each payment counts once.
      - If a screenshot shows no reference, the admin can skip the box with a reason.
    - **Paperform receipts** are fingerprinted too when an admin opens them, if the link lets the server download the image. So a sign-up screenshot reused for a jam booking is caught.
31. Receipt files are served only to signed-in admins, never reachable by guessing a URL.

### Admin, time and safety

32. Every write goes to `audit_log`, with who, station, when, and the before and after values.
33. **Access control:**
    - staff can't change payments, settings or exports, and can't open the GM console;
    - admin sign-in is rate-limited, and sessions expire;
    - cookies are HttpOnly and Secure;
    - state-changing requests need a CSRF token.
34. **The server clock is the only clock.** Every response includes `server_time`, and the app corrects countdowns with it.
35. **The test clock** (§17):
    - affects only the server's notion of "now";
    - shows a banner everywhere in `/admin`;
    - can't be on while event-day mode is on.

### Resilience

36. **Backups:** SQLite runs in WAL mode with a busy timeout. An automatic backup copy is made every 10 minutes into `data\backups`, keeping the last 36, plus a "Back up now" button.
37. **Outages:**
    - keep the printable fallback list (§6.9) and a documented paper process;
    - after an outage, admins can enter paper claims with the real time;
    - the desk devices keep the escape room running without the server.
38. **After the event:** export, then delete receipts and any personal data I no longer need.

---

## 10. Keeping the roster up to date (Paperform)

Build these in order:

1. **Upload (must-have, always works).** I export from Paperform and upload the file in `/admin`, as often as I like (§6.7).
2. **Walk-ins (must-have).** Added by hand in `/admin` on the day, and marked paid once I've seen the payment.
3. **Webhook (optional).** Paperform webhooks exist only on certain Paperform plans. If mine has them:
   - Paperform POSTs each new submission as JSON to `/webhooks/paperform`;
   - protect the endpoint with a secret custom header;
   - answer fast, because Paperform waits only about 10 seconds;
   - upsert by Paperform ID, and log it;
   - use Paperform's "Test" button to try it.

   Submissions made while my laptop is off are missed, so the upload path stays the safety net.

The import copes with "name", "@name", "@Name " and t.me links, so my sign-up form doesn't need to change.

---

## 11. Bot behaviour (bot.py)

- **/start**
  - If allowed: greet by name, show an "Open The Yard" button, and set that chat's menu button to the Mini App.
  - That button must be an **inline-keyboard web-app button**, never a reply-keyboard one. Telegram sends no user data to a Mini App opened from a reply-keyboard button, so the gate would refuse everyone. Don't copy bot examples built around `sendData`, because they use the reply keyboard. The menu button and BotFather's direct link do send user data.
  - If not allowed: explain why (with the same wording as the gate), and log the attempt.
  - The Mini App's own gate stays the real lock, because the bot's Mini App can still be opened by anyone who finds it.
- **/pass:** sends the person's pass as a QR image with the code. It works even if the Mini App won't load, because it doesn't go through the tunnel.
- **Photos:** saved as receipts and attached to that person's pending jam booking, or else to their entrance payment. The bot replies with what it did.
- **Reminders:**
  - 10 minutes before an escape game or jam slot;
  - on jam approval or rejection;
  - optionally, when their phone unlocks (desk half only).
- **/actor <PIN>:** registers the actor's chat to receive hint lines.
- **/help:** the organiser contact.
- **Blocked bots:** if a message fails because someone blocked the bot, mark them as not messageable. Ask for write access from the Mini App when it's missing.

---

## 12. API contract

Every response is JSON in one of two shapes:
- `{ "ok": true, "data": {…}, "server_time": "…" }`
- `{ "ok": false, "error": { "code": "SLOT_FULL", "message": "…" }, "server_time": "…" }`

The UI maps error codes to copy.

### Mini App endpoints

These use the header `Authorization: tma <initData>`.

| Method and path | Purpose |
|---|---|
| POST /api/session | Start-screen check; returns status, profile and the settings the UI needs |
| POST /api/session/claimed-handle | "Signed up with a different username?" request. Works for refused people with valid initData; rate-limited (§9, rule 7) |
| GET /api/me | Home, pass, claims, payment status, bookings, phone state |
| POST /api/receipts | Upload an entrance or jam receipt (multipart) |
| GET /api/escape/slots | Escape game board |
| POST /api/escape/bookings | Book, with optional friends |
| DELETE /api/escape/bookings/{ref} | Cancel |
| GET /api/escape/phone/status | Lock state, the person's half once revealed, unlock_at, lock_at |
| GET /api/escape/phone | The phone file, only when §9 rule 21 passes; `Cache-Control: no-store` |
| POST /api/escape/phone/link | One-time link for the full-page fallback (§9, rule 23) |
| GET /phone/{token} | The phone as a full page, once |
| GET /api/jam/slots | Jam slot board |
| POST /api/jam/holds | Hold a slot; returns ref, hold expiry and payment details |
| DELETE /api/jam/bookings/{ref} | Cancel or release |

### Admin endpoints

These use the session cookie plus a CSRF header.

| Method and path | Purpose |
|---|---|
| POST /admin/api/login, /admin/api/logout | Admin password, or staff or GM PIN + name + station |
| GET /admin/api/overview | Dashboard numbers |
| GET /admin/api/people, GET /admin/api/people/{id} | Search and person page |
| POST /admin/api/people, PATCH /admin/api/people/{id} | Walk-in; edits (reason required) |
| POST /admin/api/people/{id}/payment, POST /admin/api/payments/bulk-verify | Verify or reject |
| POST /admin/api/people/{id}/unlink | Unlink a Telegram account |
| GET /admin/api/lookup/{code} | Booth lookup |
| POST /admin/api/claims, POST /admin/api/claims/{id}/void | Hand over; void |
| POST /admin/api/checkins | Event, escape or jam check-in |
| GET /admin/api/reviews, POST /admin/api/reviews/{id} | Receipt queue; approve (transaction reference or skip reason required) or reject |
| GET /admin/api/receipts/{id}/file | The receipt image, admins only (§9, rule 31) |
| GET /admin/api/slots, POST /admin/api/slots/{id}/block, POST /admin/api/escape/move | Schedules |
| GET /admin/api/gm/state | GM console state (gm and admin only) |
| POST /admin/api/gm/{slot_id}/halves | Re-balance, or swap one player's half |
| POST /admin/api/gm/{slot_id}/{action} | start, pause, extend, end, unlock, lock, phone-on, phone-off |
| POST /admin/api/gm/hints/{key}/send | Send a hint line to the actor |
| POST /admin/api/roster/preview, POST /admin/api/roster/commit/{run_id} | Import |
| GET /admin/api/gate-attempts, POST /admin/api/gate-attempts/{id}/resolve | Front desk |
| GET, PUT /admin/api/settings | Settings |
| GET /admin/api/audit, GET /admin/api/export/{kind} | Audit log and exports |
| POST /webhooks/paperform | Paperform webhook (secret header) |

### Error codes

- **Session and identity:** INITDATA_INVALID, INITDATA_EXPIRED, NOT_ON_LIST, NO_USERNAME, LINKED_ELSEWHERE, GATE_CLOSED, INACTIVE.
- **Bookings:** SLOT_FULL, SLOT_CLOSED, SLOT_STARTED, SLOT_BLOCKED, ALREADY_BOOKED, TIME_CONFLICT, LIMIT_REACHED, HOLD_EXPIRED, FRIEND_NOT_ELIGIBLE, FRIEND_ALREADY_BOOKED.
- **Phone:** PHONE_LOCKED, PHONE_OFF, PHONE_NOT_YOUR_HALF, NOT_CHECKED_IN, HALVES_LOCKED, LINK_USED.
- **Claims:** PAYMENT_NOT_VERIFIED, ALREADY_CLAIMED, OUT_OF_STOCK, UNKNOWN_CODE, NOT_A_YARD_CODE.
- **Uploads and reviews:** FILE_TOO_LARGE, NOT_AN_IMAGE, DUPLICATE_RECEIPT (a warning, not a failure), DUPLICATE_TXN_REF.
- **General:** RATE_LIMITED, FORBIDDEN, VALIDATION_FAILED.

---

## 13. Design direction

**The Yard's own look comes first.**
- Build the identity from the attached e-invites and posters: colour, type, texture, imagery and tone of voice.
- Start Round 1 with your brand read (§0), then apply it.
- Where the posters or the deck have a clear style, follow them.

**At home in Telegram.**
- Respect light and dark themes, the safe areas and Telegram's own buttons, so the app feels native.
- Let the posters' identity carry through type, colour, texture and imagery.
- If the posters' palette doesn't work in dark mode, design a dark version and show me both.

**Imagery for the three areas:**
- Use photography where it fits the posters' vibe and genuinely adds something, for example food or jam-room photos if I supply them.
- Otherwise, draw one matched set of high-quality icons in the posters' style, with consistent stroke, corner radius and weight.
- Never use the phone's evidence photos (§3, rule 4). If you want a photo for The Last Guest, ask me for a mood shot that shows none of the evidence.

**Three sections, one system:**
- **The Last Guest:** a night-time case file inside The Yard's identity.
  - Take cues from the deck and the phone. The phone's wallpaper runs from deep navy #16265C to teal #7FD8D0.
  - Time is this game's heart, so start times are the visual hero, in large tabular numerals.
  - Keep it spoiler-free.
- **Food & Drinks:** the pass as a physical ticket stub whose two spots get punched when collected, so the once-only rule explains itself.
- **Jam Room:** a rehearsal-room booking board with an obvious price and state.
- **Admin:**
  - dense and utilitarian on desktop, with keyboard-first search;
  - booth mode is huge, high-contrast and readable in sunlight;
  - the GM console is readable in a dim room.

**In Round 1,** show two distinct directions, both rooted in the posters, applied to the same three screens: Start gate, Pass, and Booth result. I'll pick one, then you build it out.

**Avoid generic templated looks:**
- identical rounded cards everywhere;
- decorative gradient washes;
- cream with terracotta;
- neon on black.

**Copy:**
- Plain, active voice, sentence case, in The Yard's tone from the posters.
- Buttons say exactly what happens ("Book 5:50 PM", "Hand over matcha"), and confirmations reuse the same verb ("Matcha handed over").
- Errors say what happened and what to do next. They don't apologise and don't use jargon: no "initData", "HMAC" or "403" on screen.

**Accessibility:**
- touch targets at least 44 px;
- AA contrast;
- reduced motion respected;
- colour never the only signal;
- tabular numerals for times and codes.

---

## 14. What to put on the canvas

Organise the canvas into these sections:

0. Read me, the brand read and the system map.
1. **Design system:** colour and type tokens, plus components (buttons, username box, slot cells, status chips, the pass, punch states, half badges, result cards, banners, empty states).
2. **Mini App flows** at 390×844, with dark-mode versions of the key screens.
3. **Mini App interactive prototype.**
4. **Admin console** (1440 wide), booth mode and the GM console (390 wide).
5. **Admin interactive prototype.**
6. **States gallery:** every error code in §12, shown in context.
7. **The fixed phone file,** with its fix list (§1).
8. **Printables:**
   - a booth cheat card (A6);
   - a GM card with the scaled timing table and the reset checklist (A5; gm and admin only);
   - a door poster with the bot's QR (A4), in the posters' style.
9. **Handoff** (§15, Round 4).

### Demo controls for review

Use adjustment sliders and toggles.

- **Mini App:**
  - a persona switcher: paid and allowed, receipt missing, not on the list, sent a "signed up as" username, no username, linked elsewhere, @maxi_muslim, desk half, flat half, server unreachable;
  - a clock slider across the evening (5:00 to 10:00 PM), to watch games close and the phone lock, unlock and relock for each half;
  - an in-app phone on/off toggle;
  - a light/dark toggle.
- **Admin:**
  - a role switcher (admin, staff, gm);
  - a scan-result simulator: valid, already collected, unpaid, unknown, not a Yard code, inactive;
  - a review simulator: clean, exact duplicate, look-alike, reused transaction reference.

### Code shape

This is what makes the handoff clean:

- `templates/index.html` and `templates/admin.html`, each a single file with inline CSS and JS.
- One data layer at the top of each file, with `MODE = 'mock' | 'live'`:
  - mock responses follow §12 exactly (same shapes and error codes);
  - live mode calls the real endpoints with the headers from §3 and §5.
- The UI never makes decisions the server owns (capacity, eligibility, halves, unlock time). It renders what the server says.
- Device storage is used only for harmless preferences, never for access or claims.

---

## 15. Rounds, priorities and build order

### Rounds

- **Round 1:**
  - the brand read, the design system and the system map;
  - the two directions on the three critical screens;
  - your answers to §18;
  - the phone fix list from §1, for my approval.

  Then stop for my review.
- **Round 2:** the full Mini App prototype with every state and the demo controls, plus the fixed phone file (photos embedded, works offline). Then stop.
- **Round 3:** the full admin console, booth mode and the GM console. Then stop.
- **Round 4:** the handoff to Claude Code, containing:
  - the production-shaped `index.html` and `admin.html`;
  - the fixed phone file;
  - `BUILD_SPEC.md`, which includes:
    - §2, §3 and §7–§12, finalised, keeping this brief's section and rule numbers so references like "§9, rule 24" still make sense;
    - the priorities below;
    - the §17 acceptance tests, plus a pytest plan that includes concurrent double-claim, game-capacity and half-rule tests;
    - an instruction to keep the API contract and the front-end in sync;
  - `RUNBOOK.md` (§16), also laid out as a readable document on the canvas;
  - `.env.example`;
  - `requirements.txt`: flask, python-telegram-bot[job-queue], python-dotenv, openpyxl, pillow, waitress, requests, qrcode[pil], pytest;
  - `scripts\start_event.ps1`;
  - a README telling Claude Code to:
    - target Python/Flask on Windows;
    - keep the existing files and the `TELEGRAM_TOKEN` name;
    - ask me before changing any rule in §3 or §9;
    - work through the priorities in order, and have me test each tier in Telegram before starting the next.

### Priorities

The backend is built in this order. Each tier must work end to end before the next one starts.

- **P0 (required for the event):**
  - the gate, with roster import and the @maxi_muslim override;
  - the pass and booth hand-over (once-only), plus event check-in;
  - admin search and the person page, with receipts and payment status;
  - escape-room booking with capacity and halves;
  - phone lock and unlock, with the half rule;
  - jam booking with receipt review and the transaction-reference check;
  - the audit log;
  - backups;
  - the RUNBOOK, including Tailscale Funnel and the desk devices.
- **P1:**
  - bot reminders, `/pass` and photo receipts;
  - the GM console with hint sending;
  - walk-ins, gate-denial linking and "signed up as" requests;
  - export in the sheet's layout;
  - the exact and look-alike duplicate checks;
  - stock counts;
  - the Paperform webhook.
- **P2:**
  - stats charts;
  - printables;
  - an escape-time leaderboard (no spoilers).

---

## 16. The RUNBOOK (my step-by-step guide)

This project isn't one piece of code. It's several systems working together: my terminal windows, Flask, the bot, the tunnel, BotFather, Telegram and the desk devices. So the guide must explain how they connect, not just what to type.

### Format for every step

- The goal, in one line.
- Why it matters and what it connects to, in one or two lines.
- The exact PowerShell commands, in a code block.
- "You should see…"
- "If you see X, do Y."

Where a step can fail in several ways, tell me to screenshot the whole window and send it with the step number. Menu labels in BotFather, Tailscale and phone settings change over time, so describe what to look for rather than exact button names.

### Phases

1. **How it fits together.**
   - The three-windows picture (web, bot, tunnel).
   - What each piece does, in plain words: Flask, SQLite, the bot, the tunnel (Tailscale Funnel or ngrok), BotFather, initData, venv, `.env`.
   - Where each file lives.
   - Why the desk devices run on their own.
2. **Save a copy** of my working project before changing anything.
3. **Install packages** into the existing venv, and create `requirements.txt`.
4. **Add the new files** from the handoff, file by file.
   - Fill in `.env` from `.env.example`.
   - Use `manage.py` to generate the secret key and to set the admin password, the staff PIN and the GM PIN.
5. **Create the database,** and check the file appeared.
6. **Import the roster** from the Paperform export.
   - Read the preview. The current file should show 17 people and 3 missing receipts.
   - Commit.
7. **Generate the games** (every 20 minutes from 5:30 PM) and the jam slots, and check both boards in `/admin`.
8. **Run the web app** locally, and sign in at http://localhost:5000/admin.
9. **Start ngrok for development,** as today.
   - Confirm the forwarding URL is my fixed dev domain.
   - Open it once and click through the warning page.
   - Use the request inspector at http://127.0.0.1:4040 to watch traffic.
10. **Point Telegram at it.**
    - Update the Mini App URL in BotFather.
    - Let `bot.py` set the menu button.
    - Check that the `/start` button is an inline button (§11).
11. **Run the bot,** and test `/start` from my account.
12. **Test everything in Telegram** with the §17 checklist. Use a friend's account for the "not on the list" case.
13. **Booth rehearsal:** two phones scanning the same code at once.
14. **Set up Tailscale Funnel for event day** (once):
    - install Tailscale for Windows and sign in;
    - rename the laptop;
    - enable HTTPS and Funnel when Tailscale asks;
    - run the funnel for port 5000 and note the address;
    - switch tunnels (§7.4);
    - test on a phone using mobile data, with wifi off;
    - confirm with me that the event fits the free plan's non-commercial use.
15. **Prepare the desk devices:**
    - copy the fixed phone file onto each device;
    - open it offline on each device type I might use (iPhone, Android, iPad, laptop), and say honestly where a platform makes that hard;
    - lock the screen to it with Guided Access or screen pinning;
    - turn auto-lock off and keep chargers attached;
    - print the backup screenshots and seal them in an envelope;
    - practise the phone's built-in reset.
16. **Event-day setup:**
    - waitress instead of the development server;
    - `start_event.ps1`;
    - the laptop never sleeps while plugged in;
    - the clock is synced;
    - a charger and a hotspot as backup;
    - backups running;
    - the fallback list printed.
17. **Event-day runbook:**
    - the day before;
    - two hours before;
    - during: what to watch (the overview, the review queue, the tunnel);
    - after: export, back up, shut down, and delete what we don't need.
18. **Troubleshooting table,** covering:
    - a blank white screen in Telegram;
    - everyone refused at Start (the app was opened from a reply-keyboard button, or the token is wrong);
    - the ngrok warning page;
    - the Tailscale address not loading (Funnel not enabled, laptop asleep or signed out);
    - INITDATA_INVALID (wrong token, expired, or `initDataUnsafe` used);
    - a PowerShell execution-policy error;
    - ModuleNotFoundError (the venv isn't active);
    - port 5000 already in use;
    - "database is locked";
    - the booth camera won't open (it needs HTTPS and permission);
    - BotFather still pointing to an old URL;
    - the ngrok monthly limit reached;
    - seeing errors inside Telegram: how to turn on Telegram's hidden setting for inspecting Mini Apps, so I can open developer tools inside one.

Also include a one-page "daily start and stop" card.

---

## 17. Acceptance tests

Run these before the event; they're listed in the RUNBOOK. Turn the test clock on for testing only.

1. **The gate:**
   - a listed username gets in;
   - a friend who isn't listed is refused;
   - an account with no username gets instructions;
   - @maxi_muslim gets in without being listed;
   - a refused person who types the username they signed up with lands on the front-desk list, and still isn't let in until an admin links them.
2. Opening the app from the bot's inline button, the menu button and the direct link all pass the gate.
3. The same person, listed as "@Name" and as "name ", still matches.
4. Two phones hand over the same matcha at the same moment. Exactly one succeeds; the other shows "already collected" with the first one's time.
5. **Escape-room booking:**
   - the 11th person can't book a 10-seat game;
   - a group booking with one ineligible friend books nobody;
   - ten bookings split into halves of five.
6. Games start at 5:30, 5:50 and 6:10 PM and so on, each with a 15:00 timer, and the hint times match Settings.
7. **`/api/escape/phone`, called directly:**
   - refuses before the game;
   - works for a checked-in desk-half player during the game;
   - refuses a flat-half player during the game;
   - refuses after the relock time;
   - refuses everyone when the GM switches the in-app phone off.
8. **Jam room and receipts:**
   - an unpaid jam hold expires after 10 minutes and the slot frees up;
   - the same screenshot uploaded twice raises the exact-duplicate warning;
   - a re-saved copy raises the look-alike warning;
   - a transaction reference that's already used is refused.
9. Re-importing the same export changes nothing. Removing a row makes that person inactive without deleting their bookings or claims.
10. Every hand-over, void, verification, half swap and setting change appears in the audit log, with who and when.
11. The export reproduces the original sheet layout, with the check-in and redeemed columns filled.
12. Stopping and restarting `app.py` mid-test loses nothing, and backups are being written.
13. A typical attendee visit makes six requests or fewer (check in the ngrok inspector during development).
14. **The fixed phone file** on a desk device, with wifi off:
    - plays a whole game;
    - the clock photo zooms legibly;
    - the call log shows Ryan's 10:06 PM call.
15. **Before the event:**
    - the test clock is off and event-day mode is on;
    - the Tailscale address works from mobile data.

---

## 18. Open questions

Answer these with clearly labelled defaults in the prototype.

1. **Event date and hours?** The phone's widget shows "Thursday 24". Is the event on Thursday 24 September?
   - Default: doors open at 5:00 PM, 30 minutes before the first game.
   - Closing time?
2. **Escape room:**
   - When does the last game start?
   - 10 players (the deck) or 12 (my earlier number)?
   - Meeting point?
3. **Escape booking:** do individuals book their own seats (default), or does one leader book a whole group?
4. **Jam room:**
   - Hours?
   - People per booking?
   - Instruments provided?
   - Is the $10 per slot (default) or per person?
   - Refund policy?
5. **PayNow details** for jam payments? Also confirm Singapore time and PayNow as the defaults.
6. **Food:**
   - Exactly one matcha and one panini per ticket (default)?
   - Flavours?
   - Stock counts?
   - Separate booths?
7. **Unverified receipts:** can staff hand over food before a receipt is verified?
   - Default: no; admin override only.
8. **Game master and actor:**
   - Who are they, and what are their Telegram usernames?
   - What is the finder's name, for the phone?
9. **Paperform plan:** does it include webhooks?
   - Default: upload-based sync.
10. **Booths and staff:** how many booths and staff, and what are their names?
11. **@maxi_muslim:**
    - Should it count as a test account, excluded from headcounts (default)?
    - Should it also be an admin?
12. **Hosting:** does The Yard count as non-commercial for Tailscale's free plan? If not, do we use the ngrok fallback on the day?
13. **Phone:**
    - `gm_start` (recommended) or `scheduled`?
    - Require check-in before the phone opens (default: yes)?
14. **The story gaps in §1:**
    - How should Ryan's 10:06 PM call appear on the finder's phone (fix 4)?
    - Should the clock photo show second in Photos, or keep time order (fix 2)?
15. **Imagery:** do I have food or jam-room photos for the three areas, or should we use icons?
