-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 03 · JOINs sobre el modelo estrella
-- MAGIC Hechos (`fact_*`) con claves; dimensiones (`dim_*`) con descripciones. Toda dimensión tiene la fila `-1` "desconocido".

-- COMMAND ----------

USE CATALOG andes_viento_dev;
USE SCHEMA gold;

-- COMMAND ----------

-- INNER JOIN: órdenes con el nombre del parque y la cuadrilla
SELECT o.order_id, p.park_name, c.specialty, o.component, round(o.downtime_hours, 1) AS horas
FROM fact_maintenance_order o
JOIN dim_park p ON p.park_key = o.park_key
JOIN dim_crew c ON c.crew_key = o.crew_key
WHERE o.severity = 'MAYOR';

-- COMMAND ----------

-- Join POINT-IN-TIME con una dimensión SCD2: la multiplicadora que estaba instalada en el momento de la medición
SELECT f.reading_date, t.turbine_tag, t.gearbox_serial, t.change_reason, round(avg(f.gearbox_bearing_c), 1) AS temp
FROM fact_turbine_10min f
JOIN dim_turbine t ON t.turbine_key = f.turbine_key
WHERE f.park_code = 'LEO' AND f.reading_date BETWEEN '2025-06-20' AND '2025-08-31'
GROUP BY ALL ORDER BY t.turbine_tag, f.reading_date;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Ejercicios
-- MAGIC 1. LEFT JOIN: todos los parques eólicos con sus MWh perdidos por curtailment en 2025 (aunque sea 0).
-- MAGIC 2. Anti-join: ¿hay mediciones de `fact_turbine_10min` sin turbina (`turbine_key = -1`)? ¿y sin clima en `dim_weather`?
-- MAGIC 3. Para cada contrato vigente, sus parques de origen con el nombre (pista: `explode(source_parks)`).
-- MAGIC 4. Generación diaria de LEO en julio 2025 con la condición climática del día.
-- MAGIC 5. ¿Cuántas versiones tiene cada turbina que cambió la multiplicadora? (self-join o GROUP BY sobre `dim_turbine`)

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Soluciones

-- COMMAND ----------

SELECT p.park_name, round(coalesce(sum(f.lost_curtailment_mwh), 0), 1) AS mwh
FROM dim_park p
LEFT JOIN fact_curtailment_hourly f ON f.park_key = p.park_key AND year(f.reading_date) = 2025
WHERE p.technology = 'Eólico'
GROUP BY p.park_name ORDER BY mwh DESC;

-- COMMAND ----------

SELECT count(*) AS sin_turbina FROM fact_turbine_10min WHERE turbine_key = -1;

-- COMMAND ----------

SELECT count(*) AS sin_clima FROM fact_turbine_10min f LEFT ANTI JOIN dim_weather w ON w.weather_key = f.weather_key;

-- COMMAND ----------

SELECT c.contract_id, c.client_name, p.park_name
FROM dim_contract c LATERAL VIEW explode(c.source_parks) s AS park_code
JOIN dim_park p ON p.park_code = s.park_code
WHERE c.is_current AND c.contract_key <> -1;

-- COMMAND ----------

SELECT d.reading_date, round(d.generated_mwh, 1) AS mwh, w.weather_condition, w.temp_min_c
FROM v_park_daily d JOIN dim_weather w ON w.park_code = d.park_code AND w.date = d.reading_date
WHERE d.park_code = 'LEO' AND d.year_month = '2025-07' ORDER BY d.reading_date;

-- COMMAND ----------

SELECT turbine_id, count(*) AS versiones
FROM dim_turbine
WHERE turbine_id IN (SELECT turbine_id FROM dim_turbine WHERE change_reason = 'CAMBIO_MULTIPLICADORA')
GROUP BY turbine_id;
