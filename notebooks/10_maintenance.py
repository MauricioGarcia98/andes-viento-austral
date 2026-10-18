# Databricks notebook source
# MAGIC %md
# MAGIC # 10 · Mantenimiento de tablas Delta
# MAGIC `OPTIMIZE` (compacta archivos chicos y aplica liquid clustering), `VACUUM` (borra archivos viejos,
# MAGIC retención 7 días) y `ANALYZE` (estadísticas para el optimizador y para Genie).
# MAGIC En producción conviene habilitar **Predictive Optimization** y dejar que Databricks lo haga solo.

# COMMAND ----------

# MAGIC %run ./_bootstrap

# COMMAND ----------

from andes_viento.utils.delta import optimize

for layer in ("silver", "gold"):
    for t in spark.catalog.listTables(cfg.schema(layer)):
        if t.tableType == "VIEW" or t.name.startswith("v_") or t.name.startswith("mv_"):
            continue
        full = f"{cfg.schema(layer)}.{t.name}"
        try:
            optimize(spark, full)
            spark.sql(f"VACUUM {full} RETAIN 168 HOURS")
            spark.sql(f"ANALYZE TABLE {full} COMPUTE STATISTICS FOR ALL COLUMNS")
            print("ok", full)
        except Exception as exc:
            print("omitida", full, str(exc)[:120])
