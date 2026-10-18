-- =============================================================================
-- v_park_daily: "una sola tabla" por parque y día para Genie y para análisis rápidos
-- -----------------------------------------------------------------------------
-- Junta generación, potencial, pérdidas, presupuesto diario, clima y precio. Genie
-- responde mejor con pocas tablas anchas y bien comentadas que con 20 joins.
-- =============================================================================
CREATE OR REPLACE VIEW ${gold}.v_park_daily
COMMENT 'Vista diaria por parque: generación, pérdidas por causa, presupuesto, disponibilidad, clima y precio'
AS
WITH wind AS (
    SELECT park_code, reading_date,
           sum(energy_kwh) / 1000 AS generated_mwh, sum(potential_kwh) / 1000 AS potential_mwh,
           sum(lost_curtailment_kwh) / 1000 AS lost_curtailment_mwh, sum(lost_fault_kwh) / 1000 AS lost_fault_mwh,
           sum(lost_maintenance_kwh) / 1000 AS lost_maintenance_mwh, sum(lost_icing_kwh) / 1000 AS lost_icing_mwh,
           CAST(NULL AS DOUBLE) AS lost_soiling_mwh,
           avg(wind_used_ms) AS avg_wind_ms
    FROM ${gold}.fact_turbine_10min GROUP BY ALL
),
solar AS (
    SELECT park_code, reading_date, actual_mwh, expected_clean_mwh, 0D, 0D, 0D, 0D, soiling_lost_mwh, CAST(NULL AS DOUBLE)
    FROM ${gold}.mart_panel_cleaning
),
avail AS (
    SELECT park_code, reading_date, avg(availability_contractual) AS availability_contractual
    FROM ${gold}.fact_availability_daily GROUP BY ALL
),
budget AS (
    SELECT b.park_code, d.date AS reading_date, b.budget_p50_mwh / d.days_in_month AS budget_mwh
    FROM ${silver}.generation_budget b JOIN ${gold}.dim_date d ON d.month_start = b.month_start
    WHERE b.version LIKE '%-v1'
)
SELECT
    g.park_code, p.park_name, p.technology, p.province, p.region,
    g.reading_date, d.year_month, d.month_name, d.season, d.is_holiday, d.holiday_name,
    round(g.generated_mwh, 3)        AS generated_mwh,
    round(g.potential_mwh, 3)        AS potential_mwh,
    round(b.budget_mwh, 3)           AS budget_mwh,
    round(g.lost_curtailment_mwh, 3) AS lost_curtailment_mwh,
    round(g.lost_fault_mwh, 3)       AS lost_fault_mwh,
    round(g.lost_maintenance_mwh, 3) AS lost_maintenance_mwh,
    round(g.lost_icing_mwh, 3)       AS lost_icing_mwh,
    round(g.lost_soiling_mwh, 3)     AS lost_soiling_mwh,
    round(g.avg_wind_ms, 2)          AS avg_wind_ms,
    round(a.availability_contractual, 4) AS availability_contractual,
    w.weather_condition, w.temp_min_c, w.snow_cm, w.precip_mm, w.ice_risk_hours,
    p.installed_mw,
    round(g.generated_mwh / (p.installed_mw * 24), 4) AS capacity_factor
FROM (SELECT * FROM wind UNION ALL SELECT * FROM solar) g
JOIN ${gold}.dim_park p USING (park_code)
JOIN ${gold}.dim_date d ON d.date = g.reading_date
LEFT JOIN avail a USING (park_code, reading_date)
LEFT JOIN budget b USING (park_code, reading_date)
LEFT JOIN ${gold}.dim_weather w ON w.park_code = g.park_code AND w.date = g.reading_date;
