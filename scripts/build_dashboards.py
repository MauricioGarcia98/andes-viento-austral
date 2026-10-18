"""Genera los dashboards AI/BI (Lakeview) de cada caso de negocio en dashboards/*.lvdash.json.

    python scripts/build_dashboards.py

¿Por qué generarlos? Un .lvdash.json escrito a mano tiene cientos de líneas repetidas.
Acá cada dashboard es una lista corta de datasets + widgets; el script arma el JSON.
Las consultas usan `gold.<tabla>` sin catálogo: el bundle fija `dataset_catalog` por target.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "dashboards"
COLORS = {"rojo": "#E5484D", "verde": "#30A46C", "azul": "#3E63DD", "naranja": "#F76B15", "gris": "#8B8D98"}


def _field(name: str, expr: str) -> dict:
    return {"name": name, "expression": expr}


class Page:
    def __init__(self, name: str, title: str):
        self.name, self.title, self.layout, self.y, self._n = name, title, [], 0, 0

    def _wid(self) -> str:
        self._n += 1
        return f"{self.name}_w{self._n}"

    def _place(self, widget: dict, width: int, height: int, x: int | None = None, newline: bool = True) -> None:
        pos = {"x": 0 if x is None else x, "y": self.y, "width": width, "height": height}
        self.layout.append({"widget": widget, "position": pos})
        if newline:
            self.y += height

    def text(self, md: str, height: int = 2) -> Page:
        self._place({"name": self._wid(), "multilineTextboxSpec": {"lines": md.splitlines()}}, 6, height)
        return self

    def counters(self, dataset: str, items: list[tuple[str, str, str]], height: int = 3) -> Page:
        width = 6 // len(items)
        for i, (title, expr, fmt) in enumerate(items):
            w = {"name": self._wid(),
                 "queries": [{"name": "main_query", "query": {"datasetName": dataset, "fields": [_field("value", expr)],
                                                               "disaggregated": False}}],
                 "spec": {"version": 2, "widgetType": "counter",
                          "encodings": {"value": {"fieldName": "value", "displayName": title,
                                                  **({"format": {"type": fmt}} if fmt else {})}},
                          "frame": {"showTitle": True, "title": title}}}
            self._place(w, width, height, x=i * width, newline=i == len(items) - 1)
        return self

    def chart(self, kind: str, dataset: str, title: str, x: tuple[str, str, str], ys: list[tuple[str, str]],
              color: tuple[str, str] | None = None, width: int = 6, height: int = 6, x_pos: int = 0,
              newline: bool = True, stacked: bool = False) -> Page:
        """kind: bar | line | area. x = (campo, expresión, tipo de escala: categorical|temporal|quantitative)."""
        fields = [_field(x[0], x[1])] + [_field(n, e) for n, e in ys]
        enc: dict = {"x": {"fieldName": x[0], "scale": {"type": x[2]}, "displayName": x[0]}}
        if len(ys) == 1:
            enc["y"] = {"fieldName": ys[0][0], "scale": {"type": "quantitative"}, "displayName": ys[0][0]}
        else:
            enc["y"] = {"scale": {"type": "quantitative"},
                        "fields": [{"fieldName": n, "displayName": n} for n, _ in ys]}
        if color:
            fields.append(_field(color[0], color[1]))
            enc["color"] = {"fieldName": color[0], "scale": {"type": "categorical"}, "displayName": color[0]}
        spec = {"version": 3, "widgetType": kind, "encodings": enc, "frame": {"showTitle": True, "title": title}}
        if stacked:
            spec["mark"] = {"layout": "stack"}
        w = {"name": self._wid(),
             "queries": [{"name": "main_query", "query": {"datasetName": dataset, "fields": fields,
                                                           "disaggregated": False}}],
             "spec": spec}
        self._place(w, width, height, x=x_pos, newline=newline)
        return self

    def table(self, dataset: str, title: str, columns: list[str], height: int = 7) -> Page:
        w = {"name": self._wid(),
             "queries": [{"name": "main_query", "query": {"datasetName": dataset,
                                                           "fields": [_field(c, f"`{c}`") for c in columns],
                                                           "disaggregated": True}}],
             "spec": {"version": 1, "widgetType": "table",
                      "encodings": {"columns": [{"fieldName": c, "displayName": c} for c in columns]},
                      "frame": {"showTitle": True, "title": title}}}
        self._place(w, 6, height)
        return self

    def to_json(self) -> dict:
        return {"name": self.name, "displayName": self.title, "pageType": "PAGE_TYPE_CANVAS", "layout": self.layout}


def dashboard(datasets: dict[str, tuple[str, str]], pages: list[Page]) -> dict:
    return {
        "datasets": [{"name": k, "displayName": v[0], "queryLines": [line + "\n" for line in v[1].strip().splitlines()]}
                     for k, v in datasets.items()],
        "pages": [p.to_json() for p in pages],
    }


# =============================================================================
# 1 · Dirección: generación vs. presupuesto
# =============================================================================
def direccion() -> dict:
    ds = {
        "monthly": ("Real vs presupuesto mensual", """
