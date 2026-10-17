"""Genera los diagramas `.excalidraw` de Andes Viento Austral.

    python docs/diagrams/src/build_diagrams.py
    ./docs/diagrams/build_all.sh            # + SVG, PNG, GIF y SVG animados

Cada elemento lleva `customData.step`: el orden en que aparece en las animaciones.
Los archivos resultantes son .excalidraw normales: se abren y editan en excalidraw.com.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from excalidraw_kit import (  # noqa: E402
    BLUE,
    BRONZE,
    CODE,
    CYAN,
    GOLD,
    GRAPE,
    GRAY,
    GREEN,
    HAND,
    INK,
    NORMAL,
    ORANGE,
    RED,
    SILVER,
    TEAL,
    VIOLET,
    YELLOW,
    Scene,
)

OUT = Path(__file__).resolve().parents[1]
DB, DP, IT, GH, PROC, SRC = "databricks", "data-platform", "it-icons", "github-actions", "data-processing", "data-sources"
MUTED = "#495057"


def header(s: Scene, cx: float, title: str, subtitle: str) -> None:
    s.text(cx, 0, title, size=44, anchor="n")
    s.text(cx, 60, subtitle, size=20, anchor="n", font=NORMAL, color=MUTED)


# =============================================================================
# 00 · Proceso completo (hero animado)
# =============================================================================
def proceso_completo() -> Scene:
    s = Scene(seed=2009)
    header(s, 1200, "Andes Viento Austral · del viento y el sol a una respuesta de Genie",
           "13 parques · 11 fuentes reales y sucias · medallion en Databricks · 4 Genie Agents para las áreas")
    stages = [
        ("1", "Generar", "el negocio, sintético", CYAN, PROC, "Data collection",
         "SCADA 10 min · inversores\nCMMS · CAMMESA · PPA\nclima · dólar · presupuesto", "Spark distribuido"),
        ("2", "Bronze", "lo que llegó, tal cual", BRONZE, DB, "Streaming",
         "Auto Loader + schemaHints\nschema drift HT-OS 5.0\nlinaje · rescued data", "Delta Lake"),
        ("3", "Silver", "limpio y confiable", SILVER, PROC, "Data cleansing/transformation",
         "relojes y husos · kW/MW\nsensores clavados · CDC\nreglas + cuarentena · SCD2", "foreachBatch + MERGE"),
        ("4", "Gold", "el negocio modelado", GOLD, DB, "Lakehouse",
         "estrella Kimball\npérdidas por causa\n9 marts por caso", "Liquid clustering"),
        ("5", "Semántica", "una sola verdad", VIOLET, DB, "Unity Catalog",
         "7 metric views\n7 funciones confiables\ncomments · PII · máscaras", "Unity Catalog"),
        ("6", "Genie", "las áreas preguntan", GREEN, DB, "Genie",
         "4 agents · 86 benchmarks\nAgent mode: ¿por qué?\nApp + dashboards", "Genie + AI/BI"),
    ]
    cards = []
    for i, (num, title, sub, color, lib, ic, bullets, tech) in enumerate(stages):
        s.step = i + 1
        x, y, w, h = 30 + i * 395, 140, 340, 470
        card = s.rect(x, y, w, h, color, fill="hachure", stroke_width=3)
        s.rect(x + 12, y + 12, w - 24, h - 24, (color[0], "#ffffff"), fill="solid", stroke_width=1)
        s.ellipse(x - 18, y - 22, 64, 64, color, fill="solid", label=num, size=30)
        ic_box = s.icon(lib, ic, 0, 0, 120)
        s.move_group(ic_box, x + (w - ic_box["width"]) / 2, y + 40)
        s.text(x + w / 2, y + 180, title, size=34, anchor="n", color=color[0])
        s.text(x + w / 2, y + 225, sub, size=17, anchor="n", font=NORMAL, color=MUTED)
        s.text(x + w / 2, y + 268, bullets, size=18, anchor="n", align="center")
        s.text(x + w / 2, y + h - 58, tech, size=16, anchor="n", font=CODE, color=color[0])
        if cards:
            s.arrow(cards[-1], card, color=color[0], width=4)
        cards.append(card)
    s.step = 7
    s.line([(60, 660), (2340, 660)], color="#adb5bd", width=2, dashed=True)
    areas = [
        (ORANGE, "Operación de parques", "¿por qué Cañadón León\ngeneró 18 % menos en julio?"),
        (RED, "Mantenimiento", "¿qué multiplicadora\nse va a romper?"),
        (BLUE, "Comercial PPA", "¿llegamos al volumen\ndel data center?"),
        (TEAL, "Finanzas", "¿en qué parque\nponemos baterías?"),
        (GRAPE, "HSE / Puna", "¿cuándo limpiar paneles\ncon el agua justa?"),
    ]
    for k, (color, title, q) in enumerate(areas):
        x = 30 + k * 475
        s.rect(x, 690, 445, 150, color, fill="solid")
        ic_box = s.icon(IT, "User", 0, 0, 64)
        s.move_group(ic_box, x + 16, 690 + (150 - ic_box["height"]) / 2)
        s.text(x + 100, 704, title, size=24, color=color[0])
        s.text(x + 100, 745, q, size=18, font=HAND, color="#343a40")
    s.step = 8
    stats = [("380", "aerogeneradores (SF=1)", CYAN), ("1,2 M", "paneles en la Puna", YELLOW),
             ("11 → 40", "fuentes → tablas", BRONZE), ("6", "casos de negocio", GOLD),
             ("4", "Genie Agents", GREEN), ("21", "módulos de aprendizaje", TEAL)]
    for k, (big, small, color) in enumerate(stats):
        x = 30 + k * 395
        s.rect(x, 880, 340, 120, color, fill="solid", stroke_width=2)
        s.text(x + 170, 888, big, size=46, anchor="n", color=color[0])
        s.text(x + 170, 955, small, size=19, anchor="n", font=NORMAL, color="#343a40")
    return s


# =============================================================================
# 01 · La empresa: parques, bases y áreas
# =============================================================================
def empresa() -> Scene:
    s = Scene(seed=13)
    header(s, 900, "Andes Viento Austral S.A. · dónde está cada cosa",
           "9 parques eólicos en la Patagonia · 4 solares en la Puna y Catamarca · 2 bases de mantenimiento")
    s.step = 1
    s.zone(20, 130, 860, 1010, "PATAGONIA · viento (Chubut y Santa Cruz)", BLUE, icon=(IT, "Signal", 40))
    wind = [("RAW", "Rawson Sur", "45 × 3,6 MW · AWS · fibra", 380), ("MAD", "Puerto Madryn Norte", "40 × 3,6 MW · AWS", 440),
            ("GAR", "Garayalde", "35 × 3,0 MW · PEI · VSAT", 160), ("CRV", "Cerro Arenales", "50 × 3,6 MW · AWS · renombrado 2024", 25),
            ("PAM", "Pampa del Castillo", "45 × 3,0 MW · PEI · huso UTC 2024", 60),
            ("DES", "Bahía Deseado", "38 × 4,5 MW · HTW · VSAT", 290), ("PIC", "Pico Truncado Alto", "42 × 4,5 MW · HTW", 130),
            ("SJU", "San Julián Meseta", "40 × 4,5 MW · HTW · VSAT", 350), ("LEO", "Cañadón León", "45 × 4,5 MW · HTW · 520 km", 520)]
    base = s.row_card(IT, "Home", 300, 190, 280, 80, ORANGE, "Base Patagonia", "Comodoro Rivadavia")
    for i, (code, name, sub, km) in enumerate(wind):
        s.step = 2 + i // 3
        col, row = i % 2, i // 2
        x, y = 50 + col * 410, 300 + row * 160
        color = RED if code == "LEO" else (BLUE if km < 300 else CYAN)
        card = s.row_card(IT, "Signal", x, y, 390, 110, color, f"{code} · {name}", sub, icon_size=52)
        s.text(x + 380, y + 8, f"{km} km", size=16, anchor="ne", font=CODE, color=MUTED)
        if i in (3, 4):
            s.arrow(base, card, "bottom", "top", color=ORANGE, dashed=True, width=1)
    s.step = 5
    s.zone(920, 130, 860, 520, "NOA · sol (Jujuy y Catamarca)", YELLOW, icon=(IT, "Event", 40))
    sol = [("SUS", "Susques Solar", "400 mil paneles · 3.700 m · VSAT"), ("ABR", "Abra Pampa Solar", "300 mil paneles · 3.480 m"),
           ("TIN", "Tinogasta Sol", "250 mil paneles · fibra"), ("FIA", "Fiambalá Solar", "250 mil · exportaba MW como kW")]
    s.row_card(IT, "Home", 1200, 190, 280, 80, ORANGE, "Base NOA", "San Salvador de Jujuy")
    for i, (code, name, sub) in enumerate(sol):
        x, y = 950 + (i % 2) * 410, 300 + (i // 2) * 160
        s.row_card(IT, "Pie chart", x, y, 390, 110, YELLOW, f"{code} · {name}", sub, icon_size=52)
    s.step = 6
    s.zone(920, 680, 860, 460, "Quién le pregunta qué a Genie", GREEN, icon=(DB, "Genie", 40))
    people = [("Lucía Ferreyra · CEO", "¿por qué generamos menos que el presupuesto?"),
              ("Martín Quiroga · Operaciones", "¿qué parque perdió más energía ayer?"),
              ("Ramiro Llancaqueo · Mantenimiento", "¿qué turbina se va a romper?"),
              ("Sofía Bertolini · Comercial", "¿llegamos al volumen del PPA?"),
              ("Diego Achával · CFO", "¿en qué parque ponemos baterías?"),
              ("Andrea Colque · HSE", "¿cuánta agua usamos en la Puna?")]
    for i, (who, q) in enumerate(people):
        y = 740 + i * 64
        s.text(950, y, who, size=19, color=GREEN[0])
        s.text(1300, y + 2, q, size=17, font=NORMAL, color="#343a40")
    return s


# =============================================================================
# 02 · Arquitectura
# =============================================================================
def arquitectura() -> Scene:
    s = Scene(seed=11)
    header(s, 1250, "Arquitectura · Databricks serverless + Unity Catalog",
           "landing (Volume) → bronze → silver → gold → capa semántica → Genie · todo como código en un Asset Bundle")
    s.step = 1
    s.zone(20, 130, 360, 860, "Fuentes", GRAY, icon=(PROC, "Data collection", 40))
    srcs = [(IT, "Signal", "SCADA turbinas", "JSON gz · 10 min"), (IT, "Pie chart", "Inversores solares", "CSV · 5 min"),
            (IT, "Settings", "CMMS", "activos · órdenes · CDC"), (IT, "Network", "CAMMESA", "despacho · spot ;"),
            (IT, "Document", "Contratos PPA", "CSV CDC"), (IT, "Cloud", "Clima", "observado + pronóstico"),
            (IT, "Bar chart", "Finanzas", "dólar BNA · presupuesto")]
    cards = [s.row_card(lib, ic, 40, 190 + i * 110, 320, 92, GRAY, t, st, icon_size=50) for i, (lib, ic, t, st) in enumerate(srcs)]
    s.step = 2
    land = s.icon_card(DP, "S3 Bucket", 430, 420, 220, 230, GRAY, "landing", "UC Volume\ningest_date=…", icon_size=90)
    for c in cards:
        s.arrow(c, land, color="#adb5bd", width=1)
    s.step = 3
    br = s.icon_card(DB, "Streaming", 710, 420, 220, 230, BRONZE, "bronze", "Auto Loader\nschemaHints · drift", icon_size=90)
    s.arrow(land, br, color=BRONZE[0], width=3)
    s.step = 4
    sv = s.icon_card(PROC, "Data cleansing/transformation", 990, 420, 240, 230, SILVER, "silver",
                     "relojes · unidades · CDC\nSCD2 · cuarentena", icon_size=90)
    s.arrow(br, sv, color=SILVER[0], width=3)
    s.step = 5
    gd = s.icon_card(DB, "Lakehouse", 1290, 420, 240, 230, GOLD, "gold", "7 dims · 6 facts\n9 marts SQL", icon_size=90)
    s.arrow(sv, gd, color=GOLD[0], width=3)
    s.step = 6
    sem = s.icon_card(DB, "Unity Catalog", 1590, 420, 240, 230, VIOLET, "semántica", "metric views\nfunciones · gobierno",
                      icon_size=90)
    s.arrow(gd, sem, color=VIOLET[0], width=3)
    s.step = 7
    s.zone(1890, 130, 590, 860, "Consumo", GREEN, icon=(DB, "Databricks One", 40))
    outs = [(DB, "Genie", "4 Genie Agents", "Operación · Mantenimiento · Comercial · Finanzas"),
            (DB, "Agent Bricks", "Agent mode / Genie One", "preguntas de ¿por qué?"),
            (DB, "Dashboards", "6 dashboards AI/BI", "uno por caso de negocio"),
            (DB, "Apps", "App de chat", "Conversation API"),
            (DB, "Notebooks", "Genie Code", "instrucciones + 2 skills")]
    for i, (lib, ic, t, st) in enumerate(outs):
        c = s.row_card(lib, ic, 1910, 190 + i * 150, 550, 120, GREEN, t, st, icon_size=70, title_size=22)
        s.arrow(sem, c, color=GREEN[0], width=1)
    s.step = 8
    s.zone(430, 720, 1400, 270, "Transversal", ORANGE)
    trans = [(DB, "Lakeflow Jobs", "Lakeflow Jobs", "e2e · diario · mantenimiento"),
             (DB, "Lakeflow Declarative Pipelines", "Declarativo", "LDP SQL + expectations"),
             (GH, "GitHub Actions", "CI/CD", "ruff · pytest · bundle"),
             (IT, "Firewall", "ops", "auditoría · calidad")]
    for i, (lib, ic, t, st) in enumerate(trans):
        s.row_card(lib, ic, 450 + i * 345, 790, 325, 110, ORANGE, t, st, icon_size=60)
    return s


# =============================================================================
# 03 · Linaje de tablas
# =============================================================================
def linaje() -> Scene:
    s = Scene(seed=21)
    header(s, 1250, "Linaje · de cada fuente a cada pregunta",
           "las flechas son lecturas reales (Unity Catalog las muestra en la pestaña Lineage)")
    cols = [
        ("bronze", BRONZE, ["scada_turbine", "inverter_5min", "cmms_assets", "cmms_work_orders", "cammesa_dispatch",
                            "cammesa_spot_prices", "ppa_contracts", "weather", "fx_rates", "generation_budget"]),
        ("silver", SILVER, ["scada_10min", "inverter_5min", "assets_history (SCD2)", "asset_tags", "work_orders",
                            "curtailment_instructions", "spot_prices", "contracts_history (SCD2)", "weather_hourly",
                            "fx_rates", "generation_budget"]),
        ("gold · estrella", GOLD, ["fact_turbine_10min", "fact_inverter_hourly", "fact_curtailment_hourly",
                                   "fact_availability_daily", "fact_maintenance_order", "dim_turbine", "dim_contract",
                                   "dim_weather", "dim_date"]),
        ("gold · marts", ORANGE, ["mart_generation_vs_budget", "fact_ppa_settlement", "mart_curtailment_battery",
                                  "mart_turbine_health", "mart_panel_cleaning", "mart_ppa_forecast",
                                  "mart_warranty_claims", "v_park_daily"]),
        ("semántica", VIOLET, ["mv_generacion", "mv_curtailment", "mv_mantenimiento", "mv_disponibilidad", "mv_ppa",
                               "fn_explicar_desvio", "fn_ranking_baterias", "fn_turbinas_en_riesgo"]),
    ]
    boxes: dict[str, dict] = {}
    for c, (title, color, items) in enumerate(cols):
        s.step = c + 1
        x = 30 + c * 500
        s.text(x + 210, 120, title, size=30, anchor="n", color=color[0])
        for i, name in enumerate(items):
            b = s.rect(x, 170 + i * 74, 420, 58, color, fill="solid", label=name, size=17, font=CODE)
            boxes[f"{c}:{name}"] = b
    edges = [
        (0, "scada_turbine", 1, "scada_10min"), (0, "inverter_5min", 1, "inverter_5min"),
        (0, "cmms_assets", 1, "assets_history (SCD2)"), (0, "cmms_assets", 1, "asset_tags"),
        (0, "cmms_work_orders", 1, "work_orders"), (0, "cammesa_dispatch", 1, "curtailment_instructions"),
        (0, "cammesa_spot_prices", 1, "spot_prices"), (0, "ppa_contracts", 1, "contracts_history (SCD2)"),
        (0, "weather", 1, "weather_hourly"), (0, "fx_rates", 1, "fx_rates"), (0, "generation_budget", 1, "generation_budget"),
        (1, "scada_10min", 2, "fact_turbine_10min"), (1, "asset_tags", 1, "scada_10min"),
        (1, "curtailment_instructions", 2, "fact_turbine_10min"), (1, "assets_history (SCD2)", 2, "dim_turbine"),
        (1, "inverter_5min", 2, "fact_inverter_hourly"), (1, "work_orders", 2, "fact_maintenance_order"),
        (1, "contracts_history (SCD2)", 2, "dim_contract"), (1, "weather_hourly", 2, "dim_weather"),
        (1, "fx_rates", 2, "dim_date"), (1, "spot_prices", 2, "fact_curtailment_hourly"),
        (2, "fact_turbine_10min", 2, "fact_curtailment_hourly"), (2, "fact_turbine_10min", 2, "fact_availability_daily"),
        (2, "fact_turbine_10min", 3, "mart_generation_vs_budget"), (2, "fact_inverter_hourly", 3, "mart_panel_cleaning"),
        (1, "generation_budget", 3, "mart_generation_vs_budget"), (3, "mart_generation_vs_budget", 3, "fact_ppa_settlement"),
        (2, "fact_curtailment_hourly", 3, "mart_curtailment_battery"), (2, "fact_turbine_10min", 3, "mart_turbine_health"),
        (2, "fact_availability_daily", 3, "mart_warranty_claims"), (2, "fact_availability_daily", 3, "mart_ppa_forecast"),
        (3, "v_park_daily", 4, "mv_generacion"), (2, "fact_curtailment_hourly", 4, "mv_curtailment"),
        (2, "fact_maintenance_order", 4, "mv_mantenimiento"), (3, "mart_warranty_claims", 4, "mv_disponibilidad"),
        (3, "fact_ppa_settlement", 4, "mv_ppa"), (3, "mart_generation_vs_budget", 4, "fn_explicar_desvio"),
        (3, "mart_curtailment_battery", 4, "fn_ranking_baterias"), (3, "mart_turbine_health", 4, "fn_turbinas_en_riesgo"),
    ]
    for a, an, b, bn in edges:
        s.step = max(a, b) + 1
        same = a == b
        s.arrow(boxes[f"{a}:{an}"], boxes[f"{b}:{bn}"], "bottom" if same else "right", "top" if same else "left",
                color="#868e96", width=1, roughness=0)
    return s


# =============================================================================
# 04 · Modelo estrella
# =============================================================================
def modelo_estrella() -> Scene:
    s = Scene(seed=31)
    header(s, 1100, "Modelo estrella (Kimball) · gold",
           "hechos al centro, dimensiones conformadas alrededor · SCD2 en turbinas y contratos")
    s.step = 1
    f = s.table(820, 360, "fact_turbine_10min", [
        ("turbine_id", "string", "PK"), ("ts_utc", "timestamp", "PK"), ("date_key", "int", "FK"), ("park_key", "int", "FK"),
        ("turbine_key", "bigint", "FK"), ("weather_key", "bigint", "FK"), ("state", "string", "DD"),
        ("energy_kwh", "double", "M"), ("potential_kwh", "double", "M"), ("lost_curtailment_kwh", "double", "M"),
        ("lost_fault_kwh", "double", "M"), ("lost_icing_kwh", "double", "M"), ("gearbox_bearing_c", "double", "M")],
        GOLD, width=380, subtitle="1 fila por turbina cada 10 minutos")
    s.step = 2
    dims = [
        (120, 150, "dim_turbine", [("turbine_key", "bigint", "PK"), ("turbine_id", "string", "NK"), ("turbine_tag", "string"),
                                   ("gearbox_serial", "string", "SCD"), ("firmware", "string", "SCD"),
                                   ("effective_from", "ts"), ("effective_to", "ts")], VIOLET, "SCD2"),
        (120, 620, "dim_weather", [("weather_key", "bigint", "PK"), ("park_code", "string"), ("date", "date"),
                                   ("weather_condition", "string"), ("ice_risk_hours", "int"), ("snow_cm", "double")], CYAN, None),
        (1500, 150, "dim_park", [("park_key", "int", "PK"), ("park_code", "string", "NK"), ("park_name", "string"),
                                 ("province", "string"), ("installed_mw", "double"), ("turbine_manufacturer", "string")], BLUE, None),
        (1500, 620, "dim_date", [("date_key", "int", "PK"), ("date", "date"), ("year_month", "string"), ("season", "string"),
                                 ("is_holiday", "boolean"), ("fx_ars_usd", "double")], TEAL, None),
    ]
    tables = {}
    for x, y, name, cols_, color, sub in dims:
        tables[name] = s.table(x, y, name, cols_, color, width=330, subtitle=sub)
    for name, side in (("dim_turbine", "left"), ("dim_weather", "left"), ("dim_park", "right"), ("dim_date", "right")):
        t = tables[name]
        s.arrow(f, t, side, "right" if side == "left" else "left", color="#868e96", width=2)
    s.step = 3
    s.text(1100, 1060, "otros hechos que comparten dimensiones:", size=22, anchor="n", color=MUTED)
    others = [("fact_inverter_hourly", "inversor × hora"), ("fact_curtailment_hourly", "parque × hora"),
              ("fact_availability_daily", "turbina × día"), ("fact_maintenance_order", "orden (accumulating)"),
              ("fact_ppa_settlement", "contrato × mes")]
    for i, (n, g) in enumerate(others):
        s.rect(60 + i * 430, 1110, 400, 80, GOLD, fill="solid", label=f"{n}\n{g}", size=16, font=CODE)
    s.note(1540, 1000, 560, "Identidad de pérdidas (en cada fila):\npotencial = generado + red + fallas\n"
                             "              + mantenimiento + hielo + otras", GREEN, size=17)
    return s


# =============================================================================
# 05 · Matriz bus
# =============================================================================
def matriz_bus() -> Scene:
    s = Scene(seed=41)
    header(s, 900, "Matriz bus · procesos de negocio × dimensiones conformadas", "● clave directa · ○ vía source_parks")
    dims = ["date", "park", "turbine", "inverter", "weather", "contract", "crew"]
    rows = [("Medición de turbinas", "fact_turbine_10min", "●●●·●··"), ("Generación solar", "fact_inverter_hourly", "●●·●●··"),
            ("Curtailment", "fact_curtailment_hourly", "●●·····"), ("Disponibilidad", "fact_availability_daily", "●●●····"),
            ("Mantenimiento", "fact_maintenance_order", "●●●●··●"), ("Liquidación PPA", "fact_ppa_settlement", "●○···●·")]
    s.step = 1
    for j, d in enumerate(dims):
        s.rect(640 + j * 160, 130, 150, 60, BLUE, fill="solid", label=d, size=20)
    for i, (proc, fact, marks) in enumerate(rows):
        s.step = 2 + i
        y = 210 + i * 90
        s.rect(20, y, 600, 76, GOLD, fill="solid", label=f"{proc}\n{fact}", size=17)
        for j, m in enumerate(marks):
            if m == "·":
                s.rect(640 + j * 160, y, 150, 76, ("#dee2e6", "#f8f9fa"), fill="solid")
            else:
                s.rect(640 + j * 160, y, 150, 76, GREEN if m == "●" else YELLOW, fill="solid", label=m, size=34)
    return s


# =============================================================================
# 06 · SCD2
# =============================================================================
def scd2() -> Scene:
    s = Scene(seed=51)
    header(s, 1000, "SCD Tipo 2 · la historia de la turbina LEO-01",
           "cada cambio de componente, firmware o nombre crea una versión · los hechos se unen point-in-time")
    s.step = 1
    events = [("2023-02-14", "alta", "GBX412233 · HT-OS 4.1", BLUE), ("2025-03-01", "firmware HT-OS 5.0", "+3 sensores (drift)", VIOLET),
              ("2025-07-26", "falla multiplicadora", "21 días parada", RED), ("2025-08-16", "multiplicadora nueva", "GBX887120", GREEN)]
    s.line([(80, 300), (1920, 300)], color="#868e96", width=3)
    for i, (d, t, sub, color) in enumerate(events):
        s.step = 1 + i
        x = 120 + i * 470
        s.ellipse(x - 14, 286, 28, 28, color, fill="solid")
        s.text(x, 240, d, size=20, anchor="n", font=CODE, color=color[0])
        s.text(x, 330, t, size=22, anchor="n", color=color[0])
        s.text(x, 365, sub, size=16, anchor="n", font=NORMAL, color=MUTED)
    s.step = 5
    rows = [("v1", "GBX412233", "HT-OS 4.1", "ALTA", "1900-01-01", "2025-03-01", "false"),
            ("v2", "GBX412233", "HT-OS 5.0", "ACTUALIZACION_FIRMWARE", "2025-03-01", "2025-08-16", "false"),
            ("v3", "GBX887120", "HT-OS 5.0", "CAMBIO_MULTIPLICADORA", "2025-08-16", "9999-12-31", "true")]
    heads = ["versión", "gearbox_serial", "firmware", "change_reason", "effective_from", "effective_to", "is_current"]
    widths = [110, 200, 160, 330, 200, 200, 150]
    x0 = 60
    for j, h in enumerate(heads):
        s.rect(x0 + sum(widths[:j]), 460, widths[j], 50, VIOLET, fill="solid", label=h, size=16, font=CODE)
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            color = GREEN if (i == 2 and j == 6) else ("#ced4da", "#ffffff")
            s.rect(x0 + sum(widths[:j]), 510 + i * 50, widths[j], 50, color, fill="solid", label=v, size=15, font=CODE)
    s.step = 6
    s.note(60, 700, 900, "Una medición de julio 2025 se une con v2 (la multiplicadora vieja, la que se rompió).\n"
                         "Una de septiembre, con v3. El modelo predictivo compara antes y después del cambio.", YELLOW)
    s.note(1000, 700, 760, "Casos finos: varios cambios en un lote · re-envíos idénticos\n"
                           "· llegadas tardías · bajas (op = D) · idempotencia", CYAN)
    return s


# =============================================================================
# 07 · Ejecución de Spark (el generador)
# =============================================================================
def ejecucion_spark() -> Scene:
    s = Scene(seed=61)
    header(s, 1000, "Cómo ejecuta Spark el generador de SCADA",
           "driver: tablas guía chicas · executors: millones de filas con expresiones de columna")
    s.step = 1
    drv = s.icon_card(IT, "Server", 80, 150, 420, 330, ORANGE, "Driver",
                      "clima AR(1) · fallas · curtailment\nsuciedad · presupuesto P50\n(secuencial, miles de filas)", icon_size=90)
    s.step = 2
    plan = s.rect(620, 180, 560, 270, BLUE, fill="solid",
                  label="plan (Catalyst + Photon)\n\nspark.range(slots)\n× broadcast(flota)\n⨝ broadcast(tablas guía)\n→ física en columnas",
                  size=19, font=CODE)
    s.arrow(drv, plan, color=ORANGE[0], width=3, label="broadcast")
    s.step = 3
    for i in range(4):
        e = s.icon_card(IT, "Host", 1320 + (i % 2) * 330, 150 + (i // 2) * 290, 300, 260, GREEN, f"executor {i + 1}",
                        f"partición {i + 1}: ~600 mil filas\nxxhash64(id, sal) = azar fijo", icon_size=70)
        s.arrow(plan, e, color=GREEN[0], width=1)
    s.step = 4
    s.rect(620, 560, 1360, 120, BRONZE, fill="solid",
           label="escritura: repartition(ingest_date) → 1 archivo JSON.gz por día en el Volume (≈1.370 archivos a SF 0,1)",
           size=19)
    s.step = 5
    s.note(80, 560, 480, "¿Por qué no F.rand()?\nDepende del particionado: con otro\ncluster saldrían otros datos.", YELLOW)
    return s


# =============================================================================
# 08 · DAG del job
# =============================================================================
def dag_job() -> Scene:
    s = Scene(seed=71)
    header(s, 1250, "Lakeflow Job · andes-viento-e2e", "condition + 3 for_each + run_if + outcome · serverless")
    s.step = 1
    setup = s.rect(30, 400, 200, 90, GRAY, fill="solid", label="setup", size=22)
    cond = s.diamond(290, 380, 220, 130, YELLOW, fill="solid", label="should\ngenerate?", size=18)
    s.arrow(setup, cond, color=INK)
    s.step = 2
    gen = s.rect(580, 180, 260, 140, CYAN, fill="solid", label="generate_data\nfor_each × 11\n(3 en paralelo)", size=18)
    s.arrow(cond, gen, "top", "left", color=GREEN[0], label="true", elbow=True)
    s.step = 3
    br = s.rect(920, 400, 230, 90, BRONZE, fill="solid", label="bronze_ingest\nrun_if NONE_FAILED", size=17)
    s.arrow(gen, br, "right", "top", color=INK, elbow=True)
    s.arrow(cond, br, "bottom", "bottom", color=RED[0], label="false", via=[(400, 600), (1035, 600)])
    s.step = 4
    sr = s.rect(1220, 380, 250, 130, SILVER, fill="solid", label="silver_reference\nfor_each × 8", size=18)
    st = s.rect(1530, 380, 250, 130, SILVER, fill="solid", label="silver_telemetry\nfor_each × 3", size=18)
    s.arrow(br, sr, color=INK)
    s.arrow(sr, st, color=INK)
    s.step = 5
    gd = s.rect(1840, 400, 200, 90, GOLD, fill="solid", label="gold_dimensions", size=17)
    gf = s.rect(2090, 400, 180, 90, GOLD, fill="solid", label="gold_facts", size=17)
    gm = s.rect(2320, 400, 180, 90, GOLD, fill="solid", label="gold_marts", size=17)
    s.arrow(st, gd, color=INK)
    s.arrow(gd, gf, color=INK)
    s.arrow(gf, gm, color=INK)
    s.step = 6
    gov = s.rect(2320, 160, 180, 90, VIOLET, fill="solid", label="governance", size=17)
    sem = s.rect(2320, 640, 180, 90, VIOLET, fill="solid", label="semantic_layer", size=17)
    qg = s.rect(2560, 400, 180, 90, GREEN, fill="solid", label="quality_gate", size=17)
    s.arrow(gm, gov, "top", "bottom", color=INK)
    s.arrow(gm, sem, "bottom", "top", color=INK)
    s.arrow(gov, qg, "right", "top", color=INK, elbow=True)
    s.arrow(sem, qg, "right", "bottom", color=INK, elbow=True)
    s.step = 7
    s.note(580, 760, 1000, "Error real de NovaMart (ya aplicado): las dependencias de un if/else\n"
                           "DEBEN declarar outcome: \"true\" o \"false\" (si no: INVALID_PARAMETER_VALUE).", RED)
    s.note(1640, 760, 860, "Job diario: generate_next_day → run_job_task(e2e, generate=false)\n"
                           "Job de mantenimiento: OPTIMIZE + VACUUM + ANALYZE", CYAN)
    return s


# =============================================================================
# 09 · CI/CD
# =============================================================================
def cicd() -> Scene:
    s = Scene(seed=81)
    header(s, 1100, "CI/CD · GitHub Actions + Databricks Asset Bundles", "todo push se valida · el deploy es manual con aprobación")
    s.step = 1
    dev = s.icon_card(IT, "User", 30, 200, 240, 220, GRAY, "vos + Genie Code", "git push", icon_size=80)
    gh = s.icon_card(GH, "GitHub", 330, 200, 240, 220, GRAY, "GitHub", "rama / PR", icon_size=80)
    s.arrow(dev, gh, color=INK)
    jobs = [("lint", "ruff + JSON válidos", BLUE), ("unit-tests", "pytest + Spark/Delta", BLUE),
            ("integration", "pipeline local 5 sem.", BLUE), ("bundle-validate", "dev y prod", VIOLET)]
    prev = gh
    for i, (t, sub, color) in enumerate(jobs):
        s.step = 2 + i
        c = s.icon_card(GH, "GitHub Actions", 640 + i * 280, 200, 250, 220, color, t, sub, icon_size=70)
        s.arrow(prev, c, color=INK)
        prev = c
    s.step = 6
    dep = s.icon_card(DB, "Databricks", 1800, 140, 300, 160, GREEN, "deploy -t dev", "workflow_dispatch", icon_size=60)
    prod = s.icon_card(DB, "Databricks", 1800, 340, 300, 160, RED, "deploy -t prod", "environment con aprobación",
                       icon_size=60)
    s.arrow(prev, dep, color=GREEN[0])
    s.arrow(prev, prod, color=RED[0])
    s.step = 7
    s.note(640, 480, 1460, "Secretos: DATABRICKS_TOKEN en Secrets (repo y environment prod) · DATABRICKS_HOST en Variables.\n"
                           "Nunca en el código ni en los logs. El deploy puede incluir los Genie Agents (deploy_genie.py).",
           YELLOW)
    return s


# =============================================================================
# 10 · Ruta de aprendizaje (animada)
# =============================================================================
def ruta_aprendizaje() -> Scene:
    s = Scene(seed=91)
    header(s, 1150, "Ruta de aprendizaje · 21 módulos con los datos de Andes", "de un SELECT a un Genie Agent en producción")
    mods = [("00", "Entorno", GRAY), ("01", "SELECT", BLUE), ("02", "Agregar", BLUE), ("03", "JOINs", BLUE),
            ("04", "CTEs", BLUE), ("05", "Ventanas", BLUE), ("06", "Fechas y husos", BLUE), ("07", "SQL avanzado", BLUE),
            ("08", "Spark", ORANGE), ("09", "Transformar", ORANGE), ("10", "Performance", ORANGE), ("11", "Delta", BRONZE),
            ("12", "Streaming", BRONZE), ("13", "Calidad y SCD2", SILVER), ("14", "Modelado", GOLD), ("15", "Declarativo", GOLD),
            ("16", "Gobierno", VIOLET), ("17", "Métricas", VIOLET), ("18", "Genie", GREEN), ("19", "CI/CD", TEAL),
            ("20", "Desafíos", RED)]
    prev = None
    for i, (n, t, color) in enumerate(mods):
        s.step = 1 + i // 3
        row, col = divmod(i, 7)
        col = col if row % 2 == 0 else 6 - col
        x, y = 40 + col * 330, 150 + row * 260
        c = s.rect(x, y, 280, 170, color, fill="solid")
        s.text(x + 140, y + 18, n, size=44, anchor="n", color=color[0])
        s.text(x + 140, y + 92, t, size=24, anchor="n")
        if prev:
            s.arrow(prev, c, "right" if (row % 2 == 0 and col > 0) else ("left" if col < 6 or row % 2 else "bottom"),
                    "left" if (row % 2 == 0 and col > 0) else ("right" if row % 2 and col < 6 else "top"),
                    color="#868e96", width=2)
        prev = c
    return s


# =============================================================================
# 11 · Capa Genie
# =============================================================================
def capa_genie() -> Scene:
    s = Scene(seed=101)
    header(s, 1100, "La capa Genie · por qué responde bien", "de abajo hacia arriba: si Genie se equivoca, el arreglo casi siempre está abajo")
    layers = [("gold bien modelado", "grano claro · identidad de pérdidas · v_park_daily (tabla ancha)", GOLD),
              ("comentarios + PK/FK + tags", "governance/data_dictionary.yml → 150 COMMENT", BLUE),
              ("metric views (7)", "métricas oficiales con sinónimos: 'recorte', 'multa del fabricante'", VIOLET),
              ("funciones de UC (7)", "trusted assets: fn_explicar_desvio, fn_ranking_baterias...", TEAL),
              ("Genie Agents (4)", "instrucciones cortas · ejemplos SQL · 86 benchmarks", GREEN),
              ("Agent mode / Genie One", "¿por qué Cañadón León generó 18 % menos en julio?", ORANGE)]
    for i, (t, sub, color) in enumerate(layers):
        s.step = i + 1
        w = 1900 - i * 230
        x = 1100 - w / 2
        y = 1060 - i * 150
        s.rect(x, y, w, 130, color, fill="solid", label=f"{t}\n{sub}", size=20)
    return s


DIAGRAMS = {
    "00_proceso_completo": proceso_completo,
    "01_empresa": empresa,
    "02_arquitectura": arquitectura,
    "03_linaje": linaje,
    "04_modelo_estrella": modelo_estrella,
    "05_matriz_bus": matriz_bus,
    "06_scd2": scd2,
    "07_ejecucion_spark": ejecucion_spark,
    "08_dag_job": dag_job,
    "09_cicd": cicd,
    "10_ruta_aprendizaje": ruta_aprendizaje,
    "11_capa_genie": capa_genie,
}


if __name__ == "__main__":
    only = sys.argv[1:]
    for name, fn in DIAGRAMS.items():
        if only and name not in only:
            continue
        fn().save(OUT / f"{name}.excalidraw")
        print("ok", name)
