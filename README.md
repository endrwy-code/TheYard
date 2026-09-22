# The Yard — handoff to Claude Code

You are building the backend for a one-day event on **Thursday 24 September
2026** in Singapore. The front-end is designed, approved and finished. Your job
is the Flask app, the Telegram bot and the database behind it.

## Read these, in this order

0. **`STATE.md`** — where the build is right now: what is live, what is still
   mock, every decision taken since this handoff and why, and what the next
   step is. Start here. Keep it current: after every major decision, update
   `STATE.md`, this file, `BUILD_SPEC.md`, `RUNBOOK.md` and
   `context/PROJECT_STATUS.md` in the same pass, so the project can be handed
   to a new agent cold.
1. **`BUILD_SPEC.md`** — the whole specification. Architecture, data model,
   integrity rules, API contract, build priorities and acceptance tests. Section
   numbers (§2, §3, §7–§12) match the organiser's original brief, so a reference
   like "§9, rule 24" means something.
2. **`RUNBOOK.md`** — the organiser's own step-by-step guide. Read it so you know
   what they will be doing with what you build. Keep it accurate: if you change
   a command, a file path or what a screen shows, update the matching phase.
   Two companions to it: **`TESTPLAN.md`** is the single testing list (Part A
   alone, Part B with the crowd — RUNBOOK 13c/13d point at it), and
   **`HOW_IT_WORKS.md`** explains the five layers and which one each error
   message is really about, for when a symptom isn't in Phase 18's table.
   **`DEPLOY.md`** is for hosting it on a real server instead of the laptop.
3. **`prototypes/`** — the approved front-end, as the interactive prototypes the
   organiser signed off. Every screen, every state, every error code, plus the
   demo controls (persona switcher, clock slider, role switcher, scan and review
   simulators). These are the design contract. Open them in a browser.

## Ground rules

- **Target Python and Flask on Windows.** The organiser works in PowerShell and
  VS Code and is not a developer. Every instruction you write for them is
  numbered, copy-paste ready, uses `;` not `&&` and `venv\Scripts\activate`, and
  says what they should see afterwards.
