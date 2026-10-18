// Convierte un .excalidraw (con customData.step) en UN SVG animado autocontenido.
//
//   node render_animated_svg.mjs <in.excalidraw> <out.svg> [segundos_por_paso] [pausa_final]
//
// Cómo funciona:
//   1. Exporta el diagrama completo con la librería oficial de Excalidraw (para las fuentes embebidas).
//   2. Exporta cada paso por separado con el MISMO encuadre (dos anclas invisibles fijan el viewBox).
//   3. Une todo en un solo <svg>: cada paso es un <g class="sN"> con CSS que lo hace aparecer
//      (fade + desplazamiento) y "dibuja" sus trazos (stroke-dashoffset con pathLength=1).
// El resultado funciona como <img> en GitHub, sin JavaScript.
import { chromium } from "playwright-core";
import fs from "fs";
import http from "http";
import path from "path";

const [inp, out, stepArg, holdArg] = process.argv.slice(2);
const STEP = Number(stepArg || 1.1);
const HOLD = Number(holdArg || 6);
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
const page = await browser.newPage();
await page.goto(`http://127.0.0.1:${server.address().port}/index.html`);
await page.waitForFunction(() => window.__ready === true, null, { timeout: 60000 });

const scene = JSON.parse(fs.readFileSync(inp, "utf8"));
const step = e => (e.customData || {}).step || 0;
const steps = [...new Set(scene.elements.map(step))].sort((a, b) => a - b);

// bounding box del diagrama completo -> anclas invisibles para un encuadre idéntico en cada paso
let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
for (const e of scene.elements) {
  const pts = e.points ? e.points.map(p => [e.x + p[0], e.y + p[1]]) : [[e.x, e.y], [e.x + e.width, e.y + e.height]];
  for (const [px, py] of pts) { x0 = Math.min(x0, px); y0 = Math.min(y0, py); x1 = Math.max(x1, px); y1 = Math.max(y1, py); }
}
const anchor = (id, x, y) => ({
  id, type: "rectangle", x, y, width: 1, height: 1, angle: 0, strokeColor: "transparent",
  backgroundColor: "transparent", fillStyle: "solid", strokeWidth: 1, strokeStyle: "solid", roughness: 0,
  opacity: 0, groupIds: [], frameId: null, roundness: null, seed: 1, version: 1, versionNonce: 1,
  isDeleted: false, boundElements: [], updated: 1, link: null, locked: false,
});
const anchors = [anchor("__a0", x0 - 30, y0 - 30), anchor("__a1", x1 + 30, y1 + 30)];

const exportSvg = (elements, background) => page.evaluate(async ({ elements, appState, background }) => {
  const s = await window.exportToSvg({
    elements, files: {}, exportPadding: 10,
    appState: { ...appState, exportBackground: background, exportWithDarkMode: false },
  });
  return s.outerHTML;
}, { elements, appState: scene.appState, background });

const full = await exportSvg([...anchors, ...scene.elements], true);
const openTag = full.match(/<svg[^>]*>/)[0];
const viewBox = openTag.match(/viewBox="([^"]+)"/)[1];
const [, , vw, vh] = viewBox.split(" ").map(Number);
const fonts = (full.match(/<style class="style-fonts">[\s\S]*?<\/style>/) || [""])[0];

const strip = svg => svg
  .replace(/^<svg[^>]*>/, "").replace(/<\/svg>\s*$/, "")
  .replace(/<metadata>[\s\S]*?<\/metadata>/g, "")
  .replace(/<!--[\s\S]*?-->/g, "")
  .replace(/<style class="style-fonts">[\s\S]*?<\/style>/g, "")
  .replace(/<defs>\s*<\/defs>/g, "")
  .replace(/<path /g, '<path pathLength="1" ');

const T = steps.length * STEP + HOLD;
const pct = s => ((s / T) * 100).toFixed(2);
let css = `
  .st { opacity: 0; animation-duration: ${T}s; animation-iteration-count: infinite; animation-timing-function: ease-out; }
  .st path { stroke-dasharray: 1; animation-duration: ${T}s; animation-iteration-count: infinite; animation-timing-function: ease-in-out; }`;
let groups = "";
for (const [i, k] of steps.entries()) {
  const t0 = i * STEP;
  const a = pct(t0), b = pct(t0 + 0.45), d = pct(t0 + 1.0);
  css += `
  .s${i} { animation-name: f${i}; }
  .s${i} path { animation-name: d${i}; }
  @keyframes f${i} { 0%, ${a}% { opacity: 0; transform: translateY(14px); } ${b}% { opacity: 1; transform: translateY(0); } 93% { opacity: 1; transform: translateY(0); } 98%, 100% { opacity: 0; } }
  @keyframes d${i} { 0%, ${a}% { stroke-dashoffset: 1; } ${d}%, 100% { stroke-dashoffset: 0; } }`;
  const svg = await exportSvg([...anchors, ...scene.elements.filter(e => step(e) === k)], false);
  if (!svg.match(/viewBox="([^"]+)"/)[1].startsWith(viewBox.split(" ").slice(0, 2).join(" "))) {
    throw new Error(`El paso ${k} quedó con otro encuadre`);
  }
  groups += `<g class="st s${i}">${strip(svg)}</g>\n`;
}

const result = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}" width="${vw}" height="${vh}" role="img" aria-label="${path.basename(inp, ".excalidraw")}">
<!-- Generado con Excalidraw + docs/diagrams/src/render_animated_svg.mjs -->
<defs>${fonts}<style>${css}
</style></defs>
<rect x="0" y="0" width="${vw}" height="${vh}" fill="${scene.appState.viewBackgroundColor || "#ffffff"}"/>
${groups}</svg>
`;
fs.writeFileSync(out, result);
console.log(`ok ${out} · ${steps.length} pasos · ${T.toFixed(1)}s · ${(result.length / 1e6).toFixed(2)} MB`);
await browser.close();
server.close();
