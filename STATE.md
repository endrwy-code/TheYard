# STATE — where this build is right now

**Read this first, then `README.md`, `BUILD_SPEC.md`, `RUNBOOK.md`.**

This file is the handover point. It records what exists, what is still mock,
every decision taken since the original handoff and why, and what happens next.
If you are a new agent or a new session, everything you need to continue is
here — you should not have to reconstruct anything from conversation history.

Keep it current. The rule on this project is that after every major decision,
**every** affected file gets updated in the same pass: this file, `README.md`,
`BUILD_SPEC.md`, `RUNBOOK.md`, and `context/PROJECT_STATUS.md`.

Last updated: 22 Sep 2026, 18:50. **Latest (decisions 135–137, live):**
Overview counts **Opened the app** and **At the event** apart, the second
only from 3 PM on the 24th; **"the front desk"** is the one name for the desk
(Registration on the plan); the floorplan is a fixed frame you **pinch,
double-tap and drag**, with no Zoom button; and **payments are not checked at
all** (decision 138) while their screenshots stay on the person page —
145 of 152 are now saved on the laptop. **434 tests pass.**
**22 Sep (late):** decisions 132–134,
live — the pass is **Pastry (four kinds, staff tap which), Photo Strip,
Vinyl Making**, with no circles; Help has a **price list** (a Settings row)
and opens one question at a time; a **Floorplan** screen; escape games
**3:05–9:45 PM** (21); places from Settings ("the escape room entrance",
"Heaven 2", Two Goose, Shiopan Paninis); every bot message in a **relaxed
voice**; and `.gitignore` + `DEPLOY.md` for moving to a real server via a
private GitHub repo. **430 tests pass; `bot.py` needs a restart** (§8).
**Escape room story:** `ESCAPE_ROOM_FLOW.md`
(spoilers) proposes one flow for The Last Guest and lists what doesn't fit
yet. It is not agreed; the organiser answers its §12 before anything is edited.
**22 Sep (evening):** decisions 127–130 — Up next
with nothing booked is a card that opens Your bookings; new pass and jam
photographs in colour; Settings in plain words (**Real time / Test time**,
where test time is the 24th; event-day mode gone); and **everyone in the
escape game gets the phone, only from a bot message**, for 25 minutes.
**428 tests pass; `app.py` was stopped for the build and must be restarted,
with `bot.py`** (§8). **22 Sep:** decisions 122–126 — "The Yard Pass",
normal capitals for headings and buttons, a readable Help with the full venue
address, matcha/panini orders with a one-tap Telegram "ready" call, and a
console with two sign-ins, **Mobile** and **Laptop**. **408 tests pass**; not
yet tried on a phone (§8). **21 Sep, afternoon:** a UI pass at the
organiser's request (decisions 115–121) — Up next opens Your bookings and
grows into it, a free escape time has its own page, both rooms list people as
numbered boxes, the small print is gone, escape screens are dark to the edges,
and a button audit fixed five odd landings. **396 tests pass**; not yet tried
on a phone (§8). Before that: **Every P0 tier is built, and the spec
has no unbuilt rule left in it.** P0.2 is signed off, P0.3 tested by the
organiser. On 18 Sep: the roster-commit bug was found and fixed; crashes stopped
being reported as network failures; receipt archiving, the §9 r23 one-time phone
links, and two invariant bugs (halves after a removal, lowering seat counts)
were done. Then, on two rounds of the organiser's review of the finished Mini App:
friends stay together in the halves (93); the jamming studio is booked **by
instrument** (100, which reverses part of 96); the pass covers the cookie and
the photo strip only (101); every bot message is structured (102); Home is
re-ordered with a line under each row (103); the "next up" card opens a new
My bookings screen (104); Help is its own screen (105); the jam room has two
screens (106); photographs are optional and server-listed (107). **392 tests pass.** Testing lives in one file,
`TESTPLAN.md`, split into a solo part and a crowd part. §8 has what the
organiser does next. Dated changes are in `CHANGELOG.md`.

---

## 1. One-paragraph summary

The Yard is a Telegram Mini App plus a staff console for a one-day event on
Thursday 24 September 2026, **3–10 PM** (since 22 Sep, decision 131; games
3:05–9:45 since decision 133, jam 3:00–9:30 ending 10:00) at @ Hub @ L5 Hafary. Entry ($12, $10
early bird) is paid outside the app. The app handles what entry includes: a
pastry (one of four kinds), the first photo strip and vinyl making (each
collected once, decision 132), the escape room, and the jamming studio —
booked by instrument, five to a room. Help carries the price list for
everything else.
Everything is live; nothing in either page is faked. Attendees pass the gate,
show their pass, book The Last Guest with friends, book the jamming studio for
their group (free, and theirs for the slot), and open the in-app phone when
their game starts — everyone in the game, from the bot's "Open the phone"
message (since 22 Sep, decision 130).
Staff run the booth; the GM runs games from the GM console; admins verify
payments, fix the roster, change settings, read the audit log, export, back
up, block and move. The bot sends a small set of messages, in test mode (only
`@maxi_muslim`) until someone switches it on in Settings or with
`manage.py notify on`.

---

## 2. Build status

| P0 | Item | Status |
|---|---|---|
| 1 | The gate, roster import, `@maxi_muslim` override | **Done, live, signed off** |
| 2 | The pass and booth hand-over (once-only), event check-in | **Done, signed off 17 Sep**. Three items since 22 Sep (decision 132): the pastry (four kinds, the kind recorded), the photo strip, vinyl making |
| 3 | Admin search, the person page, payment status | **Built, tested by the organiser (13b)** |
| 4 | Escape booking with capacity and halves | **Built 17 Sep**; admin block/move and GM re-balancing 18 Sep; friends kept together 18 Sep (decision 93). Test: `TESTPLAN.md` B1 |
| 5 | Phone lock and unlock, with the half rule | **Built 18 Sep** (`services/game.py`), with §9 r23 one-time links and the phone's pictures. **22 Sep: everyone in the game, 25 minutes, reached only from a bot message** (decision 130). Test: `TESTPLAN.md` A5 and B3 |
| 6 | Jam booking | **Built 18 Sep**, free; **by instrument** since 19 Sep (decision 100) — five instruments, one seat each, anyone may join a slot. Test: `TESTPLAN.md` A4 and B1b |
| 7 | The audit log | **Built 18 Sep**: Audit screen with filters and search |
| 8 | Backups | **Built 18 Sep**: automatic every `backup_minutes` while app.py runs, plus Back up now |
| 9 | The RUNBOOK, Tailscale Funnel, desk devices | RUNBOOK current; Funnel and desk devices are the organiser's to set up |

P1 built: `bot.py` with reminders and `/actor`; the GM console with hint
sending; walk-ins; gate-denial linking; exports in the sheet's layout; stock
counts; **the exact and look-alike duplicate checks** (18 Sep, against the
archived receipts rather than uploads); **one-time full-page phone links**
(§9 r23, 18 Sep). Not built: **the Paperform webhook** — it needs a plan the
organiser may not have, and the upload path is the safety net either way
(§10). P2 (stats charts, printables beyond the fallback list, an escape
leaderboard) is untouched and deliberately not started: the event is on 24 Sep
and nothing in P2 affects whether the night runs.

---

## 3. What is live and what is mock

Nothing is mock. Both pages call the server for everything.

- **Mini App** (`templates/index.html`): the gate; Home; Your pass; The Last
  Guest (board, group booking); the ticket; the phone's own screen and the
  phone itself, reached only from the bot's message (decision 130); the
  jamming studio (board, then instruments); My bookings; Help.
  Event facts (date, hours,
  venue, entry fee, paid extras, help desk) come from Settings through the
  `event` block. It does not poll; screens refresh when opened, and
  countdowns re-render once a minute.
- **Console** (`templates/admin.html`): every screen is live. A reload keeps
  the sign-in. `GET /admin/api/live` pushes a change marker, and the screen
  you're on reloads within about a second unless you're typing. The top bar
  shows LIVE while the stream is connected; without it, Overview, People,
  Schedules and GM refresh every 30 seconds.

---

## 4. Files, and what each one does

```
STATE.md            this file — the handover point
CHANGELOG.md        dated entries: features, known bugs, structure, approach swaps
TESTPLAN.md         the one testing list: Part A alone, Part B with the crowd
HOW_IT_WORKS.md     for the organiser: the five layers, which layer each error
                    names, and a real fault traced end to end
DESIGN.md           the design system ("Yard Paper"): principles, tokens, type, components
app.py              web process: pages, every endpoint, the live stream, the backup timer
config.py           .env, paths, the item list, defaults for every Settings row
db.py               connection (WAL + busy timeout), the schema and its migrations,
                    settings helpers, audit(), code generation, backups
auth.py             initData verification, the gate rules, console sign-in:
                    server-side sessions, CSRF, sign-in and lookup rate limits
services/roster.py  Paperform import: read, preview, commit
services/claims.py  code parsing, pass QR, lookup, once-only claims, void, check-in
services/people.py  search, person page, payment verdicts and the reference check,
                    voids, the gate-denial list
services/bookings.py  escape and jam timetables, boards, group booking for both
                    rooms, cancel/leave, the halves rule, time clashes
services/game.py    P0.5 — game clock, the phone rules (§9 r21), GM actions,
                    half swaps and re-balance, script cues to the actor
services/admin.py   Overview, Settings, Audit, backups, Roster, walk-ins,
                    link/dismiss/unlink, block a slot, move a person
services/receipts.py  archiving the Paperform screenshots before their links
                    expire; the SHA-256 and look-alike duplicate warnings (§9 r30)
services/export.py  Registrations sheet, bookings, claims, printable fallback list
services/prices.py  reads the price_list Setting into groups for Help (decision 132)
static/floorplan.png  the venue map on the Floorplan screen (decision 132)
DEPLOY.md           for the developer moving it to a real server (decision 134)
.gitignore          what never goes to GitHub: .env, data/, imports/, receipts, .xlsx
services/notify.py  bot message copy, the outbox, staff direct messages, the send
bot.py              /start, /pass, /help, /actor; menu button; sends both queues every 5 s
manage.py           init-db · import · roster · make-secret · set-admin-password ·
                    set-staff-pin · set-gm-pin · backup · fetch-receipts ·
                    phone-images · void-claim · generate-slots · cancel-group ·
                    set-public-url · notify · notify-test · outbox
templates/index.html   Mini App, one file, inline CSS and JS
templates/admin.html   staff console, one file, inline CSS and JS
static/             yard-logo.png; shots/ — the optional photograph on each
                    Mini App screen, with a README naming them
private/phone/the-phone.html   the phone, served only by /api/escape/phone
private/gm/script.json         hint lines and the changeover checklist (spoilers)
scripts/start_event.ps1        opens the web (waitress, 24 threads), bot and tunnel windows
scripts/check_pages.mjs        node --check on each page's inline script
scripts/record_answers.py      saves the real server's answers to a JSON file
scripts/render_views.mjs       renders all 30 Mini App screen states from those
                               answers, in Node, so a template error is caught
                               here rather than on somebody's phone; also checks
                               the removed small print stays removed (119)
scripts/build_design_file.py   writes design\the-yard-design.html: the real page,
                               offline, with a 19-state picker (decision 109);
                               #state=N in the address opens a given state
scripts/merge_design.py        deletes the harness blocks to put it back
scripts/tap_through.mjs        taps through the buttons and booking controls in
                               headless Edge and checks where each lands (115–118)
scripts/motion_frames.mjs      captures the Up next grow and shrink frame by frame
                               in headless Edge (121)
design/DESIGN_BRIEF.md         the brief that goes out with the design file
design/the-yard-design.html    the design file itself (built; not hand-edited here)
design/index.html.bak          the page as it was before the last merge
design/old-shots/              the pass and jam photographs replaced on 22 Sep (128)
tests/              conftest.py, test_gate.py, test_roster_import.py,
                    test_claims_concurrent.py, test_people.py,
                    test_escape_capacity.py, test_notify.py,
                    test_phone_and_gm.py, test_admin_screens.py,
                    test_receipts.py, test_phone_links.py,
                    test_error_reporting.py, test_invariants.py,
                    test_orders.py (434 tests)
services/orders.py  matcha/panini orders and the "ready" call (decision 125)
private/receipts/   our own copies of the Paperform screenshots. Random
                    filenames, admin-only, never served without a sign-in
requirements.txt    pinned with pip freeze
```

`private/phone/the-phone.html` is finished except for five images the
organiser is supplying.

---

## 5. Decisions taken since the handoff, and why

Nothing in §3 or §9 of `BUILD_SPEC.md` has been changed. These are decisions the
spec left open, or points where the organiser gave a direct instruction.

### Front-end conversion

1. **Demo controls are mock-mode only.** Both templates carry a small floating
   "Demo" button opening the prototype's persona / clock / role / scan / review
   simulators. They are not rendered at all when `MODE` is `'live'`, so no
   attendee or volunteer can reach them.
2. **The simulated iOS status bar renders in mock mode only.** Inside Telegram,
   Telegram draws the real one; two would look broken.
3. **The in-page main button was kept rather than Telegram's `MainButton` API.**
   Telegram's button carries Telegram's own theming, which would change the
   approved design. The designed `#AE7338` button sheet is used in both modes.
4. **The prototype's bot-chat screen was not carried into `index.html`.** It is
   not a Mini App screen; it documents what `bot.py` will send. Its four
   messages are the specification for the bot at P1.
5. **A `static/` folder was added**, holding the logo and the demo QR that both
   pages load. `BUILD_SPEC` §7.2 did not list one. One cached request each, which
   is cheaper against the §3 rule 6 budget than inlining ~91 KB of base64 into
   every page load.
6. **The live pass QR will arrive as a data URI inside `GET /api/me`**, not as a
   separate image request, to hold a typical attendee visit to six requests.

### Navigation and coherence (organiser-directed)

