# Databricks notebook source
# MAGIC %md
# MAGIC # 08 · Capa semántica para Genie
# MAGIC - **Metric views**: las métricas oficiales del negocio (una sola definición de "energía perdida").
# MAGIC - **Funciones de UC** (trusted assets): respuestas certificadas que los Genie Agents pueden invocar.
# MAGIC Todo en `sql/semantic/*.sql`.

# COMMAND ----------

# MAGIC %run ./_bootstrap

# COMMAND ----------

from andes_viento.gold.marts import run_sql_folder

print(run_sql_folder(spark, cfg, "semantic"))

# COMMAND ----------

# (SHOW VIEWS IN catalogo.esquema falla en serverless: CROSS_CATALOG_SCHEMA_REFERENCE_NOT_SUPPORTED)
display(spark.sql(f"""
  SELECT table_name, table_type, comment FROM {cfg.catalog}.information_schema.tables
  WHERE table_schema = 'gold' AND (table_name LIKE 'mv_%' OR table_type = 'METRIC_VIEW')
  UNION ALL
  SELECT routine_name, 'FUNCTION', comment FROM {cfg.catalog}.information_schema.routines
  WHERE routine_schema = 'gold'
"""))
