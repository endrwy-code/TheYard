# The phone's one picture — and why dropping it in here is not enough

**Spoilers.** This folder is inside `private\`, is never served to an attendee
screen (§3 rule 4), and is only reachable by someone booked into a game whose
booked time has come — everyone in it, for 25 minutes from that time, opened
from the bot's "Open the phone" message. Do not put anything from here into
`static\`.

## Since the 23 Sep rewrite there is only one file

The phone used to have a Photos app holding four camera stills and seventeen
ordinary camera-roll shots. **It does not any more.** The Photos app was
removed, the tile now answers "Cannot Connect" like FaceTime and Calendar, and
the camera evidence became **printed paper at the desk**.

So this folder wants exactly one picture:

| Filename | What it should show |
|---|---|
| `ethan-bank-screenshot.jpg` | A banking app, a transfer list, one outgoing payment a month from Kai's account since May. It appears **inside the Messages thread with Ethan**, under his line "i wasnt going to send this" |

This is the only asset the phone loads (`EVIDENCE_BRIEF.md` §5.9), and it
carries the **motive**. Without it a player can find out that Natalie was alone
with the cake, but not why she would want to be.

## The file has to be committed, not just copied here

**This is the trap, and it is new since the app moved to Render.**

The live game does not run from this laptop. Render builds the service from the
GitHub repository, so the only files that exist in the live game are the files
that are **committed and pushed**. A picture sitting in this folder on the
laptop and nowhere else does not exist as far as players are concerned: the
live phone shows a grey tile, the room loses its motive, and nothing anywhere
reports an error — a missing picture is answered with a placeholder by design,
precisely so the game stays playable while you wait for it.

So the old advice — "add the file, reload the phone, it is there" — is **only
true when running locally.** On Render:

```powershell
cd C:\Users\endrw\my-mini-app
git add private/phone/assets/ethan-bank-screenshot.jpg
git commit -m "the bank screenshot"
git push
```

Then deploy on Render. `ESCAPE_ROOM_PLAN.md` §6 has the full sequence and says
what you should see at each step.

## Two things that work here and fail on the server

1. **Capitals.** Render runs Linux, where `ethan-bank-screenshot.jpg` and
   `Ethan-Bank-Screenshot.JPG` are two different files. Windows treats them as
   the same, so a wrongly-capitalised name works perfectly on the laptop and
   shows a grey tile live. Lower case, `.jpg`, exactly as written above.
2. **Anything uploaded to the running server.** The repository checkout on
   Render is rebuilt from git on every deploy. Only `/var/yard` survives, and
   this folder is not under it. A file placed on the server by any other route
   disappears at the next deploy.

## It cannot be zoomed, so shoot it large

The picture is shown inline in the conversation at the width of a message
bubble, and it cannot be tapped open — the full-screen viewer was removed with
the Photos app. The transfer amounts and the dates have to be readable at chat
bubble size, on a phone, held by somebody standing up. Shoot it large and
high-contrast.

## Checking before you push

```powershell
cd C:\Users\endrw\my-mini-app
venv\Scripts\activate
python manage.py phone-images
```

It says whether the picture is here **and** whether git has it. Three things it
can tell you:

- `STILL NEEDED` — the file is not on this laptop at all.
- `HERE BUT NOT LIVE` — it is here but never committed, so Render has never
  seen it. It prints the exact `git add` / `git commit` / `git push` to run.
- `The phone has its picture, and it is committed` — you are done.

## What is *not* in this folder

The seven camera stills and the two bin photographs. They are generated as
files too, but they are printed and never served, so they live in
`private\props\` and are deliberately not committed. See that folder's README,
and `EVIDENCE_BRIEF.md` §7 for the shoot list.
