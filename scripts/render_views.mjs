/* Render every Mini App screen from real server answers, in Node.
 *
 * The page is one file with inline JS. Pull the script out, stub the few
 * browser things it touches, feed it recorded answers from the real API,
 * and call each VIEWS.* function. A template error becomes a thrown
 * exception here instead of a blank screen on somebody's phone.
 */
import { readFileSync } from "node:fs";
import vm from "node:vm";

const html = readFileSync("templates/index.html", "utf8");
const code = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)]
  .map((m) => m[1]).join("\n");

const answers = JSON.parse(readFileSync(process.argv[2], "utf8"));

const el = () => ({
  classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
  style: {}, dataset: {}, querySelectorAll: () => [], appendChild(){},
  addEventListener(){}, focus(){}, set innerHTML(v){}, get innerHTML(){ return ""; },
  set textContent(v){}, get textContent(){ return ""; }, hidden: false, value: "",
  scrollTop: 0, onclick: null, oninput: null, onchange: null, remove(){},
});

const sandbox = {
  console,
  document: {
    getElementById: el, querySelector: el, querySelectorAll: () => [],
    createElement: el, body: el(), addEventListener(){}, activeElement: null,
  },
  window: { addEventListener(){}, location:{ origin:"https://x" }, matchMedia:()=>({matches:false}) },
  navigator: { userAgent: "node" },
  location: { origin: "https://x", search: "" },
  setTimeout, clearTimeout, setInterval: () => 0, clearInterval,
  requestAnimationFrame: (f) => f(),
  fetch: async () => ({ ok: true, json: async () => ({ ok: true, data: {} }) }),
  URL: { createObjectURL: () => "blob:x", revokeObjectURL(){} },
  Blob: class {},
  alert(){}, confirm: () => true,
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
// `S` and `VIEWS` are const inside the script, so they never land on the
// sandbox's global object. Hand them out explicitly.
vm.runInContext(code + "\n;globalThis.__S = S; globalThis.__VIEWS = VIEWS;",
                sandbox, { timeout: 5000 });
sandbox.VIEWS = sandbox.__VIEWS;

const S = sandbox.__S;
S.session = answers.session;
S.me = answers.me;
S.esc = answers.esc;
S.jam = answers.jam;
S.phone = answers.phone;

let bad = 0;

// States the recorded user never reaches on their own, built from it.
const openSlot = answers.esc.slots.find((s) => s.status === "open") || answers.esc.slots[0];
const notBooked = { ...answers.esc, my_booking: null };
const eb = answers.me.escape_booking;
const asGuest = { ...answers.me, escape_booking: { ...eb, i_am_owner: false,
  booked_by: { handle: "joncjy", name: "Jon Tan", me: false },
  group: eb.group.map((g) => ({ ...g, owner: !g.me, removable: false })), can_add: false } };
const locked = { ...answers.me, escape_booking: { ...eb, locked: true, can_add: false, can_leave: false,
  group: eb.group.map((g) => ({ ...g, removable: false })) } };
const jb = answers.me.jam_bookings[0];
const sharedRoom = { ...answers.me, jam_bookings: [{ ...jb, line_up: [...jb.line_up,
  { handle: "stranger", name: "Sam Lee", instrument: "keys", instrument_label: "Keyboard", me: false, mine_to_remove: false }] }] };
// The phone's own screen (decision 130), in each state the server can answer.
const soon = (m) => new Date(Date.now() + m * 60000).toISOString();
const phoneAs = (code) => ({ ...answers.phone, code, game_starts_at: soon(10), lock_at: soon(22) });
const noMessages = { ...answers.me, can_message: false };
const jamSlot = answers.jam.slots[0];
const jamTaken = { ...answers.jam, slots: answers.jam.slots.map((s) =>
  s.id === jamSlot.id ? { ...s, free: ["acoustic", "electric", "keys"] } : s) };

const cases = [
  ["gate", {}],
  ["home", {}],
  ["home (nothing booked)", { me: { ...answers.me, escape_booking: null, jam_bookings: [] } }],
  ["food", {}],
  ["food (pastry collected)", { me: { ...answers.me, claims: { ...answers.me.claims,
    pastry: { claimed: true, at: "2026-09-24T19:42:00+08:00", variant: "tart", variant_label: "Mini Tart" } } } }],
  ["esc", {}],
  ["escbook", { esc: notBooked, pickedSlot: openSlot.id, draft: [], badFriends: [] }],
  ["escbook (two names)", { esc: notBooked, pickedSlot: openSlot.id, draft: ["heidily", "joncjy"], badFriends: [] }],
  ["escbook (a name refused)", { esc: notBooked, pickedSlot: openSlot.id, draft: ["nobody"], badFriends: ["nobody"] }],
  ["escbook (time gone)", { esc: notBooked, pickedSlot: -1, draft: [] }],
  ["jam", {}],
  ["jambook", { pickedJam: answers.jam.slots[0].id }],
  ["jambook (instrument picked)", { pickedJam: answers.jam.slots[0].id, jamPick: "bass" }],
  ["jambook (+ a guest)", { pickedJam: answers.jam.slots[0].id, jamPick: "bass",
                            jamGuests: [{ handle: "heidily", instrument: "drums" }] }],
  ["jambook (some taken)", { jam: jamTaken, pickedJam: jamSlot.id, jamPick: "keys",
                             jamGuests: [{ handle: "heidily", instrument: "acoustic" }] }],
  ["mybookings", {}],
  ["mybookings (empty)", { me: { ...answers.me, escape_booking: null, jam_bookings: [] } }],
  ["ticket", {}],
  ["ticket (as a guest)", { me: asGuest }],
  ["ticket (locked)", { me: locked }],
  ["ticket (can't message them)", { me: noMessages }],
  ["phone (open)", { phone: phoneAs(null) }],
  ["phone (not yet)", { phone: phoneAs("NOT_YET") }],
  ["phone (locked by the GM)", { phone: phoneAs("PHONE_LOCKED") }],
  ["phone (time's up)", { phone: phoneAs("RELOCKED") }],
  ["phone (not on this laptop)", { phone: phoneAs("PHONE_OFF") }],
  ["phone (no game)", { phone: phoneAs("NO_BOOKING") }],
  ["jamticket", { openJam: jb.ref }],
  ["jamticket (another group in the room)", { me: sharedRoom, openJam: jb.ref }],
  ["prices", {}],
  ["help", {}],
  ["help (payments not checked)", { me: { ...answers.me,
    event: { ...answers.me.event, payment_required: false } } }],
  ["floorplan", {}],
  ["bookings (old deep link)", {}],
];

// What each screen must, or must no longer, say. The fine print removed on
// 21 Sep (STATE.md decision 119) must not creep back.
const GONE = ["Grab a time", "Show the QR at the counter", "One slot each", "going spare",
  "Your mates need", "Whoever you add", "Open either one", "Yours to change until",
  "Up to 6 of you", "Everything you hold</button>", "All games", "All slots",
  // The empty Up next card was a paragraph you couldn't tap (decision 127).
  "Nothing in the diary yet"];
const MUST = {
  "home": ['data-go="mybookings"', 'data-go="floorplan"', 'data-go="prices"', "pastry, photo strip and vinyl crafting"],
  // 22 Sep (STATE.md 132): three things on the pass, the pastry's kinds
  // under its name, the kind that went once it's collected; a price list and
  // a floorplan; the places from Settings on both tickets.
  "food": ["Vinyl Crafting", "Mini tart, brownie, cookie or shiopan", "Your first strip"],
  "food (pastry collected)": ["Mini Tart", "Collected"],
  "help": ['name="helpfaq"', 'data-go="floorplan"', 'data-go="prices"', "Board Games",
           "You haven’t seen my payment."],
  // With payment unchecked, Help stops sending people to the desk about it.
  "help (payments not checked)": ['data-go="prices"', "Board Games"],
  // The price list is a screen now: the groups as cards, the photograph in
  // its own colours, and what entry already covers underneath.
  "prices": ["price-row", "Mini Tart", "$2.50", "MUTED. Gelato", "Waffle Bites",
             "shot-prices", "Already yours"],
  // The map moves inside a fixed frame now: pinch, double-tap, drag
  // (23 Sep, STATE.md 135). No zoom button, and no zoomed-page state.
  "floorplan": ['id="plan"', 'id="planimg"', "floorplan.png",
                "marked Registration on the plan"],
  "jamticket": ["Heaven 2"],
  "home (nothing booked)": ['data-go="mybookings"', ">None<", "Book something!"],
  // The phone lives on its own screen now, reached from the bot's message.
  "ticket (can't message them)": ["Kai Chen’s phone", "that’s how Kai Chen’s phone reaches you"],
  "phone (open)": ['id="openphone"', 'id="openphonetab"', "min left", "Unlocked"],
  "phone (not yet)": ["Not yet", "Your game starts", "Kai Chen’s phone opens at your booked time"],
  "phone (locked by the GM)": ["Locked", "has locked Kai Chen’s phone"],
  "phone (time's up)": ["Time’s up"],
  "phone (not on this laptop)": ["Something’s wrong", "isn’t loading"],
  "phone (no game)": ["No game booked"],
  "mybookings (empty)": ["bk-hero", ">None<", "Book something!", "hold empty room-esc", "hold empty room-jam"],
  "escbook (two names)": ['data-redraft="heidily"', 'data-undraft="joncjy"', 'id="friendadd"'],
  "ticket": ["You can change this anytime, until 5 minutes before your booking.",
             "You can cancel anytime, until 30 minutes before your booking.", "Kai Chen’s phone",
             "The escape room entrance"],
  "ticket (as a guest)": ["Booked by", "prow locked"],
  "ticket (locked)": ["Changes are closed."],
  "jamticket (another group in the room)": ["prow locked"],
  "mybookings": ["bk-hero", "room-esc", "room-jam"],
  // Two taken, you, one friend: four of five, and the last instrument is
  // picked for the next friend without asking.
  "jambook (some taken)": [">Taken<", "4 of 5", 'class="kitchip on" data-guestkit="electric"'],
};
// What a screen must no longer say. The escape board's phone card went on
// 22 Sep (decision 130): the bot's message is the only way to the phone.
const NOT = {
  "help (payments not checked)": ["You haven’t seen my payment."],
  "floorplan": ['id="planzoom"', "Fit to screen"],
  "esc": ['id="openphone"', 'id="openphonetab"', 'class="phone"'],
  "ticket": ["with the phone", "escape-room door", "Where you start",
             "Inside the flat", "At the desk"],
  // The ring before each pass item read as a tick box; it went on 22 Sep.
  "food": ['class="hole"', "Cookie or Pastry"],
};

for (const [name, patch] of cases) {
  const view = name.split(" ")[0];
  const saved = {};
  for (const k of Object.keys(patch)) { saved[k] = S[k]; S[k] = patch[k]; }
  try {
    const out = sandbox.VIEWS[view]();
    if (typeof out !== "string" || out.length < 30) throw new Error("empty render");
    const back = GONE.concat(NOT[name] || []).filter((s) => out.includes(s));
    const missing = (MUST[name] || []).filter((s) => !out.includes(s));
    if (back.length || missing.length) {
      if (back.length) console.log(`!!  ${name}: still says ${back.map((s) => JSON.stringify(s)).join(", ")}`);
      if (missing.length) console.log(`!!  ${name}: missing ${missing.map((s) => JSON.stringify(s)).join(", ")}`);
      bad++;
    } else if (/undefined|\[object Object\]|NaN/.test(out)) {
      console.log(`!!  ${name}: rendered but contains undefined / [object Object] / NaN`);
      const m = out.match(/.{0,70}(undefined|\[object Object\]|NaN).{0,70}/);
      console.log("       …" + (m ? m[0].replace(/\s+/g, " ") : ""));
      bad++;
    } else {
      console.log(`OK  ${name} (${out.length} chars)`);
    }
  } catch (e) {
    console.log(`!!  ${name}: ${e.message}`);
    bad++;
  }
  for (const k of Object.keys(patch)) S[k] = saved[k];
}
console.log("\nFAILURES:", bad);
process.exit(bad ? 1 : 0);
