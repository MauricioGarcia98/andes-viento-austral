"""Generadores de las 11 fuentes de Andes Viento Austral.

Dos familias:
  * GRANDES y distribuidas (SCADA, inversores, clima horario): `spark.range()` x flota,
    todo con expresiones de columna y `xxhash64` (determinístico a cualquier escala).
  * CHICAS (CMMS, CAMMESA, contratos, dólar, presupuesto): se arman en el driver a partir
    de las tablas guía de `events.py` y se convierten a DataFrame.

Cada generador devuelve un DataFrame con la columna `ingest_date` (el día en que el
archivo LLEGA a landing, que no siempre es el día del dato: ahí viven los datos tardíos).

"Suciedad" inyectada a propósito (y dónde la resuelve silver):
  SCADA      relojes desfasados, huso horario cambiado (PAM 2024), 3 formatos de fecha según
             fabricante, potencia en MW o kW, sensores clavados, nulos, valores imposibles,
             huecos satelitales (perdidos o re-enviados tarde), duplicados, turbinas renombradas,
             sensores nuevos desde 2025 (schema drift en el JSON).
  Inversores CSV con 2 formatos de fecha, potencia en MW en una columna "kW" (FIA), exportes
             tardíos y repetidos, columna nueva en 2025.
  CMMS       CDC (I/U/D) con imagen completa, fechas en formato viejo antes de la migración.
  CAMMESA    hora 1..24, decimales con coma, versiones PRELIMINAR/DEFINITIVO, instrucciones
             corregidas y anuladas.
"""

from __future__ import annotations

import contextlib
from collections import defaultdict
from datetime import date, datetime, timedelta

from pyspark.sql import Column, DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T

from andes_viento.config import ProjectConfig
from andes_viento.datagen import events as E
from andes_viento.datagen import physics as ph
from andes_viento.datagen import reference as R
from andes_viento.datagen.rand import prng, uniform

ART_S = ph.ART_OFFSET_S
ART = E.ART


def _set_utc(spark: SparkSession) -> None:
    """Todas las fechas se formatean en UTC: así el resultado no depende del workspace."""
    with contextlib.suppress(Exception):  # algunos entornos no lo permiten
        spark.conf.set("spark.sql.session.timeZone", "UTC")


def _date_of(epoch: Column) -> Column:
    return F.date_from_unix_date(F.floor(epoch / 86_400).cast("int"))


def _fmt(epoch: Column, pattern: str) -> Column:
    return F.date_format(F.timestamp_seconds(epoch), pattern)


