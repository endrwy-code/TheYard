"""Build a standalone design copy of the Mini App.

    python scripts\\build_design_file.py

Writes `design\\the-yard-design.html`: one file you can open by
double-clicking it, or hand to a design tool. No server, no Telegram, no
database. Every screen is reachable from a picker in the corner, including
the empty and error states you would otherwise have to arrange by hand.

**Nothing in the page itself is edited.** Everything this adds sits inside
marked blocks, and the harness fixes image paths and stubs the network at
run time rather than rewriting the markup. That is what makes
`merge_design.py` able to take your edited file and put it back safely: it
deletes the marked blocks and what is left is the page.

So: restyle freely, move markup around, rewrite the CSS, add animations.
Just leave the marked blocks alone.
"""

import base64
import json
import mimetypes
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "templates" / "index.html"
OUT_DIR = ROOT / "design"
OUT = OUT_DIR / "the-yard-design.html"
ANSWERS = OUT_DIR / "answers.json"

HEAD_START = "<!-- ===== DESIGN-HARNESS START — deleted by merge_design.py ===== -->"
HEAD_END = "<!-- ===== DESIGN-HARNESS END ===== -->"
BRIDGE_START = "/* ===== DESIGN-BRIDGE START — deleted by merge_design.py ===== */"
BRIDGE_END = "/* ===== DESIGN-BRIDGE END ===== */"


def data_uri(path):
    kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{kind};base64," + base64.b64encode(path.read_bytes()).decode()


