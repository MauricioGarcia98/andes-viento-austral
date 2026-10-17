-- =============================================================================
-- mart_warranty_claims: disponibilidad contractual vs. garantía del fabricante (97 %)
-- -----------------------------------------------------------------------------
-- Contrato de garantía (estilo IEC 61400-26, simplificado):
--   * período útil = horas del período - excluidas (red, hielo, mantenimiento programado,
--     sin dato) ; las horas de ruta cortada por nieve son fuerza mayor y tampoco cuentan;
--   * disponibilidad = 1 - horas de falla imputables / período útil, en ventana móvil de 12 meses;
--   * si queda < 97 %: liquidated damages = puntos faltantes x USD/punto/MW x MW instalados / 12.
-- Grano: parque eólico x mes (cada parque tiene un solo fabricante).
-- =============================================================================
CREATE OR REPLACE TABLE ${gold}.mart_warranty_claims
USING DELTA
COMMENT 'Disponibilidad contractual mensual y móvil 12 meses por parque/fabricante y reclamo estimado'
AS
WITH m AS (
    SELECT park_code, trunc(reading_date, 'MM') AS month_start,
           max(manufacturer) AS manufacturer,
           count(DISTINCT turbine_id) AS turbines,
           sum(fault_h) AS fault_h,
           sum(24 - excluded_h) AS useful_h,
           sum(icing_h) AS icing_h, sum(curtailed_h) AS curtailed_h, sum(maintenance_h) AS maintenance_h,
           sum(no_data_h) AS no_data_h,
           sum(lost_fault_mwh) AS lost_fault_mwh
    FROM ${gold}.fact_availability_daily
    GROUP BY ALL
),
fm AS (  -- fuerza mayor: horas de acceso cortado (nieve) en órdenes correctivas
    SELECT park_code, trunc(created_date, 'MM') AS month_start,
           sum(coalesce(access_delay_h, 0)) AS access_delay_h,
           count(CASE WHEN severity = 'MAYOR' THEN 1 END) AS major_failures
    FROM ${gold}.fact_maintenance_order
    WHERE order_type = 'CORRECTIVA'
    GROUP BY ALL
),
j AS (
    SELECT m.*, coalesce(fm.access_delay_h, 0) AS force_majeure_h, coalesce(fm.major_failures, 0) AS major_failures,
           greatest(m.fault_h - coalesce(fm.access_delay_h, 0), 0) AS chargeable_fault_h
    FROM m LEFT JOIN fm USING (park_code, month_start)
),
r AS (
    SELECT j.*,
           sum(chargeable_fault_h) OVER w12 AS fault_12m_h,
           sum(useful_h) OVER w12           AS useful_12m_h,
           count(*) OVER w12                AS months_in_window
    FROM j
    WINDOW w12 AS (PARTITION BY park_code ORDER BY month_start ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)
)
SELECT
    r.park_code,
    p.park_name,
    r.manufacturer,
    r.month_start,
    date_format(r.month_start, 'yyyy-MM')                               AS year_month,
    r.turbines,
    p.installed_mw,
    round(r.fault_h, 1)                                                 AS fault_h,
    round(r.force_majeure_h, 1)                                         AS force_majeure_h,
    round(r.chargeable_fault_h, 1)                                      AS chargeable_fault_h,
    round(r.useful_h, 1)                                                AS useful_h,
    round(r.icing_h, 1)                                                 AS icing_h,
    round(r.curtailed_h, 1)                                             AS curtailed_h,
    r.major_failures,
    round(r.lost_fault_mwh, 2)                                          AS lost_fault_mwh,
    round(1 - r.chargeable_fault_h / nullif(r.useful_h, 0), 5)          AS availability_month,
    round(1 - r.fault_12m_h / nullif(r.useful_12m_h, 0), 5)             AS availability_12m,
    p.guaranteed_availability,
    r.months_in_window,
    round(greatest(0, p.guaranteed_availability - (1 - r.fault_12m_h / nullif(r.useful_12m_h, 0))) * 100, 3)
                                                                        AS shortfall_points,
    round(greatest(0, p.guaranteed_availability - (1 - r.fault_12m_h / nullif(r.useful_12m_h, 0))) * 100
          * p.ld_usd_per_point_mw * p.installed_mw / 12, 0)             AS ld_accrued_usd,
    (1 - r.fault_12m_h / nullif(r.useful_12m_h, 0)) < p.guaranteed_availability AND r.months_in_window = 12
                                                                        AS claim_eligible
FROM r
JOIN ${gold}.dim_park p USING (park_code);
