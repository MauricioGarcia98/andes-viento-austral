"""Genera `docs/animations/job_run.svg`: una ejecución animada del job `andes-viento-e2e`.

Simula la vista de un run en Databricks (tema oscuro): cada tarea del DAG pasa por
pending -> running -> succeeded, las aristas muestran el flujo de datos, el `for_each`
de silver procesa sus entidades (referencia y telemetría), el panel derecho va mostrando las filas
escritas por capa y al final el quality gate aprueba el run. Es CSS puro (sin JS),
así que GitHub lo anima dentro del README.

    python docs/diagrams/src/build_job_svg.py
"""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "animations" / "job_run.svg"

W, H = 1240, 560
CYCLE = 18  # segundos por ciclo
START, STEP = 3.0, 10.0  # % del ciclo: inicio y duración de cada tarea
RESET = 95.0

PENDING, RUNNING, OK = "#3b444f", "#4c9aff", "#3fb950"
CARD_STROKE = "#30363d"

# (key, título, subtítulo, recurso, columna, fila, ícono, color de capa)
TASKS = [
    ("setup", "setup", "Notebook · UC", "capas + volumen", 0, 0, "cfg", None),
    ("generate", "generate_data", "for_each · 11 fuentes", "landing · SF=0.1", 0, 1, "gen", None),
    ("bronze", "bronze_ingest", "Auto Loader · drift", "bronze.* (11)", 1, 0.5, "nb", "bronze"),
    ("silver", "silver", "2 × for_each", "", 2, 0.5, "each", "silver"),
    ("dims", "gold_dimensions", "SCD2 · point-in-time", "gold.dim_* (7)", 3, 0, "nb", "gold"),
    ("facts", "gold_facts", "pérdidas por causa", "gold.fact_* (6)", 3, 1, "nb", "gold"),
    ("marts", "marts + semántica", "SQL · metric views", "9 marts · 7 mv", 4, 0, "sql", "gold"),
    ("gate", "quality_gate", "10 invariantes", "bloquea si falla", 4, 1, "check", None),
]
LOGS = [
    "andes_viento_dev · 5 capas · volumen raw",
    "11 fuentes · 37 turbinas · 2023-01 → 2026-09",
    "HT-OS 5.0: 3 sensores nuevos → stream reiniciado",
    "relojes, husos, kW/MW, clavados · SCD2 activos",
    "dim_turbine: cambios de multiplicadora (SCD2)",
    "potencial = generado + red + fallas + hielo",
    "LEO jul-2025: -18 % vs presupuesto, explicado",
    "10/10 invariantes OK → Genie listo",
]
ENTITIES = ["assets", "contracts", "spot", "dispatch", "weather", "scada", "inverter", "orders"]
EDGES = [  # (desde, hasta) -> se enciende cuando corre "hasta"
    ("setup", "generate"), ("generate", "bronze"), ("bronze", "silver"), ("silver", "dims"),
    ("dims", "facts"), ("facts", "marts"), ("marts", "gate"),
]

COL_X = [62, 238, 414, 590, 766]
ROW_Y = [176, 320]
CW, CH = 156, 64


def r(i: int) -> float:
    """% del ciclo en que arranca la tarea i (y termina la i-1)."""
    return START + i * STEP


DONE = r(len(TASKS))  # todo en verde


def pos(task):
    col, row = task[4], task[5]
    x = COL_X[col]
    y = ROW_Y[0] + (ROW_Y[1] - ROW_Y[0]) * row
    h = 128 if task[0] == "silver" else CH
    if task[0] == "silver":
        y -= (h - CH) / 2
    return x, y, CW, h


def kf(name: str, frames: list[tuple[float, str]]) -> str:
    body = " ".join(f"{p:.2f}%{{{v}}}" for p, v in frames)
    return f"@keyframes {name}{{{body}}}"