def placeholder_shot():
    """A neutral photograph stand-in, so the photo treatment can be designed
    before the real pictures exist. Deliberately a plain gradient with a
    figure in it: enough shape for the halftone to bite on."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#d8d3c8"/><stop offset="1" stop-color="#2a2622"/>'
        "</linearGradient></defs>"
        '<rect width="1600" height="1000" fill="url(#g)"/>'
        '<circle cx="1120" cy="300" r="150" fill="#00000055"/>'
        '<path d="M120 1000 L420 380 L720 1000 Z" fill="#0000004d"/>'
        '<path d="M620 1000 L980 520 L1340 1000 Z" fill="#00000033"/>'
        '<rect x="0" y="880" width="1600" height="120" fill="#00000066"/>'
        '<text x="60" y="120" font-family="Arial" font-size="54" fill="#00000055">'
        "PLACEHOLDER</text></svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def record_answers():
    """Ask the real app for real answers, so the design copy shows real
    names, real times and real edge cases rather than invented ones."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    recorder = ROOT / "scripts" / "record_answers.py"
    proc = subprocess.run([sys.executable, str(recorder), str(ANSWERS)],
                          capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit("Could not record answers — is the venv active?")
    return json.loads(ANSWERS.read_text(encoding="utf-8"))


def build():
    page = PAGE.read_text(encoding="utf-8")
    answers = record_answers()

    assets = {}
    logo = ROOT / "static" / "yard-logo.png"
    if logo.exists():
        assets["/static/yard-logo.png"] = data_uri(logo)
    plan = ROOT / "static" / "floorplan.png"            # the Floorplan screen (STATE.md 132)
    if plan.exists():
        assets["/static/floorplan.png"] = data_uri(plan)
    shots_dir = ROOT / "static" / "shots"
    real_shots = {}
    for f in sorted(shots_dir.glob("*")) if shots_dir.exists() else []:
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            real_shots[f"/static/shots/{f.name}"] = data_uri(f)
    assets.update(real_shots)
    # The answers are recorded against an empty photo folder, so point the
    # screens at the real files here — otherwise the design copy embeds the
    # photographs and then never shows them.
    if real_shots:
        shots = answers.setdefault("me", {}).setdefault("event", {}).setdefault("shots", {})
        for path in real_shots:
            shots.setdefault(Path(path).stem, path)

    # If the organiser has not supplied photographs yet, give every screen a
    # placeholder so the treatment can be designed now rather than later.
    if not real_shots:
        for name in ("home", "pass", "esc", "jam", "help"):
            answers.setdefault("me", {}).setdefault("event", {}).setdefault("shots", {})
            answers["me"]["event"]["shots"][name] = f"/static/shots/{name}.jpg"
            assets[f"/static/shots/{name}.jpg"] = placeholder_shot()

    harness = f"""{HEAD_START}
<script>
/* Stand-ins for the three things this page normally gets from outside:
   Telegram, the server, and /static. Nothing here is part of the app. */
(function(){{
  var ASSETS = {json.dumps(assets)};
  var A = {json.dumps(answers)};

  /* 1. Telegram. Enough of the SDK that the page boots and the buttons that
     call into it do not throw. */
  window.Telegram = {{ WebApp: {{
    initData: 'design-preview', initDataUnsafe: {{ user: {{ username: 'maxi_muslim' }} }},
    ready: function(){{}}, expand: function(){{}}, close: function(){{}},
    disableVerticalSwipes: function(){{}}, enableVerticalSwipes: function(){{}},
    openLink: function(u){{ window.open(u, '_blank'); }},
    requestWriteAccess: null,
    HapticFeedback: {{ notificationOccurred: function(){{}}, impactOccurred: function(){{}} }},
    BackButton: {{ show: function(){{}}, hide: function(){{}}, onClick: function(){{}} }},
    MainButton: {{ show: function(){{}}, hide: function(){{}}, setText: function(){{}}, onClick: function(){{}} }},
    themeParams: {{}}, colorScheme: 'light',
    setHeaderColor: function(){{}}, setBackgroundColor: function(){{}}
  }} }};

  /* 2. The server. Recorded answers for the reads; a polite refusal for
     anything that would change data, because nothing here is real. */
  var READS = {{
    'POST /api/session': A.session,
    'GET /api/me': A.me,
    'GET /api/escape/slots': A.esc,
    'GET /api/jam/slots': A.jam,
    'GET /api/escape/phone/status': A.phone
  }};
  window.__DESIGN_NOTE = function(msg){{
    var n = document.getElementById('dh-note');
    if (!n) return;
    n.textContent = msg; n.hidden = false;
    clearTimeout(window.__dhT);
    window.__dhT = setTimeout(function(){{ n.hidden = true; }}, 2600);
  }};
  window.fetch = function(path, opts){{
    opts = opts || {{}};
    var key = (opts.method || 'GET') + ' ' + String(path).split('?')[0];
    var body = READS[key];
    if (body !== undefined){{
      return Promise.resolve(new Response(
        JSON.stringify({{ ok: true, data: body, server_time: new Date().toISOString() }}),
        {{ status: 200, headers: {{ 'Content-Type': 'application/json' }} }}));
    }}
    window.__DESIGN_NOTE('Preview only — "' + key + '" does not run here.');
    return Promise.resolve(new Response(
      JSON.stringify({{ ok: false, error: {{ code: 'DESIGN_PREVIEW',
        message: 'This is a design preview. Nothing is saved.' }} }}),
      {{ status: 200, headers: {{ 'Content-Type': 'application/json' }} }}));
  }};

  /* 3. /static. Rewritten at run time so the markup keeps its real paths and
     the merge back stays a plain deletion. */
  function fixAssets(){{
    document.querySelectorAll('img[src^="/static/"]').forEach(function(img){{
      var key = img.getAttribute('src').split('?')[0];   // photos carry ?v=
      if (ASSETS[key]) img.src = ASSETS[key];
    }});
  }}
  var css = document.createElement('style');
  css.textContent = ASSETS['/static/yard-logo.png']
    ? ".navlogo{{-webkit-mask-image:url('" + ASSETS['/static/yard-logo.png'] + "');"
      + "mask-image:url('" + ASSETS['/static/yard-logo.png'] + "')}}"
    : '';
  document.addEventListener('DOMContentLoaded', function(){{
    document.head.appendChild(css);
    fixAssets();
    new MutationObserver(fixAssets).observe(document.documentElement,
      {{ childList: true, subtree: true }});
  }});
}})();
</script>
{HEAD_END}"""

    # No leading newline, one trailing newline. `merge_design.cut` removes a
    # block plus exactly one newline after it, so every insertion has to be
    # shaped this way for the round trip to come back byte-identical.
    bridge = f"""{BRIDGE_START}
/* Hands the picker a way in. `S`, `VIEWS`, `render` and `go` are const in
   this scope, so they never reach the window by themselves. */
window.__S = S; window.__VIEWS = VIEWS; window.__render = render; window.__go = go;
{BRIDGE_END}
"""

    picker = HEAD_START + PICKER + "\n" + HEAD_END

    out = page
    out = out.replace('<script src="https://telegram.org/js/telegram-web-app.js"></script>',
                      '<script src="https://telegram.org/js/telegram-web-app.js"></script>\n'
                      + harness, 1)
    # The bridge goes at the very end of the page's own script block.
    last = out.rindex("</script>")
    out = out[:last] + bridge + out[last:]
    out = out.replace("</body>", picker + "\n</body>", 1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(out, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}  ({len(out) // 1024} KB)")
    print(f"  photographs: {'the real ones' if real_shots else 'placeholders (none supplied yet)'}")
    print(f"  screens in the picker: {len(STATES)}")
    print()
    print("Open it by double-clicking. Everything works offline.")
    print("When you are done:  python scripts\\merge_design.py")


# The states worth designing against — the same list the render check uses,
# plus the ones that only appear when something is wrong or empty.
STATES = [
    ("Gate — welcome", "gate", {}),
    ("Gate — not on the list", "gate", {"session": None, "gateCode": "NOT_ON_LIST"}),
    ("Home", "home", {}),
    ("Home — nothing booked", "home", {"__me": {"escape_booking": None, "jam_bookings": []}}),
    ("Home — payment not seen", "home", {"__me": {"payment_status": "missing"}}),
    ("Your pass", "food", {}),
    ("Your pass — pastry collected", "food", {"__me": {"claims": {
        "pastry": {"claimed": True, "at": "2026-09-24T19:42:00+08:00", "variant": "tart",
                   "variant_label": "Mini Tart", "staff": "Wei", "station": "Booth 1"},
        "photo": {"claimed": False}, "vinyl": {"claimed": False}}}}),
    ("Your pass — not verified", "food", {"__me": {"payment_ok": False}}),
    ("The Last Guest", "esc", {}),
    ("Escape — booking page", "escbook", {"__pickSlot": True}),
    ("Escape — booking page, two names", "escbook", {"__pickSlot": True,
                                                     "draft": ["heidily", "joncjy"]}),
    ("Your ticket", "ticket", {}),
    ("Jam ticket", "jamticket", {}),
    ("Jamming studio — board", "jam", {}),
    ("Jam — pick instrument", "jambook", {"__pickJam": True}),
    ("Jam — instrument chosen", "jambook", {"__pickJam": True, "jamPick": "bass"}),
    ("Jam — with a friend", "jambook", {"__pickJam": True, "jamPick": "bass",
                                        "jamGuests": [{"handle": "heidily", "instrument": "drums"}]}),
    ("My bookings", "mybookings", {}),
    ("My bookings — empty", "mybookings", {"__me": {"escape_booking": None, "jam_bookings": []}}),
    ("Help", "help", {}),
    ("Help — price list open", "help", {"__open": 0}),
    ("Floorplan", "floorplan", {}),
    ("Floorplan — zoomed", "floorplan", {"planZoom": True}),
]

PICKER = """
<style>
  /* The picker is not part of the app. Delete this block and it is gone. */
  #dh-bar{position:fixed;left:0;right:0;bottom:0;z-index:99999;display:flex;gap:8px;
    align-items:center;padding:8px 10px;background:#101010;color:#F2EFE8;
    font:12px/1.2 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
  #dh-bar select{flex:1;min-width:0;background:#26262A;color:#F2EFE8;border:0;
    border-radius:8px;padding:8px 10px;font:inherit}
  #dh-bar button{background:#AE7338;color:#fff;border:0;border-radius:8px;
    padding:8px 11px;font:inherit;font-weight:700;cursor:pointer}
  #dh-bar .dh-tag{opacity:.55;letter-spacing:.14em;text-transform:uppercase;font-size:9px}
  #dh-note{position:fixed;left:10px;right:10px;bottom:52px;z-index:99999;background:#AE7338;
    color:#fff;border-radius:10px;padding:9px 12px;font:12px/1.35 -apple-system,sans-serif}
  body{padding-bottom:46px !important}
</style>
<div id="dh-note" hidden></div>
<div id="dh-bar">
  <span class="dh-tag">Preview</span>
  <select id="dh-pick"></select>
  <button id="dh-again" title="Re-apply this state">Reset</button>
</div>
<script>
(function(){
  var STATES = __STATES__;
  var sel = document.getElementById('dh-pick');
  STATES.forEach(function(s, i){
    var o = document.createElement('option');
    o.value = i; o.textContent = s[0]; sel.appendChild(o);
  });

  var BASE = null;
  function snapshot(){
    if (BASE) return;
    BASE = { me: JSON.parse(JSON.stringify(window.__S.me || null)) };
  }

  function apply(i){
    var S = window.__S, spec = STATES[i][2], view = STATES[i][1];
    snapshot();
    // Back to a known state before each one, so they do not stack up.
    S.me = JSON.parse(JSON.stringify(BASE.me));
    S.pickedSlot = null; S.pickedJam = null; S.jamPick = null;
    S.jamGuests = []; S.jamGuestKit = null; S.jamAddKit = null;
    S.draft = []; S.badFriends = []; S.booked = null; S.gateCode = null; S.planZoom = false;
    S.stack = view === 'home' || view === 'gate' ? [] : [{ view:'home', scroll:0 }];

    Object.keys(spec).forEach(function(k){
      if (k === '__me'){ Object.assign(S.me, spec[k]); }
      else if (k === '__open'){ /* after the render, below */ }
      else if (k === '__pickSlot'){ S.pickedSlot = (S.esc.slots.find(function(x){
        return x.status === 'open'; }) || S.esc.slots[0]).id; }
      else if (k === '__pickJam'){ S.pickedJam = (S.jam.slots.find(function(x){
        return x.status === 'open'; }) || S.jam.slots[0]).id; }
      else { S[k] = spec[k]; }
    });
    S.view = view;
    window.__render();
    // A Help question shown open, e.g. the price list.
    if ('__open' in spec){
      var d = document.querySelectorAll('.help-faq details')[spec.__open];
      if (d) d.open = true;
    }
  }

  sel.onchange = function(){ apply(Number(sel.value)); };
  document.getElementById('dh-again').onclick = function(){ apply(Number(sel.value)); };

  // The page only asks for what its current screen needs, and it starts on
  // the gate, so it never has all of this on its own. Ask for it here (the
  // network in this file is the recorded answers), then open a state.
  function load(path, key){
    return fetch(path).then(function(r){ return r.json(); })
      .then(function(j){ if (j.ok) window.__S[key] = j.data; });
  }
  Promise.all([load('/api/me', 'me'), load('/api/escape/slots', 'esc'),
               load('/api/jam/slots', 'jam'), load('/api/escape/phone/status', 'phone')])
    .then(function(){
      // Home, unless the address asks for another state (#state=5), which
      // is how a screenshot tool opens a given screen.
      var asked = Number((location.hash.match(/state=(\\d+)/) || [])[1]);
      var i = asked >= 0 && asked < STATES.length ? asked : 2;
      sel.value = i;
      apply(i);
    });
})();
</script>
"""

PICKER = PICKER.replace("__STATES__", json.dumps(STATES))


if __name__ == "__main__":
    build()
