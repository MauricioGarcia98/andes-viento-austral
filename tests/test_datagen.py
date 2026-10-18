"""Generador distribuido: determinismo, suciedad inyectada y datos tardíos."""

from datetime import date

from pyspark.sql import functions as F

from andes_viento.datagen import generators as G

D0, D1 = date(2025, 2, 27), date(2025, 3, 3)


def test_scada_is_deterministic(spark, cfg):
    a = G.generate_scada_turbine(spark, cfg, D0, D1)
    b = G.generate_scada_turbine(spark, cfg, D0, D1)
    assert a.count() == b.count() > 0
    assert a.exceptAll(b).count() == 0


def test_scada_has_realistic_dirt(spark, cfg):
    df = G.generate_scada_turbine(spark, cfg, date(2024, 3, 25), date(2024, 4, 5)).cache()
    # 3 formatos de fecha: ISO con offset, epoch ms y dd/MM/yyyy
    assert df.where(F.col("ts").like("%-03:00")).count() > 0
    assert df.where(F.col("ts_epoch_ms").isNotNull()).count() > 0
    assert df.where(F.col("ts").rlike(r"^\d{2}/\d{2}/\d{4}")).count() > 0
    # PEI manda MW: valores < 5 con viento
    pei = df.where(F.col("site").isin("GAR", "PAM") & (F.col("sensors.wind_ms") > 9))
    assert pei.agg(F.max("sensors.active_power")).first()[0] < 5
    # duplicados (mismo turbine + ts) y re-envíos que llegan otro día
    dups = df.groupBy("turbine", "ts", "ts_epoch_ms").count().where("count > 1").count()
    assert dups > 0
    # hay nulos
    assert df.where(F.col("sensors.main_bearing_c").isNull()).count() > 0


def test_scada_schema_drift_only_after_firmware(spark, cfg):
    df = G.generate_scada_turbine(spark, cfg, D0, D1)
    new = df.where(F.col("sensors.oil_particle_count").isNotNull())
    assert new.where(F.col("fw") != "HT-OS 5.0").count() == 0
    assert new.count() > 0


def test_inverter_late_and_unit_bug(spark, cfg):
    df = G.generate_inverter_5min(spark, cfg, date(2024, 2, 20), date(2024, 2, 29)).cache()
    assert df.count() > 0
    fia = df.where((F.col("plant") == "FIA") & (F.col("poa_irradiance_wm2") > 800))
    assert fia.agg(F.max("ac_power_kw")).first()[0] < 5  # MW disfrazados de kW
    assert "soiling_sensor_pct" in df.columns


def test_small_sources_formats(spark, cfg):
    spot = G.generate_cammesa_spot_prices(spark, cfg, D0, D1)
    row = spot.first()
    assert "," in row.PRECIO_ARS_MWH and 1 <= row.HORA <= 24
    assert spot.where("HORA = 24").count() > 0
    wo = G.generate_cmms_work_orders(spark, cfg, date(2023, 1, 1), date(2023, 6, 30))
    assert {r.op for r in wo.select("op").distinct().collect()} >= {"I", "U"}
