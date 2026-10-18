# Databricks notebook source
# MAGIC %md
# MAGIC # 11 · Simular la llegada de un día nuevo
# MAGIC Genera los archivos que **llegan** el día siguiente al último procesado (modo incremental):
# MAGIC SCADA del día, re-envíos satelitales atrasados, el CSV de inversores, órdenes, precios PRELIMINAR
# MAGIC del día anterior, el pronóstico de mañana... Después el Job dispara el pipeline completo, que sólo
# MAGIC procesa lo nuevo (Auto Loader + watermarks).

# COMMAND ----------

# MAGIC %run ./_bootstrap

# COMMAND ----------

from dataclasses import replace
from datetime import date, timedelta

from andes_viento.datagen.writer import generate_all

dbutils.widgets.text("run_date", "", "Fecha a generar (vacío = siguiente)")
raw = dbutils.widgets.get("run_date")
if raw:
    run_date = date.fromisoformat(raw)
else:
    last = spark.sql(f"SELECT MAX(ingest_date) FROM {cfg.table('bronze', 'scada_turbine')}").collect()[0][0]
    run_date = (last or cfg.end_date) + timedelta(days=1)

print("Llegan los archivos del", run_date)
generate_all(spark, replace(cfg, end_date=run_date), start=run_date, end=run_date, mode="incremental")
dbutils.jobs.taskValues.set("run_date", run_date.isoformat())
