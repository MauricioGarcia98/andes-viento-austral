-- =============================================================================
-- FUNCIONES DE UC = "trusted assets" de los Genie Agents
-- -----------------------------------------------------------------------------
-- Cuando una pregunta tiene una respuesta CERTIFICADA (la calcula siempre igual el área
-- dueña), se escribe como función. Genie la invoca con parámetros y marca la respuesta
-- como confiable ("Trusted"). Parámetros con DEFAULT NULL = "todos".
-- Los parques se pueden pasar por código (LEO) o por nombre (Cañadón León).
-- Error real (bitácora): Genie NO acepta parámetros DATE en funciones confiables
-- ("certified answer argument type is not supported: date"): las fechas van como STRING 'yyyy-MM-dd'.
-- =============================================================================

CREATE OR REPLACE FUNCTION ${gold}.fn_perdida_curtailment(
    p_parque STRING DEFAULT NULL COMMENT 'Código o nombre del parque; NULL, vacío o TODOS = todos',
    p_desde STRING DEFAULT NULL COMMENT 'Fecha inicial yyyy-MM-dd (incluida); NULL = desde el inicio',
    p_hasta STRING DEFAULT NULL COMMENT 'Fecha final yyyy-MM-dd (incluida); NULL = hasta el último dato')
RETURNS TABLE (park_name STRING, curtailed_mwh DOUBLE, curtailed_pct_of_potential DOUBLE,
               value_at_spot_usd DOUBLE, value_at_ppa_usd DOUBLE, hours_with_order BIGINT)
COMMENT 'Energía perdida por curtailment (MWh), % del potencial y su valor a spot y a precio PPA, por parque'
RETURN
    SELECT p.park_name,
           round(sum(f.lost_curtailment_mwh), 1),
           round(sum(f.lost_curtailment_mwh) / sum(f.potential_mwh), 4),
           round(sum(f.lost_value_spot_usd), 0),
           round(sum(f.lost_curtailment_mwh * coalesce(pr.ppa_price_usd_mwh, f.spot_usd_mwh)), 0),
           count_if(f.has_instruction)
    FROM ${gold}.fact_curtailment_hourly f
    JOIN ${gold}.dim_park p ON p.park_key = f.park_key
    LEFT JOIN ${gold}.v_park_price_month pr ON pr.park_code = f.park_code AND pr.month_start = trunc(f.reading_date, 'MM')
    WHERE (coalesce(upper(trim(p_parque)), 'NULL') IN ('NULL', '', 'TODOS') OR upper(p.park_code) = upper(p_parque) OR lower(p.park_name) = lower(p_parque))
      AND (try_to_date(p_desde) IS NULL OR f.reading_date >= to_date(p_desde))
      AND (try_to_date(p_hasta) IS NULL OR f.reading_date <= to_date(p_hasta))
    GROUP BY p.park_name;

CREATE OR REPLACE FUNCTION ${gold}.fn_ranking_baterias(
    p_meses INT DEFAULT 12 COMMENT 'Cantidad de meses hacia atrás para valorizar (default 12)')
RETURNS TABLE (park_name STRING, option_code STRING, battery_mw DOUBLE, battery_mwh DOUBLE,
               curtailed_mwh DOUBLE, recovered_mwh DOUBLE, recovered_value_usd DOUBLE,
               battery_capex_usd DOUBLE COMMENT 'Inversión de UNA batería de esa opción en ese parque (USD)',
               simple_payback_years DOUBLE COMMENT 'Repago simple en años = capex / valor recuperado por año',
               ranking INT COMMENT 'Posición en el ranking (1 = mejor repago); no es una cantidad de años')