SELECT park_name, technology, month_start, year_month, actual_mwh, budget_p50_mwh, variance_pct,
       lost_curtailment_mwh, lost_fault_mwh, lost_maintenance_mwh, lost_icing_mwh, lost_soiling_mwh, resource_effect_mwh
FROM gold.mart_generation_vs_budget"""),
        "last12": ("Últimos 12 meses", """
SELECT sum(actual_mwh) AS actual_mwh, sum(budget_p50_mwh) AS budget_mwh,
       sum(actual_mwh) / sum(budget_p50_mwh) - 1 AS variance_pct,
       sum(lost_curtailment_mwh) AS curtailment_mwh
FROM gold.mart_generation_vs_budget
WHERE month_start > add_months((SELECT max(month_start) FROM gold.mart_generation_vs_budget), -12)"""),
        "losses_last": ("Pérdidas del último mes por parque", """
SELECT park_name, causa, mwh FROM (
  SELECT park_name, lost_curtailment_mwh AS curtailment, lost_fault_mwh AS fallas, lost_maintenance_mwh AS mantenimiento,
         lost_icing_mwh AS hielo, lost_soiling_mwh AS suciedad
  FROM gold.mart_generation_vs_budget
  WHERE month_start = (SELECT max(month_start) FROM gold.mart_generation_vs_budget)
) UNPIVOT (mwh FOR causa IN (curtailment, fallas, mantenimiento, hielo, suciedad))"""),
    }
    p = Page("resumen", "Generación vs. presupuesto")
    p.text("# Andes Viento Austral · Dirección\nGeneración real vs. presupuesto P50 aprobado y las causas del desvío. "
           "Dueña: Lucía Ferreyra (CEO).")
    p.counters("last12", [("MWh generados (12 m)", "SUM(`actual_mwh`)", None),
                          ("Desvío vs presupuesto (12 m)", "SUM(`actual_mwh`) / SUM(`budget_mwh`) - 1", "number-percent"),
                          ("MWh perdidos por curtailment (12 m)", "SUM(`curtailment_mwh`)", None)])
    p.chart("line", "monthly", "Real vs presupuesto (todas las plantas)", ("month_start", "`month_start`", "temporal"),
            [("Real MWh", "SUM(`actual_mwh`)"), ("Presupuesto MWh", "SUM(`budget_p50_mwh`)")])
    p.chart("bar", "monthly", "Desvío mensual por parque (MWh)", ("year_month", "`year_month`", "categorical"),
            [("Desvío MWh", "SUM(`actual_mwh` - `budget_p50_mwh`)")], color=("park_name", "`park_name`"), stacked=True)
    p.chart("bar", "losses_last", "Pérdidas del último mes por causa", ("park_name", "`park_name`", "categorical"),
            [("MWh", "SUM(`mwh`)")], color=("causa", "`causa`"), stacked=True)
    return dashboard(ds, [p])


# =============================================================================
# 2 · Curtailment y baterías
# =============================================================================
def curtailment() -> dict:
    ds = {
        "monthly": ("Curtailment mensual", """
