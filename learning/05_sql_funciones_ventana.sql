-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 05 · Funciones de ventana: el corazón del mantenimiento predictivo
-- MAGIC `OVER (PARTITION BY ... ORDER BY ... ROWS BETWEEN ...)` calcula sin colapsar filas.

-- COMMAND ----------

USE CATALOG andes_viento_dev;
USE SCHEMA gold;

-- COMMAND ----------

-- Residuo vs. pares: cuánto calienta una turbina más que el resto de su parque el mismo día
WITH d AS (
    SELECT turbine_id, park_code, reading_date, avg(gearbox_bearing_c) AS temp
    FROM fact_turbine_10min WHERE state = 'PRODUCIENDO' AND park_code = 'LEO'
      AND reading_date BETWEEN '2025-06-15' AND '2025-07-31'
    GROUP BY ALL)
SELECT *, temp - avg(temp) OVER (PARTITION BY park_code, reading_date) AS residuo,
       avg(temp - avg(temp) OVER (PARTITION BY park_code, reading_date)) OVER () AS no_se_puede
FROM d LIMIT 5;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC La última columna da error: **no se puede anidar ventanas**. Se resuelve con un CTE intermedio (ejercicio 2).

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Ejercicios
-- MAGIC 1. Ranking de parques por generación de cada mes de 2025 (`rank()`), sólo el top 3 por mes (`QUALIFY`).
-- MAGIC 2. Residuo térmico de multiplicadora de cada turbina de LEO y su promedio móvil de 7 días.
-- MAGIC 3. Generación acumulada en el mes (running total) de Rawson Sur en septiembre 2026.
-- MAGIC 4. Días desde la última limpieza en Susques usando `last_value(... IGNORE NULLS)`.
-- MAGIC 5. Variación mes contra mes (`lag`) de los MWh perdidos por curtailment de toda la empresa.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Soluciones

-- COMMAND ----------

SELECT year_month, park_name, actual_mwh, rank() OVER (PARTITION BY year_month ORDER BY actual_mwh DESC) AS pos
FROM mart_generation_vs_budget WHERE year = 2025
QUALIFY pos <= 3 ORDER BY year_month, pos;

-- COMMAND ----------

WITH d AS (
    SELECT turbine_id, park_code, reading_date, avg(gearbox_bearing_c) AS temp
    FROM fact_turbine_10min WHERE state = 'PRODUCIENDO' AND park_code = 'LEO' GROUP BY ALL),
r AS (SELECT *, temp - avg(temp) OVER (PARTITION BY park_code, reading_date) AS residuo FROM d)
SELECT *, avg(residuo) OVER (PARTITION BY turbine_id ORDER BY reading_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS residuo_7d
FROM r WHERE reading_date BETWEEN '2025-06-15' AND '2025-07-31' ORDER BY turbine_id, reading_date;

-- COMMAND ----------

SELECT reading_date, generated_mwh,
       sum(generated_mwh) OVER (ORDER BY reading_date) AS acumulado_mes
FROM v_park_daily WHERE park_code = 'RAW' AND year_month = '2026-09' ORDER BY reading_date;

-- COMMAND ----------

SELECT reading_date, last_cleaning_date,
       datediff(reading_date, last_value(last_cleaning_date, true) OVER (ORDER BY reading_date)) AS dias
FROM mart_panel_cleaning WHERE park_code = 'SUS' ORDER BY reading_date DESC LIMIT 30;

-- COMMAND ----------

WITH m AS (SELECT year_month, sum(lost_curtailment_mwh) AS mwh FROM mart_generation_vs_budget GROUP BY year_month)
SELECT year_month, round(mwh, 1) AS mwh, round(mwh / lag(mwh) OVER (ORDER BY year_month) - 1, 3) AS var_mom
FROM m ORDER BY year_month;
