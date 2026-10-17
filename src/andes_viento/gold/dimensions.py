"""Dimensiones del modelo estrella (Kimball).

| dimensión     | tipo   | grano                         | de dónde sale                              |
|---------------|--------|-------------------------------|--------------------------------------------|
| dim_date      | SCD0   | 1 fila por día                | calendario + feriados AR + dólar BNA       |
| dim_park      | SCD1   | 1 fila por parque             | maestro de parques (seed) + activos CMMS   |
| dim_turbine   | SCD2   | 1 fila por versión de turbina | silver.assets_history (componentes/nombre) |
| dim_inverter  | SCD1   | 1 fila por inversor           | silver.assets_history vigente              |
| dim_weather   | SCD0   | 1 fila por parque y día       | silver.weather_hourly (observado + pron.)  |
| dim_contract  | SCD2   | 1 fila por versión de contrato| silver.contracts_history (adendas)         |
| dim_crew      | SCD1   | 1 fila por cuadrilla          | silver.crews                               |

Todas tienen una fila "desconocido" (clave -1): un hecho nunca pierde filas por una FK rota.
"""

from __future__ import annotations

from datetime import timedelta

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from andes_viento.config import ProjectConfig
from andes_viento.datagen import reference as R
from andes_viento.utils.delta import create_table_if_not_exists

UNKNOWN_KEY = -1
FAR_FUTURE = "9999-12-31 00:00:00"
MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
             "noviembre", "diciembre"]
DAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _write(spark: SparkSession, df: DataFrame, target: str, cluster_by: list[str], comment: str) -> int:
    create_table_if_not_exists(spark, target, df, cluster_by=cluster_by, comment=comment)
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(target)
    return spark.table(target).count()


def _arr(values) -> F.Column:
    return F.array(*[F.lit(v) for v in values])


# ===================================================================== fecha
def build_dim_date(spark: SparkSession, cfg: ProjectConfig) -> DataFrame:
    end = cfg.end_date + timedelta(days=400)  # margen para el job diario y para proyecciones
    hol = spark.createDataFrame([(d, n) for d, n in R.HOLIDAYS_AR.items()], "date date, holiday_name string")
    days = spark.sql(f"SELECT explode(sequence(DATE'{cfg.start_date}', DATE'{end}', INTERVAL 1 DAY)) AS date")
    fx_t = cfg.table("silver", "fx_rates")
    fx = (spark.table(fx_t).where("rate_type = 'BNA_VENDEDOR'").select(F.col("fx_date").alias("date"), "ars_per_usd")
          if spark.catalog.tableExists(fx_t) else spark.createDataFrame([], "date date, ars_per_usd double"))
    w = Window.orderBy("date").rowsBetween(Window.unboundedPreceding, 0)
    m = F.month("date")
    return (
        days.join(hol, "date", "left").join(fx, "date", "left")
        # el BNA no publica fines de semana ni feriados: vale la última cotización conocida
        .withColumn("fx_ars_usd", F.last("ars_per_usd", ignorenulls=True).over(w))
        .withColumn("fx_is_published", F.col("ars_per_usd").isNotNull())
        .select(
            F.date_format("date", "yyyyMMdd").cast("int").alias("date_key"), "date",
            F.year("date").alias("year"), F.quarter("date").alias("quarter"), m.alias("month"),
            F.element_at(_arr(MONTHS_ES), m).alias("month_name"),
            F.date_format("date", "yyyy-MM").alias("year_month"),
            F.trunc("date", "month").alias("month_start"),
            F.dayofmonth("date").alias("day"),
            F.weekday("date").alias("weekday_idx"),
            F.element_at(_arr(DAYS_ES), F.weekday("date") + 1).alias("day_name"),
            (F.weekday("date") >= 5).alias("is_weekend"),
            F.col("holiday_name").isNotNull().alias("is_holiday"), "holiday_name",
            ((F.weekday("date") < 5) & F.col("holiday_name").isNull()).alias("is_business_day"),
            F.when(m.isin(12, 1, 2), "verano").when(m.isin(3, 4, 5), "otoño").when(m.isin(6, 7, 8), "invierno")
            .otherwise("primavera").alias("season"),
            F.round("fx_ars_usd", 2).alias("fx_ars_usd"), "fx_is_published",
            F.dayofmonth(F.last_day("date")).alias("days_in_month"),
        )
    )


