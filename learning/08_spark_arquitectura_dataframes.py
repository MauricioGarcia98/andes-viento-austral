# Databricks notebook source
# MAGIC %md
# MAGIC # 08 · Spark: arquitectura y DataFrames (con el generador del proyecto)
# MAGIC - **Driver** planifica; **executors** ejecutan tareas sobre **particiones**. En serverless no ves los nodos, pero existen.
# MAGIC - Las transformaciones son **perezosas**: nada corre hasta una **acción** (`count`, `write`, `display`).
# MAGIC - El generador de SCADA hace `spark.range(slots) x flota` y calcula todo con **expresiones de columna**:
# MAGIC   sin UDFs de Python, Spark optimiza el plan completo (Catalyst + Photon).

# COMMAND ----------

import sys, os
sys.path.insert(0, os.path.abspath("../src"))
from datetime import date
from pyspark.sql import functions as F
from andes_viento.config import ProjectConfig
from andes_viento.datagen import physics as ph
from andes_viento.datagen.generators import generate_scada_turbine

cfg = ProjectConfig(catalog="andes_viento_dev", scale_factor=0.1)

# COMMAND ----------

df = generate_scada_turbine(spark, cfg, date(2025, 7, 1), date(2025, 7, 2))   # perezoso: todavía no corrió nada
df.explain("formatted")   # mirá los BroadcastHashJoin de las tablas guía (fallas, curtailment, clima)

# COMMAND ----------

print(df.count())   # acción: ahora sí se ejecuta

# COMMAND ----------

# MAGIC %md
# MAGIC ### Azar determinístico distribuido
# MAGIC `F.rand()` depende de cómo están particionados los datos. `xxhash64(id, sal)` no: cada fila da SIEMPRE lo mismo.

# COMMAND ----------

from andes_viento.datagen.rand import uniform
r = spark.range(5).withColumn("u", uniform("id", salt="demo"))
display(r.repartition(3).orderBy("id"))   # mismo resultado con 1, 3 o 300 particiones

# COMMAND ----------

# MAGIC %md
# MAGIC ### Ejercicios
# MAGIC 1. Calculá con `ph.wind_ms_col` el viento de Cañadón León cada hora del 3 de julio de 2025 y compará con `ph.wind_ms_py`.
# MAGIC 2. ¿Cuántas particiones tiene `df`? Cambiá a `df.repartition(4)` y medí el tiempo de `count()`.
# MAGIC 3. Reescribí `uniform` como una UDF de Python y compará el tiempo sobre `spark.range(5_000_000)`.
# MAGIC 4. ¿Qué parte del generador corre en el driver y por qué? (pista: `datagen/events.py`)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Soluciones

# COMMAND ----------

from andes_viento.datagen.events import local_epoch
h = spark.range(24).select((F.lit(local_epoch(date(2025, 7, 3))) + F.col("id") * 3600).alias("epoch"))
loc = F.col("epoch") - ph.ART_OFFSET_S
h = h.withColumn("w", ph.wind_ms_col("LEO", F.col("epoch").cast("double"), F.lit(7),
                                     F.pmod(loc, F.lit(86400)) / 3600.0, F.lit(1.0)))
rows = h.collect()
print([(round(r.w, 2), round(ph.wind_ms_py("LEO", r.epoch), 2)) for r in rows[:5]])

# COMMAND ----------

import time
print(df.rdd.getNumPartitions() if hasattr(df, "rdd") else "serverless: usar df.explain()")
t = time.time(); df.repartition(4).count(); print(f"{time.time() - t:.1f}s")

# COMMAND ----------

from pyspark.sql.types import DoubleType
import zlib
slow = F.udf(lambda i: (zlib.crc32(str(i).encode()) % 1000) / 1000, DoubleType())
big = spark.range(5_000_000)
t = time.time(); big.select(F.sum(uniform("id", salt="x"))).collect(); print("columnas:", round(time.time() - t, 1))
t = time.time(); big.select(F.sum(slow("id"))).collect(); print("UDF Python:", round(time.time() - t, 1))

# COMMAND ----------

# MAGIC %md
# MAGIC 4) Clima diario AR(1), fallas, curtailment, suciedad y presupuesto: son **secuenciales** (hoy depende de ayer) y
# MAGIC **chicos** (miles de filas). Se calculan en el driver y se unen por *broadcast* a la tabla grande.
