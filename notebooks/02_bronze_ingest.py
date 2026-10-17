# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Bronze: Auto Loader de las 11 fuentes
# MAGIC
# MAGIC - JSON (SCADA, CMMS, CAMMESA, clima): esquema inferido y evolutivo (`addNewColumns`).
# MAGIC - CSV: el contrato va por `cloudFiles.schemaHints` (nunca `.schema()` con `addNewColumns`).
# MAGIC - Si aparece una columna nueva (sensores HT-OS 5.0, sensor de suciedad), Auto Loader corta con
# MAGIC   `UNKNOWN_FIELD_EXCEPTION`: el código reinicia el stream (es esperado, no es una falla).

# COMMAND ----------

# MAGIC %run ./_bootstrap

# COMMAND ----------

from andes_viento.ingestion.bronze import ingest_all
from andes_viento.utils.audit import audited

with audited(cfg, spark, "bronze", "bronze.*") as res:
    counts = ingest_all(spark, cfg)
    res["rows_written"] = sum(counts.values())
counts

# COMMAND ----------

display(spark.sql(f"""
  SELECT site, fw, count(*) AS filas, count(sensors.oil_particle_count) AS con_sensor_nuevo,
         count(_rescued_data) AS rescatadas
  FROM {cfg.table('bronze', 'scada_turbine')} GROUP BY ALL ORDER BY site
"""))