SELECT p.park_name, date_format(f.reading_date, 'yyyy-MM') AS year_month, trunc(f.reading_date, 'MM') AS month_start,
       sum(f.lost_curtailment_mwh) AS curtailed_mwh, sum(f.potential_mwh) AS potential_mwh,
       sum(f.lost_value_spot_usd) AS value_spot_usd, count_if(f.has_instruction) AS hours_with_order
FROM gold.fact_curtailment_hourly f JOIN gold.dim_park p USING (park_key)
GROUP BY ALL"""),
        "hour_profile": ("Perfil horario", """
SELECT hour(hour_local) AS hora_local, sum(lost_curtailment_mwh) AS curtailed_mwh, avg(spot_usd_mwh) AS spot_usd_mwh
FROM gold.fact_curtailment_hourly GROUP BY 1"""),
        "battery": ("Ranking de baterías (12 meses)", "SELECT * FROM gold.fn_ranking_baterias(12)"),
    }
    p = Page("curtailment", "Curtailment y baterías")
    p.text("# Caso 1 · Energía perdida por curtailment\n¿Cuántos MWh y USD perdimos porque CAMMESA nos hizo bajar "
           "potencia? ¿Dónde conviene una batería? Dueño: Diego Achával (CFO).")
    p.counters("monthly", [("MWh perdidos (total)", "SUM(`curtailed_mwh`)", None),
                           ("% del potencial", "SUM(`curtailed_mwh`) / SUM(`potential_mwh`)", "number-percent"),
                           ("Horas con orden de CAMMESA", "SUM(`hours_with_order`)", None)])
    p.chart("bar", "monthly", "MWh perdidos por mes y parque", ("month_start", "`month_start`", "temporal"),
            [("MWh", "SUM(`curtailed_mwh`)")], color=("park_name", "`park_name`"), stacked=True)
    p.chart("bar", "hour_profile", "¿A qué hora nos limitan? (MWh por hora local)",
            ("hora_local", "`hora_local`", "categorical"), [("MWh", "SUM(`curtailed_mwh`)")], width=3, newline=False)
    p.chart("line", "hour_profile", "Precio spot medio por hora (USD/MWh)", ("hora_local", "`hora_local`", "categorical"),
            [("USD/MWh", "AVG(`spot_usd_mwh`)")], width=3, x_pos=3)
    p.table("battery", "Caso de inversión: repago simple por parque y tamaño de batería",
            ["ranking", "park_name", "option_code", "battery_mwh", "recovered_mwh", "recovered_value_usd",
             "battery_capex_usd", "simple_payback_years"])
    return dashboard(ds, [p])


# =============================================================================
# 3 · Mantenimiento predictivo
# =============================================================================
def predictivo() -> dict:
    ds = {
        "risk_now": ("Turbinas en riesgo hoy", "SELECT * FROM gold.fn_turbinas_en_riesgo(NULL)"),
        "health": ("Salud diaria", """
SELECT reading_date, park_code, turbine_id, health_score, gearbox_residual_7d, vibration_ratio, risk_level,
       failure_within_30d
FROM gold.mart_turbine_health WHERE reading_date >= date_sub((SELECT max(reading_date) FROM gold.mart_turbine_health), 120)"""),
        "lead": ("Anticipación de las alertas", """
WITH f AS (SELECT DISTINCT turbine_id, next_major_failure_date FROM gold.mart_turbine_health
           WHERE next_major_failure_date IS NOT NULL)
SELECT f.turbine_id, f.next_major_failure_date,
       max(datediff(f.next_major_failure_date, h.reading_date)) AS dias_de_anticipacion
