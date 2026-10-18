-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 01 · SQL básico: SELECT, WHERE, ORDER BY, LIMIT
-- MAGIC Tablas: `gold.dim_park` (13 parques) y `gold.v_park_daily` (un día por parque).

-- COMMAND ----------

USE CATALOG andes_viento_dev;
USE SCHEMA gold;

-- COMMAND ----------

-- Todo de una tabla chica
SELECT * FROM dim_park;

-- COMMAND ----------

-- Columnas elegidas, filtro y orden
SELECT park_name, province, installed_mw, distance_to_base_km
FROM dim_park
WHERE technology = 'Eólico'
ORDER BY distance_to_base_km DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **Ojo con los NULL:** `turbine_manufacturer` es NULL en los parques solares. `WHERE x <> 'algo'` NO trae los NULL.

-- COMMAND ----------

SELECT park_name, turbine_manufacturer FROM dim_park WHERE turbine_manufacturer IS NULL;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Ejercicios
-- MAGIC 1. Parques de Santa Cruz con su potencia instalada, de mayor a menor.
-- MAGIC 2. Los 5 días de mayor generación de Cañadón León (`v_park_daily`).
-- MAGIC 3. Días de 2025 en que Susques Solar tuvo pérdida por suciedad mayor a 5 MWh.
-- MAGIC 4. Parques con enlace satelital (VSAT) y su jefe/a de parque.
-- MAGIC 5. ¿Qué devuelve `WHERE turbine_manufacturer <> 'Hanse Turbinen Werke'`? ¿Aparecen los solares? ¿Por qué?

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Soluciones

-- COMMAND ----------

SELECT park_name, installed_mw FROM dim_park WHERE province = 'Santa Cruz' ORDER BY installed_mw DESC;

-- COMMAND ----------

SELECT reading_date, generated_mwh FROM v_park_daily WHERE park_code = 'LEO' ORDER BY generated_mwh DESC LIMIT 5;

-- COMMAND ----------

SELECT reading_date, lost_soiling_mwh FROM v_park_daily
WHERE park_code = 'SUS' AND year(reading_date) = 2025 AND lost_soiling_mwh > 5 ORDER BY reading_date;

-- COMMAND ----------

SELECT park_name, park_manager FROM dim_park WHERE comm_link = 'VSAT';

-- COMMAND ----------

-- 5) Los solares NO aparecen: NULL <> 'x' es NULL (desconocido), no TRUE. Para incluirlos:
SELECT park_name FROM dim_park WHERE turbine_manufacturer IS DISTINCT FROM 'Hanse Turbinen Werke';
