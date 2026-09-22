# The Yard — design brief

**Read this before touching `the-yard-design.html`.**

You are being handed one self-contained HTML file: a working Telegram Mini App
for a real one-day event, with real data baked in and the network stubbed out.
Your job is how it **looks and moves**. Its behaviour, its data and its rules
are already built and tested elsewhere, and this file is a copy — nothing you
do here can break the live app until a merge script puts it back.

---

## 1. Open it

Double-click `the-yard-design.html`. It works offline: no server, no Telegram,
no database.

Along the bottom is a **preview bar** with a dropdown of **17 screen states**.
That bar is not part of the app. Use it to jump to:

| | |
|---|---|
| **Gate** | welcome · not on the list |
| **Home** | normal · nothing booked · payment not seen |
| **Your pass** | normal · payment not verified |
| **The Last Guest** | board · a time picked |
| **Your ticket** | |
| **Jamming studio** | board · pick an instrument · instrument chosen · with a friend |
| **My bookings** | normal · empty |
| **Help** | |

Design against **all** of them, not just the happy ones. A screen that looks
good full and terrible empty is half a screen.

**Buttons that would change data do nothing.** Booking, cancelling, adding a
friend — you get an amber note saying it is a preview. Everything that *reads*
is real.

---

## 2. What this is

**The Yard** is a one-day event for pre-university students in Singapore:
Thursday 24 September 2026, 3–10 PM, at @ Hub @ L5 Hafary. Entry is $12 and
paid at the door, not in the app.

The app is opened **inside Telegram, on a phone**, by people who are already at
or heading to the event. It is not a website and nobody browses it — every
visit has an errand:

1. **Prove who I am** and get in.
2. **Collect my cookie and photo strip** at the counter.
3. **Book the escape room** with my friends.
4. **Claim an instrument** in the jam room.
5. **Find out what's next** and when.

That is the whole app. Five errands, done standing up, usually in under a
minute, often one-handed, sometimes in a dark room.

### The two rooms

**The Last Guest** — a 15-minute escape room. A murder, four suspects, one
liar. Your group is split in two: half in the flat, half at a desk with the
victim's phone. Neither half can finish alone. It runs every 20 minutes,
12 seats a game.

**The jamming studio** — a room with five instruments (acoustic guitar,
electric guitar, keyboard, drums, bass). You book a 30-minute slot on **one
instrument**, and strangers can take the others. Free.

These two should not feel alike. More on that in §6.

---

## 3. The look it already has

The design system is called **Yard Paper**: minimal, modern, streetwear, on
matte paper with halftone. It should feel like a pre-U event flyer, not a
utility app. Keep this unless the person directing you says otherwise.

### Principles

1. **Say it once.** If a screen shows a status, nothing near it repeats it.
2. **Rows and rules, not dots.** Never join facts with " · ". A fact is a row:
   label left, value right, a 1px rule between. A destination is a numbered
   row with an arrow.
3. **Big type does the talking.** Times and titles are huge. Labels are small,
   wide, spaced capitals. Body copy is plain and short.
4. **One accent.** Caramel marks "selected" and "needs you". Green is booked
   or ready. Red is refused. Ultramarine belongs to the jam room. Nothing else
   is coloured.
5. **Texture, not decoration.** Paper grain over everything, halftone dots
   fading across hero blocks. **No gradients, no drop-shadow cards, no emoji
   in the interface.**
6. **A screen with its own big title leaves the top bar empty.**

### Tokens — they live in `:root` at the top of the file

| Token | Value | Use |
|---|---|---|
| `--paper` | `#EEEAE1` | the ground |
| `--paper-2` | `#E4DFD3` | pressed rows, quiet strips |
| `--card` | `#F8F6F1` | the pass, the item list |
| `--ink` | `#111111` | text, primary buttons |
| `--muted` | `#5A5750` | secondary text |
| `--rule` | `#11111124` | 1px rules |
| `--accent` | `#AE7338` | selected, warnings |
| `--ok` | `#8FA65B` | ready, booked |
| `--bad` | `#A8231B` | refusals |
| `--jam` | `#3B32C4` | the jam room |
| `--night` / `--night-2` | `#0E0E10` / `#18181C` | the escape room's ground and panels |
| `--bone` | `#D9DDD6` | your own game, the phone button |
| `--grain` | inline SVG noise | the paper texture |

