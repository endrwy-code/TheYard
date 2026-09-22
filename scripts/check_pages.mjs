/* Syntax-check the inline <script> of each page.
 *
 * Both pages are one HTML file with inline CSS and JS (§3 rule 6), so a typo
 * in the JavaScript is invisible until a browser runs it — and on event day
 * the first browser to run it belongs to an attendee. `node --check` cannot
 * read HTML, so pull the script out and check that.
 *
 *   node scripts/check_pages.mjs
 */
import { readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PAGES = ["templates/index.html", "templates/admin.html"];
const dir = mkdtempSync(join(tmpdir(), "yard-check-"));
let bad = 0;

for (const page of PAGES) {
  const html = readFileSync(page, "utf8");
  const blocks = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)]
    .map((m) => m[1]);
  if (!blocks.length) {
    console.log(`${page}: no inline script found`);
    bad++;
    continue;
  }
  blocks.forEach((code, i) => {
    const file = join(dir, `${page.replace(/[\\/]/g, "_")}.${i}.js`);
    writeFileSync(file, code);
    try {
      execFileSync(process.execPath, ["--check", file], { stdio: "pipe" });
      console.log(`${page} block ${i + 1}/${blocks.length}: ok (${code.length} chars)`);
    } catch (e) {
      console.error(`${page} block ${i + 1}: SYNTAX ERROR`);
      console.error(String(e.stderr || e.message));
      bad++;
    }
  });
}
process.exit(bad ? 1 : 0);
