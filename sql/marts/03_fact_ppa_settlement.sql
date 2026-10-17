-- =============================================================================
-- fact_ppa_settlement: liquidación mensual de cada contrato PPA (contrato x mes)
-- -----------------------------------------------------------------------------
-- Regla MATER simplificada (ver docs/02_casos_de_negocio.md):
--   * La energía de cada parque se asigna PRIMERO a los contratos (prioridad de despacho),
--     a prorrata de lo que cada uno reclama; el excedente se vende al spot.
--   * Faltante = comprometido x (1 - tolerancia) - entregado.
--   * Opciones ante faltante: pagar penalidad (USD/MWh del contrato) o cubrir comprando
--     en el spot (precio medio nacional del mes + 5 % de cargos).
-- =============================================================================
CREATE OR REPLACE TABLE ${gold}.fact_ppa_settlement
COMMENT 'Liquidación mensual de contratos PPA: entregado, faltante, penalidad vs. compra spot'
AS
WITH gen AS (
    SELECT park_code, month_start, actual_mwh FROM ${gold}.mart_generation_vs_budget
),
claims AS (
    SELECT c.*, sum(c.claim_mwh) OVER (PARTITION BY c.park_code, c.month_start) AS park_total_claim_mwh
    FROM ${gold}.v_contract_park_month c
),
alloc AS (
    SELECT c.*, g.actual_mwh AS park_actual_mwh,
           least(c.claim_mwh, g.actual_mwh * c.claim_mwh / c.park_total_claim_mwh) AS allocated_mwh
    FROM claims c
    JOIN gen g USING (park_code, month_start)
),
spot AS (
    SELECT trunc(s.price_date, 'MM') AS month_start,
           avg(s.price_ars_mwh / d.fx_ars_usd) AS spot_avg_usd_mwh
    FROM ${silver}.spot_prices s
    JOIN ${gold}.dim_date d ON d.date = s.price_date
    GROUP BY ALL
),
last_day_data AS (SELECT max(reading_date) AS d FROM ${gold}.fact_turbine_10min),
contract_month AS (
    SELECT contract_key, contract_id, client_name, sector, month_start, month_end,
           max(price_usd_mwh) AS price_usd_mwh, max(penalty_usd_mwh) AS penalty_usd_mwh,
           max(tolerance_pct) AS tolerance_pct, max(committed_mwh_month) AS committed_mwh,
           sum(allocated_mwh) AS delivered_mwh,
           count(*) AS source_parks_with_data,
           max(n_source_parks) AS n_source_parks
    FROM alloc
    GROUP BY ALL
)
SELECT
    cast(date_format(cm.month_start, 'yyyyMMdd') AS INT)               AS month_date_key,
    cm.contract_key,
    cm.contract_id,
    cm.client_name,
    cm.sector,
    cm.month_start,
    date_format(cm.month_start, 'yyyy-MM')                             AS year_month,
    cm.month_end <= (SELECT d FROM last_day_data)                      AS is_closed_month,
    round(cm.committed_mwh, 2)                                         AS committed_mwh,
    round(cm.committed_mwh * (1 - cm.tolerance_pct), 2)                AS min_required_mwh,
    round(cm.delivered_mwh, 2)                                         AS delivered_mwh,
    round(cm.delivered_mwh / cm.committed_mwh, 4)                      AS compliance_pct,
    round(greatest(cm.committed_mwh * (1 - cm.tolerance_pct) - cm.delivered_mwh, 0), 2) AS shortfall_mwh,
    cm.price_usd_mwh,
    cm.penalty_usd_mwh,
    cm.tolerance_pct,
    round(cm.delivered_mwh * cm.price_usd_mwh, 2)                      AS revenue_usd,
    round(s.spot_avg_usd_mwh, 2)                                       AS spot_avg_usd_mwh,
    round(greatest(cm.committed_mwh * (1 - cm.tolerance_pct) - cm.delivered_mwh, 0) * cm.penalty_usd_mwh, 2)
                                                                       AS penalty_cost_usd,
    round(greatest(cm.committed_mwh * (1 - cm.tolerance_pct) - cm.delivered_mwh, 0) * s.spot_avg_usd_mwh * 1.05, 2)
                                                                       AS spot_cover_cost_usd,
    CASE
        WHEN cm.delivered_mwh >= cm.committed_mwh * (1 - cm.tolerance_pct) THEN 'CUMPLE'
        WHEN s.spot_avg_usd_mwh * 1.05 < cm.penalty_usd_mwh THEN 'COMPRAR_SPOT'
        ELSE 'PAGAR_PENALIDAD'
    END                                                                AS best_option,
    round(least(greatest(cm.committed_mwh * (1 - cm.tolerance_pct) - cm.delivered_mwh, 0) * cm.penalty_usd_mwh,
                greatest(cm.committed_mwh * (1 - cm.tolerance_pct) - cm.delivered_mwh, 0) * s.spot_avg_usd_mwh * 1.05), 2)
                                                                       AS best_option_cost_usd
FROM contract_month cm
LEFT JOIN spot s USING (month_start);
