# The Last Guest — one flow for the escape room

> **Spoilers. The whole solution is in here.** Keep it off attendee screens.
>
> **Status (24 Sep 2026):** the cast below is live — the phone, the GM script
> and the Mini App's premise all carry it. The phone now opens at the booked
> time alone: no GM press, no check-in (§9 r21).
> §12 lists the decisions only the organiser can make, each with a recommendation. The
> flow below assumes those recommendations. §11 is the work list once they're
> answered.

## 0. How this was put together

Four sources disagree. When they conflict, this order decides:

1. **The built phone** (`private/phone/the-phone.html`) and **the app**
   (`config.py`, the Mini App's premise text): this is what players will actually see.
2. **The 20-minute deck** (`context/The_Last_Guest_20min.pptx`), the most
   complete puzzle design. Its mechanics are kept and cut down to 15 minutes.
3. **The GM Flow Deck** (`The Last Guest Guide.pdf`, 18 slides), which settles
   the cast and the puzzle chain. Its names — Kai Chen, Ethan, Darren, Natalie,
   Jasmine — are the ones in the app.

---

## 1. The answer

| | |
|---|---|
| **Killer** | **Natalie**, Kai Chen's sister |
| **Time** | **10:12 PM**: alone in the kitchen with both dessert plates |
| **Motive** | At **9 AM tomorrow** Kai Chen was signing a new will that cut her out, because she'd been taking his money for four months. If he died tonight, the old will stood. |
| **Method** | She swapped his nut-free dessert for the one with nuts, and took his EpiPen out of its case. |
| **Lock code** | **1012** |
| **The trap** | **Jasmine.** She lied about when she left, and the uncorrected camera puts her in the kitchen at 10:15. |
| **The key** | The home cameras' clock runs **15 minutes fast**. |

**How players get there:**

```
Still 4: wall clock 10:12 vs stamp 22:27 ─► every camera stamp is 15 min fast
Allergy card (10–20 min) + missed calls 10:31/10:32 + SOS 10:33 ─► he ate it 10:10–10:20
Corrected stamps × that window ─► only Natalie was with the food (10:12)
Will + solicitor's letter + notebook + Natalie/Ethan messages ─► motive: 9 AM tomorrow
Receipt + plates at the wrong seats + empty EpiPen case ─► method
        ─► box opens on 1012 ─► warrant ─► the finder reads it to the dispatcher ─► out
```

---

## 2. What really happened (real times)

Kai Chen is dead. It's a murder warrant. The Mini App's "he collapsed" works as the teaser.

| Real time | What happened | Where players can see it |
|---|---|---|
| 7:42 PM | Kai Chen checks everyone is still coming | Group chat |
| ~8:00–8:19 | Ethan, Natalie, Darren (8:04), Jasmine (8:19) arrive | Group chat |
| 8:32 | Darren buys two desserts on Kandahar Street, one marked nut-free for Kai Chen | Receipt (flat); group chat 8:41 |
| 9:45 | Jasmine says goodnight in the group chat, but only pretends to leave | Group chat; Jasmine's messages |
| 10:00 | Jasmine is back upstairs, in the kitchen with Kai Chen, collecting her things | Kitchen cam, stamped 22:15 |
| 10:04–10:05 | Darren leaves | Group chat 10:04; hallway cam 22:20 |
| 10:05 | Ethan "steps out for work". Really he goes to ring Kai Chen privately about Natalie | Group chat |
| 10:06–10:24 | Ethan and Kai Chen argue on the phone for 18 minutes. Kai Chen is away from the table | Call log: Ethan, incoming, 10:06, 18m 14s |
| 10:08 | Jasmine leaves | Hallway cam 22:23 |
| **10:12** | **Natalie alone in the kitchen with both plates. She swaps them.** (She took the EpiPen earlier in the evening.) | Kitchen cam 22:27, wall clock reads 10:12 |
| ~10:15 | Natalie leaves. Kai Chen eats the wrong dessert | The plates (flat) |
| 10:19 | Natalie: "night kai. think about what i said" | Group chat |
| 10:24 | Ethan: not coming back up (after the edit in §11-A1) | Ethan's messages |
| ~10:30 | Kai Chen collapses | **Mum**'s calls at 10:31 and 10:32 go unanswered |
| 10:33 | Kai Chen triggers Emergency SOS himself. The call runs 4m 12s | Call log |
| 10:37 | the finder arrives as the SOS call ends, finds him, takes over. **He leaves no trace on the phone** — he exists in the room only (24 Sep) | Actor's opening |
| 10:41 | the finder pulls the camera stills onto Kai Chen's phone | Photo info panel: "Today 10:41 PM" |
| **10:45** | **The game starts.** Police are fifteen minutes out | The phone's clock starts at 10:45 PM |
| 11:00 | Police arrive: game over | |

**The window:** collapse at about 10:30, and a reaction starts 10–20 minutes after
eating, so he ate it between **10:10 and 10:20**. Only Natalie was with him then.

---

## 3. The people

| Person | Who | What they give players | Why they look guilty | What settles it |
|---|---|---|---|---|
| **Kai Chen** | Victim, host. A real person lies in the flat (the deck's "living sacrifice") | — | — | — |
| **the finder** | Wasn't at the party. **Found him. Played by the actor.** Nowhere on the phone — the room only | Opens the game, relays the hints, takes the warrant | — | At work until 10:22 |
| **Ethan** | Best friend | Why the new will exists: he saw Natalie's transfers and told Kai Chen (bank screenshot in his messages) | Lied to the group about a "work call"; argued with Kai Chen that night | Call log: on the phone with Kai Chen from downstairs 10:06–10:24, which covers the whole window |
| **Darren** | Business partner | The dessert and the receipt: proof that a safe plate existed | Kai Chen wanted him out ("the restructure"); he brought the dessert | Left at 10:05 (chat 10:04, hallway cam 22:20), before the window |
| **Jasmine** | Ex-girlfriend | The lie. She is what a guilty person looks like | Says 9:45; camera says kitchen at 10:15, out at 10:23, inside the window | Fix the clock: really 10:00–10:08. Her messages say why she hid it (she came back for her things) |
| **Natalie** | Sister | Motive and opportunity | The will, the money, the kitchen photo | Nothing clears her: alone with both plates at 10:12 |

All four knew about the allergy ("got you the nut free one kai", 8:41), so
knowing it clears nobody. Only the clock does.

---

## 4. The one mechanic: the camera clock is 15 minutes fast

| Still | File (`private/phone/assets/`) | Stamp | Real | Shows |
|---|---|---|---|---|
| 1 | `cam-01-kitchen-2215.jpg` | 22:15 | 10:00 | Jasmine in the kitchen with Kai Chen |
| 2 | `cam-02-hallway-2220.jpg` | 22:20 | 10:05 | Darren leaving |
| 3 | `cam-03-hallway-2223.jpg` | 22:23 | 10:08 | Jasmine leaving, with a bag |
| 4 | `cam-04-kitchen-2227.jpg` (shown large) | 22:27 | 10:12 | Natalie alone with both plates; the wall clock reads 10:12 |

**Three ways to find the 15 minutes**, so no team depends on spotting just one:

1. **Still 4:** the wall clock in the picture says 10:12 and the stamp says 22:27.
   The phone draws that clock itself, top-left of the full-screen view.
2. **Darren:** "heading off too" in the group chat at 10:04; the hallway camera
   shows him leaving at 22:20.
3. **Natalie:** "night kai" at 10:19, yet the camera has her in the kitchen at
   22:27.

Chat and call-log times come from the network and are right. Only the camera
stamps are wrong.

**The trap.** Trust the stamps and Jasmine is in the kitchen at 10:15 and leaves at
10:23, right in the middle of 10:10–10:20. She also lied about 9:45, so every
team goes for her. Natalie at 10:27 looks like she came after the window.
Subtract 15 and the picture flips.

---

## 5. Where everything is

**Rule:** anything with a timestamp is on the phone; anything with a signature
is paper. Since 22 Sep (`STATE.md` decision 130) **every player gets the
phone**, so the phone no longer separates the two halves. The paper does that now.

### The phone: every player gets it on Telegram at Start, open for 25 minutes

| Where | What's there | What it gives |
|---|---|---|
| Messages → "kai's place 🍷" | The whole night in order | Arrivals and departures, the nut-free dessert, Jasmine's 9:45 lie, Natalie's 10:19 goodnight — which is now the last message in the thread |
| Messages → Natalie | "the account", the solicitor, "i can put it back", "four months" | Motive |
| Messages → Ethan | Bank screenshot, "i saw the transfers" | Why the will is changing |
| Messages → Darren | "the restructure", "i'll bring dessert" | Red herring |
| Messages → Jasmine | Staying back for her things, "don't tell natalie" | Why Jasmine lied |
| Phone → Recents | SOS 10:33 (4m 12s); **Mum** missed 10:31 and 10:32; Ethan 10:06 (18m 14s); Mum 8:47 PM; Tan & Associates 4:02 PM | Collapse time; Ethan's alibi; the solicitor |
| Photos → Today | The four camera stills | The clock; who was where |

Everything else on the phone shows "Cannot Connect" on purpose. **Desk handset:** the
same phone on a device in a stand at the desk, for anyone the bot can't reach.
The GM console marks those players "Can't reach — desk handset".

### Zone A — the flat (how and why)

| Prop | What it says or shows |
|---|---|
| Kai Chen | Lying in the victim area. Players don't move him |
| Two dessert plates | The half-eaten one (with nuts) at his seat; the untouched **NUT FREE** one at another seat |
| Darren's receipt | Kandahar Street, Thu 24 Sep, 8:32 PM: two desserts, one "NUT FREE — SH" |
| Allergy card on the fridge | "Severe nut allergy. Reaction starts 10–20 minutes after eating. EpiPen: case on the kitchen shelf." This replaces the paramedic's note (§12) |
| EpiPen case on the shelf | Empty. The pen is nowhere in the flat |
| Kai Chen's notebook | Four months of missing money, matched to Natalie |
| Unsigned will + Tan & Associates letter (in a drawer) | Removes Natalie. Signing is Friday 25 Sep, 9:00 AM; until then the old will stands |
| Set dressing | Wine glasses, sofa, lamp. **No broken watch and no working clock** (§10) |

### Zone B — the desk (when)

| Prop | What it's for |
|---|---|
| Four statements | the finder's notes from ringing each guest (text in §11-E) |
| Timeline board | Four camera rows filled in; the "real time" column blank; markers |
| Four suspect cards | Photo, name and relationship only (§12) |
| Lock box, 4 digits, code **1012** | Holds the blank arrest warrant and a pen |
| Desk handset | In its stand, on charge |

**Why the split still works:** the flat has how, why and the window, but no
statements. The desk has the statements and the board, but doesn't know which
minute matters. Both have the phone. The warrant needs both halves.

---

## 6. Minute by minute (15:00)

The GM console counts cue times from Start. In Settings, `hint_1` 4:30, `hint_2`
6:45, `forced_merge` 7:30 and `hint_3` 10:30 are the deck's 20-minute timings
× 0.75, so they stay as they are.

| Clock | What happens | GM / actor |
|---|---|---|
| Changeover (5 min) | Reset (§9). GM checks the next group in, splits them at the door by the console's halves, walks the flat half into Zone A, seats the desk half, gives the three rules | The phone only reaches checked-in players |
| **0:00** | Lights down, background music, smoke. **GM presses Start** and the phone goes to every player's Telegram. The door bursts open: the finder | Actor's opening (§7) |
| 0:45–7:30 | **Split.** Flat: plates, receipt, EpiPen case, allergy card, will, notebook. Desk: statements, board, stills | |
| 4:30 | Hint 1: the Jasmine plant | GM taps Send |
| 6:45 | Hint 2: the clock | Send, or skip if they already have it |
| 7:30 | **Forced merge** at the desk | GM taps Merge; the actor says the line |
| 7:30–10:30 | Window + corrected times: only Natalie, at 10:12 | |
| 10:30 | Hint 3: all four boxes | Send |
| ~11–13 | Box opens on **1012**: the warrant | |
| ~13–15 | Fill it in and hand it to the finder, who reads it into the phone | Right: door opens, GM taps **End** |
| 15:00 | Police arrive | Actor's time-up line; the GM gives a 30-second reveal at the door |

The phone stays open until 25:00, so a late Start doesn't cut anyone off mid-read.

**The three rules** (under 20 seconds, before the door opens): don't move Kai Chen;
nothing needs force, and the one lock's code is a time; stay out of anything
taped off (the Crib 2 door, the OFF LIMITS areas).

---

## 7. the finder's script (the actor)

He never improvises. The opening and the merge line are learned. The hints
reach his Telegram (after he sends `/actor <GM PIN>` to the bot) and he reads
them off the screen as the dispatcher's words.

**Opening (~45 seconds):**

> "I found him. I got home and he was on the floor. His phone had already
> called 995. The police are fifteen minutes out.
> He was fine. He was fine an hour ago.
> I've rung all four of them. Ethan, Darren, Natalie, Jasmine. Every one says they'd
> gone home before it happened. That can't be right.
> I've sent you his phone. It's on your Telegram now. Our group chat's on it,
> and I've put the pictures from his kitchen and hallway cameras on it. I can't
> touch anything once they get here.
> *(to the flat half)* You: the flat. Don't move him.
> *(to the desk half)* You: the desk. What they told me is on there.
> Just tell me when it happened. If we know when, we know who."

**Hints.** These replace the lines in `private/gm/script.json`; keys and times are unchanged.

| key | at | Line |
|---|---|---|
| `hint1` | 4:30 | "They're saying Jasmine lied about when she left." |
| `hint2` | 6:45 | "They're asking if the clock in the kitchen picture matches the camera's time." |
| `merge` | 7:30 | "Everyone, to the desk. They want one story, not two." (A Merge cue isn't sent to the actor, so he learns this line) |
| `hint3` | 10:30 | "They need four things on that warrant: who, the minute, why, and how." |

**Taking the warrant.** He reads each box into the phone.
- **All right:** "…Yes. That's her. Go, they're here." He opens the door.
- **Something wrong:** "They're saying that won't hold up. Look at the ___
  again." (He names the wrong box.) One retry.
- **15:00, no warrant:** "They're here." Then the GM gives the reveal outside.

---

## 8. The warrant: what counts as right

| Box | Answer | Accept |
|---|---|---|
| Name | Natalie | Natalie only |
| Time | 10:12 PM | 10:12 |
| Motive | The new will, signed at 9 AM tomorrow, cut her out; the old one leaves her the money | Anything about the will, the inheritance, or the money about to come out |
| Method | Swapped his nut-free dessert for the nut one; took his EpiPen | The dessert swap is required; the EpiPen is a bonus |

Print this table small as **the finder's answer card**.

---

## 9. Reset (4 minutes or less of the 5-minute changeover)

1. Plates: the half-eaten nut one at Kai Chen's seat, the untouched NUT FREE one
   at the other seat.
2. Papers back in place: receipt, allergy card on the fridge, notebook, will
   and letter in the drawer (flat); four statements (desk).
3. EpiPen case on the shelf, closed, empty.
4. Wipe the "real time" column of the timeline board.
5. Fresh blank warrant and pen in the box; close it; **scramble the lock**
   (never leave it on 1012; the deck's "reset to 1012" gives the answer away).
6. Desk handset: hold the top strip of the screen (where the time is) for 3
   seconds and the phone returns to its home screen. Check it's charging.
7. Kai Chen in place. Lights, music and smoke back to the start.
8. Console: next game, check-in, halves.

---

## 10. What doesn't fit today, and the proposed fix

| # | Where | Problem | Proposed fix |
|---|---|---|---|
| 1 | ~~PDF pp. 4, 7, 10–13~~ | **Settled 24 Sep.** The GM Flow Deck (`The Last Guest Guide.pdf`) is the finished artifact and keeps the original names, so the local cast that briefly replaced them is retired instead | Victim **Kai Chen**; suspects **Ethan** (best friend) / **Darren** (business partner) / **Natalie** (sister, killer) / **Jasmine** (ex). The finder is not on the phone at all — his messages and calls are gone, and **Mum**'s two unanswered calls at 10:31 and 10:32 carry the collapse time |
| 2 | PDF p. 7, infographic, deck | 15 vs 20 minutes; "last night… the police haven't solved it… before the evidence is taken away" | The app wins: 15 minutes, **tonight**, police fifteen minutes out (`game_minutes` 15, the Mini App premise, the phone clock at 10:45 PM) |
| 3 | Deck slides 7–8 | The phone is the finder's own, handed over at the door, one device at the desk | The built phone is **Kai Chen's** and reaches every player on Telegram at Start. The actor's lines are changed to fit (§7) |
| 4 | Deck, infographic | The split relied on only the desk having the phone | The phone is shared now, so the split rests on paper (§5) |
| 5 | Phone: call log vs Ethan's messages | Kai Chen's log shows **Ethan calling him** at 10:06 for 18m 14s, but Ethan's 10:24 message to Kai Chen says "boss is unhinged… coming back up". He can't have been on with his boss, and "coming back up" would make him the finder | Keep the call: it's Ethan's alibi, and it's why Kai Chen left the table. Change the 10:24 message (§11-A1) |
| 6 | Phone: Natalie's messages | "Yesterday: i'm seeing the solicitor at 9 tomorrow morning" means *this* morning, which has already passed. And Kai Chen raises "the account" on Monday, before Ethan shows him the transfers on Tuesday | Move the dates (§11-A2) |
| 7 | Phone: Jasmine's messages | "come by at the end, after the others go" and "don't tell natalie i'm coming", but Jasmine arrived at 8:19 and said "here" in the group chat Natalie is in | Reword (§11-A3) |
| 8 | Phone: Ethan's messages | "in april" vs Natalie's "four months" (April to September is five) | "in may" (optional, §11-A4) |
| 9 | Phone: message list | Ethan's thread shows "Tuesday / I won't" but holds messages from 10:24 tonight | Fix time, preview and order (§11-A1) |
| 10 | Deck | The clock is on "still #2" | On the phone it's still 4 (`cam-04`), shown large |
| 11 | Deck slide 11 | A "free check" row: the collapse on camera at 22:45 | There's no such still on the phone. Use the Darren cross-check instead (§4) |
| 12 | Deck, PDF | The actor is unnamed ("the man who found him"); "whoever found him called at 10:33" | **the finder**, the only other person in the group chat. Kai Chen pressed SOS himself; the finder arrived at 10:37 as the 4m 12s call ended (his "home in 15" was sent at 10:22). Settings → The finder's name = the finder |
| 13 | Deck, floor plan | A real wall clock ("check it against your own watch") | Games run 3:30–9:30 PM, so a working clock shows the afternoon and breaks the fiction. Drop it (§12) |
| 14 | Deck, PDF | "Paramedic's note", but no paramedic has come: the police are 15 minutes out and he's still in the flat | An allergy card on the fridge carrying the same facts (§12) |
| 15 | PDF p. 6 | Broken watch | Drop it. A broken watch reads as "time of death" and competes with the clock mechanic |
| 16 | `script.json` cues | Placeholder lines: "Units are fifteen out" at 4:30; "Two minutes" at 10:30; hint 2 "We have a name. Ask about the kitchen" gives the answer away | Replace (§7) |
| 17 | `script.json` reset | Placeholder steps ("note under the lamp", "timeline board face down", "lock to 0000") | Replace (§9) |
| 18 | Phone clock | Starts at 10:45 PM when *each player* opens it, so players' clocks differ | Harmless. Don't build a clue on it |

---

## 11. Work list for the next agent (after §12 is answered)

The phone file is read from disk every time it's opened, so an edit reaches the
next player at once. Edit between games or before the event. A–C touch no
`.py` file, so the organiser's running `app.py` won't reload.

### A. Phone text: `private/phone/the-phone.html`

The phone's script is a JSON string inside `<script type="__bundler/template">`.
The story text sits in it as plain text, and each "before" string below appears
**exactly once** (checked 22 Sep). Double quotes appear as `\"`. Use exact
find-and-replace and change nothing else. Afterwards run `python -m pytest` and
open the phone to read each edited thread.

**A1: Ethan (decision 2)**

```
before: ['them','Ethan','sorry that took forever, boss is unhinged'],['them','Ethan','20 minutes of my life gone. coming back up']
after:  ['them','Ethan',\"not coming back up. can't sit across the table from her tonight\"],['them','Ethan','9am. sign it.']

before: time:'Tuesday', preview:\"I won't\",
after:  time:'10:24 PM', preview:'9am. sign it.',

before: const threadList = ['group','Natalie','Jasmine','Darren','Ethan']
after:  const threadList = ['group','Ethan','Natalie','Jasmine','Darren']
```

**A2: Natalie's dates.** Do the second replacement first.

```
before: ['sep','Yesterday'],['me',\"i'm seeing the solicitor at 9 tomorrow morning\"]
after:  ['sep','Today 10:52 AM'],['me',\"i'm seeing the solicitor at 9 tomorrow morning\"]

before: ['sep','Monday'],['me','can you call me']
after:  ['sep','Yesterday'],['me','can you call me']

before: {name:'Natalie', kind:'Outgoing', time:'Monday',
after:  {name:'Natalie', kind:'Outgoing', time:'Yesterday',
```

**A3: Jasmine**

```
before: \"i know it's weird but can i come by tonight\"
after:  \"i know it's weird but can i stay back after tonight\"

before: ['me','come by at the end, after the others go']
after:  ['me',\"say bye with everyone, then come back up once they've gone\"]

before: \"and don't tell natalie i'm coming, she'll make it a thing\"
after:  \"and don't tell natalie, she'll make it a thing\"
```

**A4 (optional):** `her banking app in april.` → `her banking app in may.`

### B. `private/gm/script.json`

Replace the four `line` values with §7's lines and the `reset` list with §9.
**Keep the keys** `hint1`, `hint2`, `merge`, `hint3`, the `time_setting` names
and `merge`'s `"action": "Merge"`, because `tests/test_phone_and_gm.py` checks the keys.
Times stay in Settings.

### C. Settings

Console (Laptop sign-in) → Settings → **The finder's name: the finder.** The GM and
actor handles are still placeholders too.

### D. Mini App text

No change needed. The premise (`templates/index.html`, around line 1332) already
says Kai Chen, 10:30, four guests, fifteen minutes, and his phone on Telegram.

### E. Paper to make

1. **Four statements**, in the finder's handwriting, one per page:
   - **Ethan:** "Went downstairs about 10 and told everyone it was work. It wasn't.
     Rang Kai Chen from downstairs so we could talk without everyone there. We
     argued. Won't say what about. Went home after. Never went back up."
   - **Darren:** "Brought dessert, two from the place on Kandahar Street, one
     nut-free for Kai Chen. Left just after 10, early start. He was fine."
   - **Jasmine:** "Left at 9:45. 'It's in the group chat.' Went straight home."
   - **Natalie:** "Left just after 10, not long after Darren. Texted him goodnight
     on the way home. He was fine when I left." *(The lie: she was there at 10:12.)*
2. **Timeline board.** Columns: Event · Camera · Stamp · Real time. Rows, with
   everything but "Real time" filled in:
   Jasmine in the kitchen with Kai Chen · kitchen · 22:15 /
   Darren leaves · hallway · 22:20 /
   Jasmine leaves · hallway · 22:23 /
   Natalie alone with the dessert · kitchen · 22:27.
   Footer: "He collapsed around 10:30. He ate it between ___ and ___. Who was
   there? ___"
3. **Suspect cards:** photo, name, relationship.
4. **Allergy card** for the fridge (text in §5).
5. **Receipt** (§5).
6. **Notebook:** four months of dated amounts, the last entries matched to
   Natalie; the final line "Solicitor Fri 9am. New will."
7. **Will** (unsigned draft, removes Natalie) and a **Tan & Associates letter**:
   signing Friday 25 September 2026, 9:00 AM; until signed, the existing will,
   with Natalie as main beneficiary, stays in force.
8. **Arrest warrant**, one per game plus spares: NAME / TIME / MOTIVE / METHOD.
9. **the finder's answer card** (§8).
10. **Sealed envelope for the GM, in case the phone dies:** printed screenshots of the group chat, the
    four message threads, the call log and the four stills.

### F. Pictures to shoot

These go in `private/phone/assets/` with the exact filenames from its `README.md`;
`python manage.py phone-images` shows what's missing.

- Players must be able to tell **who** is in each still. The easiest way:
  four volunteers play Ethan, Darren, Natalie and Jasmine, and their suspect-card
  portraits and the stills are shot in the real set on the same day, in the
  same outfits.
- `cam-01`: Jasmine with Kai Chen in the kitchen. `cam-02`: Darren in the hallway,
  leaving. `cam-03`: Jasmine leaving with a bag. `cam-04`: Natalie alone at the
  dessert table with both plates.
- In `cam-04`, **leave the top-left of the frame clear**: the phone draws the
  10:12 wall clock there on the full-screen view.
- Portrait orientation, CCTV look (high angle, a little grain). **Don't burn in
  a timestamp**, because the phone adds "KITCHEN CAM — 22:27" itself.
- `ethan-bank-screenshot.jpg`: Natalie's banking app, showing monthly transfers from Si
  Hong's account into hers since May.

### G. Record it

Once the organiser agrees, write the decisions into `STATE.md` §5 and the other
four context files, and add a `CHANGELOG.md` entry, as their standing rule requires.

---

## 12. Decisions for the organiser

Each has a recommendation; the flow above assumes it.

| # | Question | Recommendation | Why |
|---|---|---|---|
| 1 | Who found him, and who does the actor play? | **the finder** | The only other person in the group chat; his "home in 15" at 10:22 lands at 10:37, exactly when the SOS call ends |
| 2 | Who was Ethan's 18-minute call with? | **Kai Chen** (the argument), and edit Ethan's 10:24 message | The alternative (delete the call and keep "boss is unhinged") leaves Ethan with no alibi and makes him the finder |
| 3 | Where does the 10–20 minute window come from? | **An allergy card on the fridge** instead of the paramedic's note | No paramedic has been; he's still in the flat |
| 4 | A real wall clock in the flat? | **No.** If you want one for the look, stop it at 10:45 | A working clock shows the afternoon |
| 5 | Where does the lock box sit? | **At the desk** | The desk's job is the minute; the flat has to bring the window over |
| 6 | What goes on the suspect cards? | **Photo, name and relationship only** | The deck's lines ("being written out of the will", "the camera says otherwise") hand out what the flat is meant to find |
| 7 | Kai Chen's and Natalie's surname (for the will and letter)? | Anything but Tan | Ethan and Tan & Associates already use it |
| 8 | Keep the Jasmine plant at 4:30? | **Keep it**, and skip it for a group already onto the clock | Hitting that dead end is what makes fixing the clock feel like a discovery |
