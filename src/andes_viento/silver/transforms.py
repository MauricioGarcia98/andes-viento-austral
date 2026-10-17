"""Transformaciones bronze -> silver: tipado, fechas, unidades, relojes y sensores.

Convención de fechas del proyecto (¡importante para Genie!):
  * columnas `*_ts` / `ts_utc`  -> TIMESTAMP en UTC (instante real),
  * columnas `*_local`          -> hora de pared argentina (UTC-3) para mostrar,
  * `reading_date` / `*_date`   -> DATE local (el "día operativo" del parque).

Las funciones son puras (DataFrame -> DataFrame) para poder testearlas una por una.
"""

from __future__ import annotations

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F

TZ = "America/Argentina/Buenos_Aires"
SLOT_S = 600

ISO_OFFSET = "yyyy-MM-dd'T'HH:mm:ssXXX"
ISO_Z = "yyyy-MM-dd'T'HH:mm:ss'Z'"
LOCAL_FORMATS = ("yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd'T'HH:mm:ss", "dd/MM/yyyy HH:mm:ss", "dd/MM/yyyy HH:mm",
                 "yyyy-MM-dd HH:mm", "dd/MM/yyyy", "yyyy-MM-dd")


def try_ts(col: Column | str, *formats: str) -> Column:
    c = F.col(col) if isinstance(col, str) else col
    return F.coalesce(*[F.try_to_timestamp(c, F.lit(f)) for f in formats])


def try_date(col: Column, fmt: str) -> Column:
    """`try_to_date` no existe en la API de Python: se arma con try_to_timestamp."""
    return F.to_date(F.try_to_timestamp(col, F.lit(fmt)))


def local_to_utc(col: Column | str, formats: tuple[str, ...] = LOCAL_FORMATS) -> Column:
    """Texto con hora local argentina (sin offset) -> instante UTC."""
    return F.to_utc_timestamp(try_ts(col, *formats), TZ)


def utc_to_local(col: Column | str) -> Column:
    return F.from_utc_timestamp(F.col(col) if isinstance(col, str) else col, TZ)


def local_date(col: Column | str) -> Column:
    return F.to_date(utc_to_local(col))


def ar_number(col: Column | str) -> Column:
    """'1.234.567,50' -> 1234567.5 (formato argentino)."""
    c = F.col(col) if isinstance(col, str) else col
    return (F.regexp_replace(F.regexp_replace(c, r"\.", ""), ",", ".")).try_cast("double")


def num(col: str) -> Column:
    return (F.col(col)).try_cast("double")


def op_flag(col: str = "op") -> Column:
    return (F.upper(F.trim(F.col(col))) == "D")


# =============================================================================
# SCADA
# =============================================================================
SCADA_SENSORS = ["wind_ms", "wind_dir_deg", "rotor_rpm", "pitch_deg", "gearbox_bearing_c", "main_bearing_c",
                 "generator_bearing_c", "nacelle_c", "ambient_c", "vibration_mm_s"]
DRIFT_SENSORS = ["ice_detector", "oil_particle_count", "tower_accel_mg"]
STUCK_CHECK = ["gearbox_bearing_c", "wind_ms", "vibration_mm_s"]
STUCK_RUN = 6  # 6 lecturas idénticas seguidas (1 hora) = sensor clavado


def _sensor(df: DataFrame, name: str) -> Column:
    fields = df.schema["sensors"].dataType.fieldNames() if "sensors" in df.columns else []
    return F.col(f"sensors.{name}").cast("double") if name in fields else F.lit(None).cast("double")


