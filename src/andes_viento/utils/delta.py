"""Operaciones Delta Lake reutilizables (MERGE, overwrite parcial, mantenimiento)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession

from andes_viento.config import is_databricks


def table_exists(spark: SparkSession, full_name: str) -> bool:
    return spark.catalog.tableExists(full_name)


def create_table_if_not_exists(
    spark: SparkSession,
    full_name: str,
    df: DataFrame,
    cluster_by: Sequence[str] = (),
    comment: str | None = None,
) -> bool:
    """Crea la tabla vacía con el esquema de `df` si no existe.

    En Databricks se aplica *Liquid Clustering* (`CLUSTER BY`), que reemplaza a
    `PARTITIONED BY` + `ZORDER` en tablas nuevas. Devuelve True si la creó.
    """
    if table_exists(spark, full_name):
        return False
    writer = df.limit(0).writeTo(full_name).using("delta")
    writer = writer.tableProperty("delta.enableChangeDataFeed", "true")
    if is_databricks():  # pragma: no cover
        writer = writer.tableProperty("delta.enableDeletionVectors", "true")
        if cluster_by:
            writer = writer.clusterBy(*cluster_by)
    writer.create()
    if comment:
        spark.sql(f"COMMENT ON TABLE {full_name} IS '{comment.replace(chr(39), '')}'")
    return True


def merge_upsert(
    spark: SparkSession,
    source: DataFrame,
    target_name: str,
    keys: Iterable[str],
    sequence_col: str | None = None,
    update_condition: str | None = None,
) -> None:
    """MERGE genérico tipo SCD1 (insert si no existe, update si cambió).

    `sequence_col` evita que un registro viejo que llega tarde pise a uno más
    nuevo (orden de eventos fuera de secuencia, muy común en CDC).
    """
    keys = list(keys)
    cond = " AND ".join(f"t.`{k}` <=> s.`{k}`" for k in keys)
    target = DeltaTable.forName(spark, target_name)
    matched_cond = update_condition
    if sequence_col:
        seq = f"s.`{sequence_col}` >= t.`{sequence_col}`"
        matched_cond = f"({matched_cond}) AND {seq}" if matched_cond else seq
    (
        target.alias("t")
        .merge(source.alias("s"), cond)
        .whenMatchedUpdateAll(condition=matched_cond)
        .whenNotMatchedInsertAll()
        .execute()
    )


def overwrite_partitions(df: DataFrame, target_name: str, predicate: str) -> None:
    """Sobrescribe sólo el rango de datos que cumple `predicate` (idempotente).

    Patrón clave para facts: reprocesar los días afectados sin tocar el resto.
    """
    (
        df.write.format("delta")
        .mode("overwrite")
        .option("replaceWhere", predicate)
        .saveAsTable(target_name)
    )


def optimize(spark: SparkSession, full_name: str, zorder_by: Sequence[str] = ()) -> None:
    """OPTIMIZE compacta archivos chicos. Con liquid clustering no hace falta ZORDER."""
    stmt = f"OPTIMIZE {full_name}"
    if zorder_by and not is_databricks():
        stmt += f" ZORDER BY ({', '.join(zorder_by)})"
    spark.sql(stmt)
