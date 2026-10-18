# Databricks notebook source
# MAGIC %md
# MAGIC # 09 · Quality gate
# MAGIC El Job **falla** si se rompe alguna invariante del modelo (grano, FKs, SCD2 sin solapes, cascada que
# MAGIC cierra, cuarentena < 1 %). Es la última barrera antes de que Genie responda con un dato roto.

# COMMAND ----------

# MAGIC %run ./_bootstrap

# COMMAND ----------

from andes_viento.quality.gate import run_quality_gate

results = run_quality_gate(spark, cfg)
display(spark.createDataFrame([(n, float(v)) for n, v in results], "chequeo string, valor double"))
