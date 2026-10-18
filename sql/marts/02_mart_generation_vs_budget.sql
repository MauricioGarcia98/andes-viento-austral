-- =============================================================================
-- mart_generation_vs_budget: real vs. presupuesto P50, con la cascada de pérdidas
-- -----------------------------------------------------------------------------
-- Pregunta que responde: "¿por qué el parque X generó N % menos que el presupuesto?"
--
-- Identidad (en MWh, por parque y mes):
--   presupuesto = potencial_presupuestado x disponibilidad_supuesta x (1 - curtailment_supuesto)
--   real        = potencial_real - curtailment - fallas - mantenimiento - hielo - otras
--   desvío      = recurso (viento/sol) - exceso_curtailment - exceso_indisponibilidad - hielo - otras
-- Cada término es una columna: Genie puede explicar el desvío sumando columnas.
-- Usa el presupuesto ORIGINAL aprobado por el directorio (versión v1). En el mes en curso el
-- presupuesto se prorratea por días con datos (is_month_to_date = true).
-- =============================================================================
CREATE OR REPLACE TABLE ${gold}.mart_generation_vs_budget
USING DELTA
COMMENT 'Generación real vs. presupuesto P50 por parque y mes, con descomposición del desvío'
AS
WITH wind AS (
    SELECT park_code,
           trunc(reading_date, 'MM')                 AS month_start,
           sum(energy_kwh) / 1000                    AS generated_mwh,
           sum(potential_kwh) / 1000                 AS potential_mwh,
           sum(lost_curtailment_kwh) / 1000          AS lost_curtailment_mwh,
           sum(lost_fault_kwh) / 1000                AS lost_fault_mwh,
           sum(lost_maintenance_kwh) / 1000          AS lost_maintenance_mwh,
           sum(lost_icing_kwh) / 1000                AS lost_icing_mwh,
           0D                                        AS lost_soiling_mwh,
           count(*)                                  AS readings,
           144 * count(DISTINCT turbine_id, reading_date) AS expected_readings,
           count(DISTINCT reading_date)              AS days_with_data
    FROM ${gold}.fact_turbine_10min
    GROUP BY ALL
),
solar AS (
    SELECT park_code,
           trunc(reading_date, 'MM')                 AS month_start,
           sum(energy_kwh) / 1000                    AS generated_mwh,
           sum(expected_clean_kwh) / 1000            AS potential_mwh,
           0D                                        AS lost_curtailment_mwh,
           sum(expected_clean_kwh * fault_readings / readings) / 1000 AS lost_fault_mwh,
           0D                                        AS lost_maintenance_mwh,
           0D                                        AS lost_icing_mwh,
           greatest(sum(expected_clean_kwh * (1 - fault_readings / readings)) - sum(energy_kwh), 0) / 1000
                                                     AS lost_soiling_mwh,
           sum(readings)                             AS readings,
           sum(readings)                             AS expected_readings,
           count(DISTINCT reading_date)              AS days_with_data
    FROM ${gold}.fact_inverter_hourly
    GROUP BY ALL
),
actual AS (SELECT * FROM wind UNION ALL SELECT * FROM solar),
budget AS (
    SELECT park_code, month_start,
           max(CASE WHEN version LIKE '%-v1' THEN budget_p50_mwh END)       AS budget_p50_mwh,
           max(CASE WHEN version LIKE '%-v1' THEN budget_p90_mwh END)       AS budget_p90_mwh,
           max(CASE WHEN version LIKE '%-v2' THEN budget_p50_mwh END)       AS reforecast_p50_mwh,
           max(CASE WHEN version LIKE '%-v1' THEN assumed_availability END) AS assumed_availability,
           max(CASE WHEN version LIKE '%-v1' THEN assumed_curtailment END)  AS assumed_curtailment
    FROM ${silver}.generation_budget
    GROUP BY ALL
),
j AS (
    SELECT a.*,
           -- huecos de comunicación: se estiman con el promedio del mes (la factura usa el medidor SMEC)
           greatest(a.expected_readings - a.readings, 0) * a.generated_mwh / a.readings AS data_gap_mwh,
           greatest(a.expected_readings - a.readings, 0) * a.potential_mwh / a.readings AS data_gap_potential_mwh,
           -- mes en curso (el job diario trae día a día): el presupuesto se prorratea por los días con datos
           a.days_with_data < day(last_day(a.month_start))                          AS is_month_to_date,
           b.budget_p50_mwh * least(1, a.days_with_data / day(last_day(a.month_start)))     AS budget_p50_mwh,
           b.budget_p90_mwh * least(1, a.days_with_data / day(last_day(a.month_start)))     AS budget_p90_mwh,
           b.reforecast_p50_mwh * least(1, a.days_with_data / day(last_day(a.month_start))) AS reforecast_p50_mwh,
           b.assumed_availability, b.assumed_curtailment
    FROM actual a
    LEFT JOIN budget b USING (park_code, month_start)
)
SELECT
    j.park_code,
    p.park_name,
    p.technology,
    p.province,
    p.region,
    j.month_start,
    date_format(j.month_start, 'yyyy-MM')                                    AS year_month,
    year(j.month_start)                                                      AS year,
    month(j.month_start)                                                     AS month,
    j.is_month_to_date,
    j.days_with_data,
    round(j.generated_mwh + j.data_gap_mwh, 2)                               AS actual_mwh,
    round(j.generated_mwh, 2)                                                AS scada_mwh,
    round(j.data_gap_mwh, 2)                                                 AS data_gap_mwh,
    round(j.potential_mwh + j.data_gap_potential_mwh, 2)                     AS potential_mwh,
    round(j.budget_p50_mwh, 2)                                               AS budget_p50_mwh,
    round(j.budget_p90_mwh, 2)                                               AS budget_p90_mwh,
    round(j.reforecast_p50_mwh, 2)                                           AS reforecast_p50_mwh,
    round(j.generated_mwh + j.data_gap_mwh - j.budget_p50_mwh, 2)            AS variance_mwh,
    round((j.generated_mwh + j.data_gap_mwh) / j.budget_p50_mwh - 1, 4)      AS variance_pct,
    -- cascada del desvío
    round(j.budget_p50_mwh / (j.assumed_availability * (1 - j.assumed_curtailment)), 2) AS budget_potential_mwh,
    round(j.potential_mwh + j.data_gap_potential_mwh
          - j.budget_p50_mwh / (j.assumed_availability * (1 - j.assumed_curtailment)), 2) AS resource_effect_mwh,
    round(j.lost_curtailment_mwh, 2)                                         AS lost_curtailment_mwh,
    round(j.lost_fault_mwh, 2)                                               AS lost_fault_mwh,
    round(j.lost_maintenance_mwh, 2)                                         AS lost_maintenance_mwh,
    round(j.lost_icing_mwh, 2)                                               AS lost_icing_mwh,
    round(j.lost_soiling_mwh, 2)                                             AS lost_soiling_mwh,
    -- "otras" cierra la identidad: performance, sobre-producción (negativo) y huecos de dato
    round(j.potential_mwh + j.data_gap_potential_mwh - j.generated_mwh - j.data_gap_mwh - j.lost_curtailment_mwh
          - j.lost_fault_mwh - j.lost_maintenance_mwh - j.lost_icing_mwh - j.lost_soiling_mwh, 2) AS lost_other_mwh,
    round(j.budget_p50_mwh / (1 - j.assumed_curtailment) * j.assumed_curtailment, 2) AS budget_curtailment_allowance_mwh,
    round(j.budget_p50_mwh / (j.assumed_availability * (1 - j.assumed_curtailment))
          * (1 - j.assumed_availability), 2)                                 AS budget_availability_allowance_mwh,
    j.assumed_availability,
    j.assumed_curtailment,
    round(j.readings / j.expected_readings, 4)                               AS data_completeness,
    pr.ppa_price_usd_mwh,
    round((j.generated_mwh + j.data_gap_mwh - j.budget_p50_mwh) * pr.ppa_price_usd_mwh, 0) AS variance_value_usd
FROM j
JOIN ${gold}.dim_park p USING (park_code)
LEFT JOIN ${gold}.v_park_price_month pr USING (park_code, month_start);
