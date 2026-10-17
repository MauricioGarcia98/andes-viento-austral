"""Transformaciones de silver: cada problema de datos real tiene su test."""

from datetime import datetime, timezone

import pytest
from pyspark.sql import functions as F

from andes_viento.silver import transforms as T


def test_ar_number_and_cammesa_hour(spark):
    df = spark.createDataFrame([("15/07/2025", "24", "PATAGONIA", "45.231,50", "PRELIMINAR")],
                               "FECHA string, HORA string, NODO string, PRECIO_ARS_MWH string, TIPO string")
    df = df.withColumn("_ingested_at", F.current_timestamp())
    row = T.clean_spot_prices(df).first()
    assert row.price_ars_mwh == pytest.approx(45231.5)
    assert row.hour_local == datetime(2025, 7, 15, 23, 0)          # hora 24 = de 23 a 24
    assert row.hour_ts == datetime(2025, 7, 16, 2, 0)              # en UTC
    assert row.version_rank == 1


def _scada(spark, rows):
    schema = ("site string, turbine string, ts string, ts_epoch_ms long, received_at string, fw string, status long, "
              "setpoint_kw double, alarms array<string>, sensors struct<wind_ms:double, active_power:double, "
              "power_unit:string, gearbox_bearing_c:double, vibration_mm_s:double>, _rescued_data string, "
              "_source_file string, _ingested_at timestamp")
    return spark.createDataFrame(rows, schema)


def _tags(spark):
    return spark.createDataFrame([("PAM-01", "WTG00001", 3000.0, "PAM"), ("LEO-01", "WTG00002", 4500.0, "LEO"),
                                  ("RAW-01", "WTG00003", 3600.0, "RAW")],
                                 "asset_tag string, asset_id string, rated_kw double, park_code string")


def _row(site, turbine, ts=None, epoch=None, recv="2025-07-15T13:00:20Z", power=1000.0, unit=None, wind=9.0):
    return (site, turbine, ts, epoch, recv, "fw", 0, None, [], (wind, power, unit, 50.0, 2.0), None, "f",
            datetime(2025, 7, 15))


def test_three_timestamp_formats_and_units(spark):
    df = _scada(spark, [
        _row("RAW", "RAW-01", ts="2025-07-15T10:00:00-03:00", unit="kW", power=1500.0),
        _row("LEO", "LEO-01", epoch=1752584400000, power=2000.0),                 # 2025-07-15 13:00 UTC
        _row("PAM", "PAM-01", ts="15/07/2025 10:00:00", power=1.2),                # local, en MW sin unidad
    ])
    out = {r.turbine_tag: r for r in T.clean_scada(df, _tags(spark)).collect()}
    assert all(r.ts_utc == datetime(2025, 7, 15, 13, 0) for r in out.values())
    assert out["PAM-01"].power_kw == pytest.approx(1200.0) and out["PAM-01"].unit_converted
    assert not out["RAW-01"].unit_converted


def test_timezone_switch_is_detected(spark):
    # el equipo manda UTC pero el formato dice "hora local": queda 3 h corrido -> se corrige
    rows = [_row("PAM", "PAM-01", ts=f"15/07/2025 13:{m:02d}:00", recv=f"2025-07-15T13:{m:02d}:15Z")
            for m in range(0, 60, 10)]
    out = T.clean_scada(_scada(spark, rows), _tags(spark)).collect()
    assert all(r.tz_corrected for r in out)
    assert out[0].ts_utc.hour == 13


def test_clock_skew_and_late_resend(spark):
    rows = [_row("LEO", "LEO-01", epoch=(1752584400 + m * 600 - 420) * 1000,          # reloj 7 min atrasado
                 recv=datetime.fromtimestamp(1752584400 + m * 600 + 20, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
            for m in range(12)]
    rows.append(_row("LEO", "LEO-01", epoch=(1752584400 - 6 * 3600 - 420) * 1000, recv="2025-07-15T13:30:00Z"))
    out = T.clean_scada(_scada(spark, rows), _tags(spark)).orderBy("ts_utc").collect()
    assert out[-1].clock_corrected and out[-1].clock_offset_s == 420
    assert out[-1].ts_utc == datetime(2025, 7, 15, 14, 50)
    assert out[0].late_arrival  # el re-envío de 6 h antes


def test_stuck_sensor(spark):
    rows = [("A", datetime(2025, 1, 1, h // 6, (h % 6) * 10), 41.3 if h >= 2 else 40.0 + h) for h in range(10)]
    df = spark.createDataFrame(rows, "asset_id string, ts_utc timestamp, gearbox_bearing_c double") \
        .withColumn("wind_ms", F.lit(None).cast("double")).withColumn("vibration_mm_s", F.col("gearbox_bearing_c"))
    out = T.flag_stuck_sensors(df).orderBy("ts_utc").collect()
    assert out[-1].gearbox_bearing_c is None and "gearbox_bearing_c" in out[-1].stuck_sensors
    assert out[2].gearbox_bearing_c == 41.3  # las primeras repeticiones todavía no son "clavado"


def test_dedupe_first_arrival(spark):
    df = spark.createDataFrame([("A", 1, 10), ("A", 1, 5), ("A", 2, 7)], "k string, slot int, received int")
    out = sorted((r.slot, r.received) for r in T.dedupe_first_arrival(df, ["k", "slot"], "received").collect())
    assert out == [(1, 5), (2, 7)]


def test_inverter_mw_bug(spark):
    df = spark.createDataFrame([("FIA", "FIA-INV01", "15/02/2024 13:00", "900", "45", "25", "2600", "2.45", "OK",
                                 datetime(2024, 2, 15).date(), "f", datetime(2024, 2, 15))],
                               "plant string, inverter string, timestamp string, poa_irradiance_wm2 string, "
                               "module_temp_c string, ambient_temp_c string, dc_power_kw string, ac_power_kw string, "
                               "status string, ingest_date date, _source_file string, _ingested_at timestamp")
    tags = spark.createDataFrame([("FIA-INV01", "INV00001", 2500.0, 3000.0)],
                                 "asset_tag string, asset_id string, rated_kw double, dc_kwp double")
    row = T.clean_inverter(df, tags).first()
    assert row.ac_power_kw == pytest.approx(2450.0) and row.unit_converted
    assert row.ts_utc == datetime(2024, 2, 15, 16, 0)


def test_split_statements_respects_strings_and_dollar_blocks():
    from andes_viento.gold.marts import split_statements

    sql = """-- comentario; con punto y coma
COMMENT ON TABLE t IS 'uno; dos \\' tres';
CREATE VIEW v AS $$
a: b; c
$$;
SELECT `x;y` FROM t -- fin; de línea
"""
    stmts = split_statements(sql)
    assert len(stmts) == 3
    assert stmts[0].endswith("'uno; dos \\' tres'")
    assert "a: b; c" in stmts[1]