def parse_scada_time(df: DataFrame) -> DataFrame:
    """3 formatos según fabricante -> `device_ts` (UTC tal como lo cree el equipo)."""
    has_epoch = "ts_epoch_ms" in df.columns
    epoch = F.timestamp_millis(F.col("ts_epoch_ms").cast("long")) if has_epoch else F.lit(None).cast("timestamp")
    iso = F.try_to_timestamp(F.col("ts"), F.lit(ISO_OFFSET))
    dmy = F.to_utc_timestamp(F.try_to_timestamp(F.col("ts"), F.lit("dd/MM/yyyy HH:mm:ss")), TZ)
    return (
        df.withColumn("device_ts", F.coalesce(epoch, iso, dmy))
        .withColumn("ts_format", F.when(epoch.isNotNull(), "epoch_ms").when(iso.isNotNull(), "iso_offset")
                    .when(dmy.isNotNull(), "local_dmy"))
        .withColumn("received_ts", F.try_to_timestamp(F.col("received_at"), F.lit(ISO_Z)))
    )


def estimate_clock_offset(df: DataFrame) -> DataFrame:
    """Estima cuánto atrasa/adelanta el reloj de cada turbina, por día de recepción.

    El concentrador del parque sella `received_at` con hora de GPS (confiable). La demora
    normal es de segundos; los re-envíos satelitales llegan horas tarde. El percentil 5 de
    (recepción - hora del equipo) es la demora mínima: si da -3 h, el equipo cambió de huso;
    si da +7 min, el reloj atrasa. Sirve para los dos problemas con UN mismo método.
    """
    delta = F.unix_timestamp("received_ts") - F.unix_timestamp("device_ts")
    stats = (
        df.withColumn("_delta", delta)
        .withColumn("_recv_date", F.to_date("received_ts"))
        .groupBy("turbine", "_recv_date")
        .agg(F.percentile_approx("_delta", 0.05, 1000).alias("_p05"))
        .withColumn("clock_offset_s", F.when(F.abs(F.col("_p05")) >= 120,
                                             (F.round(F.col("_p05") / 60) * 60).cast("long")).otherwise(F.lit(0)))
    )
    return (
        df.withColumn("_recv_date", F.to_date("received_ts"))
        .join(F.broadcast(stats.drop("_p05")), ["turbine", "_recv_date"], "left")
        .drop("_recv_date")
        .withColumn("clock_offset_s", F.coalesce("clock_offset_s", F.lit(0)))
        .withColumn("tz_corrected", F.abs(F.col("clock_offset_s")) >= 3_000)
        .withColumn("clock_corrected", (F.col("clock_offset_s") != 0) & ~F.col("tz_corrected"))
        .withColumn("_corr_epoch", F.unix_timestamp("device_ts") + F.col("clock_offset_s"))
        # redondeo al slot de 10 minutos más cercano
        .withColumn("ts_utc", F.timestamp_seconds(F.round(F.col("_corr_epoch") / SLOT_S) * SLOT_S))
        .drop("_corr_epoch")
    )


def fix_power_units(df: DataFrame) -> DataFrame:
    """kW vs MW: si el equipo declara la unidad, se usa; si no, se infiere por magnitud y viento."""
    p, w = F.col("_power_raw"), F.col("wind_ms")
    rated_mw = F.col("rated_kw") / 1000
    unit = F.col("_power_unit")
    looks_mw = (((w >= 4) & (F.abs(p) < rated_mw * 1.6)) | ((w < 4) & (F.abs(p) < 0.05)))
    is_mw = F.when(unit == "MW", True).when(unit == "kW", False).otherwise(looks_mw & F.col("rated_kw").isNotNull())
    return (df.withColumn("unit_converted", F.coalesce(is_mw, F.lit(False)))
            .withColumn("power_kw", F.when(F.col("unit_converted"), p * 1000).otherwise(p)))


