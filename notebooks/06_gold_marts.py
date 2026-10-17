# Databricks notebook source
# MAGIC %md
# MAGIC # 06 · Gold: marts por caso de negocio (SQL puro en `sql/marts/`)
# MAGIC | mart | caso | dueño |
# MAGIC |---|---|---|
# MAGIC | `mart_generation_vs_budget` | ¿por qué generamos menos? | Dirección / Finanzas |
# MAGIC | `mart_curtailment_battery` | 1 · curtailment y baterías | Finanzas |
# MAGIC | `mart_turbine_health` | 2 · mantenimiento predictivo | Mantenimiento |
# MAGIC | `mart_panel_cleaning` | 3 · limpieza en la Puna | Operación NOA / HSE |
# MAGIC | `fact_ppa_settlement`, `mart_ppa_forecast` | 4 · cumplimiento PPA | Comercial |
# MAGIC | `mart_warranty_claims` | 5 · garantía del fabricante | Mantenimiento / Legal |

# COMMAND ----------

# MAGIC %run ./_bootstrap

# COMMAND ----------

from andes_viento.gold.marts import build_marts
from andes_viento.utils.audit import audited

with audited(cfg, spark, "gold_marts", "gold.mart_*"):
    print(build_marts(spark, cfg))
