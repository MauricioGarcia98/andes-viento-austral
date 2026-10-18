-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 06 · Fechas, husos horarios, tipos y nulos (donde se rompen los datos reales)
-- MAGIC Convención del proyecto: `*_ts`/`ts_utc` en **UTC**, `*_local` en hora argentina (UTC-3), `reading_date` = día local.

-- COMMAND ----------

USE CATALOG andes_viento_dev;

-- COMMAND ----------

-- Los 3 formatos de fecha del SCADA, crudos en bronze
SELECT site, fw, ts, ts_epoch_ms, received_at FROM bronze.scada_turbine
WHERE ingest_date = '2025-07-15' AND site IN ('RAW', 'LEO', 'GAR') LIMIT 9;

-- COMMAND ----------

-- Parsear cada uno (try_to_timestamp devuelve NULL en vez de fallar: Spark 4 tiene ANSI activo)
SELECT ts, ts_epoch_ms,
       coalesce(timestamp_millis(ts_epoch_ms),
                try_to_timestamp(ts, "yyyy-MM-dd'T'HH:mm:ssXXX"),
                to_utc_timestamp(try_to_timestamp(ts, 'dd/MM/yyyy HH:mm:ss'), 'America/Argentina/Buenos_Aires')) AS utc
FROM bronze.scada_turbine WHERE ingest_date = '2025-07-15' LIMIT 10;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Ejercicios
-- MAGIC 1. Encontrá en `silver.scada_10min` las lecturas con `tz_corrected` de Pampa del Castillo: ¿desde qué fecha aparecen? ¿cuánto vale `clock_offset_s`?
-- MAGIC 2. ¿Qué turbinas tuvieron el reloj desfasado (`clock_corrected`) y en qué rango de fechas?
-- MAGIC 3. Convertí `'45.231,50'` (formato CAMMESA) a número sin usar UDFs.
-- MAGIC 4. ¿Por qué `CAST('abc' AS INT)` falla y `try_cast('abc' AS INT)` no? ¿Qué conviene en silver?
-- MAGIC 5. La "HORA 24" de CAMMESA: armá el timestamp UTC de `FECHA='15/07/2025', HORA=24`.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Soluciones

-- COMMAND ----------

SELECT min(reading_date) AS desde, max(reading_date) AS hasta, min(clock_offset_s), max(clock_offset_s), count(*)
FROM silver.scada_10min WHERE park_code = 'PAM' AND tz_corrected;

-- COMMAND ----------

SELECT asset_id, min(reading_date) AS desde, max(reading_date) AS hasta, max(abs(clock_offset_s)) AS seg
FROM silver.scada_10min WHERE clock_corrected GROUP BY asset_id ORDER BY desde;

-- COMMAND ----------

SELECT try_cast(regexp_replace(regexp_replace('45.231,50', '\\.', ''), ',', '.') AS DOUBLE) AS precio;

-- COMMAND ----------

-- 4) Con ANSI activo, CAST inválido es un error (bueno para detectar bugs). En silver se usa try_cast
--    + una regla de calidad que cuenta los NULL: así un dato malo no frena todo el pipeline.
SELECT try_cast('abc' AS INT) AS valor;

-- COMMAND ----------

SELECT to_utc_timestamp(to_timestamp('15/07/2025', 'dd/MM/yyyy') + make_interval(0, 0, 0, 0, 24 - 1, 0, 0),
                        'America/Argentina/Buenos_Aires') AS hora_ts_utc;