7. **The Mini App uses a real history stack, not a fixed parent map.** Back now
   returns to the screen the person actually came from: Home → My bookings →
   a booking → Back lands on My bookings, not on the booking board. Scroll
   position is restored. Revisiting a screen unwinds the stack instead of
   looping. Steps you must not walk back into — a spent jam hold, a cancelled
   ticket — are replaced rather than pushed.
8. **The console has one persistent top bar on every screen.** The organiser
   judged the per-screen headers incoherent and hard to navigate, and asked for
   this. It carries the logo, the current screen name, all nine nav items, who
   is signed in, and Sign out. Screens a role cannot reach stay visible but
   greyed rather than disappearing. Booth mode and the GM console were
   previously reachable only from the demo panel; they are now in the nav.
   The visual language is unchanged — only the structure.

### The four screens the prototypes never drew

9. **Schedules, Roster, Settings and Audit were designed and built** in the same
   style, at the organiser's explicit instruction. Their sub-headers, tables and
   panels reuse the approved tokens (Anton headings, Space Mono numbers,
   `#F2EFE8` ground, white panels with `inset 0 0 0 1px #10101022`).
10. **The gate-denial queue lives on the People screen**, because `RUNBOOK`
    Phase 17 tells the organiser to watch for denials there and the fix — link
    or add the person — is a People action.
11. **Exports and backups are the second tab of the Audit screen**, so the
    `RUNBOOK`'s "/admin → Exports" has somewhere to land without a tenth nav item.
12. **Settings renders from a schema array** (`SETTINGS_SCHEMA` in
    `admin.html`), so adding a row is one object, and every row looks the same.
    Rows still carrying a brief placeholder are tagged amber.

### Backend

13. **`verify_telegram_data()` was extended, not rewritten.** The signature half
    is the original implementation. The `auth_date` maximum-age check (§9 r8) was
    added underneath it. `signature_ok()` and `init_data_age_ok()` exist
    alongside it so the API can tell `INITDATA_INVALID` from `INITDATA_EXPIRED`.
14. **The database is initialised at import time, not in `__main__`.**
    `waitress-serve app:app` never runs `__main__`, and the RUNBOOK uses waitress
    on event day.
15. **`manage.py import` takes an optional `--yes`** so it can run unattended;
    without it the confirmation prompt is unchanged.
16. **`attendees.submitted_at_text`** was added to the §8 schema. Paperform's
    "Submitted At" has an unknown timezone (§9 r10), so it is kept verbatim as
    display-only text for the export-back.
17. **Backups use SQLite's own backup API**, not a file copy, so a copy taken
    while the app is writing is still consistent.

### P0.2 — the pass, booth hand-over, check-in

Nothing in §3 or §9 was changed. These fill gaps the rules left open.

18. **A claim is `BEGIN IMMEDIATE` → one `INSERT` → `COMMIT`.** There is no
    "already claimed?" check before it; the `claims_once` partial unique index
    refuses the second insert, and the `IntegrityError` becomes
    `ALREADY_CLAIMED`. `BEGIN IMMEDIATE` only serialises writers so the stock
    check and the insert are one step. `tests/test_claims_concurrent.py` races
    2 and 8 threads on real WAL files, and was also run once with the index
    dropped to prove it then fails (both booths go green).
19. **`ALREADY_CLAIMED` carries the winner.** HTTP 409, and
    `error.claim = {item, id, at, staff, station, variant}` plus
    `error.message = "Matcha already collected at 7:14 PM (Booth 1, Wei)."`
    The booth's red screen now reads the server's `error.claim`. It used to
    read its own earlier lookup, which in a two-phone race says "not collected"
    and so named nobody.
