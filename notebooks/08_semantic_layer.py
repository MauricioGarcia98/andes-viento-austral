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

display(spark.sql(f"SHOW VIEWS IN {cfg.schema('gold')}"))
