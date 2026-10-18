"""Mini-toolkit para construir diagramas Excalidraw "como código".

Los diagramas del proyecto se generan con este módulo para que sean
reproducibles y versionables, pero el resultado son archivos `.excalidraw`
normales: se abren y editan en https://excalidraw.com (File > Open).

Los iconos salen de librerías públicas de https://libraries.excalidraw.com
(copiadas en `docs/diagrams/libraries/`): se escalan, se re-identifican y se
agrupan para que en el editor se muevan como una sola pieza.
"""

from __future__ import annotations

import copy
import json
import math
import random
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parents[1] / "libraries"

# Paleta de Excalidraw (trazo, relleno)
BLUE = ("#1971c2", "#a5d8ff")
GREEN = ("#2f9e44", "#b2f2bb")
YELLOW = ("#f08c00", "#ffec99")
RED = ("#e03131", "#ffc9c9")
VIOLET = ("#6741d9", "#d0bfff")
CYAN = ("#0c8599", "#99e9f2")
ORANGE = ("#e8590c", "#ffd8a8")
GRAPE = ("#9c36b5", "#eebefa")
GRAY = ("#495057", "#e9ecef")
TEAL = ("#099268", "#96f2d7")
PINK = ("#c2255c", "#fcc2d7")
BRONZE = ("#a0522d", "#f4d2b5")
SILVER = ("#5c677d", "#dde3ea")
GOLD = ("#b8860b", "#ffe8a3")
INK = "#1e1e1e"

HAND = 5      # Excalifont (manuscrita)
NORMAL = 6    # Nunito
CODE = 8      # Comic Shanns (monoespaciada)

_LIBS: dict[str, dict[str, list]] = {}


def _load_lib(name: str) -> dict[str, list]:
    if name not in _LIBS:
        path = next(LIB_DIR.glob(f"*{name}*.excalidrawlib"))
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("libraryItems") or data.get("library") or []
        out = {}
        for i, it in enumerate(items):
            if isinstance(it, dict):
                out[it.get("name") or f"item{i}"] = it["elements"]
            else:
                out[f"item{i}"] = it
        _LIBS[name] = out
    return _LIBS[name]


def lib_items(name: str) -> dict[str, list]:
    return _load_lib(name)


