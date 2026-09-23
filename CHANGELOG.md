# CHANGELOG

A dated entry is added whenever a feature is added or removed, a bug is found
and deliberately left unfixed, the file/folder structure changes, or one
approach replaces another. Oldest first; add new entries at the bottom.

Each entry: **Changed** · **Current state** · **Left unfinished on purpose** ·
**Next step**. Decisions and their reasons live in `STATE.md` §5.

---

## 2026-09-17 — Booth QR scan kept re-triggering after a successful read

- **Changed:** Booth mode (`templates/admin.html`) was reading the same QR
  over and over, because every re-render restarted the camera. Each repeat was
  a real lookup against the 30-a-minute limit. A scan lock was added:
  `scanLocked` is set on the first read and the camera stops at once. Later the
  same day a gap was closed. After a read whose lookup showed no result (rate
  limit, network), any re-render restarted the camera and cleared the lock, so
  a pass still in view was read again. Now `wire()` does not start the camera
  while the lock is set.
- **Current state:** One read per scan. Only **Scan next**, tapping the
  full-screen result, opening Booth mode from the nav, or signing out clears
  the lock. While locked with no result, the viewfinder says "Tap Scan next to
  scan again". Leaving booth mode or hiding the tab turns the camera off.
  `camStarting` prevents two camera streams. 129 pytest tests pass; the page
  script passes `node --check`.
- **Left unfinished on purpose:** No automated test covers this, because the
  camera loop is browser-only and there is no browser test harness. It has
  not been tested on a phone yet.
- **Next step:** The organiser tests it on Android Chrome over the `https://`
  tunnel: scan a pass once, hold it in view for 10 seconds, and confirm there
  is only one lookup (one `GET /admin/api/lookup/...` line per scan in the
  `app.py` window).

## 2026-09-17 — CHANGELOG.md added

- **Changed:** New file `CHANGELOG.md` in the project root.
- **Current state:** Records features, deliberately unfixed bugs, structure
  changes and approach swaps. `STATE.md` stays the handover point.
- **Left unfinished on purpose:** Earlier work (P0.1, P0.2) is not
  back-filled; it is recorded in `STATE.md` §5, decisions 1–35.
- **Next step:** Add an entry with every qualifying change from P0.3 onward.

## 2026-09-17 — P0.3 added: people search, person page, payment verdicts, voids

- **Changed:** New endpoints: `GET /admin/api/people?q=`,
  `GET /admin/api/people/{id}`, `POST /admin/api/people/{id}/payment`,
  `POST /admin/api/claims/{id}/void`, `GET /admin/api/receipts/{id}/file`,
  and `GET /admin/api/gate-attempts` (read only). The console's People screen
  is switched to live, and the search box is wired.
- **Current state:** Built; 163 tests pass (34 new in `tests/test_people.py`).
  Admins verify with a transaction reference (or a reason for having none),
  reject with a reason, or reopen with a reason. The database refuses a
  reference used twice. Staff can search and open people but can't see
  receipts or change payments. The screen renders without errors on real
  data (checked in Node). Not yet clicked through in a browser or tested by
  the organiser.
- **Left unfinished on purpose:** bulk-verify, walk-ins, edits, unlink, and
  gate-denial link/dismiss. Their buttons say "not switched on yet" (P1).
  No receipt uploads or exact/look-alike duplicate checks yet (P0.6/P1).
- **Next step:** Organiser runs `RUNBOOK` Phase 13b. After sign-off, P0.4.

## 2026-09-17 — Structure: `services/people.py` and `tests/test_people.py` added

- **Changed:** Two new files. `services/claims.py` `ClaimError` gained
  `NOT_FOUND` (404) and `DUPLICATE_TXN_REF` (409); the people service reuses it.
- **Current state:** `app.py` routes stay thin; the logic is in the service.
- **Left unfinished on purpose:** `services/receipts.py` (uploads) is still
  to come at P0.6.
- **Next step:** None.

## 2026-09-17 — Approach swap: "reference already used" decided by the server

- **Changed:** The People screen used to mark reference `8842119` as "already
  used" in the browser (prototype logic). Now the `receipts_txn` unique index
  decides when Verify is pressed, and the error names where the reference was
  first used. The void button, which always sent claim id 1, now sends the
  real claim id.
- **Current state:** The browser shows only the server's answer. A
  four-thread race test proves one reference verifies one payment.
- **Left unfinished on purpose:** Nothing.
- **Next step:** None.

## 2026-09-17 — Known issue, not fixed: Paperform receipt links expire before the event

- **Changed:** Nothing in the data. The person page now reads `expires=` from
  each link, stops offering expired ones, and says so.
- **Current state:** Every link expires exactly 7 days after its submission.
  The current 14 die between 22 Sep 15:26 and 23 Sep 17:42 SGT. It is not
  known whether a fresh export gives fresh links.
- **Left unfinished on purpose:** The server does not save its own copy of
  each receipt. That belongs with the P1 duplicate checks (§9 r30).
- **Next step:** Organiser verifies every payment before 22 Sep 15:00 SGT.
  If that slips, build the receipt-copy step ahead of the rest of P1.

## 2026-09-17 — Feature added: bot.py and bot messages

- **Changed:** New `bot.py` (`/start`, `/pass`, `/help`, menu button) and
  `services/notify.py`. It sends a short list of messages: friend added or
  removed, a friend left, game reminder at T−10, "your matcha/panini is being
  made" (booth Call button, now live), payment verified or rejected,
  doors-open and last call on event day. New `manage.py` commands: `notify`,
  `notify-test`, `outbox`, `set-public-url`. `PUBLIC_URL` is set in `.env`.
  The Mini App's Home asks for permission to message when it isn't given.
- **Current state:** Built and unit-tested; the commands were run against a
  scratch database. Messages are in **test mode** (`notify_mode=owner`):
  only `@maxi_muslim` gets them. Not yet run against real Telegram.
- **Left unfinished on purpose:** receipt photos in the bot, `/actor` and
  hint sending (P1); the phone-unlocked message (P0.5); jam approval
  messages (P0.6).
- **Next step:** `RUNBOOK` Phase 13c; then `python manage.py notify on`
  before the event.

## 2026-09-17 — Approach swap: outbox instead of Flask calling Telegram

- **Changed:** BUILD_SPEC §7.1 had Flask call the Bot API directly. Now
  Flask queues a `notifications` row inside the same transaction, and
  bot.py sends it.
- **Current state:** Retries, expiry, de-duplication and a double-send guard
  are covered by `tests/test_notify.py`.
- **Left unfinished on purpose:** nothing is sent while bot.py is stopped.
  Messages wait, and expire if they go stale.
- **Next step:** Keep the bot window open on the day (`scripts/start_event.ps1`
  already opens it).

## 2026-09-17 — Feature added: P0.4 escape booking with friend groups

- **Changed:** `services/bookings.py`, the 14 real games (generated in
  `data/app.db`), and these endpoints: `GET /api/escape/slots`,
  `POST /api/escape/bookings` (with friends), `POST /api/escape/group`,
  `DELETE /api/escape/group/{handle}`, `DELETE /api/escape/bookings/{ref}`,
  and `GET /admin/api/slots`. `GET /api/me` now returns the real booking and
  group. The Mini App gained the "Who's coming?" panel and a group editor on
  the ticket.
- **Current state:** Built; 57 new tests (220 total). The booker must play,
  and only the booker edits the group, by add/remove only. Edits lock 5 min
  before; friends can leave until then. Groups are all or nothing, capped at
  6, and seats are per person, so part-filled games stay open. Not yet
  tested by the organiser.
- **Left unfinished on purpose:** P0.5 phone unlock (interim status says the
  phone is at the desk during a game); GM half re-balancing; admin
  block/move (the buttons say so); jam booking.
- **Next step:** `RUNBOOK` Phase 13c.

## 2026-09-17 — Structure: new files and a new table

- **Changed:** Added `bot.py`, `services/bookings.py`, `services/notify.py`,
  `tests/test_escape_capacity.py` and `tests/test_notify.py`, plus the
  `notifications` table and six Settings defaults (`notify_mode`,
  `max_party`, `reminder_minutes`, `doors_message_at`, `last_call_minutes`,
  `friend_fail_limit`).
- **Current state:** Created automatically on the next start (`db.init_db`).
- **Left unfinished on purpose:** the Settings screen still can't edit them
  (no Settings endpoint).
- **Next step:** Build `GET/PUT /admin/api/settings` before P0.6.

## 2026-09-17 — Known issue, not fixed: API tests use the real clock

- **Changed:** Nothing.
- **Current state:** The Mini App booking tests call the API with today's
  date and assume it is before 24 Sep 2026.
- **Left unfinished on purpose:** a fixed test clock for the API.
- **Next step:** Add one if the tests need to run after the event.

## 2026-09-18 — Event facts changed to the organiser's source of truth

- **Changed:** 24 Sep (Thu), 5–10 PM, @ Hub @ L5 Hafary. Entry is $12, or
  $10 early bird until 20 Sep 23:59. The two items included with entry are
  now a **cookie or pastry** and a **canned drink**
  (`config.ITEMS`, keys `pastry` and `drink`), replacing matcha and panini.
  Everything else (food, DIY, photobooth) is paid at the front desk, not in
  the app. The last escape game is 9:30 PM (13 games, 156 seats). New
  settings: `venue`, `entry_fee`, `jam_first`, `jam_last`,
  `pastry_stock`, `drink_stock`. The settings sync
  (`db.seed_settings`) updates any value still owned by the system and
  deletes removed keys. Values changed by hand are kept.
- **Current state:** The Mini App, console, bot text and services read items
  and facts from config/settings; nothing names matcha or panini. 236 tests
  pass.
- **Left unfinished on purpose:** The free photo strip is not a tracked
  item. Adding it is one line in `config.ITEMS` if the organiser wants it.
  Old claims in the real database stay under `matcha`/`panini` keys (test
  data only).
- **Next step:** Restart `app.py` (the sync runs on start), then
  `python manage.py generate-slots`.

## 2026-09-18 — Feature removed: booth "Call" button and its bot message

- **Changed:** `POST /admin/api/claims/call`, `callItem`, the button and the
  "being made" message are gone.
- **Current state:** The included items are handed over from stock, so there
  is nothing to call anyone back for. In testing it did not ping anyone
  because bot.py was not running.
- **Left unfinished on purpose:** Nothing.
- **Next step:** None.

## 2026-09-18 — Approach swap: jamming studio is free; receipts and Reviews removed

- **Changed:** Jam slots have no price, hold or approval. `POST
  /api/jam/bookings` books straight away (one slot a person,
  `jam_per_person`), `DELETE /api/jam/bookings/{ref}` cancels, and
  `GET /api/jam/slots` shows the board. Slots run from 5:00 to 9:30 PM,
  30 min each (10 slots). Clashes with the person's escape game (±5 min
  walk) are refused both ways. The console's Reviews screen, receipt
  uploads, PayNow settings and the `data/receipts` folder are removed. The
  People screen shows each jam booking.
- **Current state:** Built and tested.
- **Left unfinished on purpose:** Admin block/move for jam slots (button says
  not switched on).
- **Next step:** Organiser books and cancels a jam slot from the phone.

## 2026-09-18 — Feature added: "You're booked" confirmation

- **Changed:** After booking a game the Mini App opens the ticket with a green
  "You're booked" banner (game, time, how many friends, ref) and a success
  buzz. After a jam booking it opens My bookings with the same banner. A
  friend who can't be found keeps the booker on the form with the reason
  (intended).
- **Current state:** Checked with recorded real server answers in Node; not
  yet on a phone.
- **Left unfinished on purpose:** Nothing.
- **Next step:** Organiser books once from the phone and confirms it feels
  certain.

## 2026-09-18 — Bug fixed: console lost the sign-in on refresh and didn't update

- **Changed:** New `GET /admin/api/session`. A reload now resumes the sign-in
  and returns to the same screen. If another tab took a newer security token,
  the server answers `STALE_TOKEN` and the page fetches its token again and
  retries once. The People screen refreshes every 30 s while the tab is in
  front, unless someone is typing in search or the reference box.
- **Current state:** Tested (session resume, stale token, signed out).
- **Left unfinished on purpose:** No live push; 30 s is the delay.
- **Next step:** Organiser rechecks step F.

## 2026-09-18 — Structure: demo mode removed from both pages

- **Changed:** The Mini App is live-only (no mock data, no demo panel, no
  phone view). The console's demo panel, `MODE` and `LIVE` switches, and fake
  answers for built screens are removed. Unbuilt screens (Overview, GM,
  Roster, Settings, Audit, block/move, export, backup) still use demo answers
  listed in `NOT_BUILT` in `admin.html`. Unused CSS was removed from both
  pages. `static/qr-demo.png` was deleted (the pass shows a real QR; the
  original stays in `prototypes/assets`). The booth now shows one hand-over
  button per remaining item, and when everything is collected it still lists
  when and where each item went.
- **Current state:** Both scripts pass `node --check`; no unused CSS classes.
- **Left unfinished on purpose:** Those unbuilt screens still show demo
  numbers. Don't trust Overview, Settings or Audit yet.
- **Next step:** Build the Settings endpoint, then Overview.