- **Keep the existing files.** `venv\`, `.env`, the `TELEGRAM_TOKEN` key name,
  and the working `verify_telegram_data()` all stay. Extend it with an
  `auth_date` maximum-age check; don't rewrite it.
- **Ask before changing any rule in §3 or §9.** Those are the non-negotiables
  and the data-integrity rules. Everything else is yours to shape.
- **Work through the priorities in order.** P0 first, then P1, then P2. Each tier
  must work end to end before the next starts, and the organiser tests each tier
  **in Telegram** before you move on. Stop and hand back at each tier boundary.
- **Don't restyle the templates** unless the organiser asks. They're the
  approved design. (The organiser did ask on 21 Sep — `STATE.md` decisions
  115–121 — and `DESIGN.md` is the current system.)

## Before you say something is fixed

*Added 21 Sep, after the same visual fault was diagnosed, "fixed" and handed
back twice. Both fixes were real repairs to real bugs. Neither was the bug
being reported. The organiser found it both times, on their own phone, in
their own time. The full post-mortem is `STATE.md` decision 113.*

**A clean test run is not evidence about behaviour.** Everything in this
project either parses the page's code (`check_pages.mjs`), builds its markup
in a fake browser that has no screen (`render_views.mjs`), or exercises the
database (`pytest`). Not one of them can see a screen, feel a delay, or notice
that something was invisible for eighty milliseconds. So when the report is
about how the app *looks or behaves* — it flashes, it stutters, it feels slow,
it jumps, the camera fires twice — a green run tells you that you have not
broken anything else. It tells you nothing about whether you fixed the thing.
Say those two separately, and never let the first one imply the second.

**The detail that doesn't fit your explanation is the most valuable thing you
have.** The organiser reported that a *first* visit to a screen was fine and a
return visit was not. That single fact ruled out the theory being worked on,
twice, and it was written off as a curiosity both times. If any part of what
they describe is unexplained by your account of the cause, you do not have the
cause yet. Chase the part that doesn't fit, not the part that does.

**Finding a real bug is not the same as finding the reported bug.** It is easy
to go looking, turn up something genuinely broken, fix it well, and stop —
because a coherent, nameable culprit feels like an answer. Check your fix
against the words the organiser used, not against your own explanation.

**Search by behaviour, not by name.** The rule causing that fault was four
hundred lines away from the block headed "screen transitions", wasn't called a
transition, and had been there from the start. Looking where the label matches
finds the code you are thinking about, which is rarely the code at fault.

**Suspect whatever you wrote on autopilot.** The fault was the standard,
idiomatic way to write that kind of effect — chosen by reflex, never actually
decided. Code you didn't think about is code you won't think to check.

**Where to spend the extra care, and where not to.** This is a small project on
a deadline and thoroughness is not free, so it is not "verify everything". Slow
down and get hands-on evidence in three cases:

1. The report is about something none of the checks here can observe — looks,
   timing, feel, anything involving a real phone or a real camera.
2. The organiser is telling you the same thing a second time. Once is a bug
   report; twice means your model of the problem is wrong, and more of the same
   reasoning will not fix it.
3. You are about to write "fixed" about something you have not seen work.

Everywhere else, the normal loop is fine: make the change, run the checks, move
on. Most work here is backend logic that `pytest` genuinely does cover.

**If a rule matters and nothing can observe it, try asserting it as text.** The
four motion tests at the end of `tests/test_invariants.py` are the worked
example: the page's CSS can be read as text and made to prove the rule to
itself. Narrow, cheap, and it fails with the offending line named. Prove a new
guard works by reintroducing the fault on purpose and watching it fail — a
guard that has never failed has not been tested.

**Two scripts can now look at a screen** (21 Sep). Build the design file
(`python scripts\build_design_file.py`), then
`node --experimental-websocket scripts\motion_frames.mjs <folder>` saves
frames of the Up next card growing and shrinking at a tenth of its speed, and
`node --experimental-websocket scripts\tap_through.mjs` taps through the
buttons and booking controls and checks where each lands. They drive the
laptop's own Edge headlessly. They are real rendering and real clicks, which
nothing else here is — but a 500px headless Edge is still not a phone in
Telegram, so for anything about feel, the organiser's phone is the last word.

## How the front-end connects

The prototypes render from mock state that follows §12 exactly — the same
response shapes and the same error codes. Converting them into
`templates/index.html` and `templates/admin.html` means one mechanical pass per
file: lift the markup and styles as they are, and put one data layer at the top
of each:

```js
const MODE = 'mock';   // 'mock' | 'live'
```

In `mock` mode it answers from the same fixtures. In `live` mode it calls the
real endpoints with the headers from §3 and §5. Each finished file is one HTML
file with inline CSS and JS, libraries from public CDNs at pinned versions, per
§3 rule 6.

The wiring loop after that: build an endpoint → switch that call to live → the
organiser tests it in Telegram → next endpoint.

Two things the front-end deliberately does **not** do, and must never start
doing: it makes no decision the server owns (capacity, eligibility,
unlock time — it renders what the server says), and it uses device storage only
for harmless preferences, never for access or claims.

Don't change the design in that pass. Colours, type, spacing, copy and states
are approved. If something can't be carried across as-is, ask.

## The one thing that must not fail

The escape room's phone prop runs **offline on dedicated devices at the desk**.
That is the real game. The in-app phone you're building is an extra view for the
desk half of each group, and the GM can switch it off mid-event without
affecting the game at all. Never make the game depend on the server.
*Since 22 Sep (`STATE.md` 130) the in-app phone goes to **everyone** in the
game, reaches them **only** as a bot message ("📱 Open the phone"), and stays
open 25 minutes from the start. The desk devices remain the fallback for
anyone the message can't reach — which is why `bot.py` must be running and
messages set to Everyone on the night.*

Related, and equally firm: the phone's evidence photos and the game's solution
never reach an attendee screen. §3 rule 4 is the spoiler firewall — read it
before you write any escape-room endpoint.

## What's in this bundle

```
STATE.md                   where the build is right now — read first
CHANGELOG.md               dated log of features, known bugs, structure changes
BUILD_SPEC.md              the specification
RUNBOOK.md                 the organiser's guide
TESTPLAN.md                the one testing list: Part A alone, Part B with people
HOW_IT_WORKS.md            the five layers, and which one an error points at
README.md                  this file
.env.example               every key, commented
requirements.txt           pinned at install time by pip freeze
scripts/start_event.ps1    opens the three event-day windows
prototypes/                the approved front-end: Mini App, and the console
                           (overview, people, booth mode, GM console)
