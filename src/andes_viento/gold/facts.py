"""Tablas de hechos del modelo estrella.

| hecho                    | tipo Kimball            | grano                                  |
|--------------------------|-------------------------|----------------------------------------|
| fact_turbine_10min       | transaccional (medición)| turbina x 10 minutos                   |
| fact_inverter_hourly     | agregado                | inversor x hora                        |
| fact_curtailment_hourly  | agregado                | parque eólico x hora                   |
| fact_maintenance_order   | accumulating snapshot   | orden de trabajo (se actualiza por hito)|
| fact_availability_daily  | periodic snapshot       | turbina x día                          |
| fact_ppa_settlement      | periodic snapshot (SQL) | contrato x mes  -> sql/marts/          |

La pieza central es la DESCOMPOSICIÓN DE PÉRDIDAS de cada 10 minutos:

    potencial (curva de potencia x viento) = generado + pérdida por (red | falla | mantenimiento | hielo | otras)

Con esa identidad, "¿por qué generamos menos?" se responde sumando columnas.

Carga incremental: se recalculan sólo las fechas operativas (`reading_date`) que
recibieron datos nuevos desde el último watermark (`replaceWhere`, idempotente).
"""

from __future__ import annotations

from datetime import datetime

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from andes_viento.config import ProjectConfig
from andes_viento.datagen.physics import CUT_IN_MS, CUT_OUT_MS
from andes_viento.gold.dimensions import UNKNOWN_KEY, weather_key
from andes_viento.utils.audit import get_watermark, set_watermark
from andes_viento.utils.delta import create_table_if_not_exists, overwrite_partitions

STATE = {0: "PRODUCIENDO", 1: "FALLA", 2: "MANTENIMIENTO", 3: "HIELO", 4: "LIMITADA_RED", 5: "VIENTO_BAJO",
         6: "VIENTO_EXTREMO"}


def _date_key(col: str | F.Column) -> F.Column:
    c = F.col(col) if isinstance(col, str) else col
    return F.date_format(c, "yyyyMMdd").cast("int")


def _pit_join(fact: DataFrame, dim: DataFrame, natural_key: str, fact_key: str, ts_col: str, key_col: str,
              extra: list = ()) -> DataFrame:
    """Join point-in-time: la versión de la dimensión vigente en el momento del hecho."""
    d = dim.select(F.col(natural_key).alias("_nk"), key_col, F.col("effective_from").alias("_ef"),
                   F.col("effective_to").alias("_et"), *extra)
    joined = fact.join(F.broadcast(d), (fact[fact_key] == d["_nk"]) & (fact[ts_col] >= d["_ef"])
                       & (fact[ts_col] < d["_et"]), "left")
    return joined.drop("_nk", "_ef", "_et").withColumn(key_col, F.coalesce(F.col(key_col),
                                                                           F.lit(UNKNOWN_KEY).cast("bigint")))


def _changed_dates(spark: SparkSession, table: str, date_col: str, since: datetime | None) -> list:
    df = spark.table(table)
    if since is not None:
        df = df.where(F.col("_ingested_at") > F.lit(since))
    return sorted(r[0] for r in df.select(date_col).distinct().collect() if r[0] is not None)


def _max_ingested(spark: SparkSession, table: str):
    return spark.table(table).agg(F.max("_ingested_at")).collect()[0][0]


def _in_dates(col: str, dates: list) -> str:
    return f"{col} IN ({', '.join(repr(d.isoformat()) for d in dates)})"


def _incremental(spark: SparkSession, cfg: ProjectConfig, name: str, source: str, date_col: str, target_date_col: str,
                 builder, cluster_by: list[str], comment: str, full_refresh: bool) -> int:
    """Esqueleto común: watermark -> fechas cambiadas -> build -> overwrite/replaceWhere -> watermark."""
    target = cfg.table("gold", name)
    src = cfg.table("silver", source)
    if not spark.catalog.tableExists(src):
        return 0
    wm = None if full_refresh or not spark.catalog.tableExists(target) else get_watermark(cfg, spark, name)
    new_wm = _max_ingested(spark, src)
    dates = None if wm is None else _changed_dates(spark, src, date_col, wm)
    if dates == []:
        return 0
    df = builder(spark, cfg, dates)
    if dates is None:
        create_table_if_not_exists(spark, target, df, cluster_by=cluster_by, comment=comment)
        df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(target)
    else:
        overwrite_partitions(df, target, _in_dates(target_date_col, dates))
    if new_wm:
        set_watermark(cfg, spark, name, new_wm)
    return len(dates) if dates else -1


