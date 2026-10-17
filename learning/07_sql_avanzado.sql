-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 07 · SQL avanzado: structs, arrays, higher-order functions, PIVOT/UNPIVOT, MERGE

-- COMMAND ----------

USE CATALOG andes_viento_dev;

-- COMMAND ----------

-- Structs anidados (sensores) y arrays (alarmas) del SCADA crudo
SELECT site, sensors.wind_ms, sensors.oil_particle_count, alarms, size(alarms) AS n_alarmas,
       filter(alarms, a -> a LIKE '%-WRN') AS warnings, exists(alarms, a -> a = 'GRID-07') AS limitada
FROM bronze.scada_turbine WHERE ingest_date = '2025-07-20' AND site = 'LEO' AND size(alarms) > 0 LIMIT 10;

-- COMMAND ----------

-- UNPIVOT: de columnas de pérdidas a filas (ideal para gráficos apilados)
SELECT park_name, causa, mwh FROM (
  SELECT park_name, lost_curtailment_mwh AS curtailment, lost_fault_mwh AS fallas, lost_icing_mwh AS hielo
  FROM gold.mart_generation_vs_budget WHERE year_month = '2025-07' AND technology = 'Eólico'
) UNPIVOT (mwh FOR causa IN (curtailment, fallas, hielo));

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Ejercicios
-- MAGIC 1. PIVOT: MWh generados por parque (filas) y año (columnas).
-- MAGIC 2. Explotá los repuestos de las órdenes de bronze (`parts` es un array de structs) y sumá el costo por `part_code`.
-- MAGIC 3. Con `transform`, convertí el array de alarmas a minúsculas; con `aggregate`, contá cuántas empiezan con `HTW`.
-- MAGIC 4. Escribí un MERGE que actualice una tabla temporal de precios sólo si el precio nuevo es DEFINITIVO.
-- MAGIC 5. `QUALIFY` + `row_number()`: la última versión de cada instrucción de CAMMESA en bronze.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Soluciones

-- COMMAND ----------

SELECT * FROM (SELECT park_code, year(reading_date) AS anio, generated_mwh FROM gold.v_park_daily)
PIVOT (round(sum(generated_mwh), 0) FOR anio IN (2023, 2024, 2025, 2026));

-- COMMAND ----------

SELECT p.part_code, p.description, round(sum(p.qty * p.unit_cost_usd)) AS usd
FROM bronze.cmms_work_orders LATERAL VIEW explode(parts) x AS p
WHERE status = 'CERRADA' GROUP BY ALL ORDER BY usd DESC;

-- COMMAND ----------

SELECT alarms, transform(alarms, a -> lower(a)) AS minus,
       aggregate(alarms, 0, (acc, a) -> acc + CASE WHEN a LIKE 'HTW%' THEN 1 ELSE 0 END) AS htw
FROM bronze.scada_turbine WHERE ingest_date = '2025-07-27' AND size(alarms) > 0 LIMIT 5;

-- COMMAND ----------

CREATE OR REPLACE TEMP VIEW nuevos AS
SELECT 'PATAGONIA' AS node, TIMESTAMP'2025-07-15 03:00:00' AS hour_ts, 52000.0 AS price_ars_mwh, 2 AS version_rank;
CREATE OR REPLACE TABLE gold.tmp_precios AS SELECT node, hour_ts, price_ars_mwh, version_rank FROM silver.spot_prices
WHERE price_date = '2025-07-15';
MERGE INTO gold.tmp_precios t USING nuevos s ON t.node = s.node AND t.hour_ts = s.hour_ts
WHEN MATCHED AND s.version_rank >= t.version_rank THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
DROP TABLE gold.tmp_precios;

-- COMMAND ----------

SELECT instruction_id, version, status, valid_from, valid_to FROM bronze.cammesa_dispatch
QUALIFY row_number() OVER (PARTITION BY instruction_id ORDER BY version DESC) = 1 LIMIT 20;
