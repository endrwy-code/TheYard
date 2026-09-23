# The Last Guest — the plan to get from what is built to what is written

> **Read this first**, before `ESCAPE_ROOM_FLOW.md` and `ESCAPE_ROOM_PROPOSAL.md`.
> Both are now partly out of date; this file says which parts and why.
> **Full spoilers.**
>
> Source of truth for the *story*: `CHANGES_FOR_CLAUDE_CODE.md` (the 20-minute
> rewrite) and `EVIDENCE_BRIEF.md` (every word of the phone and the paper).
> Source of truth for *what is actually in the repo, and who does what next*:
> this file. Where they disagree about the repo, this file is right, because it
> was written by reading the code.
>
> **The app runs on Render, built from GitHub.** Nothing is live until it is
> committed and pushed — see §1d and §6.
>
> Written 23 Sep. **Status, end of 23 Sep: Tiers A, B, C, D, E and F are
> done.** 583 tests pass. What is left is not code — it is the photographs
> (§3b), the printing (§3c), the props (§3d), and the two questions in §1e that
> only the organiser can answer. The finder's name (§1f) no longer blocks
> anything: it is a Settings row that the phone now reads at serve time, and
> until it is filled in he shows as an unsaved number.

---

## 0. The short version

The rewrite in `CHANGES_FOR_CLAUDE_CODE.md` is buildable. The phone can be
edited without rebuilding anything — I checked, and that was the one thing that
could have made this expensive. It is not expensive.

But the rewrite has **three gaps that stop work starting**, and it gives **one
instruction that would break a passing test**. Those are §1 and §4 below.
Everything else splits cleanly into "I do it in the repo" (§2) and "you do it
with a camera, a printer and a decision" (§3).

The honest summary of the balance of work: **my half is about a day's editing
and is low risk. Your half is the game.** Seven photographs, two bin
photographs and a stack of printed paper are now the larger part of this room,
because the rewrite deliberately moved the evidence off the phone and onto the
desk.

---

## 1. Three gaps that block the build

### 1a. `EVIDENCE_BRIEF.md` — **resolved, and now in the repository**

`CHANGES_FOR_CLAUDE_CODE.md` §6.1 says:

> The full text of every thread and every call-log row is in `EVIDENCE_BRIEF.md`
> §§2–3. Take it from there verbatim, not from the old file.

**Resolved 23 Sep.** The organiser supplied the brief and it is now saved as
`EVIDENCE_BRIEF.md` in the project root. It is the **verbatim** source for every
thread and every call-log row, exactly as §6.1 instructs — I do not paraphrase
it, and I do not fall back to §2 of the rewrite where the two differ.

`CHANGES_FOR_CLAUDE_CODE.md` was saved at the same time and for the same
reason. **Neither existed as a file before**, which meant every reference to
them in this plan, and in the comment I left in `services/game.py`, pointed at
nothing. A cold agent would have had no story at all.

**Tier A is now unblocked.** The brief is also the thing the printed suspect
statements and the warrant get checked against, so it stays in the repo as a
file rather than being absorbed into the phone markup and lost.

> **One thing to decide about these two files.** They are total spoilers — the
> brief carries the GM answer card, the lock code and every line of every
> statement. `ESCAPE_ROOM_PROPOSAL.md` was put in `.gitignore` on 23 Sep for
> exactly that reason. I have **not** gitignored the brief or the changes file,
> because doing so would be theatre: the repository already contains
> `private\gm\script.json`, `ESCAPE_ROOM_FLOW.md` and the phone file itself,
> which between them give the whole room away. Gitignoring two more documents
> does not close a door that is already open, and it *would* cost the
> portability this project is run for. The real fix is §1e.

### 1d. The app is on Render now, and that changes what "done" means

You no longer run this locally. Render builds the service from GitHub, so the
live game is a **git checkout**, and three things follow that did not apply
before:

1. **Nothing counts until it is committed and pushed.** The phone file, its
   assets and the GM script all live inside the repository. A file saved on the
   laptop and not committed does not exist for a player. This has a nasty
   failure mode: a missing picture is deliberately answered with a grey
   placeholder so the game stays playable, so **a forgotten `git push` looks
   exactly like a picture you have not shot yet**, and nothing reports an error.
   `manage.py phone-images` now checks git as well as the folder, and says
   `HERE BUT NOT LIVE` when it finds the difference.
