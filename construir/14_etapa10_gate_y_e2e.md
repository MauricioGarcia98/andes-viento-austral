# 14 · Etapa 10 · Quality gate y el pipeline completo en local

## 🎯 Objetivo

Unir todas las piezas en **un pipeline de punta a punta** que corre en tu computadora (generar → bronze → silver →
gold → marts) y ponerle al final un **quality gate**: 10 controles que, si alguno falla, frenan todo antes de que un
número roto llegue a Genie. Y el test de integración que lo corre entero, incluido un día incremental.

Es la etapa más importante antes de ir a la nube: cuando esto pasa, el código está bien. Lo que falle en Databricks
va a ser de la plataforma, no de la lógica.

**Archivos:** `src/andes_viento/quality/gate.py`, `src/andes_viento/pipeline.py`, `tests/test_e2e.py`,
`scripts/run_local.py`.

## 📚 Conceptos

- **Invariante:** algo que **siempre** tiene que ser cierto, pase lo que pase con los datos. "Una turbina tiene una
  sola versión vigente." "La cascada cierra." Si una invariante se rompe, hay un bug.
- **Quality gate:** un control al final del pipeline que bloquea la publicación. Es preferible un job en rojo a un
  dashboard con un número equivocado.
- **Test de integración:** prueba el sistema entero, con datos reales (generados), en vez de una función aislada.

## 🧱 Paso a paso

### 1. `quality/gate.py`

```python
def checks(cfg) -> dict[str, str]:
    g = lambda t: cfg.table("gold", t)
    s = lambda t: cfg.table("silver", t)
    return {
        "fact_turbine_10min tiene el mismo grano que silver.scada_10min":
            f"SELECT abs((SELECT COUNT(*) FROM {g('fact_turbine_10min')}) - (SELECT COUNT(*) FROM {s('scada_10min')}))",
        "sin duplicados turbina x slot en silver": ...,
        "toda medición tiene turbina (FK a dim_turbine)":
            f"SELECT COUNT(*) FROM {g('fact_turbine_10min')} WHERE turbine_key = -1",
        "una sola versión vigente por turbina": ...,
        "las versiones SCD2 de turbina no se solapan": ...,
        "generado nunca supera la potencia nominal (10 min)": ...,
        "disponibilidad contractual entre 0 y 1": ...,
        "liquidación PPA: entregado nunca supera lo comprometido": ...,
        "la cascada presupuesto -> real cierra (residuo < 0,1 MWh)": ...,
        "órdenes de trabajo sin duplicar": ...,
    }

def run_quality_gate(spark, cfg, max_quarantine_ratio=0.01):
    results = [(name, int(spark.sql(q).collect()[0][0] or 0)) for name, q in checks(cfg).items()]
    failed = [f"{n} ({v})" for n, v in results if v != 0]
    ratio = spark.sql(f"SELECT SUM(failed_rows) / SUM(total_rows) FROM {cfg.table('ops', 'dq_results')} "
                      "WHERE action = 'quarantine'").collect()[0][0] or 0
    ...
    if failed:
        raise QualityGateError("; ".join(failed))
```
- **Cada control es una consulta que tiene que dar 0.** El nombre del control es la explicación (aparece en el error).
- El gate también mira la **cuarentena**: si más del 1 % de las filas fue apartado, algo llegó roto en masa (una fuente
  que cambió de formato) aunque cada fila haya sido "bien" tratada.
