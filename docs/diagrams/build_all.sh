#!/usr/bin/env bash
# Regenera TODOS los diagramas y animaciones de Andes Viento Austral.
# Requisitos: Python 3.10+ con Pillow, Node 20+, Chromium (o `npx playwright install chromium`).
#   cd docs/diagrams/src && npm install && npm run bundle
#   CHROMIUM_PATH=/ruta/a/chromium ./docs/diagrams/build_all.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
python3 src/build_diagrams.py
args=()
for f in *.excalidraw; do args+=("$f" "${f%.excalidraw}"); done
node src/render.mjs "${args[@]}"
python3 src/build_animation.py 00_proceso_completo 02_arquitectura 03_linaje 10_ruta_aprendizaje
for n in 02_arquitectura 10_ruta_aprendizaje; do
  tmp="$(mktemp -d)"
  node src/render_frames.mjs "$n.excalidraw" "$tmp" 1400
  python3 src/make_gif.py "$tmp" "../animations/$n.gif"
  rm -rf "$tmp"
done
node src/render_animated_svg.mjs 00_proceso_completo.excalidraw ../animations/proceso_completo.svg
python3 src/build_job_svg.py