def _power_curve(wind: F.Column, rated_kw: F.Column, rated_ms: F.Column) -> F.Column:
    frac = (F.pow(wind, 3) - CUT_IN_MS ** 3) / (F.pow(rated_ms, 3) - CUT_IN_MS ** 3)
    p = rated_kw * F.least(F.lit(1.0), F.greatest(F.lit(0.0), frac))
    return F.when(wind.isNull(), None).when((wind < CUT_IN_MS) | (wind >= CUT_OUT_MS), 0.0).otherwise(p)


# ======================================================= fact_turbine_10min
def build_fact_turbine_10min(spark: SparkSession, cfg: ProjectConfig, dates: list | None) -> DataFrame:
    scada = spark.table(cfg.table("silver", "scada_10min"))
    if dates is not None:
        scada = scada.where(F.col("reading_date").isin(dates))
    dim_t = spark.table(cfg.table("gold", "dim_turbine")).where(f"turbine_key <> {UNKNOWN_KEY}")
    dim_p = spark.table(cfg.table("gold", "dim_park")).select("park_code", "park_key")
    instr = spark.table(cfg.table("silver", "curtailment_instructions")).where("status <> 'ANULADA'")
    # instrucción -> slots de 10 min (tabla chica: miles de filas)
    slots = (
        instr.join(F.broadcast(spark.table(cfg.table("gold", "dim_park"))
                               .select(F.col("cammesa_agent_code").alias("agent_code"), "park_code")), "agent_code")
        .select("park_code", "instruction_id", "limit_mw", "reason",
                F.explode(F.sequence(F.col("valid_from_ts"), F.col("valid_to_ts") - F.expr("INTERVAL 1 SECOND"),
                                     F.expr("INTERVAL 10 MINUTES"))).alias("ts_utc"))
        .dropDuplicates(["park_code", "ts_utc"])
    )
    f = _pit_join(scada, dim_t, "turbine_id", "asset_id", "ts_utc", "turbine_key",
                  [F.col("rated_wind_ms").alias("_rated_ms"), F.col("rated_kw").alias("_rated_kw")])
    park_wind = Window.partitionBy("park_code", "ts_utc")
    f = (
        f.join(F.broadcast(dim_p), "park_code", "left")
        .join(slots, ["park_code", "ts_utc"], "left")
        # anemómetro clavado o nulo: se usa el viento medio del resto del parque en ese slot
        .withColumn("_park_wind", F.avg("wind_ms").over(park_wind))
        .withColumn("wind_used_ms", F.coalesce("wind_ms", "_park_wind"))
        .withColumn("wind_source", F.when(F.col("wind_ms").isNotNull(), "propio")
                    .when(F.col("_park_wind").isNotNull(), "promedio_parque"))
        .withColumn("potential_kw", _power_curve(F.col("wind_used_ms"), F.col("_rated_kw"), F.col("_rated_ms")))
        .withColumn("state", F.element_at(F.create_map(*[x for k, v in STATE.items() for x in (F.lit(k), F.lit(v))]),
                                          F.col("status_code")))
        .withColumn("_gen_kw", F.greatest(F.coalesce("power_kw", F.lit(0.0)), F.lit(0.0)))
        .withColumn("_lost_kwh", F.greatest(F.coalesce("potential_kw", F.lit(0.0)) - F.col("_gen_kw"), F.lit(0.0)) / 6)
    )
    lost = lambda st: F.when(F.col("status_code").isin(*st), F.col("_lost_kwh")).otherwise(0.0)  # noqa: E731
    return f.select(
        _date_key("reading_date").alias("date_key"), "reading_date", "ts_utc", "ts_local",
        F.hour("ts_local").alias("hour_local"),
        F.coalesce("park_key", F.lit(UNKNOWN_KEY)).alias("park_key"), "turbine_key",
        weather_key(F.col("park_code"), F.col("reading_date")).alias("weather_key"),
        F.col("asset_id").alias("turbine_id"), "park_code", "turbine_tag", "state", "status_code", "alarms",
        "instruction_id", F.col("limit_mw").alias("grid_limit_mw"), F.col("reason").alias("grid_reason"),
        "setpoint_kw", "wind_ms", "wind_used_ms", "wind_source", "rotor_rpm", "power_kw",
        F.round("potential_kw", 1).alias("potential_kw"),
        F.round(F.col("_gen_kw") / 6, 3).alias("energy_kwh"),
        F.round(F.least(F.coalesce("power_kw", F.lit(0.0)), F.lit(0.0)) / 6, 3).alias("aux_consumption_kwh"),
        F.round(F.coalesce("potential_kw", F.lit(0.0)) / 6, 3).alias("potential_kwh"),
        F.round(lost([4]), 3).alias("lost_curtailment_kwh"),
        F.round(lost([1]), 3).alias("lost_fault_kwh"),
        F.round(lost([2]), 3).alias("lost_maintenance_kwh"),
        F.round(lost([3]), 3).alias("lost_icing_kwh"),
        F.round(lost([0, 5, 6]), 3).alias("lost_other_kwh"),
        "pitch_deg", "gearbox_bearing_c", "main_bearing_c", "generator_bearing_c", "nacelle_c", "ambient_c",
        "vibration_mm_s", "ice_detector", "oil_particle_count", "tower_accel_mg",
        F.array_compact(F.array(
            F.when(F.col("clock_corrected"), F.lit("reloj_corregido")),
            F.when(F.col("tz_corrected"), F.lit("huso_corregido")),
            F.when(F.col("unit_converted"), F.lit("unidad_mw_a_kw")),
            F.when(F.col("late_arrival"), F.lit("llego_tarde")),
            F.when(F.size("stuck_sensors") > 0, F.lit("sensor_clavado")),
            F.when(F.col("wind_source") == "promedio_parque", F.lit("viento_sustituido")),
        )).alias("data_quality_flags"),
    )


