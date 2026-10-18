# 16 · Etapa 12 · Job diario, mantenimiento y pipeline declarativo (LDP)

## 🎯 Objetivo

Tres piezas de operación:
1. un **job diario** que simula la llegada de un día nuevo y procesa sólo eso, **reusando** el job principal;
2. un **job de mantenimiento** semanal que mantiene rápidas las tablas;
3. el **mismo problema resuelto de forma declarativa** con Lakeflow Declarative Pipelines (LDP), para comparar estilos.

**Archivos:** `resources/andes_daily.job.yml`, `andes_maintenance.job.yml`, `andes_ldp.pipeline.yml`,
`notebooks/10_maintenance.py`, `notebooks/11_generate_next_day.py`, `pipelines/01_bronze.sql`, `02_silver.sql`,
`03_gold.sql`.

## 📚 Conceptos

- **Schedule (Quartz cron):** `"0 15 6 * * ?"` = segundo 0, minuto 15, hora 6, todos los días. Con
  `timezone_id: America/Argentina/Buenos_Aires` es a las 06:15 hora argentina.
- **`run_job_task`:** una tarea que dispara **otro job** con los parámetros que le pases y espera a que termine.
- **Task values:** una tarea puede publicar un valor (`dbutils.jobs.taskValues.set`) y las siguientes lo leen con
  `{{tasks.<tarea>.values.<clave>}}`.
- **Imperativo vs. declarativo:**

| | imperativo (job + notebooks) | declarativo (LDP) |
|---|---|---|
| qué escribís | **cómo** hacerlo: leer, transformar, escribir, en orden | **qué** tablas querés y de dónde salen |
| quién maneja checkpoints, orden y reintentos | vos | el motor |
| calidad | tu framework (`enforce`) | `CONSTRAINT ... EXPECT` |
| SCD2 | ~100 líneas (`scd2.py`) | `AUTO CDC ... STORED AS SCD TYPE 2` (8 líneas) |
| tests locales | sí (pytest) | no (sólo en Databricks) |

- **`STREAMING TABLE` vs. `MATERIALIZED VIEW`:** una tabla de streaming procesa **sólo lo nuevo** (como Auto Loader);
  una vista materializada guarda el resultado de una consulta y el motor la refresca (incrementalmente si puede).

## 🧱 Paso a paso

### 1. El job diario

```yaml
resources:
  jobs:
    andes_daily:
      name: andes-viento-daily
      max_concurrent_runs: 1
      schedule:
        quartz_cron_expression: "0 15 6 * * ?"     # 06:15, después del cierre diario de CAMMESA
        timezone_id: America/Argentina/Buenos_Aires
        pause_status: PAUSED
      parameters: [catalog, scale_factor, start_date, end_date, run_date]
      tasks:
        - task_key: generate_next_day
          notebook_task: { notebook_path: ../notebooks/11_generate_next_day.py }
        - task_key: run_pipeline
          depends_on: [{ task_key: generate_next_day }]
          run_job_task:
            job_id: ${resources.jobs.andes_e2e.id}
            job_parameters:
              catalog: "{{job.parameters.catalog}}"
              ...
              end_date: "{{tasks.generate_next_day.values.run_date}}"
              generate: "false"
              full_refresh: "false"
```
`11_generate_next_day.py`:
```python
raw = dbutils.widgets.get("run_date")
if raw:
    run_date = date.fromisoformat(raw)
else:
    last = spark.sql(f"SELECT MAX(ingest_date) FROM {cfg.table('bronze', 'scada_turbine')}").collect()[0][0]
    run_date = (last or cfg.end_date) + timedelta(days=1)
generate_all(spark, replace(cfg, end_date=run_date), start=run_date, end=run_date, mode="incremental")
dbutils.jobs.taskValues.set("run_date", run_date.isoformat())
```
- **Qué día generar:** el siguiente al último que llegó a bronze (o el que le pases). Así, si un día no corrió, el
  siguiente sigue donde quedó.
- **Por qué reusa el e2e** (`run_job_task` con `generate=false`): un solo grafo para mantener. La condición del
  capítulo 15 saltea la generación completa, Auto Loader lee sólo los archivos nuevos y gold recalcula sólo los días
  afectados.
- `end_date` llega por *task value*: el e2e necesita saber hasta qué día hay datos (para el presupuesto, el calendario
  y el mes en curso).
