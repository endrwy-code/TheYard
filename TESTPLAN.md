# TESTPLAN — the one list, run in two sittings

This is the master checklist for testing The Yard before 24 September 2026. It
replaces the step-by-step detail that used to live in `RUNBOOK` Phases 13c and
13d; those phases now point here so there is one list to keep correct.

It is split by **what each test needs**, not by when you feel like doing it:

- **Part A — you, one phone, about 30 minutes.** Everything that can be proved
  alone. This is where the failures that stop *everything* hide: the tunnel,
  Telegram's sign-in, the camera, the bot. Run this first, this week.
- **Part B — the crowd, about 90 minutes.** Everything that genuinely needs
  other people with other Telegram accounts: group booking, the two halves,
  the actor, two phones in one game.

**Why the split matters.** If the tunnel or the Telegram sign-in is broken,
*nothing* in Part B can run — and you would find out with eight people standing
around waiting. Part A rules that out in half an hour, alone, with nobody's
evening at stake.

**When to run Part B: 21 or 22 September.** Not the 23rd. You want a clear day
afterwards to fix whatever it finds.

---

## Before either part: what must already be true

| | |
|---|---|
| `app.py` running | one PowerShell window, in the project folder, venv active |
| `bot.py` running | a **second** window, same folder, venv active |
| ngrok running | a **third** window; `PUBLIC_URL` matches it; BotFather points at it |
| Bot messages | **test mode** — only `@maxi_muslim` receives anything |
| Your own payment | verified on the People screen |

Bot messages stay in test mode for the whole of both parts. Real attendees you
add to a group get a real booking but **no message**. That is deliberate: you
are testing with live people's names on the real list.

---

# PART A — alone, one phone

## A0. Start clean

1. In the `app.py` window press **Ctrl+C**. Then, one line at a time:

```powershell
cd C:\Users\endrw\my-mini-app
venv\Scripts\activate
python -m pytest tests -q
python manage.py cancel-group maxi_muslim "test booking"
python manage.py generate-slots
python app.py
```

**You should see:** `408 passed`; then either "Cancelled N seat(s)… Nobody was
messaged." or "has no group booked" (both fine); then "13 escape games … 10 jam
slots"; then "Running on http://127.0.0.1:5000".

**If the test count is lower and something says FAILED** — stop and send the
last 20 lines. Do not carry on: the suite is the one thing that tells you the
rules still hold.

**If you see `OVER CAPACITY`** after `generate-slots` — a game holds more people
than it now seats. It names the game and how many to move. Move them on the
Schedules screen, then run `generate-slots` again.

2. Start `bot.py` in its own window (RUNBOOK Phase 11, all three lines), and
   ngrok in a third. Leave all three running for the rest of Part A.

## A1. The chain is up

3. In a browser on the **laptop**:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/healthz
```

**You should see** `status : up`.

4. Open your ngrok `https://` address in the **phone's** browser.

**You should see** the Mini App's gate screen (or the ngrok warning page once —
click through). **If you see** "endpoint offline", ngrok is not running.

*This step is the whole point of Part A. If it fails, nothing else can work,
and you have found it alone rather than in front of a room.*

## A2. The gate and your pass

5. In Telegram, open your bot and send `/start`, then `/pass`, then `/help`.

**You should see** a greeting with an **Open The Yard** button, a picture of
your pass QR with your code underneath, and the help text. Each arrives within a
couple of seconds and prints a line in the `bot.py` window.

6. Tap **Open The Yard**, then **Start**.

**You should see** Home, with your name. **If you see** "We can't confirm who
you are", the bot token and the app disagree — Phase 18.

7. Home → **The Yard Pass**.

