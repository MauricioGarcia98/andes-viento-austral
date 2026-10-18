# Databricks notebook source
# MAGIC %md
# MAGIC # 12 · Desplegar los Genie Agents desde el workspace (sin terminal)
# MAGIC Hace lo mismo que `python scripts/deploy_genie.py --target dev` en una terminal, pero desde un notebook:
# MAGIC crea (o actualiza, si ya existen) los 4 Genie Agents a partir de `genie/agents/*.json`.
# MAGIC
# MAGIC 1. Elegí el **target** en el widget de arriba (`dev` o `prod`).
# MAGIC 2. **Run all**. Al final se imprime el link de cada agent.
# MAGIC
# MAGIC Antes de desplegar revisa que ninguna función certificada tenga parámetros `DATE` (Genie los rechaza, R11 de la
# MAGIC bitácora). Si cambiaste `genie/src/*.yml`, corré antes `python scripts/build_genie.py` (o descomentá la celda 2).

# COMMAND ----------

import os
import sys

dbutils.widgets.dropdown("target", "dev", ["dev", "prod"], "Target")
target = dbutils.widgets.get("target")

_scripts = os.path.abspath(os.path.join(os.getcwd(), "..", "scripts"))
if _scripts not in sys.path:
    sys.path.insert(0, _scripts)

# COMMAND ----------

# Celda 2 (opcional): regenerar los JSON desde los YAML de genie/src/
# import build_genie; build_genie.main()

# COMMAND ----------

import deploy_genie  # noqa: E402

spaces = deploy_genie.deploy(target, None, "Serverless Starter Warehouse", None)
print(f"\n{len(spaces)} Genie Agents listos en el target {target}: menú Genie del workspace.")