Change values freely. **Keep the token names** — the markup and the console
both reference them.

### Type

Two families, both Google Fonts, already loaded:

- **Anton** — display. Titles, times, item names, big buttons. Always
  uppercase, line-height 0.85–0.95. Sizes in use: 72 (ticket time), 64 (next
  up), 58–60 (screen heroes), 48 (page title), 34 (menu rows), 24–30 (slot
  times).
- **Archivo** — variable width, everything else, tabular numerals on.
  - Body 15px. `.label` is 11px / 700 / uppercase / 0.14em tracking / 115%
    width — that is the streetwear label and it is used everywhere.
  - `.fine` is 13px muted, the one line of help a screen may carry.

### Texture

- **Grain**: fixed overlay on `body::after`, 22% opacity, multiply.
- **Halftone**: add `.halftone` to a block — dots in the block's own text
  colour on a 6px grid, fading across at 200°.
- **Photographs**: the `.shot` block. Greyscale, contrast pushed, a halftone
  laid over, so a photograph belongs to the same world as the grain rather
  than looking pasted in. **The pictures you see are placeholders** — the real
  ones are not taken yet, so design the *treatment*, not around the image.

---

## 4. Rules you must not break

These are not style preferences. Break one and the app stops working, or stops
being safe, in a way that will not show up in a browser.

### The harness

The file contains blocks marked:

```
<!-- ===== DESIGN-HARNESS START — deleted by merge_design.py ===== -->
<!-- ===== DESIGN-HARNESS END ===== -->
/* ===== DESIGN-BRIDGE START — deleted by merge_design.py ===== */
/* ===== DESIGN-BRIDGE END ===== */
```

**Do not edit, move or delete these, or anything between them.** They are the
preview scaffolding and a script deletes them on the way back in. It refuses
to merge if a marker is missing, so a half-deleted harness cannot reach a real
attendee — but it means the work has to be redone.

### One file, no build step

Everything is inline: one `<style>`, one `<script>`. **No Sass, no Tailwind, no
bundler, no framework, no npm.** The file is served as-is by a Python server.

The only permitted outside resources are the two already there: Telegram's SDK
and Google Fonts. **Do not add a CDN, an icon set, an animation library or a
web font.** Attendees load this on venue wifi and there is a hard budget of six
requests for a typical visit.

Icons are inline SVG. There is one arrow, drawn in the `ARROW` constant.

### Do not remove these

The merge refuses if any are missing, and each one is the whole of a screen:

`VIEWS.gate`, `VIEWS.home`, `VIEWS.food`, `VIEWS.esc`, `VIEWS.ticket`,
`VIEWS.jam`, `VIEWS.jambook`, `VIEWS.mybookings`, `VIEWS.help`

and the elements `#screen`, `#navback`, `#mainbtn`, plus the Telegram
bootstrap and the `Authorization` header on API calls.

### Do not change what a screen *shows*

The page renders what the server sends. It decides nothing itself — not
capacity, not eligibility, not who is in which half, not whether the phone
opens. If a design needs a piece of information that is not already on the
screen, **say so in your notes rather than inventing a field**. The server has
to send it, and that is a change in eight other files and 392 tests.

Restyling `${esc(b.ref)}` is fine. Replacing it with `${b.reference}` breaks
the screen silently.

### Telegram's webview is not a browser

- **Never use `100vh`.** Telegram's chrome overlaps it. The shell already uses
  `height:100%` with flex; keep that.
- **Respect `env(safe-area-inset-bottom)`.** It is already applied to the
  bottom button sheet. A notch or a home bar will eat anything that ignores it.
- **The phone's own back-swipe fights horizontal transitions.** There is
  already a drag-to-go-back gesture; be careful adding anything that competes
  for a horizontal drag from the left edge.
- **Assume a mid-range Android on bad wifi.** Heavy blur, large shadows and
  many simultaneous animated elements will judder.
- Design at **390px wide** first. It should survive 320px and look
  deliberate up to about 600px.

