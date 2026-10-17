-- =============================================================================
-- mart_turbine_health: salud diaria de cada turbina (mantenimiento predictivo)
-- -----------------------------------------------------------------------------
-- Idea (Ingeniería de Confiabilidad + Data Science): una multiplicadora o un rodamiento
-- que se está por romper CALIENTA más que sus vecinas con el MISMO viento, y vibra más
-- que su propia historia. Comparar contra los pares del parque el mismo día elimina el
-- efecto del clima y de la carga.
--
--   residuo_t  = temperatura de la turbina - promedio del resto del parque (mismo día)
--   tendencia  = promedio móvil de 7 días del residuo
--   vib_ratio  = vibración 7 días / vibración de los 30 días previos
--   health_score 100 = sana; < 60 = riesgo ALTO (abrir orden PREDICTIVA)
--
-- Etiqueta para evaluar el modelo: ¿hubo falla MAYOR en los 30 días siguientes?
-- =============================================================================
CREATE OR REPLACE TABLE ${gold}.mart_turbine_health
USING DELTA
COMMENT 'Salud diaria por turbina: residuos térmicos vs. pares, vibración, alarmas y riesgo de falla'
AS
WITH d AS (
    SELECT turbine_id, park_code, reading_date, max(turbine_key) AS turbine_key,
           avg(CASE WHEN state IN ('PRODUCIENDO', 'LIMITADA_RED') THEN gearbox_bearing_c END)   AS gearbox_c,
           avg(CASE WHEN state IN ('PRODUCIENDO', 'LIMITADA_RED') THEN main_bearing_c END)      AS main_bearing_c,
           avg(CASE WHEN state IN ('PRODUCIENDO', 'LIMITADA_RED') THEN generator_bearing_c END) AS generator_bearing_c,
           avg(CASE WHEN state IN ('PRODUCIENDO', 'LIMITADA_RED') THEN vibration_mm_s END)      AS vibration_mm_s,
           avg(CASE WHEN state IN ('PRODUCIENDO', 'LIMITADA_RED') THEN oil_particle_count END)  AS oil_particles,
           sum(CASE WHEN state IN ('PRODUCIENDO', 'LIMITADA_RED') THEN 1 ELSE 0 END)            AS running_readings,
           sum(CASE WHEN exists(alarms, a -> a LIKE '%-WRN') THEN 1 ELSE 0 END)                 AS warning_alarms,
           sum(CASE WHEN state = 'FALLA' THEN 1 ELSE 0 END) / 6                                  AS fault_hours
    FROM ${gold}.fact_turbine_10min
    GROUP BY turbine_id, park_code, reading_date
),
peers AS (
    -- promedio del RESTO del parque ese día = (suma del parque - la propia) / (n - 1)
    SELECT d.*,
           ((sum(gearbox_c) OVER pd) - gearbox_c) / nullif((count(gearbox_c) OVER pd) - 1, 0)               AS peer_gearbox_c,
           ((sum(main_bearing_c) OVER pd) - main_bearing_c) / nullif((count(main_bearing_c) OVER pd) - 1, 0) AS peer_main_c,
           ((sum(generator_bearing_c) OVER pd) - generator_bearing_c)
               / nullif((count(generator_bearing_c) OVER pd) - 1, 0)                                         AS peer_generator_c
    FROM d
    WINDOW pd AS (PARTITION BY park_code, reading_date)
),
feat AS (
    SELECT p.*,
           gearbox_c - peer_gearbox_c            AS gearbox_residual_c,
           main_bearing_c - peer_main_c          AS main_bearing_residual_c,
           generator_bearing_c - peer_generator_c AS generator_residual_c,
           avg(gearbox_c - peer_gearbox_c) OVER w7            AS gearbox_residual_7d,
           avg(main_bearing_c - peer_main_c) OVER w7          AS main_bearing_residual_7d,
           avg(generator_bearing_c - peer_generator_c) OVER w7 AS generator_residual_7d,
           avg(vibration_mm_s) OVER w7                        AS vibration_7d,
           avg(vibration_mm_s) OVER w30_prev                  AS vibration_baseline,
           sum(warning_alarms) OVER w7                        AS warnings_7d
    FROM peers p
    WINDOW w7 AS (PARTITION BY turbine_id ORDER BY reading_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),
           w30_prev AS (PARTITION BY turbine_id ORDER BY reading_date ROWS BETWEEN 37 PRECEDING AND 7 PRECEDING)
),
failures AS (
    SELECT asset_id AS turbine_id, to_date(from_utc_timestamp(failure_ts, 'America/Argentina/Buenos_Aires')) AS failure_date,
           component AS failure_component, order_id
    FROM ${gold}.fact_maintenance_order
    WHERE order_type = 'CORRECTIVA' AND severity = 'MAYOR'
),
scored AS (
    SELECT f.*,
           greatest(coalesce(gearbox_residual_7d, 0), coalesce(main_bearing_residual_7d, 0),
                    coalesce(generator_residual_7d, 0))                                   AS max_residual_7d,
           vibration_7d / nullif(vibration_baseline, 0)                                   AS vibration_ratio
    FROM feat f
),
nf AS (
    SELECT s.turbine_id, s.reading_date,
           min(fl.failure_date)                            AS failure_date,
           min_by(fl.failure_component, fl.failure_date)   AS failure_component
    FROM scored s
    JOIN failures fl ON fl.turbine_id = s.turbine_id AND fl.failure_date > s.reading_date
    GROUP BY s.turbine_id, s.reading_date
)
SELECT
    cast(date_format(s.reading_date, 'yyyyMMdd') AS INT)                     AS date_key,
    s.reading_date,
    s.turbine_key,
    s.turbine_id,
    s.park_code,
    round(s.gearbox_c, 2)                AS gearbox_c,
    round(s.gearbox_residual_c, 2)       AS gearbox_residual_c,
    round(s.gearbox_residual_7d, 2)      AS gearbox_residual_7d,
    round(s.main_bearing_residual_7d, 2) AS main_bearing_residual_7d,
    round(s.generator_residual_7d, 2)    AS generator_residual_7d,
    round(s.vibration_7d, 3)             AS vibration_7d,
    round(s.vibration_ratio, 3)          AS vibration_ratio,
    round(s.oil_particles, 0)            AS oil_particles,
    s.warnings_7d,
    s.running_readings,
    round(s.fault_hours, 2)              AS fault_hours,
    round(greatest(0, least(100,
        100 - 7 * greatest(0, s.max_residual_7d - 1.5)
            - 60 * greatest(0, coalesce(s.vibration_ratio, 1) - 1.15)
            - 2 * least(s.warnings_7d, 10))), 1)                              AS health_score,
    CASE
        WHEN s.running_readings < 12 THEN 'SIN_DATOS_SUFICIENTES'
        WHEN 100 - 7 * greatest(0, s.max_residual_7d - 1.5) - 60 * greatest(0, coalesce(s.vibration_ratio, 1) - 1.15)
             - 2 * least(s.warnings_7d, 10) < 60 THEN 'ALTO'
        WHEN 100 - 7 * greatest(0, s.max_residual_7d - 1.5) - 60 * greatest(0, coalesce(s.vibration_ratio, 1) - 1.15)
             - 2 * least(s.warnings_7d, 10) < 80 THEN 'MEDIO'
        ELSE 'BAJO'
    END                                                                       AS risk_level,
    CASE greatest(coalesce(s.gearbox_residual_7d, -99), coalesce(s.main_bearing_residual_7d, -99),
                  coalesce(s.generator_residual_7d, -99))
        WHEN s.gearbox_residual_7d THEN 'GEARBOX'
        WHEN s.main_bearing_residual_7d THEN 'MAIN_BEARING'
        ELSE 'GENERATOR_BEARING'
    END                                                                       AS suspected_component,
    nf.failure_date                                                           AS next_major_failure_date,
    nf.failure_component                                                      AS next_major_failure_component,
    datediff(nf.failure_date, s.reading_date)                                 AS days_to_failure,
    coalesce(datediff(nf.failure_date, s.reading_date) BETWEEN 1 AND 30, false) AS failure_within_30d
FROM scored s
LEFT JOIN nf USING (turbine_id, reading_date);