## 2026-09-18 — Known issue, not fixed: the bot only works while its window is open

- **Changed:** Nothing in the code. In testing `/start` got no reply because
  `bot.py` was started from `C:\Users\endrw` with the system Python, so it
  never ran.
- **Current state:** Messages wait safely in the outbox and are sent once the
  bot runs (test mode: only `@maxi_muslim`). Stale ones expire.
- **Left unfinished on purpose:** No auto-start or watchdog.
- **Next step:** Start it from `C:\Users\endrw\my-mini-app` with the venv
  (RUNBOOK Phase 11).

## 2026-09-18 — Feature added: the photo strip is a third included item

- **Changed:** `config.ITEMS` now has `photo` ("Photo strip"), with a
  `photo_stock` setting. The pass, the booth, the person page, the bot's
  `/pass`, last-call and payment messages, the Overview and the exports all
  pick it up from that one list.
- **Current state:** Built and tested (291 tests).
- **Left unfinished on purpose:** Nothing.
- **Next step:** Hand one over at the booth in the next test.

## 2026-09-18 — Approach swap: the Mini App's new design system ("Yard Paper")

- **Changed:** `templates/index.html` rebuilt on `DESIGN.md`: matte paper
  with grain, halftone blocks, Anton for titles and times, Archivo for the
  rest (Space Mono and Inter retired). Repeated information and dot-separated
  strings are gone. Home is a numbered list with arrows. The pass shows only
  the QR and code, then one row per item with a single status. The black
  "included with entry" note moved to Bookings & help. The ticket shows the
  arrival time and half as fact rows. Countdowns read "in 7 days". The top
  bar's title is blank where the screen has its own big title. The Food &
  drinks section is now called "Your pass", because it includes the photo
  strip.
- **Current state:** Rendered in headless Chrome at 390px from recorded real
  answers; the booking flows pass the Node render test. Not yet on a phone.
- **Left unfinished on purpose:** No dark theme (the design is paper by
  choice). The console only got the new type and grain, not a full redesign.
- **Next step:** The organiser looks at it in Telegram and says what to tweak.

## 2026-09-18 — Bug fixed: stripped animations and layout breakpoints

- **Changed:** An earlier CSS clean-up had removed the `@keyframes` and
  `@media` wrappers in both pages. The Mini App had no animations. The
  console used its phone layout on every screen: one-column People,
  two-column stats. Both are restored, with breakpoints at 600/700/800/900/
  1000/1200px.
- **Current state:** Console screens checked in headless Chrome at 1440px.
- **Left unfinished on purpose:** Nothing.
- **Next step:** None.

## 2026-09-18 — Feature added: P0.5, the in-app phone and the GM console

- **Changed:** New `services/game.py`. `GET /api/escape/phone` serves
  `private/phone/the-phone.html` only while §9 r21 holds: the game has
  started, it isn't past the relock time, the in-app phone is on, the person
  is in half B, and (if Settings asks) they are checked in. `GET
  /api/escape/phone/status` gives the real code. The GM console is live:
  pick a game, Start, Pause/Resume, +1 min, End, Lock/Unlock phone, in-app
  phone on/off, swap a half, even out the halves, and mark each script cue
  done. The timer ticks on the device. The hint lines moved out of the page
  into `private/gm/script.json`, sent only to gm and admin sign-ins. The bot
  has `/actor <GM PIN>`, and hint lines go to that chat through a new
  `direct_messages` queue. New column `game_sessions.paused_at` (added
  automatically).
- **Current state:** 22 new tests (`tests/test_phone_and_gm.py`).
- **Left unfinished on purpose:** One-time full-page phone links (§9 r23).
  The in-app iframe covers it. The GM can't check people in from the GM
  screen; check-in is at the booth.
- **Next step:** Rehearse a whole game with two phones (RUNBOOK Phase 13d).

## 2026-09-18 — Feature added: every console screen is live

- **Changed:** New `services/admin.py` and `services/export.py`, with these
  endpoints: Overview, Settings (get/save, with validation), Audit (filters,
  search), Back up now, exports (Registrations sheet in Paperform's columns,
  bookings, claims, a printable fallback list), Roster (summary, upload
  preview, commit), walk-ins, gate-list Link/Dismiss, Unlink, block/unblock
  a slot, and move a person to another game (they get a message). Saving game
  or jam times rebuilds the timetable and names anyone still booked on a
  removed time. The web app now makes a backup every `backup_minutes` by
  itself. The console's demo answers are gone.
- **Current state:** 33 new tests (`tests/test_admin_screens.py`). Every
  screen renders from real answers.
- **Left unfinished on purpose:** Unlink/relink edits beyond that; the
  Paperform webhook.
- **Next step:** RUNBOOK Phase 13d.

## 2026-09-18 — Approach swap: live updates instead of 30-second polling

- **Changed:** New `GET /admin/api/live`, a server-sent-events stream. It
  sends a change marker within about a second of any write, and the console
  reloads the screen you're on unless you're typing. One stream counts as one
  request, so it stays inside §3 r6 even on ngrok. Streams close after 4
  minutes and the browser reconnects. If the stream can't connect, the old
  30-second refresh takes over. The top bar shows a green "LIVE". waitress
  now runs with 24 threads (`scripts/start_event.ps1`), because each open
  console holds one.
- **Current state:** Tested with Flask's client.
- **Left unfinished on purpose:** The Mini App doesn't live-update (it
  refreshes when you open a screen). That keeps attendee traffic small.
- **Next step:** Watch the LIVE dot on two laptops during the rehearsal.

## 2026-09-18 — Structure: new files

- **Changed:** Added `DESIGN.md`, `services/game.py`, `services/admin.py`,
  `services/export.py`, `private/gm/script.json`,
  `tests/test_phone_and_gm.py` and `tests/test_admin_screens.py`, and the
  `direct_messages` table. New settings: `photo_stock`, `paid_extras`,
  `actor_chat_id` (internal).
- **Current state:** Created automatically when app.py starts.
- **Left unfinished on purpose:** Nothing.
- **Next step:** None.

## 2026-09-18 — Bug fixed: the roster import could not be committed

- **Changed:** `roster.preview` built its "who already exists" map with
  `WHERE source != 'owner'`, hiding the organiser's own `@maxi_muslim` row.
  When they filled in their own Paperform, the preview planned them as a new
  person and the commit hit the UNIQUE index on `attendees.handle`, rolling
  the whole import back. It now matches against every row. Because that map
  now also holds walk-ins and the owner, rule 12's "missing becomes inactive"
  sweep was scoped to `source='import'` — otherwise the first re-import during
  the event would have deactivated every walk-in and taken their passes with
  them. `commit` also re-checks for a clash as it writes and names the person,
  for the case where someone is added by hand between preview and commit.
- **Current state:** Fixed and proved against the organiser's real uploaded
  file on a copy of their database: 15 new, 1 changed (them), 0 missing,
  commit clean, and a second import of the same file changes nothing. Four
  regression tests in `tests/test_roster_import.py`.
- **Left unfinished on purpose:** Nothing. Note that scoping rule 12 is an
  interpretation of a §9 rule — a walk-in is never in a Paperform export, so
  it cannot be "missing" from one. Flagged to the organiser.
- **Next step:** The organiser re-uploads the file and commits the fresh
  preview. The preview stored on 17 Sep was built by the old logic and will be
  refused by name.

## 2026-09-18 — Approach swap: a crash is no longer reported as a network fault

- **Changed:** `app.py` caught only `ClaimError`, so any other exception became
  Flask's HTML error page. Both pages read every answer with `res.json()`, so
  the parse threw and the only thing they could say was "Can't reach The Yard".
  Added: a catch-all handler returning JSON, an `sqlite3.IntegrityError` branch
  returning 409 with the constraint named, `logging.basicConfig` so the app.py
  window prints a timestamped traceback, and distinct wording in both pages
  ("something went wrong at our end" vs "can't reach").
- **Current state:** Five tests in `tests/test_error_reporting.py` prove an API
  route never answers with HTML, whatever goes wrong inside it.
- **Left unfinished on purpose:** Nothing. The two messages mean different
  things and must stay different: one is the tunnel, one is us.
- **Next step:** None.

## 2026-09-18 — Feature added: receipt copies, and the duplicate warnings

- **Changed:** New `services/receipts.py`, `manage.py fetch-receipts`, a
  "Save receipt copies" card on Audit → Exports & backups, and three
  endpoints (`POST /admin/api/receipts/archive`, `GET .../status`,
  `GET .../{id}/file`). Paperform signs each receipt link to expire 7 days
  after that person signed up, so all 14 die before the event. A copy is taken
  onto the laptop, re-saved to strip EXIF (§9 r29), stored under a random
  filename, and served only to a signed-in admin (§9 r31). The person page
  prefers the copy over the link. Having local bytes also restored §9 r30's
  first two layers after uploads were dropped: SHA-256 for an exact copy and a
  difference hash for a look-alike, both shown on the person page above the
  Verify button. They only ever warn.
- **Current state:** 21 tests in `tests/test_receipts.py`, against the real
  export's 14 links. A flat image's difference hash is degenerate, so blank
  images are excluded from look-alike matching rather than accusing everyone.
- **Left unfinished on purpose:** No re-fetch of an expired link — nothing can.
  Those stay in Paperform's own dashboard and the failure names them.
- **Next step:** The organiser runs it **before 22 Sep 15:26**.

## 2026-09-18 — Feature added: one-time links for the full-page phone (§9 r23)

- **Changed:** New `phone_tickets` table, `POST /api/escape/phone/link`, and
  `GET /p/{token}` — deliberately outside `/api/` because it opens in the real
  browser where there is no initData. Ninety seconds, single use, spent with a
  conditional UPDATE so a double tap cannot open two, and **rule 21 is
  re-checked as it is spent**, so locking the phone reaches a link already in
  someone's hand. The Mini App offers it quietly under the main button.
- **Current state:** 15 tests in `tests/test_phone_links.py`. This was the last
  unbuilt rule in the specification.
- **Left unfinished on purpose:** Nothing.
- **Next step:** Test it on a real phone (TESTPLAN A5 step 18, B3 step 11).

## 2026-09-18 — Bugs fixed: halves after a removal, and shrinking a game

- **Changed:** Two invariants that broke quietly. (1) §9 r16 balances the
  halves on the way up only, so a group of six that lost two from the desk half
  arrived 3 and 1 — and the desk half is the half with the phone. Halves now
  even out whenever someone leaves **before the game starts**; after the start
  nothing is touched, because §9 r22 locks them and only the GM moves anyone.
  (2) Lowering the seat count in Settings left games holding more people than
  they seat, silently. `generate_slots` now reports an `over` list and Settings
  names the game and how many to move.
- **Current state:** Nine tests in `tests/test_invariants.py`. Found by probing
  ordinary sequences rather than by a failing test.
- **Left unfinished on purpose:** An over-full game is reported, not corrected.
  Throwing a booked person out automatically would be worse than telling an
  admin to move them.
- **Next step:** None.

## 2026-09-18 — Bug fixed: the test suite would have failed on event day

- **Changed:** Slots are generated on `config.EVENT_DATE`, and tests that
  booked through the web API used the laptop's real clock, so every one of them
  would have started failing on 25 Sep with `SLOT_STARTED`. The RUNBOOK has the
  organiser run the suite on the morning of the event and stop if it is not
  green, so this was a false alarm waiting for the worst possible moment.
  `conftest.TEST_NOW` pins the API's clock.
- **Current state:** 345 tests pass, and the result now means the same thing on
  any date.
- **Left unfinished on purpose:** Nothing.
- **Next step:** None.

## 2026-09-18 — Structure: TESTPLAN.md, HOW_IT_WORKS.md, check_pages.mjs

- **Changed:** Testing moved out of `RUNBOOK` Phases 13c/13d into one file,
  `TESTPLAN.md`, split by what each test needs: Part A alone with one phone,
  Part B with the crowd. The phases now point at it, so there is one list
  rather than two that drift. `HOW_IT_WORKS.md` explains the five layers, which
  layer each error message points at, and traces the roster bug end to end as a
  worked example. `scripts/check_pages.mjs` runs `node --check` on each page's
  inline script, which `node --check` cannot do on HTML directly. Phase 18
  gained four rows; the stale `236 passed` became `345 passed` in five places,
  and the "Block isn't switched on yet" expectation was removed — it was built
  on 18 Sep.
- **Current state:** `README.md` reading order points at both new files.
- **Left unfinished on purpose:** Nothing.
- **Next step:** The organiser runs TESTPLAN Part A.

## 2026-09-18 — Approach swap: friends who book together stay together

- **Changed:** `services/bookings.py` gained `_assign_halves`, which decides
  both halves for a whole game at once instead of putting each new player in
  the smaller half as they arrive. The old behaviour alternated A, B, A, B
  down a booking and split every group of friends across the flat and the
  desk. Groups are now kept whole, largest first, and split only when there is
  no alternative: when a group is alone in the game, or when it is larger than
  one half. The GM's "even out the halves" calls the same function, because
  doing it separately meant the button quietly undid the grouping.
- **Current state:** Nine tests in `tests/test_invariants.py` cover it,
  including the rule that neither half may be empty when two or more are
  booked — the desk half holds the phone, so an empty desk is an unplayable
  game.
