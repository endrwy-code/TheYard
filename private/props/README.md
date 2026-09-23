# The printed evidence — generated here, printed, never served

**Spoilers.** This folder holds the nine generated images from
`EVIDENCE_BRIEF.md` §7: the seven camera stills and the two bin photographs.

## Why they are here and not in `private\phone\assets\`

Since the 23 Sep rewrite the phone has no Photos app. These nine images are
**printed paper at the desk** — an A4 contact sheet of stills 1–7, one large
print of Still 5, and bin photos A and B. **No code reads this folder.** The
app does not serve it, `manage.py phone-images` does not check it, and putting
a file here can never change what a player sees on the phone.

The one image the phone *does* load is `ethan-bank-screenshot.jpg`, and it
lives in `private\phone\assets\`. Do not put it here, and do not put these
here *and* there.

## These are not committed, on purpose

`.gitignore` excludes everything in this folder except this README. Three
reasons:

1. **They are the sharpest spoiler in the project.** `still-5-kitchen-2222`
   shows the killer alone with both cakes and the oven clock that breaks the
   case. A repository that leaks gives the room away in one image, with no
   reading required.
2. **Render has no use for them.** The live service builds from the repository,
   and it never serves these. Committing them would push megabytes to every
   deploy for nothing.
3. **They are large.** Nine high-resolution generated images, sized for print.

The consequence is that **they exist only on the machine that generated them.**
Back them up somewhere that is not this folder — they cost real time to
produce, and a lost laptop means reshooting the room.

## The nine files

Names from `EVIDENCE_BRIEF.md` §7. The extension is whatever the generator
produced; nothing reads these names, so they only have to make sense to a human
at a print shop.

| File | Stamp printed under it | What is in frame |
|---|---|---|
| `still-1-hallway-2204` | `HALLWAY CAM — 22:04` | Darren at the door, jacket on, hand on the latch |
| `still-2-kitchen-2208` | `KITCHEN CAM — 22:08` | Jasmine and Kai at the counter. Two identical closed white boxes, clearly two |
| `still-3-hallway-2210` | `HALLWAY CAM — 22:10` | Ethan leaving, phone to his ear |
| `still-4-hallway-2216` | `HALLWAY CAM — 22:16` | Jasmine leaving, bag on her shoulder |
| `still-5-kitchen-2222` | `KITCHEN CAM — 22:22` | **Natalie alone.** Both boxes open, a plate in front of her, the oven clock reading 10:02 and legible |
| `still-6-hallway-2224` | `HALLWAY CAM — 22:24` | Natalie at the door. Tied bin bag against the wall |
| `still-7-hallway-2257` | `HALLWAY CAM — 22:57` | The finder coming in, keys in hand |
| `bin-a-cake` | *none* | The opened bag: nut-free box on its side, whole uncut cake, green dot and NUT FREE card legible |
| `bin-b-epipen` | *none* | Closer: EpiPen capped and unused, and the crumpled 18:42 WALNUT receipt |

## Three rules that are easy to break here

1. **Never burn a stamp into the image.** The stamp is printed *under* the
   frame, formatted exactly `HALLWAY CAM — 22:04`. A stamp inside the picture
   cannot be corrected by a player with a pen, and the timeline board is where
   the correcting happens.
2. **The bin photographs carry no timestamp at all.** The finder took them on
   his own phone at 10:41. A stamp on them creates an eighth clock to
   reconcile, and `CHANGES_FOR_CLAUDE_CODE.md` §7 rule 9 forbids it.
3. **Do not stage guilt into Still 5.** It has to stay genuinely ambiguous —
   a woman at a counter with two open boxes and a plate. No hand over the bin,
   no glance at the camera, no cake mid-air. If a player can read guilt off it
   without correcting the clock, the room has no puzzle left.
