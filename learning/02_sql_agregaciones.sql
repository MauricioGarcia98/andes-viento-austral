-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 02 · Agregaciones: GROUP BY, HAVING y ratios bien calculados
-- MAGIC Regla de oro: **un ratio agregado es un cociente de sumas, no un promedio de ratios.**

-- COMMAND ----------

USE CATALOG andes_viento_dev;
USE SCHEMA gold;

-- COMMAND ----------

SELECT park_name, year(reading_date) AS anio, round(sum(generated_mwh), 1) AS mwh
FROM v_park_daily GROUP BY ALL ORDER BY anio, mwh DESC;

-- COMMAND ----------

-- Factor de capacidad: BIEN (cociente de sumas) vs MAL (promedio de factores diarios)
SELECT park_code,
       round(sum(generated_mwh) / sum(installed_mw * 24), 4) AS fc_bien,
       round(avg(capacity_factor), 4)                         AS fc_promedio_de_promedios
FROM v_park_daily WHERE technology = 'Eólico' GROUP BY park_code;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC En este caso dan parecido porque todos los días pesan igual. Con disponibilidad mensual (meses de 28 y 31 días,
-- MAGIC turbinas que entran a mitad de mes) el promedio de promedios sí engaña.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Ejercicios
-- MAGIC 1. MWh perdidos por curtailment por parque y año (sólo eólicos). ¿Crece año a año?
-- MAGIC 2. Parques con más de 30 días con hielo en palas en toda la historia (`HAVING`).
-- MAGIC 3. Disponibilidad contractual de 2025 por fabricante en `mart_warranty_claims`, bien calculada.
-- MAGIC 4. Costo de mantenimiento en USD por año y tipo de orden (`fact_maintenance_order`).
-- MAGIC 5. Cantidad de órdenes por componente en fallas MAYORES y su parada promedio en días.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Soluciones

-- COMMAND ----------

SELECT park_code, year(reading_date) AS anio, round(sum(lost_curtailment_mwh), 1) AS curtailment_mwh
FROM v_park_daily WHERE technology = 'Eólico' GROUP BY ALL ORDER BY park_code, anio;

-- COMMAND ----------

SELECT park_code, count(*) AS dias FROM v_park_daily WHERE lost_icing_mwh > 0 GROUP BY park_code HAVING count(*) > 30;

-- COMMAND ----------

SELECT manufacturer, round(1 - sum(chargeable_fault_h) / sum(useful_h), 4) AS disponibilidad
FROM mart_warranty_claims WHERE year(month_start) = 2025 GROUP BY manufacturer;

-- COMMAND ----------

SELECT year(created_date) AS anio, order_type, round(sum(total_cost_usd)) AS usd
FROM fact_maintenance_order GROUP BY ALL ORDER BY anio, order_type;

-- COMMAND ----------

SELECT component, count(*) AS fallas, round(avg(downtime_hours) / 24, 1) AS dias_parada
FROM fact_maintenance_order WHERE severity = 'MAYOR' GROUP BY component;
