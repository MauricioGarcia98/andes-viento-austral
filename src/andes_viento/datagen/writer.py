"""Escritura de las fuentes generadas en la zona de aterrizaje (landing).

Estructura en el UC Volume:

    /Volumes/<catalog>/landing/raw/landing/<fuente>/ingest_date=YYYY-MM-DD/part-*.{json.gz,csv}

Cada carpeta `ingest_date` es "lo que llegó ese día". Auto Loader la descubre en bronze.
Ojo: que un archivo llegue el día D no significa que sus datos sean del día D (re-envíos
satelitales, exportes tardíos, precios DEFINITIVOS del mes anterior).
"""

from __future__ import annotations

import logging
from datetime import date

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from andes_viento.config import ProjectConfig
from andes_viento.datagen.generators import SCHEMA_DRIFT_CSV, SOURCES

log = logging.getLogger(__name__)
BIG_SOURCES = {"scada_turbine", "inverter_5min", "weather"}


def _write(df: DataFrame, path: str, fmt: str, options: dict, mode: str, big: bool) -> None:
    # fuentes grandes: un archivo por día (evita miles de archivos chicos); chicas: uno solo
    df = df.repartition("ingest_date") if big else df.coalesce(1)
    writer = (
        df.write.format(fmt)
        .mode("overwrite" if mode in ("full", "incremental") else "append")
        .partitionBy("ingest_date")
        .option("maxRecordsPerFile", 1_000_000)
    )
    if mode == "incremental":
        # sólo reemplaza las carpetas ingest_date presentes en df: re-ejecutar un día es idempotente
        writer = writer.option("partitionOverwriteMode", "dynamic")
    for k, v in options.items():
        writer = writer.option(k, v)
    writer.save(path)


def write_source(spark: SparkSession, cfg: ProjectConfig, name: str, start: date, end: date,
                 mode: str = "full") -> str:
    gen, fmt, options = SOURCES[name]
    df = gen(spark, cfg, start, end)
    path = cfg.landing_path(name)
    big = name in BIG_SOURCES
    if not big and df.isEmpty():  # p.ej. cuadrillas en un día sin cambios: no hay archivo nuevo
        return "sin datos"
    drift = SCHEMA_DRIFT_CSV.get(name)
    if drift and fmt == "csv":
        # CSV no tiene esquema: la columna nueva aparece en el header recién desde la fecha de drift
        column, since = drift
        before = df.where(F.col("ingest_date") < F.lit(since)).drop(column)
        after = df.where(F.col("ingest_date") >= F.lit(since))
        if start < since:
            _write(before, path, fmt, options, mode, big)
        if end >= since:
            _write(after, path, fmt, options, "incremental" if (mode == "full" and start < since) else mode, big)
    else:
        _write(df, path, fmt, options, mode, big)
    log.info("Fuente %s escrita en %s", name, path)
    return path


def generate_all(spark: SparkSession, cfg: ProjectConfig, start: date | None = None, end: date | None = None,
                 mode: str = "full", sources: list[str] | None = None) -> dict[str, str]:
    """Genera las fuentes para el rango indicado.

    mode="full"        borra y regenera la historia completa.
    mode="incremental" agrega/reemplaza sólo los días del rango (simula "llegó un día nuevo").
    """
    start = start or cfg.start_date
    end = end or cfg.end_date
    return {name: write_source(spark, cfg, name, start, end, mode) for name in (sources or list(SOURCES))}
