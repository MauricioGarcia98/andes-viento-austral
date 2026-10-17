# Databricks notebook source
# MAGIC %md
# MAGIC # 13 · Calidad de datos, cuarentena y SCD Tipo 2
# MAGIC
# MAGIC `silver/rules.py` define reglas como SQL que debe ser VERDADERO. Acción: `warn` (cuenta), `quarantine` (aparta), `fail` (frena).
# MAGIC Todo queda en `ops.dq_results` (métricas) y `ops.quarantine` (filas apartadas con el motivo).

# COMMAND ----------

dbutils.widgets.text("catalog", "andes_viento_dev")
c = dbutils.widgets.get("catalog")
display(spark.sql(f"""
  SELECT table_name, rule, action, sum(failed_rows) AS fallas, sum(total_rows) AS filas,
         round(sum(failed_rows) / sum(total_rows) * 100, 3) AS pct
  FROM {c}.ops.dq_results GROUP BY ALL HAVING fallas > 0 ORDER BY fallas DESC"""))

# COMMAND ----------

display(spark.sql(f"SELECT table_name, failed_rules, record FROM {c}.ops.quarantine LIMIT 20"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### SCD2 en acción: la historia de una turbina de Cerro Arenales (renombrada en jun-2024)

# COMMAND ----------

display(spark.sql(f"""
  SELECT asset_id, asset_tag, firmware, gearbox_serial, valid_from, valid_to, is_current
  FROM {c}.silver.assets_history WHERE park_code = 'CRV' AND asset_id IN
    (SELECT asset_id FROM {c}.silver.assets_history WHERE park_code = 'CRV' LIMIT 1)
  ORDER BY valid_from"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Ejercicios
# MAGIC 1. Escribí una regla nueva para inversores: "la potencia AC nunca supera la DC". ¿`warn` o `quarantine`? Justificá.
# MAGIC 2. Probá `andes_viento.quality.expectations.tag_failures` con esa regla sobre `silver.inverter_5min` (100 mil filas).
# MAGIC 3. Con `silver.scd2.build_versions`, mostrá qué pasa si llega dos veces el mismo cambio (re-envío idéntico).
# MAGIC 4. ¿Qué turbinas tienen más de 2 versiones y por qué motivo cambiaron? (`gold.dim_turbine.change_reason`)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Soluciones

# COMMAND ----------

import sys, os
sys.path.insert(0, os.path.abspath("../src"))
from andes_viento.quality.expectations import Rule, tag_failures, summarize
r = [Rule("ac_menor_que_dc", "ac_power_kw IS NULL OR dc_power_kw IS NULL OR ac_power_kw <= dc_power_kw * 1.01", "warn")]
df = spark.table(f"{c}.silver.inverter_5min").limit(100_000)
print(summarize(tag_failures(df, r), r))
# warn: con potencia DC nula (clipping, falla de medición) la regla falla sin que la fila esté mal.

# COMMAND ----------

from andes_viento.silver.scd2 import build_versions
from pyspark.sql import functions as F
u = spark.createDataFrame([("A1", "CRV-07", "2024-06-01 10:00:00", False), ("A1", "CRV-07", "2024-06-02 10:00:00", False),
                           ("A1", "CRV-WTG007", "2024-06-03 10:00:00", False)],
                          "asset_id string, asset_tag string, updated_at string, is_deleted boolean") \
    .withColumn("updated_at", F.to_timestamp("updated_at"))
display(build_versions(u, ["asset_id"], ["asset_tag"], "updated_at"))   # el re-envío idéntico no crea versión

# COMMAND ----------

display(spark.sql(f"""SELECT turbine_id, count(*) AS versiones, collect_list(change_reason) AS motivos
                      FROM {c}.gold.dim_turbine GROUP BY 1 HAVING count(*) > 2 ORDER BY 2 DESC"""))