prototypes/assets/         the logo and the demo QR the prototypes reference
private/phone/the-phone.html   the escape-room phone file
context/                   reference material, not instructions:
                           The_Yard_Claude_Design_Prompt_v2.md  the original brief
                                                                the § numbers point at
                           PROJECT_STATUS.md   the organiser's environment and
                                               what already works
                           The_Yard_Sign_Up_Responses.xlsx  the real Paperform export
                                               — build the importer and the
                                               export-back against this file,
                                               not a description of it
                           The_Last_Guest_20min.pptx  the escape-room design doc.
                                               Source of truth for the GM console's
                                               hint lines and reset checklist.
                                               SPOILERS — gm and admin only, and
                                               never on an attendee screen (§3 rule 4)
```

## Where the build is

**Everything is built.** All nine P0 items, all of P1 except the Paperform
webhook, and the last unbuilt spec rule (§9 r23, one-time phone links) as of
18 Sep. **408 tests pass.** Nothing in either page is mock.

What remains is not building — it is **testing on real phones with real
Telegram accounts**, which has never happened for anything built on 17–18 Sep.
`TESTPLAN.md` is that list, split into a solo part and a crowd part.

Two things have dates attached:

- **22 Sep, 3:26 PM** — the first Paperform receipt link expires. Run
  `python manage.py fetch-receipts` before then or that payment can never be
  checked. All of them die before the event.
- **Before the day** — `python manage.py notify on`. Until then no real
  attendee receives any message.

`STATE.md` has the details and every decision. `CHANGELOG.md` has dated
entries for each change.

## Outstanding, and not blocking

- ~~`templates/index.html` and `templates/admin.html` are produced from
  `prototypes/`~~ — **done.** Both are built, with a `MODE` switch and a
  per-endpoint `LIVE` map so calls go live one at a time. `STATE.md` §3 lists
  which are live. The console also gained four screens the prototypes never
  drew — Schedules, Roster, Settings and Audit — and one shared top bar across
  every screen, both at the organiser's instruction. See `STATE.md` §5.
- `.env` still needs `ADMIN_PASSWORD_HASH`, `STAFF_PIN_HASH` and `GM_PIN_HASH`
  before anyone can sign in to the console (`RUNBOOK` Phase 13, step 2).
- The roster import must be **re-done**: the preview stored on 17 Sep was
  worked out under the bug fixed on 18 Sep, so it will be refused by name.
  Upload the file again and commit the fresh preview.
- The phone file still needs its five images embedded: four camera stills and
  Ryan's bank screenshot. The organiser is supplying them. Everything else about
  the phone is finished.
- A few Settings values are still placeholders — GM and actor handles, the
  finder's name, and pastry/photo-strip/vinyl stock (0 = not counted). They're rows in the
  Settings screen, so build against the defaults in `config.py` and let the
  organiser fill them in.
- **The event facts changed on 17–18 Sep** (organiser's source of truth,
  `STATE.md` decisions 58–67): 5–10 PM (3–10 PM since 22 Sep, decision 131) at @ Hub @ L5 Hafary; the jamming studio
  is free; the app takes no money. Where BUILD_SPEC disagrees, STATE wins.
- **The organiser's list of 22 Sep is the source of truth for what's included
  and what it costs** (`STATE.md` decision 132): the pass covers a pastry (Mini
  Tart, Brownie, Cookie or Shiopan — the booth records which), the first photo
  strip and vinyl crafting; everything with a price is the `price_list` Setting,
  shown on Help. Escape games run 3:05–9:45 PM (decision 133).
- **Hosting.** The code goes to a *private* GitHub repository and
  `DEPLOY.md` is the guide for moving it from the laptop + tunnel to a real
  server (decision 134). `.gitignore` keeps secrets and attendees' data out.