def null_impossible(df: DataFrame) -> DataFrame:
    """Valores físicamente imposibles -> NULL (y quedan contados en las reglas de calidad)."""
    return (
        df.withColumn("bad_values", F.array_compact(F.array(
            F.when((F.col("wind_ms") < 0) | (F.col("wind_ms") > 60), F.lit("wind_ms")),
            F.when(F.col("gearbox_bearing_c") > 200, F.lit("gearbox_bearing_c")),
            F.when(F.col("power_kw") > F.col("rated_kw") * 1.3, F.lit("power_kw")),
        )))
        .withColumn("wind_ms", F.when((F.col("wind_ms") < 0) | (F.col("wind_ms") > 60), None).otherwise(F.col("wind_ms")))
        .withColumn("gearbox_bearing_c", F.when(F.col("gearbox_bearing_c") > 200, None)
                    .otherwise(F.col("gearbox_bearing_c")))
        .withColumn("power_kw", F.when(F.col("power_kw") > F.col("rated_kw") * 1.3, None).otherwise(F.col("power_kw")))
    )


def flag_stuck_sensors(df: DataFrame, cols: list[str] = STUCK_CHECK, run: int = STUCK_RUN) -> DataFrame:
    """Un sensor "clavado" repite exactamente el mismo valor. Se detecta con lag() sobre la serie."""
    w = Window.partitionBy("asset_id").orderBy("ts_utc")
    flags = []
    for c in cols:
        same = [F.lag(c, k).over(w) == F.col(c) for k in range(1, run)]
        cond = same[0]
        for s in same[1:]:
            cond = cond & s
        flags.append(F.when(F.coalesce(cond, F.lit(False)), F.lit(c)))
    out = df.withColumn("stuck_sensors", F.array_compact(F.array(*flags)))
    for c in cols:
        out = out.withColumn(c, F.when(F.array_contains("stuck_sensors", c), None).otherwise(F.col(c)))
    return out


def clean_scada(df: DataFrame, tags: DataFrame) -> DataFrame:
    """bronze.scada_turbine -> silver.scada_10min (sin deduplicar todavía)."""
    base = parse_scada_time(df)
    sensors = [_sensor(df, s).alias(s) for s in SCADA_SENSORS + DRIFT_SENSORS]
    unit = (F.col("sensors.power_unit") if "power_unit" in df.schema["sensors"].dataType.fieldNames()
            else F.lit(None).cast("string"))
    base = base.select(
        "site", "turbine", "device_ts", "ts_format", "received_ts", "fw", F.col("status").cast("int").alias("status_code"),
        F.col("setpoint_kw").cast("double").alias("setpoint_kw"), "alarms", *sensors,
        F.col("sensors.active_power").cast("double").alias("_power_raw"), unit.alias("_power_unit"),
        "_rescued_data", "_source_file", "_ingested_at",
    )
    t = tags.select(F.col("asset_tag").alias("turbine"), "asset_id", "rated_kw", F.col("park_code"))
    out = estimate_clock_offset(base.join(F.broadcast(t), "turbine", "left"))
    out = null_impossible(fix_power_units(out))
    return (
        out.withColumn("ts_local", utc_to_local("ts_utc"))
        .withColumn("reading_date", F.to_date("ts_local"))
        .withColumn("latency_s", F.unix_timestamp("received_ts") - F.unix_timestamp("device_ts")
                    - F.col("clock_offset_s"))
        .withColumn("late_arrival", F.col("latency_s") > 3600)
        .withColumnRenamed("turbine", "turbine_tag")
        .drop("_power_raw", "_power_unit")
    )


def dedupe_first_arrival(df: DataFrame, keys: list[str], order_col: str) -> DataFrame:
    """Re-envíos satelitales: queda la PRIMERA copia que llegó."""
    w = Window.partitionBy(*keys).orderBy(F.col(order_col).asc_nulls_last())
    return df.withColumn("_rn", F.row_number().over(w)).where("_rn = 1").drop("_rn")


