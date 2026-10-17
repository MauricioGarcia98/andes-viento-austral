# Databricks notebook source
# MAGIC %md
# MAGIC # 12 · Structured Streaming y Auto Loader (bronze de verdad)
# MAGIC
# MAGIC - `cloudFiles` descubre archivos nuevos y guarda qué procesó en el **checkpoint**.
# MAGIC - `trigger(availableNow=True)`: procesa lo pendiente y termina → costo de batch, semántica de streaming.
# MAGIC - `schemaEvolutionMode=addNewColumns`: si aparece una columna nueva, Auto Loader **guarda el esquema ampliado y corta**
# MAGIC   con `UNKNOWN_FIELD_EXCEPTION`. Se reinicia y sigue (ver `src/andes_viento/ingestion/bronze.py`).
# MAGIC - En CSV el contrato va por `cloudFiles.schemaHints`. `.schema()` + `addNewColumns` = `CF_ADD_NEW_NOT_SUPPORTED`.

# COMMAND ----------

dbutils.widgets.text("catalog", "andes_viento_dev")
c = dbutils.widgets.get("catalog")
base = f"/Volumes/{c}/landing/raw"

# COMMAND ----------

# MAGIC %md
# MAGIC ### Laboratorio: un Auto Loader propio sobre el CSV de inversores (que tiene drift en jun-2025)

# COMMAND ----------

import time
lab = f"{base}/_lab_{int(time.time())}"
hints = ("`plant` STRING, `inverter` STRING, `timestamp` STRING, `poa_irradiance_wm2` STRING, `module_temp_c` STRING, "
         "`ambient_temp_c` STRING, `dc_power_kw` STRING, `ac_power_kw` STRING, `status` STRING, ingest_date DATE")

def run_once():
    q = (spark.readStream.format("cloudFiles")
         .option("cloudFiles.format", "csv").option("header", "true")
         .option("cloudFiles.schemaLocation", f"{lab}/schema")
         .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
         .option("cloudFiles.inferColumnTypes", "false")
         .option("cloudFiles.schemaHints", hints)
         .load(f"{base}/landing/inverter_5min")
         .writeStream.option("checkpointLocation", f"{lab}/chk").trigger(availableNow=True)
         .toTable(f"{c}.bronze.lab_inverter"))
    q.awaitTermination()

for intento in range(3):
    try:
        run_once(); print("terminó OK"); break
    except Exception as e:
        print("intento", intento, "→", str(e)[:160])

# COMMAND ----------

display(spark.sql(f"SELECT count(*), count(soiling_sensor_pct) FROM {c}.bronze.lab_inverter"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Ejercicios
# MAGIC 1. Volvé a correr `run_once()`: ¿cuántas filas nuevas entran? ¿Por qué?
# MAGIC 2. Cambiá `.option("cloudFiles.schemaHints", hints)` por `.schema(...)` con las mismas columnas: ¿qué error da?
# MAGIC 3. Mirá `_rescued_data` en `bronze.scada_turbine`: ¿hay filas? ¿Qué pondría algo ahí?
# MAGIC 4. ¿Qué diferencia hay entre el checkpoint de bronze y el watermark de gold (`ops.watermarks`)?

# COMMAND ----------

# MAGIC %md
# MAGIC ### Soluciones
# MAGIC 1. Cero: el checkpoint recuerda los archivos ya procesados (exactly-once por archivo).
# MAGIC 2. `CF_ADD_NEW_NOT_SUPPORTED`: con esquema fijo no hay evolución posible. Fue el error 3 de NovaMart.
# MAGIC 3. Valores que no encajan en el tipo inferido (ej. un texto donde se infirió número) o columnas con distinto casing.
# MAGIC 4. El checkpoint es por **archivo** (qué ya leí); el watermark es por **fecha de negocio** (qué días de gold tengo que recalcular).

# COMMAND ----------

display(spark.sql(f"SELECT count(*) AS rescatadas FROM {c}.bronze.scada_turbine WHERE _rescued_data IS NOT NULL"))
spark.sql(f"DROP TABLE IF EXISTS {c}.bronze.lab_inverter")
dbutils.fs.rm(lab, True)
