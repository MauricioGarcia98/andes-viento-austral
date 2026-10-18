"""Integración: el pipeline completo landing -> gold + quality gate en Spark local (5 semanas, SF 0,03)."""

from dataclasses import replace
from datetime import date

import pytest

from andes_viento.pipeline import run_e2e

pytestmark = pytest.mark.integration


def test_full_pipeline_and_incremental(spark, cfg):
    cfg = replace(cfg, scale_factor=0.03, start_date=date(2025, 6, 25), end_date=date(2025, 7, 31))
    run_e2e(spark, cfg)   # incluye el quality gate: si una invariante se rompe, el test falla
    g = lambda t: cfg.table("gold", t)  # noqa: E731
    leo = spark.sql(f"SELECT * FROM {g('mart_generation_vs_budget')} WHERE park_code = 'LEO' AND year_month = '2025-07'").first()
    assert leo.variance_pct < -0.15                     # la historia guionada aparece
    assert leo.lost_curtailment_mwh > 0 and leo.lost_icing_mwh > 0 and leo.lost_fault_mwh > 0
    # la foto inicial del CMMS ya trae el firmware de mar-2025 (los cambios previos al inicio se pliegan)
    htw = spark.table(g("dim_turbine")).where("is_current AND manufacturer_code = 'HTW'")
    assert htw.count() > 0 and htw.where("firmware <> 'HT-OS 5.0'").count() == 0
    before = spark.table(g("fact_turbine_10min")).count()
    # llega un día nuevo: sólo se procesa lo nuevo y el gate sigue verde
    nxt = replace(cfg, end_date=date(2025, 8, 1))
    run_e2e(spark, nxt, gen_start=date(2025, 8, 1), gen_end=date(2025, 8, 1), gen_mode="incremental")
    assert spark.table(g("fact_turbine_10min")).count() > before