20. **Lost races are logged too** ("Matcha hand-over refused — already
    collected"), because that is what the front desk gets asked about.
21. **Staff name and station always come from the signed-in session**, never
    from the request body. Staff must give a station at sign-in; a GM with no
    station is recorded as "GM"; an admin signs in with the password only and is
    recorded as "Organiser".
22. **Admin override** is an `override_reason` field on `POST /admin/api/claims`.
    It covers an unverified payment and an inactive person. A blank reason is no
    override. Staff or GM sending one get `FORBIDDEN`. The audit row carries
    `override`, `reason` and `blocked_by`. In booth mode an admin sees
    "Override — hand over matcha", which asks for the reason with the same
    `prompt()` the console already uses for voids.
23. **`payment_ok`** is returned by `GET /api/me` and by the lookup, and both
    front-ends use it instead of comparing against `'verified'`. Only the server
    knows whether Settings relaxed the rule to `submitted`.
24. **Stock (§9 r27):** `matcha_stock` / `panini_stock` of 0 means untracked.
    Remaining = stock − active claims. "Low" is 5 or fewer
    (`config.LOW_STOCK_AT`). A hand-over is blocked at zero only when
    `block_at_zero` is on; otherwise it only warns. Stock is per item, not per
    flavour. `variant` is stored on the claim if sent, but not stocked separately.
    Proper stock counts are P1.
25. **Code parsing (§9 r20):** `YARD:7K3MQ9XT`, `7K3M-Q9XT`, `7k3m q9xt` and
    `7K3MQ9XT` all find the pass. Anything not shaped like two groups of four is
    `NOT_A_YARD_CODE`. A Yard-shaped code nobody has, a mangled `YARD:` payload,
    or one using a letter outside the alphabet (0 O 1 I L) is `UNKNOWN_CODE`,
    because that is a typo. The QR payload has no hyphen.
26. **Event check-in happens once.** A second check-in returns `already: true`
    with the first time and who did it, and the booth shows a slate "Already
    checked in" screen. Inactive people are refused. `kind` other than `event`
    returns `VALIDATION_FAILED` until P0.4/P0.6.
27. **Console sessions are server-side** (new `console_sessions` table, beyond
    §8). The cookie `yard_console` holds only a random id; the table holds a
    SHA-256 of it and of the CSRF token. Sessions last 12 hours
    (`config.CONSOLE_SESSION_HOURS`), survive an `app.py` restart, and Sign out
    really ends them. Signing in again ends the previous session in that
    browser. Cookie: HttpOnly, Secure, SameSite=Lax.
28. **Role checks are deny-by-default on the server.** `ROLE_RULES` in `app.py`
    lists what staff and GM may call; everything else under `/admin/api/` is
    admin-only, including endpoints not built yet. GM-only: `/admin/api/gm/*`.
    Every POST/PUT/PATCH/DELETE needs `X-CSRF-Token`. Login must be JSON, which a
    cross-site form cannot send.
29. **Sign-in rate limit:** 5 wrong tries per device per 5 minutes, and 30 per
    role across everyone, so a 4-digit PIN takes about a day to guess. Behind
    the tunnel every request comes from localhost, so the device is the *last*
    `X-Forwarded-For` entry (the one the tunnel appends; a client can't forge
    it). Limits live in memory; a restart clears them.
30. **Lookup rate limit (§9 r28):** every lookup counts against the session's
    `lookup_rate_limit` (default 30 a minute). Hand-overs and check-ins count
    only when the code turns out to be unknown, so a busy booth is not slowed
    but the write endpoints can't be used to guess codes.
31. **Two new error codes** (in §12): `SIGNED_OUT` (401 — the console returns to
    its sign-in screen with a message) and `NOT_FOUND` (JSON 404/405 for any
    unknown `/api/` or `/admin/api/` path, instead of an HTML page the front-end
    would report as "Can't reach The Yard").
32. **Spoiler firewall fix (§3 r4).** `admin.html` carried the prototype's hint
    lines and reset checklist ("set the lock to 0000") as mock fixtures. Anyone
    could see them in the source of `/admin`, even before signing in. They are
    now inside `{% if show_mock_spoilers %}`, and `app.py` renders them empty.
    The GM screen gets its real lines from `GET /admin/api/gm/state` at P1.
33. **`python manage.py void-claim <username> <item> "<reason>"`** was added,
    beyond the P0.2 list. Without it the two-phone rehearsal can be run only
    once per item on `@maxi_muslim`, the only verified pass, and at the time
    the void endpoint did not exist. It uses `services/claims.void_claim()`:
    reason required, the void is soft, and it is audited (§9 r26).
    *(Since P0.3 the console can void from the person page too —
    `POST /admin/api/claims/{id}/void`. The command remains, for when the
    console is not to hand.)*
34. **Console coherence fixes made while wiring:** the Call button had borrowed
    the claims route key, so going live would have sent it to a missing
    endpoint. It now has its own flag and, in live mode, says it is not switched
    on yet rather than pretending to ping someone. A lookup that fails for a
    reason other than the code (rate limit, network, signed out) shows a toast
    instead of a misleading "Unknown code" card. A low-stock line appears under
    the hand-over button.
35. **Mini App coherence fixes:** `loadMe()` replaces the bare `/api/me` calls.
    If the gate refuses mid-visit (list changed, gate closed, session too old),
    the app returns to Start and says why, instead of showing "Loading…" for
    ever. The Home tile and Food & drinks now agree on "Payment not verified"
    (both use `payment_ok`).

36. **QR scans once (fixed 17 Sep, at the organiser's request, after P0.2
    sign-off).** Booth mode was reading the same QR again and again, because
    every re-render restarted the camera. Each repeat was a real lookup against
    the 30-a-minute limit. Now:
    - A read sets `scanLocked` and stops the camera straight away, so a
      detection already in progress can't fire a second lookup.
    - The camera stays off while a result is on screen, and comes back only on
      **Scan next** or when the full-screen result is tapped. That also clears
      the lock.
    - If a lookup shows no result (rate limit, network), the viewfinder says
      "Tap Scan next to scan again" instead of silently rescanning.
    - `camStarting` stops "Scan next" plus the re-render from opening two camera
      streams.
    - Leaving booth mode turns the camera off.
    - **Tightened later on 17 Sep:** after a read whose lookup showed no
      result, any re-render used to restart the camera and clear the lock, so
      a pass still in view was read again. `wire()` now does not start the
      camera while `scanLocked` is set. Only Scan next, tapping the result,
      opening Booth mode from the nav, or signing out clears it. While locked,
      the viewfinder hint reads "Tap Scan next to scan again".

    Not yet tested on a phone by the organiser (`RUNBOOK` Phase 13 step 9 has
    the check). Logged in `CHANGELOG.md`.

37. **`CHANGELOG.md` is kept from 17 Sep**, at the organiser's instruction: a
    dated entry whenever a feature is added or removed, a bug is deliberately
    left unfixed, the file structure changes, or one approach replaces another.
    Oldest first. It records *what* changed; this section keeps the *why*.

### P0.3 — search, the person page, payments

Nothing in §3 or §9 was changed.

38. **The transaction reference lives on the entrance `receipts` row.** There
    are no uploaded receipts yet, so verifying creates that row
    (`source` = `paperform`, or `admin` when there was no receipt link).
    Like claims, there is no "already used?" check first: the `receipts_txn`
    unique index refuses a second use, and that becomes `DUPLICATE_TXN_REF`
    (409), naming where the reference was first used. A four-thread race is
    in `tests/test_people.py`. References are stored upper-case with spaces
    removed, so `ab 12 34` and `AB1234` are the same reference.
39. **The console no longer guesses about references.** The prototype marked
    `8842119` as "already used" in the browser. That was removed; the server
    decides when Verify is pressed.
40. **Verdicts:** `verified` needs a reference of 4+ characters, or a reason
    for having none (stored as `txn_ref_skip_reason`; NULL references never
    clash). `rejected` needs a reason. A verified or rejected payment must be
    **reopened** (reason required) before it can change. Reopening releases
    the reference, so a mistyped one can be fixed, and goes back to
    `submitted`, or `missing` if there was never a receipt. The update only
    applies if the status is still what the admin saw, so two admins can't
    overwrite each other silently.
41. **"No receipt" people can be verified** by an admin who has seen the
    payment (§10 walk-in wording). The prototype showed a dead end there.
42. **Who decided and why is read from the audit log**, not new columns: the
    person page's `payment` is the latest "Payment verified / rejected /
    reopened" row. §8 stays unchanged.
43. **Receipt links and images are admin-only** (§9 r31). Staff get the rest
    of the person page, because the booth needs it for people whose phones
    died. Stored uploads are served only through
    `GET /admin/api/receipts/{id}/file`, with `no-store`, and a file name that
    would leave `private/receipts` is refused.
44. **Search** covers name, email, username (normalised, so `@Name` and
    `t.me/name` work), pass code in any shape, and booking refs. `%` and `_`
    are matched literally. Up to 50 results; active people first.
45. **The gate-denial panel is admin-only and read-only for now.** Linking
    and dismissing are P1; in live mode those buttons say so, as does Unlink.
    Staff don't see the panel, because its endpoint is admin-only.
46. **Paperform receipt links expire** (open question 8). The person page
    reads `expires=` from the link, stops offering an expired one, and says to
    look in Paperform's dashboard or re-export.

### bot.py and P0.4 — group booking (17 Sep, organiser-directed)

47. **Outbox instead of direct Bot API calls from Flask** (departs from §7.1).
    The web process writes a `notifications` row (new table, beyond §8) in the
    same transaction as the change; `bot.py` sends due rows every 5 s. So a
    rolled-back change sends nothing, a network failure is retried (5
    attempts), `dedupe_key` stops doubles, and stale messages (a Call, a
    reminder) expire instead of arriving late. Before sending, a row is
    claimed (`status='sending'`), so two senders never send one message
    twice. Cost: no message goes out unless `bot.py` is running.
48. **`notify_mode` = `owner` by default.** Only always-allowed/test accounts
    get messages; everyone else's are marked `suppressed` and never sent
    later. Switched with `manage.py notify on|owner|off`. This keeps testing
    with the real roster from messaging real people.
49. **The messages sent, and nothing else:** a friend added you (with how to
    leave and until when), the owner took you off, a friend left your group
    (to the owner), the game reminder at T−10 min, "your matcha/panini is
    being made" (the booth's Call button, deduplicated per 2 minutes), payment
    verified, payment rejected (with the admin's reason), doors-open on event
    day (15:00, event-day mode only), last call 30 min before close (checked-in
    and paid people with something uncollected). **Not sent:** hand-overs,
    check-ins, your own booking, a payment reopen — the person is already
    looking at the screen, or nothing changes for them.
50. **Telegram can only message people who have started the bot or allowed
    it.** `can_message` is set from `/start`, from `allows_write_to_pm` in
    initData, or from the Mini App's new **Allow** note on Home
    (`requestWriteAccess`). A failed send (403) turns it off. The ticket marks
    friends who can't be reached: "tell them yourself".
51. **Group rules.** The booker must be in the game. Friends are added by
    username, all or nothing, up to `max_party` (6 including the booker; new
    setting). `booked_by_id` records who added whom; only that person can
    add to or remove from their group. Edits are add or remove only, never a
    rename, and they lock at the booking cutoff (5 min before). Seats are
    per person, so other people can fill the rest of a game.
52. **Leaving vs cancelling.** Someone added by a friend can leave until the
    booking cutoff (5 min), because they didn't choose the game; the booker
    cancels under the normal 30-minute rule. The booker cancelling frees
    only their own seat — their friends stay booked.
53. **A friend who already has a game can't be added** (`FRIEND_ALREADY_BOOKED`),
    so nobody can be moved out of a game they chose. Failed friend adds are
    rate-limited (`friend_fail_limit`, 10 per 10 min per person), because each
    "not on the list" answer reveals something about the roster.
54. **Halves** are assigned at booking (smaller half first, §9 r16) and shown
    to attendees only once the game starts. The booth lookup shows them
    earlier, for the door. Removing people can unbalance halves; the GM
    re-balance is P1. *(Superseded by 88: the GM re-balance was built on
    18 Sep, and halves now even out by themselves when someone leaves before
    the game starts. Removing people no longer leaves them unbalanced.)*
55. **Interim phone status** until P0.5: before the game "locked", during it
    "the phone is at the desk" (true — the desk devices), after it "case
    closed". *(Superseded by 70: the in-app unlock was built on 18 Sep.)*
56. **Bot buttons deep-link.** "Open The Yard" opens `PUBLIC_URL/?go=ticket`
    (or `food`); after Start the app opens that screen, and Back returns to
    Home. `PUBLIC_URL` was set in `.env` on 17 Sep with the new
    `manage.py set-public-url`.
57. **The 14 real games were generated** in `data/app.db` on 17 Sep
    (`manage.py generate-slots`, idempotent). Superseded by 62: 13 games.

### The organiser's source of truth (17–18 Sep)

58. **The app only handles what entry includes.** Entry ($12 / $10 early
    bird until 20 Sep 23:59) and every extra (Loft food, DIY in Crib,
    photobooth) are paid at the front desk. The app sells nothing.
59. **The once-only items are a cookie or pastry and a canned drink**
    (`config.ITEMS`: `pastry`, `drink`). *(Superseded: the photo strip joined
    on 18 Sep (68) and the drink was dropped entirely on 19 Sep (101). The
    list is now `pastry`, `photo`.)* One list drives the services, the bot
    text, the Mini App and the console. The free photo strip is not tracked;
    adding it would be one line in `config.ITEMS`.
60. **Call removed.** It existed for made-to-order matcha and panini;
    pastries and cans are handed straight from stock.
61. **The jamming studio is free.** Book and it is confirmed; one slot each.
    *(Superseded in part by 96: it is booked for a group now, not one person.
    Still free, still one slot each.)* Original wording:
    (`jam_per_person`); 30-minute slots 5:00–9:30 PM. A jam slot cannot overlap
    that person's escape game (±5 min to walk), checked both ways. Receipt
    uploads, the Reviews screen, PayNow settings and `data/receipts` are gone.
    Payment problems are sorted at the front desk and marked on People.
62. *(The opening time and the count changed on 22 Sep — decision 131: doors
    3 PM, 19 games, 228 seats, 14 jam slots.)*
    **Doors close at 10 PM**, so the last game is 9:30 PM (13 games, 156
    seats) and last call is 9:30 PM. `generate-slots` removes unbooked games
    that no longer fit, retires (blocks) ones that were ever booked, and
    reports any with live bookings instead of deleting them.
63. **Settings follow the code while untouched.** On start, rows still owned
    by `system` take the new defaults and removed keys are deleted; values an
    admin changed are kept.
64. **"You're booked" is unmistakable**: a green banner with the game, time,
    friends and ref, a success buzz, and a Telegram message. Shown once.
65. **The console survives a reload.** `GET /admin/api/session` resumes the
    session and rotates the CSRF token; an older tab gets `STALE_TOKEN`, then
    fetches the token again and retries once. People refreshes every 30 s while
    in front and nobody is typing.
66. **No demo mode in live pages.** The Mini App lost its mock layer; the
    console keeps demo answers only for routes in `NOT_BUILT`.
67. **Test clean-up is a command**: `manage.py cancel-group <handle> <reason>`
    cancels a whole group, withdraws queued messages for it, and messages
    nobody.

### 18 Sep (evening) — design, P0.5 and the console (organiser-directed)

68. **The photo strip is the third included item** (`photo`). Nothing else
    needed changing; the item list drives everything.
69. **Design system "Yard Paper"** (`DESIGN.md`) replaces the prototype's
    look in the Mini App: say things once, rows and rules instead of " · ",
    Anton + Archivo, grain and halftone. BUILD_SPEC §14's "do not restyle"
    is overridden by the organiser. "Food & drinks" is now "Your pass".
70. **The in-app phone opens only for a checked-in desk-half player during a
    started game**, until `relock_minutes` after it ends (§9 r21). In
    `gm_start` mode the GM's Start starts it; in `clock` mode the schedule
    does. The GM can lock, unlock, or switch the in-app phone off per game;
    Settings can switch it off for everyone. End locks at once.
71. **"Checked in" for the phone** means the event check-in at the booth (or
    an escape-booking check-in). The GM screen shows who is in; it doesn't
    check people in.
72. **The GM picks the game** from a list; by default it is the running game,
    else the next one. The timer is the server's figure, ticked on the
    device. Pause, +1 minute and End are logged.
73. **Hint lines live in `private/gm/script.json`**, never in a page (§3 r4),
    and reach the actor's Telegram when they have sent `/actor <GM PIN>` to
    the bot. Without an actor, the GM reads them out; the cue is still marked.
74. **Halves**: a swap or re-balance is allowed before and after the start,
    and always logged; after the start the log says so. Re-balance moves the
    most recent bookings first.
75. **Live updates by server-sent events**, not faster polling. One open
    request per console stays within §3 r6 on ngrok; the audit log's newest
    id is the change marker because every write is audited.
76. **Automatic backups run inside app.py** (a background thread checks every
    minute), so there is no extra window to keep open.
77. **Settings saves are validated** (types, times, choices, doors before
    close) and audited with before/after. Changing game or jam times rebuilds
    the timetable at once; anyone booked on a removed time is named.
78. **Moving someone** re-assigns their half for the new game and messages
    them. Blocking a slot needs a reason and names who is still booked.
79. **Linking a refused account** links the Telegram id to the chosen person
    and clears every open refusal from that account; it refuses if either
    side is already linked elsewhere.
80. **The CSS clean-up bug** (stripped `@media`/`@keyframes`) is fixed in both
    pages. Future clean-ups must not use a flat regex over CSS.

### 18 Sep (morning) — the roster bug, and what it exposed

81. **The owner row is no longer hidden from the roster preview.**
    `roster.preview` used to build its "who already exists" map with
    `WHERE source != 'owner'`. When the organiser filled in their own
    Paperform, their `@maxi_muslim` row was invisible to the match, the plan
    said "new", and the INSERT hit the UNIQUE index on `attendees.handle`.
    The whole import rolled back. The preview promised a commit the database
    would always refuse. It now matches against every row.
82. **Rule 12's sweep is scoped to imported people.** Because of decision 81
    the match map now contains walk-ins and the owner too, and rule 12 marks
    anyone missing from the file inactive. Left alone, the first re-import
    during the event would have deactivated every walk-in and taken their
    passes down with them. The sweep now considers `source='import'` rows
    only. **This is an interpretation of a §9 rule, not a change to it** —
    a walk-in and the owner are never in a Paperform export, so they cannot
    meaningfully be "missing" from one. Flagged to the organiser.
83. **Commit re-checks for a clash as it writes.** A preview taken at 10:00
    and committed at 10:10 does not know about a walk-in added at 10:05. It
    now names the person instead of raising a bare SQLite error.
84. **A crash is never reported as a network failure again.** `app.py` only
    caught `ClaimError`, so anything else became Flask's HTML error page;
    both pages read every answer as JSON, so the parse threw and the only
    thing they could say was "Can't reach The Yard". That cost an evening
    looking at the tunnel. There is now a catch-all handler returning JSON,
    an `sqlite3.IntegrityError` branch returning 409 with the constraint
    named, `logging.basicConfig` so the `app.py` window prints a timestamped
    traceback, and distinct wording in both pages. **The two messages mean
    different things and must stay different:** "Can't reach The Yard" is the
    tunnel, "something went wrong at our end" is us.
85. **Receipts are archived onto the laptop** (`services/receipts.py`).
    Paperform's links expire 7 days after each sign-up — all of them before
    the event (open question 8). A local copy does not expire, is admin-only
    (§9 r31), is re-saved to strip EXIF (§9 r29) under a random filename, and
    the person page prefers it over the link. This also made §9 r30's first
    two layers possible again after uploads were dropped: SHA-256 for an exact
    copy, and a difference hash for a look-alike. Both only ever warn.
86. **A blank image has no fingerprint.** A flat picture's difference hash is
    all zeros, so two blank images would "look alike" and accuse a real
    attendee. A degenerate hash is now treated as absent.
87. **One-time phone links** (§9 r23) live at `/p/<token>`, outside `/api/`
    because they open in the real browser where there is no initData. Ninety
    seconds, single use, and **rule 21 is re-checked as the link is spent** —
    otherwise "lock the phone" would not reach a link already in a hand. The
    Mini App offers it quietly under the main button, because it is a fallback
    and sending people out of the app by default would be worse.
88. **Halves re-balance when someone leaves, before the game starts.** §9 r16
    balances on the way *up* only, so a six that lost two from the desk half
    arrived 3 and 1 — and the desk half is the half with the phone. The game
    is built so neither half finishes alone, so that is a broken game. After
    the start nothing is touched: §9 r22 locks the halves and only the GM
    moves anyone, logged.
89. **Lowering the seat count names the games that are now over-full.**
    Nothing throws a booked person out, so a game quietly read "4 of 2" and
    only a head-count at the door would have caught it. Settings and
    `generate-slots` now name the game and how many to move.
90. **The test suite no longer depends on the laptop's date.** Slots are
    generated on `config.EVENT_DATE`, so every test that booked through the
    API would have started failing on 25 Sep with `SLOT_STARTED` — and the
    RUNBOOK has the organiser run the suite on the morning of the event and
    stop if it is not green. `conftest.TEST_NOW` pins the API's clock.
91. **Testing is one document, `TESTPLAN.md`,** split by what each test needs
    rather than by tier: Part A alone with one phone, Part B with the crowd.
    RUNBOOK 13c/13d are now a pointer to it. The reason for the split is that
    a broken tunnel or sign-in stops everything in Part B, and that is worth
    half an hour alone rather than an evening of other people's time.
92. **`HOW_IT_WORKS.md` was added** for the organiser: the five layers, which
    layer each error message points at, and the roster bug traced end to end
    as a worked example. `RUNBOOK` Phase 18 stays the fast symptom lookup.

### 18 Sep (afternoon) — the organiser's answers to §7

93. **Friends who book together stay together** (`bookings._assign_halves`).
    The organiser's answer to open question 9 was "NO, as much as possible try
    to group them together". §9 r16's "each new player into the smaller half"
    alternated A, B, A, B down a booking and split every group; halves are now
    decided for the whole game at once, by group.

    The phrase "as much as possible" is doing real work, because two things
    cannot both be true: a group should stay whole, **and** the game needs
    somebody in the flat and somebody at the desk — the desk half holds the
    phone, and a game with an empty desk cannot be played. So a group is split
    only when there is no alternative: when it is **alone in the game**, or
    when it is **larger than one half**. Two or more groups sharing a game are
    never mixed. Largest group is placed first, because a split hurts it most.

    The GM's "even out the halves" runs the same function (with `force`, since
    §9 r22 has locked them by then) — doing it separately once meant the
    button quietly undid the grouping.

    **This changes the behaviour of a §9 rule.** The organiser is the design
    authority and directed it explicitly. The rule's *text* is unchanged; what
    changed is who gets put where.
94. **`low_stock_at` is a Settings row.** The organiser asked whether they
    could change the low-stock threshold on the Settings screen. They could
    not — it was `config.LOW_STOCK_AT`, a constant needing a file edit and a
    restart. It is now a setting starting at 5, validated like the rest, and
    `config.LOW_STOCK_AT` is only the seed value. Answering "yes you can" and
    leaving it in a file would have been false on the night.
95. **The phone's pictures are served, not embedded.** The phone file is a
    bundled export and asks for `assets/<name>.jpg` relative to itself, so the
    names are matched rather than the file edited — cutting into a minified
    bundle days before the event is not worth it. `/api/escape/assets/<name>`
    serves them behind **the same §9 r21 check as the phone**, because these
    *are* the evidence and §3 r4 says the evidence never reaches an attendee
    screen. Only names on a fixed list are served, so the route cannot be
    walked out of the folder. A picture that does not exist yet answers with a
    grey tile, so the game can be rehearsed before the photographs arrive. On
    a desk device the file is opened from disk and the same relative paths
    work with no server at all.

    One consequence worth knowing: the one-time link is now `/p/<token>/`
    **with a trailing slash**, because a browser resolves `assets/...` against
    the directory part of the address and without it they would land above the
    token. A link without the slash redirects, and the redirect does not spend
    the single use.

### 18 Sep (evening) — four organiser notes on the new design

93–95 are above. These came from looking at the finished Mini App.

96. **The jamming studio is booked as a group**, like the escape room. It was
    one booking per slot. The organiser's reason, in their words: an escape
    room with strangers is cool, a jamming room with strangers is weird. So
    the booker brings their own people, up to `jam_capacity`, and **the room
    does not have to fill** — leftover seats are not offered to anyone else.
    A slot belongs to the group that booked it (`SLOT_TAKEN`).

    **Partly superseded by 100 the next day.** The room is now booked by
    instrument and anyone *may* join a slot, because five strangers each on
    their own instrument turned out to be the answer to the same worry. The
    group booking, the all-or-nothing rule and everything listed below it
    survived the change; `SLOT_TAKEN` did not.

    The booking design is deliberately the escape room's: all or nothing, the
    booker adds and removes people, anyone else can only leave, and the clash
    check runs for **every member's** escape game rather than the booker's
    alone. The screen keeps its approved design — the same "Who's coming?"
    panel, now shared by both rooms.

    **What it dragged with it**, since the organiser asked for the knock-on
    effects to be found rather than waited for:
    - `jam_bookings` gained `booked_by_id` and `cancelled_at`; the unique
      index `jam_one_per_slot` (one booking held the room) was **dropped** and
      replaced by `jam_one_seat_each`. Dropping runs before the schema, in
      `db.DROPPED_INDEXES`, so an index a rule outgrew cannot survive and keep
      enforcing the old rule.
    - Four new bot messages: `jam_friend_added`, `jam_removed`,
      `jam_friend_left`, `jam_cancelled`. `text_jam_booked` now names the
      group. All five are in `manage.py notify-test`, so the organiser can
      read every message the bot can send in one pass.
    - **Reminders needed no change** and that is worth knowing: they are
      queued per booking *row*, and every member has one, so they already
      reach the whole group.
    - `cancel-group` clears jam seats too — clearing only the escape game
      would have left half of a test behind for somebody to find on the night.
    - Schedules shows the booker plus a head count; Overview's "Jam slots"
      gained the number of people; the bookings export gained a "Booked by"
      column, without which a slot reads as several unrelated people; the
      person page names whose slot it is.
    - `block_slot` needed nothing: it already names everyone on a slot,
      because it counts rows.
97. **The opening hours are off the Home screen.** The phone draws its own
    clock in the status bar directly above, and two times in one corner read
    as a contradiction. They moved to Help (then Bookings & help), under "When and where",
    where somebody is actually looking them up, and they are still on the gate
    screen, where somebody is deciding whether to come.
98. **The wordmark replaces the word "The Yard" on Home.** Drawn as a CSS mask
    filled with `var(--ink)` rather than an `<img>`, so it is the same ink as
    the type beside it and follows the palette; the artwork is black on
    transparent and the paper ground is warm, so a flat black PNG sits a shade
    cooler. Home only — every other screen has to say where you are, not whose
    app this is.
99. **The booth already answers "how do you know what they are claiming?"**
    The organiser asked. A scan shows the person and then one button per item
    still to collect, with a red line and the time, station and staff name for
    anything already taken. Nothing was needed.

### 19 Sep — the organiser's review of the finished Mini App

100. **The jamming studio is booked by instrument.** This reverses part of
     decision 96, deliberately and at the organiser's instruction. Five
     instruments — acoustic guitar, electric guitar, keyboard, drums, bass
     (`config.INSTRUMENTS`) — and one seat each. **Anyone may join a slot
     somebody else started**, which is the opposite of 96's "the room is
     theirs". The reasoning changed with the model: five strangers each on
     their own instrument is a jam, whereas five strangers sharing a room
     with nothing to do was the awkward thing 96 was avoiding. `SLOT_TAKEN`
     is gone; `INSTRUMENT_TAKEN` replaced it. A booking still brings friends,
     all or nothing, and each of them names an instrument.
     New index `jam_one_player_per_instrument` decides a race for the last
     drum kit. It lives in `db.LATE_INDEXES`, not `SCHEMA`, because it
     indexes a column `ADDED_COLUMNS` adds — on an existing database SCHEMA
     runs first and the column is not there yet.
101. **The pass covers the cookie and the photo strip only.** The canned
     drink left `config.ITEMS`. **Confirmed the same day: it is not included
     with entry at all any more**, so it is off the "included" list rather
     than merely uncounted. Drinks are sold at Loft, which `paid_extras`
     already covers.
102. **Every bot message is structured.** A heading, labelled lines, an
     optional list, then one line of what to do — built by `notify._msg`,
     sent with `parse_mode: HTML`. The organiser's complaint was "word
     vomit": the old messages were a paragraph each, and a paragraph is
     something you read twice to find the time in. Everything a person
     supplied goes through `notify.esc()` first, because a name with an
     ampersand would otherwise break the whole message.
103. **Home is re-ordered and each row explains itself**: Your pass, The Last
     Guest, Jamming studio, Help, each with a line underneath. The names
     alone assume you already know what the evening contains — "Your pass"
     means nothing until somebody says it is the thing you hold up.
104. **The "next up" card is the way into your bookings.** It was the most
     looked-at thing on Home and the only thing you could not tap, which
     read as a dead end. It now says "Your next slot" and opens **My
     bookings**, a new screen.
105. **Help is its own screen**, split from bookings, with an FAQ. Somebody
     looking for "who do I ask" had to scroll past their own tickets.
106. **The jam room has two screens, like the escape room**: board, then a
     screen for instruments and people. They are deliberately unalike —
     the escape room is dark, cramped and urgent; the jam room is paper,
     wide, with the instruments as stencilled type. Same app, but you know
     which room you are in before reading a word.
107. **Photographs are optional and server-listed.** `static/shots/<screen>`;
     `event.shots` lists only files that exist, so a missing photograph
     leaves no gap and no broken image. Greyscale + halftone in CSS so a
     photograph belongs to the same world as the grain. The organiser is
     supplying them; `static/shots/README.md` says which and what suits.
     **These are public** — the escape room's evidence stays in
     `private/phone/assets` (§3 r4).
108. **The Last Guest's premise finishes its thought.** It ended on "you have
     the same fifteen", which is a good line and a bad ending: it never said
     what you were meant to do. It now names the lie and the split.

### 21 Sep — the design round trip, and the flash

109. **The look is reworked in a design tool, through a file that goes out
     and comes back.** `scripts/build_design_file.py` writes
     `design/the-yard-design.html` — the real page, working offline, with
     the network stubbed by recorded answers, writes politely refused, and a
     picker for 17 screen states. Everything it adds is inside blocks marked
     `DESIGN-HARNESS` and `DESIGN-BRIDGE`; `scripts/merge_design.py` deletes
     exactly those and refuses if a marker or a must-keep piece is missing.
     The round trip is byte-identical, which is the whole point: a design
     pass cannot quietly change behaviour, because the only thing the merge
     does is delete. `design/DESIGN_BRIEF.md` goes out with it.
110. **The phrase "your half" is gone from the app.** The organiser: *"your
     half sounds so bad to me."* The premise now says two groups; the ticket
     row is "Where you start" with "Inside the flat" / "At the desk, with the
     phone"; the phone card says where the phone is rather than who you are.
     **The server code `PHONE_NOT_YOUR_HALF` and the zone values `A`/`B` are
     unchanged** — this is wording only, and §3 r4 and §9 are untouched.
111. **Your bookings is a dark page of one card per room.** It was a bright
     page of thin rows. An activity you have **not** booked shows as an
     outlined card of the same shape rather than disappearing, so the page is
     always two rooms and never a list that shrinks. Cancelling, names and
     instruments stay on each activity's own screen, as the organiser asked.
     It uses only fields the server already sends.
112. **The escape room's group panel is rows, not chips.** A count on the
     right ("2 of 6"), one 56px row per person, and a full-width "Add them".
     `#friendbox`, `#friendadd` and `[data-undraft]` are unchanged, so the
     wiring did not move.
113. **There is no screen transition, and that is the decision.** The
     organiser, three times: *"every single asset and button and qr code
     turns blank and then comes back."* Two rebuilds were attempted before
     the real cause was found, and both missed it, so the reasoning is worth
     keeping.
     The cause was never one bug. It was **fourteen separate CSS rules that
     start an element at `opacity:0` and fade it in**, the decisive one being
     `.view{ animation:vIn }` — and `.view` is the root element of *every
     screen*. The second attempt added
     `.scroll.fwd > * *{ animation:none }` to hold the contents still, which
     never touched `.view`, because `.view` **is** the child, not a
     descendant of one. So the whole screen went on fading up from nothing.
     Why that reads as a flash rather than as a fade: a screen is rebuilt
     with `innerHTML`, so every element is new, and the fade cannot start
     until the browser has parsed and laid all of it out. Those few frames
     are painted at `opacity:0` — a blank page — and then everything appears
     at once. It also explains the one detail that never fitted: a **first**
     visit to a screen looked fine, because it renders a skeleton, and the
     repaint when the data lands was not an arrival and so never faded.
     All fourteen are gone, along with two `tick` rules that pulsed text
     between 45% and 100% opacity for ever. **The movement then came back,**
     because the movement was never the fault: the transition is now an 18px
     `transform` nudge with no `opacity` anywhere, which has no frame in
     which anything is invisible. 18px rather than a full screen width
     because the outgoing screen is already gone, so a longer slide would
     drag a band of empty paper across.
     **The design tool's motion work — the ghost, `expandInto`,
     `data-morph`, `data-lift`, the staggered `data-seq` entrances — was
     deliberately not merged**, because that machinery is the same idea
     again.
     **The rule this leaves behind: nothing that holds content may start at
     `opacity:0`.** It is written up in `DESIGN.md` §7 with the short list of
     what is still allowed to move, and — because this went wrong three times
     and no other check in the project could see it — it is enforced by three
     tests in `tests/test_invariants.py`. They read the page's CSS as text,
     resolve which keyframes each rule uses, and fail with the offending
     selector named. Reintroducing the original fault trips all three. A new
     fade-in has to be added to their `MAY_FADE` list on purpose.
114. **What is still allowed to move, and why each one is safe.** Presses
     (`transform` on `:active`, and the person caused it); the back-swipe,
     now left-edge only at 36px — it used to start from anywhere, so every
     press on a slot tile also began a back swipe and fought the phone's own
     gesture; the bottom sheet, which slides on `.mainsheet.in` so it plays
     once when it first appears rather than on every render; the toast, which
     is an overlay that genuinely arrives and leaves; the ring on the phone
     button, which is on `.phone-open::after` and so never touches the text
     — it used to animate `box-shadow` spread, repainting that button every
     frame for as long as the app was open; and the booking stamp, built on
     demand and thrown away, which is the one deliberate moment in the app.
     Alongside those: `prewarmShots()` decodes the photographs as soon as
     `/api/me` names them, and `loading="lazy"` came off — it guaranteed a
     late decode of the one picture above the fold.

### 21 Sep (afternoon) — the UI pass (organiser-directed)

The organiser: the flow is right, now make it look better, feel smoother and
be easier to find your way around. **Status: built 21 Sep, not yet tried on a
phone** — §8 has what is verified and what is next. No server change; every
field used was already in `/api/me` and `/api/*/slots`.

115. **Up next opens Your bookings, always.** It opened whichever ticket was
     soonest, so the organiser landed on "a page of only the jamming room".
     A full audit of every button came with it: the jam board's own slot now
     opens its jam ticket (it opened Your bookings; the escape board's opens
     its ticket); Back after an escape booking returns to the board (it
     skipped to Home); cancelling or leaving returns you to wherever you came
     from (it always went to a fixed screen); the tickets lose "All games /
     All slots" and "Everything you hold", which only repeated Back; and
     `?go=bookings` is read as `mybookings` so the history stack sees one
     page, not two.
116. **Tapping a free escape time opens its own page** (`escbook`), the same
     shape as the jamming studio: the time, who's coming, the Book button.
     The board goes back to being a clean grid. Names you have typed come
     with you if you go back and pick another time.
117. **One numbered list of people, in both rooms.** A box per person:
     number, name, one tag or one button. Yours is filled; ones you can
     change have ×; ones you cannot (another group in the jam room, or
     everyone when somebody else booked) are **dimmed, not blurred** — blur
     would hide who is coming, which is the point of the list. The last box
     is the next number with the add box in it.
118. **Edit exists only before you book.** After booking, every change
     messages people on Telegram, so an "edit" would tell one person they
     were removed and another they were added, over a typo. Before booking
     it is free: Edit puts the name back in the add box.
119. **The fine print goes.** The organiser: *"ugly and over bearing."* What
     carried real information moved instead of vanishing: the booker is a
     fact row ("Booked by @x"); what cancelling does is in the confirm
     dialog; and the deadline is one line in the organiser's words — *"You
     can change this anytime, until 5 minutes before your booking."* The
     escape room also gets *"You can cancel anytime, until 30 minutes before
     your booking,"* because cancelling closes earlier than changes there.
     Both numbers are worked out from the server's `edit_until` /
     `leave_until`, never typed in, so they stay true if Settings change.
120. **One ground per room.** The escape ticket was a cream card on black —
     *"jarring."* Every escape screen is now dark all the way through: the
     ticket, the top bar, the bottom Book bar and Telegram's own header. Jam
     screens stay paper. Moving between rooms changes the ground between
     pages, never inside one.
121. **The Up next card grows into Your bookings — and this revises 113 on
     purpose.** 113 refused the design tool's `expandInto` morph because it
     animated freshly built markup, whose first frames are blank on a busy
     phone. This uses the browser's **View Transitions API** instead, which
     freezes the current frame and animates *pictures* of screens that are
     already drawn, so there is no half-built frame to show. It keeps 113's
     rule — no `opacity` anywhere — and a new test enforces that for the
     transition's own rules. It runs only for Home ↔ Your bookings, falls
     back to the 18px nudge where the API is missing (iOS before 18, some
     Telegram Desktop builds) or motion is reduced, and `MORPH = false` at
     the top of the script turns it off.

### 22 Sep — the pass, Help, capitals, ready calls, phone and laptop (organiser-directed)

**Status: built 22 Sep, not yet tried on a phone** — §8 has what is verified
and the restart it needs.

122. **"Your food pass" is "The Yard Pass".** The photo strip is on it, so
     "food" was wrong. Pass items keep their keys (`pastry`, `photo`).
123. **Normal capitals for headings and buttons; small labels stay capitals.**
     Titles, names and buttons are no longer forced into upper case: "Evening,
     Heidi", "The Yard Pass", "Book 5:30 PM for 3". Names of things take
     title case — **Cookie or Pastry, Photo Strip, The Jamming Studio, The
     Last Guest** — and sentences stay sentence case. The 11px spaced labels
     (UP NEXT, WHEN AND WHERE) stay capitals: at that size they read better,
     and they carry the look. Mini App only; the console keeps its own style.
124. **Help is easier to read**: each section is a card with its heading in
     the accent colour, the questions open and close, and the venue has its
     street address and a Maps button. **Venue: "The Hub @ Hafary Gallery
     L5", address "105 Eunos Ave 3, Singapore 409836"** — the organiser's
     draft said Level 2 in the address and L5 in the name; they confirmed
     Level 5. The address is a new setting, `venue_address`.
125. **Ready calls for matcha and panini, started at the order.** Staff scan
     the pass when someone **orders** and tap Matcha or Panini; the order
     joins a waiting list; one tap on it when it's ready sends a Telegram
     message. Scanning when the food is ready would not work — by then the
     person has walked off, which is why they are being called. These are
     paid extras from Loft, not pass items, so an order is not a claim and
     the once-only rule does not apply. This brings back, in a new shape,
     the Call removed in decision 60. The heat press can be added later as
     one line.
126. **The console is two front doors: Mobile and Laptop.** Mobile is for
     phones — Booth, Orders, the game, and looking someone up; Laptop is the
     admin password and everything, as before. **One phone PIN**: anyone
     signed in on a phone can run the game, solution included — the
     organiser chose this knowingly over keeping the GM behind its own PIN.
     On the server there is one `mobile` role; the old `staff` and `gm`
     names still sign in as it, and **either the staff PIN or the GM PIN
     works**, so no PIN stops working two days before the event. What only
     an admin could do — receipts, payments, overrides, settings — is still
     laptop only.

### 22 Sep (evening) — the empty card, plain Settings, the phone by message, two photos (organiser-directed)

**Status:** all four built 22 Sep; not yet on a phone. §8 has what was
verified and what the organiser does next.

127. **Up next with nothing booked is the same card, saying "None".** It
     was a disabled paragraph ("Nothing in the diary yet…") you could not
     tap. It is now always the live card: UP NEXT, **None** where the time
     goes, **Book something!** where the room goes, Open it →. It opens Your
     bookings and grows into it exactly like the booked card; the top of Your
     bookings always carries the same three pieces (it used to switch to a
     "Your Bookings" heading when empty, leaving the words nowhere to land),
     then the two outlined room cards. `upNextWords()` / `upNextCard()` in
     `index.html`; `morphFor` no longer needs a booking.
128. **The pass and jam photographs are new, and keep their colours.** The
     organiser supplied both (the pastry counter under The Yard's chalkboard;
     the instruments on the rugs), 1600×1000 with the subject centred; saved
     at 1400×875, JPEG, about 190 and 240 KB. Their words: *"you don't have
     to change the colours … try the halftone, just don't make it so
     intense."* So `.shot-pass` and `.shot-jam` drop the greyscale-and-tint
     treatment and get a fainter dot screen; the escape room's photo keeps
     the dark one. The old files are in `design\old-shots\`. Photo addresses
     now carry `?v=<file time>` (`app.available_shots`), so a replaced file
     shows at once rather than from Telegram's cache. Side fix: the design
     file embedded the photographs but never showed them (its recorded
     answers list none); `build_design_file.py` now points the screens at
     them.
129. **Settings say what they do, one control per idea.** The organiser's
     words: *"I don't get what event day mode means or what test clock
     means."* Their own fix, and the rule for the rest: a switch between
     **Real time** and **Test time**, and a slider for the test time, dimmed
     on Real time; then *"the way I made it simpler for the timer is the type
     of simple I want"* — it need not be a switch and a slider, it has to be
     plain. Read as: one control per idea; no setting whose help explains
     another; no number that secretly means "off"; what doesn't apply right
     now is dimmed; a two- or three-way choice shows every option. Rows that
     were already plain were left alone (the organiser: *"DO NOT change
     things that are not sensible"*).
     - **Clock.** `event_day_mode` is gone. Its three jobs were forcing the
       test clock off (one switch cannot contradict itself), allowing the
       doors-open message and allowing last call — both now have their own
       Off / On (`doors_message`, `last_call`, default on; they go out on the
       24th in real time only). **Test time now means the event day** at the
       chosen minute (`app.open_db`), where it used to be *today* at that
       minute and so could never open a 24 Sep game; it still stands still
       until the slider moves. The slider runs from an hour before the
       doors-open message to an hour after close, one minute a step, with
       −1 / +1 buttons. **Test time is global**: every attendee sees it.
     - **Stock** is Counted / Not counted plus the number (0 still means not
       counted on the server; the screen no longer asks anyone to know
       that). Low-stock and "when stock runs out" dim while nothing is
       counted; the latter is now Warn only / Block the hand-over.
     - **Who gets messages** shows the test account by name: Only
       @maxi_muslim (testing) / Everyone / Nobody.
     - **Phone opens** (When the GM presses Start / At the booked time) and
       **Phone in the app** (On / Off — desk handset only) show both options.
     - **Biggest group one person can book** moved from Bot messages to
       Escape room, the only room that uses it.
     - The top bar says **Real time** or **Test time 7:30 PM**, and the red
       banner says which day and time the app thinks it is. Both now follow a
       save at once (they used to wait for the next sign-in).
     Left alone: opening hours, venue text, game times, cutoffs, hint and
     merge times, the jam settings, the gate, "Hand-over needs payment",
     rate limits, backups.

     **Found while building, and acted on with the organiser's go-ahead.**
     The organiser's `app.py` runs with `debug=True`, so it **reloads itself
     whenever a code file is saved** — at 13:50 on 22 Sep it picked up the new
     `config.py`, which added `doors_message` and `last_call` to the real
     database and removed `event_day_mode`. The test clock had been left on
     since 21 Sep at 19:30; under the new meaning the live app told every
     attendee it was 24 Sep 7:30 PM, so earlier games read as past. At the
     organiser's instruction the Clock was set back to Real time at 14:07
     through `admin.save_settings` (audited, before/after). The organiser
     then chose to stop `app.py` for the rest of the build.
130. **Everyone in the game has the phone, and it arrives only as a bot
     message.** The organiser: *"let everyone that is in that escape room slot
     have access to the phone … The only way to access the phone should be
     when it is the person's escape room slot and when the bot sends them a
     message with the button to open the phone … give them around 25 mins …
     so that once they run out of time it doesn't immediately make them lose
     access."* This changes §9 r21 at their instruction (BUILD_SPEC records
     it).
     - **The rule** (`game.phone_access`): the desk-half check is gone; the
       halves still decide who starts in the flat and who at the desk, and the
       GM still swaps and evens them. **`phone_minutes` = 25** replaces
       `relock_minutes` (2 after the end): the phone is open from the start
       until 25 minutes later, pushed back by pauses (one in progress too) and
       the GM's +1 minutes. **End no longer locks it**; **Lock phone** still
       does, at once. `PHONE_NOT_YOUR_HALF` is no longer returned.
     - **The message** (`notify.text_phone`, kind `phone_open`, `go=phone`,
       button "📱 Open the phone" via `notify.BUTTON_LABELS`): sent to every
       booked player the moment the phone opens — the GM's Start, Unlock or
       switching the in-app phone back on (`game._send_phone` after every GM
       press), or the booked time in "At the booked time" mode
       (`game.send_phone_for_started_games`, called from
       `notify.schedule_due`, so `bot.py` must be running). Once per booking
       (`dedupe_key phone:<booking id>`). Not sent while the phone is off or
       locked. It is stamped with the **real** clock and expires after the
       real time left, because the game may be on test time while the outbox
       never is. No schema change: the label comes from `go`.
     - **The Mini App**: the phone card is gone from the escape board; the
       premise says everyone gets his phone by message. A new `phone` screen,
       reached **only** by `?go=phone` (or the `phone` start parameter),
       opens the phone at once after Start and keeps "Open the phone", the
       minutes left and the §9 r23 browser link behind it, or says why not.
       The ticket gains a "His phone — On Telegram, when the game starts" row
       and, for someone we can't message, an **Allow messages** button,
       because for them the phone would never arrive. Home's Allow line says
       so too. Help's phone answer points at the message and reads the 25
       from the server (`event.phone_minutes`).
     - **The GM console** says "Phone open until 7:55" and "Start unlocks the
       phone and messages it to everyone in this game"; End's confirmation
       says the phone stays open until the lock time; each player shows
       **Phone sent / on its way / Can't reach — desk handset / Not sent
       (test mode)**, with one line naming anyone it can't reach
       (`game.state` → `halves[].phone_msg`).
     - **Why not a token in the link**: the server re-checks the rule on every
       open (booked in this game, inside the window, checked in), so a
       `?go=phone` address in anyone else's hands opens nothing. Nothing in
       the app links there, which is what "not accessible anywhere else"
       needs.
     - **The risk it brings**, said plainly to the organiser: the phone now
       depends on `bot.py` running, **Who gets messages = Everyone**, and each
       player being reachable. The GM's markers show who isn't; the desk
       handset and sharing within the group are the fallbacks.
     - Dry-run on a scratch copy of the real database (22 Sep): the one real
       booking (@maxi_muslim, flat half, 7:50 PM) was locked before Start,
       got one message with the phone button at Start, had the phone at 2,
       16 (after End) and 24 minutes, and was locked at 26.
131. **The event is 3–10 PM, and both rooms open with it.** The organiser:
     *"Change the time to 3-10pm on everything"*, then, asked whether the
     rooms should start earlier too: rooms from 3 PM. Defaults in
     `config.py`: `doors_open` 15:00, `first_game` 15:30 (half an hour after
     doors, as before), `jam_first` 15:00; `doors_message_at` 13:00 — at
     15:00 it would have fallen on the doors themselves and never been sent,
     so it keeps its two hours' notice. Close, last game and last jam slot
     are unchanged. **19 games (228 seats) and 14 jam slots**, up from 13
     and 10. All the time rows were still owned by `system`, so the live
     database followed on `app.py`'s reload, and `manage.py generate-slots`
     was run on it at 15:3x on 22 Sep (dry-run first on a scratch copy):
     6 games and 4 jam slots added, nothing removed or moved, the one jam
     booking untouched. Everything that prints the hours reads Settings; the
     two hard-coded spots (the Start screen's fallback, the `notify-test`
     sample) and `generate-slots`' "you should see" line now follow Settings
     or say 3–10 PM.
     **Found at the same time:** `tests/test_receipts.py` read the real clock,
     so all 13 of its tests began failing at 15:26 on 22 Sep, when the first
     real Paperform link expired. Pinned to `conftest.TEST_NOW` like
     decision 90; no service code changed. **And the real one:** none of the
     152 Paperform receipts on the list had been saved to the laptop at
     15:36 — 3 links already dead, the next dying at 17:06 on 22 Sep. Told
     to the organiser to run `manage.py fetch-receipts` at once.

### 22 Sep (late) — the organiser's price list, the pass, a floorplan, the bot's voice (organiser-directed)

**Status: built and live at 17:55 on 22 Sep** (built in a copy of the project
while `app.py` kept running, at the organiser's choice, then copied in at
once; `bot.py` still needs a restart). §8 has what was verified.

132. **The organiser's list is the source of truth for what is included and
     what it costs.** Their words: *"This is now the single source of truth,
     all details and prices are here."* What follows from it:
     - **The pass holds three things** (`config.ITEMS`): **Pastry**, **Photo
       Strip** (the first; more are $2), **Vinyl Making**. The pastry is one
       item in four kinds — Mini Tart, Mini Brownie, Mini Cookie, Shiopan
       (`config.ITEM_CHOICES`). The organiser chose *"one treat, their pick"*
       over a pastry *and* a shiopan. The booth shows one button per kind, so
       the tap that hands it over records which (`claims.variant`, a column
       that already existed); a made-up kind is refused, none at all is
       accepted (an older booth tab). Overview's Pastry card lists how many
       of each kind went, so whoever restocks knows what to bring out;
       exports say "Pastry (Mini Tart)". Stock stays one number for all
       pastries. `vinyl_stock` joins the stock rows.
     - **The circle before each pass item is gone.** *"It makes it seem like
       a button when it is not."* Each item has a line under its name instead
       (the kinds; "Your first strip"); a collected pastry says which kind.
     - **Help has a price list** — the first question, *"Is there a price
       list?"* — with only what costs money: included things are under
       Included with entry, which gains **Board Games**. It is one Settings
       row, `price_list`, plain text in the organiser's own format (a line
       with `$` is a row, any other line a heading; bullets ignored),
       parsed by `services/prices.py`, shown in a multi-line box on Settings.
       `paid_extras` no longer names Loft and Crib, which are not on the
       floorplan.
     - **Only one Help question open at a time.** Opening one closes the
       rest (`name` on `<details>`, and a `toggle` handler for older
       webviews).
     - **A Floorplan screen** (`VIEWS.floorplan`, `static/floorplan.png`,
       `event.floorplan`), row 04 on Home (Help is 05) and a "See the
       floorplan" button in Help. The map is wider than a phone, so Zoom in
       shows it at 220% to drag around; a drag on the zoomed map never starts
       the back swipe. Two lines under it tie the app's names to the map's.
       **The escape room is not on the organiser's floorplan** — asked, not
       guessed.
     - **Places are Settings rows**: `escape_meet` ("the escape room
       entrance") on the ticket and in messages; `jam_room` ("Heaven 2", the
       jamming room's name) on the jam ticket and in messages. `order_pickup`
       is replaced by one row per made-to-order item, `<item>_pickup`:
       **matcha at Two Goose** (the floorplan's stall; "2 goose matcha" is on
       the chalkboard in the pass photograph) and **panini at Shiopan
       Paninis**. The organiser: the redeemables are collected together, the
       panini elsewhere, the matcha from a vendor. The console builds these
       rows from the server's order list, as its Orders screen does, so the
       page still names no order item (a test guards that).
     - **The bot speaks in a relaxed voice**, after the organiser's own
       example (*"🔔 order #128 is ready / please collect the following at
       the bakes station:"*): lower-case headings, time and place still a
       line each, a list with no bullets, no "free with entry". The order
       message follows the example exactly, without the quantity (*"No need
       for the 2x"*). `/start`, `/pass`, `/help`, `/actor` and the gate
       refusals too; the gate keeps its meaning, only the tone changed
       (§11's "same wording as the gate" is relaxed on purpose). The actor's
       hint line is now escaped — it was sent as HTML unescaped.
133. **Escape games run 3:05 to 9:45 PM, the last ending with the doors.**
     *"Make it so that every slot is until 10pm so we maximise the time."*
     Offered three ways; the organiser chose the most games: `first_game`
     15:05, `last_game` 21:45 — **21 games, 252 seats** (was 19 and 228 from
     3:30). The jam room already ran to 10 PM (last slot 9:30–10:00) and is
     unchanged. No escape game was booked, so nothing moved under anyone:
     dry-run on a scratch copy, then `manage.py generate-slots` on the live
     database at 17:56 — 21 added, 19 removed (5 of those retired, not
     deleted: test bookings once used them), the one jam booking untouched.
     The first game now starts five minutes after the doors, so the GM and
     actor are needed from 3:05.
134. **The code goes to a private GitHub repository, for a real server.**
     The organiser wants a friend to host it instead of ngrok. `.gitignore`
     keeps out `.env`, `data/`, `imports/`, `private/receipts/`, every
     `.xlsx` (the sign-up export has names and emails) and the design file
     built from it. `DEPLOY.md` is for that friend: one web process (waitress,
     threads), one `bot.py`, SQLite on a persistent disk, HTTPS, Caddy and
     systemd, and a cutover that copies `data/app.db` with both laptop
     processes stopped. **The repository must be private**: it still holds
     the solution and attendees' Telegram usernames in the tests.
     `scripts/record_answers.py` finds its own folder now instead of a
     hard-coded `C:\Users\endrw\my-mini-app`.

### 23 Sep — two counters, one name for the front desk, a map you can pinch (organiser-directed)

**Status: built and live at 18:45 on 22 Sep** (dated 23 Sep in the
organiser's next round of notes; built in a copy while `app.py` stayed up).

135. **Opening the app and being at the event are two different counts.**
     The organiser believed linking a Telegram account already counted as a
     check-in. It never has — only the booth's Check in sets `checked_in_at`
     (`claims.check_in`), and nothing else writes it — but the count they
     wanted did not exist at all. Overview now shows both:
     - **Opened the app** — active, non-test people with a `tg_user_id`: they
       started the bot or opened the Mini App, whenever that was.
     - **At the event** — people whose check-in is stamped **at or after the
       doors open on the event day** (`notify.event_local(doors_open)`, 3 PM
       on the 24th). A rehearsal check-in today is counted separately and
       named in the card's own line ("1 before that, not counted"), so it
       never inflates the headcount on the night. Nothing is blocked before
       3 PM: staff can still check people in, it simply doesn't count as
       being there yet. The rule follows the `doors_open` Setting, so moving
       the doors moves the counter.
     The Overview strapline now reads "N signed up, N opened the app, N at
     the event", and the console looks stats up **by label** rather than by
     position, because the list grows. Real numbers when it went live: 168
     signed up, 5 opened the app, 0 at the event.
136. **One name for the desk: "the front desk".** The organiser chose it over
     the floorplan's "Registration". The app already said it everywhere; the
     Settings row's label was "Help desk" and is now **Front desk**, and the
     Floorplan screen carries a line tying the two together ("The front desk
     is marked Registration on the plan"). Left alone: "the counter", which
     is where food and prints are handed over, not the desk.
137. **The floorplan is a photo, not a zoomed page.** The organiser: Zoom in
     "kinda soft locks you on the zoomed in floor plan"; they asked for a
     fixed frame with pinch and double-tap, "like how a photo app works".
     The button is gone. The frame keeps the map's own shape (taken from the
     file, so a replacement of another size still fits) and never changes
     size; the map moves inside it on pointer events — pinch about the
     midpoint, double-tap to zoom to 2.6× on the spot you tapped or back to
     the whole map, drag to pan, wheel on a laptop. Scale is held between 1×
     and 5×, and every step is clamped to the map's own edges, measured from
     the map as drawn, so it can neither be dragged into empty space nor
     left stranded. `touch-action:none` gives the page the gesture before the
     webview takes it, and a drag on the map no longer starts the back swipe.
     Opening the screen always shows the whole plan.
     Driven in headless Edge with real touch events: double-tap 1 → 2.6,
     drag pans and the screen stays on `floorplan`, a hard drag stops exactly
     at the clamp (279 of a possible 280), pinch reaches 5×, double-tap
     returns to 1× at 0,0, no page errors.

138. **Payments are not checked at all any more, and the screenshots stay.**
     The organiser, the day before: *"make it such that we don't have to
     verify anything of the payments, but still make it so that we can see the
     screenshots"*. With 150 of 169 sign-ups still unchecked, verifying each
     one before 3 PM was not going to happen, and an unverified receipt would
     have stopped that person collecting anything.
     - **The switch.** `claim_requires` takes a third value, **`none`**:
       `claims.payment_ok` returns True for everyone, so the booth hands over
       to anyone on the list. It is a Settings row (Hand-over needs payment:
       Verified / Submitted is enough / **Not needed**), so it can be put back
       in a tap. Set live at 19:04 on 22 Sep through `admin.save_settings`,
       audited. **The default in `config.py` stays `verified`** — the safe
       setting for a fresh database, and §9 r25 stands as written for anyone
       who wants it.
     - **What it does not change.** Being on the roster still matters: someone
       inactive is still refused, because that check is not about money. The
       payment status is still recorded, still shown on the person page, and
       an admin can still verify or reject if they want to. Nothing is an
       "override" any more — there is nothing to override, so no reason is
       asked for and none is logged.
     - **The screenshots.** Still on the person page, admin-only (§9 r31).
       Because Paperform's links die 7 days after each sign-up, `manage.py
       fetch-receipts` was run at 18:55 — the first time it had ever been
       run — and saved **145 of 152**. The 7 failures are the links that had
       already expired (@bananabelles, @sharmaineangg, @t_shixuan,
       @jananabana, @bingkiat, @heidily, @feliciaandiana); those screenshots
       now exist only in Paperform's dashboard. A saved copy is served from
       the laptop and keeps working on the day with no Paperform and no wifi.
     - **The console stops nagging**: with the check off, Overview drops the
       "Payments to check" job from the queue, and the Payments card reads
       "N unchecked, N with no receipt · not needed to collect" in plain
       slate rather than red. The Mini App's "We haven't spotted your
       payment" strip is gone for the same reason — it now follows whether
       payment actually blocks them, not their payment status.
     - **And the step itself is gone** (asked for straight after, same
       evening): the person page shows no verdict card asking for a decision,
       no transaction-reference box and no Verify / No reference / Reject /
       Change verdict buttons — it says what was recorded at sign-up, that
       nothing needs checking, and where to switch it back on. The booth's
       green card says **On the list** rather than claiming "Payment
       verified" about someone nobody checked, and Help drops "You haven't
       seen my payment", which would have sent people to queue at the desk
       over something nobody is looking at. A `payment_required` flag on the
       person payload and in the `event` block drives all of it, so setting
       **Verified** brings the whole workflow back. The screenshot itself is
       untouched: same place, same admin-only rule (§9 r31).

### 23 Sep — the escape room runs itself, the victim has a name, one thing at a time

139. **The victim's phone is a home screen, not a scrolling page.** The dock
     — Phone, Messages, Photos — was the last thing in one scrolling flex
     column, so on any viewport shorter than that column it went under the
     fold. Inside Telegram's in-app browser that is every phone, and the dock
     is where the game starts. It is built the way a home screen is now: a
     scrolling middle with the widgets and the app grid, and a footer that
     does not scroll with the Search pill and the dock. The two widgets take
     `min(132px, 17vh)`, so a short screen gives their height to the apps.
     - **The file is a generated bundle**, JavaScript gzipped to one base64
       line. The markup is ordinary HTML inside a JSON string in
       `<script type="__bundler/template">`. `scripts/phone_template.py`
       decodes it, hands the markup over and encodes it back, and **refuses
       to proceed unless re-encoding the untouched string reproduces the file
       byte for byte** — the bundler writes the closing script tag escaped,
       so a plain search-and-replace would destroy it.
     - `fitPhoneFrame()` takes the **smaller** of Telegram's
       `viewportStableHeight` and `window.visualViewport.height`. Telegram's
       is the only figure that knows its own chrome; `visualViewport` is the
       only one that exists outside Telegram and the only one that shrinks
       for a keyboard.

140. **The escape room runs itself: no Start, no switch, no split.** Three
     mechanisms had each been overtaken, and each was propping up the others,
     so they went together.
     - **`in_app_phone` is gone.** It was an admin switch that answered a
       player, at their booked minute, with *"This game uses the handset at
       the desk"* — and the desk could do nothing about it. That is the
       refusal the organiser hit in rehearsal. `PHONE_OFF` now means one
       thing, and it is a fault: the phone's file is not on this laptop.
     - **Start is gone.** `game.timing()` takes the booked time as the start.
       Pause, ±1 min and End stamp it into `game_sessions.started_at` on
       first use, so a touched row still says what it always said. Forgetting
       Start used to hold a room up with the clock reading zero.
     - **The split is gone.** Since decision 130 everyone in the game gets the
       phone, which left the halves deciding only where two groups stood —
       and the app never enforced that. `_assign_halves`, `_zone`,
       `game.halves`, the `/halves` route and the A/B columns on four screens
       went. The GM card lists **who is in this game** instead: number, name,
       handle, checked in, and whether the phone's message reached them.
     - **Pausing holds the phone open.** `relock_at` is the booked time plus
       `phone_minutes` **plus whatever has been paused or added**. Sorting
       something out in the room must never be why a group loses the phone.
     - **The lock stays**, manual and off by default, moved out of the main
       button row into a quiet row with End, both behind a confirm.
     - **The script became a hint list.** `private/gm/script.json` holds
       `hints` with no times against them; nothing goes amber on a timer,
       because the game master watches the room. `game.send_cue` is
       `game.give_hint`; the cues route is now `…/hints/<key>`.
     - **One vocabulary:** `upcoming · in_progress · finished · blocked`,
       printed the same by the picker, the card and the timetable. `missed`
       is gone — with no Start, nothing can be missed. This is the "ended"
       the organiser saw on a game that was happening.
     - **Left on purpose:** `escape_bookings.zone`, `.zone_changed_by`,
       `game_sessions.halves_locked_at` and `.in_app_phone` stay in `db.py`,
       read and written by nothing. Dropping a column from a live SQLite the
       night before an event buys nothing.

141. **Adding a tester hands them the phone.** The Test group let named
     accounts open the phone at any time, but adding somebody sent them
     nothing — and the bot's message is the only way in, so a tester was left
     waiting for something that was never coming. Saving that row now messages
     **the handles just added**, and the toast says who got it; saving
     anything else on Settings sends nothing, so an unrelated edit never spams
     the group. A **Send it now** button sends again without an edit. It names
     what went wrong, too: anybody not on the roster, and anybody who has
     never sent the bot `/start`, because Telegram will not let the bot message
     them until they do. `game.send_phone_to_testers()` is the one copy of the
     logic; `manage.py phone-test` calls it. **No dedupe key on purpose** —
     `utcnow()` has only seconds in it, and running it twice in a row is
     exactly what testing looks like.

142. **The victim has a name: Kai Chen.** "His phone" and "The phone" read as
     a placeholder rather than a story. It is **Kai Chen's phone** on the
     escape screen, the ticket, the phone's own screen, Help, the bot's
     messages and the button Telegram draws; `ESCAPE_ROOM_FLOW.md` had the
     name all along. **Nothing about the phone until it is theirs**: the
     premise no longer mentions a phone arriving, and the ticket's phone row
     says *At 7:40 PM* until it is genuinely open, then *Open now*. Also
     **Up next**'s button is **Manage**, not "Open it"; **Vinyl Making** is
     **Vinyl Crafting** in `config.ITEMS`, so the pass, Home, Help, the booth
     and the stock row all follow; and the Start screen reads **Hafary
     Gallery L5** with no "The Hub @" and no **Pre-U event** chip.
     - **New:** `python manage.py reset-settings <name>…` puts named rows
       back to the `config.py` defaults, showing before and after and asking
       for YES. It is needed because `config.py` is only the *starting* text:
       a row **nobody has edited** follows the default when it changes
       (`db.seed_settings`), but one somebody has typed into never does — and
       retyping a price list into a text box on the night is not a reasonable
       thing to ask.

143. **Prices is a screen of its own, and the gelato has its name.** Taken
     from the organiser's list; **MUTED. Gelato** is the stall, so the ice
     cream and waffle is under its own name rather than a generic one.

144. **The floorplan pinches, and only pinches.** `static/floorplan.png` is
     the organiser's new plan (DIY down the left, the jamming room and two
     chill rooms, the photo booth, and Two Goose, Paninis, Pastries and
     MUTED. Gelato along the top) — same 2000×1414 shape, so the clamping is
     unchanged and `floorplan_url()` still cache-busts on the file's modified
     time. **Double-tap-to-zoom is gone**: it was a second way to do what
     pinch already does, and on a phone it fires by accident — two quick taps
     while you work out where you are, and the plan jumps to 2.6× somewhere
     you were not looking. The hint reads **Pinch to zoom**. The way to the
     escape room is a note under the plan, and the escape ticket carries a
     **Where is it?** button to it, which is the moment anybody wants it.

145. **The booth counter shows one thing at a time.** The screen stacked the
     viewfinder, the code box, the verdict, the person and the hand-over
     buttons into one scroll, and the viewfinder is a 4:3 block — so on a
     counter phone the thing somebody had just scanned a pass to find out was
     below the fold. Two states on one `.booth-body` class: **scanning**, the
     viewfinder fills the phone; **a result**, the camera is already off, so
     it shrinks to a 52px strip and everything else gets the room.
     - **What is still to collect comes first and big.** What has gone sits
       under a rule at the bottom, quiet. It used to be a red `.blocked-item`
       per item, the same size as the buttons and mixed in with them, so a
       pass with two items collected read as two errors and pushed the one
       live button to third place. A pass with nothing left says
       *"Everything on this pass has been collected."*
     - **Scan next is always under a thumb**: `position:sticky; bottom:0`
       with `padding-bottom:max(2px, env(safe-area-inset-bottom, 0px))`, so
       it clears Android's gesture bar however long the list runs.
     - **The scanning mechanism is untouched.** `startCamera`, `stopCamera`,
       `scanLocked`, `camStarting` and the jsQR loop are byte-for-byte what
       they were, and both states keep every id the camera code reaches for.
       The 17 Sep one-read-per-scan fix stands.
     - **New `scripts/render_console.mjs`**, the console's answer to
       `scripts/render_views.mjs`: 18 booth and GM states rendered in Node,
       each asserting what it must and must not contain. It caught the GM
       card reading *"0 of 6 have it"* before the booked time — a count of
       something that has not happened, which reads as a fault when it is the
       design. The count appears only once something has been sent.

146. **The organiser's last four, 23 Sep.** Wording and friction, no mechanics.
     - **The cookie is $4**, not $2.50. One line of `config.PRICE_LIST`; the
       live row was still `updated_by = 'system'`, so it followed.
     - **The pass says "Tart or cookie"** where it listed four kinds.
       **Wording only, by the organiser's decision** — `ITEM_CHOICES` keeps all
       four, so the counter still has a Mini Brownie and a Shiopan button and a
       guest who asks for one gets one. The pass just stops advertising them.
     - **The Prices screen says "Redeemables"**, not "Already yours".
     - **A Mobile sign-in is the phone PIN alone.** The name and
       "where you are" boxes are gone from the form and from `admin_login`'s
       validation. Two boxes on a counter phone, every shift, was the friction.
       Both are still *accepted* if sent, so a station that wants its name on
       its hand-overs can have it; nothing asks. **The trade is real and the
       organiser chose it:** the log keeps the role, the time and the station
       when there is one, but no longer a volunteer's name. The toolbar and the
       booth header used to read `name · something` and would have shown
       "GM · " with nothing after it, so they name the door instead —
       **Mobile** or **Laptop**.

### Endpoints added beyond §12

Recorded here and in `BUILD_SPEC.md` §12.

| Endpoint | Why |
|---|---|
| `GET /healthz` | Liveness check for the tunnel windows |
| `POST /admin/api/backup` | The RUNBOOK's "Back up now" button had no endpoint |
| `GET /admin/api/roster` | Roster screen summary: active, inactive, walk-ins, past import runs |
| `POST /api/me/messages` | The Mini App's "Allow messages" answer |
| `POST /api/escape/group`, `DELETE /api/escape/group/{handle}` | Owner adds or removes friends |
| `GET /admin/api/session` | Resume the console sign-in after a reload |
| `GET /admin/api/live` | Server-sent events: "something changed" |
| `POST /admin/api/people/{id}/unlink` | Unlink a Telegram account (reason required) |
| `POST /admin/api/gm/{slot_id}/cues/{key}` | Mark a script cue done; hint lines go to the actor |
| `POST /api/jam/bookings` | Free jam booking for a group, all or nothing (replaces `POST /api/jam/holds`) |
| `POST /api/jam/bookings/{ref}/group` | The booker adds more people to their slot |
| `DELETE /api/jam/bookings/{ref}/group/{handle}` | The booker removes someone they added |
| `POST /api/jam/bookings/{ref}/leave` | Somebody added gives up their own seat |
| `POST /admin/api/receipts/archive` | Save our own copy of every Paperform screenshot before the links expire |
| `GET /admin/api/receipts/status` | Counts and the next expiry, for the Audit screen's card |
| `GET /admin/api/receipts/{attendee_id}/file` | Serve a saved receipt, admin only (§9 r31) |
| `POST /api/escape/phone/link` | Issue a one-time link to the full-page phone (§9 r23) |
| `GET /p/{token}/` | Spend one. Outside `/api/` on purpose: it opens in the real browser, where there is no initData. Trailing slash is required so the phone's relative pictures resolve under the token |
| `GET /api/escape/assets/{name}` | A picture inside the phone, behind the same §9 r21 check as the phone itself |
| `GET /p/{token}/assets/{name}` | The same, for a phone opened through a one-time link |
| `GET /admin/api/orders`, `POST /admin/api/orders` | The matcha/panini waiting list; place an order from a pass (decision 125) |
| `POST /admin/api/orders/{id}/call`, `/collected`, `/cancel` | The one-tap "ready" message; take an order off the list |

Removed 18 Sep: `POST /admin/api/claims/call`, `POST /api/receipts`,
`GET /admin/api/receipts/{id}/file`, `POST /api/jam/holds`, the review
endpoints. New error code: `STALE_TOKEN` (403).

---

## 6. How to verify the build

```powershell
cd C:\Users\endrw\my-mini-app
venv\Scripts\activate
python -m pytest tests -q
```

**You should see** `434 passed` (takes about 15–100 seconds).

The two pages are checked separately, because pytest never runs their
JavaScript:

```powershell
node scripts\check_pages.mjs
python scripts\record_answers.py design\answers.json
node scripts\render_views.mjs design\answers.json
```

**You should see** `ok` for each page, then `OK` for 32 screen states and
`FAILURES: 0`. The second command asks the real server for real answers, so
the app must be running; the third builds every screen from them, in Node, so
a template mistake is an exception here rather than a blank screen on
somebody's phone.

Since 21 Sep, two checks run in a real browser (the laptop's Edge, headless):

```powershell
python scripts\build_design_file.py
node --experimental-websocket scripts\tap_through.mjs
node --experimental-websocket scripts\motion_frames.mjs $env:TEMP
```

**You should see** `FAILS: 0` from the first, and from the second
`after open -> view: mybookings`, `after close -> view: home`, `data-morph
left: none` and `errors: none`, with `morph-*.png` frames in the temp folder.
Neither replaces the organiser's phone (`TESTPLAN.md` A7, 28b–28c).

The suite no longer depends on today's date (decision 90). Before that fix,
every test that booked through the web API would have begun failing on 25 Sep,
which is exactly when the RUNBOOK has the organiser run it and stop if it is
not green.

The suite runs against the organiser's real Paperform export
(`context/The_Yard_Sign_Up_Responses.xlsx`), not an invented fixture, so it
exercises the float Paperform IDs, the trailing spaces in names, the
capitalised `@Mr_RishieParker`, the three rows with no receipt and the ~1,000
blank formatted rows.

- `tests/test_gate.py` — §17.1, §17.2, §17.3 and §9 rules 1–9
- `tests/test_roster_import.py` — §17.9 and §9 rules 10–14
- `tests/test_claims_concurrent.py` — §17.4 (2- and 8-thread races on a real
  WAL file, plus a two-phone race through the HTTP API), §9 rules 20, 24–28,
  32–33, the pass on `GET /api/me`, and the spoiler check on `/admin`
- `tests/test_people.py` — P0.3: search, the person page, verdicts, the
  transaction-reference race, reopen, voids by id, receipt files, gate
  denials, and a check that the real export's receipt links expire before
  the event
- `tests/test_escape_capacity.py` — §17.5 (the 13th person, all-or-nothing
  groups, halves of six), group ownership, leave vs cancel, the lock at the
  cutoff, two groups racing for the last seats, one friend in two groups at
  once, list probing, and the Mini App API end to end
- `tests/test_notify.py` — the outbox (dedupe, notify modes, blocked,
  retries, expiry, double-send guard), the reminder window, event-day
  messages, last call, and which events queue messages

- `tests/test_receipts.py` — archiving (the real export's 14 links), one dead
  link not stopping the rest, EXIF stripped, random filenames, the exact and
  look-alike layers, a blank image matching nothing, and §9 r31 on the file route
- `tests/test_phone_links.py` — §9 r23: issue, spend once, expire, re-check
  rule 21 on spend, a double tap, and the route outside Telegram
- `tests/test_error_reporting.py` — every failure answers in JSON, never HTML
- `tests/test_invariants.py` — halves after a removal, over-full games after a
  seat-count change, retired item keys, one live booking per person

The §17 pytest plan named `test_halves.py`, `test_phone_access.py`,
`test_jam_holds.py`, `test_export.py`, `test_audit.py` and `test_time.py`.
Those areas are covered, but inside existing files rather than under those
names: halves and phone access in `test_phone_and_gm.py` and
`test_invariants.py`, jam in `test_escape_capacity.py` (8 tests; "holds" no
longer exist — the room is free), exports and audit in `test_admin_screens.py`,
the clock in `test_admin_screens.py` and `test_notify.py`. Splitting them out
for the sake of the filenames would duplicate, not add.

---

## 7. Open questions for the organiser

These block nothing, but they need answers before the day.

1. ~~**Tailscale Funnel non-commercial use.**~~ **Answered 18 Sep: the
   organiser judged Funnel usable.** `RUNBOOK` Phase 14 is the setup, and it
   is theirs to do. ngrok with a fixed domain stays as the fallback.
2. **Paperform webhooks** — only on certain plans. The upload path works either
   way and stays the safety net (§10).
3. **Three Settings placeholders** remain: GM and actor handles, the
   finder's name. Stock counts (pastries, photo strips, vinyl) are 0, meaning
   not counted, until someone sets them on the Settings screen. (The photo
   strip question is answered: it is tracked, decision 68.)
4. **The phone file's pictures.** Confirmed 18 Sep: the organiser will supply
   them later, and asked for the mechanism to be built first (decision 95).
   It is. They go in `private\phone\assets\` under the exact names the phone
   asks for, listed in the README there and by `python manage.py
   phone-images`. **Five are required** — `cam-01-kitchen-2215.jpg`,
   `cam-02-hallway-2220.jpg`, `cam-03-hallway-2223.jpg`,
   `cam-04-kitchen-2227.jpg`, `ryan-bank-screenshot.jpg` — and seventeen
   `filler-NN.jpg` camera-roll shots are optional. Anything missing serves a
   grey tile, so the whole game can be rehearsed before the photographs exist.
5. ~~**"Call matcha".**~~ Built 17 Sep, removed 18 Sep (decision 60).
9. ~~**Halves and friends.**~~ **Answered 18 Sep: "NO, as much as possible try
   to group them together."** The organiser did not want friends who booked
   together split up. Built as decision 93 — groups are kept whole whenever
   another group can fill the other half, and split only when there is no
   alternative. See that decision for the one case where a split is still
   unavoidable and why.
10. **When to switch messages on.** Run `python manage.py notify on` once
    testing is done, and before 24 Sep. Until then, attendees get no
    reminders.
6. ~~**Low-stock threshold.**~~ **Answered 18 Sep.** The organiser asked
   whether they could change it on the Settings screen. They could not — it
   was a constant in `config.py` — so it was made a Settings row,
   `low_stock_at`, starting at 5 (decision 94).
7. ~~**Only `@maxi_muslim` is verified.**~~ **Answered 22 Sep (decision
   138): payments are not checked at all.** "Hand-over needs payment" is set
   to **Not needed**, so the 150 unchecked and 12 receipt-less sign-ups can
   all collect. The screenshots are still on each person page, and the switch
   goes back to Verified in a tap.
8. **Paperform receipt links expire before the event.** Found 17 Sep: the 14
   links in the imported export are signed links, and each `expires=` is
   **exactly 7 days after that person's "Submitted At"**. The first dies
   22 Sep 15:26 and the last 23 Sep 17:42, Singapore time, before 24 Sep.
   After that, the person page's "Open" fails; the page says the link has
   expired. **Not known:** whether a fresh Paperform export gives fresh links.
   The dates suggest the expiry is tied to the submission, not the export.
   **Fixed 18 Sep (decision 85):** the lasting fix — saving a copy of each
   receipt on the laptop — is built. `python manage.py fetch-receipts`, or
   **Save receipt copies** on the Audit screen. **Run at last on 22 Sep,
   18:55: 145 of 152 saved** (decision 138). The 7 whose links had already
   died could not be copied and are only in Paperform's dashboard now.
   Side finding: the
   exact 7-day match suggests "Submitted At" is Singapore time (§9 r10 calls
   it unknown). Nothing relies on that yet.

---

## 8. Next step — `TESTPLAN.md` Part A, and the 22 Sep receipt deadline

### BUILT 23 Sep: the escape room runs itself; the booth shows one thing at a time (decisions 139–145)

Seven changes, all committed and none yet on a phone. The escape room has no
Start, no `in_app_phone` switch and no split: a game begins at its booked
minute and **Kai Chen's phone** opens then, for everyone in it, and a pause
holds it open for as long as the pause. The GM console lists who is in the
game and whether the bot's message reached them, gives hints with no timer
against them, and prints one vocabulary — `upcoming · in_progress ·
finished · blocked` — in the picker, the card and the timetable. Adding
somebody to the Test group now sends them the phone. The booth counter is two
states instead of one scroll, with the scanning mechanism byte-for-byte
unchanged. The floorplan is the organiser's new plan and pinches only.

**539 tests pass** (7 that were failing on `main`, describing behaviour
replaced on 22–24 Sep and never re-asserted, are fixed rather than left).
`node --check` passes on both page scripts; `scripts/render_views.mjs` and the
new `scripts/render_console.mjs` render every screen state with no failures.

**Next:** the organiser rehearses one game on test time — the phone opens at
the booked minute with nothing pressed, the picker says **In progress**, a
pause holds the phone open — then scans a pass on the counter phone and
checks the verdict and the hand-over buttons are on screen without scrolling,
with **Scan the next pass** above the gesture bar.

### LIVE 22 Sep, 19:04: no payment checking; the receipts are being saved (decision 138)

**Hand-over needs payment = Not needed**, live and audited: anyone on the list
collects, whatever their payment says. The payment status, the verify/reject
buttons and the screenshots are all still there — `manage.py fetch-receipts`
ran at 18:55–19:20 and saved **145 of 152** payment screenshots onto the
laptop (none had ever been saved; the 7 that failed are the ones whose
Paperform links had already expired, named in `CHANGELOG.md`). **434 tests
pass.** The repository at github.com/endrwy-code/TheYard was **public** when
found — the organiser is making it private before the next push.

### LIVE 22 Sep, 18:45: two counters, the front desk, a pinchable map (decisions 135–137)

Overview counts **Opened the app** and **At the event** separately, the second
only from the doors on the 24th; the Settings row is **Front desk** and the
Floorplan says it is Registration on the plan; the map is a fixed frame you
pinch, double-tap and drag. **432 tests pass** (two new: the two counters, and
the counter following the doors Setting); 32 screen states render; the
gestures were driven with real touch events in headless Edge. Still to try on
a phone, and **`bot.py` still needs its restart** (below).

### LIVE 22 Sep, 17:55: pass, prices, floorplan, games to 9:45, the bot's voice (decisions 132–134)

Verified: **430 tests pass** (428 + the pastry-kind claim and the price-list
format); both pages pass `check_pages.mjs`; **33** Mini App screen states
render with `FAILURES: 0` (new: floorplan, zoomed floorplan, a collected
pastry; checks that the circle and "escape-room door" are gone); the design
file has 23 states and was screenshotted at 390px with device emulation
(`--window-size` alone can't go below ~500px). Every bot message was printed
and read. The live app reloaded cleanly at 17:55 and `/healthz` answered;
Settings followed on reload; `generate-slots` rebuilt the games (133).
**Not yet on a real phone, and `bot.py` is still running the old copy.**

What the organiser does next:
1. **Restart `bot.py`** (close its window; `cd`, activate, `python bot.py`).
   Until then `/start`, `/pass`, `/help` and the timed messages (reminders,
   doors-open, last call) use the old wording; messages the web process
   queues (bookings, orders, the phone) are already new.
2. On a phone: Home → Floorplan (pinch and double-tap it); The Yard Pass
   (three items, no circles); Help → Is there a price list? (then open
   another question — the first closes).
3. Booth on the Mobile console: scan a pass, hand over a pastry by kind;
   Overview's Pastry card shows it.
4. `python manage.py notify-test maxi_muslim` — every message in the new voice.
5. GitHub: install Git, create a **private** repository, push (steps in the
   22 Sep chat; `DEPLOY.md` is for the friend who hosts it).

### DONE 22 Sep, 15:40: 3–10 PM (decision 131)

Live now: Settings say doors 3 PM, and the real timetable has 19 games from
3:30 and 14 jam slots from 3:00 (`generate-slots` run). 428 tests pass; 30
screen states render. **Urgent for the organiser: `python manage.py
fetch-receipts`** — 0 of 152 receipts saved, next link dies 17:06 today.

### BUILT 22 Sep (evening): empty Up next, photos, plain Settings, the phone by message

Status: decisions 127–130 are all built. **428 tests pass** (the ones that
changed did so on purpose: the phone for everyone, 25 minutes, End not
locking, event-day mode gone). Both pages pass `check_pages.mjs`; **30**
Mini App screen states render with `FAILURES: 0` (new: six phone-screen
states and a ticket for someone we can't message); tap-through `FAILS: 0`;
the empty card's grow captured frame by frame; the design-file round trip is
byte-identical. Settings and the whole phone flow were driven against a
**scratch copy** of the real database (never `data\app.db`): Test time on
the 24th, GM Start, one message per player with the "📱 Open the phone"
button, open after End, locked at 26 minutes. A Node run of the page's own
script confirms `?go=phone` → Start → the phone screen, Home behind it, the
phone opening by itself. **Not yet on a real phone or through the real bot.**

**`app.py` is stopped** (the organiser closed it at 14:12 so edits would not
go live mid-build — see 129 for why). The live clock was set back to Real
time at 14:07.

What the organiser does next:
1. **Start `app.py` again** — on start it replaces `relock_minutes` with
   `phone_minutes` (25) in the real database. **Start `bot.py` too**: it
   wasn't running, and the phone now reaches players only through it.
2. Settings: check **Clock** reads Real time, and look over the new rows.
3. `python manage.py notify-test maxi_muslim` — the new phone message is in
   the set, with its **📱 Open the phone** button.
4. `TESTPLAN.md` **A5** (rewritten: the phone by message, on test time).
5. Before the night: **Who gets messages → Everyone**, or players never get
   the phone.

Left on purpose: no token in the phone link (the server's check is the lock,
decision 130); hint and merge times stay typed; the bot's own timed messages
(reminders, the phone in "At the booked time" mode) run on the real clock,
so test the phone message with the GM's Start.

### BUILT 22 Sep: pass name, capitals, Help, orders, Mobile and Laptop

Status: decisions 122–126 are built. **408 tests pass** (12 new, in
`tests/test_orders.py` and the sign-in tests; the tests that changed did so
because the behaviour changed on purpose — phones run the game, either phone
PIN works, audit rows say `mobile`). Both pages pass `check_pages.mjs`; the
Mini App's 23 screen states render with `FAILURES: 0`. The Mini App screens
were screenshotted in headless Edge after the capitals change. The console
was driven at phone width against a **throwaway copy of the app on a scratch
database** (never `data\app.db`): Mobile sign-in, the four-tab nav, taking an
order by code, placing it, calling it, the game screen — no page errors.
**Not yet on a real phone, and the camera scan on the Orders screen has not
been tried at all** (headless Edge has no camera).

What the organiser must do, because the running `app.py` has the old code:
1. **Restart `app.py`** — on start it adds the `orders` table and updates the
   venue setting (it still followed the code, so it takes the new name) and
   adds `venue_address` and `order_pickup`.
2. **Restart `bot.py`** — for the new `/pass` wording.
3. `TESTPLAN.md` A2 step 7–7b, A3 step 8, and **A3b** (orders and the ready
   call) on your phone.
4. Before the night: `python manage.py notify on`, or the "ready" message only
   reaches test accounts (the Orders screen says so while it's off).

Left on purpose: the heat press is not in `ORDER_ITEMS` (one line to add);
the Mini App does not show order status itself — the Telegram message is the
channel, because the Mini App doesn't poll (§3 r6); the admin console keeps its
own capitals style.

### BUILT 21 Sep (afternoon): the UI pass — waiting on the organiser's phone

Status: decisions 115–121 are built in `templates/index.html`. **396 tests
pass** (one new: `test_the_card_morph_never_fades`, proved by breaking it two
ways on a copy); 23 screen states render with `FAILURES: 0`; the design-file
round trip is byte-identical; `tap_through.mjs` passes all 17 steps; and
`motion_frames.mjs` shows the card growing and shrinking with no page errors.
All of that is headless Edge at 500px. **None of it has been on a phone in
Telegram yet**, and the grow is exactly the kind of thing only a phone can
judge (README, "Before you say something is fixed").

The organiser's next steps:
1. Restart `app.py` (the page is served fresh on each open, but a restart
   rules out an old copy — see RUNBOOK Phase 18).
2. **`TESTPLAN.md` A4 step 11 and A7 steps 28b and 28c** on your own phone.
   If the grow misbehaves, `MORPH = false` (RUNBOOK Phase 18) and carry on.
3. Then Part B as planned — the screens are now as they will be on the night.

Left on purpose: no names on the jam booking page's **Taken** rows — the jam
board's API sends which instruments are free, not who holds them, and adding
that is a server change three days out. The ticket shows the whole room with
names once booked.

### BUILT 18 Sep (morning): the roster fix, receipts, phone links, invariants

Status: **392 tests pass**; both pages pass `scripts/check_pages.mjs`; the app
boots and serves both pages with every change in place. Decisions 81–92.
Nothing in the spec is left unbuilt except the Paperform webhook, which depends
on a plan the organiser may not have.

**Still not tried on a phone or with real Telegram.** That is now the whole of
the remaining risk, and `TESTPLAN.md` is how it gets closed.

The organiser's next steps, in order:
1. **Restart `app.py`** — it adds the `phone_tickets` table and the
   `private\receipts` folder on start.
2. **Re-do the roster import.** The stored preview (run 3) was worked out under
   the old, buggy logic, so it still plans `@maxi_muslim` as a new person and
   will be refused by name. Upload the file again and commit the fresh preview.
   Expect 15 new, 1 changed (them), 0 missing.
3. ~~**`python manage.py fetch-receipts`**~~ — **done 22 Sep, 18:55: 145 of
   152 saved**; the other 7 links had already died (decision 138).
4. **`TESTPLAN.md` Part A** — alone, one phone, about 30 minutes.
5. **Fill in Settings**: GM and actor handles, the finder's name, stock counts.
6. **`TESTPLAN.md` Part B** — book it for 21 or 22 Sep, not the 23rd.
7. Before the day: `python manage.py notify on`; event-day mode on.

Known limits: the Mini App doesn't live-update; the console's own layout was
repaired and
re-typed but not redesigned.

### BUILT 18 Sep: the organiser's source of truth

Status: built, 236 tests pass, both page scripts pass `node --check`, the
Mini App's booking flows were rendered in Node against recorded real server
answers. Not yet on a phone. Decisions 58–67 in §5.

**The organiser must run once** (RUNBOOK Phase 13c, step 0): restart
`app.py` (the settings sync runs on start); `python manage.py cancel-group
maxi_muslim "test booking"`; `python manage.py generate-slots` (removes the
9:50 PM game, adds 10 jam slots); re-verify @skibadena on People; start
`bot.py` from the project folder with the venv.

As first written:

The organiser gave corrected event details, which replace the brief where
they differ:

- **Thu 24 Sep, 5–10 PM, "@ Hub @ L5 Hafary".** Entry is $12 ($10 early bird
  until 20 Sep 23:59), paid outside the app.
- **Included in entry:** a cookie/pastry, a canned drink, the jamming studio,
  *(as stated 17 Sep; the drink was dropped on 19 Sep — decision 101)*
  the escape room, 1 free photo strip, and board games.
- **Paid extras** (DIY in Crib, food at Loft, the photobooth): bought at the
  front desk, **never in the app**.

Decisions taken (with reasons in §5 once built):
1. The once-only items become **pastry** and **drink** (were matcha and
   panini). The item list lives in one place (`config.ITEMS`); the UIs read it
   from the server.
2. **The booth "Call" button and its message are removed.** Pastries and
   canned drinks are grab-and-go, so there is nothing to "call".
3. **The jam room is free**: book and it is confirmed. No PayNow, holds,
   receipts or review queue. The console's Reviews screen and all jam payment
   code are removed.
4. **No receipt uploads in the app.** People without a verified payment are
   sent to the front desk. The Mini App's (mock) Upload button is removed.
5. **Closing is 10 PM**, so the last escape game is 9:30 PM (13 games, 156
   seats), and last call is 9:30 PM.
6. Bookers get a clear "You're booked" confirmation, plus a Telegram receipt.
7. The console keeps you signed in across a page reload, and the person
   page refreshes itself every 30 s while visible.

Found while checking the organiser's test (17 Sep, ~23:00 SGT):
- `bot.py` was never started (the PowerShell window was in `C:\Users\endrw`,
  not the project, and used the system Python). 4 Call and 5 friend-added
  messages sat queued. `bot.py` itself starts fine (checked with a fake
  token).
- The test left **6 real bookings** on the 8:10 PM game (@maxi_muslim plus
  @skibadena, @aalexiaho, @t_shixuan, @bananabelles, @zhnlun) that must be
  removed.
- @skibadena's payment was reopened and not re-verified; the account also
  has override hand-overs from testing (under the old matcha/panini keys).

### After `TESTPLAN.md` Parts A and B are signed off

The list that stood here (Settings, P0.5, Audit, Overview, the backup timer,
GM re-balance and hint sending, walk-ins, admin block/move) was all built on
18 Sep. What remains is the organiser's: Tailscale Funnel (RUNBOOK 14), the
desk devices (15), the five phone images, and the event-day checklist (16–17).

Known limits of what was built today: tests that go through the Mini App API
use the real clock, so they assume today is before 24 Sep. After the event
they need a fixed clock.
