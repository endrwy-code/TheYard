/* Render the console's booth and GM screens in Node, the way
   scripts/render_views.mjs does for the Mini App. A template error here
   beats a blank screen on the counter's phone. */
import { readFileSync } from "node:fs";
import vm from "node:vm";

const html = readFileSync("templates/admin.html", "utf8");
const code = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)]
  .map((m) => m[1]).join("\n");

const el = () => ({
  classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
  // setViewport() reads and writes the <meta> tag's content on every render
  // (24 Sep). Without these the harness dies before it draws anything.
  attrs: {},
  getAttribute(n){ return n in this.attrs ? this.attrs[n] : null; },
  setAttribute(n, v){ this.attrs[n] = String(v); },
  removeAttribute(n){ delete this.attrs[n]; },
  hasAttribute(n){ return n in this.attrs; },
  style: { setProperty(){} }, dataset: {}, querySelectorAll: () => [], appendChild(){},
  addEventListener(){}, focus(){}, set innerHTML(v){}, get innerHTML(){ return ""; },
  set textContent(v){}, get textContent(){ return ""; }, hidden: false, value: "",
  scrollTop: 0, onclick: null, oninput: null, onchange: null, onkeydown: null, remove(){},
  querySelector: () => null, setPointerCapture(){},
});

const store = {};
const sandbox = {
  console,
  document: {
    getElementById: () => el(), querySelector: () => el(), querySelectorAll: () => [],
    createElement: el, body: el(), head: el(), documentElement: el(),
    addEventListener(){}, activeElement: null,
  },
  window: { addEventListener(){}, location:{ origin:"https://x" }, matchMedia:()=>({matches:false}) },
  navigator: { userAgent: "node", mediaDevices: null },
  location: { origin: "https://x", search: "", href: "https://x" },
  localStorage: { getItem: (k) => store[k] ?? null, setItem: (k,v) => { store[k]=v; }, removeItem(k){ delete store[k]; } },
  sessionStorage: { getItem: () => null, setItem(){}, removeItem(){} },
  setTimeout, clearTimeout, setInterval: () => 0, clearInterval,
  requestAnimationFrame: (f) => f(),
  fetch: async () => ({ ok: true, status: 200, headers: { get: () => null }, json: async () => ({ ok: true, data: {} }) }),
  EventSource: class { constructor(){} addEventListener(){} close(){} },
  URL: { createObjectURL: () => "blob:x", revokeObjectURL(){} },
  Blob: class {}, alert(){}, confirm: () => true, prompt: () => "reason",
};
sandbox.window.localStorage = sandbox.localStorage;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
// `S` and `SCREENS` are const inside the page script, so they never land on
// the sandbox's global object. Hand them out explicitly, the way
// scripts/render_views.mjs does.
vm.runInContext(code + ";\nglobalThis.__S = S; globalThis.__SCREENS = SCREENS;"
                     + "\nglobalThis.__SCREENS.__signin = signinView;"
                     + "\nglobalThis.__SCREENS.__kiosk = kioskView;",
                sandbox, { filename: "admin.html", timeout: 5000 });

const S = sandbox.__S;
const SCREENS = sandbox.__SCREENS;
S.session = { role: "mobile", name: "Wei", station: "Counter", csrf_token: "x" };
S.items = [
  { key: "pastry", label: "Pastry", choices: [
    { key: "tart", label: "Mini Tart" }, { key: "brownie", label: "Mini Brownie" },
    { key: "cookie", label: "Mini Cookie" }, { key: "shiopan", label: "Shiopan" }] },
  { key: "photo", label: "Photo Strip", choices: [] },
  { key: "vinyl", label: "Vinyl Crafting", choices: [] },
];

const person = { name: "Heidi Lim", handle: "heidily", tg_first_name: "Heidi",
                 checked_in_at: null, escape: { ref: "ESC-BU7E", starts_at: "2026-09-24T19:05:00+08:00" } };
const claims = (gone) => Object.fromEntries(S.items.map((i) => [i.key,
  gone.includes(i.key) ? { claimed: true, at: "2026-09-24T19:10:00+08:00", variant_label: "Mini Tart",
                           station: "Counter", staff: "Wei" } : { claimed: false }]));

/* ---- The game-master console ---------------------------------------- */

// The timer counts on from the server's figure using S.gmAt, so pin it to
// now: otherwise a running game renders 0:00 and the assertion is nonsense.
S.gmAt = Date.now();

