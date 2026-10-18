"""Auditoría de ejecuciones y watermarks incrementales (esquema `ops`)."""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql import types as T

from andes_viento.config import ProjectConfig

RUNS_SCHEMA = T.StructType(
    [
        T.StructField("step", T.StringType()),
        T.StructField("target", T.StringType()),
        T.StructField("status", T.StringType()),
        T.StructField("rows_written", T.LongType()),
        T.StructField("duration_s", T.DoubleType()),
        T.StructField("error", T.StringType()),
        T.StructField("finished_at", T.TimestampType()),
    ]
)

WATERMARK_SCHEMA = T.StructType(
    [
        T.StructField("pipeline", T.StringType()),
        T.StructField("high_watermark", T.TimestampType()),
        T.StructField("updated_at", T.TimestampType()),
    ]
)


def _ensure(spark: SparkSession, name: str, schema: T.StructType) -> None:
    if not spark.catalog.tableExists(name):
        spark.createDataFrame([], schema).write.format("delta").saveAsTable(name)


def log_run(cfg: ProjectConfig, spark: SparkSession, **values) -> None:
    name = cfg.table("ops", "pipeline_runs")
    _ensure(spark, name, RUNS_SCHEMA)
    row = {f.name: values.get(f.name) for f in RUNS_SCHEMA.fields}
    row["finished_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
    spark.createDataFrame([row], RUNS_SCHEMA).write.format("delta").mode("append").saveAsTable(name)


@contextmanager
def audited(cfg: ProjectConfig, spark: SparkSession, step: str, target: str):
    """Context manager que registra duración, filas y errores de cada paso."""
    start = time.time()
    result: dict = {"rows_written": None}
    try:
        yield result
    except Exception as exc:  # se registra y se relanza
        log_run(cfg, spark, step=step, target=target, status="FAILED",
                duration_s=time.time() - start, error=str(exc)[:4000])
        raise
    log_run(cfg, spark, step=step, target=target, status="SUCCEEDED",
            rows_written=result.get("rows_written"), duration_s=time.time() - start)


def get_watermark(cfg: ProjectConfig, spark: SparkSession, pipeline: str) -> datetime | None:
    name = cfg.table("ops", "watermarks")
    _ensure(spark, name, WATERMARK_SCHEMA)
    rows = spark.table(name).where(f"pipeline = '{pipeline}'").select("high_watermark").collect()
    return rows[0][0] if rows else None


def set_watermark(cfg: ProjectConfig, spark: SparkSession, pipeline: str, value: datetime) -> None:
    from andes_viento.utils.delta import merge_upsert

    name = cfg.table("ops", "watermarks")
    _ensure(spark, name, WATERMARK_SCHEMA)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    src = spark.createDataFrame([(pipeline, value, now)], WATERMARK_SCHEMA)
    merge_upsert(spark, src, name, keys=["pipeline"])
