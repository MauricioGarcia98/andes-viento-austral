-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 14 · Modelado dimensional: estrella, grano, matriz bus y la identidad de pérdidas
-- MAGIC Leé antes `docs/07_modelado_dimensional.md`.

-- COMMAND ----------

USE CATALOG andes_viento_dev;
USE SCHEMA gold;

-- COMMAND ----------

-- El GRANO manda: una fila de fact_turbine_10min = una turbina en un slot de 10 minutos
SELECT turbine_id, ts_utc, count(*) FROM fact_turbine_10min GROUP BY ALL HAVING count(*) > 1 LIMIT 5;

-- COMMAND ----------

-- La identidad de pérdidas: potencial ≈ generado + pérdidas por causa (la diferencia es sobre-producción)
SELECT park_code, round(sum(potential_kwh) / 1000, 1) AS potencial,
       round(sum(energy_kwh + lost_curtailment_kwh + lost_fault_kwh + lost_maintenance_kwh + lost_icing_kwh + lost_other_kwh) / 1000, 1) AS suma
FROM fact_turbine_10min WHERE reading_date BETWEEN '2025-07-01' AND '2025-07-31' GROUP BY park_code;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Ejercicios
-- MAGIC 1. Diseñá (en papel) un hecho nuevo: "visitas de cuadrilla a parque". ¿Grano? ¿Dimensiones? ¿Medidas?
-- MAGIC 2. ¿Por qué `availability_contractual` NO se puede sumar ni promediar entre turbinas? Calculá la del parque LEO en 2025 bien.
-- MAGIC 3. Reproducí la cascada de `fn_explicar_desvio('LEO','2025-07')` sólo con `mart_generation_vs_budget`.
-- MAGIC 4. ¿Qué cambia si `dim_park` fuera SCD2 (por ejemplo, cambia el jefe de parque)? ¿Qué preguntas se podrían responder?

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Soluciones

-- COMMAND ----------

-- 1) Grano: una visita (cuadrilla, parque, fecha de llegada). Dimensiones: date, park, crew, (turbine si es puntual).
--    Medidas: horas de viaje, horas en sitio, km, órdenes atendidas. Es un accumulating snapshot si se actualiza al volver.
-- 2) Es un ratio: se calcula como cociente de sumas de horas.
SELECT 1 - sum(fault_h) / sum(24 - excluded_h) AS disponibilidad_leo_2025
FROM fact_availability_daily WHERE park_code = 'LEO' AND year(reading_date) = 2025;

-- COMMAND ----------

SELECT budget_p50_mwh AS presupuesto,
       resource_effect_mwh AS recurso,
       -(lost_curtailment_mwh - budget_curtailment_allowance_mwh) AS curtailment_extra,
       -(lost_fault_mwh + lost_maintenance_mwh - budget_availability_allowance_mwh) AS fallas_extra,
       -lost_icing_mwh AS hielo, -lost_other_mwh AS otras, actual_mwh AS real
FROM mart_generation_vs_budget WHERE park_code = 'LEO' AND year_month = '2025-07';

-- COMMAND ----------

-- MAGIC %md
-- MAGIC 4) Con SCD2 se podría atribuir el desempeño a cada jefe de parque en su período ("¿mejoró la disponibilidad
-- MAGIC desde que cambió el jefe?"). El costo: joins point-in-time en todos los hechos.
