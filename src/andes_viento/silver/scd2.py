"""Slowly Changing Dimension Tipo 2 implementada a mano con Delta MERGE.

Cada cambio de un atributo "historizable" crea una NUEVA versión de la fila:

    customer_id | city      | valid_from          | valid_to            | is_current
    ----------- | --------- | ------------------- | ------------------- | ----------
    42          | Rosario   | 2023-01-01 10:00:00 | 2024-05-10 08:12:00 | false
    42          | Córdoba   | 2024-05-10 08:12:00 | NULL                | true

Puntos finos que resuelve esta implementación (y que suelen fallar en entrevistas):
  1. Varios cambios del mismo cliente dentro del MISMO lote (carga histórica):
     se arma la cadena de versiones con `lead()` en vez de quedarse con la última.
  2. Re-envíos idénticos: si el hash de atributos no cambió, no se crea versión.
  3. Llegadas tardías: un cambio más viejo que la versión vigente se ignora.
  4. Bajas (DELETE): se cierra la versión vigente y se inserta una con is_deleted.
  5. Idempotencia: re-ejecutar el mismo lote no duplica versiones.
"""

from __future__ import annotations

from collections.abc import Sequence

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from andes_viento.utils.delta import create_table_if_not_exists

HASH_COL = "_row_hash"


def row_hash(cols: Sequence[str]) -> F.Column:
    return F.sha2(F.concat_ws("||", *[F.coalesce(F.col(c).cast("string"), F.lit("<null>")) for c in cols]), 256)


def build_versions(updates: DataFrame, keys: Sequence[str], tracked: Sequence[str], ts_col: str) -> DataFrame:
    """Convierte un lote de cambios en una cadena de versiones SCD2 (sin mirar el destino)."""
    w = Window.partitionBy(*keys).orderBy(F.col(ts_col))
    return (
        updates.withColumn(HASH_COL, row_hash([*tracked, "is_deleted"]))
        .dropDuplicates([*keys, ts_col, HASH_COL])
        .withColumn("_prev_hash", F.lag(HASH_COL).over(w))
        .where(F.col("_prev_hash").isNull() | (F.col("_prev_hash") != F.col(HASH_COL)))
        .drop("_prev_hash")
    )


def scd2_merge(
    spark: SparkSession,
    updates: DataFrame,
    target: str,
    keys: Sequence[str],
    tracked: Sequence[str],
    ts_col: str = "updated_at",
    cluster_by: Sequence[str] = (),
) -> None:
    keys, tracked = list(keys), list(tracked)
    versions = build_versions(updates, keys, tracked, ts_col)
    attrs = [c for c in versions.columns if c not in (HASH_COL,)]

    empty_target = (
        versions.select(*attrs, HASH_COL)
        .withColumn("valid_from", F.col(ts_col))
        .withColumn("valid_to", F.lit(None).cast("timestamp"))
        .withColumn("is_current", F.lit(True))
    )
    create_table_if_not_exists(spark, target, empty_target, cluster_by=cluster_by or keys)

    current = spark.table(target).where("is_current").select(
        *keys, F.col(HASH_COL).alias("_cur_hash"), F.col("valid_from").alias("_cur_from")
    )
    w = Window.partitionBy(*keys).orderBy(F.col(ts_col))
    candidates = (
        versions.join(current, keys, "left")
        # (3) ignorar cambios más viejos que la versión vigente
        .where(F.col("_cur_from").isNull() | (F.col(ts_col) > F.col("_cur_from")))
        .withColumn("_rn", F.row_number().over(w))
        # (2) si la primera versión del lote es igual a la vigente, no es un cambio
        .where(~((F.col("_rn") == 1) & (F.col(HASH_COL) == F.coalesce(F.col("_cur_hash"), F.lit("")))))
        .withColumn("valid_from", F.col(ts_col))
        .withColumn("valid_to", F.lead(ts_col).over(w))
        .withColumn("is_current", F.col("valid_to").isNull())
    )
    # (1) filas para CERRAR la versión vigente: una por clave, con la fecha del primer cambio
    to_close = (
        candidates.where(F.col("_cur_hash").isNotNull())
        .groupBy(*keys).agg(F.min("valid_from").alias("_close_ts"))
        .select(*[F.col(k).alias(f"_mk_{k}") for k in keys], "_close_ts", *[F.col(k) for k in keys])
    )
    to_insert = candidates.select(
        *[F.lit(None).cast(versions.schema[k].dataType).alias(f"_mk_{k}") for k in keys],
        F.lit(None).cast("timestamp").alias("_close_ts"),
        *attrs, HASH_COL, "valid_from", "valid_to", "is_current",
    )
    staged = to_close.unionByName(to_insert, allowMissingColumns=True)

    on = " AND ".join(f"t.`{k}` = s.`_mk_{k}`" for k in keys) + " AND t.is_current = true"
    insert_values = {c: F.col(f"s.`{c}`") for c in [*attrs, HASH_COL, "valid_from", "valid_to", "is_current"]}
    (
        DeltaTable.forName(spark, target).alias("t")
        .merge(staged.alias("s"), on)
        .whenMatchedUpdate(set={"valid_to": "s._close_ts", "is_current": "false"})
        .whenNotMatchedInsert(condition=f"s.`_mk_{keys[0]}` IS NULL", values=insert_values)
        .execute()
    )