# ===================================================================== parque
def build_dim_park(spark: SparkSession, cfg: ProjectConfig) -> DataFrame:
    rows = []
    for i, p in enumerate(R.PARKS, start=1):
        m = R.MANUFACTURERS.get(p.manufacturer) if p.manufacturer else None
        base = R.BASES[p.base]
        rows.append((i, p.code, p.name, "Eólico" if p.tech == "WIND" else "Solar", p.tech, p.province, p.region,
                     p.lat, p.lon, p.altitude_m, p.commissioning, p.cammesa_node, p.cammesa_code, base[0], base[1],
                     p.distance_km, round(p.distance_km / 75 + 0.5, 1), p.link, p.park_manager,
                     m.name if m else None, m.guaranteed_availability if m else None,
                     m.ld_usd_per_point_mw if m else None, p.water_cost_usd_m3 or None, p.curtail_exposure))
    seed = spark.createDataFrame(rows, (
        "park_key int, park_code string, park_name string, technology string, tech_code string, province string, "
        "region string, latitude double, longitude double, altitude_m int, commissioning_date date, "
        "cammesa_node string, cammesa_agent_code string, maintenance_base string, base_city string, "
        "distance_to_base_km int, travel_hours double, comm_link string, park_manager string, "
        "turbine_manufacturer string, guaranteed_availability double, ld_usd_per_point_mw double, "
        "water_cost_usd_m3 double, grid_exposure double"))
    assets = spark.table(cfg.table("silver", "assets_history")).where("is_current AND NOT is_deleted")
    units = assets.groupBy("park_code").agg(
        F.count("*").alias("units"), F.round(F.sum("rated_kw") / 1000, 2).alias("installed_mw"),
        F.sum(F.coalesce("panels", F.lit(0))).alias("panels"),
        F.round(F.sum(F.coalesce("dc_kwp", F.lit(0.0))) / 1000, 2).alias("dc_mwp"))
    unknown = spark.createDataFrame([(UNKNOWN_KEY, "N/D", "Desconocido")], "park_key int, park_code string, park_name string")
    return seed.join(units, "park_code", "left").unionByName(unknown, allowMissingColumns=True)


# ================================================================== turbinas
def build_dim_turbine(spark: SparkSession, cfg: ProjectConfig) -> DataFrame:
    hist = spark.table(cfg.table("silver", "assets_history")).where("asset_type = 'WTG'")
    model_ref = spark.createDataFrame(
        [(m.model, m.code, m.rated_wind_ms, m.rotor_rpm_max, m.guaranteed_availability) for m in R.MANUFACTURERS.values()],
        "model string, manufacturer_code string, rated_wind_ms double, rotor_rpm_max double, guaranteed_availability double")
    w = Window.partitionBy("asset_id").orderBy("valid_from")
    prev = lambda c: F.lag(c).over(w)  # noqa: E731
    reason = (
        F.when(prev("asset_tag").isNull(), "ALTA")
        .when(F.col("is_deleted"), "BAJA")
        .when(prev("asset_tag") != F.col("asset_tag"), "RENOMBRE")
        .when((prev("gearbox_serial") != F.col("gearbox_serial")), "CAMBIO_MULTIPLICADORA")
        .when((prev("main_bearing_serial") != F.col("main_bearing_serial")), "CAMBIO_RODAMIENTO_PPAL")
        .when((prev("generator_serial") != F.col("generator_serial")), "CAMBIO_RODAMIENTO_GENERADOR")
        .when(prev("firmware") != F.col("firmware"), "ACTUALIZACION_FIRMWARE")
        .otherwise("OTRO")
    )
    dim = (
        hist.join(F.broadcast(model_ref), "model", "left")
        .withColumn("change_reason", reason)
        .withColumn("version", F.row_number().over(w))
        .select(
            F.xxhash64("asset_id", "valid_from").alias("turbine_key"),
            F.col("asset_id").alias("turbine_id"), F.col("asset_tag").alias("turbine_tag"), "park_code",
            "manufacturer", "manufacturer_code", "model", "rated_kw", "rated_wind_ms", "rotor_rpm_max",
            "gearbox_serial", "main_bearing_serial", "generator_serial", "firmware", "commissioning_date",
            "guaranteed_availability", "status", "change_reason", "version",
            F.col("valid_from").alias("effective_from"),
            F.coalesce("valid_to", F.lit(FAR_FUTURE).cast("timestamp")).alias("effective_to"),
            "is_current", "is_deleted",
        )
    )
    unknown = spark.createDataFrame([(UNKNOWN_KEY, "N/D", "N/D", "N/D")],
                                    "turbine_key bigint, turbine_id string, turbine_tag string, park_code string")
    unknown = unknown.withColumn("effective_from", F.lit("1900-01-01").cast("timestamp")) \
        .withColumn("effective_to", F.lit(FAR_FUTURE).cast("timestamp")).withColumn("is_current", F.lit(True))
    return dim.unionByName(unknown, allowMissingColumns=True)


