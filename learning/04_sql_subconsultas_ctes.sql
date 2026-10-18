-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 04 · Subconsultas y CTEs: preguntas de negocio en pasos
-- MAGIC Un CTE (`WITH ...`) es una consulta con nombre: se lee como una receta.

-- COMMAND ----------

USE CATALOG andes_viento_dev;
USE SCHEMA gold;

-- COMMAND ----------

-- "Hoy" para el negocio es el último día con datos (nunca current_date())
WITH hoy AS (SELECT max(reading_date) AS d FROM v_park_daily),
ultimos7 AS (
    SELECT park_name, sum(generated_mwh) AS mwh, sum(budget_mwh) AS ppto
    FROM v_park_daily, hoy WHERE reading_date > hoy.d - 7 GROUP BY park_name
)
SELECT park_name, round(mwh, 1) AS mwh, round(mwh / ppto - 1, 3) AS desvio FROM ultimos7 ORDER BY desvio;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Ejercicios
-- MAGIC 1. Parques cuyo curtailment de 2025 supera el promedio de los parques eólicos (subconsulta escalar).
-- MAGIC 2. Meses en que la empresa entera estuvo más de 10 % debajo del presupuesto.
-- MAGIC 3. Para cada fabricante, su peor mes de disponibilidad (CTE + ranking simple con `max_by`/`min_by`).
-- MAGIC 4. Contratos con algún mes de faltante (`EXISTS`).
-- MAGIC 5. Turbinas que tuvieron falla mayor Y riesgo ALTO en los 30 días previos (dos CTEs + join).

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Soluciones

-- COMMAND ----------

WITH c AS (SELECT park_code, sum(lost_curtailment_mwh) AS mwh FROM v_park_daily
           WHERE technology = 'Eólico' AND year(reading_date) = 2025 GROUP BY park_code)
SELECT * FROM c WHERE mwh > (SELECT avg(mwh) FROM c) ORDER BY mwh DESC;

-- COMMAND ----------

SELECT year_month, round(sum(actual_mwh) / sum(budget_p50_mwh) - 1, 3) AS desvio
FROM mart_generation_vs_budget GROUP BY year_month HAVING desvio < -0.10 ORDER BY year_month;

-- COMMAND ----------

SELECT manufacturer, min_by(year_month, availability_month) AS peor_mes, round(min(availability_month), 4) AS disp
FROM mart_warranty_claims GROUP BY manufacturer;

-- COMMAND ----------

SELECT DISTINCT contract_id, client_name FROM fact_ppa_settlement s
WHERE EXISTS (SELECT 1 FROM fact_ppa_settlement x WHERE x.contract_id = s.contract_id AND x.shortfall_mwh > 0);

-- COMMAND ----------

WITH fallas AS (
    SELECT asset_id AS turbine_id, created_date AS fecha FROM fact_maintenance_order WHERE severity = 'MAYOR'),
alertas AS (
    SELECT turbine_id, reading_date FROM mart_turbine_health WHERE risk_level = 'ALTO')
SELECT f.turbine_id, f.fecha, max(datediff(f.fecha, a.reading_date)) AS dias_de_aviso
FROM fallas f JOIN alertas a ON a.turbine_id = f.turbine_id AND a.reading_date BETWEEN f.fecha - 30 AND f.fecha - 1
GROUP BY ALL ORDER BY f.fecha;
