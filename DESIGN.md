# DESIGN — "Yard Paper", the design system

The look of The Yard's Mini App and console. Version 2, 18 Sep 2026, set by the
organiser: **minimal, modern and streetwear, on matte paper with halftone**. It
should feel like a pre-U event, not a utility app. Reference: the organiser's
Pinterest board (heavy condensed type, cream matte ground, thin rules, arrows).

Change this file when the system changes, and add a CHANGELOG entry.

---

## 1. Principles

1. **Say it once, in the right place.** If a screen shows a status (Ready,
   Collected), nothing near it repeats it. Rules, facts and fine print live on
   **Help**, not on every screen. Since 21 Sep there is no small print under
   screens at all: a fact that matters is a **row** ("Booked by @x"), what an
   action does to other people goes in its **confirm dialog**, and a deadline
   is the one allowed line — *"You can change this anytime, until 5 minutes
   before your booking."*, its number read off the server.
2. **Rows and rules, not dots.** Never join facts with " · ". A fact is a row:
   label on the left, value on the right, a 1px rule between rows. A list of
   places to go is a numbered row with an arrow.
3. **Big type does the talking.** Times and titles are Anton, large. Small
   labels are wide, spaced capitals. Body copy is plain and short.
4. **One accent.** Caramel `#AE7338` marks "selected" and "needs you". Green
   means booked or ready. Red means refused. Ultramarine belongs to the jamming
   studio. Nothing else is coloured.
5. **Texture, not decoration.** Paper grain over everything, halftone dots
   fading across hero blocks. No gradients, no drop-shadow cards, no emoji in
   the UI.
6. **Headings aren't repeated.** A screen with its own big title leaves the top
   bar's title empty.

## 2. Tokens (`templates/index.html` `:root`)

| Token | Value | Use |
|---|---|---|
| `--paper` | `#EEEAE1` | the ground |
| `--paper-2` | `#E4DFD3` | pressed rows, quiet strips |
| `--card` | `#F8F6F1` | the pass and the item list |
| `--ink` | `#111111` | text, primary buttons |
| `--muted` | `#5A5750` | secondary text (AA on paper) |
| `--rule` | `#11111124` | 1px rules |
| `--accent` | `#AE7338` | selected, warnings, "Next up" label |
| `--accent-ink` | `#8A5626` | the accent as small text on the card (Help headings) — the plain accent is under AA there |
| `--ok` | `#8FA65B` | Ready |
| `--bad` | `#A8231B` | refusals, cancel on hover |
| `--jam` | `#3B32C4` | jamming studio title and selection |
| `--night`, `--night-2` | `#0E0E10`, `#18181C` | The Last Guest's ground and panels |
| `--bone` | `#D9DDD6` | your own game, the phone button |
| `--grain` | SVG noise | the paper texture |

The console (`templates/admin.html`) keeps its denser palette but shares the
type, the grain and the rule of no dot-strings in new copy.

## 3. Type

Two families, both from Google Fonts:

- **Anton** (display): titles, times, item names, big buttons. **Normal
  capitals since 22 Sep** (decision 123), not forced upper case: "Evening,
  Heidi", "The Yard Pass", "Book 5:30 PM for 3". Line height 0.98–1.05, a
  little more than before, because mixed case has descenders.
  Sizes: 72 (ticket time), 64 (next up), 58–60 (screen heroes), 48 (page
  title), 34 (program rows), 24–30 (slot times, item names).
- **Archivo** (variable width): everything else, with tabular numerals on.
  - Body: 15px, 400–600.
  - `.label`: 11px, 700, uppercase, 0.14em tracking, width 115%. The
    streetwear label — **the one thing that stays in capitals**, with the
    `.pill` tags. At 11px capitals read better, and they carry the look.
  - Buttons (`.btn`, Add, Edit, Allow): 13–15px, 700, normal capitals, no
    wide tracking.
  - `.code`: 700, width 125%, 0.1em tracking. Pass codes and refs.
  - `.fine`: 13px muted, for the one line of help a screen may carry.

Space Mono and Inter are retired.

## 4. Texture

- **Grain**: `body::after`, fixed, `--grain` at 22% opacity, multiply. Never
  catches taps. Hidden while the phone is open.