2. **Capital letters now matter.** Render runs Linux. `ethan-bank-screenshot.jpg`
   and `Ethan-Bank-Screenshot.JPG` are two different files there and the same
   file on Windows, so a wrongly-capitalised name works perfectly on the laptop
   and shows a grey tile live.
3. **The checkout is rebuilt on every deploy.** Only `/var/yard` survives —
   the database, its backups, the payment screenshots. Anything put on the
   running server by another route is gone at the next deploy.

### 1e. Two contradictions about the live setup that only you can settle

Neither is something I can resolve by reading the code, and both change how you
should work.

**Is the repository public or private?** `DEPLOY.md` §2 states flatly: "The repo
is **private** and must stay that way". `.gitignore` opens with "Keep the
repository PRIVATE". But `ESCAPE_ROOM_PROPOSAL.md` §6b records an actual check
on 23 Sep finding that `github.com/endrwy-code/TheYard` answers an
unauthenticated request with **200**, and so do `ESCAPE_ROOM_FLOW.md` and
`private/gm/script.json` on `raw.githubusercontent.com`. **Those cannot both be
true.** One of those documents is lying to the next person who reads it, and if
it is `DEPLOY.md` then the solution is public right now. Render deploys happily
from a private repository, so making it private costs nothing.

**Is auto-deploy on or off?** You said Render auto-pulls from GitHub.
`render.yaml` says `autoDeploy: false`, deliberately, with the reasoning written
next to it. A dashboard setting overrides the blueprint, so if it was switched
on there the file is now stale and should be corrected. This matters because the
two states need opposite habits — see §6b step 6.

### 1f. The finder's name cannot reach the phone

This is new, and it came out of the brief. `EVIDENCE_BRIEF.md` §2.1 puts **the
finder in the group chat**, with the last message in the thread: *"leaving now.
home in 15. save me a slice"* at 10:22 PM. That message is load-bearing — it is
how a player knows when he set off, which is what makes Still 7 the third
independent route to the offset.

But the phone is served as a **static file**. `services/game.py:356` reads
`the-phone.html` off disk and returns it unchanged; there is no templating step
and no place to substitute a value. So the finder's name, which is a
**Settings** placeholder (`finder_name`, still empty), **cannot get onto the
phone** the way the brief assumes.

Three ways out, and it is a decision, not a detail:

- **Hard-code the name into the phone markup.** Simplest. The Settings row then
  becomes decorative and must be kept in step by hand, which is exactly the kind
  of drift that bites later.
- **Substitute at serve time.** `_phone_html()` does one string replacement of a
  placeholder token with the Settings value. Small, and it makes the Settings
  row real. My recommendation, but it is a code change you should agree to.
- **Leave him unnamed in the thread** — "save me a slice" from a number with no
  contact entry. Defensible in-world, and arguably better: an unsaved number is
  ordinary, and it keeps the name in one place.

**Resolved 23 Sep — substitute at serve time, the middle option.**
`services/game.py` now holds a `__FINDER__` token in the markup and replaces it
in `_phone_html(conn)` with the `finder_name` Setting. Two things made it the
safe choice rather than a decision worth waiting on:

- **It cannot be wrong.** Left empty, the token becomes an unsaved number,
  `+65 8712 3390`, which is exactly what an uncontacted sender looks like on a
  real phone — so the third option above is the *default behaviour* rather than
  a road not taken. Fill the Setting in and he has a name; leave it and the
  thread still reads correctly.
- **It keeps the name in one place.** The Settings row is now real, so the
  printed statements and the phone cannot drift apart, which is what
  hard-coding would have guaranteed.

The value is stripped of quotes, backslashes and angle brackets and capped at
24 characters, because it lands inside a JavaScript string.

### 1b. None of the photographs exist — and now there are ten, not five