def icon(kind: str, x: float, y: float) -> str:
    box = f'<rect x="{x}" y="{y}" width="24" height="24" rx="5" fill="{{f}}" opacity="{{o}}"/>'
    if kind == "nb":
        return (box.format(f="#ff3621", o=".15")
                + f'<text x="{x + 12}" y="{y + 16}" text-anchor="middle" font-size="10" font-weight="700" fill="#ff7b5c" class="mono">{{ }}</text>')
    if kind == "sql":
        return (box.format(f="#1f6feb", o=".2")
                + f'<text x="{x + 12}" y="{y + 16}" text-anchor="middle" font-size="9" font-weight="700" fill="#79b8ff" class="mono">SQL</text>')
    if kind == "check":
        return (box.format(f="#238636", o=".25")
                + f'<path d="M{x + 6} {y + 12} l4 4 l7-8" stroke="#3fb950" stroke-width="2" fill="none"/>')
    if kind == "gen":
        return (box.format(f="#0c8599", o=".25")
                + f'<path d="M{x + 6} {y + 18} v-5 M{x + 10} {y + 18} v-9 M{x + 14} {y + 18} v-7 M{x + 18} {y + 18} v-12" '
                  f'stroke="#66d9e8" stroke-width="2.2" stroke-linecap="round"/>')
    if kind == "cfg":
        return (box.format(f="#6e7681", o=".25")
                + f'<circle cx="{x + 12}" cy="{y + 12}" r="5" fill="none" stroke="#c9d1d9" stroke-width="2" stroke-dasharray="3 2"/>')
    if kind == "each":
        return (box.format(f="#8957e5", o=".25")
                + f'<path d="M{x + 6} {y + 8} h12 M{x + 6} {y + 12} h12 M{x + 6} {y + 16} h12" stroke="#d2a8ff" stroke-width="2" stroke-linecap="round"/>')
    return ""