SCADA_COLUMNS = [
    "reading_date", "ts_utc", "ts_local", "asset_id", "park_code", "turbine_tag", "status_code", "setpoint_kw",
    "alarms", "wind_ms", "wind_dir_deg", "rotor_rpm", "power_kw", "pitch_deg", "gearbox_bearing_c",
    "main_bearing_c", "generator_bearing_c", "nacelle_c", "ambient_c", "vibration_mm_s", "ice_detector",
    "oil_particle_count", "tower_accel_mg", "fw", "ts_format", "received_ts", "latency_s", "late_arrival",
    "clock_offset_s", "clock_corrected", "tz_corrected", "unit_converted", "stuck_sensors", "bad_values",
    "_source_file", "_ingested_at",
]


# =============================================================================
# Inversores
# =============================================================================
def clean_inverter(df: DataFrame, tags: DataFrame) -> DataFrame:
    ts_utc = local_to_utc("timestamp", ("yyyy-MM-dd HH:mm", "dd/MM/yyyy HH:mm"))
    soiling = num("soiling_sensor_pct") if "soiling_sensor_pct" in df.columns else F.lit(None).cast("double")
    poa = num("poa_irradiance_wm2")
    ac = num("ac_power_kw")
    is_mw = (poa > 150) & (ac < 5) & (ac > 0)
    t = tags.select(F.col("asset_tag").alias("inverter"), "asset_id", "rated_kw", "dc_kwp")
    return (
        df.select(
            F.col("plant").alias("park_code"), "inverter", ts_utc.alias("ts_utc"),
            F.when(poa > 1_500, None).otherwise(F.greatest(poa, F.lit(0.0))).alias("poa_wm2"),
            num("module_temp_c").alias("module_temp_c"), num("ambient_temp_c").alias("ambient_temp_c"),
            num("dc_power_kw").alias("dc_power_kw"),
            F.when(is_mw, ac * 1000).otherwise(ac).alias("ac_power_kw"),
            F.coalesce(is_mw, F.lit(False)).alias("unit_converted"),
            (poa > 1_500).alias("poa_sentinel"),
            F.upper("status").alias("status"), soiling.alias("soiling_sensor_pct"),
            "ingest_date", "_source_file", "_ingested_at",
        )
        .join(F.broadcast(t), "inverter", "left")
        .withColumn("dc_power_kw", F.when(F.col("dc_power_kw") > F.col("dc_kwp") * 1.25, None)
                    .otherwise(F.col("dc_power_kw")))
        .withColumn("ts_local", utc_to_local("ts_utc"))
        .withColumn("reading_date", F.to_date("ts_local"))
        .withColumn("late_arrival", F.col("ingest_date") > F.col("reading_date"))
        .withColumnRenamed("inverter", "inverter_tag")
        .drop("rated_kw", "dc_kwp")
    )


# =============================================================================
# CMMS
# =============================================================================
ASSET_TRACKED = ["asset_tag", "park_code", "manufacturer", "model", "rated_kw", "dc_kwp", "panels", "gearbox_serial",
                 "main_bearing_serial", "generator_serial", "firmware", "status"]


def clean_assets(df: DataFrame) -> DataFrame:
    return df.select(
        F.trim("asset_id").alias("asset_id"), F.upper(F.trim("asset_tag")).alias("asset_tag"),
        F.upper("asset_type").alias("asset_type"), F.upper("park_code").alias("park_code"),
        F.trim("manufacturer").alias("manufacturer"), F.trim("model").alias("model"),
        num("rated_kw").alias("rated_kw"), num("dc_kwp").alias("dc_kwp"),
        (F.col("panels")).try_cast("int").alias("panels"),
        "gearbox_serial", "main_bearing_serial", "generator_serial", "firmware",
        try_date(F.col("commissioning_date"), "yyyy-MM-dd").alias("commissioning_date"),
        F.upper("status").alias("status"),
        local_to_utc("updated_at").alias("updated_at"),
        op_flag().alias("is_deleted"),
        "_ingested_at",
    )


