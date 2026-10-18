"""Convierte un diagrama `.excalidraw` en un proyecto animado de Excalimate (`.excanim`).

Cada elemento tiene `customData.step` (lo asigna build_diagrams.py). La
animación revela el diagrama paso a paso:
  * formas, textos e íconos: fade-in + leve deslizamiento hacia arriba;
  * flechas: se "dibujan" (drawProgress 0 -> 1) después de que aparece su paso.

Abrir en https://app.excalimate.com -> Open -> elegir el .excanim, y exportar a
MP4/WebM/GIF desde el editor (o editar los tiempos en el timeline).

    python docs/diagrams/src/build_animation.py 01_arquitectura 09_ruta_aprendizaje
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DIAGRAMS = Path(__file__).resolve().parents[1]
OUT = DIAGRAMS.parent / "animations"

STEP_MS = 1800      # tiempo entre pasos
FADE_MS = 700       # duración del fade
DRAW_MS = 900       # duración del dibujo de flechas
START_MS = 400
HOLD_MS = 3000      # pausa final con el diagrama completo


def _kf(track_id: str, n: int, t: float, v: float, easing: str = "easeOutCubic") -> dict:
    return {"id": f"{track_id}-k{n}", "time": round(t), "value": v, "easing": easing}


def build(name: str) -> Path:
    scene = json.loads((DIAGRAMS / f"{name}.excalidraw").read_text(encoding="utf-8"))
    elements = scene["elements"]
    tracks = []
    max_step = max((e.get("customData") or {}).get("step", 0) for e in elements)
    for e in elements:
        step = (e.get("customData") or {}).get("step", 0)
        t0 = START_MS + step * STEP_MS
        final_opacity = e.get("opacity", 100) / 100
        e["opacity"] = 100  # Excalimate controla la visibilidad sólo por keyframes
        if e.get("containerId") and any(x["id"] == e["containerId"] and x["type"] == "arrow" for x in elements):
            t0 += DRAW_MS  # el texto de una flecha aparece cuando terminó de dibujarse
        tid = f"t-{e['id']}"
        tracks.append({
            "id": f"{tid}-op", "targetId": e["id"], "targetType": "element", "property": "opacity",
            "keyframes": [_kf(f"{tid}-op", 0, 0, 0, "step"), _kf(f"{tid}-op", 1, t0, 0),
                          _kf(f"{tid}-op", 2, t0 + FADE_MS, final_opacity)],
            "enabled": True,
        })
        if e["type"] in ("arrow", "line") and step > 0:
            tracks.append({
                "id": f"{tid}-dp", "targetId": e["id"], "targetType": "element", "property": "drawProgress",
                "keyframes": [_kf(f"{tid}-dp", 0, 0, 0, "step"), _kf(f"{tid}-dp", 1, t0, 0, "easeInOutCubic"),
                              _kf(f"{tid}-dp", 2, t0 + DRAW_MS, 1)],
                "enabled": True,
            })
        elif e["type"] not in ("text",) and step > 0 and not e.get("containerId"):
            tracks.append({
                "id": f"{tid}-ty", "targetId": e["id"], "targetType": "element", "property": "translateY",
                "keyframes": [_kf(f"{tid}-ty", 0, 0, 18, "step"), _kf(f"{tid}-ty", 1, t0, 18),
                              _kf(f"{tid}-ty", 2, t0 + FADE_MS, 0)],
                "enabled": True,
            })
    xs = [e["x"] for e in elements] + [e["x"] + e["width"] for e in elements]
    ys = [e["y"] for e in elements] + [e["y"] + e["height"] for e in elements]
    width = (max(xs) - min(xs)) * 1.06
    height = (max(ys) - min(ys)) * 1.06
    width = max(width, height * 16 / 9)
    duration = START_MS + (max_step + 1) * STEP_MS + DRAW_MS + HOLD_MS
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    project = {
        "version": "2.0.0",
        "metadata": {"id": f"novamart-{name}", "name": f"NovaMart · {name}", "createdAt": now, "updatedAt": now},
        "scene": {"elements": elements, "appState": {"viewBackgroundColor": "#ffffff"}, "files": {}},
        "timeline": {"id": "timeline", "name": f"NovaMart {name}", "duration": duration, "fps": 30, "tracks": tracks},
        "playback": {
            "clipStart": 0, "clipEnd": duration,
            "cameraFrame": {"aspectRatio": "16:9", "width": round(width),
                            "x": round((max(xs) + min(xs)) / 2), "y": round((max(ys) + min(ys)) / 2)},
        },
        "preferredWorkspace": "studio",
    }
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{name}.excanim"
    path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
    print(f"✔ {path.name}: {len(tracks)} tracks, {duration / 1000:.1f}s")
    return path


if __name__ == "__main__":
    for n in sys.argv[1:] or ["01_arquitectura"]:
        build(n)
