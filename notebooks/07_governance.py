# Databricks notebook source
# MAGIC %md
# MAGIC # 07 · Gobierno en Unity Catalog
# MAGIC Comentarios de tablas y columnas, PK/FK declaradas, tags de PII, máscaras de columna
# MAGIC (contactos de clientes, teléfonos de cuadrillas, precios PPA) y row filter por parque
# MAGIC (cada jefe de parque ve sólo su parque). Todo en `sql/governance/*.sql`.

# COMMAND ----------

# MAGIC %run ./_bootstrap

# COMMAND ----------

from andes_viento.gold.marts import run_sql_folder

print(run_sql_folder(spark, cfg, "governance"))