### Accessibility, and these are firm

- Touch targets **44px minimum**.
- Text contrast **AA** on both paper and night grounds.
- **Colour is never the only signal.** Every coloured state also carries a
  word — "Booked", "Full", "Taken". Keep the word.
- `prefers-reduced-motion` must turn animation off. There is already a block
  for it; extend it to anything you add.
- Tabular numerals on anything numeric, so times do not jitter.

---

## 5. What is wanted

*(The person directing this work should edit this section before handing the
file over. What follows are the standing goals; add your own on top.)*

**The brief in one line: make it feel alive and expensive without making it
slower, louder or harder to use one-handed.**

Specifically:

1. **Motion.** The app currently has modest entrance animations. Screen
   transitions, the press states, the moment a booking lands, the phone card
   unlocking — these are the moments worth spending motion on. Everything
   should feel like paper and ink moving, not software sliding.
2. **The booking moment.** Booking a game or claiming an instrument is the
   emotional peak of the app. It currently shows a green banner. It could be
   more of an event.
3. **The two rooms should feel unmistakably different** at a glance, while
   still obviously being the same app. See §6.
4. **The photographs** need a treatment that survives bad source images and
   makes the app feel high-quality rather than decorated.
5. **Density.** Home has a big greeting, a dark card and four menu rows. It
   should feel confident, not sparse.

### Your direction goes here

> *(Fill this in. Be specific about feeling, not implementation — "the jam
> room should feel like a gig poster, loud and slightly messy" is more useful
> than "add a rotation transform". Name screens by the labels in the preview
> bar.)*
>
> —

---

## 6. Screen by screen

What each is *for*, what is fixed, and where there is room.

| Screen | Its one job | Fixed | Free |
|---|---|---|---|
| **Gate** | Tell me whether I'm in, in one glance | The error states and their wording | The whole composition. It is the first thing anyone sees |
| **Home** | Where do I go, and what's next | Four menu rows in order: pass, escape, jam, help. Each keeps its explaining line | The greeting, the "next slot" card, the rows' treatment |
| **Your pass** | A QR someone scans, and what I've collected | The QR, the code, one status per item | Everything around them. It should feel like a ticket stub |
| **The Last Guest** | Pick a time, bring friends | The 13 slots, their states, the phone card's rules | Very free. It is the dark room — it should feel tense |
| **Your ticket** | When, where, who, and my half | The fact rows, the group list | The stub, the perforation, the reveal of your half |
| **Jam board** | Which times have instruments free | The 10 slots, "N free" | Very free. It is the loud room |
| **Jam booking** | Which instrument, and who else | Five instrument buttons, guest list with instruments | The instrument picker is the centrepiece and is plain right now |
| **My bookings** | Everything I hold, with its controls | The rows, the line-up chips | The hierarchy between escape and jam |
| **Help** | Answer it without a human | The FAQ content | Its presentation |

### The two rooms, specifically

They currently differ by ground colour and title colour. That is a start, not
an answer.

- **The Last Guest** — night ground, cramped, urgent, 15 minutes, a body on
  the floor. Think interrogation lamp, evidence, a countdown.
- **The jamming studio** — paper ground, ultramarine, loud, generous. Think
  gig poster, stencilled type, cables and rugs.

Someone glancing at a screen from across a room should know which one they are
in. But the top bar, the type, the grain and the button language must stay
shared — it is one app, and the transitions between them should feel seamless.

---

## 7. Before you hand it back

- [ ] All 17 preview states still render, including the empty ones
- [ ] The `DESIGN-HARNESS` and `DESIGN-BRIDGE` blocks are untouched
- [ ] No new outside resources — no CDN, no library, no extra font
- [ ] Still one file, one `<style>`, one `<script>`, no build step
- [ ] Nothing below 44px is tappable
- [ ] Every coloured state still carries its word
- [ ] `prefers-reduced-motion` turns the new motion off
- [ ] It survives 320px and does not fall apart at 600px
- [ ] No `100vh` anywhere
- [ ] A note listing anything you wanted that the screen does not currently
      have the data for

Then hand back the single file. A merge script strips the harness, checks
every screen still renders, and runs the test suite.