- Por qué estos 10: cada uno atrapa un error que **ya pasó o que es fácil que pase** (la tabla de cada control y su
  error real está en [docs/18 · Pruebas](../docs/18_pruebas.md#5-quality-gate-el-último-control-antes-de-publicar)).

### 2. `pipeline.py`: todo en un proceso

```python
def run_e2e(spark, cfg, generate=True, gen_start=None, gen_end=None, gen_mode="full", gate=True):
    timings = {}
    def step(name, target, fn):
        t0 = time.time()
        with audited(cfg, spark, name, target) as res:
            res["rows_written"] = None
            fn()
        timings[name] = round(time.time() - t0, 1)

    create_namespace(spark, cfg)
    if generate:
        step("generate", "landing", lambda: generate_all(spark, cfg, gen_start, gen_end, gen_mode))
    step("bronze", "bronze.*", lambda: ingest_all(spark, cfg))
    step("silver", "silver.*", lambda: load_all(spark, cfg))
    step("gold_dims", "gold.dim_*", lambda: load_dimensions(spark, cfg))
    step("gold_facts", "gold.fact_*", lambda: load_facts(spark, cfg))
    step("gold_marts", "gold.mart_*", lambda: build_marts(spark, cfg))
    if gate:
        step("quality_gate", "ops.dq_results", lambda: run_quality_gate(spark, cfg))
    return timings
```
Es **lo mismo que va a hacer el job de Databricks** (capítulo 15), pero en un solo proceso y en serie. En Databricks
cada `step` es una tarea separada para poder correr en paralelo, reintentar y reparar por separado. Tener las dos
versiones permite probar la lógica en local y la orquestación en la nube.

### 3. `tests/test_e2e.py`

```python
pytestmark = pytest.mark.integration

def test_full_pipeline_and_incremental(spark, cfg):
    cfg = replace(cfg, scale_factor=0.03, start_date=date(2025, 6, 25), end_date=date(2025, 7, 31))
    run_e2e(spark, cfg)                                       # incluye el gate: si una invariante falla, el test falla
    leo = spark.sql(f"SELECT * FROM {g('mart_generation_vs_budget')} WHERE park_code = 'LEO' AND year_month = '2025-07'").first()
    assert leo.variance_pct < -0.15                           # la historia guionada aparece
    assert leo.lost_curtailment_mwh > 0 and leo.lost_icing_mwh > 0 and leo.lost_fault_mwh > 0
    htw = spark.table(g("dim_turbine")).where("is_current AND manufacturer_code = 'HTW'")
    assert htw.count() > 0 and htw.where("firmware <> 'HT-OS 5.0'").count() == 0
    before = spark.table(g("fact_turbine_10min")).count()
    nxt = replace(cfg, end_date=date(2025, 8, 1))
    run_e2e(spark, nxt, gen_start=date(2025, 8, 1), gen_end=date(2025, 8, 1), gen_mode="incremental")
    assert spark.table(g("fact_turbine_10min")).count() > before
```
- **5 semanas** (del 25-06 al 31-07-2025) con SF 0,03: alcanza para que aparezca julio 2025 entero y corre en minutos.
- Verifica **el negocio**, no sólo que "corrió": Cañadón León tiene que caer más de 15 % con curtailment, hielo y falla.
- Verifica **el incremental**: un día nuevo agrega filas y el gate sigue verde.

### 4. `scripts/run_local.py`

Lo mismo que el test, pero para correr a mano y mirar los resultados: imprime los tiempos de cada paso y la cantidad
de filas de cada tabla esperada (`EXPECTED_TABLES` del capítulo 05).

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| gate al final que **falla** | un reporte de calidad que alguien mira | nadie mira un reporte a las 6 de la mañana; un job rojo sí se ve |
| controles que dan 0 | controles con umbrales | una invariante no tiene "un poco": o se cumple o hay un bug |
| test de integración con la historia | sólo contar filas | un pipeline que corre pero da números sin sentido también "corre" |
| `pipeline.py` además del job | sólo el job | sin la versión local, cada prueba costaría una corrida de 45 minutos |

## ✅ Probalo

```bash
pytest -m integration                  # 1 passed (~5-10 min)
pytest                                 # 28 passed: todo el proyecto en local
python scripts/run_local.py            # tiempos y filas por tabla
```
`run_local.py` termina con una tabla de ~40 líneas (`bronze scada_turbine ...`, `gold fact_turbine_10min ...`). Si el
gate falla, el error dice **qué** control y cuántas filas lo rompen.

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| `QualityGateError: toda medición tiene turbina (FK a dim_turbine) (540)` | lecturas anteriores a la primera versión SCD2 | primera versión desde 1900 (capítulo 12, L6) |
| `...disponibilidad contractual entre 0 y 1 (1)` | redondeos | `_clamp01` (R7) |
| `...la cascada ... cierra (N)` | falta un término en el mart 02 | revisá la identidad |
| `variance_pct < -0.15` falla | la historia no está (o la flota está demasiado sana) | revisá `STORY` y la calibración (L7, R10) |
| `firmware <> 'HT-OS 5.0'` falla | la foto inicial del CMMS no plegó los cambios previos | el plegado de `cmms_assets` (L8) |
| el incremental no agrega filas | Auto Loader no vio el archivo nuevo o el watermark no avanzó | `partitionOverwriteMode = dynamic` en el writer; `set_watermark` |
| tarda más de 20 minutos | SF o fechas más grandes | SF 0,03 y 5 semanas |

## 📍 Punto de control

```bash
git commit -am "etapa-10: quality gate y pipeline completo en local" && git diff etapa-10 HEAD --stat
```
**Hito:** todo el código de datos está terminado y probado en local. A partir de acá es plataforma: llevarlo a
Databricks, orquestarlo, gobernarlo y ponerle Genie encima.

## 🏋️ Ejercicio

1. Agregá un control al gate: "no hay lecturas con `ts_utc` en el futuro respecto del último día de datos". Rompelo a
   propósito (sumale un día a una lectura con un UPDATE) y verificá que el gate falla con tu mensaje.
2. Corré `run_local.py --increment 2025-08-01` dos veces seguidas. ¿Cambia la cantidad de filas la segunda vez? ¿Por qué?
3. Medí qué paso tarda más en local. ¿Coincide con lo que tarda más en Databricks (capítulo 15)?
