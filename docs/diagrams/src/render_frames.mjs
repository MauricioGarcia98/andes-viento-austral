// Renderiza la revelación paso a paso de un diagrama (customData.step) a PNGs.
// Uso: node render_frames.mjs <in.excalidraw> <out_dir> [width_px]
import { chromium } from "playwright-core";
import fs from "fs";
import http from "http";
import path from "path";

const [inp, outDir, widthArg] = process.argv.slice(2);
const root = path.dirname(new URL(import.meta.url).pathname);
const types = { ".js": "text/javascript", ".html": "text/html", ".woff2": "font/woff2" };
const server = http.createServer((req, res) => {
  const p = path.join(root, decodeURIComponent(req.url.split("?")[0]));
  if (!fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { "Content-Type": types[path.extname(p)] || "application/octet-stream" });
  fs.createReadStream(p).pipe(res);
});
await new Promise(r => server.listen(0, r));
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
const page = await browser.newPage({ viewport: { width: 2000, height: 1400 } });
await page.goto(`http://127.0.0.1:${server.address().port}/index.html`);
await page.waitForFunction(() => window.__ready === true, null, { timeout: 60000 });

const scene = JSON.parse(fs.readFileSync(inp, "utf8"));
const steps = [...new Set(scene.elements.map(e => (e.customData || {}).step || 0))].sort((a, b) => a - b);
const fades = [0.25, 0.5, 0.75, 1];
fs.mkdirSync(outDir, { recursive: true });
const width = Number(widthArg || 1400);
let n = 0;
const manifest = [];
for (const k of steps) {
  for (const f of fades) {
    const els = scene.elements
      .filter(e => ((e.customData || {}).step || 0) <= k)
      .map(e => (((e.customData || {}).step || 0) === k ? { ...e, opacity: Math.round(e.opacity * f) } : e));
    // fondo fijo: todos los elementos invisibles fijan el encuadre final
    const ghost = scene.elements.filter(e => ((e.customData || {}).step || 0) > k).map(e => ({ ...e, opacity: 0 }));
    const svg = await page.evaluate(async ({ els, appState }) => {
      const s = await window.exportToSvg({ elements: els, appState: { ...appState, exportBackground: true }, files: {}, exportPadding: 40 });
      return s.outerHTML;
    }, { els: [...ghost, ...els], appState: scene.appState });
    await page.evaluate(({ svg, width }) => {
      const out = document.getElementById("out");
      out.innerHTML = svg;
      const el = out.querySelector("svg");
      const ratio = el.viewBox.baseVal.height / el.viewBox.baseVal.width;
      el.setAttribute("width", width); el.setAttribute("height", Math.round(width * ratio));
    }, { svg, width });
    const file = path.join(outDir, `f${String(n).padStart(4, "0")}.png`);
    await (await page.$("#out svg")).screenshot({ path: file });
    manifest.push({ file, ms: f === 1 ? 900 : 70 });
    n++;
  }
}
manifest[manifest.length - 1].ms = 4000;
fs.writeFileSync(path.join(outDir, "manifest.json"), JSON.stringify(manifest));
console.log("frames", n);
await browser.close();
server.close();