def build() -> str:
    css: list[str] = []
    body: list[str] = []
    geo = {t[0]: pos(t) for t in TASKS}

    # ---------------------------------------------------------------- aristas
    edges_svg, flows_svg = [], []
    for k, (a, b) in enumerate(EDGES):
        ax, ay, aw, ah = geo[a]
        bx, by, bw, bh = geo[b]
        if abs(ax - bx) < 1:  # misma columna: vertical
            d = f"M{ax + aw / 2} {ay + ah} L{bx + bw / 2} {by - 4}"
        else:
            x1, y1 = ax + aw, ay + ah / 2
            x2, y2 = bx - 4, by + bh / 2
            mx = (x1 + x2) / 2
            d = f"M{x1} {y1} C{mx} {y1} {mx} {y2} {x2} {y2}"
        i = next(n for n, t in enumerate(TASKS) if t[0] == b)
        edges_svg.append(f'<path class="edge" marker-end="url(#arr)" d="{d}"/>')
        flows_svg.append(f'<path class="flow fl{k}" d="{d}"/>')
        css.append(kf(f"e{k}", [(0, "opacity:0"), (r(i), "opacity:1"), (r(i + 1), "opacity:0")]))
        css.append(f".fl{k}{{animation:e{k} {CYCLE}s steps(1,end) infinite, march .8s linear infinite}}")
    body += edges_svg + flows_svg

    # ---------------------------------------------------------------- tarjetas
    for i, (key, title, sub, res, *_rest) in enumerate(TASKS):
        x, y, w, h = geo[key]
        layer = TASKS[i][7]
        css.append(kf(f"d{i}", [(0, f"fill:{PENDING}"), (r(i), f"fill:{RUNNING}"), (r(i + 1), f"fill:{OK}"),
                                (RESET, f"fill:{PENDING}")]))
        css.append(kf(f"b{i}", [(0, f"stroke:{CARD_STROKE}"), (r(i), f"stroke:{RUNNING}"),
                                (r(i + 1), f"stroke:{CARD_STROKE}")]))
        css.append(kf(f"sp{i}", [(0, "opacity:0"), (r(i), "opacity:1"), (r(i + 1), "opacity:0")]))
        css.append(f".k{i} .dot{{animation-name:d{i}}} .k{i} .card{{animation-name:b{i}}} "
                   f".k{i} .ring{{animation:sp{i} {CYCLE}s steps(1,end) infinite, rot .9s linear infinite}}")
        g = [f'<g class="k{i}" filter="url(#sh)">',
             f'<rect class="card cy" x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#161b22" stroke="{CARD_STROKE}" stroke-width="1.5"/>']
        if layer:
            g.append(f'<rect x="{x}" y="{y}" width="4" height="{h}" rx="2" fill="url(#{layer})"/>')
        g.append(icon(TASKS[i][6], x + 12, y + 10))
        g.append(f'<text x="{x + 43}" y="{y + 21}" class="t">{title}</text>')
        g.append(f'<text x="{x + 43}" y="{y + 35}" class="s">{sub}</text>')
        if res:
            g.append(f'<text x="{x + 12}" y="{y + 54}" class="s mono">{res}</text>')
        if key == "silver":  # las 8 iteraciones del for_each, de a 4
            for j, ent in enumerate(ENTITIES):
                ex = x + 12 + (j % 2) * 70
                ey = y + 46 + (j // 2) * 19
                s0 = r(i) + (j // 4) * STEP / 2 + (j % 4) * 0.6
                s1 = r(i) + (j // 4 + 1) * STEP / 2 - (3 - j % 4) * 0.5
                css.append(kf(f"it{j}", [(0, f"fill:{PENDING}"), (s0, f"fill:{RUNNING}"), (s1, f"fill:{OK}"),
                                         (RESET, f"fill:{PENDING}")]))
                g.append(f'<rect class="cy" style="animation-name:it{j}" x="{ex}" y="{ey}" width="9" height="9" rx="2" fill="{PENDING}"/>')
                g.append(f'<text x="{ex + 13}" y="{ey + 8}" class="xs mono">{ent}</text>')
        cx, cy = x + w - 11, y + 11
        g.append(f'<circle class="ring" cx="{cx}" cy="{cy}" r="7.5" fill="none" stroke="{RUNNING}" stroke-width="1.6" stroke-dasharray="16 8" opacity="0"/>')
        g.append(f'<circle class="dot cy" cx="{cx}" cy="{cy}" r="4.5" fill="{PENDING}"/>')
        g.append("</g>")
        body.append("".join(g))

    # ------------------------------------------------------------ panel Output
    lx, ly = 62, 404
    out = [f'<rect x="{lx}" y="{ly}" width="860" height="118" rx="8" fill="#010409" stroke="#30363d"/>',
           f'<text x="{lx + 14}" y="{ly + 20}" class="lbl" fill="#8b949e">OUTPUT</text>',
           f'<line x1="{lx}" y1="{ly + 30}" x2="{lx + 860}" y2="{ly + 30}" stroke="#21262d"/>']
    for i, msg in enumerate(LOGS):
        x = lx + 14 + (i // 4) * 430
        y = ly + 50 + (i % 4) * 20
        css.append(kf(f"lg{i}", [(0, "opacity:0"), (r(i + 1), "opacity:1"), (RESET, "opacity:0")]))
        out.append(f'<g class="cy" style="animation-name:lg{i}" opacity="0"><text x="{x}" y="{y}" class="mono" font-size="10">'
                   f'<tspan fill="#3fb950">✓</tspan><tspan fill="#79b8ff" x="{x + 14}">{TASKS[i][1]}</tspan>'
                   f'<tspan fill="#c9d1d9" x="{x + 132}">{msg}</tspan></text></g>')
    body.append("".join(out))

    # ------------------------------------------------- textos que cambian de estado
    css.append(kf("run", [(0, "opacity:1"), (DONE, "opacity:0"), (RESET, "opacity:1")]))
    css.append(kf("ok", [(0, "opacity:0"), (DONE, "opacity:1"), (RESET, "opacity:0")]))
    css.append(kf("bar", [(0, "transform:scaleX(0)"), (START, "transform:scaleX(0)"),
                          (DONE, "transform:scaleX(1)"), (RESET, "transform:scaleX(1)"), (RESET + 0.1, "transform:scaleX(0)")]))
    css.append(kf("newcell", [(0, "fill:#21262d"), (DONE, f"fill:{OK}")]))
    for name, i in (("cA", 3), ("cB", 4), ("cC", 6), ("cD", 7), ("cE", 8)):
        css.append(kf(name, [(0, "opacity:0"), (r(i), "opacity:1"), (RESET, "opacity:0")]))
    for t in range(len(TASKS) + 1):
        css.append(kf(f"cnt{t}", [(0, "opacity:0"), (r(t) if t else 0, "opacity:1"),
                                  (r(t + 1) if t < len(TASKS) else RESET, "opacity:0")]))
    return render(css, body)


def render(css: list[str], body: list[str]) -> str:
    rows = [
        ("bronze", "bronze.scada_turbine", "7.25M", "cA"),
        ("silver", "silver.scada_10min", "7.23M", "cB"),
        ("gold", "gold.fact_turbine_10min", "7.23M", "cC"),
        ("gold", "gold.fact_inverter_hourly", "0.37M", "cD"),
    ]
    rows_svg = []
    for n, (layer, table, value, anim) in enumerate(rows):
        y = 318 + n * 21
        rows_svg.append(
            f'<rect x="967" y="{y - 8}" width="8" height="8" rx="2" fill="url(#{layer})"/>'
            f'<text x="982" y="{y}" class="txt mono" font-size="10.5">{table}</text>'
            f'<text x="1220" y="{y}" text-anchor="end" class="dim mono" font-size="10.5">—</text>'
            f'<g class="cy" style="animation-name:{anim}" opacity="0"><rect x="1166" y="{y - 11}" width="56" height="14" fill="#0d1117"/>'
            f'<text x="1220" y="{y}" text-anchor="end" class="txt mono" font-size="10.5">{value}</text></g>')
    counters = "".join(
        f'<g class="cy" style="animation-name:cnt{t}" opacity="0"><text x="1220" y="244" text-anchor="end" '
        f'font-size="10.5" class="txt mono">{t}/{len(TASKS)}</text></g>' for t in range(len(TASKS) + 1))
    hist = []
    heights = [22, 18, 24, 16, 20, 22, 19, 23, 21, 18, 22, 20, 24]
    for n, hgt in enumerate(heights):
        color = "#f85149" if n == 3 else OK
        hist.append(f'<rect x="{967 + n * 18}" y="{462 - hgt}" width="14" height="{hgt}" rx="3" fill="{color}"/>')
    hist.append('<rect x="1201" y="441" width="14" height="21" rx="3" class="cy" style="animation-name:newcell" fill="#21262d"/>')

    labels = [("SETUP · LANDING", 140, "#8b949e"), ("BRONZE", 316, "#d08a4a"), ("SILVER", 492, "#b8c0c8"),
              ("GOLD", 668, "#e3b93a"), ("SERVE · QUALITY", 844, "#7ee787")]
    labels_svg = "".join(f'<text x="{x}" y="152" text-anchor="middle" class="lbl" fill="{c}">{t}</text>'
                         for t, x, c in labels)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif" role="img" aria-label="Ejecución animada del job andes-viento-e2e">
  <!-- Generado por docs/diagrams/src/build_job_svg.py · ilustración del run (no es una captura real) -->
  <defs>
    <pattern id="grid" width="18" height="18" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.9" fill="#2a323c"/></pattern>
    <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10z" fill="#4b5663"/></marker>
    <linearGradient id="bronze" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#e09a5a"/><stop offset="1" stop-color="#a8642a"/></linearGradient>
    <linearGradient id="silver" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#d9dee3"/><stop offset="1" stop-color="#8e979f"/></linearGradient>
    <linearGradient id="gold" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#f7d774"/><stop offset="1" stop-color="#c99a1a"/></linearGradient>
    <filter id="sh" x="-10%" y="-20%" width="120%" height="160%"><feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#000" flood-opacity=".45"/></filter>
    <filter id="glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  <style>
    .txt{{fill:#e6edf3}} .mut{{fill:#8b949e}} .dim{{fill:#6e7681}}
    .t{{fill:#e6edf3;font-size:12.5px;font-weight:600}}
    .s{{fill:#8b949e;font-size:10px}}
    .xs{{fill:#8b949e;font-size:8.5px}}
    .lbl{{font-size:9.5px;font-weight:700;letter-spacing:1.2px}}
    .mono{{font-family:'SFMono-Regular',Consolas,'Liberation Mono',monospace}}
    .edge{{stroke:#3b444f;stroke-width:1.5;fill:none}}
    .flow{{stroke:#4c9aff;stroke-width:2.2;fill:none;stroke-dasharray:5 7;opacity:0;filter:url(#glow)}}
    .cy{{animation-duration:{CYCLE}s;animation-iteration-count:infinite;animation-timing-function:steps(1,end)}}
    .ring{{transform-box:fill-box;transform-origin:center}}
    .spin{{transform-box:fill-box;transform-origin:center;animation:rot .9s linear infinite}}
    .bar{{transform-box:fill-box;transform-origin:left center;animation:bar {CYCLE}s linear infinite}}
    @keyframes rot{{to{{transform:rotate(360deg)}}}}
    @keyframes march{{to{{stroke-dashoffset:-48}}}}
    {chr(10).join("    " + c for c in css).strip()}
  </style>

  <!-- ventana -->
  <rect width="{W}" height="{H}" rx="12" fill="#0d1117"/>
  <rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="none" stroke="#30363d"/>
  <path d="M12 .5 H{W - 12} A11.5 11.5 0 0 1 {W - .5} 12 V40 H.5 V12 A11.5 11.5 0 0 1 12 .5z" fill="#161b22"/>
  <line x1="0" y1="40" x2="{W}" y2="40" stroke="#30363d"/>
  <circle cx="20" cy="20" r="5" fill="#ff5f57"/><circle cx="36" cy="20" r="5" fill="#febc2e"/><circle cx="52" cy="20" r="5" fill="#28c840"/>
  <g transform="translate(78,11)"><path d="M9 0 L18 5 L9 10 L0 5z" fill="#ff3621"/><path d="M0 8.5 L9 13.5 L18 8.5 L18 11.5 L9 16.5 L0 11.5z" fill="#ff3621" opacity=".8"/></g>
  <text x="104" y="25" font-size="13" font-weight="700" class="txt">databricks</text>
  <rect x="420" y="10" width="400" height="21" rx="5" fill="#0d1117" stroke="#30363d"/>
  <text x="434" y="24.5" font-size="11" class="dim">⌕  Search data, notebooks, jobs…</text>
  <text x="1060" y="25" font-size="11" class="mut">andes-viento · serverless</text>
  <circle cx="1212" cy="20" r="10" fill="#1f6feb"/><text x="1212" y="24" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">MG</text>

  <!-- sidebar -->
  <rect x="0" y="41" width="48" height="{H - 42}" fill="#0d1117"/>
  <line x1="48" y1="41" x2="48" y2="{H - 1}" stroke="#21262d"/>
  <g fill="none" stroke="#6e7681" stroke-width="1.6" stroke-linecap="round">
    <rect x="16" y="60" width="16" height="13" rx="2"/>
    <path d="M16 100 h16 M16 105 h16 M16 110 h10"/>
    <ellipse cx="24" cy="138" rx="8" ry="3"/><path d="M16 138 v9 a8 3 0 0 0 16 0 v-9"/>
    <circle cx="24" cy="180" r="7"/><path d="M24 176 v4 l3 2"/>
  </g>
  <rect x="6" y="200" width="36" height="32" rx="6" fill="#1f6feb" opacity=".18"/>
  <rect x="0" y="204" width="3" height="24" rx="1" fill="#4c9aff"/>
  <g fill="none" stroke="#4c9aff" stroke-width="1.6"><circle cx="18" cy="211" r="3"/><circle cx="30" cy="221" r="3"/><path d="M21 211 h4 v10 h2"/></g>
  <g fill="none" stroke="#6e7681" stroke-width="1.6" stroke-linecap="round">
    <path d="M17 262 l7-6 7 6 v9 h-14z"/><path d="M17 300 v-8 M24 300 v-13 M31 300 v-5"/>
  </g>

  <!-- encabezado del job -->
  <text x="68" y="64" font-size="10.5" class="mut">Jobs &amp; Pipelines  ›  andes-viento-austral</text>
  <text x="68" y="86" font-size="17" font-weight="700" class="txt">andes-viento-e2e</text>
  <g class="cy" style="animation-name:run">
    <rect x="270" y="72" width="78" height="20" rx="10" fill="#1f6feb" opacity=".2"/>
    <circle cx="283" cy="82" r="4.5" fill="none" stroke="#4c9aff" stroke-width="1.6" stroke-dasharray="14 6" class="spin"/>
    <text x="293" y="86" font-size="10.5" font-weight="600" fill="#4c9aff">Running</text>
  </g>
  <g class="cy" style="animation-name:ok" opacity="0">
    <rect x="270" y="72" width="86" height="20" rx="10" fill="#238636" opacity=".25"/>
    <circle cx="283" cy="82" r="5" fill="#3fb950"/><path d="M280.5 82 l2 2 l3.5-4" stroke="#0d1117" stroke-width="1.6" fill="none"/>
    <text x="293" y="86" font-size="10.5" font-weight="600" fill="#3fb950">Succeeded</text>
  </g>
  <text x="68" y="114" font-size="11.5" class="mut">Runs</text>
  <text x="112" y="114" font-size="11.5" font-weight="700" class="txt">Tasks</text>
  <text x="160" y="114" font-size="11.5" class="mut">Lineage</text>
  <text x="216" y="114" font-size="11.5" class="mut">Parameters</text>
  <rect x="110" y="120" width="34" height="2" fill="#4c9aff"/>
  <line x1="48" y1="122" x2="{W}" y2="122" stroke="#21262d"/>
  <rect x="770" y="70" width="80" height="24" rx="5" fill="none" stroke="#30363d"/>
  <text x="810" y="86" text-anchor="middle" font-size="11" class="txt">Run now</text>
  <rect x="860" y="70" width="70" height="24" rx="5" fill="none" stroke="#30363d"/>
  <text x="895" y="86" text-anchor="middle" font-size="11" class="txt">Edit</text>

  <!-- lienzo DAG -->
  <rect x="49" y="123" width="900" height="{H - 124}" fill="url(#grid)"/>
  {labels_svg}
  {chr(10).join("  " + b for b in body).strip()}

  <!-- leyenda -->
  <g font-size="9.5" class="mut">
    <circle cx="66" cy="{H - 22}" r="4" fill="{PENDING}"/><text x="74" y="{H - 19}">Pending</text>
    <circle cx="124" cy="{H - 22}" r="4" fill="{RUNNING}"/><text x="132" y="{H - 19}">Running</text>
    <circle cx="184" cy="{H - 22}" r="4" fill="{OK}"/><text x="192" y="{H - 19}">Succeeded</text>
    <text x="270" y="{H - 19}" class="dim">Ilustración del job definido en resources/andes_e2e.job.yml</text>
  </g>

  <!-- panel derecho -->
  <rect x="949" y="123" width="{W - 950}" height="{H - 124}" fill="#0d1117"/>
  <line x1="949" y1="123" x2="949" y2="{H - 1}" stroke="#21262d"/>
  <text x="967" y="148" font-size="12.5" font-weight="700" class="txt">Run details</text>
  <text x="1220" y="148" text-anchor="end" font-size="10.5" class="mono mut">dev</text>
  <g font-size="10.5">
    <text x="967" y="172" class="mut">Trigger</text>
    <text x="1220" y="172" text-anchor="end" fill="#79b8ff">andes-viento-daily</text>
    <text x="967" y="191" class="mut">Compute</text>
    <text x="1220" y="191" text-anchor="end" class="txt">Serverless · Photon</text>
    <text x="967" y="210" class="mut">Catalog</text>
    <text x="1220" y="210" text-anchor="end" class="txt">Unity Catalog · andes_viento_dev</text>
    <text x="967" y="229" class="mut">Parameters</text>
    <text x="1220" y="229" text-anchor="end" class="txt mono">scale_factor=0.1</text>
    <text x="967" y="244" class="mut">Tasks</text>
  </g>
  {counters}
  <rect x="967" y="254" width="253" height="5" rx="2.5" fill="#21262d"/>
  <rect class="bar" x="967" y="254" width="253" height="5" rx="2.5" fill="#4c9aff"/>

  <line x1="967" y1="276" x2="1220" y2="276" stroke="#21262d"/>
  <text x="967" y="296" class="lbl" fill="#8b949e">ROWS WRITTEN (SF=0.1, run real)</text>
  {"".join(rows_svg)}

  <line x1="967" y1="398" x2="1220" y2="398" stroke="#21262d"/>
  <text x="967" y="418" class="lbl" fill="#8b949e">RUN HISTORY · LAST 14 RUNS</text>
  {"".join(hist)}
  <g class="cy" style="animation-name:cE" opacity="0">
    <text x="967" y="484" font-size="10" fill="#3fb950">✓ quality gate: 10/10 invariantes OK</text>
  </g>
  <text x="967" y="502" font-size="10" class="mut">ops.quarantine · ops.dq_results</text>
  <text x="967" y="{H - 19}" font-size="9.5" class="dim">CI/CD: GitHub Actions → Asset Bundles</text>
</svg>
"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print("✔", OUT, f"{OUT.stat().st_size / 1024:.0f} KB")
