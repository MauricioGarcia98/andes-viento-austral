// Uso: node render.mjs <in.excalidraw> <out_base> [scale]
import { chromium } from "playwright-core";
import fs from "fs";
import http from "http";
import path from "path";

const root = path.dirname(new URL(import.meta.url).pathname);
const types = { ".js": "text/javascript", ".html": "text/html", ".woff2": "font/woff2", ".css": "text/css", ".json": "application/json" };
const server = http.createServer((req, res) => {
  const p = path.join(root, decodeURIComponent(req.url.split("?")[0]));
  if (!fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { "Content-Type": types[path.extname(p)] || "application/octet-stream" });
  fs.createReadStream(p).pipe(res);
});
await new Promise(r => server.listen(0, r));
const port = server.address().port;

const jobs = [];
for (let i = 2; i < process.argv.length; i += 2) jobs.push([process.argv[i], process.argv[i + 1]]);
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
const page = await browser.newPage({ deviceScaleFactor: 1, viewport: { width: 1600, height: 1000 } });
page.on("console", m => { if (m.type() === "error") console.error("[browser]", m.text()); });
await page.goto(`http://127.0.0.1:${port}/index.html`);
await page.waitForFunction(() => window.__ready === true, null, { timeout: 60000 });
for (const [inp, outBase] of jobs) {
  const scene = JSON.parse(fs.readFileSync(inp, "utf8"));
  const svg = await page.evaluate(async (scene) => {
    const el = await window.exportToSvg({
      elements: scene.elements,
      appState: { ...scene.appState, exportBackground: true, exportWithDarkMode: false, exportEmbedScene: false },
      files: scene.files || {},
      exportPadding: 40,
    });
    return el.outerHTML;
  }, scene);
  fs.writeFileSync(outBase + ".svg", svg);
  await page.evaluate((svg) => { document.getElementById("out").innerHTML = svg; }, svg);
  const handle = await page.$("#out svg");
  await page.waitForTimeout(300);
  await handle.screenshot({ path: outBase + ".png", omitBackground: false });
  console.log("ok", outBase);
}
await browser.close();
server.close();
