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

dbutils.widgets.dropdown("full_refresh", "false", ["false", "true"], "Full refresh (borra todo)")
full_refresh = dbutils.widgets.get("full_refresh") == "true"

from andes_viento.setup import create_namespace, drop_layers

if full_refresh:
    # Reset completo: tablas + checkpoints + esquemas inferidos de Auto Loader. Sin esto, regenerar
    # landing no sirve: Auto Loader IGNORA archivos sobrescritos en la misma ruta (allowOverwrites=false).
    drop_layers(spark, cfg)
    for d in ("_checkpoints", "_schemas"):
        try:
            dbutils.fs.rm(f"{cfg.root_path}/{d}", True)
        except Exception as exc:
            print(d, "no existía:", str(exc)[:80])

create_namespace(spark, cfg)

# quien corre el job ve todos los parques (el row filter de gold consulta esta tabla)
spark.sql(f"""
  MERGE INTO {cfg.table('ops', 'park_access')} t
  USING (SELECT current_user() AS principal, '*' AS park_code, 'Datos' AS area, current_timestamp() AS granted_at) s
  ON t.principal = s.principal AND t.park_code = s.park_code
  WHEN NOT MATCHED THEN INSERT *
""")
display(spark.sql(f"SHOW SCHEMAS IN {cfg.catalog}"))