- **Left unfinished on purpose:** A group alone in a game is still split.
  There is nobody else to fill the other half and The Last Guest is played
  from both rooms, so this is the game's own design rather than a compromise.
- **Next step:** Confirm with real people in TESTPLAN Part B, step 5.

## 2026-09-18 — Feature added: the phone's pictures

- **Changed:** The phone asks for `assets/<name>.jpg` relative to itself and
  contained no images at all. New folder `private\phone\assets\` with a README
  naming every file, `GET /api/escape/assets/<name>` and
  `GET /p/<token>/assets/<name>` to serve them, and
  `python manage.py phone-images` to report what is still missing. The
  pictures are served behind the **same §9 r21 check as the phone itself** —
  they are the evidence, and §3 r4 says the evidence never reaches an attendee
  screen. Only names on a fixed list are served, so the route cannot be walked
  out of the folder. A picture that does not exist yet answers with a plain
  grey tile, so the whole game can be rehearsed before the photographs arrive.
  The one-time phone link is now `/p/<token>/` with a trailing slash, because
  a browser resolves relative paths against the directory part of the address;
  a link without it redirects, and the redirect does not spend the single use.
- **Current state:** 20 tests in `tests/test_phone_links.py`, including one
  that reads the real phone file and fails if it is ever rebuilt with
  different image names. Five story pictures and seventeen optional filler
  ones are still to be supplied by the organiser.
- **Left unfinished on purpose:** The images are not embedded into the phone
  file. It is a bundled export, and cutting into a minified bundle days before
  the event is not worth the risk; a desk device opens the file from disk and
  the same relative paths work with no server at all.
- **Next step:** The organiser adds the five photographs.

## 2026-09-18 — Feature added: the low-stock threshold is a Settings row

- **Changed:** The organiser asked whether they could change "low stock" on
  the Settings screen. They could not — it was `config.LOW_STOCK_AT`, needing
  a file edit and a restart. It is now the setting `low_stock_at`, starting at
  5, with a row on the Settings screen; `config.LOW_STOCK_AT` is only the seed.
- **Current state:** Three tests in `tests/test_invariants.py`.
- **Left unfinished on purpose:** Nothing.
- **Next step:** None.

## 2026-09-18 — Feature audit: every screen checked against its purpose

- **Changed:** No code. Each screen was asked for exactly what it renders and
  the answer checked against what that screen is *for* — not merely that the
  endpoint returned 200. 38 checks across the Mini App gate, pass, booking,
  ticket, jam and phone, and the console's Overview, People, Booth, GM,
  Schedules, Settings, Audit, Roster and exports.
- **Current state:** 0 failures. Three apparent failures on the first run were
  the audit guessing wrong key names, not defects: the real payloads use
  `seats_left`, `i_am_owner`/`can_add`/`can_leave`, and `people`.
- **Left unfinished on purpose:** This is a server-side audit. Whether each
  screen *draws* its answer correctly on a real phone is what TESTPLAN Part A
  is for, and that has still never been done.
- **Next step:** TESTPLAN Part A.

## 2026-09-18 — Approach swap: the jamming studio is booked as a group

- **Changed:** The jam room was one booking per slot — whoever got there first
  held the whole room alone. The organiser's reason for changing it: an escape
  room with strangers is cool, a jamming room with strangers is weird. It is
  now booked the way the escape room is, for up to `jam_capacity` (15, a new
  Settings row), all or nothing, and **the room does not have to fill** —
  leftover seats are not offered to anyone else. A slot belongs to the group
  that booked it, enforced with a new `SLOT_TAKEN` refusal rather than only
  shown on the board. The booker adds and removes people; anyone else can only
  leave. The clash check runs for **every member's** escape game, not just the
  booker's. The screen keeps its approved design: the same "Who's coming?"
  panel, now shared by both rooms.
- **Current state:** 381 tests pass. `jam_bookings` gained `booked_by_id` and
  `cancelled_at`; the unique index `jam_one_per_slot` was dropped (via a new
  `db.DROPPED_INDEXES` step that runs before the schema, so an index a rule
  outgrew cannot survive and keep enforcing the old rule) and replaced by
  `jam_one_seat_each`.
- **Knock-on effects, found rather than waited for:** four new bot messages
  (`jam_friend_added`, `jam_removed`, `jam_friend_left`, `jam_cancelled`) and
  a `jam_booked` that names the group, all added to `manage.py notify-test`;
  `cancel-group` now clears jam seats too, since clearing only the escape game
  would leave half a test behind; Schedules shows the booker plus a head count;
  Overview's "Jam slots" gained the number of people; the bookings export
  gained a "Booked by" column, without which a slot reads as several unrelated
  people; the person page names whose slot it is. **Reminders needed no
  change** — they are queued per booking row and every member has one, so they
  already reach the whole group. `block_slot` needed nothing either, for the
  same reason.
- **Left unfinished on purpose:** Nothing. Note that `jam_per_person` is still
  1, so a person holds one slot whether they booked it or were added to it.
- **Next step:** TESTPLAN A4 (alone) and B1b (with a group).

## 2026-09-18 — Home screen: the hours moved, the wordmark arrived

- **Changed:** The opening hours left the top-right corner of Home. The phone
  draws its own clock in the status bar directly above, and two times in one
  corner read as a contradiction rather than information. They moved to
  Bookings & help under a new "When and where" heading, where somebody is
  actually looking them up, and they are still on the gate screen, where
  somebody is deciding whether to come. On the left, "The Yard" in type became
  the wordmark, drawn as a CSS mask filled with `var(--ink)` rather than an
  `<img>`: the artwork is black on transparent and the paper ground is warm, so
  a flat black PNG sits a shade cooler than the type beside it. Home only —
  every other screen has to say where you are, not whose app this is.
- **Current state:** Both pages pass `scripts/check_pages.mjs`.
- **Left unfinished on purpose:** Nothing. A browser with no mask support falls
  back to the word, which is why the text node is still there.
- **Next step:** The organiser looks at it on a phone.

## 2026-09-18 — Question answered, no change: how the booth knows what to hand over

- **Changed:** Nothing. The organiser asked how a volunteer knows what a person
  is collecting after a scan. It was already built: a scan shows the person and
  then one button per item still to collect, with a red line giving the time,
  station and staff name for anything already taken.
- **Current state:** Unchanged, and covered by the concurrency tests.
- **Left unfinished on purpose:** Nothing.
- **Next step:** None.

## 2026-09-19 — Approach swap: the jam room is booked by instrument

- **Changed:** This reverses part of yesterday's change, at the organiser's
  instruction. Five instruments (`config.INSTRUMENTS`: acoustic guitar,
  electric guitar, keyboard, drums, bass), one seat each, and **anyone may
  join a slot somebody else started** — the opposite of "the room is theirs".
  The reasoning changed with the model: five strangers each on their own
  instrument is a jam, whereas five strangers sharing a room with nothing to
  do was the awkward thing the previous rule avoided. `SLOT_TAKEN` is gone and
  `INSTRUMENT_TAKEN` replaced it. A booking still brings friends, all or
  nothing, and each names an instrument.
- **Current state:** 392 tests pass. New index `jam_one_player_per_instrument`
  decides a race for the last drum kit; it lives in a new `db.LATE_INDEXES`
  step rather than `SCHEMA`, because it indexes a column the migration adds
  and on an existing database SCHEMA runs first.
- **Left unfinished on purpose:** `jam_per_person` is still 1, so a person
  holds one slot whether they booked it or were added to it.
- **Next step:** TESTPLAN A4 and B1b, both rewritten for instruments.

## 2026-09-19 — Approach swap: structured bot messages

- **Changed:** Every message is now a heading, labelled lines, an optional
  list and one line of what to do, built by `notify._msg` and sent with
  `parse_mode: HTML`. The organiser's word for the old ones was "word vomit":
  each was a paragraph, and a paragraph is something you read twice to find
  the time in. Everything a person supplied goes through `notify.esc()`,
  because a name with an ampersand in it would otherwise break the whole
  message rather than just look wrong.
- **Current state:** Covered by a test that every message is headed, balanced
  and escapes a hostile name. `manage.py notify-test` shows all of them.
- **Left unfinished on purpose:** Nothing.
- **Next step:** Read them on a phone — line breaks look different there.

## 2026-09-19 — The pass no longer covers the canned drink

- **Changed:** `config.ITEMS` is the cookie or pastry and the photo strip.
  The drink is still part of the evening; it is simply not counted against
  anybody, so nobody has to be looked up to be handed one. The drink stock row
  left Settings with it.
- **Current state:** 392 tests pass.
- **Left unfinished on purpose:** **The Settings copy still implies the drink
  is included.** If it is no longer included at all, the organiser needs to
  say so and the "Included with entry" text needs editing.
- **Next step:** Confirm with the organiser.

## 2026-09-19 — Mini App: menu, photographs, and screens split apart

- **Changed:** Home is re-ordered (Your pass, The Last Guest, Jamming studio,
  Help) and each row has a line underneath saying where it goes — the names
  alone assume you already know what the evening contains. The "next up" card
  was the most looked-at thing on the screen and the only thing you could not
  tap; it now reads "Your next slot" and opens a new **My bookings** screen.
  **Help** is its own screen with an FAQ, split from bookings, because
  somebody looking for "who do I ask" had to scroll past their own tickets.
  The jam room gained a second screen, so both rooms now go board → details;
  they are deliberately unalike, the escape room dark and cramped, the jam
  room paper and wide with the instruments as stencilled type. The Last
  Guest's premise finishes its thought instead of stopping on "you have the
  same fifteen". Optional photographs at the top of each screen, greyscale
  and halftoned in CSS, listed by the server so a missing file leaves no gap.
- **Current state:** Every screen renders from real server answers —
  `scripts/render_views.mjs` with `scripts/record_answers.py` does that check
  and is now part of the routine alongside `check_pages.mjs`.
- **Left unfinished on purpose:** The photographs themselves. The organiser is
  supplying them; `static/shots/README.md` names each file and says what
  survives the halftone treatment.
- **Next step:** Look at it on a phone.

## 2026-09-20 — Confirmed: the canned drink is not included with entry at all

- **Changed:** Yesterday's entry left this open — the drink had come off the
  pass, but it was unclear whether it was still part of entry and merely
  uncounted. The organiser confirmed it is dropped entirely. The "included
  with entry" list is built from `config.ITEMS`, so it already excluded it;
  what needed fixing was the wording across `BUILD_SPEC.md`, `README.md`,
  `RUNBOOK.md`, `STATE.md` and `TESTPLAN.md`, all of which still told the
  organiser to expect three items at the booth. Drinks are sold at Loft,
  which the `paid_extras` setting already says.
- **Current state:** 392 tests pass. The booth rehearsal in `RUNBOOK` Phase 13
  now races two phones for the **photo strip** rather than the drink, and
  Part A of `TESTPLAN` expects two items on the pass. Part A's steps were
  re-numbered after the jam steps grew.
- **Left unfinished on purpose:** Nothing. `config.ITEMS` remains the single
  list that drives the pass, the booth, the console, the exports and the bot,
  so a future change is still one line.
- **Next step:** None. The organiser runs `TESTPLAN` Part A.

## 2026-09-21 — The Mini App's look was reworked in a design tool and merged back

- **Changed:** New folder `design/`, and two scripts that make a round trip
  out of it. `scripts/build_design_file.py` writes
  `design/the-yard-design.html`: the real page with the logo inlined, the
  network stubbed out with recorded server answers, writes politely refused,
  and a picker along the bottom for 17 screen states. Everything it adds sits
  inside blocks marked `DESIGN-HARNESS` and `DESIGN-BRIDGE`.
  `scripts/merge_design.py` deletes exactly those blocks to put the file back,
  and refuses if a marker is missing or any of a list of must-keep pieces
  — `VIEWS.*`, `#screen`, `#navback`, `#mainbtn`, the Telegram bootstrap,
  the `Authorization` header — has been lost. `design/DESIGN_BRIEF.md` is the
  brief that goes with the file. The three photographs came back baked into
  the harness as base64 and were written out to `static/shots/`.
- **Current state:** The round trip is byte-identical: build, merge, and the
  page's hash is unchanged. Two passes have been merged. What came back and
  was kept: the jam room's own language, the group panel rebuilt as 56px rows
  with a count instead of a box of small chips, Your bookings rebuilt as a
  dark page of one card per room (an activity you have not booked shows as an
  outlined card of the same shape, so the page is always two rooms), the
  booking stamp, contrast and 44px fixes the brief called firm, a 520px cap so
  a wide window is deliberate, and the removal of the phrase "your half"
  everywhere — the organiser's words: *"your half sounds so bad to me"*. The
  server code `PHONE_NOT_YOUR_HALF` and the zone values `A`/`B` are unchanged;
  only the wording is.
- **Left unfinished on purpose:** The design tool's motion work — the ghost
  copy of the outgoing screen, `expandInto`, `data-morph`, `data-lift` and the
  staggered `data-seq` entrances. That machinery is what was flashing, and it
  was replaced rather than merged; see the next entry. `render_views.mjs`
  cannot reach the preview picker's jam states, which is a harness limitation,
  not a page one.
