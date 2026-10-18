# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · Gold: dimensiones
# MAGIC `dim_turbine` y `dim_contract` son **SCD2**: cada cambio de componente (multiplicadora nueva),
# MAGIC firmware, nombre o adenda de contrato crea una versión. Los hechos se unen "point-in-time".

# COMMAND ----------

# MAGIC %run ./_bootstrap

# COMMAND ----------

from andes_viento.gold.dimensions import load_dimensions
from andes_viento.utils.audit import audited

with audited(cfg, spark, "gold_dimensions", "gold.dim_*"):
    print(load_dimensions(spark, cfg))

# COMMAND ----------

display(spark.sql(f"""
  SELECT turbine_id, turbine_tag, version, change_reason, gearbox_serial, firmware, effective_from, effective_to
  FROM {cfg.table('gold', 'dim_turbine')} WHERE change_reason <> 'ALTA' ORDER BY effective_from DESC LIMIT 20
"""))