**You should see** your QR, and three items — **Pastry** (with "Mini tart,
brownie, cookie or shiopan" under it), **Photo Strip** ("Your first strip") and
**Vinyl Making** — none collected, and **no circle** before any of them
(22 Sep, `STATE.md` 132). Headings and buttons across the app are in
normal capitals now ("Evening, …", "The Jamming Studio"); only the small spaced
labels are in capitals.

7b. Home → **Help**.

**You should see** each section in its own card with a brown heading; **When
and where** shows "The Hub @ Hafary Gallery L5" and "105 Eunos Ave 3, Singapore
409836" with an **Open in Maps** button; the questions open and close when
tapped.

7c. Help → **Is there a price list?** Then, without closing it, tap another
    question. (22 Sep, `STATE.md` 132.)

**You should see** the prices in groups — Activities, Pastries, Shiopan and
Panini, Ice Cream Waffle, Matcha and Hojicha, Canned Drinks — with the price
on the right of each line, and **the price list closes by itself** when you
open another question. **Included with entry** lists Pastry, Photo Strip,
Vinyl Making, The Last Guest, The Jamming Studio, Board Games.

7d. Help → **See the floorplan** (also Home → **Floorplan**). Tap **Zoom in**,
    drag the map sideways, then **Fit to screen**.

**You should see** the venue map, readable when zoomed, and dragging it moves
the map rather than going back a screen.

## A3. The booth, against your own pass

8. On the **laptop**, open the console → **Laptop** → admin password →
   **Booth**. Scan your own pass from the phone.

**You should see** your name, "Payment verified", and the two items. Hold the
QR in view for ten seconds.

**You should see exactly one** `GET /admin/api/lookup/…` line in the `app.py`
window. More than one means the scan lock has regressed — say so.

9. Under "Hand over a pastry", tap **Mini Tart**. Then try to hand over any
   pastry kind again.

**You should see** green the first time ("Mini Tart handed over"), and a
refusal the second time — whichever kind you tap — naming
who handed it over and when. On your pass, Pastry now reads **Mini Tart**
under the name. Overview's Pastry card counts the kinds. That is the once-only rule (§9 r24) — the single
most important thing the booth does.

10. Check yourself in (**event check-in**).

**You should see** "Checked in" on your pass in the Mini App after you reopen
that screen.

## A3b. Orders and the "ready" call, on a phone (22 Sep)

10b. On a **second phone** (or the same one, in its normal browser), open your
     ngrok address + `/admin`. It opens on **Mobile**. Enter the phone PIN (the
     staff PIN or the GM PIN — either works), your name, and `Loft` → **Sign in**.

**You should see** four tabs only: **Booth, Orders, Game, People**.

10c. **Orders** → **Scan a pass to order** → scan your own pass (or type its
     code) → tap **Matcha**, then **Done**.

**You should see** "Matcha for … — on the list", and a card for you under
**Waiting** with a big green **Ready — call …** button. On the laptop's Orders
screen, the same card appears within a second or two, by itself.

10d. Tap **Ready — call …**.

**You should see** the card turn green-edged with **Collected** and **Call
again**, and within about five seconds a Telegram message: "🔔 your order is
ready / please collect the following at Two Goose: 🍵 Matcha" (22 Sep,
`STATE.md` 132). (You get it because you are a test account;
other people only get it after `notify on`.) The card says **Message sent**.
Tap **Collected** and it leaves the list.

**If the card says "Can't message them — call their name"**, that person never
opened The Yard or never tapped Allow. The app is fine; call their name.

## A4. Booking, alone

11. Mini App → **The Last Guest** → tap a time.

**You should see** that time's own page, dark all the way through (the top
bar and Telegram's header too): the time big at the top, then **Who's coming**
with you as box **1** and an empty box **2** to type a name in. Tap
**Book … for 1** at the bottom.

**You should see** **Your ticket** with a green **You're booked** banner and a
reference starting `ESC-`, the phone buzzes, and a Telegram message arrives
within about five seconds. The ticket is dark, not a cream card on black.
Under your group there are only two short lines: *"You can change this
anytime, until 5 minutes before your booking."* and *"You can cancel anytime,
until 30 minutes before your booking."* **Back** takes you to the board.

12. Home → **Jamming studio**.

**You should see** a paper screen — not the dark escape-room one — the five
instruments listed across the top, and each time showing how many instruments
are **free** rather than open-or-taken.

13. Tap a time that **clashes** with your escape game.

**You should see** a second screen open with the five instruments as buttons.
Pick one, then book.

**You should see** a refusal naming the clash. Go back, pick a non-clashing
time, choose an instrument and book it.

**You should see** "BOOKED" stamped across the screen for about a second, then
your jam slot's own screen with a green banner, **In the room · 1 of 5**, your
instrument named, and nothing asking you to pay. The jam room is free.
**Back** takes you to the jam board.

14. On that booking, type a real username in the next numbered box, tap an
    instrument for them, and tap **Add**. Then tap **×** next to their name.

**You should see** them appear as box 2 with their instrument, and then go.
The name you typed stays in the box when you tap the instrument. Messages are
in test mode, so they get nothing, but the seat is real.

