"""Framework mínimo de calidad de datos (inspirado en las *expectations* de Lakeflow).

Cada regla es una expresión SQL que debe ser VERDADERA para una fila válida.
Acciones posibles:
    warn        la fila sigue, pero el fallo queda registrado en ops.dq_results
    quarantine  la fila se separa a ops.quarantine_<tabla> con el motivo
    fail        se aborta el pipeline (datos que nunca deberían existir)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T

from andes_viento.config import ProjectConfig

DQ_COL = "_dq_failed_rules"


@dataclass(frozen=True)
class Rule:
    name: str
    expr: str
    action: str = "quarantine"

    def __post_init__(self):
        if self.action not in ("warn", "quarantine", "fail"):
            raise ValueError(f"Acción inválida: {self.action}")


class DataQualityError(Exception):
    pass


def tag_failures(df: DataFrame, rules: list[Rule]) -> DataFrame:
    """Agrega un array con el nombre de cada regla que la fila NO cumple.

    `coalesce(expr, false)`: una regla que evalúa NULL se considera fallida
    (en SQL `NULL > 0` no es ni verdadero ni falso: trampa clásica).
    """
    checks = [F.when(~F.coalesce(F.expr(r.expr), F.lit(False)), F.lit(r.name)) for r in rules]
    return df.withColumn(DQ_COL, F.filter(F.array(*checks), lambda x: x.isNotNull()))


def split_valid_invalid(df: DataFrame, rules: list[Rule]) -> tuple[DataFrame, DataFrame]:
    tagged = tag_failures(df, rules)
    blocking = [r.name for r in rules if r.action in ("quarantine", "fail")]
    is_bad = F.arrays_overlap(F.col(DQ_COL), F.array(*[F.lit(n) for n in blocking])) if blocking else F.lit(False)
    return tagged.where(~is_bad), tagged.where(is_bad)


def summarize(tagged: DataFrame, rules: list[Rule]) -> dict[str, int]:
    """Cuenta fallos por regla en UNA sola pasada sobre los datos."""
    aggs = [F.count(F.lit(1)).alias("__total")]
    aggs += [F.sum(F.array_contains(DQ_COL, r.name).cast("int")).alias(r.name) for r in rules]
    row = tagged.agg(*aggs).collect()[0].asDict()
    return {k: int(v or 0) for k, v in row.items()}


DQ_RESULTS_SCHEMA = T.StructType([
    T.StructField("checked_at", T.TimestampType()),
    T.StructField("table_name", T.StringType()),
    T.StructField("rule", T.StringType()),
    T.StructField("action", T.StringType()),
    T.StructField("failed_rows", T.LongType()),
    T.StructField("total_rows", T.LongType()),
    T.StructField("batch_id", T.LongType()),
])


def enforce(
    spark: SparkSession,
    cfg: ProjectConfig,
    df: DataFrame,
    rules: list[Rule],
    table_name: str,
    batch_id: int = -1,
) -> DataFrame:
    """Aplica las reglas, registra métricas, manda a cuarentena y devuelve lo válido."""
    tagged = tag_failures(df, rules)
    stats = summarize(tagged, rules)
    total = stats.pop("__total")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    metrics = [(now, table_name, r.name, r.action, stats[r.name], total, batch_id) for r in rules]
    results_table = cfg.table("ops", "dq_results")
    spark.createDataFrame(metrics, DQ_RESULTS_SCHEMA).write.format("delta").mode("append").saveAsTable(results_table)

    fatal = {r.name: stats[r.name] for r in rules if r.action == "fail" and stats[r.name] > 0}
    if fatal:
        raise DataQualityError(f"{table_name}: reglas bloqueantes fallidas {json.dumps(fatal)}")

    valid, invalid = split_valid_invalid(df, rules)
    if any(stats[r.name] for r in rules if r.action == "quarantine"):
        q = invalid.select(
            F.lit(table_name).alias("table_name"),
            F.current_timestamp().alias("quarantined_at"),
            F.col(DQ_COL).alias("failed_rules"),
            F.to_json(F.struct(*[F.col(c) for c in df.columns])).alias("record"),
        )
        q.write.format("delta").mode("append").saveAsTable(cfg.table("ops", "quarantine"))
    return valid.drop(DQ_COL)
