# The photographs on each Mini App screen

Drop a file in here and it appears at the top of that screen. Take it out and
the screen goes back to exactly how it looked before — no gap, no broken
image. Nothing needs rebuilding or restarting; the app checks this folder on
every visit.

| Filename | Where it shows | What suits it |
|---|---|---|
| `home.jpg` | Home, under the greeting | The room, the crowd, the venue. Something that says "this is the place" |
| `pass.jpg` | Your pass, under the QR | The cookies, the photo-strip wall. The things the pass actually gets you |
| `esc.jpg` | The Last Guest, above the phone card | The flat, the desk, something staged and slightly wrong. **Not** the evidence photographs — those are spoilers and live in `private\phone\assets` |
| `jam.jpg` | Jamming studio, at the top | The instruments, the rugs, the cables. The jam-session poster would work |
| `help.jpg` | Help, under the heading | The front desk, so people know what to look for |

`.jpg`, `.jpeg`, `.png` and `.webp` all work. The first one found wins, so
don't put two files with the same name and different extensions in here.

## How they will look

**`pass.jpg` and `jam.jpg` keep their own colours** (since 22 Sep, `STATE.md`
decision 128), under a light halftone dot screen — enough to sit with the
grain, not enough to hide the photo. The current ones are the pastry counter
under The Yard's chalkboard and the instruments on the rugs, both supplied by
the organiser at 1600×1000 and saved here at 1400×875. The previous two are in
`design\old-shots\`.

**Every other screen's photo is not like the original.** It is turned
greyscale, given more contrast, and laid under a stronger dot screen so it sits
in the same world as the grain and the stencilled type rather than looking
pasted on. A busy, high-contrast photo survives that treatment; a pale, flat or
fussy one turns to mush. What works there: strong shapes, deep shadows, one
clear subject, people in silhouette, hard light. What does not: pastel colours,
fine detail that matters, anything where you need to read text in the image,
screenshots.

The dot strength for the two colour photos is one number, `opacity:.26` under
`.shot-pass::after, .shot-jam::after` in `templates\index.html`. Lower is
fainter.

They are cropped to a 16:10 letterbox (1600×1000 is exactly that), so put the
subject near the middle. Roughly 1400 pixels wide is plenty — bigger only makes
the page slower, and every attendee loads these on venue wifi.

Replacing a file under the same name shows the new one straight away: the app
adds the file's time to the address, so Telegram doesn't keep the old copy.

## A caution

These are **public**. Anyone who opens the Mini App sees them. Do not put
anything from the escape room in here — the evidence photographs, the phone,
the solution. Those belong in `private\phone\assets`, which is served only to
someone whose game is running and who is in the desk half (§3 rule 4).
