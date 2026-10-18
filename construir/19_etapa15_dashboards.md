# 19 · Etapa 15 · Dashboards como código

## 🎯 Objetivo

Un **dashboard AI/BI por caso de negocio** (6 en total), generados por un script de Python y desplegados con el
bundle. El dashboard es para el **seguimiento** (el directorio lo mira una vez por mes); Genie, para la **pregunta del
momento**.

**Archivos:** `scripts/build_dashboards.py`, `dashboards/*.lvdash.json` (generados), `resources/andes_dashboards.yml`.

## 📚 Conceptos

- **Dashboard AI/BI (ex Lakeview):** un tablero de Databricks definido en un JSON (`.lvdash.json`) con **datasets**
  (consultas SQL) y **páginas** con **widgets** (contadores, gráficos, tablas) ubicados en una grilla de 6 columnas.
- **Dataset:** una consulta SQL con nombre. Varios widgets pueden usar el mismo dataset con distintas agregaciones.
- **`dataset_catalog`:** el bundle reemplaza el catálogo de las consultas según el target. Las consultas dicen
  `gold.mart_x`, sin catálogo; en dev apuntan a `andes_viento_dev.gold.mart_x` y en prod a `andes_viento.gold.mart_x`.

## 🧱 Paso a paso

### 1. Por qué generarlos con un script

Un `.lvdash.json` escrito a mano tiene **cientos de líneas repetidas** (cada widget repite su consulta, sus
codificaciones, su posición). Exportarlo desde la interfaz funciona, pero los IDs y las posiciones cambian en cada
edición y el PR se vuelve ilegible. Con un script, cada dashboard es una lista corta de datasets y widgets.

### 2. El mini "lenguaje" de `build_dashboards.py`

```python
class Page:
    def text(self, md, height=2): ...                       # un texto en Markdown
    def counters(self, dataset, items, height=3): ...       # una fila de contadores (KPI)
    def chart(self, kind, dataset, title, x, ys, color=None, width=6, height=6, x_pos=0, newline=True, stacked=False): ...
    def table(self, dataset, title, columns, height=7): ...

def dashboard(datasets, pages) -> dict:
    return {"datasets": [...], "pages": [p.to_json() for p in pages]}
```
`Page` lleva la cuenta de la posición vertical (`self.y`): cada widget se ubica debajo del anterior, o al lado si se
pasa `newline=False` y `x_pos`. Así nadie calcula coordenadas a mano.

**Un dashboard completo** (Dirección, resumido):
```python
def direccion() -> dict:
    ds = {
        "monthly": ("Real vs presupuesto mensual", """
SELECT park_name, technology, month_start, year_month, actual_mwh, budget_p50_mwh, variance_pct, ...
FROM gold.mart_generation_vs_budget"""),
        "last12": ("Últimos 12 meses", """
SELECT sum(actual_mwh) AS actual_mwh, sum(budget_p50_mwh) AS budget_mwh, ...
FROM gold.mart_generation_vs_budget
WHERE month_start > add_months((SELECT max(month_start) FROM gold.mart_generation_vs_budget), -12)"""),
        "losses_last": ("Pérdidas del último mes por parque", """... UNPIVOT (mwh FOR causa IN (curtailment, fallas, ...))"""),
    }
    p = Page("resumen", "Generación vs. presupuesto")
    p.text("# Andes Viento Austral · Dirección\n... Dueña: Lucía Ferreyra (CEO).")
    p.counters("last12", [("MWh generados (12 m)", "SUM(`actual_mwh`)", None),
                          ("Desvío vs presupuesto (12 m)", "SUM(`actual_mwh`) / SUM(`budget_mwh`) - 1", "number-percent"),
                          ("MWh perdidos por curtailment (12 m)", "SUM(`curtailment_mwh`)", None)])
    p.chart("line", "monthly", "Real vs presupuesto (todas las plantas)", ("month_start", "`month_start`", "temporal"),
            [("Real MWh", "SUM(`actual_mwh`)"), ("Presupuesto MWh", "SUM(`budget_p50_mwh`)")])
    p.chart("bar", "losses_last", "Pérdidas del último mes por causa", ("park_name", "`park_name`", "categorical"),
            [("MWh", "SUM(`mwh`)")], color=("causa", "`causa`"), stacked=True)
    return dashboard(ds, [p])
```
**La estructura que siguen los 6** (un patrón clásico de dashboards):
1. **Arriba, el contexto:** un texto con la pregunta del caso y su dueño.
2. **Contadores:** los 2-3 números que importan.
3. **Tendencia:** cómo evolucionan.
4. **Detalle accionable abajo:** una tabla con qué hacer (qué turbina revisar, qué parque limpiar, qué contrato mirar).

