-- =============================================================================
-- mart_curtailment_battery: ¿en qué parque conviene poner baterías?
-- -----------------------------------------------------------------------------
-- Simulación simple (diaria) para 3 tamaños de batería relativos al parque:
--   * la batería se carga con la energía que CAMMESA nos obligó a tirar,
--     limitada por su potencia (MW) en cada hora y por su energía (MWh) en el día;
--   * se descarga a la noche (19 a 23 h) y se vende al precio de realización del parque
--     (PPA si tiene contratos; si no, el spot nocturno del nodo);
--   * eficiencia ida y vuelta 88 %, CAPEX 280 USD/kWh (precio 2025, instalado).
-- Grano: parque eólico x opción de batería x mes.
-- =============================================================================
CREATE OR REPLACE TABLE ${gold}.mart_curtailment_battery
COMMENT 'Curtailment mensual por parque y valor que recuperaría cada tamaño de batería'
AS
WITH options AS (
    SELECT * FROM VALUES
        ('BESS-10x4', 0.10, 4.0),
        ('BESS-20x4', 0.20, 4.0),
        ('BESS-30x2', 0.30, 2.0)
    AS t(option_code, power_fraction, duration_h)
),
h AS (
    SELECT f.*, p.installed_mw
    FROM ${gold}.fact_curtailment_hourly f
    JOIN ${gold}.dim_park p USING (park_code)
),
evening AS (
    SELECT park_code, reading_date, avg(spot_usd_mwh) AS evening_spot_usd_mwh
    FROM h WHERE hour(hour_local) BETWEEN 19 AND 22
    GROUP BY ALL
),
hc AS (
    SELECT h.*, o.option_code, o.power_fraction, o.duration_h,
           least(h.lost_curtailment_mwh, h.installed_mw * o.power_fraction) AS hour_charge_mwh
    FROM h CROSS JOIN options o
),
daily AS (
    SELECT option_code, park_code, reading_date,
           max(power_fraction)                                           AS power_fraction,
           max(duration_h)                                               AS duration_h,
           max(installed_mw)                                             AS installed_mw,
           sum(lost_curtailment_mwh)                                     AS lost_mwh,
           sum(lost_value_spot_usd)                                      AS lost_value_spot_usd,
           sum(CASE WHEN curtailed_readings > 0 THEN 1 ELSE 0 END)       AS curtailed_hours,
           least(sum(hour_charge_mwh), max(installed_mw) * max(power_fraction) * max(duration_h)) AS charged_mwh
    FROM hc
    GROUP BY option_code, park_code, reading_date
)
SELECT
    d.park_code,
    d.option_code,
    trunc(d.reading_date, 'MM')                                          AS month_start,
    date_format(trunc(d.reading_date, 'MM'), 'yyyy-MM')                  AS year_month,
    max(d.installed_mw)                                                  AS park_installed_mw,
    round(max(d.installed_mw) * max(d.power_fraction), 2)                AS battery_mw,
    round(max(d.installed_mw) * max(d.power_fraction) * max(d.duration_h), 2) AS battery_mwh,
    round(max(d.installed_mw) * max(d.power_fraction) * max(d.duration_h) * 1000 * 280, 0) AS battery_capex_usd,
    round(sum(d.lost_mwh), 2)                                            AS curtailed_mwh,
    sum(d.curtailed_hours)                                               AS curtailed_hours,
    round(sum(d.lost_mwh * coalesce(pr.ppa_price_usd_mwh, e.evening_spot_usd_mwh)), 2) AS curtailed_value_usd,
    round(sum(d.lost_value_spot_usd), 2)                                 AS curtailed_value_spot_usd,
    round(sum(d.charged_mwh * 0.88), 2)                                  AS recovered_mwh,
    round(sum(d.charged_mwh * 0.88 * coalesce(pr.ppa_price_usd_mwh, e.evening_spot_usd_mwh)), 2) AS recovered_value_usd,
    round(avg(pr.ppa_price_usd_mwh), 2)                                  AS ppa_price_usd_mwh
FROM daily d
LEFT JOIN evening e USING (park_code, reading_date)
LEFT JOIN ${gold}.v_park_price_month pr ON pr.park_code = d.park_code AND pr.month_start = trunc(d.reading_date, 'MM')
GROUP BY d.park_code, d.option_code, trunc(d.reading_date, 'MM');