def clean_crews(df: DataFrame) -> DataFrame:
    return df.select(
        "crew_id", F.upper("base").alias("base"), F.trim("leader_name").alias("leader_name"),
        F.trim("leader_phone").alias("leader_phone"), (F.col("members")).try_cast("int").alias("members"),
        "specialty", local_to_utc("updated_at").alias("updated_at"), op_flag().alias("is_deleted"), "_ingested_at",
    )


def clean_work_orders(df: DataFrame, tags: DataFrame) -> DataFrame:
    ts = lambda c: local_to_utc(c) if c in df.columns else F.lit(None).cast("timestamp")  # noqa: E731
    t = tags.select("asset_tag", "asset_id")
    cols = df.columns
    opt = lambda c, typ="double": F.col(c).cast(typ) if c in cols else F.lit(None).cast(typ)  # noqa: E731
    return (
        df.select(
            "order_id", F.upper("op").alias("op"), ts("event_ts").alias("event_ts"), "status",
            F.upper("asset_tag").alias("asset_tag"), "park_code", "order_type", "severity", "component",
            F.col("priority").cast("int").alias("priority"), ts("failure_at").alias("failure_ts"),
            ts("created_at").alias("created_ts"), ts("arrived_at").alias("arrived_ts"),
            ts("work_start").alias("work_start_ts"), ts("work_end").alias("work_end_ts"), "crew_id",
            F.coalesce(opt("remote_reset", "boolean"), F.lit(False)).alias("remote_reset"),
            opt("travel_km", "int").alias("travel_km"), opt("access_delay_h").alias("access_delay_h"),
            opt("labor_hours").alias("labor_hours"), opt("labor_cost_ars").alias("labor_cost_ars"),
            (F.col("parts") if "parts" in cols else F.lit(None)).alias("parts"),
            opt("crane_cost_usd").alias("crane_cost_usd"), opt("water_m3").alias("water_m3"),
            opt("water_cost_usd").alias("water_cost_usd"), "notes", "_ingested_at",
        )
        .join(F.broadcast(t), "asset_tag", "left")
        .withColumn("is_deleted", F.col("op") == "D")
    )


def explode_parts(orders: DataFrame) -> DataFrame:
    return (
        orders.where(F.col("parts").isNotNull())
        .select("order_id", F.posexplode("parts").alias("line", "p"))
        .select("order_id", (F.col("line") + 1).alias("line_no"), "p.part_code", "p.description",
                F.col("p.qty").cast("int").alias("qty"), F.col("p.unit_cost_usd").cast("double").alias("unit_cost_usd"))
        .withColumn("line_cost_usd", F.col("qty") * F.col("unit_cost_usd"))
    )


# =============================================================================
# CAMMESA, mercado y Finanzas
# =============================================================================
def clean_dispatch(df: DataFrame) -> DataFrame:
    return df.select(
        "instruction_id", F.col("version").cast("int").alias("version"), "agent_code", "node",
        F.try_to_timestamp(F.col("issued_at"), F.lit(ISO_OFFSET)).alias("issued_ts"),
        F.try_to_timestamp(F.col("valid_from"), F.lit(ISO_OFFSET)).alias("valid_from_ts"),
        F.try_to_timestamp(F.col("valid_to"), F.lit(ISO_OFFSET)).alias("valid_to_ts"),
        F.col("limit_mw").cast("double").alias("limit_mw"), "reason", "status", "_ingested_at",
    )


def clean_spot_prices(df: DataFrame) -> DataFrame:
    """HORA 1..24 de CAMMESA: la hora 1 es 00:00-01:00 y la 24 es 23:00-24:00."""
    day = F.try_to_timestamp(F.col("FECHA"), F.lit("dd/MM/yyyy"))
    hour = (F.col("HORA")).try_cast("int")
    local = day + F.make_interval(hours=hour - 1)
    return df.select(
        F.upper("NODO").alias("node"), F.to_utc_timestamp(local, TZ).alias("hour_ts"),
        local.alias("hour_local"), F.to_date(day).alias("price_date"), hour.alias("cammesa_hour"),
        ar_number("PRECIO_ARS_MWH").alias("price_ars_mwh"), F.upper("TIPO").alias("price_type"),
        F.when(F.upper("TIPO") == "DEFINITIVO", 2).otherwise(1).alias("version_rank"), "_ingested_at",
    )