def build_dim_inverter(spark: SparkSession, cfg: ProjectConfig) -> DataFrame:
    cur = spark.table(cfg.table("silver", "assets_history")).where("asset_type = 'INV' AND is_current")
    dim = cur.select(
        F.xxhash64("asset_id").alias("inverter_key"), F.col("asset_id").alias("inverter_id"),
        F.col("asset_tag").alias("inverter_tag"), "park_code", "manufacturer", "model", "rated_kw", "dc_kwp", "panels",
        "firmware", "commissioning_date", "status",
    )
    unknown = spark.createDataFrame([(UNKNOWN_KEY, "N/D", "N/D", "N/D")],
                                    "inverter_key bigint, inverter_id string, inverter_tag string, park_code string")
    return dim.unionByName(unknown, allowMissingColumns=True)


# ====================================================================== clima
def weather_key(park_code: F.Column, date_col: F.Column) -> F.Column:
    """Clave legible: yyyymmdd * 100 + índice del parque (ej.: 2025071509 = LEO el 15/07/2025)."""
    idx = F.element_at(F.create_map(*[x for i, p in enumerate(R.PARKS, start=1) for x in (F.lit(p.code), F.lit(i))]),
                       park_code)
    return (F.date_format(date_col, "yyyyMMdd").cast("bigint") * 100 + F.coalesce(idx, F.lit(0))).cast("bigint")


def build_dim_weather(spark: SparkSession, cfg: ProjectConfig) -> DataFrame:
    wx = spark.table(cfg.table("silver", "weather_hourly"))
    act = wx.where("kind = 'actual'").groupBy("park_code", F.col("valid_date").alias("date")).agg(
        F.round(F.avg("wind_ms_100m"), 2).alias("wind_avg_ms"), F.round(F.max("gust_ms"), 1).alias("gust_max_ms"),
        F.round(F.min("temp_c"), 1).alias("temp_min_c"), F.round(F.max("temp_c"), 1).alias("temp_max_c"),
        F.round(F.sum("precip_mm"), 1).alias("precip_mm"), F.round(F.sum("snow_cm"), 1).alias("snow_cm"),
        F.round(F.sum("ghi_wm2") / 1000, 2).alias("irradiation_kwh_m2"),
        F.round(F.avg("dust_aod"), 3).alias("dust_aod"),
        F.sum(F.when(F.col("ice_risk") == "HIGH", 1).otherwise(0)).alias("ice_risk_hours"),
    )
    fc = wx.where("kind = 'forecast'").groupBy("park_code", F.col("valid_date").alias("date")).agg(
        F.round(F.avg("wind_ms_100m"), 2).alias("forecast_wind_avg_ms"),
        F.round(F.sum("precip_mm"), 1).alias("forecast_precip_mm"),
        F.max("precip_prob_pct").alias("forecast_precip_prob_pct"))
    park = spark.createDataFrame([(p.code, p.tech) for p in R.PARKS], "park_code string, tech string")
    condition = (
        F.when(F.col("ice_risk_hours") >= 3, "Hielo")
        .when(F.col("snow_cm") > 1, "Nevada")
        .when((F.col("tech") == "SOLAR") & (F.col("dust_aod") > 0.13), "Polvo en suspensión")
        .when(F.col("precip_mm") > 2, "Lluvia")
        .when(F.col("gust_max_ms") > 30, "Viento extremo")
        .when((F.col("tech") == "WIND") & (F.col("wind_avg_ms") < 6), "Calma")
        .otherwise("Normal")
    )
    return (
        act.join(fc, ["park_code", "date"], "left").join(F.broadcast(park), "park_code", "left")
        .withColumn("weather_condition", condition)
        .withColumn("is_extreme", F.col("weather_condition").isin("Hielo", "Nevada", "Viento extremo"))
        .withColumn("forecast_wind_error_pct", F.round(F.try_divide(F.col("forecast_wind_avg_ms") - F.col("wind_avg_ms"),
                                                                    F.col("wind_avg_ms")) * 100, 1))
        .select(weather_key(F.col("park_code"), F.col("date")).alias("weather_key"), "park_code", "date",
                F.date_format("date", "yyyyMMdd").cast("int").alias("date_key"), "weather_condition", "is_extreme",
                "wind_avg_ms", "gust_max_ms", "temp_min_c", "temp_max_c", "precip_mm", "snow_cm",
                "irradiation_kwh_m2", "dust_aod", "ice_risk_hours", "forecast_wind_avg_ms", "forecast_wind_error_pct",
                "forecast_precip_mm", "forecast_precip_prob_pct")
        .unionByName(spark.createDataFrame([(UNKNOWN_KEY, "N/D", "Sin dato")],
                                           "weather_key bigint, park_code string, weather_condition string"),
                     allowMissingColumns=True)
    )


