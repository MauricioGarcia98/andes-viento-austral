# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Bienvenida y entorno
# MAGIC
# MAGIC Esta ruta usa **los datos de Andes Viento Austral** (9 parques eólicos, 4 solares) para aprender
# MAGIC SQL → Spark → performance → Delta → streaming → modelado → declarativo → gobierno → Genie → CI/CD.
# MAGIC
# MAGIC **Requisito:** haber corrido el job `andes-viento-e2e` (ver `docs/11_guia_desde_la_web.md`).
# MAGIC
# MAGIC | capa | qué hay | ejemplo |
# MAGIC |---|---|---|
# MAGIC | `landing` | archivos crudos en un Volume | `/Volumes/andes_viento_dev/landing/raw/landing/scada_turbine/` |
# MAGIC | `bronze` | tablas tal cual llegaron + linaje | `bronze.scada_turbine` |
# MAGIC | `silver` | limpio, tipado, historizado | `silver.scada_10min`, `silver.assets_history` |
# MAGIC | `gold` | estrella + marts + metric views | `gold.fact_turbine_10min`, `gold.mv_generacion` |
# MAGIC | `ops` | auditoría y calidad | `ops.pipeline_runs`, `ops.dq_results` |
# MAGIC
# MAGIC Cada módulo tiene **ejercicios** y, más abajo, las **soluciones**. Intentá antes de mirar.

# COMMAND ----------

dbutils.widgets.text("catalog", "andes_viento_dev")
catalog = dbutils.widgets.get("catalog")
spark.sql(f"USE CATALOG {catalog}")
display(spark.sql("SHOW SCHEMAS"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Recorrida rápida: ¿cuántas filas tiene cada capa?

# COMMAND ----------

rows = []
for layer in ("bronze", "silver", "gold", "ops"):
    for t in spark.catalog.listTables(f"{catalog}.{layer}"):
        if t.tableType != "VIEW":
            rows.append((layer, t.name, spark.table(f"{catalog}.{layer}.{t.name}").count()))
display(spark.createDataFrame(rows, "capa string, tabla string, filas long").orderBy("capa", "tabla"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Ejercicios
# MAGIC 1. Listá los archivos que llegaron el 2025-07-15 para `scada_turbine` (pista: `dbutils.fs.ls`).
# MAGIC 2. ¿Cuántas corridas registró `ops.pipeline_runs` y cuál fue el paso más lento?
# MAGIC 3. Abrí un JSON de SCADA de un parque de Hanse Turbinen Werke (DES, PIC, SJU o LEO) de 2025 y uno de 2024: ¿qué cambió?

# COMMAND ----------

# MAGIC %md
# MAGIC ### Soluciones

# COMMAND ----------

display(dbutils.fs.ls(f"/Volumes/{catalog}/landing/raw/landing/scada_turbine/ingest_date=2025-07-15/"))

# COMMAND ----------

display(spark.sql(f"SELECT step, status, round(duration_s) AS seg, finished_at FROM {catalog}.ops.pipeline_runs ORDER BY duration_s DESC LIMIT 10"))

# COMMAND ----------

# MAGIC %md
# MAGIC 3) Desde marzo 2025 el firmware **HT-OS 5.0** agrega `ice_detector`, `oil_particle_count` y `tower_accel_mg`
# MAGIC dentro de `sensors`: es el *schema drift* que Auto Loader absorbe en bronze.

# COMMAND ----------

display(spark.sql(f"""
  SELECT fw, count(*) AS filas, count(sensors.oil_particle_count) AS con_sensor_nuevo
  FROM {catalog}.bronze.scada_turbine WHERE site = 'LEO' GROUP BY fw
"""))