# ===================================================== fact_inverter_hourly
def build_fact_inverter_hourly(spark: SparkSession, cfg: ProjectConfig, dates: list | None) -> DataFrame:
    inv = spark.table(cfg.table("silver", "inverter_5min"))
    if dates is not None:
        inv = inv.where(F.col("reading_date").isin(dates))
    dim_i = spark.table(cfg.table("gold", "dim_inverter")).select("inverter_id", "inverter_key", "rated_kw", "dc_kwp")
    dim_p = spark.table(cfg.table("gold", "dim_park")).select("park_code", "park_key")
    temp_factor = 1 - 0.004 * (F.coalesce("module_temp_c", F.col("ambient_temp_c") + 0.03 * F.col("poa_wm2")) - 25)
    expected_kw = F.least(F.col("rated_kw"), F.col("dc_kwp") * F.col("poa_wm2") / 1000 * temp_factor * 0.975)
    return (
        inv.join(F.broadcast(dim_i), F.col("asset_id") == F.col("inverter_id"), "left")
        .join(F.broadcast(dim_p), "park_code", "left")
        .withColumn("hour_ts_utc", F.date_trunc("hour", "ts_utc"))
        .groupBy("reading_date", "hour_ts_utc", "park_code", "park_key", "inverter_key", "asset_id", "inverter_tag")
        .agg(
            F.count("*").alias("readings"),
            F.round(F.sum(F.coalesce("ac_power_kw", F.lit(0.0))) / 12, 3).alias("energy_kwh"),
            F.round(F.sum(F.coalesce("dc_power_kw", F.lit(0.0))) / 12, 3).alias("dc_energy_kwh"),
            F.round(F.sum(F.coalesce(expected_kw, F.lit(0.0))) / 12, 3).alias("expected_clean_kwh"),
            F.round(F.sum(F.coalesce("poa_wm2", F.lit(0.0))) / 12 / 1000, 4).alias("poa_irradiation_kwh_m2"),
            F.round(F.avg("module_temp_c"), 1).alias("module_temp_avg_c"),
            F.sum(F.when(F.col("status") == "FAULT", 1).otherwise(0)).alias("fault_readings"),
            F.round(F.avg("soiling_sensor_pct"), 2).alias("soiling_sensor_pct"),
            F.max(F.col("unit_converted").cast("int")).cast("boolean").alias("unit_converted"),
        )
        .select(
            _date_key("reading_date").alias("date_key"), "reading_date", "hour_ts_utc",
            F.from_utc_timestamp("hour_ts_utc", "America/Argentina/Buenos_Aires").alias("hour_local"),
            F.coalesce("park_key", F.lit(UNKNOWN_KEY)).alias("park_key"),
            F.coalesce("inverter_key", F.lit(UNKNOWN_KEY).cast("bigint")).alias("inverter_key"),
            weather_key(F.col("park_code"), F.col("reading_date")).alias("weather_key"),
            "park_code", F.col("asset_id").alias("inverter_id"), "inverter_tag", "readings", "energy_kwh",
            "dc_energy_kwh", "expected_clean_kwh", "poa_irradiation_kwh_m2", "module_temp_avg_c", "fault_readings",
            "soiling_sensor_pct", "unit_converted",
            F.round(F.try_divide(F.col("energy_kwh"), F.col("expected_clean_kwh")), 4).alias("performance_ratio"),
        )
    )