COMMENT 'Caso de inversión en baterías: valor recuperable del curtailment y repago simple por parque y tamaño'
RETURN
    WITH last_m AS (SELECT max(month_start) AS m FROM ${gold}.mart_curtailment_battery),
    w AS (
        SELECT b.park_code, b.option_code, max(b.battery_mw) AS battery_mw, max(b.battery_mwh) AS battery_mwh,
               sum(b.curtailed_mwh) AS curtailed_mwh, sum(b.recovered_mwh) AS recovered_mwh,
               sum(b.recovered_value_usd) AS recovered_value_usd, max(b.battery_capex_usd) AS capex
        FROM ${gold}.mart_curtailment_battery b, last_m
        WHERE b.month_start > add_months(last_m.m, -p_meses)
        GROUP BY b.park_code, b.option_code
    )
    SELECT p.park_name, w.option_code, w.battery_mw, w.battery_mwh, round(w.curtailed_mwh, 1),
           round(w.recovered_mwh, 1), round(w.recovered_value_usd, 0), w.capex,
           round(w.capex / nullif(w.recovered_value_usd * 12 / p_meses, 0), 1),
           CAST(rank() OVER (ORDER BY w.capex / nullif(w.recovered_value_usd, 0)) AS INT)
    FROM w JOIN ${gold}.dim_park p ON p.park_code = w.park_code;

CREATE OR REPLACE FUNCTION ${gold}.fn_turbinas_en_riesgo(
    p_parque STRING DEFAULT NULL COMMENT 'Código o nombre del parque; NULL, vacío o TODOS = todos')
RETURNS TABLE (reading_date DATE, park_code STRING, turbine_id STRING, turbine_tag STRING, health_score DOUBLE,
               risk_level STRING, suspected_component STRING, gearbox_residual_7d DOUBLE, vibration_ratio DOUBLE)
COMMENT 'Turbinas con riesgo MEDIO o ALTO en el último día con datos, ordenadas de peor a mejor'
RETURN
    SELECT h.reading_date, h.park_code, h.turbine_id, t.turbine_tag, h.health_score, h.risk_level,
           h.suspected_component, h.gearbox_residual_7d, h.vibration_ratio
    FROM ${gold}.mart_turbine_health h
    JOIN ${gold}.dim_turbine t ON t.turbine_id = h.turbine_id AND t.is_current
    JOIN ${gold}.dim_park p ON p.park_code = h.park_code
    WHERE h.reading_date = (SELECT max(reading_date) FROM ${gold}.mart_turbine_health)
      AND h.risk_level IN ('MEDIO', 'ALTO')
      AND (coalesce(upper(trim(p_parque)), 'NULL') IN ('NULL', '', 'TODOS') OR upper(p.park_code) = upper(p_parque) OR lower(p.park_name) = lower(p_parque))
    ORDER BY h.health_score;

CREATE OR REPLACE FUNCTION ${gold}.fn_recomendacion_limpieza(
    p_parque STRING DEFAULT NULL COMMENT 'Código o nombre del parque solar; NULL, vacío o TODOS = todos')
RETURNS TABLE (park_name STRING, reading_date DATE, soiling_loss_pct DOUBLE, days_since_cleaning INT,
               lost_usd_since_cleaning DOUBLE, cleaning_cost_usd DOUBLE, rain_forecast_tomorrow_mm DOUBLE,
               recommendation STRING)
COMMENT 'Recomendación de limpieza de paneles del último día con datos (LIMPIAR, ESPERAR, ESPERAR_LLUVIA, LIMPIANDO)'
RETURN
    SELECT p.park_name, c.reading_date, c.soiling_loss_pct, c.days_since_cleaning, c.lost_usd_since_cleaning,
           c.cleaning_cost_usd, c.rain_forecast_tomorrow_mm, c.recommendation
    FROM ${gold}.mart_panel_cleaning c
    JOIN ${gold}.dim_park p ON p.park_code = c.park_code
    WHERE c.reading_date = (SELECT max(reading_date) FROM ${gold}.mart_panel_cleaning)
      AND (coalesce(upper(trim(p_parque)), 'NULL') IN ('NULL', '', 'TODOS') OR upper(p.park_code) = upper(p_parque) OR lower(p.park_name) = lower(p_parque));

CREATE OR REPLACE FUNCTION ${gold}.fn_proyeccion_ppa(
    p_contrato STRING DEFAULT NULL COMMENT 'Contrato (PPA-2023-007) o parte del nombre del cliente; NULL = todos')
RETURNS TABLE (as_of_date DATE, contract_id STRING, client_name STRING, committed_mwh DOUBLE,
               delivered_mtd_mwh DOUBLE, projected_mwh DOUBLE, projected_compliance_pct DOUBLE,
               projected_shortfall_mwh DOUBLE, spot_cover_cost_usd DOUBLE, penalty_cost_usd DOUBLE,
               recommendation STRING)