| dashboard | datasets principales |
|---|---|
| Dirección · Generación vs presupuesto | `mart_generation_vs_budget` |
| Caso 1 · Curtailment y baterías | `fact_curtailment_hourly`, `fn_ranking_baterias(12)` |
| Caso 2 · Mantenimiento predictivo | `fn_turbinas_en_riesgo`, `mart_turbine_health`, `fact_maintenance_order` |
| Caso 3 · Limpieza de paneles | `mart_panel_cleaning`, `fn_recomendacion_limpieza` |
| Caso 4 · Cumplimiento PPA | `fact_ppa_settlement`, `mart_ppa_forecast` |
| Caso 5 · Garantía del fabricante | `mart_warranty_claims`, `fn_reclamos_garantia` |

Los datasets usan las **mismas funciones certificadas** que Genie: el dashboard y Genie dan el mismo número.

`main()` escribe los 6 archivos en `dashboards/`. Se commitean (el bundle los sube tal cual).

### 3. `resources/andes_dashboards.yml`

```yaml
resources:
  dashboards:
    direccion_generacion:
      display_name: "Andes · Dirección · Generación vs presupuesto"
      file_path: ../dashboards/01_direccion_generacion.lvdash.json
      warehouse_id: ${var.warehouse_id}
      dataset_catalog: ${var.catalog}
    ...
```
`warehouse_id` sale del `lookup` del capítulo 15. Un dashboard necesita un SQL warehouse para correr sus consultas.

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| generar el JSON | exportarlo de la interfaz | IDs y posiciones cambian en cada edición: PRs ilegibles, difícil reusar el patrón |
| consultas sin catálogo + `dataset_catalog` | el catálogo escrito en cada consulta | habría un JSON por ambiente |
| usar las funciones certificadas | reescribir la lógica en el dashboard | dos definiciones del mismo número que tarde o temprano difieren |
| un dashboard por caso | uno con 20 páginas | cada caso tiene su dueño y su ritmo de revisión |

## ✅ Probalo

```bash
python scripts/build_dashboards.py
python -m json.tool dashboards/01_direccion_generacion.lvdash.json > /dev/null && echo json-ok
databricks bundle deploy -t dev
```
**Dashboards → Andes · Dirección · Generación vs presupuesto**: los contadores muestran números y los gráficos tienen
datos. Si un widget dice *error*, abrí el dataset (pestaña **Data**) y corré la consulta: el error de SQL aparece ahí.

Para verificarlos todos sin abrir la interfaz: cada consulta de los datasets se puede correr en el SQL Editor
reemplazando `gold.` por `andes_viento_dev.gold.`. En el proyecto original los 17 datasets corrieron bien (`risk_now`
da 0 filas porque no hay turbinas en riesgo alto el último día, que es válido).

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| el dashboard "no tiene datos" | el job no terminó o el catálogo es otro | revisá `dataset_catalog` y que el job esté verde |
| `TABLE_OR_VIEW_NOT_FOUND gold.x` | el mart o la función todavía no existe | etapas 9 y 14 antes que ésta |
| `warehouse not found` | el warehouse tiene otro nombre | el `lookup` de `databricks.yml` |
| el JSON no carga | error de formato | `python -m json.tool archivo` (el CI lo verifica, capítulo 22) |
| cambiaste el dashboard en la interfaz y el deploy lo pisó | el bundle es la fuente de verdad | editá el script, no la interfaz (o exportá y pasá el cambio al script) |

## 📍 Punto de control

```bash
git commit -am "etapa-15: dashboards como código" && git diff etapa-15 HEAD --stat
```

## 🏋️ Ejercicio

1. Agregá a Dirección un contador con el factor de capacidad de los últimos 12 meses (pista: `mv_generacion` o
   `v_park_daily` con `installed_mw`).
2. Hacé un dashboard nuevo para HSE: agua usada en limpiezas por parque y mes (`fact_maintenance_order` con
   `order_type = 'LIMPIEZA'`). Registralo en el YAML de recursos y desplegalo.
3. Publicá un dashboard (**Publish**) y compartilo con otro usuario. ¿Qué ve si no tiene permisos sobre `gold`?