# ================================================== fact_curtailment_hourly
def build_fact_curtailment_hourly(spark: SparkSession, cfg: ProjectConfig, dates: list | None) -> DataFrame:
    t = spark.table(cfg.table("gold", "fact_turbine_10min"))
    if dates is not None:
        t = t.where(F.col("reading_date").isin(dates))
    parks = spark.table(cfg.table("gold", "dim_park")).select("park_code", "cammesa_node", "installed_mw")
    spot = spark.table(cfg.table("silver", "spot_prices")).select(
        F.col("node").alias("cammesa_node"), F.col("hour_ts").alias("hour_ts_utc"), "price_ars_mwh")
    fx = spark.table(cfg.table("gold", "dim_date")).select(F.col("date").alias("reading_date"), "fx_ars_usd")
    hourly = (
        t.withColumn("hour_ts_utc", F.date_trunc("hour", "ts_utc"))
        .groupBy("reading_date", "date_key", "hour_ts_utc", "park_code", "park_key")
        .agg(
            F.round(F.sum("energy_kwh") / 1000, 4).alias("generated_mwh"),
            F.round(F.sum("potential_kwh") / 1000, 4).alias("potential_mwh"),
            F.round(F.sum("lost_curtailment_kwh") / 1000, 4).alias("lost_curtailment_mwh"),
            F.sum(F.when(F.col("state") == "LIMITADA_RED", 1).otherwise(0)).alias("curtailed_readings"),
            F.count("*").alias("readings"),
            F.max("grid_limit_mw").alias("grid_limit_mw"),
            F.first("grid_reason", ignorenulls=True).alias("grid_reason"),
            F.first("instruction_id", ignorenulls=True).alias("instruction_id"),
        )
    )
    return (
        hourly.join(F.broadcast(parks), "park_code", "left")
        .join(spot, ["cammesa_node", "hour_ts_utc"], "left")
        .join(F.broadcast(fx), "reading_date", "left")
        .withColumn("spot_usd_mwh", F.round(F.try_divide(F.col("price_ars_mwh"), F.col("fx_ars_usd")), 2))
        .select(
            "date_key", "reading_date", "hour_ts_utc",
            F.from_utc_timestamp("hour_ts_utc", "America/Argentina/Buenos_Aires").alias("hour_local"),
            "park_key", "park_code", "cammesa_node", "generated_mwh", "potential_mwh", "lost_curtailment_mwh",
            (F.col("grid_limit_mw").isNotNull()).alias("has_instruction"), "grid_limit_mw", "grid_reason",
            "instruction_id", "curtailed_readings", "readings",
            F.round("price_ars_mwh", 2).alias("spot_ars_mwh"), "spot_usd_mwh", "fx_ars_usd",
            F.round(F.col("lost_curtailment_mwh") * F.col("spot_usd_mwh"), 2).alias("lost_value_spot_usd"),
        )
    )