class Scene:
    def __init__(self, seed: int = 7, background: str = "#ffffff"):
        self.elements: list[dict] = []
        self.rng = random.Random(seed)
        self.background = background
        self._n = 0
        self.step = 0  # paso de animación: se guarda en customData para Excalimate / GIF

    # ----------------------------------------------------------------- base
    def _id(self, prefix: str = "el") -> str:
        self._n += 1
        return f"{prefix}{self._n:04d}"

    def _base(self, kind: str, x: float, y: float, w: float, h: float, **kw) -> dict:
        el = {
            "id": kw.pop("id", None) or self._id(kind[:2]),
            "type": kind, "x": x, "y": y, "width": w, "height": h, "angle": 0,
            "strokeColor": INK, "backgroundColor": "transparent", "fillStyle": "solid",
            "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "opacity": 100,
            "groupIds": [], "frameId": None, "roundness": None,
            "seed": self.rng.randint(1, 2**31 - 1), "version": 1,
            "versionNonce": self.rng.randint(1, 2**31 - 1), "isDeleted": False,
            "boundElements": [], "updated": 1, "link": None, "locked": False,
        }
        el.update(kw)
        el["customData"] = {"step": self.step}
        self.elements.append(el)
        return el

    # ---------------------------------------------------------------- shapes
    def rect(self, x, y, w, h, color=GRAY, fill="solid", label=None, size=20, font=HAND,
             rounded=True, dashed=False, stroke_width=2, opacity=100, text_color=INK, kind="rectangle",
             roughness=1, align="center", valign="middle"):
        stroke, bg = color
        el = self._base(kind, x, y, w, h, strokeColor=stroke, backgroundColor=bg, fillStyle=fill,
                        strokeWidth=stroke_width, strokeStyle="dashed" if dashed else "solid",
                        roundness={"type": 3} if rounded and kind == "rectangle" else ({"type": 2} if kind != "rectangle" else None),
                        opacity=opacity, roughness=roughness)
        if label:
            self.bound_text(el, label, size=size, font=font, color=text_color, align=align, valign=valign)
        return el

    def ellipse(self, x, y, w, h, color=GRAY, fill="solid", label=None, size=18, **kw):
        return self.rect(x, y, w, h, color, fill, label, size, kind="ellipse", **kw)

    def diamond(self, x, y, w, h, color=GRAY, fill="solid", label=None, size=18, **kw):
        return self.rect(x, y, w, h, color, fill, label, size, kind="diamond", **kw)

    # ------------------------------------------------------------------ text
    @staticmethod
    def measure(text: str, size: float, font: int = HAND) -> tuple[float, float]:
        factor = {HAND: 0.56, NORMAL: 0.53, CODE: 0.6}.get(font, 0.55)
        lines = text.split("\n")
        w = max(len(line) for line in lines) * size * factor
        h = len(lines) * size * 1.25
        return w, h

    def text(self, x, y, text, size=20, color=INK, font=HAND, align="left", anchor="nw", opacity=100):
        w, h = self.measure(text, size, font)
        if anchor in ("n", "c", "s"):
            x -= w / 2
        if anchor in ("c", "w", "e"):
            y -= h / 2
        if anchor in ("ne", "e", "se"):
            x -= w
        return self._base("text", x, y, w, h, strokeColor=color, text=text, originalText=text,
                          fontSize=size, fontFamily=font, textAlign=align, verticalAlign="top",
                          containerId=None, autoResize=True, lineHeight=1.25, strokeWidth=1,
                          opacity=opacity)

    def bound_text(self, container, text, size=20, font=HAND, color=INK, align="center", valign="middle"):
        w, h = self.measure(text, size, font)
        cx = container["x"] + container["width"] / 2
        cy = container["y"] + container["height"] / 2
        pad = 10
        x = container["x"] + pad if align == "left" else cx - w / 2
        y = cy - h / 2 if valign == "middle" else container["y"] + pad
        t = self._base("text", x, y, w, h, strokeColor=color, text=text, originalText=text,
                       fontSize=size, fontFamily=font, textAlign=align, verticalAlign=valign,
                       containerId=container["id"], autoResize=True, lineHeight=1.25, strokeWidth=1,
                       groupIds=list(container["groupIds"]))
        container["boundElements"].append({"type": "text", "id": t["id"]})
        return t

    # ---------------------------------------------------------------- arrows
    @staticmethod
    def anchor(el, side: str) -> tuple[float, float]:
        x, y, w, h = el["x"], el["y"], el["width"], el["height"]
        return {
            "left": (x, y + h / 2), "right": (x + w, y + h / 2),
            "top": (x + w / 2, y), "bottom": (x + w / 2, y + h),
            "center": (x + w / 2, y + h / 2),
        }[side]

    def arrow(self, a, b, a_side="right", b_side="left", color=INK, dashed=False, width=2,
              label=None, label_size=16, via: list[tuple[float, float]] | None = None, head="triangle",
              start_head=None, elbow=False, gap=6, roughness=1, label_color=None, sharp=False):
        p0 = self.anchor(a, a_side) if isinstance(a, dict) else a
        p1 = self.anchor(b, b_side) if isinstance(b, dict) else b
        pts = [p0, *(via or []), p1]
        if elbow and not via:
            mx = (p0[0] + p1[0]) / 2
            pts = [p0, (mx, p0[1]), (mx, p1[1]), p1]
        x0, y0 = pts[0]
        rel = [[px - x0, py - y0] for px, py in pts]
        xs = [p[0] for p in rel]
        ys = [p[1] for p in rel]
        el = self._base("arrow", x0, y0, max(xs) - min(xs), max(ys) - min(ys),
                        strokeColor=color, strokeWidth=width, strokeStyle="dashed" if dashed else "solid",
                        roundness={"type": 2} if not (elbow or sharp) else None, points=rel,
                        lastCommittedPoint=None, startArrowhead=start_head, endArrowhead=head,
                        startBinding=None, endBinding=None, roughness=roughness)
        for target, key in ((a, "startBinding"), (b, "endBinding")):
            if isinstance(target, dict):
                el[key] = {"elementId": target["id"], "focus": 0, "gap": gap}
                target["boundElements"].append({"type": "arrow", "id": el["id"]})
        if label:
            mid = len(pts) // 2
            if len(pts) % 2 == 0:
                lx = (pts[mid - 1][0] + pts[mid][0]) / 2
                ly = (pts[mid - 1][1] + pts[mid][1]) / 2
            else:
                lx, ly = pts[mid]
            w, h = self.measure(label, label_size, HAND)
            t = self._base("text", lx - w / 2, ly - h / 2, w, h, strokeColor=label_color or color, text=label,
                           originalText=label, fontSize=label_size, fontFamily=HAND, textAlign="center",
                           verticalAlign="middle", containerId=el["id"], autoResize=True, lineHeight=1.25,
                           strokeWidth=1)
            el["boundElements"].append({"type": "text", "id": t["id"]})
        return el

    def line(self, pts, color=INK, width=2, dashed=False, roughness=1):
        x0, y0 = pts[0]
        rel = [[px - x0, py - y0] for px, py in pts]
        xs = [p[0] for p in rel]
        ys = [p[1] for p in rel]
        return self._base("line", x0, y0, max(xs) - min(xs), max(ys) - min(ys), strokeColor=color,
                          strokeWidth=width, strokeStyle="dashed" if dashed else "solid", points=rel,
                          lastCommittedPoint=None, startArrowhead=None, endArrowhead=None,
                          startBinding=None, endBinding=None, roughness=roughness)

    # ----------------------------------------------------------------- icons
    def icon(self, lib: str, name: str, x: float, y: float, size: float = 80, keep_text: bool = False,
             recolor: str | None = None) -> dict:
        """Inserta un ícono de librería escalado a `size` (lado mayor). Devuelve su bounding box."""
        src = copy.deepcopy(lib_items(lib)[name])
        src = [e for e in src if not e.get("isDeleted") and (keep_text or e["type"] != "text")]
        x0, y0, x1, y1 = _bbox(src)
        scale = size / max(x1 - x0, y1 - y0, 1)
        gid = self._id("grp")
        id_map = {e["id"]: self._id("ic") for e in src}
        group_map: dict[str, str] = {}
        for e in src:
            e["id"] = id_map[e["id"]]
            e["x"] = x + (e["x"] - x0) * scale
            e["y"] = y + (e["y"] - y0) * scale
            e["width"] = e.get("width", 0) * scale
            e["height"] = e.get("height", 0) * scale
            if "points" in e:
                e["points"] = [[p[0] * scale, p[1] * scale, *p[2:]] for p in e["points"]]
            if "fontSize" in e:
                e["fontSize"] = e["fontSize"] * scale
            e["strokeWidth"] = max(0.5, min(e.get("strokeWidth", 1) * max(scale, 0.6), 4))
            e["groupIds"] = [group_map.setdefault(g, self._id("grp")) for g in e.get("groupIds", [])] + [gid]
            if e.get("containerId"):
                e["containerId"] = id_map.get(e["containerId"])
            e["boundElements"] = [
                {**b, "id": id_map[b["id"]]} for b in (e.get("boundElements") or []) if b.get("id") in id_map
            ]
            for key in ("startBinding", "endBinding"):
                if e.get(key):
                    e[key] = None
            e["frameId"] = None
            e["seed"] = self.rng.randint(1, 2**31 - 1)
            e.setdefault("version", 1)
            e.setdefault("versionNonce", 1)
            e.setdefault("isDeleted", False)
            e.setdefault("opacity", 100)
            e.setdefault("angle", 0)
            e.setdefault("roughness", 1)
            e.setdefault("strokeStyle", "solid")
            e.setdefault("fillStyle", "solid")
            e.setdefault("backgroundColor", "transparent")
            e.setdefault("link", None)
            e.setdefault("locked", False)
            e.setdefault("updated", 1)
            if e["type"] == "draw":
                e["type"] = "line"
            e["customData"] = {"step": self.step}
            if recolor and e["type"] != "text":
                e["strokeColor"] = recolor
            self.elements.append(e)
        w, h = (x1 - x0) * scale, (y1 - y0) * scale
        return {"id": gid, "x": x, "y": y, "width": w, "height": h, "boundElements": [], "groupIds": [gid]}

    def icon_card(self, lib, name, x, y, w=150, h=150, color=GRAY, title=None, subtitle=None,
                  icon_size=70, fill="solid", title_size=18):
        """Tarjeta con ícono + título + subtítulo (nada de cajas vacías)."""
        card = self.rect(x, y, w, h, color, fill=fill)
        ic = self.icon(lib, name, 0, 0, icon_size)
        self.move_group(ic, x + (w - ic["width"]) / 2, y + 14)
        ty = y + 14 + ic["height"] + 8
        if title:
            self.text(x + w / 2, ty, title, size=title_size, anchor="n", color=color[0] if color != GRAY else INK)
            ty += title_size * 1.3
        if subtitle:
            self.text(x + w / 2, ty, subtitle, size=13, anchor="n", font=NORMAL, color="#495057")
        return card

    def row_card(self, lib, name, x, y, w=260, h=86, color=GRAY, title="", subtitle=None, icon_size=56,
                 fill="solid", title_size=18):
        """Tarjeta horizontal: ícono a la izquierda, título y subtítulo a la derecha."""
        card = self.rect(x, y, w, h, color, fill=fill)
        ic = self.icon(lib, name, 0, 0, icon_size)
        self.move_group(ic, x + 12, y + (h - ic["height"]) / 2)
        tx = x + 24 + icon_size
        if subtitle:
            self.text(tx, y + h / 2 - 10, title, size=title_size, anchor="w", color=color[0] if color != GRAY else INK)
            self.text(tx, y + h / 2 + 13, subtitle, size=13, anchor="w", font=NORMAL, color="#495057")
        else:
            self.text(tx, y + h / 2, title, size=title_size, anchor="w", color=color[0] if color != GRAY else INK)
        return card

    def move_group(self, box: dict, nx: float, ny: float) -> dict:
        dx, dy = nx - box["x"], ny - box["y"]
        for e in self.elements:
            if box["id"] in e.get("groupIds", []):
                e["x"] += dx
                e["y"] += dy
        box["x"], box["y"] = nx, ny
        return box

    # ------------------------------------------------------------ composites
    def zone(self, x, y, w, h, title, color=GRAY, fill="hachure", title_size=26, opacity=60, icon=None):
        z = self.rect(x, y, w, h, color, fill=fill, dashed=True, stroke_width=2, opacity=opacity, roughness=1)
        tx = x + 18
        if icon:
            ic = self.icon(icon[0], icon[1], x + 14, y + 10, icon[2] if len(icon) > 2 else 40)
            tx = ic["x"] + ic["width"] + 10
        self.text(tx, y + 12, title, size=title_size, color=color[0])
        return z

    def note(self, x, y, w, text, color=YELLOW, size=16, font=HAND):
        _, th = self.measure(text, size, font)
        n = self.rect(x, y, w, th + 28, color, fill="solid", rounded=False, roughness=1, stroke_width=1)
        self.bound_text(n, text, size=size, font=font, align="left")
        return n

    def badge(self, x, y, text, color=BLUE, size=14):
        w, h = self.measure(text, size, CODE)
        return self.rect(x, y, w + 16, h + 8, color, fill="solid", label=text, size=size, font=CODE,
                         stroke_width=1, text_color=color[0])

    def table(self, x, y, name, columns, color=BLUE, width=270, row_h=26, subtitle=None):
        """Caja de entidad para diagramas ER: encabezado + columnas con badges PK/FK."""
        head_h = 44 if not subtitle else 60
        body_h = row_h * len(columns) + 12
        body = self.rect(x, y, width, head_h + body_h, (color[0], "#ffffff"), fill="solid", rounded=False)
        self.rect(x, y, width, head_h, color, fill="solid", rounded=False)
        self.text(x + width / 2, y + 8, name, size=20, anchor="n", color=INK)
        if subtitle:
            self.text(x + width / 2, y + 34, subtitle, size=13, anchor="n", font=NORMAL, color="#343a40")
        cy = y + head_h + 8
        for col in columns:
            cname, ctype, *flags = (*col, None) if len(col) == 2 else col
            flag = flags[0] if flags else None
            cx = x + 10
            if flag:
                fc = {"PK": YELLOW, "FK": BLUE, "DD": GRAPE, "M": GREEN, "NK": TEAL, "PII": RED,
                      "SCD": VIOLET}.get(flag, GRAY)
                b = self.badge(cx, cy - 1, flag, fc, size=11)
                b["height"] = row_h - 6
                cx += 40
            self.text(cx, cy + 2, cname, size=14, font=CODE)
            self.text(x + width - 10, cy + 3, ctype, size=12, font=NORMAL, color="#868e96", anchor="ne")
            cy += row_h
        return body

    # ---------------------------------------------------------------- output
    def save(self, path: str | Path) -> None:
        doc = {
            "type": "excalidraw", "version": 2, "source": "https://github.com/MauricioGarcia98/andes-viento-austral",
            "elements": self.elements,
            "appState": {"viewBackgroundColor": self.background, "gridSize": 20},
            "files": {},
        }
        Path(path).write_text(json.dumps(_round(doc), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _round(obj):
    """Redondea coordenadas a 2 decimales: archivos 3x más chicos, misma precisión visual."""
    if isinstance(obj, float):
        return round(obj, 2)
    if isinstance(obj, list):
        return [_round(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    return obj


def _bbox(elements: list[dict]) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for e in elements:
        if "points" in e and e["points"]:
            for p in e["points"]:
                xs.append(e["x"] + p[0])
                ys.append(e["y"] + p[1])
        else:
            xs += [e["x"], e["x"] + e.get("width", 0)]
            ys += [e["y"], e["y"] + e.get("height", 0)]
    return min(xs), min(ys), max(xs), max(ys)


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])
