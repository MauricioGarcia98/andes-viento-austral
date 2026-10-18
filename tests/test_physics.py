"""La física existe dos veces (Spark y Python): tienen que dar exactamente lo mismo."""

from datetime import date

import pytest
from pyspark.sql import functions as F

from andes_viento.datagen import events as E
from andes_viento.datagen import physics as ph

EPOCHS = [E.local_epoch(date(2025, 7, 15), h) for h in (0.0, 6.5, 13.0, 19.25)] + \
         [E.local_epoch(date(2024, 1, 3), h) for h in (2.0, 15.0)]


def test_power_curve_shape():
    assert ph.power_kw_py(2.0, 4_500, 12.5) == 0
    assert ph.power_kw_py(30.0, 4_500, 12.5) == 0  # cut-out por viento extremo
    assert ph.power_kw_py(14.0, 4_500, 12.5) == 4_500
    assert 0 < ph.power_kw_py(8.0, 4_500, 12.5) < 4_500
    assert ph.power_kw_py(9.0, 4_500, 12.5) > ph.power_kw_py(8.0, 4_500, 12.5)


@pytest.mark.parametrize("park", ["LEO", "RAW", "PAM"])
def test_wind_spark_equals_python(spark, park):
    df = spark.createDataFrame([(e,) for e in EPOCHS], "epoch long")
    local = F.col("epoch") - ph.ART_OFFSET_S
    d = F.date_from_unix_date(F.floor(local / 86_400).cast("int"))
    out = df.select("epoch", ph.wind_ms_col(park, F.col("epoch").cast("double"), F.month(d),
                                            F.pmod(local, F.lit(86_400)) / 3600.0, F.lit(1.1), 0.97, 0.3).alias("w"))
    for row in out.collect():
        assert row.w == pytest.approx(ph.wind_ms_py(park, row.epoch, 1.1, 0.97, 0.3), rel=1e-9)


def test_solar_spark_equals_python(spark):
    df = spark.createDataFrame([(e,) for e in EPOCHS], "epoch long")
    from andes_viento.datagen.reference import PARKS_BY_CODE

    p = PARKS_BY_CODE["SUS"]
    out = df.select("epoch", ph.poa_clear_col(F.lit(p.lat), F.lit(p.lon), F.lit(float(p.altitude_m)),
                                              F.dayofyear(F.date_from_unix_date(F.floor(F.col("epoch") / 86_400)
                                                                                .cast("int"))),
                                              F.pmod(F.col("epoch"), F.lit(86_400)) / 3600.0).alias("poa"))
    rows = out.collect()
    for row in rows:
        assert row.poa == pytest.approx(ph.poa_clear_py("SUS", row.epoch), abs=1e-6)
    assert any(r.poa > 800 for r in rows) and any(r.poa == 0 for r in rows)  # mediodía y noche


def test_puna_is_cold_and_patagonia_winter_is_cold():
    assert ph.temp_c_py("SUS", E.local_epoch(date(2025, 7, 15), 6)) < 0  # helada en la Puna
    jan = ph.temp_c_py("LEO", E.local_epoch(date(2025, 1, 15), 15))
    jul = ph.temp_c_py("LEO", E.local_epoch(date(2025, 7, 15), 15))
    assert jan - jul > 10
