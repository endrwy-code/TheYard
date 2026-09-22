# The phone's pictures — drop them in this folder

**Spoilers.** These are the escape room's evidence photos. This folder is
inside `private\`, is never served to an attendee screen (§3 rule 4), and is
only reachable by someone booked in a game that is running — everyone in it
since 22 Sep, for 25 minutes from the start, opened from the bot's "Open the
phone" message. Do not put these anywhere in `static\`.

Put each file in **this folder**, with **exactly** the filename below. The
phone looks them up by name, so a different name — `cam1.jpg`, `Cam-01.JPG` —
will not be found. Lower case, `.jpg`.

Nothing needs rebuilding afterwards. Add the file, reload the phone, it is
there.

## The five that carry the story

| Filename | What it should show |
|---|---|
| `cam-01-kitchen-2215.jpg` | Kitchen camera, timestamped 22:15 |
| `cam-02-hallway-2220.jpg` | Hallway camera, 22:20 |
| `cam-03-hallway-2223.jpg` | Hallway camera, 22:23 |
| `cam-04-kitchen-2227.jpg` | Kitchen camera, 22:27 — shown large in the grid |
| `ryan-bank-screenshot.jpg` | Ryan's banking app, the transfers. Appears in the Messages thread with Ryan |

The phone tells the player each camera still is "3024 × 4032", i.e. **portrait**.
They do not have to be exactly that, but portrait photos will look right and
landscape ones will be cropped in the grid.

## The seventeen filler photos

`filler-01.jpg` through `filler-17.jpg`.

These are the ordinary camera-roll photos above and below the evidence —
Joo Chiat, Tekka Market, East Coast Park, Tan & Associates, Da Nang. They
exist so the gallery looks like somebody's real phone instead of a folder of
five clues, which is what makes a player scroll past the evidence once before
coming back to it.

**They are optional.** Any that are missing are replaced with a plain grey
tile, so the gallery still works — it just looks emptier. The five above are
not optional: without them the game has no evidence to find.

## Checking what is still missing

```powershell
cd C:\Users\endrw\my-mini-app
venv\Scripts\activate
python manage.py phone-images
```

It lists every picture the phone wants, says which are here and which are not,
and warns you if one of the five story images is missing.
