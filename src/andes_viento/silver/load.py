"""Carga incremental bronze -> silver con Structured Streaming + foreachBatch.

Patrón "streaming incremental en modo batch":
    readStream(bronze) -> foreachBatch(limpiar + validar + MERGE) -> trigger(availableNow)

Orden de dependencias (lo respeta el Job con DOS for_each):
    1) referencia: assets, crews, contracts, fx_rates, spot_prices, budget, dispatch, weather
    2) telemetría y órdenes: scada, inverter, work_orders  (necesitan silver.asset_tags)

| entidad      | estrategia                                                     |
|--------------|----------------------------------------------------------------|
| assets       | SCD2 (historia de componentes, firmware y nombres)             |
| contracts    | SCD2 (adendas de precio y volumen)                             |
| crews        | SCD1 con bajas                                                 |
| work_orders  | CDC imagen completa -> último estado (MERGE con DELETE)        |
| dispatch     | última versión de cada instrucción                             |
| spot_prices  | DEFINITIVO pisa a PRELIMINAR (nunca al revés)                  |
| scada, inverter | insert-only idempotente, primera copia recibida gana        |
"""

from __future__ import annotations

from collections.abc import Callable

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from andes_viento.config import ProjectConfig
from andes_viento.quality.expectations import enforce
from andes_viento.silver import rules
from andes_viento.silver import transforms as T
from andes_viento.silver.scd2 import scd2_merge
from andes_viento.utils.delta import create_table_if_not_exists, merge_cdc, merge_upsert


def _insert_only(spark: SparkSession, df: DataFrame, target: str, keys: list[str], cluster_by: list[str],
                 comment: str | None = None) -> None:
    """MERGE que sólo inserta lo que no existe: idempotente ante re-envíos y reprocesos."""
    create_table_if_not_exists(spark, target, df, cluster_by=cluster_by, comment=comment)
    cond = " AND ".join(f"t.`{k}` = s.`{k}`" for k in keys)
    DeltaTable.forName(spark, target).alias("t").merge(df.alias("s"), cond).whenNotMatchedInsertAll().execute()


def _latest(df: DataFrame, keys: list[str], order_cols: list) -> DataFrame:
    w = Window.partitionBy(*keys).orderBy(*order_cols)
    return df.withColumn("_rn", F.row_number().over(w)).where("_rn = 1").drop("_rn")


def run_incremental(spark: SparkSession, cfg: ProjectConfig, bronze_name: str, checkpoint_name: str,
                    process_batch: Callable[[DataFrame, int], None]) -> None:
    if not spark.catalog.tableExists(cfg.table("bronze", bronze_name)):
        print(f"bronze.{bronze_name} no existe todavía: nada que procesar")
        return
    query = (
        spark.readStream.option("maxFilesPerTrigger", 400).table(cfg.table("bronze", bronze_name))
        .writeStream.foreachBatch(process_batch)
        .option("checkpointLocation", cfg.checkpoint_path(f"silver_{checkpoint_name}"))
        .trigger(availableNow=True)
        .start()
    )
    query.awaitTermination()


# ===================================================================== activos
def load_assets(spark: SparkSession, cfg: ProjectConfig) -> None:
    target = cfg.table("silver", "assets_history")
    tags_t = cfg.table("silver", "asset_tags")

    def batch(df: DataFrame, batch_id: int) -> None:
        s = df.sparkSession
        clean = enforce(s, cfg, T.clean_assets(df), rules.ASSETS, target, batch_id)
        scd2_merge(s, clean.drop("_ingested_at"), target, ["asset_id"], T.ASSET_TRACKED, ts_col="updated_at",
                   cluster_by=["asset_id"])
        # tabla de alias: TODOS los nombres que tuvo cada equipo (resuelve re-envíos con el nombre viejo)
        hist = s.table(target)
        tags = (hist.groupBy("asset_tag", "asset_id")
                .agg(F.min("valid_from").alias("first_seen"), F.max("valid_from").alias("last_change"))
                .join(hist.where("is_current").select("asset_id", "asset_type", "park_code", "rated_kw", "dc_kwp"),
                      "asset_id"))
        tags.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(tags_t)

    run_incremental(spark, cfg, "cmms_assets", "assets", batch)