- `${resources.jobs.andes_e2e.id}`: el bundle reemplaza esto por el ID real del job e2e en tu workspace.
- **Por qué pausado:** en dev siempre queda pausado (lo fuerza `mode: development`); en prod lo activás cuando quieras
  ([19 · Operación](../docs/19_operacion_diaria.md)).

Resultado real: el día nuevo se procesa en **~12 minutos** contra ~45 de la carga completa; casi todo es costo fijo.

### 2. El job de mantenimiento

Un job con una tarea (`10_maintenance.py`) los domingos a las 04:00:
```python
for layer in ("silver", "gold"):
    for t in spark.catalog.listTables(cfg.schema(layer)):
        if t.tableType == "VIEW" or t.name.startswith("v_") or t.name.startswith("mv_"):
            continue
        optimize(spark, full)                                          # compactar archivos chicos
        spark.sql(f"VACUUM {full} RETAIN 168 HOURS")                   # borrar archivos viejos (7 días)
        spark.sql(f"ANALYZE TABLE {full} COMPUTE STATISTICS FOR ALL COLUMNS")   # estadísticas para el optimizador
```
- Los MERGE incrementales dejan **muchos archivos chicos**. `OPTIMIZE` los junta.
- `VACUUM` borra archivos que ya no usa ninguna versión de la tabla. **168 horas (7 días)** es el mínimo seguro: Delta
  necesita conservar archivos para el *time travel* y para lecturas que estén en curso.
- `ANALYZE` actualiza las estadísticas que usa el optimizador para elegir cómo unir tablas.
- Las vistas se saltean (no tienen archivos).

### 3. El pipeline declarativo

`resources/andes_ldp.pipeline.yml`:
```yaml
resources:
  pipelines:
    andes_ldp:
      name: andes-viento-ldp
      catalog: ${resources.schemas.ldp.catalog_name}
      schema: ${resources.schemas.ldp.name}
      serverless: true
      continuous: false          # se corre a mano o desde un job, no todo el tiempo
      channel: CURRENT
      photon: true
      configuration:
        landing_path: /Volumes/${var.catalog}/landing/raw/landing
      libraries:
        - file: { path: ../pipelines/01_bronze.sql }
        - file: { path: ../pipelines/02_silver.sql }
        - file: { path: ../pipelines/03_gold.sql }
```
`configuration` define variables que los SQL usan como `${landing_path}`. Lee **los mismos archivos de landing** que
el job, y escribe en su propio esquema (`ldp`; en dev, con prefijo de usuario).

**`01_bronze.sql`, ingesta:**
```sql
CREATE OR REFRESH STREAMING TABLE scada_raw
COMMENT 'SCADA de aerogeneradores tal cual llega (JSON gz, 3 formatos de fecha según fabricante)'
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${landing_path}/scada_turbine', format => 'json', partitionColumns => 'ingest_date',
                       schemaHints => 'setpoint_kw DOUBLE, ts_epoch_ms BIGINT', schemaEvolutionMode => 'addNewColumns');
```
Es Auto Loader en una línea: `read_files` + `STREAM`. El motor maneja el checkpoint y, ante columnas nuevas,
**reinicia el flujo solo** (lo que en el capítulo 09 era un bucle en Python).

**`02_silver.sql`, calidad declarativa:**
```sql
CREATE OR REFRESH STREAMING TABLE scada_clean (
  CONSTRAINT turbina_informada   EXPECT (turbine IS NOT NULL)  ON VIOLATION DROP ROW,
  CONSTRAINT fecha_parseable     EXPECT (ts_utc IS NOT NULL)   ON VIOLATION DROP ROW,
  CONSTRAINT viento_posible      EXPECT (wind_ms IS NULL OR wind_ms BETWEEN 0 AND 60),
  CONSTRAINT temperatura_posible EXPECT (gearbox_bearing_c IS NULL OR gearbox_bearing_c < 200),
  CONSTRAINT potencia_en_rango   EXPECT (power_kw IS NULL OR power_kw <= 6000)
) AS ...
```
| sintaxis | equivale a |
|---|---|
| `EXPECT (...)` (sin acción) | `warn`: se cuenta en las métricas del pipeline |
| `ON VIOLATION DROP ROW` | `quarantine`, pero la fila **se descarta** (no queda guardada) |
| `ON VIOLATION FAIL UPDATE` | `fail` |

