from datetime import datetime

from pyspark.sql import functions as F

from andes_viento.silver.scd2 import scd2_merge


def _df(spark, rows):
    return spark.createDataFrame(rows, "asset_id string, asset_tag string, firmware string, updated_at timestamp, "
                                       "is_deleted boolean")


def test_scd2_history_resends_and_late_changes(spark, cfg):
    target = cfg.table("silver", "assets_history_test")
    d = lambda day: datetime(2024, 6, day, 10)  # noqa: E731
    scd2_merge(spark, _df(spark, [("A", "CRV-07", "4.1", d(1), False), ("A", "CRV-07", "4.1", d(2), False),
                                  ("A", "CRV-WTG007", "4.1", d(3), False)]),
               target, ["asset_id"], ["asset_tag", "firmware"])
    scd2_merge(spark, _df(spark, [("A", "CRV-WTG007", "5.0", d(10), False),     # cambio nuevo
                                  ("A", "CRV-07", "4.1", d(1), False)]),        # llegada tardía vieja: se ignora
               target, ["asset_id"], ["asset_tag", "firmware"])
    rows = spark.table(target).orderBy("valid_from").collect()
    assert [(r.asset_tag, r.firmware, r.is_current) for r in rows] == [
        ("CRV-07", "4.1", False), ("CRV-WTG007", "4.1", False), ("CRV-WTG007", "5.0", True)]
    assert spark.table(target).where("is_current").count() == 1
    # idempotencia: el mismo lote otra vez no cambia nada
    scd2_merge(spark, _df(spark, [("A", "CRV-WTG007", "5.0", d(10), False)]), target, ["asset_id"],
               ["asset_tag", "firmware"])
    assert spark.table(target).count() == 3
    assert spark.table(target).where(F.col("valid_to").isNull()).count() == 1