def load_crews(spark: SparkSession, cfg: ProjectConfig) -> None:
    target = cfg.table("silver", "crews")

    def batch(df: DataFrame, batch_id: int) -> None:
        s = df.sparkSession
        clean = _latest(enforce(s, cfg, T.clean_crews(df), rules.CREWS, target, batch_id), ["crew_id"],
                        [F.col("updated_at").desc()])
        create_table_if_not_exists(s, target, clean, cluster_by=["crew_id"])
        merge_cdc(s, clean, target, ["crew_id"], "updated_at")

    run_incremental(spark, cfg, "cmms_crews", "crews", batch)


def load_contracts(spark: SparkSession, cfg: ProjectConfig) -> None:
    target = cfg.table("silver", "contracts_history")

    def batch(df: DataFrame, batch_id: int) -> None:
        s = df.sparkSession
        clean = enforce(s, cfg, T.clean_contracts(df), rules.CONTRACTS, target, batch_id)
        scd2_merge(s, clean.drop("_ingested_at"), target, ["contract_id"], T.CONTRACT_TRACKED,
                   ts_col="updated_at", cluster_by=["contract_id"])

    run_incremental(spark, cfg, "ppa_contracts", "contracts", batch)


# ======================================================== mercado y Finanzas
def load_fx(spark: SparkSession, cfg: ProjectConfig) -> None:
    target = cfg.table("silver", "fx_rates")

    def batch(df: DataFrame, batch_id: int) -> None:
        s = df.sparkSession
        clean = enforce(s, cfg, T.clean_fx(df), rules.FX, target, batch_id).dropDuplicates(
            ["fx_date", "currency", "rate_type"])
        create_table_if_not_exists(s, target, clean, cluster_by=["fx_date"])
        merge_upsert(s, clean, target, ["fx_date", "currency", "rate_type"])

    run_incremental(spark, cfg, "fx_rates", "fx_rates", batch)


def load_spot(spark: SparkSession, cfg: ProjectConfig) -> None:
    target = cfg.table("silver", "spot_prices")

    def batch(df: DataFrame, batch_id: int) -> None:
        s = df.sparkSession
        clean = _latest(enforce(s, cfg, T.clean_spot_prices(df), rules.SPOT, target, batch_id),
                        ["node", "hour_ts"], [F.col("version_rank").desc(), F.col("_ingested_at").desc()])
        create_table_if_not_exists(s, target, clean, cluster_by=["price_date", "node"])
        merge_upsert(s, clean, target, ["node", "hour_ts"], sequence_col="version_rank")

    run_incremental(spark, cfg, "cammesa_spot_prices", "spot_prices", batch)


def load_budget(spark: SparkSession, cfg: ProjectConfig) -> None:
    target = cfg.table("silver", "generation_budget")

    def batch(df: DataFrame, batch_id: int) -> None:
        s = df.sparkSession
        clean = enforce(s, cfg, T.clean_budget(df), rules.BUDGET, target, batch_id).dropDuplicates(
            ["park_code", "year", "month", "version"])
        create_table_if_not_exists(s, target, clean, cluster_by=["year", "park_code"])
        merge_upsert(s, clean, target, ["park_code", "year", "month", "version"])

    run_incremental(spark, cfg, "generation_budget", "budget", batch)


def load_dispatch(spark: SparkSession, cfg: ProjectConfig) -> None:
    target = cfg.table("silver", "curtailment_instructions")

    def batch(df: DataFrame, batch_id: int) -> None:
        s = df.sparkSession
        clean = _latest(enforce(s, cfg, T.clean_dispatch(df), rules.DISPATCH, target, batch_id),
                        ["instruction_id"], [F.col("version").desc(), F.col("issued_ts").desc()])
        create_table_if_not_exists(s, target, clean, cluster_by=["valid_from_ts"])
        merge_upsert(s, clean, target, ["instruction_id"], sequence_col="version")

    run_incremental(spark, cfg, "cammesa_dispatch", "dispatch", batch)


def load_weather(spark: SparkSession, cfg: ProjectConfig) -> None:
    target = cfg.table("silver", "weather_hourly")

    def batch(df: DataFrame, batch_id: int) -> None:
        s = df.sparkSession
        clean = _latest(enforce(s, cfg, T.clean_weather(df), rules.WEATHER, target, batch_id),
                        ["park_code", "kind", "valid_ts"], [F.col("issued_ts").desc()])
        create_table_if_not_exists(s, target, clean, cluster_by=["valid_date", "park_code"])
        merge_upsert(s, clean, target, ["park_code", "kind", "valid_ts"], sequence_col="issued_ts")

    run_incremental(spark, cfg, "weather", "weather", batch)


