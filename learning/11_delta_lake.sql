-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 11 · Delta Lake a fondo: historia, time travel, MERGE, CDF, OPTIMIZE, VACUUM

-- COMMAND ----------

USE CATALOG andes_viento_dev;

-- COMMAND ----------

-- Cada escritura es una versión: el log de transacciones (_delta_log) guarda todo
DESCRIBE HISTORY silver.assets_history;

-- COMMAND ----------

-- Time travel: ¿cómo estaba el registro de activos antes de la última carga?
SELECT count(*) FROM silver.assets_history VERSION AS OF 1;

-- COMMAND ----------

-- Change Data Feed (habilitado en todas las tablas del proyecto)
SELECT _change_type, count(*) FROM table_changes('silver.assets_history', 1) GROUP BY 1;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Ejercicios
-- MAGIC 1. ¿Qué operación (`operation`) usó cada versión de `silver.work_orders`? ¿Por qué hay MERGE con DELETE?
-- MAGIC 2. Restaurá una copia de `gold.dim_park` a una versión anterior (`RESTORE`) — en una copia, no en la original.
-- MAGIC 3. Con CDF, listá las turbinas cuya versión vigente cambió en la última corrida.
-- MAGIC 4. `OPTIMIZE` + `DESCRIBE DETAIL`: ¿cuántos archivos había antes y después en `silver.scada_10min`?
-- MAGIC 5. ¿Qué pasa con el time travel después de un `VACUUM ... RETAIN 0 HOURS`? (no lo hagas en prod)

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Soluciones

-- COMMAND ----------

SELECT version, operation, operationMetrics.numTargetRowsDeleted, operationMetrics.numTargetRowsUpdated
FROM (DESCRIBE HISTORY silver.work_orders) ORDER BY version;
-- Las órdenes creadas por error llegan con op = 'D': merge_cdc las BORRA del destino.

-- COMMAND ----------

CREATE OR REPLACE TABLE gold.tmp_dim_park DEEP CLONE gold.dim_park;
UPDATE gold.tmp_dim_park SET park_manager = 'Nadie' WHERE park_code = 'LEO';
RESTORE TABLE gold.tmp_dim_park TO VERSION AS OF 0;
SELECT park_manager FROM gold.tmp_dim_park WHERE park_code = 'LEO';
DROP TABLE gold.tmp_dim_park;

-- COMMAND ----------

SELECT asset_id, asset_tag, _change_type, _commit_version
FROM table_changes('silver.assets_history', (SELECT max(version) - 1 FROM (DESCRIBE HISTORY silver.assets_history)))
WHERE _change_type IN ('insert', 'update_postimage');

-- COMMAND ----------

DESCRIBE DETAIL silver.scada_10min;
OPTIMIZE silver.scada_10min;
DESCRIBE DETAIL silver.scada_10min;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC 5) VACUUM borra los archivos que ya no referencia la versión actual: las versiones viejas dejan de poder leerse.
-- MAGIC Por eso la retención mínima por defecto es de 7 días (y el job de mantenimiento usa 168 horas).