COMMENT 'Proyección de cumplimiento de cada PPA para el mes en curso (última fecha de corte) y qué conviene hacer'
RETURN
    SELECT as_of_date, contract_id, client_name, committed_mwh, delivered_mtd_mwh, projected_mwh,
           projected_compliance_pct, projected_shortfall_mwh, spot_cover_cost_usd, penalty_cost_usd, recommendation
    FROM ${gold}.mart_ppa_forecast
    WHERE as_of_date = (SELECT max(as_of_date) FROM ${gold}.mart_ppa_forecast)
      AND (p_contrato IS NULL OR contract_id = p_contrato OR lower(client_name) LIKE concat('%', lower(p_contrato), '%'));

CREATE OR REPLACE FUNCTION ${gold}.fn_reclamos_garantia(
    p_anio INT DEFAULT NULL COMMENT 'Año; NULL = todos')
RETURNS TABLE (park_name STRING, manufacturer STRING, year_month STRING, availability_12m DOUBLE,
               guaranteed_availability DOUBLE, shortfall_points DOUBLE, ld_accrued_usd DOUBLE)
COMMENT 'Meses en que la disponibilidad móvil 12 m quedó debajo de la garantía y el monto a reclamar al fabricante'
RETURN
    SELECT park_name, manufacturer, year_month, availability_12m, guaranteed_availability, shortfall_points,
           ld_accrued_usd
    FROM ${gold}.mart_warranty_claims
    WHERE claim_eligible AND (p_anio IS NULL OR year(month_start) = p_anio)
    ORDER BY month_start, park_name;

CREATE OR REPLACE FUNCTION ${gold}.fn_explicar_desvio(
    p_parque STRING COMMENT 'Código o nombre del parque',
    p_mes STRING COMMENT 'Mes en formato yyyy-MM (ej. 2025-07)')
RETURNS TABLE (orden INT, concepto STRING, mwh DOUBLE, pct_del_presupuesto DOUBLE)
COMMENT 'Cascada del desvío real vs. presupuesto de un parque en un mes: presupuesto, efecto del recurso, curtailment, fallas, mantenimiento, hielo, suciedad, otras, real y desvío total (fila 9: pct_del_presupuesto es el desvío %)'
RETURN
    WITH m AS (
        SELECT * FROM ${gold}.mart_generation_vs_budget
        WHERE year_month = p_mes AND (upper(park_code) = upper(p_parque) OR lower(park_name) = lower(p_parque))
    ),
    rows AS (
        SELECT 1 AS orden, 'Presupuesto P50' AS concepto, budget_p50_mwh AS mwh, budget_p50_mwh AS base FROM m
        UNION ALL SELECT 2, 'Efecto del recurso (viento/sol)', resource_effect_mwh, budget_p50_mwh FROM m
        UNION ALL SELECT 3, 'Curtailment por encima de lo presupuestado',
                         -(lost_curtailment_mwh - budget_curtailment_allowance_mwh), budget_p50_mwh FROM m
        UNION ALL SELECT 4, 'Fallas y mantenimiento por encima de lo presupuestado',
                         -(lost_fault_mwh + lost_maintenance_mwh - budget_availability_allowance_mwh), budget_p50_mwh FROM m
        UNION ALL SELECT 5, 'Hielo en palas', -lost_icing_mwh, budget_p50_mwh FROM m
        UNION ALL SELECT 6, 'Suciedad de paneles', -lost_soiling_mwh, budget_p50_mwh FROM m
        UNION ALL SELECT 7, 'Otras (performance y huecos de dato)', -lost_other_mwh, budget_p50_mwh FROM m
        UNION ALL SELECT 8, 'Generación real', actual_mwh, budget_p50_mwh FROM m
        UNION ALL SELECT 9, 'Desvío total vs. presupuesto', actual_mwh - budget_p50_mwh, budget_p50_mwh FROM m
    )
    SELECT orden, concepto, round(mwh, 1), round(mwh / base, 4) FROM rows ORDER BY orden;