def clean_fx(df: DataFrame) -> DataFrame:
    return df.select(
        try_date(F.col("FECHA"), "dd/MM/yyyy").alias("fx_date"), F.upper("MONEDA").alias("currency"),
        F.upper("TIPO").alias("rate_type"), ar_number("VALOR").alias("ars_per_usd"), "_ingested_at",
    )


def clean_budget(df: DataFrame) -> DataFrame:
    return df.select(
        (F.col("anio")).try_cast("int").alias("year"), (F.col("mes")).try_cast("int").alias("month"),
        F.upper("parque").alias("park_code"), "version",
        num("energia_p50_mwh").alias("budget_p50_mwh"), num("energia_p90_mwh").alias("budget_p90_mwh"),
        num("disponibilidad_supuesta").alias("assumed_availability"),
        num("curtailment_supuesto").alias("assumed_curtailment"),
        try_date(F.col("publicado"), "yyyy-MM-dd").alias("published_date"), "_ingested_at",
    ).withColumn("month_start", F.make_date("year", "month", F.lit(1)))


CONTRACT_TRACKED = ["client_name", "sector", "client_cuit", "contact_name", "contact_email", "contact_phone",
                    "start_date", "end_date", "price_usd_mwh", "committed_mwh_month", "penalty_usd_mwh",
                    "tolerance_pct", "source_parks", "status"]


def clean_contracts(df: DataFrame) -> DataFrame:
    return df.select(
        "contract_id", F.trim("client_name").alias("client_name"), "sector",
        F.regexp_replace("client_cuit", r"[^0-9-]", "").alias("client_cuit"),
        F.initcap(F.trim("contact_name")).alias("contact_name"), F.lower(F.trim("contact_email")).alias("contact_email"),
        "contact_phone",
        try_date(F.col("start_date"), "yyyy-MM-dd").alias("start_date"),
        try_date(F.col("end_date"), "yyyy-MM-dd").alias("end_date"),
        num("price_usd_mwh").alias("price_usd_mwh"), num("committed_mwh_month").alias("committed_mwh_month"),
        num("penalty_usd_mwh").alias("penalty_usd_mwh"), num("tolerance_pct").alias("tolerance_pct"),
        "source_parks", F.upper("status").alias("status"),
        local_to_utc("updated_at").alias("updated_at"), op_flag().alias("is_deleted"), "_ingested_at",
    )


def clean_weather(df: DataFrame) -> DataFrame:
    d = lambda c: F.col(c).cast("double") if c in df.columns else F.lit(None).cast("double")  # noqa: E731
    return df.select(
        F.upper("park_code").alias("park_code"), F.lower("kind").alias("kind"),
        F.try_to_timestamp(F.col("issued_at"), F.lit(ISO_OFFSET)).alias("issued_ts"),
        F.try_to_timestamp(F.col("valid_time"), F.lit(ISO_Z)).alias("valid_ts"),
        d("wind_ms_100m").alias("wind_ms_100m"), d("gust_ms").alias("gust_ms"), d("wind_dir_deg").alias("wind_dir_deg"),
        d("temp_c").alias("temp_c"), d("rh_pct").alias("rh_pct"), d("precip_mm").alias("precip_mm"),
        d("snow_cm").alias("snow_cm"), d("ghi_wm2").alias("ghi_wm2"), d("cloud_pct").alias("cloud_pct"),
        d("dust_aod").alias("dust_aod"), F.upper("ice_risk").alias("ice_risk"),
        d("precip_prob_pct").alias("precip_prob_pct"), "_ingested_at",
    ).withColumn("valid_date", local_date("valid_ts"))
