"""Orquestación end-to-end en un solo proceso (lo mismo que hace el Job, sin paralelismo).

Útil para correr todo en local (`scripts/run_local.py`) y en el test de integración.
En Databricks cada paso es una *task* del Job (resources/andes_e2e.job.yml) para poder
paralelizar (for_each), reintentar y monitorear por separado.
"""

from __future__ import annotations

import logging
import time
from datetime import date

from pyspark.sql import SparkSession

from andes_viento.config import ProjectConfig
from andes_viento.datagen.writer import generate_all
from andes_viento.gold.dimensions import load_dimensions
from andes_viento.gold.facts import load_facts
from andes_viento.gold.marts import build_marts
from andes_viento.ingestion.bronze import ingest_all
from andes_viento.quality.gate import run_quality_gate
from andes_viento.setup import create_namespace
from andes_viento.silver.load import load_all
from andes_viento.utils.audit import audited

log = logging.getLogger("andes_viento")


def run_e2e(spark: SparkSession, cfg: ProjectConfig, generate: bool = True, gen_start: date | None = None,
            gen_end: date | None = None, gen_mode: str = "full", gate: bool = True) -> dict[str, float]:
    timings: dict[str, float] = {}

    def step(name: str, target: str, fn):
        t0 = time.time()
        with audited(cfg, spark, name, target) as res:
            res["rows_written"] = None
            fn()
        timings[name] = round(time.time() - t0, 1)
        log.info("%-12s %7.1fs", name, timings[name])

    create_namespace(spark, cfg)
    if generate:
        step("generate", "landing", lambda: generate_all(spark, cfg, gen_start, gen_end, gen_mode))
    step("bronze", "bronze.*", lambda: ingest_all(spark, cfg))
    step("silver", "silver.*", lambda: load_all(spark, cfg))
    step("gold_dims", "gold.dim_*", lambda: load_dimensions(spark, cfg))
    step("gold_facts", "gold.fact_*", lambda: load_facts(spark, cfg))
    step("gold_marts", "gold.mart_*", lambda: build_marts(spark, cfg))
    if gate:
        step("quality_gate", "ops.dq_results", lambda: run_quality_gate(spark, cfg))
    return timings