- **Halftone**: add `.halftone` to a block. Dots in the block's text colour
  (6px grid) fade out across it at 200°. Used on: Next up, the pass, the
  escape hero, the ticket stub. The Start screen has its own radial halftone.

## 5. Components

| Component | Where | Notes |
|---|---|---|
| Program row (`.prog-row`) | Home | number label, Anton title, drawn arrow; the arrow moves on press |
| Next up (`.next`) | Home | dark, halftone; big time, then a rule, then what and when ("in 7 days") |
| Strip (`.strip`) | anywhere | one-line status: warn (caramel), ok (green); title + one sentence |
| Pass (`.pass`) | Your pass | QR and code only |
| Item list (`.items`, `.item`) | Your pass | punch hole, name, and **one** status on the right: Ready pill or "Collected / time" |
| Slot cell (`.game`) | The Last Guest | time + one label: `12 left`, `Yours`, `Full`, `Closed`, `Past`, `Off`. A free one opens its booking page |
| Booking head (`.bookhead`) | Escape booking page | label + seats left, the time in Anton in `--bone`, a 2px rule under it |
| Ticket stub (`.tstub`) | Your ticket | on `--night-2` with a hairline, like the room cards: time in `--bone`, then fact rows (arrive by, meet at, where you start, booked by). The people list sits under it, not inside it |
| People list (`.plist-wrap`, `.prow`) | all four booking screens | one numbered 58px box per person: number, name, `@handle` under it, then **one** tag (instrument, Booked it, Taken) or buttons. `.me` filled (bone on night, ultramarine in the jam room); `.locked` dimmed with no buttons — never blurred; `.bad` ringed red. Edit only before booking. The last box, `.prow.add`, is the next number with `@`, the input and Add; in the jam room the free instruments sit inside it as `.kitchip`s, and a lone one is pre-picked. Colours come from `--p-*` variables, so one set of rules serves night and paper |
| Jam row (`.jamslot`) | Jamming studio | time range left, one label right |
| Up next hero (`.bk-hero`) | Your bookings | the Home card's label, 64px time and foot, carried up; what the card grows into |
| Hold card (`.hold`) | Your bookings | one per room, on the night ground: label + when, the time in Anton, then a rule and a numbered line of first names (`.hold-who`). `.hold.empty` is the same shape drawn as an outline for a room you have not booked, so the page is always two rooms |
| Buttons | | `.btn-ink` primary, `.btn-line` secondary, `.btn-quiet` destructive, `.btn-bone` on the night ground; the bottom sheet button is Anton, `--bone` on night screens |
| Help card (`.help-card`) | Help | one card per section on `--card`, heading in `--accent-ink`; When and where carries the date and hours in Anton, the venue, its street address and an **Open in Maps** button; the questions are `<details>` that open and close, with a drawn chevron |
| Night frame (`body.dark`) | every escape screen and Your bookings | the top bar, the bottom sheet and Telegram's header and bottom bar go night with the page — one ground per room |
| The stamp (`#stamp`) | after a booking | full-screen, "BOOKED" in Anton inside a caramel frame with what you booked underneath; built, held, and thrown away in 1.24s. Never built under `prefers-reduced-motion` |

## 6. Copy

- Sentence case, active voice, no apologies, no codes on screen.
- **Names of things take title case** (22 Sep, decision 123): The Yard Pass,
  Pastry, Photo Strip, Vinyl Making, The Last Guest, The Jamming Studio, Your
  Bookings. Sentences and buttons stay sentence case ("Book 5:30 PM for 3",
  "That time has gone"). Item and instrument names come from `config.py`, so
  that is where their capitals are set.
- Countdowns read naturally: "in 45 min", "in 3 hours", "in 7 days".
- Time ranges: "7:30–8:00 PM" (one AM/PM when both match).
- Buttons say what happens: "Book 5:50 PM for 2", "Cancel my seat",
  "Hand over photo strip".

## 7. Motion

**The first rule is that content does not animate in.** Nothing that holds
something a person came to look at — a screen, a card, a photograph, the pass
QR — may start at `opacity:0`.

