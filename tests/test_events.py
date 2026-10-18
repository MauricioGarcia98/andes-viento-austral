"""Tablas guía del driver: determinismo e historia guionada."""

from datetime import date

from andes_viento.config import ProjectConfig
from andes_viento.datagen import events as E
from andes_viento.datagen import reference as R


def test_fleet_scales_and_totals():
    full = ProjectConfig(scale_factor=1.0)
    assert len(E.fleet(full, "WTG")) == 380
    assert len(E.fleet(full, "INV")) == 220
    assert abs(sum(u.panels for u in E.fleet(full, "INV")) - 1_200_000) < 500  # 1,2 M de paneles
    small = ProjectConfig(scale_factor=0.01)
    assert all(n >= 1 for n in E.park_units(small).values())  # todo parque existe a cualquier escala


def test_weather_series_is_prefix_stable():
    """El día D es idéntico pidiendo la historia hasta D o hasta D+100 (job diario)."""
    cfg = ProjectConfig(scale_factor=0.1)
    a = E.park_day_index(cfg, date(2024, 3, 1))
    b = E.park_day_index(cfg, date(2024, 6, 9))
    assert a[("LEO", date(2024, 3, 1))] == b[("LEO", date(2024, 3, 1))]


def test_story_failure_and_grid_maintenance_exist():
    cfg = ProjectConfig(scale_factor=0.1)
    story = R.STORY["leo_july_2025"]
    ev = [e for e in E.downtime_events(cfg, date(2025, 9, 30)) if e["park"] == "LEO" and e["kind"] == "MAJOR_FAILURE"]
    assert any(abs(e["start"] - E.local_epoch(story["gearbox_failure"], 12)) < 86_400 for e in ev)
    big = [e for e in ev if e["component"] == "GEARBOX"]
    assert any(round((e["end"] - e["start"]) / 86_400) == 21 for e in big)
    ins = E.curtailment_instructions(cfg, date(2025, 7, 31))
    assert sum(1 for i in ins if i["park"] == "LEO" and i["reason"] == "MANTENIMIENTO_ET") == 11


def test_no_overlapping_downtime():
    cfg = ProjectConfig(scale_factor=0.05)
    by_asset = {}
    for e in E.downtime_events(cfg, date(2024, 12, 31)):
        by_asset.setdefault(e["asset_id"], []).append(e)
    for evs in by_asset.values():
        evs.sort(key=lambda x: x["start"])
        assert all(a["end"] <= b["start"] for a, b in zip(evs, evs[1:], strict=False))


def test_fx_devaluation_and_inflation():
    assert E.fx_rate(date(2023, 12, 12)) < 400 < 790 < E.fx_rate(date(2023, 12, 13))
    assert E.cpi_index(date(2025, 1, 1)) > 5  # inflación acumulada 2023-2024 brutal
    assert E.labor_rate_ars(date(2026, 1, 1)) > E.labor_rate_ars(date(2024, 1, 1))