`private\phone\assets\` contains exactly one file, `README.md`. This was already
the top blocker in `ESCAPE_ROOM_PROPOSAL.md` §6a, and the rewrite **increases**
the count while moving most of it to paper.

| | Before the rewrite | After the rewrite |
|---|---|---|
| On the phone | 4 camera stills + bank screenshot | **bank screenshot only** |
| On paper at the desk | nothing photographic | **7 stills + 2 bin photos** |

So the shoot list goes from 5 to 10 images. The good news is that only one of
them — the bank screenshot — has to be a file with an exact name in a folder.
The other nine are printed, which means they can be shot on a phone and sent to
a print shop, and no code knows or cares about them.

### 1c. The finder still has no name

`config.py:208` has `"finder_name": ""`, and it is listed in
`PLACEHOLDER_SETTINGS`. This was open in `ESCAPE_ROOM_FLOW.md` §12 and in
`ESCAPE_ROOM_PROPOSAL.md` §4d, and it is still open.

It matters more now than it did. In the new timeline the finder is
load-bearing: he arrives at 10:37, he is **Still 7**, he is one of the three
independent routes to the 20-minute offset, and he is the person who took bin
photos A and B at 10:41. He is a character with a timeline now, not a voice at
the door. He needs a name before the statements are printed, because the
statements refer to him.

---

## 2. What I change in the repo

Ordered so that each tier is testable on its own before the next starts.

### Tier A — the phone's words

**File:** `private\phone\the-phone.html`, edited **only** through
`scripts\phone_template.py`.

The important finding: **all of the phone's content is editable, and none of it
needs a rebuild.** The file looks unusable — it is a bundled artifact with 70 KB
of gzipped base64 JavaScript on one line — but I decompressed it and checked.
The compiled JavaScript contains **zero** occurrences of "Natalie", "Jasmine",
"Darren", "Ethan", "Photos" or "cam-0". Every name, every message, every
timestamp and the whole call log live in an ordinary HTML string inside
`<script type="__bundler/template">`, and `scripts\phone_template.py` exists
precisely to decode, edit and re-encode that string safely. Its `load()` refuses
to hand the markup over unless re-encoding reproduces the file byte for byte, so
a bad edit fails loudly instead of silently corrupting the phone.

What changes:

1. **Every time on the phone is rewritten to §2 of the rewrite.** Nothing on the
   phone may ever be 20 minutes out — the phone is the network, and the network
   is true.
2. **Group chat.** Add Kai's 7:40 "8pm. all of you." and his 9:20 "leave the
   cake, i'll have mine later". Re-time the arrivals to 8:00 / 8:05 / 8:10 /
   8:20. Move Darren's exit to 9:43 and Ethan's to 9:49. **Move Jasmine's
   "heading off" to 9:30** — this is her lie, and it has to be on the phone in
   her own words for the trap to close.
3. **Natalie's thread.** Add **6:47 PM, "passed your bakery. couldn't resist."**
   and **10:15 PM, "was it good? x"**. The 6:47 line is the only thing in the
   game that ties her to the walnut cake, and by rule 6 it must read as nothing
   until the cash receipt in bin photo B is found.
4. **Ethan's thread.** The current last messages say "Today 10:24 PM … 20
   minutes of my life gone". Both the time and the duration are now wrong.
5. **Call log.** Ethan's call becomes **Incoming, 9:52 PM, 16m 12s** (it is
   currently 10:06 PM, 18m 14s). This row does more work than anything else on
   the phone: it is half of the eating window, and by the boxed rule in §2 the
   window must never touch a camera.
6. **Thread list times and previews.** Each thread carries its own `time` and
   `preview` for the list view; they go stale if only the messages are changed.
7. **A coherence bug I would fix while I am in there, unless you say not to.**
   The contacts' initials do not match their names — Natalie shows **C**,
   Jasmine **Z**, Darren **A**, Ethan **R**. They are leftovers from an earlier
   set of character names (`services/game.py:365` still calls the bank
   screenshot "Ryan's"). On a phone that is pretending to be real, a contact
   whose avatar says C next to the name Natalie is the kind of detail a player
   notices, and then distrusts everything else.

### Tier B — removing Photos, and the code behind it — **DONE 23 Sep**

Cutting the Photos app was not one edit, because five other places knew it
existed. All of them are now done; 565 tests pass and the remaining phone
JavaScript passes `node --check`.

1. **The home screen tile stays, but goes dead.** The rewrite says anything that
   is not Messages or Recents shows "Cannot Connect" as before, and there is
   already a `dead` handler used by FaceTime and Calendar. So Photos becomes
   another dead tile. It should not vanish — a phone home screen with a
   Photos-shaped hole is more suspicious than one with a Photos app that will
   not open.
2. **Delete from the markup:** the whole `isPhotos` screen, the photo tab bar,
   the viewer, the drawn wall-clock overlay, the `CAMS` array, the
   `FILLER_TITLES` array, and the "Today 10:41 PM" info panel.
3. **`services/game.py`:** `STORY_IMAGES` drops from five names to one
   (`ethan-bank-screenshot.jpg`), and `FILLER_IMAGES` goes entirely.
4. **`manage.py phone-images`** currently prints "The five that carry the story"
   and counts seventeen filler photos. It becomes a check for one file. It
   should still exist — it is how you confirm the bank screenshot landed.
5. **`private\phone\assets\README.md`** is rewritten. Most of it describes
   photographs that are now printed paper.

**Kept deliberately:** the `/api/escape/assets/<name>` route, and
`MISSING_TILE`, the grey placeholder served when an image is absent. The bank
screenshot still goes through both, it still does not exist yet, and
`tests/test_phone_links.py:201` asserts the grey tile behaviour.

**Two things found while doing it, both now handled:**

- `services/game.py` named the bank screenshot **"Ryan's"** in a comment — the
  same stale cast that left the wrong initials on the contacts. Corrected.
- `tests/test_phone_at_booked_time.py` passed the literal string
  `"cam-01-kitchen-2215.jpg"` as "a valid picture name". Because `phone_image`
  checks the name **before** it checks access, that test would have started
  failing with `NOT_FOUND` instead of `NOT_YET`. It now uses
  `game.STORY_IMAGES[0]`, so it cannot go stale again. This is a fix, not a
  weakening — the assertion it makes is unchanged.

**One consequence worth knowing.** Removing the full-screen viewer removed
pinch-zoom with it. The bank screenshot was always rendered inline in the
Messages thread and never used that viewer, so nothing regressed — but it does
mean the phone's only remaining picture **cannot be opened or zoomed**, and it
is the one carrying the motive. Shoot it large and high-contrast so the
transfer amounts read at the size of a chat bubble. This is noted in
`private\phone\assets\README.md` too. If it turns out to be too small to read
on the night, the viewer can be brought back for message images alone.

### Tier C — the GM console

**File:** `private\gm\script.json`. See §4a — the rewrite's instruction here is
written against a version of this file that no longer exists, so this tier needs
your decision before I touch it.

Independent of that decision: the reset list is replaced with the eight steps in
rewrite §6.4, and **step 6 changes `1012` to `1002`**.

### Tier D — settings and the Mini App

1. **`finder_name`** gets whatever you answer to §1c.
2. **The lock code.** The rewrite §6.3 says "lock code 1002 wherever the console
   stores it". It is worth saying plainly: **the console does not store it.** The
   code exists in exactly two places, both of them prose — the reset line in
   `script.json`, and the documentation. Nothing in the app checks it, because
   the lock box is a physical box with a dial.
   I proposed making it a real Settings row. **Decided 23 Sep: no — it stays as
   prose.** So this is a straight text change, `1012` to `1002`, in the
   `script.json` reset line and across the documentation. Nothing new is built,
   and a future agent should not re-propose it without being asked.
3. **Mini App premise text** needs no rewrite, but must be checked for any
   sentence that puts photographs on the phone. If one exists, it now lies.

### Tier E — one test worth writing

Not ceremony. The clock is the game, and the rewrite's §7 is ten rules that are
each one careless edit away from silently destroying the room. A test can hold
four of them permanently:

- **No camera stamp appears anywhere on the phone.** This is the boxed rule in
  §2 — if the eating window ever derives from a camera, correcting the clock
  moves the window by the same 20 minutes, and the whole puzzle cancels out and
  does nothing. That failure is invisible to a human reader and fatal in a room.
- **The offset is uniform.** Every still's stamp minus twenty equals its real
  time, checked arithmetically against the §3 table.
- **No raw stamp falls after 10:30** (rule 3).
- **The order is preserved** under the shift (rule 4).

The existing `tests/test_phone_and_gm.py` covers access, timing and the console
thoroughly. It does not, and cannot, know whether the story is self-consistent.
This would.

### Tier F — the documentation sweep

Not optional, and not a tidy-up. The rule on this project is that a new agent
should be able to start cold from the repo. Right now a cold agent would read
`ESCAPE_ROOM_FLOW.md` and confidently build a 15-minute offset.

| File | What is now wrong |
|---|---|
| `ESCAPE_ROOM_FLOW.md` | §§1–4 and §10 superseded wholesale. §1 gives the answer as 10:12 and the code as 1012. §4 is titled "the camera clock is 15 minutes fast". §11's work list is written against the old phone |
| `ESCAPE_ROOM_PROPOSAL.md` | §3's table says lock code 1012. §6a says five photographs, which is now both the wrong number and the wrong medium. §4b's argument for making the clock unmissable is *answered* by the rewrite's three independent routes — worth saying so, rather than leaving the concern standing |
| `private\phone\assets\README.md` | Describes four camera stills and seventeen filler photos the phone will no longer ask for |
| `BUILD_SPEC.md`, `RUNBOOK.md`, `STATE.md`, `TESTPLAN.md`, `README.md`, `context\PROJECT_STATUS.md` | Each carries some of: the 15-minute offset, the code 1012, the answer 10:12, the Photos app, the five-image shoot list |
| `CHANGELOG.md` | A dated entry for the rewrite: the decision and the reasoning, not just the diff |

---

## 3. What you add

Nothing in this section is code, and none of it is something I can do for you.

### 3a. Four decisions, and the first three are quick

| # | Decision | Status | Blocks |
|---|---|---|---|
| 1 | **The finder's name** | **Still open.** A creative choice, and it goes in your Settings screen | The four statements, and §1c |
| 2 | **The brief** | **Answered 23 Sep: the organiser is sending `EVIDENCE_BRIEF.md`.** It is not written from rewrite §2; the organiser's own file is the verbatim source, as §6.1 instructs | **All of Tier A**, until it lands |
| 3 | **Make the GitHub repository private** | **Still open.** `ESCAPE_ROOM_PROPOSAL.md` §6b: the repo answers anonymous requests with 200, and it contains the killer, the code and every hint | Nothing technically. It just matters |
| 4 | **The `merge` hint question** in §4a | **Answered 23 Sep: Option 1.** Keep the five existing keys, add the merge line as a sixth, optional entry | Nothing — Tier C is unblocked |

### 3b. The shoot list — ten photographs

**One is served, nine are printed.** Corrected 23 Sep against
`EVIDENCE_BRIEF.md` §7: the nine printed ones *do* have filenames —
`still-1-hallway-2204` through `still-7-hallway-2257`, plus `bin-a-cake` and
`bin-b-epipen` — because they are generated from photographs of the real set
before they go to a print shop. What is true is that **no code ever reads
them**. They are not phone assets, they are never served, and they must not go
in `private\phone\assets\`.

They have a home now: **`private\props\`**, with a README listing all nine and
the rules for each. It is deliberately **not committed** — `still-5` shows the
killer and the oven clock that breaks the case, Render has no use for files it
never serves, and nine print-resolution images would be pushed on every deploy
for nothing. The consequence is that **they exist only on the machine that
generates them, so back them up somewhere else.**

Shoot the seven stills in one session, in the room, in the order below, because
they share a set. Per the brief: photograph the real set and the four
volunteers first, then generate from those frames, so the flat in every picture
is the flat the players are standing in.

**The stamp is printed under the frame, never inside the picture** — brief §4,
formatted exactly `HALLWAY CAM — 22:04`. A stamp burnt into the image cannot be
corrected by a player with a pen, and correcting it on the timeline board is the
whole activity.

| # | File | Shot | The thing that must be right |
|---|---|---|---|
| 1 | `still-1-hallway-2204` | Darren at the door, jacket on, hand on the latch | Caption `HALLWAY CAM — 22:04` |
| 2 | `still-2-kitchen-2208` | Jasmine and Kai at the counter | `KITCHEN CAM — 22:08`. **Two identical white boxes, closed, clearly two** |
| 3 | `still-3-hallway-2210` | Ethan leaving, phone already at his ear | `HALLWAY CAM — 22:10` |
| 4 | `still-4-hallway-2216` | Jasmine leaving, bag on her shoulder | `HALLWAY CAM — 22:16` |
| 5 | `still-5-kitchen-2222` | **Natalie alone**, back half to the camera | `KITCHEN CAM — 22:22`. Both boxes open, one plate in front of her, and **the oven clock legible at 10:02**. This one frame is the game |
| 6 | `still-6-hallway-2224` | Natalie at the door | `HALLWAY CAM — 22:24`. **A tied bin bag against the wall** |
| 7 | `still-7-hallway-2257` | The finder coming in, keys in hand | `HALLWAY CAM — 22:57` |
| A | `bin-a-cake` | The opened bag: nut-free box on its side, **whole uncut cake**, green dot and NUT FREE card legible, ordinary rubbish around it | **No timestamp at all** (rule 9) |
| B | `bin-b-epipen` | Closer, same bag: **EpiPen capped and unused**, and the crumpled **18:42 WALNUT** cash receipt | No timestamp. **No name on the receipt** (rule 6) |
| — | `ethan-bank-screenshot.jpg` | Banking app, one outgoing payment a month since May | The only one that is a **served file**, lower case, in `private\phone\assets\`, **and committed to git** |

Four practical notes that will cost you a reshoot if they are missed:

- **Still 5 is the hardest shot in the room, and everything else is insurance.**
  If the oven clock is not legible at 10:02 in the print, route 1 to the offset
  is gone. Shoot it more than once, and check it at print size rather than on a
  phone screen. Routes 2 and 3 exist precisely so a soft Still 5 does not end the
  game — but do not spend that insurance on the first shot.
- **Do not stage guilt into Still 5.** The brief is emphatic and it is right: she
  is a woman at a counter with two open boxes and a plate, and a player reading
  the raw stamp should be able to say "she's plating up after he ate" and feel
  satisfied. No hand over the bin, no glance at the camera, no cake mid-air. If
  guilt can be read off it without correcting the clock, the room has no puzzle.
- **Set the oven clock to 10:02 for shot 5, and put it back afterwards.** Rule 8
  says no working clock as set dressing, because games run in the afternoon and
  a real clock shows the afternoon. The oven clock is allowed *only* as a
  photograph.
- **Shots 2 and 5 have to agree about the boxes.** Closed and identical in 2,
  both open in 5. If the boxes look visibly different in shot 2, the answer to
  "why didn't he notice" collapses.

**The two kinds of picture must not look alike.** Stills are high-angle,
slightly wide, a little grain, fixed-camera flatness, portrait. The bin photos
are handheld, phone flash, slightly off level. They came from different devices
and should look like it.

### 3c. The print list

- **One A4 contact sheet** of stills 1–7, stamps legible.
- **One large print of Still 5.** Large enough that the oven clock reads across a
  table, because a group of four will be leaning over it at once.
- **Bin photos A and B**, printed, untimestamped.
- **Four suspect statements.** Natalie's needs the hardest edit: by rule 5 her
  clock matches the raw stamps exactly, and her lie is about *what Kai was
  doing* — she says he was already eating when she left.
- **Four suspect cards.**
- **Warrant forms** — four boxes: who, the minute, why, how. Plus a pen.

### 3d. The props

Cake boxes from one bakery, two versions, **identical but for a coloured dot
sticker** — green for nut-free, brown for walnut. A walnut coffee cake, one
slice cut, that slice half-eaten on Kai's plate. A nut-free cake to go in the bin
unopened. Darren's receipt for the nut-free one, 8:32 PM, on the counter. The
fridge card giving the 10–20 minute reaction window — **this card and the call
log are the only two things the eating window may come from.** An EpiPen case,
open and empty, on the kitchen shelf. The notebook. The will and the solicitor's
letter, in the drawer. The lock box, **scrambled, and never left reading 1002**.

---

## 4. Where the rewrite and the repository disagree

Two places. Both need you before I build the tier they sit in.

### 4a. The GM hints — the rewrite describes a file that does not exist

`CHANGES_FOR_CLAUDE_CODE.md` §6.2 says:

> Keep the keys `hint1`, `hint2`, `merge`, `hint3` and `merge`'s
> `"action": "Merge"` — `tests/test_phone_and_gm.py` checks them.

That is not what is in the repository. The actual `private\gm\script.json` has
five hints, keyed **`hint1`, `hint2`, `hint3`, `motive`, `method`**, the last two
flagged `"optional": true` so the console files them under "If they are still
stuck". There is no `merge` key and no `"action": "Merge"` anywhere in the
project.

And the test does not check what the rewrite says it checks. It checks this:

```python
assert [h["key"] for h in s["hints"]] == ["hint1", "hint2", "hint3", "motive", "method"]
assert [h["optional"] for h in s["hints"]] == [False, False, False, True, True]
```

So following §6.2 literally — writing a `merge` key and dropping `motive` and
`method` — would **break a currently passing test** and remove two hints the
console already has a place for.

My reading is that §6.2 was written against an older version of this file, and
that what it actually wants is the **four new hint lines**, not the old key
shape. The four lines it gives are good, and they fit the new story. Three of
them map straight onto existing keys. The fourth, `merge`, is not a hint at all
— *"Everyone, to the desk. They want one story, not two."* is a **stage
direction**, an instruction to the actor to pull a split group back together.

So the question is genuinely about how you run the room:

- **Option 1 (my recommendation).** Keep all five existing keys. Rewrite
  `hint1`, `hint2` and `hint3` with the new lines. Leave `motive` and `method`
  as the optional two. The merge line becomes a sixth, optional entry. Nothing
  breaks, nothing is lost, and the game master gains a "bring them back
  together" line they can send to the actor.
- **Option 2.** Follow §6.2 exactly: four keys, `merge` with an action, and I
  update the test to match. This is a real change to the console's shape and it
  drops two hints — defensible if the merge moment is meant to be a formal beat
  of the script rather than something the game master reaches for.

**Decided 23 Sep: Option 1.** The five existing keys stay, `hint1`/`hint2`/
`hint3` get the new lines, `motive` and `method` stay optional, and the merge
line joins them as a sixth optional entry. `tests/test_phone_and_gm.py` asserts
the key list and the `optional` flags, so that test needs its two expected lists
extended by one entry for the new sixth key — it is not being weakened, only
told about the addition.

### 4b. "Wherever the console stores" the lock code

It does not store it. Covered in Tier D above. Not a conflict so much as an
instruction with no target, but worth writing down so the next agent does not
spend an hour looking for a setting that was never built.

---

## 5. The order to do this in

Each numbered step is finishable and checkable before the next starts, which is
how this project has run so far.

1. ~~You answer §3a decisions 2 and 4.~~ **Done 23 Sep.** Decision 1, the
   finder's name, is still open. It now blocks only the printed statements and
   how he reads on the phone — Settings → The finder's name, and it takes
   effect the next time the phone is opened.
2. **The brief lands.** The organiser is sending `EVIDENCE_BRIEF.md`. Tier A
   cannot start until it is in the project root.
3. ~~**Tier A.** The phone's words.~~ **Done 23 Sep.** Every message, every
   chat time and the whole call log rewritten to the brief. Test it on your own
   phone — §6b.
4. ~~**Tier B.** Photos removed.~~ **Done 23 Sep**, ahead of Tier A because it
   does not depend on the brief. Worth a look on your own phone.
5. ~~**Tier C and D.** Console, reset list, settings.~~ **Done 23 Sep.** Six
   hint entries, the eight-step reset, lock code 1002.
6. ~~**Tier E.** The clock invariants test.~~ **Done 23 Sep.**
   `tests/test_clock_invariants.py`, 18 tests.
7. ~~**Tier F.** The documentation sweep.~~ **Done 23 Sep.** `ESCAPE_ROOM_FLOW.md`
   §§1–4 rewritten and the rest banner-marked; `ESCAPE_ROOM_PROPOSAL.md`,
   `README.md`, `STATE.md` and `context/PROJECT_STATUS.md` corrected.
8. **In parallel with all of it, and starting as early as you can: §3b, the
   shoot.** It is the long pole and it does not depend on a single line of code.

Steps 3 to 7 were mine and are finished. **Step 8 is yours, and it is the one
that decides whether there is a game.** Nothing in the code is waiting on
anything now; the room is waiting on photographs.

---

## 6. How you check my half — on Render

**Rewritten 23 Sep**, when you said you no longer run the app locally.
Everything this section said before assumed `python app.py` on the laptop.

### 6a. What changed, in one paragraph

The live game is a **git checkout**. Render builds the service from the GitHub
repository, and `private\phone\the-phone.html`, `private\phone\assets\` and
`private\gm\script.json` all sit inside that checkout. So **a file that is not
committed and pushed does not exist in the live game**, and a file saved only on
the laptop changes nothing for a player. Everything under the repository is also
**rebuilt from git on every deploy** — only `/var/yard` (the database, its
backups, the payment screenshots) survives. Nothing placed on the running server
by any other route lasts.

That makes "commit and push" part of the work, not the tidying up afterwards.

### 6b. The checks, in order

Steps 1 to 4 run on the laptop **before** anything is pushed. They are cheap,
and they catch everything a deploy would otherwise catch slowly.

1. Open PowerShell, go to the project, and activate the environment:

   ```powershell
   cd C:\Users\endrw\my-mini-app
   venv\Scripts\activate
   ```

   You should see `(venv)` appear at the start of the prompt line.

2. Check the phone file is still valid after my edits:

   ```powershell
   python -c "import sys; sys.path.insert(0,'.'); from scripts import phone_template as pt; raw,m,markup = pt.load(); print('phone markup OK,', len(markup), 'characters')"
   ```

   You should see one line reading `phone markup OK, 44193 characters`. The
   number changes with every edit — that is expected and fine. If instead you
   see `re-encoding is not byte-identical; refusing to edit`, stop and tell me:
   the phone file is damaged and I will restore it from git.

3. Check the picture, and whether git has it:

   ```powershell
   python manage.py phone-images
   ```

   Three answers are possible, and the middle one is the trap this section
   exists for:

   - `STILL NEEDED` — the bank screenshot is not on the laptop at all.
   - `HERE BUT NOT LIVE` — it is on the laptop but was never committed, so
     **Render has never seen it and the live phone shows a grey tile.** The
     command prints the exact `git add` / `git commit` / `git push` to fix it.
   - `The phone has its picture, and it is committed` — done.

4. Run the tests:

   ```powershell
   python -m pytest -q
   ```

   You should see a line ending in `565 passed`, and no `failed`. If anything
   fails, send me the whole output — the failure text names the exact
   assertion, which tells me immediately what I broke. **Do not push a red test
   run:** on Render a bad push can become a bad deploy, and a rollback is slower
   than the fix.

5. Push:

   ```powershell
   git add -A
   git commit -m "the phone"
   git push
   ```

   You should see a line ending in `main -> main`. If git asks for a username
   and password, stop — the push did not happen.

6. **Deploy on Render — and check first whether that is automatic.**
   `render.yaml` in this repository says `autoDeploy: false`, with the comment
   "a deploy restarts the bot and bounces the app; on event day that is a
   decision, not a push". You have told me Render auto-pulls, which would mean
   the dashboard has been switched on since, because a dashboard setting
   overrides the blueprint. **Both states are defensible and they need opposite
   habits**, so it matters which one you are in:

   - **Auto-deploy ON:** every `git push` restarts the bot and bounces the live
     app, including mid-game. Push deliberately, and never during the event.
   - **Auto-deploy OFF:** nothing happens until you press **Manual Deploy →
     Deploy latest commit**. Safer, but it also means a fix you pushed is not
     live until you press it.

   Render → the `the-yard` service → **Settings → Build & Deploy → Auto-Deploy**
   answers it in one look. Please tell me which, because it changes what I say
   to you after every future change.

7. Watch the deploy finish. Render's **Logs** tab should end with the service
   coming up and the health check at `/healthz` passing. If the deploy goes red,
   send me the log — the traceback names the file.

8. Open the phone on your own phone, through Telegram, as a player would. To
   open it outside a booked time your handle has to be in Settings →
   `phone_always_handles`, or in `ALWAYS_ALLOW_HANDLES` in the Render dashboard.
   **Empty it again before the event** — it hands out the whole solution.

   What you should see after Tier B: Messages and Recents open normally;
   **Photos opens and then says "Cannot Connect"**, like FaceTime and Calendar;
   and there are no camera stills anywhere on the phone.

---

## 7. Still open

1. **The finder's name, and how it reaches the phone** (§1f). Two questions in
   one now: what he is called, and whether the phone hard-codes it, substitutes
   it at serve time, or leaves the number unsaved. **This blocks the group chat
   in Tier A.**
2. **Is the repository public or private?** `DEPLOY.md` and
   `ESCAPE_ROOM_PROPOSAL.md` §6b flatly contradict each other (§1e). One of them
   is misleading the next reader, and if it is `DEPLOY.md` the solution is
   public right now.
3. **Is Render auto-deploy on or off?** You say on, `render.yaml` says off
   (§1e). Whichever it is, the other should be corrected so it stops lying.
4. ~~Does `EVIDENCE_BRIEF.md` exist outside the repo?~~ **Answered 23 Sep:** it
   was supplied and is now saved in the project root, along with
   `CHANGES_FOR_CLAUDE_CODE.md`. Neither had existed as a file before.
5. ~~The `merge` hint question.~~ **Answered 23 Sep:** Option 1, §4a.
6. ~~Should the lock code become a Settings row?~~ **Answered 23 Sep:** no, it
   stays as prose.
6. **A wrinkle in Natalie's story that I would rather raise than quietly smooth
   over.** By rule 5 her statement matches the raw stamps, so she says she left
   at **10:24**. But §2 has her texting Kai **"was it good? x" at 10:15** — nine
   minutes *before* the departure she claims. A player who lines those two up
   will ask why she was texting a man she says she was standing next to. That
   may be fine, or even good: it can read as a second crack in her story, found
   by a sharp group. But it is currently an accident rather than a decision, and
   if it is unwanted the cheapest fix is to move the text later than her claimed
   exit. Worth thirty seconds of your thought before the statements are printed,
   because it is expensive to change afterwards.
