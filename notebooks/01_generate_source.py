# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Generación de datos sintéticos (una fuente por ejecución)
# MAGIC
# MAGIC El Job corre este notebook **una vez por fuente** con un `for_each_task` (3 en paralelo).
# MAGIC El generador es distribuido (`spark.range` x flota, `xxhash64` como azar determinístico):
# MAGIC con la misma semilla y el mismo `scale_factor` produce SIEMPRE los mismos datos.
# MAGIC
# MAGIC | scale_factor | turbinas | inversores | filas SCADA | filas inversores | landing aprox. |
# MAGIC |---|---|---|---|---|---|
# MAGIC | 0.1 | 37 | 23 | ~7 M | ~5 M | ~3 GB (sin comprimir) |
# MAGIC | 1 | 380 | 220 | ~70 M | ~50 M | ~30 GB |
# MAGIC | 10 | 3.800 | 2.200 | ~700 M | ~500 M | ~300 GB |

# COMMAND ----------

# MAGIC %run ./_bootstrap

# COMMAND ----------

dbutils.widgets.text("source", "scada_turbine", "Fuente")
dbutils.widgets.dropdown("mode", "full", ["full", "incremental"], "Modo")
source, mode = dbutils.widgets.get("source"), dbutils.widgets.get("mode")

import time

from andes_viento.datagen.writer import write_source

t0 = time.time()
path = write_source(spark, cfg, source, cfg.start_date, cfg.end_date, mode)
print(f"{source}: {path} en {time.time() - t0:,.0f}s")

# COMMAND ----------

display(dbutils.fs.ls(cfg.landing_path(source))[:10])
