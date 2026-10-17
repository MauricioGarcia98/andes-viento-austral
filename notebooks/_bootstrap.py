# Databricks notebook source
# MAGIC %md
# MAGIC ### Bootstrap común
# MAGIC Se ejecuta con `%run ./_bootstrap` desde cada notebook:
# MAGIC 1. Agrega `../src` al `sys.path` para importar el paquete `andes_viento` (código versionado y testeado).
# MAGIC 2. Fija la zona horaria de la sesión en UTC (convención del proyecto: `*_ts` en UTC, `*_local` en hora argentina).
# MAGIC 3. Declara los widgets comunes y construye `cfg`. En un Job, los *job parameters* llenan los widgets.

# COMMAND ----------

import os
import sys

_src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

spark.conf.set("spark.sql.session.timeZone", "UTC")

dbutils.widgets.text("catalog", "andes_viento_dev", "Catálogo UC")
dbutils.widgets.text("scale_factor", "0.1", "Scale factor")
dbutils.widgets.text("start_date", "2023-01-01", "Fecha inicio")
dbutils.widgets.text("end_date", "2026-09-30", "Fecha fin")

from andes_viento.config import config_from_widgets  # noqa: E402

cfg = config_from_widgets(dbutils)
print(f"catalog={cfg.catalog} | scale_factor={cfg.scale_factor} | rango={cfg.start_date}..{cfg.end_date}")
print(f"landing={cfg.root_path}")
