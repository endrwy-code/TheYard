# HOW IT WORKS — the shape of the thing, and how to tell what broke

This is the file to read when something does not work and you want to know
*why*, not just which button to press next. `RUNBOOK` Phase 18 is the fast
lookup table for known symptoms. This is the map that lets you work out a
symptom nobody wrote down.

It assumes you are not a developer. It does not simplify what is actually
happening — it just names each part in plain words and says what that part can
and cannot be responsible for.

---

## 1. The five layers

Everything anyone sees passes through the same five layers, in the same order.
Almost every fault is one layer failing and the layers above it reporting it
badly.

```
  YOU / AN ATTENDEE
        |
  1. THE PAGE            index.html (phone)  ·  admin.html (laptop)
        |                one file each: the look, the buttons, the wording
        |                Decides nothing. Draws what it is told.
        v
  2. THE TUNNEL          ngrok  (or Tailscale Funnel)
        |                Gives your laptop a public https:// address
        |                so Telegram can reach it. Carries, never decides.
        v
  3. THE WEB APP         app.py
        |                Answers every address. Checks who is asking.
        |                Hands the real question to a service.
        v
  4. THE SERVICES        services\*.py
        |                Where every rule actually lives: who may book,
        |                once-only, the phone, payments.
        v
  5. THE DATABASE        data\app.db  (SQLite, one file)
                         The last word. Refuses anything that would break
                         its own rules, even if layer 4 forgot to check.
```

Two more things sit beside this, not inside it:

- **`bot.py`** — a separate program in its own window. It talks to Telegram,
  sends the messages, and answers `/start`, `/pass`, `/help` and `/actor`. It
  reads the same database. **If it is not running, nothing breaks — messages
  just queue up and send when it starts.**
- **`private\phone\the-phone.html`** — the escape-room phone. The real game runs
  this file *offline, on the desk devices*. The in-app version is a convenience.
  **The game never depends on any of the five layers above.**

---

## 2. The one rule that explains most of the design

**The server decides. The page draws.**

The page on the phone never works out whether a game is full, whether someone
has already had their pastry, whether the phone should open, or who is in which
half. It asks, and it renders the answer. Every one of those decisions is made
in layer 4 and enforced in layer 5.

This is why you cannot fix a wrong answer by reloading the page, and why a
person who "sees the wrong thing" is almost never a page problem.

It is also why the booth is safe. If two volunteers scan the same pass at the
same instant, both pages will happily show a green button — but the database
holds a rule that only one hand-over per item per person can exist, so exactly
one wins and the other gets a refusal naming who beat them.

---

## 3. How to tell which layer broke

Work from the bottom up. Each check rules out everything below it.

### Step 1 — Is the web app alive?

```powershell
cd C:\Users\endrw\my-mini-app
venv\Scripts\activate
Invoke-RestMethod http://127.0.0.1:5000/healthz
```

**`status : up`** means layers 3, 4 and 5 are all fine. The fault is the tunnel
or the page. **"Unable to connect"** means `app.py` is not running.

### Step 2 — Is the tunnel up?

Open your `https://` ngrok address in the laptop's own browser. If the laptop
can reach it, so can a phone. If you get "endpoint offline", ngrok is not
running or is pointed at the wrong port.

### Step 3 — What does the `app.py` window say?

**This is the single most useful thing in the whole system, and it is easy to
forget.** Every request prints a line. Every crash prints a full traceback with
a timestamp. If something went wrong at ten past, look for the lines at ten
past.

A line looks like:

```
10:07:14  ERROR    unhandled error on POST /admin/api/roster/commit/3
Traceback (most recent call last):
  ...
sqlite3.IntegrityError: UNIQUE constraint failed: attendees.handle
```

The last line is the answer. The rest is the path it took to get there.

---

## 4. What each error message actually means

The wording on screen is written for an attendee. Here is what it means to you.

| On screen | What really happened | Which layer | What to do |
|---|---|---|---|
| **"Can't reach The Yard"** | The phone could not get a reply *at all*. Tunnel down, laptop asleep, wifi gone. | 2 | Step 2 above |
| **"Something went wrong at our end"** / "The Yard answered with an error (HTTP 500)" | We *were* reached, and we crashed. Nothing was saved. | 3 or 4 | Read the traceback in the `app.py` window |
| **"The database refused that change"** (HTTP 409) | Layer 5 blocked something layer 4 should have caught. Nothing was saved. | 5 | The message names the rule. Usually two records clashing |
| **"Your sign-in has ended"** | Console sign-in older than 12 hours, or Sign out was pressed | 3 | Sign in again |
| **"This page's security token is out of date"** | The console was reloaded in another tab | 1 | It retries itself; if it persists, reload |
| **A refusal naming a person or a rule** | Working as designed. Layer 4 said no, on purpose. | 4 | Read it — it names what to do |

