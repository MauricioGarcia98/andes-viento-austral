-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 17 · Capa semántica: metric views y funciones de UC
-- MAGIC Una métrica se define UNA vez. `MEASURE()` la agrega correctamente con cualquier dimensión (incluidos los ratios).

-- COMMAND ----------

USE CATALOG andes_viento_dev;
USE SCHEMA gold;

-- COMMAND ----------

SELECT `Mes`, `Parque`, MEASURE(`Energía generada (MWh)`) AS mwh, MEASURE(`Desvío vs presupuesto (%)`) AS desvio
FROM mv_generacion WHERE `Año` = 2025 AND `Tecnología` = 'Eólico' GROUP BY ALL ORDER BY `Mes`, `Parque`;

-- COMMAND ----------

-- El ratio se recalcula a cualquier nivel: por año entero no es el promedio de los desvíos mensuales
SELECT `Año`, MEASURE(`Desvío vs presupuesto (%)`) AS desvio FROM mv_generacion GROUP BY ALL ORDER BY 1;

-- COMMAND ----------

-- Funciones confiables (trusted assets de Genie)
SELECT * FROM fn_explicar_desvio('Cañadón León', '2025-07');

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Ejercicios
-- MAGIC 1. Agregá a `mv_curtailment` una medida "MWh perdidos por hora con orden" y probala.
-- MAGIC 2. Con `mv_ppa`, cumplimiento por sector y año.
-- MAGIC 3. Escribí `fn_generacion_dia(p_parque, p_fecha)` que devuelva generado, presupuesto y desvío de ese día.
-- MAGIC 4. ¿Por qué conviene que la función acepte código **o** nombre del parque?

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Soluciones

-- COMMAND ----------

SELECT `Parque`, MEASURE(`Energía perdida por curtailment (MWh)`) / MEASURE(`Horas con orden de CAMMESA`) AS mwh_por_hora
FROM mv_curtailment GROUP BY ALL ORDER BY 2 DESC;

-- COMMAND ----------

SELECT `Sector`, `Año`, MEASURE(`Cumplimiento (%)`) AS cumplimiento FROM mv_ppa GROUP BY ALL ORDER BY `Año`, cumplimiento;

-- COMMAND ----------

CREATE OR REPLACE FUNCTION gold.fn_generacion_dia(p_parque STRING, p_fecha DATE)
RETURNS TABLE (park_name STRING, generated_mwh DOUBLE, budget_mwh DOUBLE, desvio DOUBLE)
RETURN SELECT park_name, generated_mwh, budget_mwh, round(generated_mwh / budget_mwh - 1, 4)
       FROM gold.v_park_daily
       WHERE reading_date = p_fecha AND (upper(park_code) = upper(p_parque) OR lower(park_name) = lower(p_parque));
SELECT * FROM gold.fn_generacion_dia('LEO', DATE'2025-07-15');

-- COMMAND ----------

-- MAGIC %md
-- MAGIC 4) Porque Genie pasa lo que dijo el usuario ("Cañadón León", "LEO", "cañadón león"): la función tiene que tolerarlo.
