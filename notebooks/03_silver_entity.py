# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Silver por entidad (lo llaman dos `for_each` del Job)
# MAGIC
# MAGIC ```
# MAGIC readStream(bronze) ─▶ foreachBatch: tipar · corregir relojes/husos/unidades · reglas ─▶ MERGE en silver
# MAGIC                                                                    └─▶ ops.quarantine / ops.dq_results
# MAGIC ```
# MAGIC Primero corren las entidades de **referencia** (activos, contratos, precios, clima...) y después la
# MAGIC **telemetría** (SCADA, inversores, órdenes), que necesita `silver.asset_tags` para resolver nombres.

# COMMAND ----------

# MAGIC %run ./_bootstrap

# COMMAND ----------

dbutils.widgets.text("entity", "scada", "Entidad")
entity = dbutils.widgets.get("entity")

from andes_viento.silver.load import LOADERS
from andes_viento.utils.audit import audited

with audited(cfg, spark, f"silver_{entity}", f"silver.{entity}"):
    LOADERS[entity](spark, cfg)

# COMMAND ----------

display(spark.sql(f"""
  SELECT table_name, rule, action, SUM(failed_rows) AS fallas, MAX(total_rows) AS filas_lote
  FROM {cfg.table('ops', 'dq_results')} GROUP BY ALL ORDER BY fallas DESC LIMIT 30
"""))