**The distinction in the first two rows matters more than it looks.** Until
18 September the console said "Can't reach The Yard" for *both*, which sent a
whole evening looking at the tunnel while `app.py` sat there with the real
answer in its window. They are now different messages on purpose. If you see
"Can't reach The Yard", check the tunnel. If you see "something went wrong at
our end", the tunnel is fine and the answer is in the `app.py` window.

---

## 5. Worked example: the roster upload that would not commit

This is the real fault from 17–18 September, traced the way you would trace one
yourself.

**What you saw.** Roster → upload the new Paperform export → the preview looked
right (16 new, 17 unchanged, no problems) → press Commit → **"Can't reach The
Yard"**. The website was running. The file was fine.

**Layer 1 (the page).** The page asked the server to commit and got back
something it could not read. Its only guess was "network". That guess was wrong,
and that wrong guess is what made this take an evening.

**Layer 2 (the tunnel).** Fine. Everything else on the console worked
throughout — which is the clue that it was never the tunnel. *A tunnel failure
breaks everything at once, not one button.*

**Layer 3 (the web app).** It crashed. Because there was no handler for an
unexpected crash, Flask replied with an HTML error page. The page expected JSON,
could not read HTML, and reported "network".

**Layer 4 (the services).** `roster.py` worked out the plan when you *previewed*
the file. It deliberately ignored the owner row — your own `@maxi_muslim`
account — when checking who already existed. You had signed yourself up on the
new form. So it planned you as a **new** person.

**Layer 5 (the database).** The plan said "insert a second `@maxi_muslim`". The
database holds a rule that a username appears once. It refused, and — correctly
— threw the entire import away rather than half-applying it.

**So the fault was one line in layer 4**, reported as a network problem by layer
1. Three things were changed:

1. The preview now matches against **everyone**, including your owner row and
   any walk-ins, so you are recognised instead of duplicated.
2. Any crash now answers in the format the page expects, so the page can say
   "something went wrong at our end" and tell you where to look.
3. The commit re-checks for a clash as it writes, and names the person, in case
   someone was added by hand between the preview and the commit.

**The lesson for reading future faults:** *one thing broken while everything
else works* is almost never the tunnel. *Everything broken at once* almost
always is.

---

## 6. Where each thing lives

| If you want to change… | Look in |
|---|---|
| Times, capacities, what entry includes, message settings | the console's **Settings** screen — not a file |
| The wording an attendee sees | `templates\index.html` |
| The wording on the console | `templates\admin.html` |
| Who may do what | `app.py`, the `ROLE_RULES` list |
| A booking or claim rule | `services\bookings.py`, `services\claims.py` |
| The phone's rules | `services\game.py` |
| The escape room's puzzle, hints, script | `private\gm\script.json` and the phone file — **spoilers** |
| Defaults for a fresh database | `config.py` |

Anything in the **Settings** screen takes effect immediately; changing game or
jam times rebuilds the timetable on the spot and tells you if anyone is left
stranded or a game is now over-full.

---

## 7. What is safe to do while the event is running

**Safe:** restart `app.py` (nothing is lost — everything is in the database);
restart `bot.py` (queued messages send when it comes back); restart ngrok
(update `PUBLIC_URL` and BotFather afterwards); change most Settings; back up.

**Careful:** changing game or jam **times** rebuilds the timetable and can
strand people who are already booked. It tells you who. Do it before doors, not
during.

**Never needed:** editing the database by hand. Everything has a screen or a
`manage.py` command, and every one of them writes an audit entry. A hand edit
writes none, so nobody can later work out what happened.

---

## 8. If it all falls over on the night

The escape room does not need any of this. The phone runs offline on the desk
devices; the GM has the script on paper or on the GM screen. The booth can work
from the printable fallback list:

Console → **Audit** → **Exports & backups** → **Offline fallback list**. Print
it before doors. It has every name, username and pass code, with boxes to tick.

With that sheet, the night runs without the laptop, the tunnel, the bot or the
database. Everything else here is convenience on top of that.