# =================================================== fact_maintenance_order
def build_fact_maintenance_order(spark: SparkSession, cfg: ProjectConfig) -> DataFrame:
    wo = spark.table(cfg.table("silver", "work_orders"))
    parts = spark.table(cfg.table("silver", "work_order_parts")).groupBy("order_id").agg(
        F.round(F.sum("line_cost_usd"), 2).alias("parts_cost_usd"), F.count("*").alias("part_lines"))
    dim_t = spark.table(cfg.table("gold", "dim_turbine")).where(f"turbine_key <> {UNKNOWN_KEY}")
    dim_i = spark.table(cfg.table("gold", "dim_inverter")).select("inverter_id", "inverter_key")
    dim_p = spark.table(cfg.table("gold", "dim_park")).select("park_code", "park_key", "travel_hours",
                                                              "turbine_manufacturer")
    dim_c = spark.table(cfg.table("gold", "dim_crew")).select("crew_id", "crew_key")
    fx = spark.table(cfg.table("gold", "dim_date")).select("date", "fx_ars_usd")
    hours = lambda a, b: F.round((F.unix_timestamp(b) - F.unix_timestamp(a)) / 3600, 2)  # noqa: E731
    f = (
        wo.withColumn("_ref_ts", F.coalesce("failure_ts", "created_ts"))
        .transform(lambda d: _pit_join(d, dim_t, "turbine_id", "asset_id", "_ref_ts", "turbine_key"))
        .join(F.broadcast(dim_i), F.col("asset_id") == F.col("inverter_id"), "left")
        .join(F.broadcast(dim_p), "park_code", "left")
        .join(F.broadcast(dim_c), "crew_id", "left")
        .join(parts, "order_id", "left")
        .withColumn("_close_date", F.to_date(F.from_utc_timestamp(F.coalesce("work_end_ts", "event_ts"),
                                                                  "America/Argentina/Buenos_Aires")))
        .join(F.broadcast(fx.withColumnRenamed("date", "_close_date")), "_close_date", "left")
    )
    labor_usd = F.round(F.try_divide(F.col("labor_cost_ars"), F.col("fx_ars_usd")), 2)
    total = (F.coalesce("parts_cost_usd", F.lit(0.0)) + F.coalesce(labor_usd, F.lit(0.0))
             + F.coalesce("crane_cost_usd", F.lit(0.0)) + F.coalesce("water_cost_usd", F.lit(0.0)))
    created_local = F.from_utc_timestamp("created_ts", "America/Argentina/Buenos_Aires")
    return f.select(
        "order_id", _date_key(F.to_date(created_local)).alias("created_date_key"),
        F.to_date(created_local).alias("created_date"),
        _date_key("_close_date").alias("closed_date_key"),
        F.coalesce("park_key", F.lit(UNKNOWN_KEY)).alias("park_key"), "turbine_key",
        F.coalesce("inverter_key", F.lit(UNKNOWN_KEY).cast("bigint")).alias("inverter_key"),
        F.coalesce("crew_key", F.lit(UNKNOWN_KEY).cast("bigint")).alias("crew_key"),
        "park_code", F.col("asset_id").alias("asset_id"), "asset_tag", "order_type", "severity", "component",
        "priority", "status", (F.col("status") != "CERRADA").alias("is_open"),
        "remote_reset", "failure_ts", "created_ts", "arrived_ts", "work_start_ts", "work_end_ts",
        hours("failure_ts", "arrived_ts").alias("response_hours"),
        F.col("travel_hours").alias("travel_hours_standard"), "access_delay_h",
        hours("arrived_ts", "work_start_ts").alias("waiting_hours"),
        hours("work_start_ts", "work_end_ts").alias("repair_hours"),
        hours(F.coalesce("failure_ts", "work_start_ts"), "work_end_ts").alias("downtime_hours"),
        "labor_hours", "labor_cost_ars", "fx_ars_usd", labor_usd.alias("labor_cost_usd"),
        F.coalesce("parts_cost_usd", F.lit(0.0)).alias("parts_cost_usd"), "part_lines", "crane_cost_usd",
        "water_m3", "water_cost_usd", F.round(total, 2).alias("total_cost_usd"),
        ((F.col("order_type") == "CORRECTIVA") & F.col("turbine_manufacturer").isNotNull()
         & ~F.col("remote_reset")).alias("is_warranty_relevant"),
        "notes",
    )


def load_fact_maintenance_order(spark: SparkSession, cfg: ProjectConfig) -> int:
    target = cfg.table("gold", "fact_maintenance_order")
    df = build_fact_maintenance_order(spark, cfg)
    create_table_if_not_exists(spark, target, df, cluster_by=["park_code", "created_date"],
                               comment="Órdenes de mantenimiento (accumulating snapshot: 1 fila por orden)")
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(target)
    return spark.table(target).count()