This is the rule the app failed three times, and each failure looked the same
to the organiser: *"every single asset and button and qr code turns blank and
then comes back."* A screen is rebuilt with `innerHTML`, so every element on
it is new. Fading that in means the whole screen starts at nothing and arrives
together; and when the fade begins a few frames late — which it does on a
mid-range phone busy laying out the markup it was just handed — what you
actually see is a blank page that pops back. Shortening the fade does not fix
it. Only not fading does.

**The movement was never the problem — `opacity` was.** So there *is* a
screen transition, and it moves `transform` only: the arriving screen starts
18px to the side and settles, 0.2s. Start that late and the content is simply
sitting still, fully visible, and then it moves. There is no frame in which it
is absent.

18px rather than a full screen width, because the outgoing screen has already
been thrown away — nothing is sliding out underneath — so a long slide would
drag a band of empty paper across. At this distance nothing is ever uncovered.

What is allowed to move:

| | |
|---|---|
| Between screens | an 18px `transform` nudge, 0.2s: `.scroll.fwd` / `.scroll.back`. **Never `opacity`** |
| Home ↔ Your bookings | the Up next card grows into the page and shrinks back (below) |
| Presses | `transform: scale()` on `:active`. Instant, and the person caused it |
| The back-swipe | follows the thumb, left edge only (36px) |
| The bottom sheet | `.mainsheet.in`, a transform slide, **once**, when it first appears |
| The toast | an overlay that genuinely appears and leaves |
| The phone button's ring | on `.phone-open::after`, so it is a pseudo-element and not the text |
| The booking stamp | built on demand and thrown away; the one deliberate moment in the app |

And the standing constraints, which still hold for anything added later:

- **Never animate a painted property.** No `box-shadow`, no `filter`, no
  `width`/`height`, no `mix-blend-mode`. Those repaint every frame. The phone
  button's ring scales and fades; the shadow on it is still.
- **Never let two engines drive one property.** A CSS animation and a CSS
  transition on the same property of the same element is undefined behaviour,
  and it judders.
- **Nothing is copied or rebuilt in order to animate it.** A recreated `<img>`
  loses its decoded bitmap and paints nothing until it decodes again.
  `reuseDecoded()` moves the decoded node into the new markup instead, and
  `prewarmShots()` decodes the photographs as soon as the server names them.
- **The transition may change, but not in kind.** Distance, duration and
  easing are free. `opacity` is not. Animating things *inside* a freshly
  built screen is not either — with one exception, which works differently
  (next section). Three tests in `tests/test_invariants.py` enforce this and
  name the offending selector when they fail; the last of them makes any
  *new* fade-in a deliberate act by requiring its selector in `MAY_FADE`.
- `prefers-reduced-motion: reduce` turns all of it off, and the booking stamp
  is never built at all.

### The card that grows (21 Sep, `STATE.md` decision 121)

Tapping **Up next** on Home grows the card into Your bookings: the card, as a
solid night shape, expands up and down to fill the screen; "Up next", the
time and the line under it glide up to the top; the page's frame appears
once the card has landed; then the two room cards rise 24px into place.
**Back** runs it in reverse, with Home there from the first frame.

It is the one place where things inside a screen move, and it is allowed
because it cannot fail the way decision 113's did. It uses the **View
Transitions API**: the browser freezes the current frame, builds the next
screen behind it, and animates *pictures* of screens that are already drawn.
There is no frame in which a half-built screen shows. The rules still hold
inside it: reveals are `visibility`, movement is `transform`, the browser's
default cross-fade is switched off (and its additive blend with it, which
would turn paper plus night pale), and `test_the_card_morph_never_fades`
fails if any of that changes.

- It runs only for Home ↔ Your bookings, only when there is a live card, and
  its `view-transition-name`s exist only while `<html data-morph>` is set.
- Where the API is missing (iOS before 18, some Telegram Desktop builds) or
  motion is reduced, the ordinary 18px nudge runs.
- `MORPH = false` at the top of the script turns it off entirely.
- The corners of the growing shape are a static 20px, not animated: once the
  page's own night frame appears behind it they cannot be seen.

## 8. Accessibility

Touch targets ≥ 44px; text contrast AA on paper and on night; colour is never
the only signal (every coloured state also has a word); reduced motion turns
animation off; tabular numerals everywhere. The back-swipe gesture starts only
within 36px of the left edge, so it does not steal presses on a slot tile or
fight the phone's own gesture.
