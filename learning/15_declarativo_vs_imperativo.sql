-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 15 · Lakeflow Declarative Pipelines vs. Job imperativo
-- MAGIC El pipeline `andes-viento-ldp` (archivos `pipelines/*.sql`) hace SCADA + CAMMESA + activos + presupuesto
-- MAGIC en estilo declarativo. Corrélo desde **Jobs & Pipelines → andes-viento-ldp → Start** (después del job e2e).
-- MAGIC
-- MAGIC | lo que escribís | qué hace el motor |
-- MAGIC |---|---|
-- MAGIC | `CREATE OR REFRESH STREAMING TABLE ... FROM STREAM read_files(...)` | checkpoint, evolución de esquema, reintentos |
-- MAGIC | `CONSTRAINT x EXPECT (cond) ON VIOLATION DROP ROW` | métricas de calidad en el event log |
-- MAGIC | `CREATE FLOW ... AS AUTO CDC INTO ... STORED AS SCD TYPE 2` | SCD2 con `__START_AT` / `__END_AT` |
-- MAGIC | `CREATE OR REFRESH MATERIALIZED VIEW` | recálculo incremental cuando puede |

-- COMMAND ----------

USE CATALOG andes_viento_dev;

-- COMMAND ----------

-- Resultado del declarativo vs. el imperativo para el mismo mes
SELECT d.park_code, d.month_start, d.generated_mwh AS declarativo_mwh, m.scada_mwh AS imperativo_mwh,
       round(d.generated_mwh / m.scada_mwh - 1, 4) AS diferencia
FROM ldp.generation_vs_budget_monthly d
JOIN gold.mart_generation_vs_budget m ON m.park_code = d.park_code AND m.month_start = d.month_start
WHERE d.month_start = '2025-07-01' ORDER BY d.park_code;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Ejercicios
-- MAGIC 1. Explicá la diferencia de la consulta anterior. Pista: el declarativo NO corrige relojes desfasados ni turbinas renombradas.
-- MAGIC 2. Mirá el SCD2 declarativo (`ldp.assets_scd2`) y comparalo con `silver.assets_history` para una turbina de CRV.
-- MAGIC 3. Consultá el *event log* del pipeline: ¿cuántas filas descartó cada expectation?
-- MAGIC 4. Agregá una expectation `ON VIOLATION FAIL UPDATE` a `scada_clean` que nunca se cumpla y mirá qué pasa (en dev).

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Soluciones
-- MAGIC 1. Diferencias chicas: los slots con reloj corrido caen en otro slot (posibles "duplicados" que la MV deduplica distinto) y
-- MAGIC    las lecturas de Pampa del Castillo con huso cambiado quedan 3 h corridas (y algunas en otro día).

-- COMMAND ----------

SELECT asset_id, asset_tag, firmware, __START_AT, __END_AT FROM ldp.assets_scd2 WHERE park_code = 'CRV' ORDER BY asset_id, __START_AT LIMIT 10;

-- COMMAND ----------

SELECT timestamp, details:flow_progress:data_quality:expectations AS expectations
FROM event_log(TABLE(ldp.scada_clean))
WHERE event_type = 'flow_progress' AND details:flow_progress:data_quality IS NOT NULL
ORDER BY timestamp DESC LIMIT 5;