FROM f LEFT JOIN gold.mart_turbine_health h ON h.turbine_id = f.turbine_id AND h.risk_level = 'ALTO'
  AND h.reading_date BETWEEN date_sub(f.next_major_failure_date, 45) AND date_sub(f.next_major_failure_date, 1)
GROUP BY ALL"""),
        "orders": ("Órdenes correctivas mayores", """
SELECT date_format(created_date, 'yyyy-MM') AS year_month, component, count(*) AS ordenes,
       avg(downtime_hours) AS horas_parada, sum(total_cost_usd) AS costo_usd
FROM gold.fact_maintenance_order WHERE order_type = 'CORRECTIVA' AND severity = 'MAYOR' GROUP BY ALL"""),
    }
    p = Page("predictivo", "Mantenimiento predictivo")
    p.text("# Caso 2 · Mantenimiento predictivo\nTurbinas cuya multiplicadora o rodamientos calientan más que sus pares "
           "y vibran más que su historia. Dueño: Ramiro Llancaqueo (Jefe de Mantenimiento).")
    p.table("risk_now", "Turbinas en riesgo (último día)", ["park_code", "turbine_tag", "health_score", "risk_level",
                                                            "suspected_component", "gearbox_residual_7d",
                                                            "vibration_ratio"], height=6)
    p.chart("line", "health", "Health score (últimos 120 días)", ("reading_date", "`reading_date`", "temporal"),
            [("Health score", "MIN(`health_score`)")], color=("turbine_id", "`turbine_id`"))
    p.table("lead", "¿Con cuántos días de anticipación avisó el modelo? (null = falla sorpresa)",
            ["turbine_id", "next_major_failure_date", "dias_de_anticipacion"], height=6)
    p.chart("bar", "orders", "Costo de correctivas mayores (USD)", ("year_month", "`year_month`", "categorical"),
            [("USD", "SUM(`costo_usd`)")], color=("component", "`component`"), stacked=True)
    return dashboard(ds, [p])


# =============================================================================
# 4 · Limpieza de paneles en la Puna
# =============================================================================
def limpieza() -> dict:
    ds = {
        "daily": ("Suciedad diaria", """
SELECT reading_date, park_code, soiling_loss_pct, soiling_sensor_pct, lost_usd_since_cleaning, cleaning_cost_usd,
       soiling_lost_usd, soiling_lost_mwh, recommendation
FROM gold.mart_panel_cleaning"""),
        "now": ("Recomendación de hoy", "SELECT * FROM gold.fn_recomendacion_limpieza(NULL)"),
        "water": ("Agua por limpieza", """
SELECT park_code, date_format(created_date, 'yyyy') AS anio, count(*) AS limpiezas, sum(water_m3) AS agua_m3,
       sum(total_cost_usd) AS costo_usd
FROM gold.fact_maintenance_order WHERE order_type = 'LIMPIEZA' GROUP BY ALL"""),
    }
    p = Page("limpieza", "Limpieza de paneles")
    p.text("# Caso 3 · Limpieza de paneles en la Puna\nEl polvo baja la generación; el agua es escasa y cara. "
           "Regla: limpiar cuando lo perdido desde la última limpieza supera su costo y no se pronostica lluvia.")
    p.table("now", "Recomendación del último día", ["park_name", "soiling_loss_pct", "days_since_cleaning",
                                                    "lost_usd_since_cleaning", "cleaning_cost_usd",
                                                    "rain_forecast_tomorrow_mm", "recommendation"], height=5)
    p.chart("line", "daily", "Suciedad estimada (%)", ("reading_date", "`reading_date`", "temporal"),
            [("Suciedad", "AVG(`soiling_loss_pct`)")], color=("park_code", "`park_code`"))
    p.chart("line", "daily", "USD perdidos desde la última limpieza vs costo de limpiar",
            ("reading_date", "`reading_date`", "temporal"),
            [("Perdido USD", "SUM(`lost_usd_since_cleaning`)"), ("Costo limpieza USD", "SUM(`cleaning_cost_usd`)")])
    p.chart("bar", "water", "Agua usada por año (m3)", ("anio", "`anio`", "categorical"), [("m3", "SUM(`agua_m3`)")],
            color=("park_code", "`park_code`"), stacked=True)
    return dashboard(ds, [p])


# =============================================================================
# 5 · Cumplimiento de PPA
# =============================================================================
def ppa() -> dict:
    ds = {
        "settlement": ("Liquidación mensual", """
