"""Quality gate: invariantes del modelo que, si se rompen, frenan el Job.

Es la última barrera antes de que un jefe de parque vea en Genie un número equivocado.
Cada chequeo es una consulta que debe devolver 0 (cantidad de violaciones).
"""

from __future__ import annotations

from pyspark.sql import SparkSession

from andes_viento.config import ProjectConfig


class QualityGateError(Exception):
    pass


def checks(cfg: ProjectConfig) -> dict[str, str]:
    g = lambda t: cfg.table("gold", t)  # noqa: E731
    s = lambda t: cfg.table("silver", t)  # noqa: E731
    return {
        "fact_turbine_10min tiene el mismo grano que silver.scada_10min":
            f"SELECT abs((SELECT COUNT(*) FROM {g('fact_turbine_10min')}) - (SELECT COUNT(*) FROM {s('scada_10min')}))",
        "sin duplicados turbina x slot en silver":
            f"SELECT COUNT(*) FROM (SELECT asset_id, ts_utc FROM {s('scada_10min')} GROUP BY ALL HAVING COUNT(*) > 1)",
        "toda medición tiene turbina (FK a dim_turbine)":
            f"SELECT COUNT(*) FROM {g('fact_turbine_10min')} WHERE turbine_key = -1",
        "una sola versión vigente por turbina":
            f"SELECT COUNT(*) FROM (SELECT turbine_id FROM {g('dim_turbine')} WHERE is_current AND turbine_key <> -1 "
            f"GROUP BY 1 HAVING COUNT(*) > 1)",
        "las versiones SCD2 de turbina no se solapan":
            f"SELECT COUNT(*) FROM {g('dim_turbine')} a JOIN {g('dim_turbine')} b ON a.turbine_id = b.turbine_id "
            f"AND a.turbine_key < b.turbine_key AND a.effective_from < b.effective_to AND b.effective_from < a.effective_to",
        "generado nunca supera la potencia nominal (10 min)":
            f"SELECT COUNT(*) FROM {g('fact_turbine_10min')} f JOIN {g('dim_turbine')} d USING (turbine_key) "
            f"WHERE f.energy_kwh > d.rated_kw / 6 * 1.2",
        "disponibilidad contractual entre 0 y 1":
            f"SELECT COUNT(*) FROM {g('fact_availability_daily')} WHERE availability_contractual < 0 "
            f"OR availability_contractual > 1",
        "liquidación PPA: entregado nunca supera lo comprometido":
            f"SELECT COUNT(*) FROM {g('fact_ppa_settlement')} WHERE delivered_mwh > committed_mwh * 1.0001",
        "la cascada presupuesto -> real cierra (residuo < 0,1 MWh)":
            f"SELECT COUNT(*) FROM {g('mart_generation_vs_budget')} WHERE abs(potential_mwh - actual_mwh "
            f"- lost_curtailment_mwh - lost_fault_mwh - lost_maintenance_mwh - lost_icing_mwh - lost_soiling_mwh "
            f"- lost_other_mwh) > 0.1",
        "órdenes de trabajo sin duplicar":
            f"SELECT COUNT(*) FROM (SELECT order_id FROM {g('fact_maintenance_order')} GROUP BY 1 HAVING COUNT(*) > 1)",
    }


def run_quality_gate(spark: SparkSession, cfg: ProjectConfig, max_quarantine_ratio: float = 0.01) -> list[tuple]:
    results = [(name, int(spark.sql(q).collect()[0][0] or 0)) for name, q in checks(cfg).items()]
    failed = [f"{n} ({v})" for n, v in results if v != 0]
    ratio = spark.sql(
        f"SELECT SUM(failed_rows) / SUM(total_rows) FROM {cfg.table('ops', 'dq_results')} WHERE action = 'quarantine'"
    ).collect()[0][0] or 0.0
    results.append(("ratio de filas en cuarentena", round(float(ratio), 6)))
    if ratio > max_quarantine_ratio:
        failed.append(f"cuarentena {ratio:.2%} > {max_quarantine_ratio:.0%}")
    for name, value in results:
        print(f"{'✅' if value == 0 or name.startswith('ratio') else '❌'} {name}: {value}")
    if failed:
        raise QualityGateError(f"Quality gate FALLÓ: {failed}")
    return results