const hints = [
  { key: "drawer", title: "The drawer", line: "Ask whether anybody has tried the desk drawer.",
    optional: false, given: false, given_at: null },
  { key: "tape", title: "The tape", line: "The number is read backwards.",
    optional: false, given: true, given_at: "2026-09-24T19:22:00+08:00" },
  { key: "last", title: "If they are really stuck", line: "Tell them the code is 4-7-1.",
    optional: true, given: false, given_at: null },
];
const player = (over) => ({ id: 1, name: "Heidi Lim", handle: "heidily", in: true,
                            phone_msg: "sent", ...over });
const games = [
  { id: 7, starts_at: "2026-09-24T19:05:00+08:00", booked: 6, state: "in_progress" },
  { id: 8, starts_at: "2026-09-24T19:35:00+08:00", booked: 4, state: "upcoming" },
];
// The shape services/game.py returns, mid-game, with one more to follow.
const gm = (over = {}) => ({
  slot_id: 7, game_number: 9, games_total: 14, games,
  starts_at: "2026-09-24T19:05:00+08:00", state: "in_progress",
  started: true, paused: false, ended: false,
  elapsed_seconds: 540, game_seconds: 1200, remaining_seconds: 660,
  ends_at: "2026-09-24T19:25:00+08:00", relock_at: "2026-09-24T19:27:00+08:00",
  next_game_at: "2026-09-24T19:35:00+08:00",
  phone_open: true, phone_locked: false,
  booked: 2, checked_in: 1,
  people: [player({}), player({ id: 2, name: "Arun Rao", handle: "arunrao", in: false,
                                phone_msg: "waiting" })],
  hints, reset: ["Put the letter back in the drawer", "Set the padlock back to 0-0-0"],
  changeover_minutes: 10, actor_ready: true, ...over,
});

const cases = [
  ["booth (scanning)", "booth", { lookup: null }],
  ["booth (signed in with the PIN alone)", "booth",
   { lookup: null, session: { role: "mobile", name: "", station: "", csrf_token: "x" } }],
  ["booth (nothing collected yet)", "booth", { lookup: { data: { person, payment_ok: true, claims: claims([]),
      can_hand_over: true, stock: null } } }],
  ["booth (pastry already gone)", "booth", { lookup: { data: { person, payment_ok: true, claims: claims(["pastry"]),
      can_hand_over: true, stock: null } } }],
  ["booth (everything collected)", "booth", { lookup: { data: { person: { ...person, checked_in_at: "2026-09-24T18:00:00+08:00" },
      payment_ok: true, claims: claims(["pastry", "photo", "vinyl"]), can_hand_over: true, stock: null } } }],
  ["booth (low stock)", "booth", { lookup: { data: { person, payment_ok: true, claims: claims([]),
      can_hand_over: true, stock: { pastry: { low: true, left: 2, blocks_at_zero: false } } } } }],
  ["booth (unpaid, override)", "booth", { lookup: { data: { person, payment_ok: false, payment_status: "missing",
      claims: claims([]), can_hand_over: false, can_override: true, stock: null } } }],
  ["booth (not a Yard code)", "booth", { lookup: { error: "NOT_A_YARD_CODE" } }],
  ["booth (unknown code)", "booth", { lookup: { error: "UNKNOWN_CODE" } }],

  ["signin (mobile)", "__signin", { signinRole: "mobile", signinErr: "" }],
  ["signin (laptop)", "__signin", { signinRole: "admin", signinErr: "" }],
  ["signin (refused)", "__signin", { signinRole: "mobile", signinErr: "That did not match." }],

  ["gm (no game yet)", "gm", { gmState: null, gmError: "No games are scheduled." }],
  ["gm (before the start)", "gm", { gmState: gm({ state: "upcoming", started: false,
      elapsed_seconds: 0, remaining_seconds: 1200, phone_open: false, next_game_at: null,
      people: [player({ phone_msg: null }), player({ id: 2, name: "Arun Rao", handle: "arunrao",
                                                     in: false, phone_msg: null })] }) }],
  ["gm (running)", "gm", { gmState: gm() }],
  ["gm (paused)", "gm", { gmState: gm({ paused: true }) }],
  ["gm (finished)", "gm", { gmState: gm({ state: "finished", ended: true, paused: false,
      phone_open: false, elapsed_seconds: 1200, remaining_seconds: 0 }) }],
  ["gm (phone locked)", "gm", { gmState: gm({ phone_locked: true }) }],
  ["gm (somebody it can't reach)", "gm", { gmState: gm({
      people: [player({}), player({ id: 2, name: "Arun Rao", handle: "arunrao",
                                    phone_msg: "unreachable" })] }) }],
  ["gm (messages still on testing)", "gm", { gmState: gm({
      people: [player({ phone_msg: "held" })], booked: 1, checked_in: 1 }) }],
  ["gm (nobody booked)", "gm", { gmState: gm({ people: [], booked: 0, checked_in: 0 }) }],
  ["gm (no hint file)", "gm", { gmState: gm({ hints: [] }) }],

  /* Self-serve: the iPad turned round at the door (24 Sep). What matters here
     is as much what is absent as what is present — see NOT below. */
  ["self-serve (waiting)", "__kiosk", { kiosk: true, kioskSaid: null, kioskAsk: null }],
  ["self-serve (checked in)", "__kiosk", { kiosk: true, kioskAsk: null,
    kioskSaid: { tone: "good", mark: "\u2713", big: "You are in, Heidi",
                 small: "Checked in at 7:04pm" } }],
  ["self-serve (already checked in)", "__kiosk", { kiosk: true, kioskAsk: null,
    kioskSaid: { tone: "good", mark: "\u2713", big: "Already checked in",
                 small: "Heidi \u2014 you are all set." } }],
  ["self-serve (see the front desk)", "__kiosk", { kiosk: true, kioskAsk: null,
    kioskSaid: { tone: "warn", mark: "!", big: "Please see the front desk",
                 small: "Heidi \u2014 you are checked in." } }],
  ["self-serve (anything else)", "__kiosk", { kiosk: true, kioskAsk: null,
    kioskSaid: { tone: "bad", mark: "\u00b7", big: "Please see a staff member", small: "" } }],
  ["self-serve (staff unlocking)", "__kiosk", { kiosk: true, kioskSaid: null,
    kioskAsk: { err: "" } }],
  ["self-serve (wrong PIN)", "__kiosk", { kiosk: true, kioskSaid: null,
    kioskAsk: { err: "That did not match." } }],
  ["self-serve (signed out mid-event)", "__kiosk", { kiosk: true, kioskSaid: null,
    kioskAsk: { err: "" }, session: null }],
];

