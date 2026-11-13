// One headless Chromium for a build: render Mermaid to static SVG, then check the page. Network blocked.
// Reads one JSON request per stdin line, answers one JSON line each:
//   {"op":"render","mermaid":"<mermaid.min.js>","diagrams":[{id,code}]} -> [{id,svg} | {id,error}]
//   {"op":"check","page":"<abs page.html>","shots":"<dir>"}            -> {problems,notes,pictures}
import { createRequire } from "module";
import { createInterface } from "readline";
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.VX_PLAYWRIGHT);

let browser;
const open = async () => (browser ??= await chromium.launch({ executablePath: process.env.VX_CHROME }));

async function render({ mermaid: js, diagrams }) {
  const page = await (await open()).newPage();
  await page.setContent("<!doctype html><html><body></body></html>");
  await page.addScriptTag({ path: js });
  const out = await page.evaluate(async (items) => {
    const font = 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif';
    mermaid.initialize({
      startOnLoad: false, securityLevel: "strict", theme: "base", htmlLabels: false, fontFamily: font,
      themeVariables: { fontFamily: font, fontSize: "14px", primaryColor: "#f4f4f5", primaryBorderColor: "#a1a1aa", lineColor: "#71717a" },
      flowchart: { htmlLabels: false, curve: "basis", padding: 14, nodeSpacing: 40, rankSpacing: 52 },
      sequence: { mirrorActors: false, messageMargin: 34, actorMargin: 60, useMaxWidth: true },
      state: { useMaxWidth: true },
    });
    const res = [];
    for (const d of items) {
      try { const { svg } = await mermaid.render(d.id + "svg", d.code); res.push({ id: d.id, svg }); }
      catch (e) { res.push({ id: d.id, error: String(e.message || e).split("\n").slice(0, 3).join(" ") }); }
    }
    return res;
  }, diagrams);
  await page.close();
  return out;
}

// JS errors, requests, diagrams left as text, sideways scroll on a phone, every step of every sequence diagram.
async function check({ page: file, shots }) {
  const problems = [];
  const notes = new Set();
  const pictures = [];
  let requests = 0;
  for (const run of [{ scheme: "light", width: 1280 }, { scheme: "dark", width: 1280 }, { scheme: "light", width: 390 }]) {
    const ctx = await (await open()).newContext({ viewport: { width: run.width, height: 900 }, colorScheme: run.scheme });
    await ctx.route("**/*", (r) => {
      const u = r.request().url();
      if (u.startsWith("file:") || u.startsWith("data:")) return r.continue();
      requests++;
      return r.abort();
    });
    const page = await ctx.newPage();
    const tag = `${run.scheme}-${run.width}`;
    page.on("pageerror", (e) => problems.push(`${tag}: JS error: ${e.message}`));
    page.on("console", (m) => { if (m.type() === "error") problems.push(`${tag}: console: ${m.text()}`); });
    await page.goto("file://" + file);
    await page.waitForTimeout(100);
    if (!(await page.locator("header h1").count())) problems.push(`${tag}: no title: the page did not render`);
    const asText = await page.locator(".mm .mm-src").count();
    if (asText) notes.add(`${asText} diagram(s) shown as Mermaid text, not drawn`);
    if (run.width === 1280 && run.scheme === "light") {
      const bars = page.locator(".steps");
      for (let b = 0; b < (await bars.count()); b++) {
        const bar = bars.nth(b);
        const total = Number(((await bar.locator(".n").textContent()) || "0").match(/\d+/)?.[0] || 0);
        for (let k = 0; k < total; k++) await bar.locator('[data-d="1"]').click();
      }
    }
    if (run.width === 390) {
      const wide = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
      if (wide > 2) problems.push(`${tag}: page is ${wide}px wider than the screen`);
    }
    const path = `${shots}/${tag}.png`;
    await page.screenshot({ path, fullPage: true });
    pictures.push(path);
    await ctx.close();
  }
  if (requests) problems.push(`network requests: ${requests}; the page must work offline`);
  return { problems, notes: [...notes], pictures };
}

for await (const line of createInterface({ input: process.stdin })) {
  if (!line.trim()) continue;
  const req = JSON.parse(line);
  let res;
  try { res = req.op === "render" ? await render(req) : await check(req); }
  catch (e) { res = { fatal: String(e.message || e).slice(0, 400) }; }
  process.stdout.write(JSON.stringify(res) + "\n");
}
await browser?.close();