# ================================================================== contratos
def build_dim_contract(spark: SparkSession, cfg: ProjectConfig) -> DataFrame:
    hist = spark.table(cfg.table("silver", "contracts_history"))
    w = Window.partitionBy("contract_id").orderBy("valid_from")
    dim = hist.select(
        F.xxhash64("contract_id", "valid_from").alias("contract_key"), "contract_id", "client_name", "sector",
        "client_cuit", "contact_name", "contact_email", "contact_phone", "start_date", "end_date", "price_usd_mwh",
        "committed_mwh_month", "penalty_usd_mwh", "tolerance_pct",
        F.split("source_parks", r"\|").alias("source_parks"), "status",
        F.row_number().over(w).alias("version"),
        F.col("valid_from").alias("effective_from"),
        F.coalesce("valid_to", F.lit(FAR_FUTURE).cast("timestamp")).alias("effective_to"), "is_current", "is_deleted",
    )
    unknown = spark.createDataFrame([(UNKNOWN_KEY, "N/D", "Desconocido")],
                                    "contract_key bigint, contract_id string, client_name string")
    return dim.unionByName(unknown, allowMissingColumns=True)


def build_dim_crew(spark: SparkSession, cfg: ProjectConfig) -> DataFrame:
    crews = spark.table(cfg.table("silver", "crews"))
    base_name = F.element_at(F.create_map(*[x for k, v in R.BASES.items() for x in (F.lit(k), F.lit(v[0]))]), F.col("base"))
    dim = crews.select(F.xxhash64("crew_id").alias("crew_key"), "crew_id", "base", base_name.alias("base_name"),
                       "leader_name", "leader_phone", "members", "specialty")
    unknown = spark.createDataFrame([(UNKNOWN_KEY, "N/D", "Sin cuadrilla (reset remoto)")],
                                    "crew_key bigint, crew_id string, specialty string")
    return dim.unionByName(unknown, allowMissingColumns=True)


DIMENSIONS = {
    "dim_date": (build_dim_date, ["date"], "Calendario con feriados argentinos, estaciones australes y dólar BNA"),
    "dim_park": (build_dim_park, ["park_code"], "Parques eólicos y solares (1 fila por parque)"),
    "dim_turbine": (build_dim_turbine, ["turbine_id"], "Aerogeneradores SCD2: una versión por cambio de componente, "
                                                      "firmware o nombre"),
    "dim_inverter": (build_dim_inverter, ["inverter_id"], "Inversores solares centrales"),
    "dim_weather": (build_dim_weather, ["date", "park_code"], "Clima diario por parque (observado y pronóstico)"),
    "dim_contract": (build_dim_contract, ["contract_id"], "Contratos PPA del MATER SCD2 (adendas de precio y volumen)"),
    "dim_crew": (build_dim_crew, ["crew_id"], "Cuadrillas de mantenimiento"),
}


def load_dimensions(spark: SparkSession, cfg: ProjectConfig, names: list[str] | None = None) -> dict[str, int]:
    out = {}
    for name in names or list(DIMENSIONS):
        builder, cluster, comment = DIMENSIONS[name]
        out[name] = _write(spark, builder(spark, cfg), cfg.table("gold", name), cluster, comment)
    return out