15. Go back to the jam board and look at the slot you booked.

**You should see** it marked **Yours**, and the instruments you and your friend
took no longer offered — the others still free for anybody else.

16. Try to book a second jam slot.

**You should see** "You can hold 1 jam slot at a time."

## A5. The GM console and the phone — alone

This is the part everyone assumes needs two people. It does not.

**Rewritten 22 Sep (`STATE.md` 130):** everyone in the game gets the phone,
and it arrives only as a message from the bot when the game starts. You need
**`bot.py` running** for this part (the "Who gets messages" setting can stay on
testing — your own account is always allowed).

16b. Have a game booked (you have the 7:50 PM one). On the laptop: Settings →
     **Clock** → **Test time**, slide to **two minutes before your game**, and
     **Save changes**.

**You should see** the red banner: "Test time — the app thinks it is Thu 24 Sep,
7:48 PM …". Every attendee sees that time too, so do this part in one go.

16c. On your phone, open **The Last Guest**.

**You should see** the board with no phone card on it any more. Tap your game
(**Yours**): the ticket has a row **His phone — On Telegram, when the game
starts**.

17. Console → **Game** → pick your game → **Start**. (This works on a Mobile
    sign-in too, since 22 Sep.)

**You should see** the timer counting and the hint cues listed. Within about
five seconds your phone gets a message from **@The_YardBot**: **📱 HIS PHONE IS
UNLOCKED — THE LAST GUEST**, "Open until" a time 25 minutes after you pressed
Start, and a button **📱 Open the phone**. On the GM screen your name says
**Phone sent**.

If no message comes: is the `bot.py` window open? The GM screen says **Phone on
its way** while it waits for the bot, and **Can't reach** if the bot has no
chat with you (open @The_YardBot and tap Start).

18. Tap **📱 Open the phone** in that message, then **Start** in the app.

**You should see** the escape-room phone fill the screen. Open **Photos**.

**You should see** a grid of grey tiles until the photographs are added. That is
expected — the pictures do not exist yet. To check which are still missing:

```powershell
cd C:\Users\endrw\my-mini-app
venv\Scripts\activate
python manage.py phone-images
```

