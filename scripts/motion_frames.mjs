/* See the Up next card grow, frame by frame (STATE.md decision 121).
 *
 *     python scripts\build_design_file.py
 *     node --experimental-websocket scripts\motion_frames.mjs <folder>
 *
 * Opens Home in the design file in headless Edge, slows every animation to a
 * tenth of its speed, taps Up next, and saves morph-open-*.png and
 * morph-close-*.png into <folder> (default: the temp folder) through the grow
 * and the shrink back. It prints any page error, and whether the morph flag
 * was left behind. This is the one check in the project that actually looks
 * at the screen; it still is not a phone (see README, "Before you say
 * something is fixed"). Edge will not go narrower than about 500px headless.
 */
import { spawn } from "node:child_process";
import { writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";

const SP = process.argv[2] || tmpdir();
const EDGE = [
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
].find((p) => existsSync(p));
if (!EDGE) { console.log("Needs Microsoft Edge or Google Chrome installed."); process.exit(1); }
const PAGE_URL = new URL("../design/the-yard-design.html", import.meta.url).href + "#state=2";
const PORT = 9333;

const edge = spawn(EDGE, ["--headless=new", "--disable-gpu", "--hide-scrollbars",
  `--user-data-dir=${SP}\\edgeprofile-cdp`, `--remote-debugging-port=${PORT}`,
  "--window-size=500,1000", PAGE_URL], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let targets = [];
for (let i = 0; i < 40; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json(); if (targets.some((t) => t.type === "page")) break; } catch {}
  await sleep(250);
}
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const pending = new Map(); const errors = [];
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
  if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") errors.push(m.params.args.map((a) => a.value || a.description).join(" "));
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expr) => (await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result?.result?.value;
const shot = async (name) => {
  const r = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(`${SP}\\morph-${name}.png`, Buffer.from(r.result.data, "base64"));
};

await send("Runtime.enable"); await send("Page.enable"); await send("Animation.enable");
await sleep(2500);
console.log("view:", await evaluate("__S.view"), "| startViewTransition:", await evaluate("typeof document.startViewTransition"));
await send("Animation.setPlaybackRate", { playbackRate: 0.1 });

// Open: tap the card.
await evaluate("document.querySelector('.next.live').click(); true");
for (const t of [150, 1500, 3000, 4200, 6000]) { await sleep(t - (shot.last || 0)); shot.last = t; await shot("open-" + t); }
await sleep(3000);
console.log("after open -> view:", await evaluate("__S.view"), "| data-morph left:", await evaluate("document.documentElement.dataset.morph || 'none'"),
  "| body.dark:", await evaluate("document.body.classList.contains('dark')"));
await shot("open-end");

// Close: Back.
shot.last = 0;
await evaluate("document.getElementById('navback').click(); true");
for (const t of [150, 1500, 3000, 4200]) { await sleep(t - (shot.last || 0)); shot.last = t; await shot("close-" + t); }
await sleep(3000);
console.log("after close -> view:", await evaluate("__S.view"), "| data-morph left:", await evaluate("document.documentElement.dataset.morph || 'none'"));
await shot("close-end");

// The same trip with nothing booked: the card says None and grows the same
// way (decision 127). Frames are morph-empty-open-* and morph-empty-close-*.
await evaluate("window.__me = JSON.stringify(__S.me); __S.me.escape_booking = null; __S.me.jam_bookings = []; __render(); true");
await sleep(400);
shot.last = 0;
await evaluate("document.querySelector('.next.live').click(); true");
for (const t of [150, 1500, 3000, 4200]) { await sleep(t - (shot.last || 0)); shot.last = t; await shot("empty-open-" + t); }
await sleep(3000);
console.log("empty: after open -> view:", await evaluate("__S.view"), "| data-morph left:", await evaluate("document.documentElement.dataset.morph || 'none'"));
await shot("empty-open-end");
shot.last = 0;
await evaluate("document.getElementById('navback').click(); true");
for (const t of [150, 1500, 3000]) { await sleep(t - (shot.last || 0)); shot.last = t; await shot("empty-close-" + t); }
await sleep(3000);
console.log("empty: after close -> view:", await evaluate("__S.view"), "| data-morph left:", await evaluate("document.documentElement.dataset.morph || 'none'"));
await evaluate("__S.me = JSON.parse(window.__me); __render(); true");

// Any other route must not morph: Home -> pass.
await send("Animation.setPlaybackRate", { playbackRate: 1 });
await evaluate("__go('food'); true");
await sleep(50);
console.log("home -> food morph flag:", await evaluate("document.documentElement.dataset.morph || 'none'"));

console.log("errors:", errors.length ? errors : "none");
ws.close(); edge.kill();
process.exit(0);
