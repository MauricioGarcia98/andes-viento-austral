# Databricks notebook source
# MAGIC %md
# MAGIC # 10 · Performance: leer menos, mover menos, escribir mejor
# MAGIC
# MAGIC | palanca | en este proyecto |
# MAGIC |---|---|
# MAGIC | **Pruning de archivos** | liquid clustering por `(reading_date, park_code)` en los hechos; filtrar SIEMPRE por fecha |
# MAGIC | **Broadcast** | dimensiones y tablas guía (fallas, curtailment) se unen por broadcast |
# MAGIC | **AQE** | serverless lo trae activo: une particiones chicas y corrige skew en joins |
# MAGIC | **Pre-agregar** | `fact_inverter_hourly` (5 min → hora) y los marts mensuales |
# MAGIC | **Evitar UDFs de Python** | toda la física son expresiones de columna |
# MAGIC | **Archivos del tamaño correcto** | landing: un archivo por día y fuente; `OPTIMIZE` semanal |

# COMMAND ----------

dbutils.widgets.text("catalog", "andes_viento_dev")
c = dbutils.widgets.get("catalog")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Mirá cuántos archivos lee una consulta (pestaña "Query profile" o `EXPLAIN`)

# COMMAND ----------

display(spark.sql(f"DESCRIBE DETAIL {c}.gold.fact_turbine_10min"))

# COMMAND ----------

q_bien = f"SELECT sum(energy_kwh) FROM {c}.gold.fact_turbine_10min WHERE reading_date BETWEEN '2025-07-01' AND '2025-07-31' AND park_code = 'LEO'"
q_mal = f"SELECT sum(energy_kwh) FROM {c}.gold.fact_turbine_10min WHERE date_format(ts_local, 'yyyy-MM') = '2025-07' AND turbine_tag LIKE 'LEO%'"
import time
for name, q in (("filtrando por columnas de clustering", q_bien), ("filtrando con funciones", q_mal)):
    t = time.time(); spark.sql(q).collect(); print(f"{name}: {time.time() - t:.2f}s")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Skew: una fuente de desbalance real
# MAGIC Cerro Arenales tiene más turbinas que nadie; y en las horas de curtailment Santa Cruz concentra filas.
# MAGIC En un `groupBy("park_code")` con millones de filas, un parque "pesado" puede retrasar una tarea.

# COMMAND ----------

display(spark.sql(f"SELECT park_code, count(*) AS filas FROM {c}.gold.fact_turbine_10min GROUP BY 1 ORDER BY 2 DESC"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Ejercicios
# MAGIC 1. Corré `EXPLAIN FORMATTED` de las dos consultas de arriba: ¿dónde aparece el filtro empujado (*PushedFilters* / *data filters*)?
# MAGIC 2. ¿Cuántas filas generaría el SCADA a SF=10? Estimá cuánto tardaría el generador si a SF 0,1 tardó lo que dice `ops.pipeline_runs`.
# MAGIC 3. Agregá `CLUSTER BY` distinto (por `turbine_id`) en una copia de la tabla y medí la consulta por turbina.
# MAGIC 4. ¿Por qué `mart_turbine_health` agrega a día ANTES de calcular las ventanas?

# COMMAND ----------

# MAGIC %md
# MAGIC ### Soluciones

# COMMAND ----------

spark.sql("EXPLAIN FORMATTED " + q_bien).show(truncate=False)

# COMMAND ----------

display(spark.sql(f"""SELECT step, round(duration_s) AS seg FROM {c}.ops.pipeline_runs
                      WHERE step LIKE 'silver_scada%' OR step = 'bronze' ORDER BY finished_at DESC LIMIT 5"""))
# SF 10 = 100x las filas de SF 0,1 (~700 M). El generador escala casi lineal con el cómputo disponible.

# COMMAND ----------

spark.sql(f"CREATE OR REPLACE TABLE {c}.gold.tmp_por_turbina CLUSTER BY (turbine_id) AS SELECT * FROM {c}.gold.fact_turbine_10min WHERE year(reading_date) = 2025")
t = time.time(); spark.sql(f"SELECT sum(energy_kwh) FROM {c}.gold.tmp_por_turbina WHERE turbine_id = 'WTG00033'").collect(); print(time.time() - t)
spark.sql(f"DROP TABLE {c}.gold.tmp_por_turbina")

# COMMAND ----------

# MAGIC %md
# MAGIC 4) Las ventanas ordenan dentro de cada partición: sobre 144 filas por turbina-día es 144 veces más caro que sobre 1.
# MAGIC Agregar primero reduce el volumen que hay que ordenar y mover (*shuffle*).