SELECT client_name, contract_id, month_start, year_month, committed_mwh, delivered_mwh, compliance_pct, shortfall_mwh,
       penalty_cost_usd, spot_cover_cost_usd, best_option, best_option_cost_usd
FROM gold.fact_ppa_settlement"""),
        "forecast": ("Proyección del mes", "SELECT * FROM gold.fn_proyeccion_ppa(NULL)"),
    }
    p = Page("ppa", "Cumplimiento PPA")
    p.text("# Caso 4 · Cumplimiento de PPA\n¿Llegamos al volumen comprometido este mes? Si no, ¿comprar en el spot o "
           "pagar la penalidad? Dueña: Sofía Bertolini (Gerente Comercial).")
    p.table("forecast", "Proyección del mes en curso", ["client_name", "committed_mwh", "delivered_mtd_mwh",
                                                       "projected_mwh", "projected_compliance_pct",
                                                       "projected_shortfall_mwh", "spot_cover_cost_usd",
                                                       "penalty_cost_usd", "recommendation"], height=6)
    p.chart("line", "settlement", "Cumplimiento mensual por cliente", ("month_start", "`month_start`", "temporal"),
            [("Cumplimiento", "AVG(`compliance_pct`)")], color=("client_name", "`client_name`"))
    p.chart("bar", "settlement", "Costo de faltantes (mejor opción, USD)", ("year_month", "`year_month`", "categorical"),
            [("USD", "SUM(`best_option_cost_usd`)")], color=("client_name", "`client_name`"), stacked=True)
    return dashboard(ds, [p])


# =============================================================================
# 6 · Disponibilidad vs. garantía
# =============================================================================
def garantia() -> dict:
    ds = {
        "monthly": ("Disponibilidad mensual", """
SELECT park_name, manufacturer, month_start, year_month, availability_month, availability_12m, guaranteed_availability,
       ld_accrued_usd, claim_eligible, chargeable_fault_h, force_majeure_h
FROM gold.mart_warranty_claims"""),
        "claims": ("Reclamos", "SELECT * FROM gold.fn_reclamos_garantia(NULL)"),
    }
    p = Page("garantia", "Garantía del fabricante")
    p.text("# Caso 5 · Disponibilidad contractual vs. garantía (97 %)\nCuándo reclamar al fabricante y cuánto. "
           "Dueño: Ramiro Llancaqueo (Mantenimiento) con Legal.")
    p.counters("monthly", [("LD devengados (USD)", "SUM(`ld_accrued_usd`)", None),
                           ("Meses con reclamo", "COUNT_IF(`claim_eligible`)", None)])
    p.chart("line", "monthly", "Disponibilidad móvil 12 m por fabricante", ("month_start", "`month_start`", "temporal"),
            [("Disponibilidad 12 m", "AVG(`availability_12m`)")], color=("manufacturer", "`manufacturer`"))
    p.table("claims", "Meses reclamables", ["park_name", "manufacturer", "year_month", "availability_12m",
                                            "shortfall_points", "ld_accrued_usd"])
    return dashboard(ds, [p])


DASHBOARDS = {
    "01_direccion_generacion": direccion,
    "02_curtailment_baterias": curtailment,
    "03_mantenimiento_predictivo": predictivo,
    "04_limpieza_paneles": limpieza,
    "05_cumplimiento_ppa": ppa,
    "06_garantia_disponibilidad": garantia,
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, fn in DASHBOARDS.items():
        (OUT / f"{name}.lvdash.json").write_text(json.dumps(fn(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(DASHBOARDS)} dashboards en {OUT}")


if __name__ == "__main__":
    main()
