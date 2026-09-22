"""Put the reworked design file back into the app.

    python scripts\\merge_design.py

Takes `design\\the-yard-design.html`, deletes the preview harness, and writes
what is left over `templates\\index.html`.

The merge is a deletion and nothing else. The harness never edited the page —
it stubbed Telegram and the network at run time and fixed image paths in the
browser — so removing its blocks leaves exactly the page you designed.

It refuses rather than guesses:

* if a marked block is missing or unbalanced, so a half-deleted harness can
  never end up served to an attendee;
* if the result still mentions the harness anywhere;
* if the page has lost something it cannot work without.

Your previous `index.html` is copied to `design\\index.html.bak` first.
"""

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "design" / "the-yard-design.html"
PAGE = ROOT / "templates" / "index.html"
BACKUP = ROOT / "design" / "index.html.bak"

HEAD_START = "<!-- ===== DESIGN-HARNESS START"
HEAD_END = "<!-- ===== DESIGN-HARNESS END ===== -->"
BRIDGE_START = "/* ===== DESIGN-BRIDGE START"
BRIDGE_END = "/* ===== DESIGN-BRIDGE END ===== */"

# Things the app cannot work without. If a redesign drops one of these the
# page still looks fine in a browser and fails in Telegram, which is the
# worst way to find out.
MUST_KEEP = [
    ("const tg = window.Telegram", "the Telegram bootstrap"),
    ("Authorization", "the initData header every API call needs"),
    ("id=\"screen\"", "the element every screen renders into"),
    ("id=\"navback\"", "the back button"),
    ("id=\"mainbtn\"", "the main action button"),
    ("VIEWS.gate", "the gate screen"),
    ("VIEWS.home", "the home screen"),
    ("VIEWS.esc", "the escape-room screen"),
    ("VIEWS.escbook", "the escape booking screen"),
    ("VIEWS.jamticket", "the jam ticket screen"),
    ("VIEWS.jam", "the jam board"),
    ("VIEWS.jambook", "the jam booking screen"),
    ("VIEWS.mybookings", "the bookings screen"),
    ("VIEWS.help", "the help screen"),
    ("VIEWS.food", "the pass screen"),
    ("VIEWS.ticket", "the ticket screen"),
    ("VIEWS.phone", "the phone screen the bot's message opens"),
    ("/api/me", "the call that loads the person"),
    ("/api/escape/slots", "the escape-room board"),
    ("/api/jam/slots", "the jam board"),
]


def cut(text, start_marker, end_marker, end_len):
    """Remove every start..end block, plus the one newline that follows it.

    The newline matters. `build_design_file.py` shapes every insertion as
    "block + exactly one newline", so taking that newline back makes the
    round trip byte-identical — build, merge, and the page is the same file
    it was. Anything less exact and a merge that changed nothing would still
    show up as a change.
    """
    out, removed = text, 0
    while True:
        i = out.find(start_marker)
        if i < 0:
            break
        j = out.find(end_marker, i)
        if j < 0:
            raise SystemExit(
                f"A harness block opens at character {i} and never closes.\n"
                f"Looking for: {end_marker}\n"
                "Nothing was written. Put the marker back, or rebuild the design\n"
                "file with build_design_file.py and redo the change.")
        k = j + end_len
        if out[k:k + 1] == "\n":
            k += 1
        out = out[:i] + out[k:]
        removed += 1
    return out, removed


def main():
    if not DESIGN.exists():
        raise SystemExit(f"No design file at {DESIGN}.\n"
                         "Run: python scripts\\build_design_file.py")

    text = DESIGN.read_text(encoding="utf-8")
    text, n_head = cut(text, HEAD_START, HEAD_END, len(HEAD_END))
    text, n_bridge = cut(text, BRIDGE_START, BRIDGE_END, len(BRIDGE_END))

    if n_head == 0 and n_bridge == 0:
        raise SystemExit("That file has no harness in it. Either it was already\n"
                         "merged, or it is not the design file. Nothing was written.")

    leftovers = [w for w in ("__DESIGN_NOTE", "dh-bar", "dh-pick", "window.__S",
                             "DESIGN-HARNESS", "DESIGN-BRIDGE") if w in text]
    if leftovers:
        raise SystemExit("The harness is still partly in there after the cut: "
                         + ", ".join(leftovers) + ".\nNothing was written.")

    missing = [why for needle, why in MUST_KEEP if needle not in text]
    if missing:
        raise SystemExit("The page has lost something it needs:\n  - "
                         + "\n  - ".join(missing)
                         + "\n\nNothing was written. This usually means a whole block was\n"
                           "deleted rather than restyled. Compare against design\\index.html.bak.")

    # Tidy the blank lines the cuts leave behind.
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    if PAGE.exists():
        shutil.copy2(PAGE, BACKUP)
    PAGE.write_text(text, encoding="utf-8")

    print(f"Merged. Removed {n_head} harness block(s) and {n_bridge} bridge block(s).")
    print(f"Previous page saved as {BACKUP.relative_to(ROOT)}")
    print()
    print("Now check it, in this order:")
    print("  node scripts\\check_pages.mjs")
    print("  python scripts\\record_answers.py design\\answers.json")
    print("  node scripts\\render_views.mjs design\\answers.json")
    print("  python -m pytest tests -q")
    print()
    print("If any of those complain, put the old page back with:")
    print(f"  Copy-Item {BACKUP.relative_to(ROOT)} templates\\index.html -Force")


if __name__ == "__main__":
    main()
