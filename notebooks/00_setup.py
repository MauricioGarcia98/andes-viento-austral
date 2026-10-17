# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Setup: esquemas, volumen y tablas de operación
# MAGIC
# MAGIC **Antes del primer deploy** el catálogo tiene que existir. En Free Edition (Default Storage) la API
# MAGIC del bundle NO puede crearlo: se crea una vez desde el SQL Editor:
# MAGIC ```sql
# MAGIC CREATE CATALOG IF NOT EXISTS andes_viento_dev COMMENT 'Andes Viento Austral (dev)';
# MAGIC ```
# MAGIC Este notebook crea las capas `landing, bronze, silver, gold, ops`, el volumen `landing.raw`
# MAGIC y las tablas de `ops` (para que las tareas en paralelo no compitan por crearlas).

# COMMAND ----------

# MAGIC %run ./_bootstrap

# COMMAND ----------

from andes_viento.setup import create_namespace

create_namespace(spark, cfg)

# quien corre el job ve todos los parques (el row filter de gold consulta esta tabla)
spark.sql(f"""
  MERGE INTO {cfg.table('ops', 'park_access')} t
  USING (SELECT current_user() AS principal, '*' AS park_code, 'Datos' AS area, current_timestamp() AS granted_at) s
  ON t.principal = s.principal AND t.park_code = s.park_code
  WHEN NOT MATCHED THEN INSERT *
""")
display(spark.sql(f"SHOW SCHEMAS IN {cfg.catalog}"))
