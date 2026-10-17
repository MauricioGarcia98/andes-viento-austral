"""Corre el pipeline completo en local con Spark + Delta OSS.

    python scripts/run_local.py --scale-factor 0.03 --start 2025-06-25 --end 2025-07-31
    python scripts/run_local.py --increment 2025-08-01     # simula la llegada de un día nuevo
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from andes_viento.config import EXPECTED_TABLES, local_config  # noqa: E402
from andes_viento.pipeline import run_e2e  # noqa: E402
from andes_viento.utils.spark import build_local_spark  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale-factor", type=float, default=0.03)
    ap.add_argument("--start", default="2025-06-25")
    ap.add_argument("--end", default="2025-07-31")
    ap.add_argument("--increment", help="Fecha a agregar en modo incremental (requiere una corrida previa)")
    ap.add_argument("--workdir", default=str(ROOT / ".local"))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    spark = build_local_spark("andes-local", warehouse_dir=f"{args.workdir}/warehouse")
    spark.sparkContext.setLogLevel("ERROR")
    cfg = local_config(f"{args.workdir}/volume", scale_factor=args.scale_factor,
                       start_date=date.fromisoformat(args.start), end_date=date.fromisoformat(args.end))
    if args.increment:
        d = date.fromisoformat(args.increment)
        timings = run_e2e(spark, replace(cfg, end_date=d), gen_start=d, gen_end=d, gen_mode="incremental")
    else:
        timings = run_e2e(spark, cfg)
    print("\nTiempos (s):", timings)
    for layer, tables in EXPECTED_TABLES.items():
        for t in tables:
            name = cfg.table(layer, t)
            if spark.catalog.tableExists(name):
                print(f"{layer:7s} {t:32s} {spark.table(name).count():>12,}")


if __name__ == "__main__":
    main()
