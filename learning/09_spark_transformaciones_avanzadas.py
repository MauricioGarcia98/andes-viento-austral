# Databricks notebook source
# MAGIC %md
# MAGIC # 09 · Spark: transformaciones avanzadas (lo que hace silver)
# MAGIC Ventanas, `explode`, funciones de orden superior, joins por rango y *broadcast*.

# COMMAND ----------

dbutils.widgets.text("catalog", "andes_viento_dev")
c = dbutils.widgets.get("catalog")
from pyspark.sql import Window, functions as F

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1) Sensores clavados con `lag()`: 6 lecturas iguales seguidas = 1 hora clavado

# COMMAND ----------

s = spark.table(f"{c}.silver.scada_10min").where("park_code = 'LEO' AND reading_date = '2025-07-15'")
w = Window.partitionBy("asset_id").orderBy("ts_utc")
same = [F.lag("vibration_mm_s", k).over(w) == F.col("vibration_mm_s") for k in range(1, 6)]
cond = same[0]
for x in same[1:]:
    cond = cond & x
display(s.withColumn("clavado", F.coalesce(cond, F.lit(False))).groupBy("asset_id", "clavado").count())

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2) Instrucciones de CAMMESA → slots de 10 minutos con `sequence` + `explode`

# COMMAND ----------

ins = spark.table(f"{c}.silver.curtailment_instructions").where("status <> 'ANULADA'")
slots = ins.select("instruction_id", "agent_code", "limit_mw",
                   F.explode(F.sequence("valid_from_ts", F.col("valid_to_ts") - F.expr("INTERVAL 1 SECOND"),
                                        F.expr("INTERVAL 10 MINUTES"))).alias("ts_utc"))
display(slots.groupBy("agent_code").count().orderBy(F.desc("count")))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Ejercicios
# MAGIC 1. Con `percentile_approx`, recalculá el desfase de reloj de una turbina por día de recepción (como `estimate_clock_offset`).
# MAGIC 2. Con `filter` sobre el array `alarms` de `gold.fact_turbine_10min`, contá cuántas lecturas con warning (`-WRN`) tuvo cada turbina de LEO en julio 2025.
# MAGIC 3. Hacé un join por rango: a cada lectura de SCADA de LEO del 26/07/2025 asignale la orden de trabajo abierta (si la hay).
# MAGIC 4. Compará el plan (`explain`) de un join con `F.broadcast(dim_park)` y sin él.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Soluciones

# COMMAND ----------

b = spark.table(f"{c}.bronze.scada_turbine").where("site = 'PAM' AND ingest_date BETWEEN '2024-03-28' AND '2024-04-03'")
ts = F.to_utc_timestamp(F.try_to_timestamp("ts", F.lit("dd/MM/yyyy HH:mm:ss")), "America/Argentina/Buenos_Aires")
rec = F.try_to_timestamp("received_at", F.lit("yyyy-MM-dd'T'HH:mm:ss'Z'"))
display(b.withColumn("delta", F.unix_timestamp(rec) - F.unix_timestamp(ts)).groupBy("turbine", F.to_date(rec).alias("dia"))
         .agg(F.percentile_approx("delta", 0.05).alias("p05_seg")).orderBy("turbine", "dia"))

# COMMAND ----------

f = spark.table(f"{c}.gold.fact_turbine_10min").where("park_code = 'LEO' AND reading_date BETWEEN '2025-07-01' AND '2025-07-31'")
display(f.withColumn("wrn", F.size(F.filter("alarms", lambda a: a.endswith("-WRN"))) > 0)
         .groupBy("turbine_tag").agg(F.sum(F.col("wrn").cast("int")).alias("lecturas_con_warning")))

# COMMAND ----------

o = spark.table(f"{c}.gold.fact_maintenance_order").where("park_code = 'LEO'").select("order_id", "asset_id", "failure_ts", "work_end_ts")
x = f.where("reading_date = '2025-07-26'").alias("f").join(
    o.alias("o"), (F.col("f.turbine_id") == F.col("o.asset_id")) & (F.col("f.ts_utc") >= F.col("o.failure_ts"))
    & (F.col("f.ts_utc") < F.col("o.work_end_ts")), "left")
display(x.select("f.turbine_tag", "f.ts_local", "f.state", "o.order_id").orderBy("f.turbine_tag", "f.ts_local"))

# COMMAND ----------

p = spark.table(f"{c}.gold.dim_park")
f.join(F.broadcast(p), "park_key").explain()   # BroadcastHashJoin
f.join(p, "park_key").explain()                # Spark igual elige broadcast: la tabla es chica (AQE)