- **Next step:** The organiser looks at it on a phone, inside Telegram.

## 2026-09-21 — Screen transitions rebuilt from scratch: the blank-then-reappear flash

- **Changed:** The organiser: *"the animation makes the whole page stutter and
  flash. Every single asset and button and qr code and whatever it is turns
  blank and then comes back."* Three separate causes, all now gone.
  **One:** `transition()` moved the outgoing screen's real nodes into a still
  copy (`#leaving`) that stayed in the document, so `reuseDecoded()` — the
  cache that hands an already-decoded photograph to the incoming screen —
  found them "still connected" and refused to reuse them. Every photograph and
  the pass QR was rebuilt from scratch and painted as an empty box until it
  decoded. That empty box was the flash. The ghost is gone, and the cache
  reuses a node when it is loaded rather than when it is disconnected.
  **Two:** `expandInto` ran a CSS animation on `transform` while `.scroll`
  also carried a CSS transition on `transform`. Two engines driving one
  property is undefined behaviour, and it juddered. Both are gone.
  **Three:** `render()` wrote `translateX(0px)` on every render, so the scroll
  area kept a compositing layer for the whole session and kept re-arming that
  transition. It now writes a transform only while a drag is happening.
  Alongside those: the bottom sheet's slide moved from `.mainsheet` to
  `.mainsheet.in`, added only when the sheet goes from hidden to shown, so it
  no longer re-slides; `prewarmShots()` decodes the photographs once, as soon
  as `/api/me` names them; `loading="lazy"` came off the hero image, which had
  guaranteed a late decode of the one picture above the fold; the phone
  button's pulse moved from `box-shadow` (repainted every frame, for ever) to
  a ring on `.phone-open::after` that scales and fades; and the 23 staggered
  board-cell entrances were dropped.
- **Current state:** What is left is a 0.2s nudge and fade on **one** element,
  transform and opacity only, with `.scroll.fwd > * *{ animation:none }` so
  nothing inside a screen animates while it arrives. Forward comes from the
  right, back from the left. The back-swipe gesture is now left-edge only
  (36px) — starting it anywhere meant every press on a slot tile also began a
  back swipe, and it fought the phone's own gesture. 392 tests pass;
  `check_pages.mjs` and `render_views.mjs` are clean across 16 screen states.
- **Left unfinished on purpose:** None of this is covered by an automated
  test, because it is browser-only and there is no browser test harness. It
  has not been seen on a phone yet.
- **Next step:** The organiser opens the app in Telegram on a phone and walks
  Home → The Last Guest → back → The Last Guest again, which is the exact
  path that flashed. If any of it still stutters, the page transition can be
  turned off in one line by deleting the two `.scroll.fwd` / `.scroll.back`
  animation rules in `templates/index.html`; nothing else depends on them.

## 2026-09-21 (later) — The flash, actually found: content is no longer animated in at all

- **Changed:** The entry above claimed the flash was fixed. It was not, and the
  organiser's report was the same as before: *"still flashing, and it's the
  same every time."* Both earlier attempts had chased mechanisms — the ghost
  copy, the double image decode, the compositing layer — which were real
  faults and worth removing, but were not **this**.
  The cause is **fourteen CSS rules that start an element at `opacity:0` and
  fade it in**, and one of them decides the whole thing:
  `.view{ animation:vIn .3s both }`. **`.view` is the root element of every
  screen in the app.** The previous attempt added
  `.scroll.fwd > * *{ animation:none !important }` specifically to hold a
  screen's contents still while it arrived — and that selector cannot match
  `.view`, because `.view` *is* the direct child, not a descendant of one. So
  every navigation still faded the entire screen up from nothing.
  Why that is seen as a flash and not as a fade: a screen is rebuilt with
  `innerHTML`, so every element on it is new, and the fade cannot begin until
  the browser has parsed and laid all of it out. Those frames are painted at
  `opacity:0` — a blank page — and then the photographs, the buttons and the
  pass QR all appear together. That is exactly the organiser's description,
  word for word, from the first report onwards.
  It also explains the one detail that never fitted either earlier theory: a
  **first** visit to a screen looked fine. A first visit renders `skeleton()`
  and then repaints when the data lands, and that repaint is not an arrival,
  so it never faded. Come back with the data cached and the first render *is*
  the arrival, and it fades. The organiser reported precisely this about the
  jamming room and it was not taken seriously enough at the time.
  All fourteen rules are gone: `.view`, `.gate`, `.gate-logo`, `.gate-dates`,
  `.gate-card`, `.gate-cta`, `.next`, `.phone`, `.tstub`, `.pass`, `.items`,
  `.shot`, `.strip`, `.jstub`, plus the `.scroll.fwd` / `.scroll.back` page
  transition and the `noanim` / `navDir` / `render._animate` bookkeeping that
  existed only to drive it. Two `tick` rules that pulsed text between 45% and
  100% opacity for ever — on Home's countdown and the phone's count — went
  with them. The keyframes `vIn`, `pop`, `tick`, `pageFwd` and `pageBack` are
  deleted rather than left unused.
- **Current state:** **Navigation is instant.** Six animations remain in the
  whole page and none of them fades content: the bottom sheet's one transform
  slide, the ring on the phone button (on a pseudo-element, so it never
  touches the text), the toast, the two halves of the booking stamp, and the
  blanket `prefers-reduced-motion` rule. Presses still scale and the
  back-swipe still follows the thumb, because the person is causing those.
  392 tests pass; `check_pages.mjs` and `render_views.mjs` clean across 16
  screen states; the design round trip is still byte-identical.
- **Left unfinished on purpose:** No automated test can catch this class of
  fault — it is a perception of timing in a real browser, and every check in
  this project either parses the script or renders the markup in Node. The
  standing rule is written into `DESIGN.md` §7 instead: **nothing that holds
  content may start at `opacity:0`**, and if a screen transition is ever
  wanted again it must move `transform` only, never `opacity`, and sit on
  `.scroll` rather than on the screen's contents.
- **Next step:** The organiser walks `TESTPLAN.md` A7 on a phone. If a screen
  still goes blank, that is now a bug rather than a taste question, and what
  is needed is which screen and whether it was the whole page or one part of
  it.

## 2026-09-21 (later still) — The slide came back, without the fade

- **Changed:** The organiser asked whether a slide was possible at all. It is:
  the fault was never the movement, it was `opacity`. An element that fades in
  is genuinely absent until its animation runs, and on a phone busy laying out
  freshly written markup that start is a few frames late — so those frames are
  a blank page. A `transform` has no such failure mode: start it late and the
  content is sitting still, fully visible, and then it moves.
  So the transition is back as an **18px transform nudge, 0.2s**, forward from
  the right and back from the left, with no `opacity` anywhere. 18px rather
  than a full screen width because the outgoing screen has already been thrown
  away — nothing slides out underneath — so a longer slide would drag a band of
  empty paper across. The arrival flag (`navDir`) came back with it, because
  `render()` rebuilds the screen on every call and without it the page would
  nudge every time a tap changed something; it is now one flag rather than the
  two the old code carried, and it is cleared at the top of the next render
  instead of on a timer.
- **Current state:** **395 tests pass** — three new ones. They read the Mini
  App's CSS as text, resolve which `@keyframes` each rule actually uses, and
  assert that the screen transition never animates `opacity`, that `.view`
  never animates in, and that the only selectors allowed to use a fading
  keyframe are the three overlays in `MAY_FADE` (`#toast`, `#stamp`,
  `.phone-open::after`). Reintroducing the original fault was tried
  deliberately and trips all three, each naming the offending selector.
  `check_pages.mjs` and `render_views.mjs` clean; round trip byte-identical.
- **Left unfinished on purpose:** The guard reads CSS with regular
  expressions, which is not a parser. It is deliberately narrow — it resolves
  `animation:<name>` against `@keyframes <name>` and nothing more — and it is
  a backstop for one specific mistake, not a linter.
- **Next step:** The organiser walks `TESTPLAN.md` A7. The thing to watch for
  is content that is *missing* while the screen moves, as against content that
  is *offset* while it moves. The first is the bug; the second is the
  animation.

## 2026-09-21 — A working rule added to README, after two wrong diagnoses in a row

- **Changed:** New section in `README.md`, **"Before you say something is
  fixed"**, placed with the ground rules so a cold agent reads it before
  touching anything. It generalises what went wrong with the screen
  transitions rather than restating it: a clean test run is evidence about
  regressions, not about behaviour, because nothing in this project can see a
  screen or feel a delay; the detail in a report that your explanation does
  not cover is the disproof of your explanation, not a curiosity; finding a
  real bug is not the same as finding the reported one; search by behaviour
  rather than by what a block of code is labelled; suspect whatever was
  written by reflex. It also names the three cases worth slowing down for —
  behaviour no check can observe, the organiser reporting the same thing
  twice, and being about to claim a fix you have not seen work — and says the
  normal loop is fine everywhere else, because thoroughness is not free on a
  deadline.
- **Current state:** `README.md` is 139 lines longer by one section. Nothing
  executable changed; 395 tests pass. The worked example the section points at
  — the three motion guards at the end of `tests/test_invariants.py` — is
  already in place, along with the note that a guard which has never failed
  has not been tested.
- **Left unfinished on purpose:** Nothing. This is guidance, not a mechanism,
  and it is deliberately short: it has to earn its place in the context of
  every future session.
- **Next step:** None. It applies from the next piece of work onwards.

## 2026-09-21 — The UI pass: Up next, one people list, no small print, one ground per room

- **Changed:** `templates/index.html` only on the app side; no server change
  (`STATE.md` decisions 115–121).
  - **Up next opens Your bookings**, not the soonest ticket. A button audit
    fixed five more landings: the jam board's own slot opens its jam ticket;
    Back after an escape booking lands on the board; Cancel / Leave return to
    wherever the ticket was opened from; the tickets lose "All games / All
    slots" and "Everything you hold"; `?go=bookings` is read as `mybookings`.
  - **A free escape time opens its own page** (`VIEWS.escbook`). The board's
    `picked` state and the panel under the grid are gone. A free time tapped
    by someone who already holds a game shows the server's own "You already
    have a game…" at once.
  - **One numbered people list** (`peopleList()`, `.plist-wrap` / `.prow`)
    replaces `partyPanel`, `jamPartyPanel`, the ticket's `.who` rows and the
    jam ticket's chips, on all four booking screens. Dimmed rows for people
    you cannot change; Edit only before booking; the last box is the add box.
    The jam room's free instruments sit inside it; a lone one is pre-picked.
    Every existing element id and data attribute was kept.
  - **Small print removed** from the escape board, the booking panel, the
    ticket, the pass, the jam board, the jam booking page, the jam ticket and
    Your bookings. Deadlines became one line in the organiser's words, the
    number computed from `edit_until` / `leave_until`; the booker became a
    row; what cancelling does moved into the confirm dialog.
  - **One ground per room**: the escape ticket stub is night, and
    `body.dark` turns the top bar, bottom sheet and (through `setChrome()`)
    Telegram's header and bottom bar night on every escape screen.
  - Fixed on the way: a name typed in the jam room's add box vanished when an
    instrument was tapped, because only the escape box survived a redraw. All
    three add boxes now do (`ADD_BOXES`).
  - Dead CSS removed: `.party*`, `.mate*`, `.chip*`, `.addbox`, `.who*`,
    `.group-head`, `.guest*`, `.jgroup`, `.holdbtn`, `.game.picked`,
    `.jamslot.picked`, `.kitpick.small`, and the old `.bk*` bookings rows.
- **Current state:** 396 tests pass. `render_views.mjs` covers 23 states (7
  new) and now fails if removed small print comes back. New
  `scripts/tap_through.mjs` passes 17 steps in headless Edge. The design
  harness opens a given state from `#state=N`, fetches its own data (it used
  to wait on the gate for ever), and its picker has the booking page and the
  jam ticket; `merge_design.py` must-keep gained `VIEWS.escbook` and
  `VIEWS.jamticket`; round trip byte-identical. Docs: `DESIGN.md` §1 and §5,
  `TESTPLAN.md` A4 / A7 / B1 / B1b, `RUNBOOK.md` Phase 13c–d and 18,
  `BUILD_SPEC.md` §14, `README.md`, `context/PROJECT_STATUS.md`.
  **Not yet tried on a phone.**
- **Left unfinished on purpose:** the jam booking page's **Taken** rows carry
  no names, because `/api/jam/slots` sends free instruments, not who holds
  them; that is a server change, three days out. Blurring locked names, as
  first suggested, was not done: it would hide who is coming.
- **Next step:** The organiser runs `TESTPLAN.md` A4 step 11 and A7 steps
  28b–28c on their phone, then Part B.

## 2026-09-21 — Approach swap: a View Transition for Up next, revising decision 113

- **Changed:** Tapping Up next grows the card into Your bookings, and Back
  shrinks it into the card again (`morphFor()` / `morph()` in `go()` and
  `back()`, the CSS under "the card growing"). Decision 113 refused the design
  tool's `expandInto` for animating freshly built markup, whose first frames a
  busy phone paints blank. This uses `document.startViewTransition`, which
  freezes the frame and animates pictures of screens already drawn. It still
  never touches opacity: reveals are `visibility`, movement `transform`, the
  browser's cross-fade and its additive `plus-lighter` blend are switched off.
  Names exist only under `html[data-morph]`. New test
  `test_the_card_morph_never_fades`.
