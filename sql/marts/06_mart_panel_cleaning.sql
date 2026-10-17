-- =============================================================================
-- mart_panel_cleaning: ¿cuándo conviene limpiar los paneles de la Puna?
-- -----------------------------------------------------------------------------
-- El polvo baja la generación de a poco; limpiar cuesta agua (escasa y cara: va en
-- camión cisterna) y cuadrilla. Regla económica (umbral):
--     limpiar cuando  la plata perdida desde la última limpieza >= costo de una limpieza
-- salvo que el pronóstico traiga lluvia (> 4 mm), que limpia gratis.
--
-- Suciedad estimada = 1 - PR / PR_referencia, donde PR = generado / esperado "limpio"
-- (irradiancia x potencia DC x temperatura) y PR_referencia = percentil 95 del parque.
-- Desde junio 2025 hay sensores de suciedad: sirven para validar la estimación.
-- =============================================================================
CREATE OR REPLACE TABLE ${gold}.mart_panel_cleaning
USING DELTA
COMMENT 'Suciedad diaria estimada por parque solar, pérdida acumulada en USD y recomendación de limpieza'
AS
WITH d AS (
    SELECT park_code, reading_date,
           sum(energy_kwh) / 1000                                            AS actual_mwh,
           sum(expected_clean_kwh * (1 - fault_readings / readings)) / 1000  AS expected_mwh,
           sum(poa_irradiation_kwh_m2) / count(DISTINCT inverter_id)         AS irradiation_kwh_m2,
           avg(soiling_sensor_pct)                                           AS soiling_sensor_pct
    FROM ${gold}.fact_inverter_hourly
    GROUP BY park_code, reading_date
),
pr AS (
    SELECT d.*, actual_mwh / nullif(expected_mwh, 0) AS pr
    FROM d WHERE expected_mwh > 0
),
ref AS (
    SELECT park_code, percentile_approx(pr, 0.95) AS pr_ref FROM pr GROUP BY park_code
),
cost_ref AS (  -- antes de la primera limpieza registrada se usa el costo mediano del parque
    SELECT park_code, percentile_approx(total_cost_usd, 0.5) AS median_cleaning_cost_usd
    FROM ${gold}.fact_maintenance_order WHERE order_type = 'LIMPIEZA' GROUP BY park_code
),
cleanings AS (
    SELECT park_code, to_date(from_utc_timestamp(work_end_ts, 'America/Argentina/Buenos_Aires')) AS clean_end_date,
           to_date(from_utc_timestamp(work_start_ts, 'America/Argentina/Buenos_Aires')) AS clean_start_date,
           total_cost_usd, water_m3
    FROM ${gold}.fact_maintenance_order
    WHERE order_type = 'LIMPIEZA' AND work_end_ts IS NOT NULL
),
cleaning_days AS (
    SELECT DISTINCT park_code, explode(sequence(clean_start_date, clean_end_date)) AS reading_date FROM cleanings
),
cal AS (
    SELECT p.*, r.pr_ref,
           greatest(0, least(0.4, 1 - p.pr / r.pr_ref))                              AS soiling_loss_pct,
           greatest(0, p.expected_mwh * r.pr_ref - p.actual_mwh)                      AS soiling_lost_mwh,
           c.clean_end_date, c.total_cost_usd AS cleaning_cost_usd, c.water_m3 AS cleaning_water_m3,
           cd.park_code IS NOT NULL AS is_cleaning_day
    FROM pr p
    JOIN ref r ON r.park_code = p.park_code
    LEFT JOIN cleanings c ON c.park_code = p.park_code AND c.clean_end_date = p.reading_date
    LEFT JOIN cleaning_days cd ON cd.park_code = p.park_code AND cd.reading_date = p.reading_date
),
w AS (
    SELECT cal.*,
           last_value(clean_end_date, true) OVER (PARTITION BY park_code ORDER BY reading_date)    AS last_cleaning_date,
           coalesce(last_value(cleaning_cost_usd, true) OVER (PARTITION BY park_code ORDER BY reading_date),
                    cr.median_cleaning_cost_usd)                                                   AS last_cleaning_cost_usd,
           last_value(cleaning_water_m3, true) OVER (PARTITION BY park_code ORDER BY reading_date) AS last_cleaning_water_m3,
           count(clean_end_date) OVER (PARTITION BY park_code ORDER BY reading_date)               AS cleaning_epoch
    FROM cal
    LEFT JOIN cost_ref cr USING (park_code)
),
priced AS (
    SELECT w.*,
           coalesce(pp.ppa_price_usd_mwh, 55.0)                                       AS price_usd_mwh,
           wx.weather_condition,
           wx.precip_mm,
           lead(wx.forecast_precip_mm, 1) OVER (PARTITION BY w.park_code ORDER BY w.reading_date) AS rain_forecast_tomorrow_mm
    FROM w
    LEFT JOIN ${gold}.v_park_price_month pp ON pp.park_code = w.park_code AND pp.month_start = trunc(w.reading_date, 'MM')
    LEFT JOIN ${gold}.dim_weather wx ON wx.park_code = w.park_code AND wx.date = w.reading_date
),
acc AS (
    SELECT priced.*,
           soiling_lost_mwh * price_usd_mwh                                           AS soiling_lost_usd,
           sum(soiling_lost_mwh * price_usd_mwh) OVER (PARTITION BY park_code, cleaning_epoch ORDER BY reading_date)
                                                                                      AS lost_usd_since_cleaning,
           avg(soiling_lost_mwh * price_usd_mwh) OVER (PARTITION BY park_code ORDER BY reading_date
                                                       ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS lost_usd_per_day_7d
    FROM priced
)
SELECT
    cast(date_format(reading_date, 'yyyyMMdd') AS INT)       AS date_key,
    reading_date,
    park_code,
    round(actual_mwh, 3)                                     AS actual_mwh,
    round(expected_mwh, 3)                                   AS expected_clean_mwh,
    round(pr, 4)                                             AS performance_ratio,
    round(pr_ref, 4)                                         AS performance_ratio_ref,
    round(soiling_loss_pct, 4)                               AS soiling_loss_pct,
    round(soiling_sensor_pct / 100, 4)                       AS soiling_sensor_pct,
    round(soiling_lost_mwh, 3)                               AS soiling_lost_mwh,
    price_usd_mwh,
    round(soiling_lost_usd, 2)                               AS soiling_lost_usd,
    last_cleaning_date,
    datediff(reading_date, last_cleaning_date)               AS days_since_cleaning,
    round(lost_usd_since_cleaning, 2)                        AS lost_usd_since_cleaning,
    round(last_cleaning_cost_usd, 2)                         AS cleaning_cost_usd,
    last_cleaning_water_m3                                   AS cleaning_water_m3,
    round(last_cleaning_cost_usd / nullif(lost_usd_per_day_7d, 0), 1) AS breakeven_days,
    is_cleaning_day,
    weather_condition,
    precip_mm,
    rain_forecast_tomorrow_mm,
    CASE
        WHEN is_cleaning_day THEN 'LIMPIANDO'
        WHEN coalesce(rain_forecast_tomorrow_mm, 0) > 4 THEN 'ESPERAR_LLUVIA'
        WHEN lost_usd_since_cleaning >= last_cleaning_cost_usd THEN 'LIMPIAR'
        ELSE 'ESPERAR'
    END                                                      AS recommendation
FROM acc;