# ================================================================ telemetría
def _tags(spark: SparkSession, cfg: ProjectConfig) -> DataFrame:
    return spark.table(cfg.table("silver", "asset_tags"))


def load_scada(spark: SparkSession, cfg: ProjectConfig) -> None:
    target = cfg.table("silver", "scada_10min")

    def batch(df: DataFrame, batch_id: int) -> None:
        s = df.sparkSession
        clean = T.dedupe_first_arrival(T.clean_scada(df, _tags(s, cfg)), ["asset_id", "turbine_tag", "ts_utc"],
                                       "received_ts")
        clean = T.flag_stuck_sensors(clean).select(*T.SCADA_COLUMNS)
        valid = enforce(s, cfg, clean, rules.SCADA, target, batch_id)
        _insert_only(s, valid, target, ["reading_date", "asset_id", "ts_utc"], ["reading_date", "asset_id"],
                     "SCADA de aerogeneradores limpio: 1 fila por turbina cada 10 minutos (UTC)")

    run_incremental(spark, cfg, "scada_turbine", "scada", batch)


def load_inverter(spark: SparkSession, cfg: ProjectConfig) -> None:
    target = cfg.table("silver", "inverter_5min")

    def batch(df: DataFrame, batch_id: int) -> None:
        s = df.sparkSession
        clean = T.dedupe_first_arrival(T.clean_inverter(df, _tags(s, cfg)), ["asset_id", "inverter_tag", "ts_utc"],
                                       "ingest_date")
        valid = enforce(s, cfg, clean, rules.INVERTER, target, batch_id)
        _insert_only(s, valid, target, ["reading_date", "asset_id", "ts_utc"], ["reading_date", "asset_id"],
                     "Inversores solares limpios: 1 fila por inversor cada 5 minutos (sólo de día)")

    run_incremental(spark, cfg, "inverter_5min", "inverter", batch)


def load_work_orders(spark: SparkSession, cfg: ProjectConfig) -> None:
    target = cfg.table("silver", "work_orders")
    parts_t = cfg.table("silver", "work_order_parts")

    def batch(df: DataFrame, batch_id: int) -> None:
        s = df.sparkSession
        clean = enforce(s, cfg, T.clean_work_orders(df, _tags(s, cfg)), rules.WORK_ORDERS, target, batch_id)
        # último evento de cada orden; ante empate de hora, la baja (D) gana
        last = _latest(clean, ["order_id"], [F.col("event_ts").desc(), F.col("is_deleted").desc()])
        create_table_if_not_exists(s, target, last.drop("parts"), cluster_by=["park_code", "created_ts"])
        merge_cdc(s, last.drop("parts"), target, ["order_id"], "event_ts")
        parts = T.explode_parts(last.where("NOT is_deleted"))
        create_table_if_not_exists(s, parts_t, parts, cluster_by=["order_id"])
        ids = last.select("order_id").distinct()
        DeltaTable.forName(s, parts_t).alias("t").merge(ids.alias("s"), "t.order_id = s.order_id") \
            .whenMatchedDelete().execute()
        parts.write.format("delta").mode("append").saveAsTable(parts_t)

    run_incremental(spark, cfg, "cmms_work_orders", "work_orders", batch)


LOADERS = {
    "assets": load_assets,
    "crews": load_crews,
    "contracts": load_contracts,
    "fx_rates": load_fx,
    "spot_prices": load_spot,
    "budget": load_budget,
    "dispatch": load_dispatch,
    "weather": load_weather,
    "scada": load_scada,
    "inverter": load_inverter,
    "work_orders": load_work_orders,
}
REFERENCE_ENTITIES = ["assets", "crews", "contracts", "fx_rates", "spot_prices", "budget", "dispatch", "weather"]
TELEMETRY_ENTITIES = ["scada", "inverter", "work_orders"]


def load_all(spark: SparkSession, cfg: ProjectConfig, names: list[str] | None = None) -> None:
    for name in names or (REFERENCE_ENTITIES + TELEMETRY_ENTITIES):
        LOADERS[name](spark, cfg)