**SCD2 en 8 líneas:**
```sql
CREATE OR REFRESH STREAMING TABLE assets_scd2;
CREATE FLOW assets_scd2_flow AS AUTO CDC INTO assets_scd2
FROM STREAM(assets_clean)
KEYS (asset_id)
APPLY AS DELETE WHEN op = 'D'
SEQUENCE BY updated_at
COLUMNS * EXCEPT (op)
STORED AS SCD TYPE 2;
```
Hace lo mismo que `scd2.py` (capítulo 11): cadenas de versiones, reenvíos, tardíos y bajas, con columnas
`__START_AT` / `__END_AT`.

**`03_gold.sql`:** cuatro vistas materializadas: el SCADA deduplicado (`scada_dedup`), la generación diaria por parque, las instrucciones de curtailment por día y la generación vs. presupuesto por mes.

**Lo que el declarativo no hace fácil:** la corrección de relojes con el percentil por turbina y día de recepción
(capítulo 10) necesita agrupar y volver a unir; en streaming declarativo es complicado. El LDP redondea al bloque de
10 minutos y lo documenta. Por eso **el job imperativo es el principal** y el LDP es la comparación
([ADR-006](../docs/adr/ADR-006-imperativo-y-declarativo.md)).

## 🤔 Por qué así y no de otra forma

| decisión | alternativa | por qué no |
|---|---|---|
| el diario dispara el e2e | un job diario con sus propias tareas | dos grafos que se desincronizan |
| `VACUUM 168 HOURS` | menos | rompe el *time travel* y lecturas en curso; Delta lo bloquea por defecto |
| LDP como comparación | sólo LDP | no se puede testear en local; la corrección de relojes no entra |
| sólo job | sólo imperativo | LDP tiene ventajas reales (menos código, calidad y linaje integrados) que vale la pena conocer |

## ✅ Probalo

```bash
databricks bundle deploy -t dev
databricks bundle run andes_daily -t dev       # ~12 min: genera el día siguiente y procesa sólo eso
databricks bundle run andes_ldp -t dev         # ~3 min (después de que el e2e generó landing)
databricks bundle run andes_maintenance -t dev
```
- **Diario:** en la corrida del e2e que dispara, `generate_data` aparece **Excluded** y `bronze_ingest` corre igual.
  Después: `SELECT max(reading_date) FROM andes_viento_dev.gold.v_park_daily` → un día más.
- **LDP:** en **Jobs & Pipelines → andes-viento-ldp** ves el grafo de tablas y, en cada una, la pestaña **Data
  quality** con las expectations (en la corrida real: 633 potencias y 2.166 temperaturas fuera de rango).

## 🔥 Si falla

| ves esto | por qué | hacé esto |
|---|---|---|
| el diario genera un día que ya existía | `run_date` mal calculado | se toma de `max(ingest_date)` de bronze; pasale `run_date` a mano para reprocesar un día |
| el diario no procesa nada | `generate=false` y no hay archivos nuevos | revisá la carpeta `ingest_date=<día>` en el volumen |
| el LDP falla con *table already managed by another pipeline* | dos pipelines escriben el mismo esquema | un esquema por pipeline (`ldp`) |
| el LDP ocupa 27 tablas de la cuota | 13 tablas propias + 14 internas de materialización | si no lo usás, borrá su esquema ([19 · Cuota](../docs/19_operacion_diaria.md#la-cuota-de-500-tablas)) |
| `VACUUM` falla por retención | menos de 168 horas | dejá 168 |

## 📍 Punto de control

```bash
git commit -am "etapa-12: job diario, mantenimiento y LDP" && git diff etapa-12 HEAD --stat
```

## 🏋️ Ejercicio

1. Corré el diario dos veces seguidas con el mismo `run_date`. ¿Se duplica algo? ¿Por qué no?
2. Agregá al LDP una expectation `FAIL UPDATE` que sepas que va a fallar (por ejemplo `wind_ms < 10`). Corré el pipeline,
   mirá el error y sacala.
3. Escribí en LDP la tabla de órdenes de trabajo con `AUTO CDC ... STORED AS SCD TYPE 1` y comparala con
   `silver.work_orders` del job. ¿Coinciden?