# ================================================== fact_availability_daily
def build_fact_availability_daily(spark: SparkSession, cfg: ProjectConfig, dates: list | None) -> DataFrame:
    t = spark.table(cfg.table("gold", "fact_turbine_10min"))
    if dates is not None:
        t = t.where(F.col("reading_date").isin(dates))
    dim_t = spark.table(cfg.table("gold", "dim_turbine")).where("is_current").select(
        "turbine_id", "commissioning_date", "manufacturer", "guaranteed_availability")
    h = lambda st: F.round(F.sum(F.when(F.col("state").isin(*st), 1).otherwise(0)) / 6, 2)  # noqa: E731
    d = (
        t.groupBy("date_key", "reading_date", "park_key", "park_code", "turbine_id")
        .agg(F.max("turbine_key").alias("turbine_key"), F.count("*").alias("readings"),
             h(["PRODUCIENDO"]).alias("producing_h"), h(["VIENTO_BAJO", "VIENTO_EXTREMO"]).alias("wind_out_of_range_h"),
             h(["FALLA"]).alias("fault_h"), h(["MANTENIMIENTO"]).alias("maintenance_h"), h(["HIELO"]).alias("icing_h"),
             h(["LIMITADA_RED"]).alias("curtailed_h"),
             F.round(F.sum("energy_kwh") / 1000, 3).alias("energy_mwh"),
             F.round(F.sum("potential_kwh") / 1000, 3).alias("potential_mwh"),
             F.round(F.sum("lost_fault_kwh") / 1000, 3).alias("lost_fault_mwh"),
             F.round(F.sum("lost_maintenance_kwh") / 1000, 3).alias("lost_maintenance_mwh"))
        .join(F.broadcast(dim_t), "turbine_id", "left")
    )
    period = F.lit(24.0)
    no_data = F.greatest(period - F.col("readings") / 6, F.lit(0.0))
    # Definición contractual (garantía del fabricante, estilo IEC 61400-26):
    #   excluidas = red (CAMMESA) + hielo (fuerza mayor climática) + mantenimiento programado + sin dato
    #   disponibilidad = 1 - horas de falla / (período - excluidas)
    excluded = F.col("curtailed_h") + F.col("icing_h") + F.col("maintenance_h") + no_data
    return d.select(
        "date_key", "reading_date", "park_key", "turbine_key", "park_code", "turbine_id", "manufacturer",
        "readings", F.round(no_data, 2).alias("no_data_h"), "producing_h", "wind_out_of_range_h", "fault_h",
        "maintenance_h", "icing_h", "curtailed_h", F.round(excluded, 2).alias("excluded_h"),
        F.round(F.try_divide(period - excluded - F.col("fault_h"), period - excluded), 5)
        .alias("availability_contractual"),
        F.round(F.try_divide(period - no_data - F.col("fault_h") - F.col("maintenance_h"), period - no_data), 5)
        .alias("availability_technical"),
        F.round(F.try_divide(F.col("energy_mwh"),
                             F.col("energy_mwh") + F.col("lost_fault_mwh") + F.col("lost_maintenance_mwh")), 5)
        .alias("availability_energy_based"),
        "energy_mwh", "potential_mwh", "lost_fault_mwh", "lost_maintenance_mwh", "guaranteed_availability",
    )


FACTS = [
    ("fact_turbine_10min", "scada_10min", "reading_date", build_fact_turbine_10min, ["reading_date", "park_code"],
     "Mediciones de aerogeneradores cada 10 min con potencial y descomposición de pérdidas"),
    ("fact_inverter_hourly", "inverter_5min", "reading_date", build_fact_inverter_hourly, ["reading_date", "park_code"],
     "Generación solar por inversor y hora, con energía esperada 'limpia' para estimar suciedad"),
]
DERIVED = [  # se alimentan de fact_turbine_10min (mismo watermark de silver.scada_10min)
    ("fact_curtailment_hourly", "scada_10min", "reading_date", build_fact_curtailment_hourly,
     ["reading_date", "park_code"], "Curtailment por parque y hora: energía perdida y su valor a precio spot"),
    ("fact_availability_daily", "scada_10min", "reading_date", build_fact_availability_daily,
     ["reading_date", "park_code"], "Disponibilidad diaria por turbina (contractual, técnica y por energía)"),
]


def load_facts(spark: SparkSession, cfg: ProjectConfig, full_refresh: bool = False) -> dict[str, int]:
    out = {}
    for name, src, date_col, builder, cluster, comment in FACTS + DERIVED:
        out[name] = _incremental(spark, cfg, name, src, date_col, "reading_date", builder, cluster, comment,
                                 full_refresh)
    out["fact_maintenance_order"] = load_fact_maintenance_order(spark, cfg)
    return out