- **Current state:** Built. `scripts/motion_frames.mjs` captured the grow and
  the shrink at a tenth of speed in headless Edge — the card grows up and
  down from its place on Home, the words glide to the top, the room cards
  rise in, the flag is cleared afterwards, other routes do not morph, no page
  errors. The new test was broken two ways on a copy (a fading keyframe on a
  room card; the root's cross-fade left on) and caught both. **Not yet tried
  on a phone in Telegram**, which is the only place its feel can be judged.
- **Left unfinished on purpose:** No animated corner radius — the shape keeps
  20px corners, invisible once the page's night frame is behind it, so no
  painted property is animated. The card's "Open it →" line is not carried
  over; it reappears when the shrink ends. iOS before 18 and some Telegram
  Desktop builds have no View Transitions and get the ordinary nudge.
- **Next step:** `TESTPLAN.md` A7 step 28b. If it misbehaves on a phone,
  `MORPH = false` (RUNBOOK Phase 18) turns it off with nothing else changed.

## 2026-09-22 — The Yard Pass, normal capitals, a readable Help, matcha/panini calls, Mobile and Laptop

- **Changed** (`STATE.md` decisions 122–126):
  - **"Your food pass" is "The Yard Pass"** in the Mini App, the bot's `/pass`
    and the payment-verified and doors-open messages.
  - **Normal capitals for headings and buttons in the Mini App**; the 11px
    spaced labels and the pills stay in capitals. Names of things are title
    case: `config.ITEMS` is now "Cookie or Pastry", "Photo Strip", and the
    instruments "Acoustic Guitar", "Electric Guitar". "The Jamming Studio"
    everywhere.
  - **Help rebuilt**: a card per section with an `--accent-ink` heading, date
    and hours in Anton, the venue with its address and an **Open in Maps**
    button, questions that fold, and a new question about matcha/panini.
  - **Venue** default "The Hub @ Hafary Gallery L5"; new setting
    `venue_address` ("105 Eunos Ave 3, Singapore 409836"), in Settings and the
    Mini App's `event` block. The organiser confirmed Level 5 over the draft's
    "Level 2".
  - **Orders**: new `orders` table, `services/orders.py`, `config.ORDER_ITEMS`
    (matcha, panini), setting `order_pickup`, four endpoints, the
    `order_ready` bot message, and a console **Orders** screen — scan a pass
    when someone orders, one tap on **Ready** when it's made. The camera on
    that screen opens only while taking an order. The booth lookup now says
    whether a person can get bot messages (`person.reachable`).
  - **Console sign-in is Mobile or Laptop.** Server roles are `admin` and
    `mobile`; `staff` and `gm` sign in as mobile, old sessions are read as
    mobile, and Mobile takes either PIN. Mobile gets Booth, Orders, Game and
    People, and the nav shows only those. `GET /admin/api/slots` became
    laptop-only (the game screen never used it). The phone-width console
    drops the drawn phone frame, the fake status-bar gap and the design notes.
- **Current state:** 408 tests pass. Tests that changed did so because the
  behaviour changed on purpose. Mini App screens checked in headless Edge; the
  console driven at phone width against a scratch copy of the app. Docs:
  `STATE.md`, `DESIGN.md` §2/§3/§5/§6, `BUILD_SPEC.md` §9 r33 and §12,
  `RUNBOOK.md` Phases 13 and 18, `TESTPLAN.md` A2/A3/A3b/A5,
  `context/PROJECT_STATUS.md`. **Not yet on a phone; the Orders camera scan
  not tried at all.** `app.py` and `bot.py` must be restarted to pick it up.
- **Left unfinished on purpose:** no heat press (one line in
  `config.ORDER_ITEMS`); no order status inside the Mini App — the Telegram
  message is the channel; the console keeps its own capitals style.
- **Next step:** restart `app.py` and `bot.py`, then `TESTPLAN.md` A3b on a
  phone; `python manage.py notify on` before the night.

## 2026-09-22 — Approach swap: one Mobile sign-in replaces Staff and GM (§9 r33)

- **Changed:** Three console roles became two. The organiser was asked whether
  every phone PIN holder should see the escape room's solution and chose one
  phone PIN for everything. No PIN was retired: either old PIN signs in as
  Mobile, and `bot.py`'s `/actor` still checks the GM PIN on its own.
- **Current state:** Built; `BUILD_SPEC.md` §9 r33 carries the change and why.
- **Left unfinished on purpose:** `set-gm-pin` still exists and still works;
  merging the two PINs into one would mean re-issuing PINs two days out.
- **Next step:** Hand the phone PIN only to people it's fine to show the
  solution to.

## 2026-09-22 — The bot is now @The_YardBot

- **Changed:** `TELEGRAM_TOKEN` in `.env` now belongs to a **new bot**,
  `@The_YardBot` (id 8164503586), replacing `@TheYard_Timeslots_bot` (id
  8831231555). Checked with Telegram's `getMe` before the switch. The old
  token is kept as a comment in `.env`. No code changed: `bot.py` sets the
  new bot's commands and its "Open The Yard" menu button on start.
- **Current state:** Takes effect when `app.py` and `bot.py` are restarted.
  After that, the Mini App only accepts people who open it from
  `@The_YardBot`. Opening it from the old bot shows "We can't confirm who you
  are". Five people had opened the app through the old bot; the new bot can't
  message them until they open `@The_YardBot` once.
- **Left unfinished on purpose:** The old bot's menu button still points at
  the app. It can be changed with the old token, but anyone using it now just
  sees the sign-in refusal, which tells them nothing wrong happened.
- **Next step:** Restart both, open `@The_YardBot` → `/start` → Open The Yard,
  and give out the new bot's name everywhere the old one appeared.

## 2026-09-22 — Up next with nothing booked is a card you can tap (STATE.md 127)

- **Changed:** `templates/index.html`. The empty Up next card was a disabled
  paragraph. It is now the same live card as a booking — UP NEXT, **None**,
  **Book something!**, Open it → — and it opens Your bookings with the same
  grow. Your bookings always starts with that header now (it used to switch to
  a "Your Bookings" heading when empty). `render_views.mjs`, `tap_through.mjs`
  and `motion_frames.mjs` check the empty state too.
- **Current state:** Built. 23 screen states render with `FAILURES: 0`;
  tap-through `FAILS: 0`; the empty grow captured frame by frame in headless
  Edge with no page errors. Not yet on a phone.
- **Left unfinished on purpose:** nothing.
- **Next step:** `TESTPLAN.md` A7 28b, with nothing booked as well as with
  bookings.

## 2026-09-22 — New pass and jam photographs, in colour (STATE.md 128)

- **Changed:** `static/shots/pass.jpg` and `jam.jpg` replaced with the
  organiser's photos (1400×875 JPEG). Those two keep their colours with a
  fainter dot screen (`templates/index.html`); the escape room's stays dark.
  Photo addresses gain `?v=<file time>`. `build_design_file.py` now shows the
  real photographs in the design file (it embedded them but never used them).
- **Structure:** new folder `design/old-shots/` with the two replaced photos.
- **Current state:** Built; screenshotted in headless Edge. Not yet on a phone.
- **Left unfinished on purpose:** no `home.jpg` or `help.jpg` — none supplied.
- **Next step:** look at Your pass and the jamming studio on a phone; if the
  dots are too strong or too faint, it's one number (`static/shots/README.md`).

## 2026-09-22 — Approach swap: Real time / Test time replaces event-day mode and the test clock (STATE.md 129)

- **Changed:** Settings (`templates/admin.html`) rebuilt around one control per
  idea. **Clock: Real time / Test time** with a minute slider (dimmed on Real
  time) replaces Event-day mode, Test clock and "Test clock set to". Test time
  now means **24 Sep** at that minute (`app.open_db`), not today. New switches
  `doors_message` and `last_call` (`config.py`, default on) replace the
  event-day-mode gate on those two messages (`services/notify.py`); test time
  never sends them. Stock is Counted / Not counted plus a number; low-stock
  and "when stock runs out" dim while nothing is counted. Who gets messages,
  Phone opens, Phone in the app and When stock runs out show every option.
  "Biggest group one person can book" moved to Escape room. The top bar
  and banner name the test time and follow a save at once. The "can't both be
  on" rule in `services/admin.py` is gone.
- **Current state:** Built. Tests changed on purpose (`test_admin_screens.py`,
  `test_notify.py`: 7 replaced or added). Settings driven in headless Edge
  against a scratch copy: switch, drag, ±1, save, banner, `server_time` on the
  24th, stock Counted/Not counted — no page errors.
- **Found:** the organiser's `app.py` runs with `debug=True` and reloads on
  every code save, so it picked up the new `config.py` at 13:50 (real database
  gained `doors_message`/`last_call`, lost `event_day_mode`). Its test clock
  had been on since 21 Sep, so under the new meaning the live app showed every
  attendee 24 Sep 7:30 PM. Set back to Real time at 14:07 at the organiser's
  instruction (audited). The organiser stopped `app.py` for the rest of the
  build.
- **Left unfinished on purpose:** `relock_minutes` is still a plain number
  until the phone change replaces it; hint and merge times stay typed.
- **Next step:** restart `app.py`; Settings → check the Clock reads Real time.

## 2026-09-22 — Approach swap: the phone for everyone in the game, only from a bot message (STATE.md 130)

- **Changed:** `services/game.py` — no desk-half check; the phone is open from
  the start for `phone_minutes` (25, replacing `relock_minutes`), pushed back
  by pauses and extra minutes; End no longer locks it; every GM press that
  leaves it open messages it to every player once (`_send_phone`), and "At
  the booked time" mode does the same from `bot.py`
  (`send_phone_for_started_games`). `services/notify.py` — new message
  `text_phone`, `GO_PHONE`, button label "📱 Open the phone"; the reminder
  says the phone arrives as a message. `templates/index.html` — the escape
  board's phone card is gone; new `phone` screen reached only by `?go=phone`,
  which opens the phone after Start; the ticket has a "His phone" row and an
  Allow button for anyone we can't message; Help rewritten. `templates/admin.html`
  — GM screen wording, per-player "Phone sent / Can't reach — desk handset"
  markers and a warning line, End's confirmation, and Settings' "Phone stays
  open … minutes from the start". `manage.py notify-test` sends the phone
  message too. `bookings.py` and `test_invariants.py` comments no longer say
  the desk half holds the phone.
- **Current state:** Built. 428 tests pass; 30 screen states render; the flow
  dry-run on a scratch copy of the real database. `PHONE_NOT_YOUR_HALF` is no
  longer returned (the code stays in the error table). Not yet on a phone or
  through the real bot.
- **Left unfinished on purpose:** no per-message token in the link (the
  server re-checks every open); the bot's timed messages stay on the real
  clock, so under test time the phone message comes from the GM's Start, not
  from "At the booked time".
- **Next step:** restart `app.py` **and** `bot.py`; `TESTPLAN.md` A5; before
  the night, Who gets messages → Everyone.

## 2026-09-22 — Known bug, left unfixed: laptop console screens clip below 1440px wide

- **Found:** while screenshotting Settings in headless Edge. Every laptop
  screen (`.wide`, `templates/admin.html`) lays out 1440px wide; in a browser
  window narrower than that, both edges are cut off and the page scrolls
  sideways. Checked on Audit, which was not touched today — same result, so
  it predates the 22 Sep changes.
- **Current state:** unfixed. At 1500px everything shows.
- **Left unfinished on purpose:** a layout change to every console screen two
  days out was not asked for.
- **Next step:** if the laptop's browser clips Settings, make the window wider
  or zoom out (Ctrl and −). Say so, and it can be fixed.

## 2026-09-22 — The event is 3–10 PM; games from 3:30, jam from 3:00 (STATE.md 131)

- **Changed:** `config.py` defaults: doors 15:00, first game 15:30, first jam
  slot 15:00, doors-open message 13:00. Live database followed (rows were
  still system-owned) and `manage.py generate-slots` was run: 19 games (6
  added), 14 jam slots (4 added), nothing removed. `templates/index.html`
  Start-screen fallback says 3–10 PM; `manage.py` `notify-test` and
  `generate-slots` read the times from Settings. Tests updated for the new
  timetable. Docs: BUILD_SPEC §1/§2/§17, RUNBOOK, TESTPLAN, README, STATE,
  DESIGN_BRIEF.
- **Current state:** Live. 428 tests pass.
- **Left unfinished on purpose:** nothing.
- **Next step:** GM and actor needed from 3:30 PM.

## 2026-09-22 — Test time bomb in test_receipts.py, fixed

- **Changed:** `tests/test_receipts.py` pinned the receipts module's clock to
  `conftest.TEST_NOW`. On the real clock, all its tests started failing at
  15:26 on 22 Sep, when the first real Paperform link expired.
- **Current state:** fixed; test code only.
- **Next step:** the real receipts — 0 of 152 saved as of 15:36 — need
  `python manage.py fetch-receipts` now.

## 2026-09-22 — ESCAPE_ROOM_FLOW.md: one flow for The Last Guest (proposal)

- **Changed:** new file `ESCAPE_ROOM_FLOW.md` (project root, spoilers). It
  reconciles the "Overall Sheets" PDF, `context/The_Last_Guest_20min.pptx`,
  the built phone and the app into one 15-minute flow: the answer, the real
  timeline, the evidence map, minute by minute, the actor's script, the
  warrant, the reset, and a work list. Nothing else was changed.
- **Current state:** a proposal awaiting the organiser's eight decisions
  (its §12). Its §10 lists 18 mismatches found. Three are **bugs in the phone's text, left
  unfixed** until the organiser decides: Ryan's 10:24 "boss is unhinged"
  message contradicts his 18-minute call to Si Hong in the call log; Chloe's
  "solicitor at 9 tomorrow" is dated Yesterday (so already past); and Ziv's
  "come by at the end" contradicts her arriving at 8:19. The four hint lines
  and the reset list in `private/gm/script.json` are still mock text.
- **Left unfinished on purpose:** no edits to the phone, `script.json` or
  Settings until the organiser has answered §12.
- **Next step:** go through §12 with the organiser, then do §11 A–G and
  record the decisions in `STATE.md` §5.

## 2026-09-22 — The pass is a pastry, a photo strip and vinyl making; kinds recorded (STATE.md 132)

- **Changed:** `config.ITEMS` is now `pastry` (label "Pastry"), `photo`,
  `vinyl`; `config.ITEM_CHOICES` gives the pastry four kinds (Mini Tart, Mini
  Brownie, Mini Cookie, Shiopan) and `ITEM_NOTES` the line under each name.
  The booth shows one button per kind and sends `variant`, which `claims.claim`
  validates against the kinds (a wrong kind is refused; none is accepted).
  Overview's Pastry card counts each kind; exports say "Pastry (Mini Tart)";
  the person page and `/pass` name the kind. New `vinyl_stock` Setting.
  The circle (`.hole`) before each pass item is gone — the organiser: "it
  makes it seem like a button when it is not".
- **Current state:** live. 430 tests pass (two new: the pastry-kind claim, the
  price-list format). Screenshotted at phone width.
- **Left unfinished on purpose:** one stock number covers all four kinds;
  per-kind stock was not asked for.
- **Next step:** hand one over at the booth on a phone.

## 2026-09-22 — A price list on Help, one question open at a time, a Floorplan screen (STATE.md 132)

- **Changed:** new Setting `price_list` (plain text, the organiser's own
  format), parsed by the new `services/prices.py` into groups and shown as
  Help's first question, "Is there a price list?". Settings gained a
  multi-line box (`type:'longtext'`), and `_coerce` keeps line breaks for it.
  Opening a Help question closes the others. New `VIEWS.floorplan` with
  `static/floorplan.png` (`event.floorplan`, `?v=` cache-busting), Home row 04
  (Help is 05) and a button in Help; Zoom in shows the map at 220% to drag,
  and a drag on the zoomed map no longer starts the back swipe. "Included with
  entry" gained Board Games; `paid_extras` no longer names Loft or Crib.
- **Current state:** live. 33 screen states render (was 30).
- **Left unfinished on purpose:** the escape room is not on the floorplan the
  organiser supplied — asked, not guessed.
- **Next step:** check the map is readable zoomed, on a phone.

## 2026-09-22 — Escape games run 3:05–9:45 PM (STATE.md 133)

- **Changed:** `first_game` 15:05, `last_game` 21:45 — 21 games, 252 seats,
  the last ending at 10 PM with the doors. The jam room already ran to 10 PM.
  Dry-run on a scratch copy, then `manage.py generate-slots` on the live
  database at 17:56: 21 added, 19 removed (5 retired rather than deleted
  because they once held test bookings), the one jam booking untouched.
  Docs and tests follow.
- **Current state:** live, 0 escape bookings existed, so nothing moved under
  anyone.
- **Next step:** the GM and actor are now needed from 3:05 PM, not 3:30.

## 2026-09-22 — Every bot message in the organiser's relaxed voice (STATE.md 132)

- **Changed:** `services/notify.py` copy rewritten — lower-case headings, the
  facts on their own lines under them (time, place, ref), lists without
  bullets, no "free with entry"; the order message copies the organiser's own
  example without the quantity. `bot.py`'s `/start`, `/pass`, `/help`,
  `/actor`, the gate refusals and the "I can't take receipts" reply too.
  Places are Settings now: `escape_meet` ("the escape room entrance") and
  `jam_room` ("Heaven 2") reach the tickets and the messages; `order_pickup`
  became `matcha_pickup` ("Two Goose") and `panini_pickup` ("Shiopan
  Paninis"), with the Settings rows built from the server's order list.
  The actor's hint line is now HTML-escaped — it was not.
- **Current state:** live in the web process. **`bot.py` still runs the old
  copy until the organiser restarts it**, so `/start`, `/pass`, `/help` and
  the timed messages (reminders, doors-open, last call) keep the old wording.
- **Found:** `cmd_start` matched a refusal by its English text, which the
  rewrite would have broken; it now compares against the gate text itself.
- **Next step:** restart `bot.py`, then `manage.py notify-test maxi_muslim`.

## 2026-09-22 — Ready for GitHub and a real server (STATE.md 134)

- **Changed:** new `.gitignore` (keeps out `.env`, `data/`, `imports/`,
  `private/receipts/`, every `.xlsx`, and the design file built from the
  sign-up list) and new `DEPLOY.md` for the developer hosting it: one web
  process, one `bot.py`, SQLite on a persistent disk, HTTPS, Caddy and
  systemd units, and a cutover that copies `data/app.db` with both laptop
  processes stopped. `scripts/record_answers.py` no longer hard-codes
  `C:\Users\endrw\my-mini-app`.
- **Current state:** written, not yet pushed — **Git is not installed on the
  laptop**. Nothing was committed or sent anywhere.
- **Left unfinished on purpose:** the repository must be **private**: the
  tests carry attendees' Telegram usernames and `private/` holds the escape
  room's solution.
- **Next step:** install Git, create the private repo, push, then hand
  `DEPLOY.md` to the friend.

## 2026-09-22 — Overview counts "Opened the app" and "At the event" apart (STATE.md 135)

- **Changed:** `services/admin.py` `overview()` gained two stats in place of
  "Checked in": **Opened the app** (active, non-test people with a
  `tg_user_id`) and **At the event** (check-ins stamped at or after
  `doors_open` on `EVENT_DATE`, i.e. 3 PM on the 24th). The card's own line
  names any earlier check-ins ("1 before that, not counted"). The console's
  strapline reads "N signed up, N opened the app, N at the event" and now
  looks stats up by label, not by position.
- **Found:** the organiser believed linking a Telegram account already counted
  as a check-in. It never did — only `claims.check_in` writes `checked_in_at`
  — but there was no count of who had opened the app at all, which is what
  they were missing. Said so plainly rather than "fixing" a bug that wasn't.
- **Current state:** live. 432 tests pass (two new: the two counters, and the
  counter following the `doors_open` Setting). Real numbers at 18:44: 168
  signed up, 5 opened the app, 0 at the event.
- **Left unfinished on purpose:** nothing blocks a check-in before 3 PM; it
  simply is not counted as being there.
- **Next step:** watch both numbers on the night.

## 2026-09-22 — One name for the desk: "the front desk" (STATE.md 136)

- **Changed:** the Settings row label "Help desk" is now **Front desk**, with
  help text saying the plan calls it Registration; the Floorplan screen
  carries the same line. The app's copy already said "the front desk"
  everywhere.
- **Left unfinished on purpose:** "the counter" still means where food and
  prints are handed over, which is not the desk.

## 2026-09-22 — The floorplan pinches and double-taps like a photo (STATE.md 137)

- **Changed:** `templates/index.html` — the Zoom in / Fit to screen button is
  gone. `.plan` is a fixed frame shaped by the image itself, with
  `touch-action:none`; the map moves inside it on pointer events
  (`wirePlan`, `planZoomAt`, `planClamp`): pinch about the midpoint,
  double-tap to 2.6× on the tapped spot or back out, drag to pan, wheel on a
  laptop, scale held to 1–5× and clamped to the map's drawn edges. Opening the
  screen resets to the whole map, and a drag on the map no longer starts the
  back swipe. The hint sits under the frame, not over the labels.
- **Found:** the first version zoomed the whole block to 220% inside a
  scrolling box — the organiser: it "kinda soft locks you on the zoomed in
  floor plan".
- **Current state:** live. Driven with real touch events in headless Edge:
  double-tap 1 → 2.6, drag pans with the screen still on `floorplan`, a hard
  drag stops at the clamp (279 of 280), pinch reaches 5×, double-tap returns
  to 1× at 0,0, no page errors. 32 screen states render (the "floorplan
  zoomed" state went with the button).
- **Next step:** try the pinch on a real phone inside Telegram — a webview can
  claim the gesture before the page sees it.

## 2026-09-22 — Payments are no longer checked before a hand-over (STATE.md 138)

- **Changed:** `claim_requires` takes a third value, `none`, and
  `claims.payment_ok` returns True for everyone under it, so the booth hands
  over to anyone on the list. The Settings row is now a three-way choice
  (Verified / Submitted is enough / **Not needed**). Overview drops the
  "Payments to check" job and reads "N unchecked, N with no receipt · not
  needed to collect" in slate instead of red; the Mini App's "We haven't
  spotted your payment" strip now follows whether payment actually blocks
  them, so it is gone. The default in `config.py` stays `verified`.
- **Why:** 150 of 169 sign-ups were still unchecked the day before, and an
  unverified receipt stopped that person collecting anything.
- **Current state:** live and audited at 19:04 (`claim_requires` verified →
  none). 434 tests pass, two of them new: the check switched off, and the
  receipts still being reachable with it off.
- **Left unfinished on purpose:** being on the roster still gates a
  hand-over — an inactive person is still refused, because that is not about
  money. Payment status, verify/reject and the screenshots all stay.
- **Next step:** if it ever needs putting back, Settings → Hand-over needs
  payment → Verified.

## 2026-09-22 — Saving our own copies of the payment screenshots

- **Changed:** ran `python manage.py fetch-receipts` (18:55). Nothing in the
  code changed; the mechanism was built on 18 Sep (STATE.md 85) and had never
  been run — 0 of 152 were saved, and 7 Paperform links had already expired.
- **Current state:** done at 19:20 — **145 of 152 saved** (28.5 MB in
  `private\receipts`, served admin-only from the person page). A saved copy
  works on the day with no Paperform, no link and no wifi.
- **Known bug, left unfixed:** the **7** whose links had already expired
  could not be copied: @bananabelles, @sharmaineangg, @t_shixuan,
  @jananabana, @bingkiat, @heidily, @feliciaandiana. Their screenshots exist
  only in Paperform's own dashboard now.
- **Next step:** none for the other 145. If those 7 ever matter, open
  Paperform's dashboard.

## 2026-09-22 — Known risk: the GitHub repository was public

- **Found:** `github.com/endrwy-code/TheYard` was created public, not private.
  Readable by anyone: `private/phone/the-phone.html` (the escape room's whole
  content), `private/gm/script.json`, `ESCAPE_ROOM_FLOW.md`,
  `context/The_Last_Guest_20min.pptx`, attendees' Telegram usernames in the
  tests, and `design/the-yard-design-kit.zip` (which carries real usernames).
  **Not** exposed: `.env`, the database, the Paperform export, the receipts —
  `.gitignore` kept those out.
- **Current state:** the organiser is switching it to private; no further
  push until they have.
- **Next step:** after it is private, consider whether the design kit zip
  belongs in the repository at all.

## 2026-09-22 — The verification step itself is gone from the app (STATE.md 138)

- **Changed:** a `payment_required` flag (person payload and the Mini App's
  `event` block) now drives every place the app asked anyone to check a
  screenshot. With payments unchecked: the person page drops the verdict
  card's demand, the transaction-reference box and the Verify / No reference /
  Reject / Change verdict buttons, and says what was recorded at sign-up
  instead; the booth's green card reads "On the list" rather than "Payment
  verified"; Help loses "You haven't seen my payment". `RUNBOOK.md` Phase 13b
  is marked as not needed, with what it would mean if the setting went back.
- **Kept:** the screenshot, in the same place, admin-only (§9 r31); the
  payment status on the record; and the whole workflow behind Settings →
  Hand-over needs payment → Verified.
- **Current state:** live. 434 tests pass (the switched-off test now also
  checks the flag both ways); 33 screen states render, including Help with
  payments unchecked.
- **Next step:** none.

## 2026-09-22 — Pushed to GitHub; the repository is still public

- **Changed:** three commits pushed to `github.com/endrwy-code/TheYard`
  (`d73acbf..bc90242`).
- **Known risk, not fixed:** the repository is **public**. Changing that needs
  a GitHub sign-in, which is the organiser's to do — Claude's attempt to read
  the stored credential was refused by the sandbox, correctly. Until it is
  private, the escape room's content and attendees' usernames are readable by
  anyone (`.env`, the database, the Paperform export and the receipts are
  not — `.gitignore` keeps them out).
- **Next step:** repo → Settings → Danger Zone → Change visibility → Private.

## 2026-09-23 — The victim's phone: the dock is on the screen again

- **Changed:** the phone's home screen was one scrolling flex column holding
  the widgets, the app grid, the Search pill and the dock. On any viewport
  shorter than that column the column scrolled and the last thing in it went
  under the fold — and the last thing in it is the dock, which is where Phone,
  Messages and Photos live. Inside Telegram's in-app browser that is every
  phone. It is now built the way a home screen actually is: a scrolling middle
  holding the widgets and the app grid, and a footer that does not scroll
  holding the Search pill and the dock. The two weather/calendar widgets take
  `min(132px, 17vh)` so a short screen gives their height to the apps instead.
- **How the phone was edited:** `private/phone/the-phone.html` is a generated
  `.dc.html` bundle whose JavaScript is gzipped base64 on one line, but whose
  markup is ordinary HTML inside a JSON string in
  `<script type="__bundler/template">`, read at load. New helper
  `scripts/phone_template.py` decodes that string, hands over the markup and
  encodes it back — refusing to proceed unless re-encoding the untouched
  string reproduces the file byte for byte, because the bundler writes
  `</script>` as `</script>` and a plain search-and-replace would destroy
  the file.
- **Also:** `fitPhoneFrame()` in `templates/index.html` now takes the *smaller*
  of Telegram's `viewportStableHeight` and `window.visualViewport.height`, and
  re-runs on `visualViewport` resize and scroll. Telegram's is the only figure
  that knows about its own chrome; `visualViewport` is the only one that
  exists outside Telegram, and the only one that shrinks for a keyboard. It no
  longer returns early when there is no Telegram, so the one-time browser link
  (`/p/<token>/`) gets a correctly sized frame too.
- **Current state:** 536 tests pass, unchanged. Both pages pass
  `node scripts/check_pages.mjs`.
- **Left unfinished on purpose:** no automated test covers this. The layout is
  inside a generated bundle and the bug only appears at a real device height,
  so there is nothing a pytest could assert that would have caught it.
- **Next step:** the organiser opens the phone on a real handset inside
  Telegram and confirms all four dock icons are fully visible and tappable
  with no page scroll, then repeats through "Phone not working? Open it in
  your browser", which serves the same file as a whole page.

## 2026-09-23 — The escape room runs itself: no Start, no switch, no split

- **Changed:** three mechanisms that had each been overtaken, removed together
  because each was propping up the others.
  - **The `in_app_phone` setting is gone.** It was an admin switch that
    answered a player, at their booked minute, with *"This game uses the
    handset at the desk"* — and the desk could do nothing about it. That is
    the refusal the organiser hit in rehearsal. `PHONE_OFF` now means one
    thing only, and it is a fault: the phone's file is not on this laptop.
  - **Start is gone.** `game.timing()` takes the booked time as the start,
    and Pause, ±1 min and End stamp it into `game_sessions.started_at` on
    first use so a touched row still says what it always said. Forgetting
    Start used to hold a room up with the clock reading zero.
  - **The split is gone.** Since 22 Sep everyone in the game got the phone,
    which left the halves deciding only where two groups stood — and the app
    never enforced that. `_assign_halves`, `_zone`, `game.halves`, the
    `/halves` route and the A/B columns on four screens all went. The GM card
    that showed them now lists **who is in this game**: number, name, handle,
    checked in, and whether the phone's message reached them.
- **Pausing now holds the phone open.** `relock_at` is the booked time plus
  `phone_minutes` **plus whatever has been paused or added**. Sorting
  something out in the room must never be the reason a group loses the phone.
- **The lock stays, manual and off by default**, moved out of the main button
  row into a quiet "rare" row with End, both behind a confirm.
- **The script became a hint list.** `private/gm/script.json` holds `hints`
  with no times against them; `hint_1`, `hint_2`, `hint_3` and `forced_merge`
  left Settings with it. Each hint has one button that becomes *Given 6:42*.
  `game.send_cue` is now `game.give_hint`; `POST /admin/api/gm/<id>/cues/<key>`
  is now `…/hints/<key>`.
- **One vocabulary for what a game is doing.** The server emits
  `upcoming · in_progress · finished · blocked` and the picker, the card and
  the timetable all print the same four words. `missed` is gone — with no
  Start, nothing can be missed. This is the "ended" the organiser saw on a
  game that was happening.
- **Also:** the one-time browser link now reports the real refusal instead of
  flattening "not yet" and "no booking" into `PHONE_LOCKED`; the console
  follows the night to the next game unless a game master has picked one by
  hand; a changeover shows *Next 7:40 PM*; the changeover ticks survive a
  reload in `localStorage`; and the console finally uses
  `env(safe-area-inset-bottom)`, which it has had `viewport-fit=cover` for all
  along — the booth's last row was sitting under the gesture bar.
- **Current state:** **532 tests pass.** Both pages pass
  `node scripts/check_pages.mjs`. Seven of those tests were failing before
  this change, on `main`, describing behaviour that had been replaced on
  22–24 Sep and never re-asserted; they are fixed here rather than left.
- **Left unfinished on purpose:** `escape_bookings.zone`,
  `escape_bookings.zone_changed_by`, `game_sessions.halves_locked_at` and
  `game_sessions.in_app_phone` stay in `db.py`. Nothing reads or writes them.
  Dropping a column from a live SQLite the night before an event buys nothing.
- **Next step:** the organiser rehearses one game on test time and confirms
  the phone opens at the booked minute with nothing pressed, that the picker
  says **In progress**, and that a pause holds the phone open.

## 2026-09-23 — Adding a tester now hands them the phone

- **Changed:** the escape room's **Test group** (Settings → Escape room — the
  phone) let named Telegram accounts open Kai Chen's phone at any time, but
  adding somebody to it sent them nothing. The only way into the phone is the
  bot's message, so a tester was added and then left to wait for something
  that was never coming — unless whoever added them knew to run
  `python manage.py phone-test` in PowerShell.
- **Now:** saving that row messages **the handles just added**, and the toast
  says who got it. Saving anything else on the Settings screen sends nothing,
  so an unrelated edit never spams the group. A **Send it now** button beside
  the row sends it again without an edit
  (`POST /admin/api/gm/phone-test`, open to any console sign-in).
- **It names what went wrong, too**: anybody on the list who is not on the
  roster, and anybody who has never written to the bot — Telegram will not let
  the bot message them until they send it `/start`. Silence there used to look
  like it had worked.
- **One copy of the logic.** `game.send_phone_to_testers()` is new;
  `manage.py phone-test` now calls it rather than holding its own version.
  Deliberately no dedupe key: `utcnow()` has only seconds in it, so a key
  built from it would swallow a second run in the same second, and running it
  twice in a row is exactly what testing looks like.
- **Current state:** 535 tests pass. Three new ones cover the save path, the
  "only the ones just added" rule, and the unreachable/missing report.
- **Next step:** the organiser adds their own handle to the Test group, saves,
  and confirms the message arrives with a button that opens the phone.

## 2026-09-23 — The victim has a name, and three other words

- **Changed:** the escape room's phone was "his phone" and "The phone" on
  every screen, which reads as a placeholder rather than a story. It is
  **Kai Chen's phone** now — on the escape screen, on the ticket, on the
  phone's own screen, in Help, in the bot's messages and on the button
  Telegram draws. `ESCAPE_ROOM_FLOW.md` had the name all along.
- **Nothing about the phone until it is theirs.** The escape screen's premise
  no longer mentions a phone arriving, and the ticket's phone row says
  *At 7:40 PM* until the phone is genuinely open, then *Open now*. The button
  still appears only when the server says the phone is open to that person,
  which is unchanged — but now there is nothing else on the screen promising
  something that has not happened yet.
- **Up next** → the button reads **Manage**, not "Open it". It opens a
  booking to change, which is what people want it for.
- **Vinyl Making** → **Vinyl Crafting**, from `config.ITEMS`, so the pass, the
  Home blurb, Help, the booth and the stock row all follow.
- **The Start screen** reads **Hafary Gallery L5**, with no "The Hub @", and
  the **Pre-U event** chip is gone.
- **New:** `python manage.py reset-settings <name>...` puts named Settings
  rows back to the defaults in `config.py`. It shows before and after and asks
  for YES unless given `--yes`. It is needed because `config.py` is only the
  *starting* text: a row **nobody has edited** follows the default when the
  default changes (`db.seed_settings`), but one somebody has typed into on the
  Settings screen never does — and retyping a price list into a text box on
  the night is not a reasonable thing to ask.
- **Current state:** 539 tests pass. On this laptop's database every settings
  row is still `updated_by = 'system'`, so the venue and the price list picked
  up their new defaults by themselves.
- **Next step:** none for the wording. If the organiser edits a row on the
  night and wants the default back, that is what `reset-settings` is for.

## 2026-09-23 — Prices is a screen, and the gelato has its own name

- **Changed:** the price list was **Help's first question** — the thing people
  ask about most, folded into a `<details>` they had to find and open, inside
  a screen they had to think to visit. It is now a screen of its own:
  **Home row 04, Prices**, with a card in Help that opens it. Floorplan and
  Help move to 05 and 06.
- **The screen:** the matcha photograph across the top in **its own colours**
  (the `.shot-pass` / `.shot-jam` opt-out, dot screen at `.26` rather than the
  escape hero's `.34`), masked so it fades into the paper instead of sitting
  on it as a card; each price group a card with an Anton heading; rows at
  16px so they read at arm's length in a queue. Underneath, one line naming
  what entry already covers, so the page answers "do I have to pay for this?"
  as well as "how much?".
- Same data and same parser (`services/prices.py`, the `price_list` Settings
  row), so a price changed on the night still shows straight away.
- **Ice Cream Waffle → MUTED. Gelato**: Premium Flavours $6, Classic Flavours
  $5, Waffle Bites $2.50. The parser reads a heading with a full stop in the
  middle of it correctly; there is now a test that says so.
- **Also:** `scripts/record_answers.py` recorded its answers against an empty
  shots folder, so every photograph on every screen rendered as nothing and
  the render check never exercised one. It uses the real `static/shots` now.
- **Current state:** 539 tests pass; **33 screen states render** with no
  failures, which includes the new one.
- **Next step:** the organiser checks the photograph reads well on a phone —
  it is the one picture on the page and it is doing the work of a header.

## 2026-09-23 — The new floorplan, pinch only, and the way to the escape room

- **Changed:** `static/floorplan.png` is the organiser's new plan — the DIY
  area down the left, the jamming room and two chill rooms, the photo booth,
  and Two Goose, Paninis, Pastries and **MUTED. Gelato** along the top. Same
  2000×1414 shape, so `.plan{aspect-ratio:2000/1414}` and the clamping are
  unchanged, and `floorplan_url()` cache-busts on the file's modified time by
  itself. The `alt` text describes the new plan.
- **Pinch only.** Double-tap-to-zoom is gone. It was a second way to do what
  pinch already does, and on a phone it fires by accident: two quick taps
  while you work out where you are, and the plan jumps to 2.6× somewhere you
  were not looking. The hint reads **Pinch to zoom**. Drag-to-pan and the
  trackpad wheel are unchanged, and the `lastTap` / `moved` bookkeeping that
  only double-tap used went with it.
- **The way to the escape room** is a note under the plan: *go out of the
  entrance and take the first door on your right. The sign on it says Escape
  Room.* The escape ticket carries a **Where is it?** button to the plan,
  which is the moment anybody actually wants it.
- **Current state:** 539 tests pass; 33 screen states render. The render check
  now asserts the plan says "Pinch to zoom" and carries the directions, and
  that "double-tap" has not crept back.
- **Next step:** the organiser pinches the new plan on a phone and checks the
  stall names are legible zoomed in.

## 2026-09-23 — The booth counter: one thing at a time

- **Changed:** the booth screen (`templates/admin.html`, `SCREENS.booth`,
  `handBox`) stacked the viewfinder, the code box, the verdict, the person
  and the hand-over buttons into one scroll. The viewfinder is a 4:3 block,
  so on a counter phone the thing somebody had just scanned a pass to find
  out was below the fold. The screen now has two states, on one `.booth-body`
  class:
  - **Scanning** (`.scanning`): the viewfinder fills the phone, as before.
  - **A result** (`.showing`): the camera is already off at that point, so
    the viewfinder shrinks to a 52px strip — frame and sweep line hidden,
    the hint still readable — and the verdict, the person and the buttons
    get the room. The code box tightens to 44px.
- **What is left to collect comes first.** `handBox` used to render one red
  `.blocked-item` per item already gone, the same size as the buttons and
  mixed in with them, so a pass with two items collected read as two errors
  and pushed the one live button to third place. Items still to collect are
  now the whole list; what has gone sits under a rule at the bottom as a
  quiet `.gonebox` — item name, then time, kind, counter and staff. A pass
  with nothing left says *"Everything on this pass has been collected."*
- **Scan next is always under a thumb.** `.boothfoot` is `position:sticky;
  bottom:0` with a fade behind it and
  `padding-bottom:max(2px, env(safe-area-inset-bottom, 0px))`, so it clears
  Android's gesture bar however long the hand-over list runs. With a result
  on screen it reads **Scan the next pass** and goes solid black; **Check in**
  is disabled until there is somebody to check in, and says **Check in again**
  for somebody already in.
- **Two things the booth no longer says.** A person with no check-in gets a
  plain *Not checked in* tag rather than nothing at all, and the escape tag
  reads **The Last Guest · 7:05** instead of `Esc 7:05 · half B — desk`:
  the split went this morning, so there is no half to name.
- **The scanning mechanism is untouched.** `startCamera`, `stopCamera`,
  `scanLocked`, `camStarting` and the jsQR decode loop are byte-for-byte what
  they were, and both states keep every id the camera code reaches for
  (`#viewfinder`, `#cam`, `#vfhint`, `#codebox`, `#checkin`, `#scannext`).
  The 17 Sep one-read-per-scan fix stands.
- **A status line that counted nothing.** The GM card read
  *"Upcoming · phone opens at 7:05 · 0 of 6 have it"* before the booked time,
  which reads as a fault when it is the design. The count now appears only
  once something has actually been sent.
- **New file `scripts/render_console.mjs`** — the console's answer to
  `scripts/render_views.mjs`. It pulls the page script out of
  `templates/admin.html`, stubs the browser, and renders 18 booth and GM
  states against fixtures, asserting what each must and must not contain.
- **Current state:** 539 tests pass; `node --check` passes on the page
  script; 18 console states render with 0 failures.
- **Left unfinished on purpose:** no browser test covers the camera, for the
  same reason as 17 Sep — there is no browser harness here.
- **Next step:** the organiser scans a pass on the counter phone and checks
  that the verdict and the hand-over buttons are on screen without scrolling,
  and that **Scan the next pass** sits above the gesture bar.

## 2026-09-23 — The written record catches up with the room

- **Changed:** seven commits went in today and none reached the documents.
  `TESTPLAN.md` was the urgent one — the organiser works through it by hand,
  the event is tomorrow, and it still told them to press a **Start** that no
  longer exists, to swap somebody's **half**, and to look for "The Hub @" and
  "Vinyl Making".
- **`STATE.md`:** decisions **139–145** with their reasons, and a §8 status
  block for 23 Sep.
- **`BUILD_SPEC.md`**, following its own convention of a dated note appended
  to a rule rather than a rewrite: **rule 21** gains the 23 Sep change (the
  booked time is the whole rule; no check-in condition; `PHONE_OFF` is a fault
  and not a switch); **rule 22** (halves lock at Start) is struck through as
  withdrawn; the endpoint table drops `/halves`, renames `…/cues/{key}` to
  `…/hints/{key}` and adds `/gm/phone-test`; the error list is the five codes
  that are actually returned; and `halves_locked_at` and `in_app_phone` are
  marked dead in the schema.
- **`TESTPLAN.md`:** §A5 rewritten around a game that starts itself — step 17
  is now *"then wait — do not look for a Start button"* — with new steps for
  the Test group (24c) and for the changeover ticks surviving a reload (24b).
  Part B's halves check becomes a group check, and §A6's numbering, which
  restarted at 24 and collided with §A5, is fixed through to 31.
- **`RUNBOOK.md`:** the troubleshooting table no longer answers *"the phone
  says Locked"* with *"press Start"*. It now separates **Not yet** (wait for
  the booked minute) from **Locked** (a game master did that; Unlock), and
  says that Pause holds the phone open.
- **`ESCAPE_ROOM_FLOW.md`** keeps the **physical** two-space split, which is
  real and still how the room is played. What went is the app's part in it:
  the game master splits the group at the door themselves, because the console
  no longer assigns anybody to a side. The hint table's clock column stays as
  a guide to when a room usually needs each hint, not as something the console
  enforces.
- **Also** `README.md`, `DESIGN.md`, `HOW_IT_WORKS.md` — vinyl crafting, and
  halves out of the list of decisions the server owns.
- **Current state:** 539 tests pass; 18 console states render; both pages pass
  `node scripts/check_pages.mjs`.
- **Next step:** the organiser runs `TESTPLAN.md` Part A end to end. §A5 is
  the part that changed most and is worth reading before starting.

## 2026-09-23 — A review of the escape room, kept off GitHub

- **Changed:** new file **`ESCAPE_ROOM_PROPOSAL.md`**, and a `.gitignore` rule
  that keeps it on the laptop. It is the opinion layer next to
  `ESCAPE_ROOM_FLOW.md`'s operational flow: what the room is for, what to cut,
  where the design is fragile, and — §1 — a table of exactly which sources were
  read and which were not.
- **Why it is ignored:** the organiser's decision. It names the killer, the
  code and every hint, and the repository is still public. (`ESCAPE_ROOM_FLOW.md`
  is already up there in more detail, which is an argument for making the
  repository private rather than for adding to it.)
- **What it found, and neither is a code problem:**
  - **None of the five story photographs exist.** `manage.py phone-images`
    reports 5 of 5 still needed and `private/phone/assets/` holds only its
    README, so the evidence chain — the clock still, the corrected times, the
    bank screenshot — is not there. A player opening Photos sees grey tiles.
    The phone re-reads the folder on every open, so they can be dropped in on
    the night with no restart.
  - **`finder_name` is empty**, so the actor's character is unnamed; no actor
    is registered (`actor_chat_id` 0), so every hint is read aloud; and
    `phone_always_handles` is empty, so nobody can open the phone to test it
    outside a booked slot.
- **Also recorded:** `The Last Guest Guide.pdf`, which `ESCAPE_ROOM_FLOW.md`
  cites as the source that settles the cast and the puzzle chain, **is not in
  the repository**. Nothing here can be checked against it.
- **Current state:** 539 tests pass, unchanged — no code was touched.
- **Next step:** shoot `cam-04-kitchen-2227.jpg` first (the wall clock at 10:12
  against the 22:27 stamp); it is the one image the room cannot be played
  without.

## 2026-09-23 — The organiser's last four changes

- **The cookie is $4.** `Mini Cookie: $2.50` → `Mini Cookie: $4` in
  `config.PRICE_LIST`. The live row was still `updated_by = 'system'`, so
  `db.seed_settings` picked it up; checked against the database, not just the
  default.
- **The pass says "Tart or cookie".** `ITEM_NOTES["pastry"]` was
  "Mini tart, brownie, cookie or shiopan". **Wording only, at the organiser's
  decision** — `ITEM_CHOICES` is untouched, so the counter keeps all four
  buttons and a guest who asks for a brownie still gets one. The pass simply
  stops advertising four kinds.
- **The Prices screen says "Redeemables"**, not "Already yours". (The Help
  page's own "Included with entry" heading is a different block and is
  unchanged.)
- **A Mobile sign-in is the phone PIN and nothing else.** The **Your name** and
  **Where you are** boxes are gone from the form, from `doSignin`, and from the
  server's validation in `admin_login`. Filling two boxes on a counter phone,
  every shift, was the friction.
  - **Both are still accepted** if a caller sends them, so a station that wants
    its name on its hand-overs can still have it. Nothing asks.
  - **What the log loses** is the volunteer's name. It keeps the role, the
    time, and the station when there is one. Every `claims` and `audit_log`
    reader already joined those with `filter(Boolean)`, so an empty name
    degrades to a shorter line rather than a dangling separator.
  - **Two headers had to change.** The toolbar and the booth built theirs as
    `name · something` and would have read "GM · " with nothing after it. They
    name the door instead: **Mobile** or **Laptop**.
- **Current state:** **541 tests pass** (two new, replacing the one that
  asserted a name and a station were required). 22 console states render, up
  from 18: the sign-in screen is now covered on both doors and in its refused
  state, and the booth is rendered with the nameless session that is now the
  normal one. A broken sign-in screen locks every volunteer out of the console,
  so it was worth a case.
- **Next step:** the organiser signs in on a counter phone with the PIN alone
  and confirms the top of the booth reads **Mobile**.

## 2026-09-23 — Payment checking was still the default, so a fresh database gated everything

- **Found:** the organiser asked whether any payment gate was left anywhere in
  the app, not just the People page. **Yes — and the dangerous part was not a
  gate, it was a default.**
  - Every payment gate in the app comes through `claims.payment_ok`, which
    reads one settings row, `claim_requires`. The laptop's row said **`none`**
    because the organiser set it on 22 Sep, so the laptop was fine.
  - But `config.DEFAULT_SETTINGS["claim_requires"]` said **`"submitted"`**, and
    so did *both* `get_setting` fallbacks (`claims.payment_ok`,
    `people.person`). So **a database nobody has touched came up refusing
    hand-overs** — any fresh install, and the Render service on its first
    deploy, where the disk at `/var/yard` starts empty and `db.seed_settings`
    writes the defaults. The laptop's `none` lives only in the laptop's
    `data/app.db`; the server has its own.
  - `db.seed_settings` only re-seeds rows whose `updated_by` is `'system'`, so
    the organiser's edit would never have propagated to a new database either.
- **What that would have looked like on the night:** a pass scans and the booth
  shows the amber **! Not verified — Payment submitted, not checked — You
  cannot hand over** card; `hand_over` answers `PAYMENT_NOT_VERIFIED`; only an
  admin sees an override, and only with a typed reason; `/pass` in the bot adds
  *"we haven't verified your payment yet, so nothing can be handed over. pop by
  the front desk"*; Help grows a **"You haven't seen my payment"** question; the
  Overview grows a red **Payments to check** job; and the last-call message is
  silently **not sent** to anyone unpaid. With 150 of 169 receipts never
  checked, that is most of the room.
- **Fixed:** the default and both fallbacks are **`none`**. A gate now has to be
  asked for — a missing row cannot switch checking on by itself. The three modes
  (`verified`, `submitted`, `none`) all still work and are still one tap apart
  in Settings → **Hand-over needs payment**; nothing was removed.
- **Also:** the Settings help for **Entry fee** claimed it was "Shown to people
  whose payment isn't verified". It is sent in the event payload and rendered
  **nowhere** in the Mini App, so the help now says so.
- **New `tests/test_payment_gate_is_off.py`, 23 tests** — the guard, asserting
  the shape of a *virgin* database: the default, a deleted row, the booth
  hand-over and its warning card, `/api/me`, the person page, the last-call
  message and the Overview queue, each across all four payment states
  (missing, submitted, rejected, verified). One test still checks all three
  modes behave when asked for, so the feature is pinned as well as the default.
- **Eight existing tests** leaned on the old default to exercise the gate. They
  now set `claim_requires` explicitly, which is what they always meant.
  `tests/test_payment_no_reference.py` says it once in an autouse fixture,
  since the whole file is about the `submitted` rule.
- **Current state:** **564 tests pass.** 23 console states render; both pages
  pass `node scripts/check_pages.mjs`.
- **Still to check by hand, and not fixable from here:** the **Render service
  has its own database**. If it has ever been deployed, its `claim_requires` was
  seeded from the old default and is **`submitted` right now**. Open the console
  on the live URL → Settings → **Hand-over needs payment** → confirm it reads
  **Not needed**. This commit fixes what a *new* database does; it cannot reach
  a row an old one already wrote.

## 2026-09-23 — The organiser's last eight: copy, two prices, and no brownie

- **The escape room asks for a group of six.** A line under the premise: one of
  you books a time and adds the other five, because the flat and the desk each
  hold half of what the group needs. It says **six** rather than "a group"
  because `max_party` is 6 — a booker plus five.
- **"Are you musical?" is gone** from the Home row for the jamming studio. It
  asked a question the row could not answer, and half the people who read it
  say no to a room they would have liked. It reads **"Half an hour with a full
  kit — give our jamming room a try"**.
- **"Invite your friends to come hear you play" is gone** from the jam page.
  Nobody comes to watch, and the next sentence already says what the room is
  for: **"Pick a time and claim an instrument. Whoever takes the rest is your
  band for the night."**
- **"Paid at the front desk" → "Pay at the booth itself"** on the Prices screen.
  It no longer interpolates the `meeting_point` Setting, because the answer is
  no longer the front desk.
- **Mini Cookie: `$4` → `$2.50-4`.** **Leather Journal Making: `$25` →
  `$25-35`.** Both live rows were still `updated_by = 'system'`, so
  `db.seed_settings` carried them; checked against the database.
- **"How do I open Kai Chen's phone?" is gone from Help.** Anybody who needs it
  is already in a game and has the bot's message, and the button is on The Last
  Guest screen; Help was the one place describing a way in to people who had no
  way in.
- **The brownie is gone everywhere.** Out of `config.ITEM_CHOICES`, so the booth
  has three buttons — **Mini Tart, Mini Cookie, Shiopan** — and out of the price
  list, where it was $3.20. No claim in the database had ever been handed over
  as one, so the key is removed rather than retired.
  - Two tests handed over a brownie or asserted four kinds; both now use the
    three that exist. `RUNBOOK.md`'s booth step said four buttons, `README.md`
    and `BUILD_SPEC.md` listed four kinds, and this morning's `STATE.md`
    decision 146 said the counter would keep its Mini Brownie button — all
    four corrected, with 146 marked superseded the same day.
- **Current state:** **564 tests pass.** 23 console states render; both pages
  pass `node scripts/check_pages.mjs`.
- **Next step:** nothing for the wording. The brownie is the only one of these
  with a physical consequence — whoever stocks the pastry counter needs telling.