Drop the files into `private\phone\assets\` under exactly the names it lists.
Nothing needs rebuilding: add the file, reload the phone, it is there.

19. Close the phone (Back).

**You should see** a dark **His Phone** screen: **Unlocked**, the minutes left,
**Open the phone**, and "Phone not working? Open it in your browser". Nothing
else in the app leads here — only the message does.

20. On the GM screen, tap your name to **swap yourself to the other half**.
    Tap **📱 Open the phone** in the message again.

**You should see** it still opens. Since 22 Sep both halves have the phone; the
halves only decide where people start.

21. On the His Phone screen, tap **Phone not working? Open it in your browser**.

**You should see** your phone's normal browser open with the escape-room phone
in it. Go back and tap the same link a second time.

**You should see** it refuse: the link works once, and dies after 90 seconds.

22. On the GM screen: **+1 minute**, **Pause**, **Resume**, then **End**.

**You should see** the timer respond to each. End asks "…their phone stays open
until …" — and the phone **does** still open after End.

23. Settings → Clock → slide the test time to **27 minutes after you pressed
    Start** → Save. Tap **📱 Open the phone** again.

**You should see** "Time's up". (25 minutes, plus the 1 minute you added.)

24. Mark one hint cue **done**.

**You should see** it turn green. (With no actor set up, the GM reads the line
out; the cue is still recorded.)

25. **Settings → Clock → Real time → Save changes.**

**You should see** the red banner disappear and the top bar say **Real time**.

## A6. Settings, receipts, and the things with deadlines

24. Console → **Audit** → **Exports & backups** → **Save receipt copies**.

**You should see** "N saved". This takes a copy of every Paperform payment
screenshot onto the laptop.

**Do this before 22 September, 3:26 PM.** Paperform's links expire seven days
after each person signed up, and after that a payment you have not already
verified cannot be checked. The card on that screen shows the exact deadline.

**If any fail**, it names them. Open Paperform's own dashboard for those.

25. Console → **People** → open anyone with a receipt.

**You should see** "Saved copy" rather than "Paperform receipt", and the
screenshot opens from the laptop.

26. Console → **Settings**. Fill in: **GM handle**, **actor handle**, **finder's
    name**, and the three stock counts if you are counting stock.

**You should see** the amber "needs filling in" marks clear.

27. Console → **Schedules**. Reload the page.

**You should see** 21 games from 3:05 to 9:45 and 14 jam slots from 3:00, and you stay
signed in through the reload.

## A7. How it moves, on a real phone

This one is not about data. It is the only check the automated tests cannot
make, because nothing in them runs a browser.

28. On your phone, in Telegram, walk this exact path twice:
    **Home → The Last Guest → back → The Last Guest → back → Your pass →
    back → Home**. Watch the photographs, the QR and the buttons, not the
    screens.

**You should see** each screen **settle in from the side over about a fifth
of a second, complete the whole way** — the photograph on The Last Guest and
the QR on Your pass are visible from the first frame of the movement, not
after it. Nothing blinks, redraws or goes blank. The second visit looks
exactly like the first, and the fifth looks like the second.

The thing to watch for is content that is *missing* while the screen moves, as
opposed to content that is *offset* while it moves. The first is the bug; the
second is the animation. If anything still goes blank, say which screen and
whether it was the whole page or one part of it — those point at different
causes.

28b. **The Up next card growing into Your bookings** (21 Sep, `STATE.md`
     decision 121). With both rooms booked, on Home tap the dark **Up next**
     card.

**You should see** the card itself grow up and down until it fills the screen,
"Up next" and the time slide up to the top, and then the two room cards rise
in underneath — The Last Guest, then the jamming studio — each with a
numbered line of who's coming. Nothing goes blank at any point. Then press
**Back** (the arrow, Telegram's own Back, and a swipe from the left edge, one
at a time).

**You should see** the page shrink back into the card on Home.

28b-2. **The same with nothing booked** (22 Sep, decision 127). Use an
       account with no bookings (or cancel yours for a minute). The card on
       Home should read **UP NEXT / None / Book something!**. Tap it.

**You should see** the same grow, with "Up next", "None" and "Book something!"
sliding to the top of Your bookings, and two outlined cards underneath: **Book
a game** and **Grab an instrument**. Each opens its room.

**On an older iPhone (iOS 17 or earlier)** you will see the ordinary short
slide instead. That is the planned fallback, not a fault.

**If the grow misbehaves** — stutters, flashes, lands in the wrong place — say
what you saw. It can be switched off with one line (`MORPH = false` at the
top of the Mini App's script) and everything else keeps working.

28c. **Every button goes somewhere sensible.** Tap each and check where it
     lands:

| On | Tap | Lands on | Back goes to |
|---|---|---|---|
| Home | Up next | Your bookings | Home |
| Your bookings | a room card | that room's ticket | Your bookings |
| Your bookings | an empty (outlined) card | that room's board | Your bookings |
| The Last Guest | a free time | its booking page | the board |
| The Last Guest | your time (**Yours**) | Your ticket | the board |
| The Last Guest, while holding a game | another free time | stays put; says *"You already have a game…"* | — |
| Jamming studio | your slot (**Yours**) | that jam ticket | the jam board |
| Either ticket | Cancel / Leave | back where you opened it from | — |

Neither ticket should have **All games**, **All slots** or **Everything you
hold** buttons any more — Back does their job.

## A8. Tidy up

29. Cancel your jam slot and your game booking. Void the pastry hand-over on
    your own person page so your pass is clean for the day.

**You should see** all three gone, and the voids in the audit log with a reason.

---

# PART B — with other people

Everyone taking part needs a Telegram account **on the sign-up list**. Add them
as walk-ins on the People screen first if they are not. Messages stay in **test
mode**, so only you will receive anything.

## B1. Group booking, all or nothing

1. Mini App → **The Last Guest** → a time → on its page, add a name that does
   not exist (`notarealperson1`) plus two real friends, one per numbered box →
   **Book**.

**You should see** a red refusal naming only the bad name, that name's box
ringed red, and **nobody booked**. That is the all-or-nothing rule: a group is
booked whole or not at all.

2. Tap **Edit** on the bad name, fix it (or **×** to remove it), and book again.

**You should see** your ticket, the group listed as numbered boxes, and a
Telegram message to you.

3. Ask a friend to open The Yard → **Up next** → the escape card.

**They should see** a **Booked by @maxi_muslim** row, every other name dimmed
with no Add or Remove buttons, and a **Leave this game** button.

4. Have them tap **Leave this game**.

**You should see** a Telegram message telling you they left, and the group drop
by one.

5. **Check the halves on the GM screen now.**

**You should see** everyone who booked together **in the same half**, as long as
another group is there to fill the other one. Friends are no longer split up.

**You should also see** both halves occupied — somebody in the flat and somebody
at the desk. Each side finds things the other can't see, so a game with an
empty side cannot be played.

**The one time a group is still split** is when they are the *only* group in
that game. There is nobody else to put in the other half, and the game is
played from both rooms, so they are divided as evenly as possible. That is
correct, not a bug.

**Say so if** two separate groups end up mixed together, or if one half is
empty while two or more people are booked.

## B1b. The jamming studio, by instrument

7b. Have one person book a jam slot on one instrument and add two others, each
    on a different one.

**They should see** a green banner and **In the room · 3 of 5**, each name with
its instrument.

**Everyone added should see** a Telegram message naming *their* instrument and
the time — *you* will not, since messages are in test mode and only reach
`@maxi_muslim`. Check their phones. The message should read as a heading and a
few labelled lines, not a paragraph.

7c. Have a **fourth person, not part of that group**, book one of the two
    instruments still free in the same slot.

**They should see** it work. This is the point of the change: the room is
shared, the instrument is not. They should also see the whole room on their
own booking — all four names and what each is playing.

7d. Have a fifth person try to take an instrument somebody already has.

**They should see** it refused, naming the instrument.

7e. Have one of the added people open **Up next** → the jam card → **Leave**.
    (On their booking, the fourth person's name should be dimmed — not theirs
    to change.)

**The booker should see** a Telegram message saying they left, and that
instrument free again on the board.

## B2. A full game, six people

6. Book a game for six.

**You should see** three in each half on the GM screen.

7. Check everyone in at the booth, on the real scanner, one after another.

**You should see** each scan take one lookup and show the right name.

## B3. The game itself, two phones

**Rewritten 22 Sep (`STATE.md` 130):** the phone goes to everyone in the game,
only as a bot message. Before this part: `bot.py` running, and Settings → Who
gets messages → **Everyone** (in testing mode only `@maxi_muslim` would get it).

8. GM: **Start**.

**Everyone in the game should get** a Telegram message, **📱 HIS PHONE IS
UNLOCKED**, with a **📱 Open the phone** button, within a few seconds. The GM
screen marks each name **Phone sent**; anyone marked **Can't reach** gets the
desk handset.

9. Everyone taps **📱 Open the phone**, then Start.

**They should all see** the phone open — both halves.

10. Have someone open The Yard **from the menu button** (not the message) and
    look for the phone anywhere: Home, The Last Guest, their ticket.

**They should see** no way in. Only the message leads to it.

11. Have one player use **Phone not working? Open it in your browser**, then
    forward that same link to someone who is **not** in this game.

**The other person should see** it refused. The link is single-use and dies in
90 seconds. *This is worth doing once — it is the one place where a link
leaves the app and could leak.*

12. With the actor signed in (they send `/actor <GM PIN>` to the bot), mark each
    hint cue done as its time arrives.

**The actor should see** each hint line arrive in their own Telegram.

13. GM: **+1 minute**, then **End** at the right moment.

**Everyone should see** the phone **stay open** after End — until 25 minutes
(plus the extra minute) after Start, then "Time's up". To close it sooner, the
GM taps **Lock phone**, and it locks at once.

## B4. The awkward ones

14. While a game is running, have an admin **move** one booked person to another
    game.

**They should see** a Telegram message about the move, and the GM screen should
show the halves re-assigned for the new game.

15. **Block** a slot on the Schedules screen with a reason.

**You should see** it refuse to disappear quietly — it names anyone still booked
on it.

16. Two people scan the **same** pass at two booths at the same moment.

**You should see** one green and one refusal. If both go green, **stop and
screenshot both** — that is the one failure that costs real money.

---

## After both parts

1. `python manage.py cancel-group <handle> "test booking"` for every test group.
2. Void every test hand-over on the People screen.
3. `python manage.py notify on` — **only when you are done testing**. Until you
   run it, no real attendee receives any message at all.
4. Settings → **Clock** reads **Real time**, and the red banner is gone.
   (Event-day mode no longer exists, 22 Sep.)

**You should see**, on the Schedules screen, 21 games (3:05–9:45 PM) all reading "0 of 12
booked" before doors open. If any game has bookings you did not expect, they are
leftovers from testing — cancel them.
