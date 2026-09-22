"""The price list on the Mini App's Help screen (22 Sep, STATE.md 132).

It is one Settings row of plain text, so the organiser can change a price on
the night without touching a file. The format is the one they wrote it in:

    Pastries:
    • Mini Tart: $2.50
    Panini: $5 a slice

A line with a `$` in it is a row: the name before the price, the price from
the `$` on. Any other line is a heading. Bullets and blank lines are ignored.
"""

import re

_BULLET = re.compile(r"^[\s•·*\-–—]+")
_TRAILING = re.compile(r"[\s:–—\-]+$")


def parse(text):
    """[{'title': str or None, 'rows': [{'name', 'price'}]}], in order.
    A heading with nothing under it is dropped."""
    sections = []
    current = None
    for raw in str(text or "").splitlines():
        line = _BULLET.sub("", raw).strip()
        if not line:
            continue
        if "$" in line:
            name, price = line.split("$", 1)
            if current is None:
                current = {"title": None, "rows": []}
                sections.append(current)
            current["rows"].append({"name": _TRAILING.sub("", name), "price": "$" + price.strip()})
        else:
            current = {"title": _TRAILING.sub("", line), "rows": []}
            sections.append(current)
    return [s for s in sections if s["rows"]]
