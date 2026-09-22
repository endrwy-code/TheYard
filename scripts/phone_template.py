"""Read / edit the victim's phone, which is a bundle and not a normal page.

`private/phone/the-phone.html` is a generated `.dc.html` artifact: its
JavaScript is gzipped base64 on one enormous line and cannot be edited by
hand. Its *markup*, though, is ordinary HTML held as a JSON string in
`<script type="__bundler/template">`, and the runtime reads that on load. So
the screens can be changed without rebuilding anything — decode the string,
edit the HTML, encode it back.

The one trap is the encoding. The bundler writes `</script>` inside that
string as `<\\u002Fscript>`, because a literal `</script>` would close the
tag it lives in and destroy the file. `json.dumps` does not do that by
itself, so `_encode` re-escapes it, and `load()` refuses to hand anything
over unless re-encoding the untouched string reproduces the file byte for
byte. Never edit the file with a plain search-and-replace.

Usage, from the project root:

    from scripts import phone_template as pt   # or copy it next to your script
    raw, block, markup = pt.load()
    markup = pt.replace_once(markup, "old", "new")
    pt.save(raw, block, markup)
"""
import io
import json
import os
import re
import sys

PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "private", "phone", "the-phone.html")
BLOCK = re.compile(
    r'(<script type="__bundler/template">\s*)(".*?")(\s*</script>)', re.S)


def _encode(text):
    return json.dumps(text, ensure_ascii=False).replace("</", "<\\u002F")


def load(path=PATH):
    raw = io.open(path, encoding="utf-8").read()
    m = BLOCK.search(raw)
    if not m:
        sys.exit("template block not found")
    markup = json.loads(m.group(2))
    if _encode(markup) != m.group(2):
        sys.exit("re-encoding is not byte-identical; refusing to edit")
    return raw, m, markup


def save(raw, m, markup, path=PATH):
    out = raw[:m.start(2)] + _encode(markup) + raw[m.end(2):]
    io.open(path, "w", encoding="utf-8", newline="").write(out)


def replace_once(markup, old, new):
    n = markup.count(old)
    if n != 1:
        sys.exit("expected 1 occurrence, found %d of: %.90s" % (n, old))
    return markup.replace(old, new)


def replace_all(markup, old, new, expect):
    n = markup.count(old)
    if n != expect:
        sys.exit("expected %d occurrences, found %d of: %.90s" % (expect, n, old))
    return markup.replace(old, new)
