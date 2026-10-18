import pytest

from andes_viento.quality.expectations import DataQualityError, Rule, enforce


def test_enforce_quarantine_and_fail(spark, cfg):
    df = spark.createDataFrame([(1, 10.0), (2, None), (3, -5.0)], "id int, ars_per_usd double")
    rules = [Rule("informado", "ars_per_usd IS NOT NULL"), Rule("positivo", "ars_per_usd > 0", "warn")]
    valid = enforce(spark, cfg, df, rules, "test.fx")
    assert sorted(r.id for r in valid.collect()) == [1, 3]   # el NULL va a cuarentena, el negativo sólo avisa
    q = spark.table(cfg.table("ops", "quarantine")).where("table_name = 'test.fx'")
    assert q.count() == 1
    with pytest.raises(DataQualityError):
        enforce(spark, cfg, df, [Rule("positivo_fail", "ars_per_usd > 0", "fail")], "test.fx")