const MUST = {
  "booth (scanning)": ['id="cam"', 'id="vfhint"', 'id="viewfinder"', 'id="codebox"', 'id="lookup"',
                       'id="checkin"', 'id="scannext"', "booth-body scanning",
                       // 24 Sep: flip the camera, and hand the screen over.
                       'id="camflip"', 'id="kioskgo"', "Turn the screen round for guests"],
  "booth (signed in with the PIN alone)": ['id="cam"', 'id="scannext"', "Mobile"],
  "booth (nothing collected yet)": ['id="cam"', 'id="codebox"', 'id="scannext"', "booth-body showing",
                                    'data-hand="photo"', 'data-hand="vinyl"', 'data-variant="tart"',
                                    "Heidi Lim", "Not checked in", "The Last Guest"],
  "booth (pastry already gone)": ["Already collected", "gone-row", 'data-hand="photo"'],
  "booth (everything collected)": ["Everything on this pass has been collected.", "Check in again"],
  "booth (low stock)": ["Stock is low", "2 left"],
  "booth (unpaid, override)": ['data-override="1"', "Override"],
  "booth (not a Yard code)": ['id="scannext"'],
  "booth (unknown code)": ['id="scannext"'],
};
Object.assign(MUST, {
  // 23 Sep: the phone PIN is the whole Mobile sign-in.
  "signin (mobile)": ['id="pin"', 'id="signin"', "Phone PIN", "Mobile", "Laptop"],
  "signin (laptop)": ['id="pw"', 'id="signin"', "Admin password"],
  "signin (refused)": ["That did not match.", 'id="pin"'],
  "gm (no game yet)": ["No game yet", "No games are scheduled."],
  "gm (before the start)": ['id="gmtimer"', "Upcoming", "phone opens at 7:05", "Starts 7:05",
                            'data-hint="drawer"'],
  "gm (running)": ['id="gmpick"', 'id="gmtimer"', "In progress", "phone open until 7:27",
                   "1 of 2 have it", 'data-gm="pause"', 'data-gm="shorten"', 'data-gm="extend"',
                   'data-gm="lock"', 'data-gm="end"', 'data-hint="drawer"', "Given 7:22",
                   "Heidi Lim", "Changeover", "Put the letter back in the drawer"],
  "gm (paused)": ['data-gm="resume"', ">Resume<"],
  "gm (finished)": ["Finished", "phone closed"],
  "gm (phone locked)": ['data-gm="unlock"', "phone locked by you", "Unlock the phone"],
  "gm (somebody it can't reach)": ["can't reach Arun Rao", "desk handset"],
  "gm (messages still on testing)": ["Not sent (test mode)", "Who gets messages"],
  "gm (nobody booked)": ["Nobody is booked on this game."],
  "gm (no hint file)": ["No hint file on this laptop"],

  "self-serve (waiting)": ['id="kiosk"', 'id="cam"', 'id="kioskstaff"', 'id="kioskflip"',
                           "Scan your pass", "Open The Yard in Telegram"],
  "self-serve (checked in)": ["said good", "You are in, Heidi", "Checked in at 7:04pm"],
  "self-serve (already checked in)": ["said good", "Already checked in", "you are all set"],
  "self-serve (see the front desk)": ["said warn", "Please see the front desk",
                                      "you are checked in"],
  "self-serve (anything else)": ["said bad", "Please see a staff member"],
  "self-serve (staff unlocking)": ['id="kioskpin"', 'id="kioskunlock"', 'id="kioskback"',
                                   "Staff only", "phone PIN", ">Unlock<"],
  "self-serve (wrong PIN)": ["That did not match.", 'id="kioskpin"'],
  // No session left, so there is nothing to unlock against: the way back is
  // the sign-in, and the box that would take a PIN is gone with it.
  "self-serve (signed out mid-event)": ["signed out", ">Sign in<", 'id="kioskback"'],
});