def _ts_local_str(d: datetime | int, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    if isinstance(d, int):
        d = datetime.fromtimestamp(d, tz=ART)
    return d.strftime(fmt)


def _ar_number(col: Column, decimals: int = 2) -> Column:
    """1234567.5 -> '1.234.567,50' (formato argentino: punto de miles, coma decimal)."""
    return F.translate(F.format_number(col, decimals), ",.", ".,")


def _array_of_structs(spark: SparkSession, rows: list[dict], key: str, fields: list[tuple[str, T.DataType]],
                      key_alias: str) -> DataFrame:
    """Agrupa filas chicas por clave en un array<struct>: se une por broadcast a la tabla grande."""
    grouped: dict[str, list[tuple]] = defaultdict(list)
    for r in rows:
        grouped[r[key]].append(tuple(r[f] for f, _ in fields))
    struct = T.StructType([T.StructField(f, t) for f, t in fields])
    schema = T.StructType([T.StructField(key_alias, T.StringType()), T.StructField("items", T.ArrayType(struct))])
    return spark.createDataFrame([(k, v) for k, v in grouped.items()], schema)


def _first_active(items: str, epoch: Column, start: str = "start", end: str = "end") -> Column:
    arr = F.coalesce(F.col(items), F.array())
    return F.try_element_at(F.filter(arr, lambda e: (epoch >= e[start]) & (epoch < e[end])), F.lit(1))


def _maybe_null(c: Column, *keys: Column | str, salt: str, p: float) -> Column:
    return F.when(uniform(*keys, salt=salt) < p, F.lit(None)).otherwise(c)


def _range_partitions(n_days: int, n_units: int) -> int:
    return max(4, int(n_days * n_units / 2_000))


# =============================================================================
# SCADA de aerogeneradores (10 minutos, JSON)
# =============================================================================
def _turbines_df(spark: SparkSession, cfg: ProjectConfig) -> DataFrame:
    rows = []
    units = E.park_units(cfg)
    for u in E.fleet(cfg, "WTG"):
        m = R.MANUFACTURERS[u.manufacturer]
        rows.append((u.asset_id, u.park, u.idx, u.tag, u.new_tag, u.manufacturer, u.rated_kw, m.rated_wind_ms,
                     m.rotor_rpm_max, u.wake, E.local_epoch(u.commissioning), units[u.park],
                     R.PARKS_BY_CODE[u.park].link))
    schema = ("asset_id string, park string, idx int, tag string, new_tag string, mfr string, rated_kw double, "
              "rated_ms double, rpm_max double, wake double, comm_epoch long, park_units int, link string")
    return spark.createDataFrame(rows, schema)


def _weather_days_df(spark: SparkSession, cfg: ProjectConfig, end: date) -> DataFrame:
    rows = [(r["park"], r["date"], r["wind_mult"], r["temp_anom"], r["precip_mm"], r["snow_cm"], r["rh_pct"],
             r["cloud"], r["ice_start_h"], r["ice_end_h"]) for r in E.park_days(cfg, end)]
    schema = ("park string, date_local date, wind_mult double, temp_anom double, precip_mm double, "
              "snow_cm double, rh_pct double, cloud double, ice_start_h int, ice_end_h int")
    return spark.createDataFrame(rows, schema)


def _alarm_for(mfr: str | None, kind: str, component: str) -> str:
    if mfr is None:
        return f"INV-{component[:4]}"
    codes = R.ALARM_CODES[mfr]
    if kind == "PREVENTIVE":
        return "SVC-100"
    return codes.get(component, codes["MINOR"])


def generate_scada_turbine(spark: SparkSession, cfg: ProjectConfig, start: date, end: date) -> DataFrame:
    _set_utc(spark)
    gen_from = max(cfg.start_date, start - timedelta(days=2))  # re-envíos que llegan días después
    tur = _turbines_df(spark, cfg)
    mfr_of = {u.asset_id: u.manufacturer for u in E.fleet(cfg, "WTG")}
    ev_rows = [dict(e, alarm=_alarm_for(mfr_of.get(e["asset_id"]), e["kind"], e["component"]))
               for e in E.downtime_events(cfg, end) if e["asset_type"] == "WTG"]
    L = T.LongType()
    events = _array_of_structs(spark, ev_rows, "asset_id", [("kind", T.StringType()), ("component", T.StringType()),
                               ("start", L), ("end", L), ("degrade_start", L), ("alarm", T.StringType())], "ev_asset")
    units = E.park_units(cfg)
    curt_rows = [dict(c, setpoint_kw=c["limit_mw"] * 1000 / units[c["park"]])
                 for c in E.curtailment_instructions(cfg, end)]
    curt = _array_of_structs(spark, curt_rows, "park", [("start", L), ("end", L), ("setpoint_kw", T.DoubleType())],
                             "cu_park")
    comm = _array_of_structs(spark, E.comm_outages(cfg, end), "park",
                             [("start", L), ("end", L), ("buffered", T.BooleanType())], "co_park")
    skew = _array_of_structs(spark, E.clock_skews(cfg, end), "asset_id",
                             [("start", L), ("end", L), ("offset_s", L)], "sk_asset")
    stuck = _array_of_structs(spark, E.stuck_sensors(cfg, end), "asset_id",
                              [("sensor", T.StringType()), ("start", L), ("end", L), ("value", T.DoubleType())],
                              "st_asset")
    wx = _weather_days_df(spark, cfg, end)

    t0, t1 = E.local_epoch(gen_from), E.local_epoch(end + timedelta(days=1))
    n_parts = _range_partitions((end - gen_from).days + 1, len(E.fleet(cfg, "WTG")))
    slots = spark.range(t0 // 600, t1 // 600, 1, n_parts).select((F.col("id") * 600).alias("epoch"))
    df = (
        slots.crossJoin(F.broadcast(tur))
        .where(F.col("epoch") >= F.col("comm_epoch"))
        .withColumn("local", F.col("epoch") - ART_S)
        .withColumn("date_local", _date_of(F.col("local")))
        .withColumn("hour_local", F.pmod(F.col("local"), F.lit(86_400)) / 3600.0)
        .withColumn("month_local", F.month("date_local"))
        .withColumn("doy", F.dayofyear("date_local"))
        .join(F.broadcast(wx), ["park", "date_local"], "left")
        .join(F.broadcast(events), F.col("asset_id") == F.col("ev_asset"), "left").withColumnRenamed("items", "ev")
        .join(F.broadcast(curt), F.col("park") == F.col("cu_park"), "left").withColumnRenamed("items", "cu")
        .join(F.broadcast(comm), F.col("park") == F.col("co_park"), "left").withColumnRenamed("items", "co")
        .join(F.broadcast(skew), F.col("asset_id") == F.col("sk_asset"), "left").withColumnRenamed("items", "sk")
        .join(F.broadcast(stuck), F.col("asset_id") == F.col("st_asset"), "left").withColumnRenamed("items", "st")
    )
    e = F.col("epoch")
    u = lambda salt: uniform("asset_id", "epoch", salt=salt)  # noqa: E731
    df = (
        df.withColumn("wind_true", ph.wind_by_park_col(F.col("park"), e.cast("double"), F.col("month_local"),
                                                       F.col("hour_local"), F.col("wind_mult"), F.col("wake"),
                                                       u("turb")))
        .withColumn("potential_kw", ph.power_kw_col(F.col("wind_true"), F.col("rated_kw"), F.col("rated_ms")))
        .withColumn("down", _first_active("ev", e))
        .withColumn("degr", F.try_element_at(F.filter(F.coalesce(F.col("ev"), F.array()), lambda x: (
            (x["kind"] == "MAJOR_FAILURE") & x["degrade_start"].isNotNull()
            & (e >= x["degrade_start"]) & (e < x["start"]))), F.lit(1)))
        .withColumn("progress", F.when(F.col("degr").isNotNull(),
                                       (e - F.col("degr.degrade_start"))
                                       / (F.col("degr.start") - F.col("degr.degrade_start"))).otherwise(F.lit(0.0)))
        .withColumn("degr_comp", F.col("degr.component"))
        .withColumn("setpoint_kw", _first_active("cu", e)["setpoint_kw"])
        .withColumn("outage", _first_active("co", e))
        .withColumn("offset_s", F.coalesce(_first_active("sk", e)["offset_s"], F.lit(0).cast("long")))
        .withColumn("stuck", _first_active("st", e))
        .withColumn("icing", F.col("ice_start_h").isNotNull() & (F.col("hour_local") >= F.col("ice_start_h"))
                    & (F.col("hour_local") < F.col("ice_end_h")))
    )
    kind = F.col("down.kind")
    status = (
        F.when(kind.isin("MAJOR_FAILURE", "MINOR_FAULT"), 1)
        .when(kind == "PREVENTIVE", 2)
        .when(F.col("icing"), 3)
        .when(F.col("wind_true") >= ph.CUT_OUT_MS, 6)
        .when(F.col("wind_true") < ph.CUT_IN_MS, 5)
        .when(F.col("setpoint_kw").isNotNull() & (F.col("potential_kw") > F.col("setpoint_kw")), 4)
        .otherwise(0)
    )
    df = df.withColumn("status", status)
    running = F.col("status").isin(0, 4)
    power = (
        F.when(running, F.least(F.col("potential_kw"), F.coalesce(F.col("setpoint_kw"), F.lit(1e9)))
               * (1 + 0.03 * (u("pw") - 0.5)))
        .when(F.col("status").isin(5, 6), -(2 + 6 * u("aux")))
        .otherwise(-(5 + 10 * u("aux")))
    )
    p2 = F.col("progress") * F.col("progress")
    p3 = p2 * F.col("progress")
    comp = F.col("degr_comp")
    df = (
        df.withColumn("power_kw", power)
        .withColumn("load", F.greatest(F.col("power_kw"), F.lit(0.0)) / F.col("rated_kw"))
        .withColumn("rpm", F.when(running, ph.rotor_rpm_col(F.col("wind_true"), F.col("rpm_max"), F.col("rated_ms"))
                                  * F.when(F.col("status") == 4, 0.85).otherwise(1.0))
                    .otherwise(0.3 * u("rpm")))
        .withColumn("ambient", ph.temp_c_col(F.col("park"), F.col("doy"), F.col("hour_local"), F.col("temp_anom")))
        .withColumn("gearbox_bearing_c", F.when(running, F.col("ambient") + 28 + 30 * F.col("load")
                                                + 2 * (u("t1") - 0.5) + F.when(comp == "GEARBOX", 16 * p2)
                                                .when(comp == "MAIN_BEARING", 4 * p2).otherwise(0.0))
                    .otherwise(F.col("ambient") + 4 + 3 * u("t1")))
        .withColumn("main_bearing_c", F.when(running, F.col("ambient") + 14 + 18 * F.col("load")
                                             + 2 * (u("t2") - 0.5) + F.when(comp == "MAIN_BEARING", 18 * p2)
                                             .otherwise(0.0))
                    .otherwise(F.col("ambient") + 3 + 2 * u("t2")))
        .withColumn("generator_bearing_c", F.when(running, F.col("ambient") + 32 + 30 * F.col("load")
                                                  + 2 * (u("t3") - 0.5)
                                                  + F.when(comp == "GENERATOR_BEARING", 20 * p2).otherwise(0.0))
                    .otherwise(F.col("ambient") + 5 + 3 * u("t3")))
        .withColumn("vibration_mm_s", F.when(running, 1.1 + 1.9 * F.col("rpm") / F.col("rpm_max")
                                             + 0.3 * (u("vb") - 0.5)
                                             + F.when(comp == "GEARBOX", 3.5 * p3)
                                             .when(comp == "MAIN_BEARING", 4.0 * p3)
                                             .when(comp == "GENERATOR_BEARING", 2.0 * p3).otherwise(0.0))
                    .otherwise(0.15 + 0.1 * u("vb")))
        .withColumn("wind_ms", F.col("wind_true") * (1 + 0.02 * (u("an") - 0.5)))
    )
    # ------------------------------------------------------------- sensores clavados
    for sensor in E.STUCK_SENSORS:
        df = df.withColumn(sensor, F.when(F.col("stuck.sensor") == sensor, F.col("stuck.value"))
                           .otherwise(F.col(sensor)))
    # ------------------------------------------------------------- comunicación y relojes
    latency = F.when(F.col("link") == "VSAT", 15 + 105 * u("lat")).otherwise(2 + 18 * u("lat"))
    df = (
        df.where(F.col("outage").isNull() | F.col("outage.buffered"))
        .withColumn("recv_epoch", F.when(F.col("outage").isNotNull(),
                                         F.col("outage.end") + 30 + 570 * u("buf") + (e - F.col("outage.start")) / 60)
                    .otherwise(e + latency).cast("long"))
        .withColumn("copies", F.when(u("dup") < 0.004, F.array(F.lit(0), F.lit(1))).otherwise(F.array(F.lit(0))))
        .withColumn("copy", F.explode("copies"))
        .withColumn("recv_epoch", F.when(F.col("copy") == 1, F.col("recv_epoch") + (3600 * (1 + 29 * u("rt"))).cast("long"))
                    .otherwise(F.col("recv_epoch")))
        .withColumn("ingest_date", _date_of(F.col("recv_epoch") - ART_S))
        .where((F.col("ingest_date") >= F.lit(start)) & (F.col("ingest_date") <= F.lit(end)))
        .withColumn("device_epoch", e + F.col("offset_s"))
        .withColumn("device_date", _date_of(F.col("device_epoch") - ART_S))
    )
    return _scada_payload(df)


def _scada_payload(df: DataFrame) -> DataFrame:
    """Arma el JSON tal cual lo manda cada fabricante (cada uno a su manera)."""
    u = lambda salt: uniform("asset_id", "epoch", F.col("copy"), salt=salt)  # noqa: E731
    mfr, dev = F.col("mfr"), F.col("device_epoch")
    drift_mfr, drift_date, _ = R.SCHEMA_DRIFT_SCADA
    tz_park, tz_date = R.TZ_SWITCH
    ren_park, ren_date = R.TURBINE_RENAME
    pei_fw_date = date(2024, 2, 1)
    drift = (mfr == drift_mfr) & (F.col("device_date") >= F.lit(drift_date))
    pei_utc = (F.col("park") == tz_park) & (F.col("device_date") >= F.lit(tz_date))
    tag = (F.when(F.col("new_tag").isNotNull() & (F.col("device_date") >= F.lit(ren_date))
                  # dos turbinas siguieron mandando el nombre viejo un mes y medio (nadie actualizó el PLC)
                  & ~(F.col("idx").isin(2, 4) & (F.col("device_date") < F.lit(date(2024, 7, 15)))),
                  F.col("new_tag")).otherwise(F.col("tag")))
    fw = (F.when(mfr == "AWS", F.lit("AW-FW 8.2.1"))
          .when(mfr == "HTW", F.when(drift, F.lit("HT-OS 5.0")).otherwise(F.lit("HT-OS 4.1")))
          .otherwise(F.when(F.col("device_date") >= F.lit(pei_fw_date), F.lit("PEI-CTL 2.4"))
                     .otherwise(F.lit("PEI-CTL 2.3"))))
    ts = (F.when(mfr == "AWS", F.concat(_fmt(dev - ART_S, "yyyy-MM-dd'T'HH:mm:ss"), F.lit("-03:00")))
          .when(mfr == "PEI", _fmt(F.when(pei_utc, dev).otherwise(dev - ART_S), "dd/MM/yyyy HH:mm:ss")))
    # potencia: PEI la manda en MW; con valores imposibles ocasionales (picos de 1,5x la nominal)
    power_kw = F.when(u("spk") < 0.0002, F.col("rated_kw") * 1.5).otherwise(F.col("power_kw"))
    active_power = F.when(mfr == "PEI", F.round(power_kw / 1000, 4)).otherwise(F.round(power_kw, 1))
    power_unit = (F.when(mfr == "AWS", F.lit("kW"))
                  .when((mfr == "PEI") & (F.col("device_date") >= F.lit(pei_fw_date)), F.lit("MW")))

    def sensor(name: str, value: Column, digits: int, p_null: float = 0.004) -> Column:
        return _maybe_null(F.round(value, digits), "asset_id", "epoch", salt=f"n_{name}", p=p_null).alias(name)

    wind = F.when(u("ws9") < 0.0005, F.lit(99.9)).otherwise(F.col("wind_ms"))  # código de error del anemómetro
    gbx = F.when(u("gb9") < 0.0003, F.lit(999.0)).otherwise(F.col("gearbox_bearing_c"))
    sensors = F.struct(
        sensor("wind_ms", wind, 2),
        sensor("wind_dir_deg", F.pmod(265 + 40 * F.sin(F.col("epoch") / 86_400.0) + 30 * (u("wd") - 0.5),
                                      F.lit(360.0)), 0),
        sensor("rotor_rpm", F.col("rpm"), 2),
        _maybe_null(active_power, "asset_id", "epoch", salt="n_pw", p=0.003).alias("active_power"),
        power_unit.alias("power_unit"),
        sensor("pitch_deg", F.when(F.col("status").isin(0, 4), F.when(F.col("status") == 4, 8 + 10 * u("pt"))
                                   .otherwise(2 * u("pt"))).otherwise(86 + 3 * u("pt")), 1),
        sensor("gearbox_bearing_c", gbx, 1),
        sensor("main_bearing_c", F.col("main_bearing_c"), 1),
        sensor("generator_bearing_c", F.col("generator_bearing_c"), 1),
        sensor("nacelle_c", F.col("ambient") + 10 + 6 * F.col("load"), 1),
        sensor("ambient_c", F.col("ambient"), 1),
        sensor("vibration_mm_s", F.col("vibration_mm_s"), 3),
        # --- schema drift: el firmware HT-OS 5.0 agrega 3 sensores desde marzo 2025
        F.when(drift, F.col("icing").cast("int")).alias("ice_detector"),
        F.when(drift, F.round(1_200 + 300 * u("oil") + F.when(F.col("degr_comp") == "GEARBOX",
                                                               9_000 * F.col("progress") ** 2).otherwise(0.0), 0)
               .cast("int")).alias("oil_particle_count"),
        F.when(drift, F.round(20 + 30 * F.col("rpm") / F.col("rpm_max") + 5 * u("acc"), 1)).alias("tower_accel_mg"),
    )
    alarms = F.array_compact(F.array(
        F.when(F.col("status") == 1, F.col("down.alarm")),
        F.when(F.col("status") == 2, F.col("down.alarm")),
        F.when(F.col("status") == 3, F.element_at(F.create_map(*[x for m, c in R.ALARM_CODES.items()
                                                                 for x in (F.lit(m), F.lit(c["ICE"]))]), mfr)),
        F.when(F.col("status") == 4, F.lit(R.GRID_ALARM)),
        F.when((F.col("progress") > 0.75) & (u("warn") < F.col("progress") - 0.6),
               F.concat(F.element_at(F.create_map(*[x for m, c in R.ALARM_CODES.items()
                                                    for x in (F.lit(m), F.lit(c["GEARBOX"][:4]))]), mfr),
                        F.lit("-WRN"))),
    ))
    return df.select(
        F.substring(F.sha2(F.concat_ws("|", "asset_id", "epoch", "copy"), 256), 1, 24).alias("msg_id"),
        F.col("park").alias("site"),
        tag.alias("turbine"),
        ts.alias("ts"),
        F.when(mfr == "HTW", dev * 1000).alias("ts_epoch_ms"),
        _fmt(F.col("recv_epoch"), "yyyy-MM-dd'T'HH:mm:ss'Z'").alias("received_at"),
        fw.alias("fw"),
        F.col("status").cast("int").alias("status"),
        F.when(F.col("setpoint_kw").isNotNull(), F.round(F.col("setpoint_kw"), 1)).alias("setpoint_kw"),
        alarms.alias("alarms"),
        sensors.alias("sensors"),
        "ingest_date",
    )


# =============================================================================
# Inversores solares (5 minutos, CSV exportado por la plataforma de monitoreo)
# =============================================================================
def generate_inverter_5min(spark: SparkSession, cfg: ProjectConfig, start: date, end: date) -> DataFrame:
    _set_utc(spark)
    gen_from = max(cfg.start_date, start - timedelta(days=4))
    rows = []
    for u in E.fleet(cfg, "INV"):
        p = R.PARKS_BY_CODE[u.park]
        rows.append((u.asset_id, u.park, u.tag, u.rated_kw, u.dc_kwp, u.wake, p.lat, p.lon, float(p.altitude_m),
                     E.local_epoch(u.commissioning)))
    inv = spark.createDataFrame(rows, "asset_id string, park string, tag string, rated_kw double, dc_kwp double, "
                                      "eff double, lat double, lon double, alt double, comm_epoch long")
    soil_series, _ = E.soiling(cfg, end)
    soil = spark.createDataFrame([(k[0], k[1], v) for k, v in soil_series.items()],
                                 "park string, date_local date, soiling double")
    L = T.LongType()
    ev = _array_of_structs(spark, [e for e in E.downtime_events(cfg, end) if e["asset_type"] == "INV"], "asset_id",
                           [("start", L), ("end", L)], "ev_asset")
    wx = _weather_days_df(spark, cfg, end).select("park", "date_local", "cloud", "temp_anom")
    t0, t1 = E.local_epoch(gen_from), E.local_epoch(end + timedelta(days=1))
    n_parts = _range_partitions((end - gen_from).days + 1, len(rows))
    days = spark.range(t0 // 86_400, t1 // 86_400 + 1, 1, n_parts).select((F.col("id") * 86_400).alias("day0"))
    # sólo entre las 06:00 y las 21:00 locales (de noche el inversor no reporta)
    slots = days.select(F.explode(F.sequence(F.col("day0") + 9 * 3600, F.col("day0") + 24 * 3600, F.lit(300)))
                        .alias("epoch"))
    e = F.col("epoch")
    u = lambda salt: uniform("asset_id", "epoch", salt=salt)  # noqa: E731
    df = (
        slots.crossJoin(F.broadcast(inv))
        .where((e >= F.col("comm_epoch")) & (e >= t0) & (e < t1))
        .withColumn("local", e - ART_S)
        .withColumn("date_local", _date_of(F.col("local")))
        .withColumn("hour_local", F.pmod(F.col("local"), F.lit(86_400)) / 3600.0)
        .withColumn("doy_utc", F.dayofyear(_date_of(e)))
        .withColumn("hour_utc", F.pmod(e, F.lit(86_400)) / 3600.0)
        .withColumn("poa_clear", ph.poa_clear_col(F.col("lat"), F.col("lon"), F.col("alt"), F.col("doy_utc"),
                                                  F.col("hour_utc")))
        .where(F.col("poa_clear") > 0)
        .join(F.broadcast(wx), ["park", "date_local"], "left")
        .join(F.broadcast(soil), ["park", "date_local"], "left")
        .join(F.broadcast(ev), F.col("asset_id") == F.col("ev_asset"), "left").withColumnRenamed("items", "ev")
        .withColumn("down", _first_active("ev", e))
    )
    cumulus = F.when((F.col("cloud") < 0.9) & (u("cu") < 0.35), 1 - 0.45 * u("cu2")).otherwise(1.0)
    df = (
        df.withColumn("poa", F.col("poa_clear") * F.col("cloud") * cumulus * (1 + 0.02 * (u("ir") - 0.5)))
        .withColumn("ambient", ph.temp_c_col(F.col("park"), F.dayofyear("date_local"), F.col("hour_local"),
                                             F.col("temp_anom")))
        .withColumn("module_c", F.col("ambient") + 0.03 * F.col("poa"))
        .withColumn("dc_kw", F.col("dc_kwp") * F.col("poa") / 1000 * (1 - 0.004 * (F.col("module_c") - 25))
                    * (1 - F.coalesce(F.col("soiling"), F.lit(0.0))) * F.col("eff"))
        .withColumn("dc_kw", F.when(F.col("down").isNotNull(), F.lit(0.0)).otherwise(F.col("dc_kw")))
        .withColumn("ac_kw", F.least(F.col("rated_kw"), F.col("dc_kw") * 0.975))
    )
    fmt_ymd = F.col("park").isin("SUS", "ABR")
    mw_bug = (F.col("park") == R.INVERTER_MW_BUG[0]) & (F.col("date_local") < F.lit(R.INVERTER_MW_BUG[1]))
    poa_out = F.when(u("ir9") < 0.0005, F.lit(9999.0)).otherwise(F.col("poa") - 3 * u("off"))  # offset de madrugada
    drift_col, drift_date = R.SCHEMA_DRIFT_INVERTER
    # el CSV de cada día se exporta a la noche; a veces llega tarde (VSAT) y a veces se re-exporta
    late = F.when(uniform("park", "date_local", salt="late") < 0.10, 1 + F.floor(3 * uniform("park", "date_local",
                                                                                            salt="late2")))
    df = (
        df.withColumn("copies", F.when(uniform("park", "date_local", salt="reexp") < 0.03,
                                       F.array(F.lit(0), F.lit(1))).otherwise(F.array(F.lit(0))))
        .withColumn("copy", F.explode("copies"))
        .withColumn("ingest_date", F.date_add(F.col("date_local"),
                                              (F.coalesce(late, F.lit(0)) + F.col("copy")).cast("int")))
        .where((F.col("ingest_date") >= F.lit(start)) & (F.col("ingest_date") <= F.lit(end)))
    )
    return df.select(
        F.col("park").alias("plant"),
        F.col("tag").alias("inverter"),
        F.when(fmt_ymd, _fmt(F.col("local"), "yyyy-MM-dd HH:mm")).otherwise(_fmt(F.col("local"), "dd/MM/yyyy HH:mm"))
        .alias("timestamp"),
        F.round(poa_out, 1).alias("poa_irradiance_wm2"),
        _maybe_null(F.round(F.col("module_c"), 1), "asset_id", "epoch", salt="nmt", p=0.005).alias("module_temp_c"),
        F.round(F.col("ambient"), 1).alias("ambient_temp_c"),
        F.round(F.when(u("spk") < 0.0002, F.col("dc_kwp") * 1.4).otherwise(F.col("dc_kw")), 2).alias("dc_power_kw"),
        F.round(F.when(mw_bug, F.col("ac_kw") / 1000).otherwise(F.col("ac_kw")), 3).alias("ac_power_kw"),
        F.when(F.col("down").isNotNull(), F.lit("FAULT")).otherwise(F.lit("OK")).alias("status"),
        F.when(F.col("date_local") >= F.lit(drift_date),
               F.round(F.col("soiling") * 100 + 0.4 * (u("ss") - 0.5), 2)).alias(drift_col),
        "ingest_date",
    )


# =============================================================================
# Clima horario: observado y pronóstico (JSON de un proveedor meteorológico)
# =============================================================================
def generate_weather(spark: SparkSession, cfg: ProjectConfig, start: date, end: date) -> DataFrame:
    _set_utc(spark)
    gen_from = max(cfg.start_date, start - timedelta(days=3))
    parks = spark.createDataFrame([(p.code, p.tech, p.lat, p.lon, float(p.altitude_m)) for p in R.PARKS],
                                  "park string, tech string, lat double, lon double, alt double")
    wx = _weather_days_df(spark, cfg, end + timedelta(days=1))
    t0, t1 = E.local_epoch(gen_from), E.local_epoch(end + timedelta(days=2))
    hours = spark.range(t0 // 3600, t1 // 3600, 1, max(4, (end - gen_from).days // 60)).select(
        (F.col("id") * 3600).alias("epoch"))
    e = F.col("epoch")
    u = lambda salt: uniform("park", "epoch", salt=salt)  # noqa: E731
    df = (
        hours.crossJoin(F.broadcast(parks))
        .withColumn("local", e - ART_S)
        .withColumn("date_local", _date_of(F.col("local")))
        .withColumn("hour_local", F.pmod(F.col("local"), F.lit(86_400)) / 3600.0)
        .join(F.broadcast(wx), ["park", "date_local"], "left")
        .withColumn("wind", F.coalesce(ph.wind_by_park_col(F.col("park"), e.cast("double"), F.month("date_local"),
                                                           F.col("hour_local"), F.col("wind_mult"), 1.0, u("tw")),
                                       3 + 4 * u("tw") * F.col("wind_mult")))
        .withColumn("temp", ph.temp_c_col(F.col("park"), F.dayofyear("date_local"), F.col("hour_local"),
                                          F.col("temp_anom")))
        .withColumn("ghi", ph.poa_clear_col(F.col("lat"), F.col("lon"), F.col("alt"), F.dayofyear(_date_of(e)),
                                            F.pmod(e, F.lit(86_400)) / 3600.0) / 1.12 * F.col("cloud"))
        .withColumn("ice", F.col("ice_start_h").isNotNull() & (F.col("hour_local") >= F.col("ice_start_h") - 1)
                    & (F.col("hour_local") < F.col("ice_end_h") + 1))
        .withColumn("precip", F.when((F.col("precip_mm") > 0) & (F.floor(F.col("hour_local")) >= 12)
                                     & (F.floor(F.col("hour_local")) < 18), F.col("precip_mm") / 6).otherwise(0.0))
    )
    dust = F.when(F.col("tech") == "SOLAR", 0.05 + 0.15 * u("aod")).otherwise(0.03 + 0.05 * u("aod"))
    actual = df.select(
        F.col("park").alias("park_code"), F.lit("actual").alias("kind"),
        F.concat(_fmt(e - ART_S + 3600 + 600 * u("iss"), "yyyy-MM-dd'T'HH:mm:ss"), F.lit("-03:00")).alias("issued_at"),
        _fmt(e, "yyyy-MM-dd'T'HH:mm:ss'Z'").alias("valid_time"),
        F.round(F.col("wind"), 2).alias("wind_ms_100m"),
        F.round(F.col("wind") * (1.3 + 0.3 * u("gu")), 2).alias("gust_ms"),
        F.round(F.pmod(265 + 50 * F.sin(e / 90_000.0) + 20 * u("wd"), F.lit(360.0)), 0).alias("wind_dir_deg"),
        F.round(F.col("temp"), 1).alias("temp_c"),
        F.round(F.least(F.lit(100.0), F.col("rh_pct") + 10 * (u("rh") - 0.5)), 1).alias("rh_pct"),
        F.round(F.col("precip"), 2).alias("precip_mm"),
        F.round(F.when(F.col("snow_cm") > 0, F.col("precip") * 1.2).otherwise(0.0), 2).alias("snow_cm"),
        F.round(F.col("ghi"), 1).alias("ghi_wm2"),
        F.round((1 - F.col("cloud")) * 100, 0).alias("cloud_pct"),
        F.round(dust, 3).alias("dust_aod"),
        F.when(F.col("ice"), F.lit("HIGH")).when((F.col("temp") < 1) & (F.col("rh_pct") > 80), F.lit("MEDIUM"))
        .otherwise(F.lit("LOW")).alias("ice_risk"),
        F.when(uniform("park", "date_local", salt="wlate") < 0.03, F.date_add("date_local", 1))
        .otherwise(F.col("date_local")).alias("ingest_date"),
        F.lit(None).cast("int").alias("precip_prob_pct"),
    )
    err = F.lit(1.0) + 0.25 * (u("fe") - 0.5) + 0.10 * (uniform("park", "date_local", salt="fb") - 0.5)
    forecast = df.select(
        F.col("park").alias("park_code"), F.lit("forecast").alias("kind"),
        F.concat(F.date_format(F.date_sub("date_local", 1), "yyyy-MM-dd"), F.lit("T12:00:00-03:00")).alias("issued_at"),
        _fmt(e, "yyyy-MM-dd'T'HH:mm:ss'Z'").alias("valid_time"),
        F.round(F.col("wind") * err, 2).alias("wind_ms_100m"),
        F.round(F.col("wind") * err * 1.45, 2).alias("gust_ms"),
        F.round(F.pmod(265 + 50 * F.sin(e / 90_000.0) + 40 * u("fwd"), F.lit(360.0)), 0).alias("wind_dir_deg"),
        F.round(F.col("temp") + 3 * (u("ft") - 0.5), 1).alias("temp_c"),
        F.round(F.col("rh_pct"), 1).alias("rh_pct"),
        F.round(F.col("precip") * (0.5 + u("fp")), 2).alias("precip_mm"),
        F.lit(None).cast("double").alias("snow_cm"),
        F.round(F.col("ghi") * (0.9 + 0.2 * u("fg")), 1).alias("ghi_wm2"),
        F.round((1 - F.col("cloud")) * 100 + 20 * (u("fc") - 0.5), 0).alias("cloud_pct"),
        F.lit(None).cast("double").alias("dust_aod"),
        F.when(F.col("ice") & (u("fi") < 0.8), F.lit("HIGH")).otherwise(F.lit("LOW")).alias("ice_risk"),
        F.date_sub("date_local", 1).alias("ingest_date"),
        F.when(F.col("precip_mm") > 0, F.round(60 + 40 * u("pp"))).otherwise(F.round(15 * u("pp")))
        .cast("int").alias("precip_prob_pct"),
    )
    out = actual.unionByName(forecast)
    dup = out.where(uniform("park_code", "valid_time", "kind", salt="wdup") < 0.01)
    return (out.unionByName(dup)
            .where((F.col("ingest_date") >= F.lit(start)) & (F.col("ingest_date") <= F.lit(end))))


# =============================================================================
# Fuentes chicas (driver)
# =============================================================================
def _serial(prefix: str, asset_id: str, version: int) -> str:
    """Número de serie determinístico; cambia cuando se reemplaza el componente."""
    return f"{prefix}{prng(0, prefix, asset_id, version).randint(100_000, 999_999)}"


def _fmt_old_or_new(dt: datetime, migration: date = date(2024, 3, 1)) -> str:
    """El CMMS viejo exportaba dd/MM/yyyy HH:mm; desde la migración, ISO."""
    return dt.strftime("%d/%m/%Y %H:%M") if dt.date() < migration else dt.strftime("%Y-%m-%d %H:%M:%S")


def _in_range(d: date, start: date, end: date) -> bool:
    return start <= d <= end


def generate_cmms_assets(spark: SparkSession, cfg: ProjectConfig, start: date, end: date) -> DataFrame:
    rows: list[tuple] = []
    majors = defaultdict(list)
    for ev in E.downtime_events(cfg, end):
        if ev["kind"] == "MAJOR_FAILURE":
            majors[ev["asset_id"]].append(ev)
    pei_fw, (drift_mfr, drift_date, _) = date(2024, 2, 1), R.SCHEMA_DRIFT_SCADA
    for u in E.fleet(cfg):
        m = R.MANUFACTURERS.get(u.manufacturer) if u.manufacturer else None
        state = {
            "asset_id": u.asset_id, "asset_tag": u.tag, "asset_type": u.asset_type, "park_code": u.park,
            "manufacturer": m.name if m else "SolarDrive", "model": m.model if m else "SD-2500C",
            "rated_kw": u.rated_kw, "dc_kwp": u.dc_kwp or None, "panels": u.panels or None,
            "gearbox_serial": _serial("GBX", u.asset_id, 0) if m else None,
            "main_bearing_serial": _serial("MBR", u.asset_id, 0) if m else None,
            "generator_serial": _serial("GEN", u.asset_id, 0) if m else None,
            "firmware": ({"AWS": "AW-FW 8.2.1", "HTW": "HT-OS 4.1", "PEI": "PEI-CTL 2.3"}[m.code] if m
                         else "SD-FW 3.0"),
            "commissioning_date": u.commissioning.isoformat(), "status": "OPERATIVO",
        }
        changes: list[tuple[datetime, dict, str]] = []
        first = datetime.combine(max(u.commissioning, cfg.start_date), datetime.min.time(), ART) + timedelta(hours=9)
        changes.append((first, {}, "I"))
        if u.new_tag:
            changes.append((datetime.combine(R.TURBINE_RENAME[1], datetime.min.time(), ART) + timedelta(hours=10),
                            {"asset_tag": u.new_tag}, "U"))
        if m and m.code == "PEI":
            changes.append((datetime.combine(pei_fw, datetime.min.time(), ART) + timedelta(hours=11),
                            {"firmware": "PEI-CTL 2.4"}, "U"))
        if m and m.code == drift_mfr:
            changes.append((datetime.combine(drift_date, datetime.min.time(), ART) + timedelta(hours=11),
                            {"firmware": "HT-OS 5.0"}, "U"))
        for n, ev in enumerate(majors.get(u.asset_id, []), start=1):
            col = {"GEARBOX": ("gearbox_serial", "GBX"), "MAIN_BEARING": ("main_bearing_serial", "MBR"),
                   "GENERATOR_BEARING": ("generator_serial", "GEN")}[ev["component"]]
            changes.append((datetime.fromtimestamp(ev["end"], ART) + timedelta(hours=6),
                            {col[0]: _serial(col[1], u.asset_id, n)}, "U"))
        for when, delta, op in sorted(changes, key=lambda c: c[0]):
            state = {**state, **delta}
            ingest = when.date()
            rec = (*state.values(), op, _fmt_old_or_new(when.replace(tzinfo=None)))
            if _in_range(ingest, start, end):
                rows.append((*rec, ingest))
            if op == "U" and prng(cfg.seed, "adup", u.asset_id, when.isoformat()).random() < 0.05:
                dup_day = ingest + timedelta(days=1)
                if _in_range(dup_day, start, end):
                    rows.append((*rec, dup_day))  # re-envío idéntico al día siguiente
    schema = ("asset_id string, asset_tag string, asset_type string, park_code string, manufacturer string, "
              "model string, rated_kw double, dc_kwp double, panels int, gearbox_serial string, "
              "main_bearing_serial string, generator_serial string, firmware string, commissioning_date string, "
              "status string, op string, updated_at string, ingest_date date")
    return spark.createDataFrame(rows, schema)


def generate_cmms_crews(spark: SparkSession, cfg: ProjectConfig, start: date, end: date) -> DataFrame:
    rows = []
    for crew in R.CREWS:
        rec = (*crew, "I", f"{cfg.start_date:%d/%m/%Y} 08:00")
        if _in_range(cfg.start_date, start, end):
            rows.append((*rec, cfg.start_date))
    change = date(2025, 5, 2)
    if _in_range(change, start, end):
        c = R.CREWS[1]
        rows.append((c[0], c[1], "Diego Huenchumil", "+54 297 466-0034", c[4], c[5], "U",
                     f"{change:%Y-%m-%d} 09:30:00", change))
    return spark.createDataFrame(rows, "crew_id string, base string, leader_name string, leader_phone string, "
                                       "members int, specialty string, op string, updated_at string, ingest_date date")


PART_CATALOG = {
    "GEARBOX": [("GBX-ASSY", "Multiplicadora completa", 1, 140_000.0), ("OIL-GBX", "Aceite multiplicadora (l)", 600, 9.5)],
    "MAIN_BEARING": [("MBR-ASSY", "Rodamiento principal", 1, 85_000.0), ("GRS-01", "Grasa especial (kg)", 40, 32.0)],
    "GENERATOR_BEARING": [("GBR-ASSY", "Rodamiento lado acople generador", 2, 11_000.0)],
    "PITCH": [("PCH-MOT", "Motor de pitch", 1, 6_800.0)],
    "YAW": [("YAW-BRK", "Pastillas freno de yaw", 8, 240.0)],
    "CONVERTIDOR": [("CNV-IGBT", "Módulo IGBT convertidor", 1, 9_500.0)],
    "SENSOR": [("SNS-ANM", "Anemómetro ultrasónico", 1, 2_900.0)],
    "CONTROL": [],
    "PREVENTIVO": [("FLT-KIT", "Kit de filtros", 1, 850.0), ("OIL-HYD", "Aceite hidráulico (l)", 60, 7.5)],
    "IGBT": [("INV-IGBT", "Stack IGBT inversor", 1, 4_200.0)],
    "VENTILACION": [("INV-FAN", "Ventilador de gabinete", 2, 380.0)],
    "AISLACION": [("INV-ISO", "Kit de reparación de aislación DC", 1, 650.0)],
    "LIMPIEZA": [],
}
NOTES = {
    "MAJOR_FAILURE": "Falla de {c}. Se espera repuesto importado y grúa de 600 t desde Comodoro.",
    "MINOR_FAULT": "Alarma {c}. Diagnóstico y reparación en sitio.",
    "PREVENTIVE": "Mantenimiento preventivo semestral según plan del fabricante.",
    "CLEANING": "Limpieza de módulos con agua desmineralizada transportada en camión cisterna.",
}


def _work_orders(cfg: ProjectConfig, end: date) -> list[dict]:
    """Una lista de órdenes con todos sus hitos (lo que después se emite como CDC)."""
    tags = {u.asset_id: u for u in E.fleet(cfg)}
    orders: list[dict] = []
    for ev in E.downtime_events(cfg, end):
        rng = prng(cfg.seed, "wo", ev["asset_id"], ev["start"])
        if ev["remote"] and rng.random() < 0.5:
            continue  # la mitad de los resets remotos ni siquiera se registra (¡dato que falta!)
        s, f = datetime.fromtimestamp(ev["start"], ART), datetime.fromtimestamp(ev["end"], ART)
        if ev["kind"] == "PREVENTIVE":
            created = s - timedelta(days=rng.randint(7, 14))
            arrived = s
        else:
            created = s + timedelta(minutes=rng.randint(5, 40))
            arrived = s + timedelta(hours=1 + ev["travel_h"] + ev["access_delay_h"]) if not ev["remote"] else s
        work_start = max(arrived, f - timedelta(hours=ev["repair_h"] or (f - s).total_seconds() / 3600))
        crew = ("CU-NOA-02" if ev["asset_type"] == "INV" else "CU-PAT-01" if ev["kind"] == "MAJOR_FAILURE"
                else "CU-PAT-04" if ev["kind"] == "PREVENTIVE" else rng.choice(["CU-PAT-02", "CU-PAT-03"]))
        parts = [{"part_code": c, "description": d, "qty": q, "unit_cost_usd": round(p * rng.uniform(0.95, 1.1), 2)}
                 for c, d, q, p in PART_CATALOG.get(ev["component"], [])]
        crew_size = next(c[4] for c in R.CREWS if c[0] == crew)
        hours = 0.5 if ev["remote"] else crew_size * (ev["repair_h"] + 2 * ev["travel_h"] + 4)
        orders.append({
            "asset_id": ev["asset_id"], "park": ev["park"], "kind": ev["kind"], "component": ev["component"],
            "failure_at": s if ev["kind"] != "PREVENTIVE" else None, "created": created, "arrived": arrived,
            "work_start": work_start, "work_end": f,
            "closed": f + timedelta(hours=rng.uniform(2, 72)), "crew": None if ev["remote"] else crew,
            "parts": parts, "labor_h": round(hours, 1), "travel_km": 0 if ev["remote"] else
            2 * R.PARKS_BY_CODE[ev["park"]].distance_km, "access_delay_h": ev["access_delay_h"],
            "crane_usd": round(rng.uniform(35_000, 60_000), 0) if ev["component"] in ("GEARBOX", "MAIN_BEARING")
            and ev["kind"] == "MAJOR_FAILURE" else 0.0, "water_m3": None, "unit": tags[ev["asset_id"]],
            "remote": ev["remote"],
        })
    _, cleanings = E.soiling(cfg, end)
    for c in cleanings:
        park = R.PARKS_BY_CODE[c["park"]]
        s = datetime.combine(c["start"], datetime.min.time(), ART) + timedelta(hours=7)
        f = datetime.combine(c["end"], datetime.min.time(), ART) + timedelta(hours=18)
        rng = prng(cfg.seed, "wo-clean", c["park"], c["start"])
        days = (c["end"] - c["start"]).days + 1
        orders.append({
            "asset_id": None, "park": c["park"], "kind": "CLEANING", "component": "LIMPIEZA", "failure_at": None,
            "created": s - timedelta(days=rng.randint(3, 8)), "arrived": s, "work_start": s, "work_end": f,
            "closed": f + timedelta(hours=rng.uniform(4, 48)), "crew": "CU-NOA-01", "parts": [],
            "labor_h": 8 * 10 * days, "travel_km": 2 * park.distance_km, "access_delay_h": 0.0, "crane_usd": 0.0,
            "water_m3": c["water_m3"], "unit": None, "remote": False, "trigger": c["trigger"],
        })
    orders.sort(key=lambda o: o["created"])
    for n, o in enumerate(orders, start=1):
        o["order_id"] = f"OT-{o['created'].year}-{n:06d}"
    return orders


ORDER_TYPE = {"MAJOR_FAILURE": "CORRECTIVA", "MINOR_FAULT": "CORRECTIVA", "PREVENTIVE": "PREVENTIVA",
              "CLEANING": "LIMPIEZA"}


def generate_cmms_work_orders(spark: SparkSession, cfg: ProjectConfig, start: date, end: date) -> DataFrame:
    rows: list[dict] = []
    ren_park, ren_date = R.TURBINE_RENAME
    for o in _work_orders(cfg, end):
        u: E.Unit | None = o["unit"]
        tag = None
        if u is not None:
            tag = u.new_tag if (u.new_tag and o["created"].date() >= ren_date) else u.tag
        labor_ars = round(o["labor_h"] * E.labor_rate_ars(o["work_end"].date()), 0)
        water_usd = round((o["water_m3"] or 0) * R.PARKS_BY_CODE[o["park"]].water_cost_usd_m3, 2)
        base = {
            "order_id": o["order_id"], "asset_tag": tag, "park_code": o["park"], "order_type": ORDER_TYPE[o["kind"]],
            "severity": "MAYOR" if o["kind"] == "MAJOR_FAILURE" else "MENOR" if o["kind"] == "MINOR_FAULT" else None,
            "component": o["component"], "priority": 1 if o["kind"] == "MAJOR_FAILURE" else 3,
            "failure_at": _fmt_old_or_new(o["failure_at"].replace(tzinfo=None)) if o["failure_at"] else None,
            "crew_id": o["crew"], "remote_reset": o["remote"], "travel_km": o["travel_km"],
            "access_delay_h": o["access_delay_h"],
            "notes": NOTES.get(o["kind"], "").format(c=R.COMPONENTS.get(o["component"], (o["component"].lower(),))[0]),
        }
        milestones = [("I", o["created"], "ABIERTA", {})]
        if not o["remote"]:
            milestones.append(("U", o["arrived"], "EN_CURSO", {"arrived_at": o["arrived"]}))
        milestones.append(("U", o["closed"], "CERRADA", {
            "arrived_at": o["arrived"], "work_start": o["work_start"], "work_end": o["work_end"],
            "labor_hours": o["labor_h"], "labor_cost_ars": labor_ars, "parts": o["parts"],
            "crane_cost_usd": o["crane_usd"], "water_m3": o["water_m3"], "water_cost_usd": water_usd or None,
        }))
        for op, when, status, extra in milestones:
            rec = {**base, "op": op, "status": status, "event_ts": _fmt_old_or_new(when.replace(tzinfo=None)),
                   "created_at": _fmt_old_or_new(o["created"].replace(tzinfo=None)), "ingest_date": when.date()}
            for k, v in extra.items():
                rec[k] = _fmt_old_or_new(v.replace(tzinfo=None)) if isinstance(v, datetime) else v
            rows.append(rec)
        rng = prng(cfg.seed, "wo-dup", o["order_id"])
        if rng.random() < 0.02:  # orden duplicada por error del operador: se crea y se borra
            dup_id = o["order_id"].replace("OT-", "OT-D")
            t = o["created"] + timedelta(minutes=rng.randint(2, 30))
            for op, dt in (("I", t), ("D", t + timedelta(hours=rng.randint(1, 20)))):
                rows.append({**base, "order_id": dup_id, "op": op, "status": "ABIERTA" if op == "I" else "ANULADA",
                             "event_ts": _fmt_old_or_new(dt.replace(tzinfo=None)),
                             "created_at": _fmt_old_or_new(t.replace(tzinfo=None)), "ingest_date": dt.date()})
    rows = [r for r in rows if _in_range(r["ingest_date"], start, end)]
    part = T.StructType([T.StructField("part_code", T.StringType()), T.StructField("description", T.StringType()),
                         T.StructField("qty", T.IntegerType()), T.StructField("unit_cost_usd", T.DoubleType())])
    fields = [("order_id", T.StringType()), ("op", T.StringType()), ("event_ts", T.StringType()),
              ("status", T.StringType()), ("asset_tag", T.StringType()), ("park_code", T.StringType()),
              ("order_type", T.StringType()), ("severity", T.StringType()), ("component", T.StringType()),
              ("priority", T.IntegerType()), ("failure_at", T.StringType()), ("created_at", T.StringType()),
              ("arrived_at", T.StringType()), ("work_start", T.StringType()), ("work_end", T.StringType()),
              ("crew_id", T.StringType()), ("remote_reset", T.BooleanType()), ("travel_km", T.IntegerType()),
              ("access_delay_h", T.DoubleType()), ("labor_hours", T.DoubleType()),
              ("labor_cost_ars", T.DoubleType()), ("parts", T.ArrayType(part)), ("crane_cost_usd", T.DoubleType()),
              ("water_m3", T.DoubleType()), ("water_cost_usd", T.DoubleType()), ("notes", T.StringType()),
              ("ingest_date", T.DateType())]
    schema = T.StructType([T.StructField(n, t) for n, t in fields])

    def value(r: dict, name: str, dtype: T.DataType):
        v = r.get(name)
        if name == "parts" and v is not None:
            return [tuple(p.values()) for p in v]
        return float(v) if isinstance(dtype, T.DoubleType) and v is not None else v

    return spark.createDataFrame([tuple(value(r, n, t) for n, t in fields) for r in rows], schema)


def generate_cammesa_dispatch(spark: SparkSession, cfg: ProjectConfig, start: date, end: date) -> DataFrame:
    rows = []

    def iso(epoch: int) -> str:
        return datetime.fromtimestamp(epoch, ART).strftime("%Y-%m-%dT%H:%M:%S-03:00")

    instructions = E.curtailment_instructions(cfg, end)
    rng0 = prng(cfg.seed, "fake-dsp")
    for c in instructions:  # instrucciones que se emitieron y se anularon antes de aplicarse
        if rng0.random() < 0.03:
            instructions = instructions + [dict(c, instruction_id=c["instruction_id"] + "X", fake=True,
                                                start=c["start"] + 86_400, end=c["end"] + 86_400)]
    for c in instructions:
        park = R.PARKS_BY_CODE[c["park"]]
        rng = prng(cfg.seed, "dsp", c["instruction_id"])
        issued = c["start"] - rng.randint(30, 120) * 60
        base = {"instruction_id": c["instruction_id"], "agent_code": park.cammesa_code, "node": park.cammesa_node,
                "limit_mw": c["limit_mw"], "reason": c["reason"]}
        versions = []
        if c.get("fake"):
            versions = [(1, issued, c["end"], "EMITIDA"), (2, issued + 600, c["end"], "ANULADA")]
        elif rng.random() < 0.15:  # se emitió con un horario y después se corrigió
            versions = [(1, issued, c["end"] + rng.choice([-2, -1, 1, 2]) * 3600, "EMITIDA"),
                        (2, c["start"] + 1800, c["end"], "MODIFICADA")]
        else:
            versions = [(1, issued, c["end"], "EMITIDA")]
        for v, iss, stop, status in versions:
            rec = {**base, "version": v, "issued_at": iso(iss), "valid_from": iso(c["start"]), "valid_to": iso(stop),
                   "status": status, "ingest_date": datetime.fromtimestamp(iss, ART).date()}
            rows.append(rec)
            if rng.random() < 0.01:
                rows.append(dict(rec))
    rows = [r for r in rows if _in_range(r["ingest_date"], start, end)]
    schema = ("instruction_id string, version int, agent_code string, node string, issued_at string, "
              "valid_from string, valid_to string, limit_mw double, reason string, status string, ingest_date date")
    cols = [c.split()[0] for c in schema.split(", ")]
    return spark.createDataFrame([tuple(r[c] for c in cols) for r in rows], schema)


def _congested_hours(cfg: ProjectConfig, end: date) -> set[tuple[date, int]]:
    out = set()
    for c in E.curtailment_instructions(cfg, end):
        if c["reason"] != "RESTRICCION_TRANSPORTE":
            continue
        t = c["start"]
        while t < c["end"]:
            dt = datetime.fromtimestamp(t, ART)
            out.add((dt.date(), dt.hour))
            t += 3600
    return out


def generate_cammesa_spot_prices(spark: SparkSession, cfg: ProjectConfig, start: date, end: date) -> DataFrame:
    """Formato CAMMESA: FECHA dd/MM/yyyy, HORA 1..24 (¡la hora 24 es de 23 a 24!), precio con coma."""
    congested = _congested_hours(cfg, end)
    rows = []
    for d in E.daterange(cfg.start_date, end + timedelta(days=1)):
        fx = E.fx_rate(d)
        for node in ("PATAGONIA", "NOA"):
            rng = prng(cfg.seed, "spot", node, d)
            for h in range(24):
                usd = E.spot_price_usd(node, d, h, rng, (d, h) in congested)
                ars = usd * fx
                pre = d + timedelta(days=1)
                if _in_range(pre, start, end):
                    rows.append((d.strftime("%d/%m/%Y"), h + 1, node, ars, "PRELIMINAR", pre))
                nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 10)
                if _in_range(nxt, start, end):
                    fin = ars * (rng.uniform(0.97, 1.03) if rng.random() < 0.2 else 1.0)
                    rows.append((d.strftime("%d/%m/%Y"), h + 1, node, fin, "DEFINITIVO", nxt))
    df = spark.createDataFrame(rows, "FECHA string, HORA int, NODO string, precio double, TIPO string, "
                                     "ingest_date date")
    return df.select("FECHA", "HORA", "NODO", _ar_number(F.col("precio")).alias("PRECIO_ARS_MWH"), "TIPO",
                     "ingest_date")


def generate_fx_rates(spark: SparkSession, cfg: ProjectConfig, start: date, end: date) -> DataFrame:
    rows = []
    for d in E.daterange(max(start, cfg.start_date), end):
        if d.weekday() >= 5 or d in R.HOLIDAYS_AR:
            continue  # el BNA no publica cotización: silver tiene que completar el calendario
        rows.append((d.strftime("%d/%m/%Y"), "USD", "BNA_VENDEDOR", E.fx_rate(d), d))
    df = spark.createDataFrame(rows, "FECHA string, MONEDA string, TIPO string, valor double, ingest_date date")
    return df.select("FECHA", "MONEDA", "TIPO", _ar_number(F.col("valor")).alias("VALOR"), "ingest_date")


def budget_rows(cfg: ProjectConfig, end: date) -> list[dict]:
    """Presupuesto P50 por parque y mes (v1 de cada año + re-presupuesto de julio 2025)."""
    units = E.park_units(cfg)
    out = []
    years = range(cfg.start_date.year, end.year + 1 + (end.month == 12))
    for year in years:
        avail, curt = E.BUDGET_ASSUMPTIONS.get(year, (0.97, 0.05))
        published = cfg.start_date if year == cfg.start_date.year else date(year - 1, 12, 1)
        for park in R.PARKS:
            for month in range(1, 13):
                first = date(year, month, 1)
                days = (date(year + (month == 12), month % 12 + 1, 1) - first).days
                op_days = max(0, min(days, (date(year + (month == 12), month % 12 + 1, 1) - park.commissioning).days))
                kw = E.expected_unit_kw(cfg, park, year, month)
                gross = units[park.code] * kw * 24 * op_days / 1000
                a, c = (avail, curt) if park.tech == "WIND" else (0.99, 0.0)
                versions = [("v1", published, a, c)]
                if year == E.REFORECAST_2025[0].year and month >= E.REFORECAST_2025[0].month and park.tech == "WIND":
                    versions.append(("v2", E.REFORECAST_2025[0], a, E.REFORECAST_2025[1]))
                for v, pub, aa, cc in versions:
                    p50 = gross * aa * (1 - cc)
                    out.append({"anio": year, "mes": month, "parque": park.code, "version": f"PPTO-{year}-{v}",
                                "energia_p50_mwh": round(p50, 1), "energia_p90_mwh": round(p50 * 0.88, 1),
                                "disponibilidad_supuesta": aa, "curtailment_supuesto": cc,
                                "publicado": pub.isoformat(), "ingest_date": pub})
    return out


def generate_generation_budget(spark: SparkSession, cfg: ProjectConfig, start: date, end: date) -> DataFrame:
    rows = [r for r in budget_rows(cfg, end) if _in_range(r["ingest_date"], start, end)]
    schema = ("anio int, mes int, parque string, version string, energia_p50_mwh double, energia_p90_mwh double, "
              "disponibilidad_supuesta double, curtailment_supuesto double, publicado string, ingest_date date")
    cols = [c.split()[0] for c in schema.split(", ")]
    return spark.createDataFrame([tuple(r[c] for c in cols) for r in rows], schema)


def contract_committed_mwh(cfg: ProjectConfig, c: R.Contract) -> float:
    units = E.park_units(cfg)
    total = 0.0
    for code in c.sources:
        park = R.PARKS_BY_CODE[code]
        year = max(2023, c.start.year) if c.start.year >= 2023 else 2023
        monthly = [units[code] * E.expected_unit_kw(cfg, park, year, m) * 730 / 1000 for m in range(1, 13)]
        total += sum(monthly) / 12 * 0.97
    return round(total * c.share_of_sources, 1)


def generate_ppa_contracts(spark: SparkSession, cfg: ProjectConfig, start: date, end: date) -> DataFrame:
    rows = []
    term_id, term_date = R.CONTRACT_TERMINATION
    for c in R.CONTRACTS:
        state = {"contract_id": c.contract_id, "client_name": c.client, "sector": c.sector, "client_cuit": c.cuit,
                 "contact_name": c.contact_name, "contact_email": c.contact_email, "contact_phone": c.contact_phone,
                 "start_date": c.start.isoformat(), "end_date": c.end.isoformat(), "price_usd_mwh": c.price_usd_mwh,
                 "committed_mwh_month": contract_committed_mwh(cfg, c), "penalty_usd_mwh": c.penalty_usd_mwh,
                 "tolerance_pct": c.tolerance_pct, "source_parks": "|".join(c.sources), "status": "VIGENTE"}
        changes = [(max(cfg.start_date, c.start - timedelta(days=20)), {}, "I")]
        for year in range(max(c.start.year + 1, 2024), end.year + 1):  # indexación anual de precio en enero
            changes.append((date(year, 1, 5), {"price_usd_mwh": None}, "U"))
        if c.contract_id == "PPA-2019-002":
            changes.append((date(2024, 9, 2), {"contact_name": "Rocío Albarracín",
                                               "contact_email": "ralbarracin@cementeradelplata.com.ar",
                                               "contact_phone": "+54 11 4555-2377"}, "U"))
        if c.contract_id == "PPA-2023-007":  # adenda: el data center amplía 20 % el volumen comprometido
            changes.append((date(2024, 6, 1), {"committed_mwh_month": round(state["committed_mwh_month"] * 1.2, 1)}, "U"))
        if c.contract_id == term_id:
            changes.append((term_date, {"status": "RESCINDIDO", "end_date": term_date.isoformat()}, "U"))
            changes.append((term_date + timedelta(days=45), {}, "D"))
        for when, delta, op in sorted(changes, key=lambda x: x[0]):
            if "price_usd_mwh" in delta and delta["price_usd_mwh"] is None:
                delta = {"price_usd_mwh": round(state["price_usd_mwh"] * 1.02, 2)}
            state = {**state, **delta}
            stamp = (when.strftime("%d/%m/%Y") if when < date(2024, 3, 1) else f"{when.isoformat()}T10:00:00")
            if _in_range(when, start, end):
                rows.append((*state.values(), op, stamp, when))
                if prng(cfg.seed, "cdup", c.contract_id, when).random() < 0.08:
                    rows.append((*state.values(), op, stamp, when))
    schema = ("contract_id string, client_name string, sector string, client_cuit string, contact_name string, "
              "contact_email string, contact_phone string, start_date string, end_date string, "
              "price_usd_mwh double, committed_mwh_month double, penalty_usd_mwh double, tolerance_pct double, "
              "source_parks string, status string, op string, updated_at string, ingest_date date")
    return spark.createDataFrame(rows, schema)


# =============================================================================
# Registro: nombre -> (generador, formato, opciones de escritura)
# =============================================================================
SOURCES = {
    "scada_turbine": (generate_scada_turbine, "json", {"compression": "gzip"}),
    "inverter_5min": (generate_inverter_5min, "csv", {"header": "true"}),
    "cmms_assets": (generate_cmms_assets, "csv", {"header": "true"}),
    "cmms_work_orders": (generate_cmms_work_orders, "json", {}),
    "cmms_crews": (generate_cmms_crews, "csv", {"header": "true"}),
    "cammesa_dispatch": (generate_cammesa_dispatch, "json", {}),
    "cammesa_spot_prices": (generate_cammesa_spot_prices, "csv", {"header": "true", "sep": ";"}),
    "ppa_contracts": (generate_ppa_contracts, "csv", {"header": "true"}),
    "weather": (generate_weather, "json", {"compression": "gzip"}),
    "fx_rates": (generate_fx_rates, "csv", {"header": "true", "sep": ";"}),
    "generation_budget": (generate_generation_budget, "csv", {"header": "true"}),
}
# CSV sin esquema: la columna nueva aparece en el header recién desde esta fecha.
SCHEMA_DRIFT_CSV = {"inverter_5min": R.SCHEMA_DRIFT_INVERTER}

