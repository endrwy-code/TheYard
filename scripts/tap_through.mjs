/* Tap through the Mini App's buttons and booking controls in a real browser.
 *
 *     python scripts\build_design_file.py
 *     node --experimental-websocket scripts\tap_through.mjs
 *
 * Opens the design file in headless Edge and taps through the button audit
 * of STATE.md decision 115 and the people list of 117–118 — Up next, the
 * board, the escape booking page, Add / Enter / Edit / ×, the jam room's
 * instruments — checking where each lands and what state it leaves. Writes
 * are refused by the design file, so it stops short of the server saying
 * yes. Prints OK / !! per step and exits 1 on any failure.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { tmpdir } from "node:os";

const SP = process.argv[2] || tmpdir();
const EDGE = [
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
].find((p) => existsSync(p));
if (!EDGE) { console.log("Needs Microsoft Edge or Google Chrome installed."); process.exit(1); }
const PAGE_URL = new URL("../design/the-yard-design.html", import.meta.url).href + "#state=2";
const PORT = 9334;
const edge = spawn(EDGE, ["--headless=new", "--disable-gpu", `--user-data-dir=${SP}\\edgeprofile-flows`,
  `--remote-debugging-port=${PORT}`, "--window-size=500,1000", PAGE_URL], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets = [];
for (let i = 0; i < 40; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json(); if (targets.some((t) => t.type === "page")) break; } catch {}
  await sleep(250);
}
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const pending = new Map(); const errors = [];
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: `(async () => { ${expr} })()`, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return "THREW: " + r.result.exceptionDetails.exception?.description;
  return r.result?.result?.value;
};
await send("Runtime.enable");
await sleep(2500);

let fails = 0;
const check = (label, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) fails++;
  console.log(`${ok ? "OK " : "!! "} ${label}: ${JSON.stringify(got)}${ok ? "" : "  (wanted " + JSON.stringify(want) + ")"}`);
};
const tick = "await new Promise(r => setTimeout(r, 400));";

// 1. Home -> Up next -> Your bookings.
check("Up next opens", await ev(`document.querySelector('.next.live').click(); ${tick} return __S.view;`), "mybookings");
await ev(`document.getElementById('navback').click(); ${tick}`);
check("Back returns", await ev(`return __S.view;`), "home");

// 1b. Nothing booked: the card still opens Your bookings (decision 127).
await ev(`window.__me = JSON.stringify(__S.me); __S.me.escape_booking = null; __S.me.jam_bookings = []; __render();`);
check("empty card reads None", await ev(`return document.querySelector('.next.live .next-time').textContent;`), "None");
check("empty card opens", await ev(`document.querySelector('.next.live').click(); ${tick} return [__S.view, !!document.querySelector('.bk-hero'), document.querySelectorAll('.hold.empty').length];`), ["mybookings", true, 2]);
await ev(`document.getElementById('navback').click(); ${tick}`);
await ev(`__S.me = JSON.parse(window.__me); __render();`);

// 2. Board, someone who already holds a game: a free time says so and stays.
await ev(`__go('esc'); ${tick}`);
check("free time while holding a game stays on the board",
  await ev(`document.querySelector('.game.live').click(); ${tick} return [__S.view, document.getElementById('toast').textContent];`),
  ["esc", "You already have a game. Cancel it on your ticket to move."]);
check("your time opens the ticket", await ev(`document.querySelector('.game.mine').click(); ${tick} return __S.view;`), "ticket");
check("ticket has no All games / Everything you hold", await ev(`return /All games|Everything you hold/.test(document.getElementById('screen').innerText);`), false);
await ev(`document.getElementById('navback').click(); ${tick}`);

// 3. Board, someone with no game: a free time opens its own page.
await ev(`__S.esc.my_booking = null; __render();`);
check("free time opens the booking page", await ev(`document.querySelector('.game.live').click(); ${tick} return __S.view;`), "escbook");
check("the Book button is there", await ev(`return !document.getElementById('mainsheet').hidden && document.getElementById('mainbtn').textContent;`), "Book 5:30 PM");
await ev(`const b = document.getElementById('friendbox'); b.value = '@Jon_Tan'; document.getElementById('friendadd').click(); ${tick}`);
check("Add puts them in the list", await ev(`return [__S.draft, document.getElementById('mainbtn').textContent];`), [["jon_tan"], "Book 5:30 PM for 2"]);
await ev(`const b = document.getElementById('friendbox'); b.value = 'heidi2'; b.dispatchEvent(new KeyboardEvent('keydown', { key:'Enter' })); ${tick}`);
check("Enter adds too", await ev(`return __S.draft;`), ["jon_tan", "heidi2"]);
await ev(`document.querySelector('[data-redraft="jon_tan"]').click(); ${tick}`);
check("Edit takes them out and back into the box", await ev(`return [__S.draft, document.getElementById('friendbox').value, document.activeElement.id];`), [["heidi2"], "jon_tan", "friendbox"]);
await ev(`document.getElementById('friendbox').value = 'jon_tann'; document.getElementById('friendadd').click(); ${tick}`);
await ev(`document.querySelector('[data-undraft="heidi2"]').click(); ${tick}`);
check("x removes", await ev(`return __S.draft;`), ["jon_tann"]);
check("Back goes to the board", await ev(`document.getElementById('navback').click(); ${tick} return __S.view;`), "esc");
check("names come with you to another time", await ev(`__S.esc.my_booking = null; __render(); document.querySelectorAll('.game.live')[1].click(); ${tick} return [__S.view, __S.draft];`), ["escbook", ["jon_tann"]]);

// 4. Jam: a typed name survives tapping an instrument; Add clears the box.
await ev(`__go('jam'); ${tick}`);
check("jam: your slot opens its ticket", await ev(`document.querySelector('.jamslot.mine').click(); ${tick} return [__S.view, /^JAM-/.test(__S.openJam || '')];`), ["jamticket", true]);
await ev(`document.getElementById('navback').click(); ${tick}`);
await ev(`document.querySelector('.jamslot.live').click(); ${tick}`);
await ev(`document.querySelector('[data-kit="bass"]').click(); ${tick}`);
await ev(`document.getElementById('jambox').value = 'drummer1'; document.querySelector('[data-guestkit="drums"]').click(); ${tick}`);
check("typed name kept after tapping an instrument", await ev(`return [document.getElementById('jambox').value, __S.jamGuestKit];`), ["drummer1", "drums"]);
await ev(`document.getElementById('jamguestadd').click(); ${tick}`);
check("Add stages them and clears the box", await ev(`return [__S.jamGuests, document.getElementById('jambox').value];`), [[{ handle: "drummer1", instrument: "drums" }], ""]);
await ev(`document.querySelector('[data-reguest="drummer1"]').click(); ${tick}`);
check("jam Edit refills name and instrument", await ev(`return [__S.jamGuests.length, document.getElementById('jambox').value, __S.jamGuestKit];`), [0, "drummer1", "drums"]);

console.log("page errors:", errors.length ? errors : "none");
console.log("FAILS:", fails);
ws.close(); edge.kill(); process.exit(fails ? 1 : 0);