// The scanning state must never carry a hand-over button, and a result must
// never claim a half: the split went on 23 Sep.
const NOT = {
  // Neither door asks for a name or a station any more.
  "signin (mobile)": ['id="nm"', 'id="stn"', "Your name", "Where you are"],
  "signin (laptop)": ['id="nm"', 'id="stn"', 'id="pin"'],
  "booth (scanning)": ["data-hand=", "handbox"],
  // No dangling separator where a name used to be.
  "booth (signed in with the PIN alone)": ["GM \u00b7 <", " \u00b7 </span>", "Wei"],
  "booth (nothing collected yet)": ["half ", "— desk", "— flat"],
  "booth (pastry already gone)": ["blocked-item"],
  // Nothing has gone out yet, so the console must not say it has.
  "gm (before the start)": ["have it", "Phone sent", "Phone on its way", 'data-gm="end"'],
  "gm (finished)": ['data-gm="end"', 'data-gm="pause"'],
  "gm (no hint file)": ["data-hint="],
  "self-serve (signed out mid-event)": ['id="kioskpin"', "phone PIN", "admin password"],
};
/* The whole point of the screen. A guest standing in front of an unattended
   iPad must not be able to hand themselves anything, type a code at it, walk
   into the console, sign the device out, or read the last person's details
   off it — so none of that may appear on any self-serve state. */
for (const [name] of cases) {
  if (!name.startsWith("self-serve")) continue;
  NOT[name] = (NOT[name] || []).concat([
    "data-hand=", "handbox", "Hand over", "Override",
    'id="codebox"', 'id="lookup"', 'id="checkin"', 'id="scannext"',
    'id="signout"', "Sign out", "data-screen=", "Settings", "Audit",
    "Heidi Lim", "@heidily", "payment", "Payment",
  ]);
}
// There is no Start to press and no half to stand in, on any GM screen.
for (const [name] of cases) {
  if (!name.startsWith("gm")) continue;
  NOT[name] = (NOT[name] || []).concat(['data-gm="start"', ">Start<", "Split", "half A", "half B"]);
}

let bad = 0;
for (const [name, screen, patch] of cases) {
  const saved = {};
  for (const k of Object.keys(patch)) { saved[k] = S[k]; S[k] = patch[k]; }
  try {
    const out = SCREENS[screen]();
    if (typeof out !== "string" || out.length < 30) throw new Error("empty render");
    const missing = (MUST[name] || []).filter((x) => !out.includes(x));
    const back = (NOT[name] || []).filter((x) => out.includes(x));
    if (missing.length || back.length) {
      if (missing.length) console.log(`!!  ${name}: missing ${missing.map((x) => JSON.stringify(x)).join(", ")}`);
      if (back.length) console.log(`!!  ${name}: still says ${back.map((x) => JSON.stringify(x)).join(", ")}`);
      bad++;
    } else if (/undefined|\[object Object\]|NaN/.test(out)) {
      console.log(`!!  ${name}: contains undefined / [object Object] / NaN`);
      const m = out.match(/.{0,80}(undefined|\[object Object\]|NaN).{0,80}/);
      console.log("       …" + (m ? m[0].replace(/\s+/g, " ") : ""));
      bad++;
    } else {
      if (process.env.DUMP === name) console.log(out);
      console.log(`OK  ${name} (${out.length} chars)`);
    }
  } catch (e) {
    console.log(`!!  ${name}: ${e.message}`);
    bad++;
  }
  for (const k of Object.keys(patch)) S[k] = saved[k];
}
console.log(`\nFAILURES: ${bad}`);
process.exit(bad ? 1 : 0);
