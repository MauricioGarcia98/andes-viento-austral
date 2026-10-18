# Databricks notebook source
# MAGIC %md
# MAGIC # 05 · Gold: hechos
# MAGIC La pieza central es la **descomposición de pérdidas** de cada 10 minutos:
# MAGIC `potencial = generado + red + fallas + mantenimiento + hielo + otras`.
# MAGIC Incremental: sólo se recalculan los días operativos que recibieron datos nuevos (watermark + `replaceWhere`).

# COMMAND ----------

# MAGIC %run ./_bootstrap

# COMMAND ----------

dbutils.widgets.dropdown("full_refresh", "false", ["false", "true"], "Full refresh")
full_refresh = dbutils.widgets.get("full_refresh") == "true"

from andes_viento.gold.facts import load_facts
from andes_viento.utils.audit import audited

with audited(cfg, spark, "gold_facts", "gold.fact_*"):
    print(load_facts(spark, cfg, full_refresh=full_refresh))
