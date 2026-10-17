-- =============================================================================
-- mart_ppa_forecast: ¿vamos a llegar al volumen comprometido este mes?
-- -----------------------------------------------------------------------------
-- Una foto por contrato y por día ("as of"): lo entregado en el mes hasta ese día +
-- la proyección del resto del mes = presupuesto diario restante x desempeño reciente
-- (real / presupuesto de los últimos 14 días: captura curtailment, fallas y viento).
-- Si la proyección queda debajo del mínimo: ¿comprar en el spot o pagar la penalidad?
-- Grano: contrato x fecha de corte.
-- =============================================================================
CREATE OR REPLACE TABLE ${gold}.mart_ppa_forecast
COMMENT 'Proyección diaria de cumplimiento de cada PPA en el mes en curso y recomendación spot vs. penalidad'
AS
WITH park_daily AS (
    SELECT park_code, reading_date, sum(energy_mwh) AS mwh FROM ${gold}.fact_availability_daily GROUP BY ALL
    UNION ALL
    SELECT park_code, reading_date, sum(energy_kwh) / 1000 FROM ${gold}.fact_inverter_hourly GROUP BY ALL
),
bounds AS (SELECT min(reading_date) AS d0, max(reading_date) AS d1 FROM park_daily),
budget_daily AS (
    SELECT b.park_code, d.date, b.budget_p50_mwh / d.days_in_month AS budget_mwh
    FROM ${silver}.generation_budget b
    JOIN ${gold}.dim_date d ON d.month_start = b.month_start
    WHERE b.version LIKE '%-v1'
),
asof AS (
    SELECT d.date AS as_of_date, d.month_start, d.days_in_month, d.day AS days_elapsed
    FROM ${gold}.dim_date d, bounds
    WHERE d.date BETWEEN bounds.d0 AND bounds.d1
),
park_asof AS (
    SELECT a.as_of_date, a.month_start, a.days_in_month, a.days_elapsed, bd.park_code,
           sum(CASE WHEN bd.date BETWEEN a.month_start AND a.as_of_date THEN pd.mwh END)            AS mtd_mwh,
           sum(CASE WHEN bd.date > a.as_of_date AND bd.date <= last_day(a.month_start) THEN bd.budget_mwh END) AS remaining_budget_mwh,
           sum(CASE WHEN bd.date BETWEEN a.as_of_date - 13 AND a.as_of_date THEN pd.mwh END)
               / nullif(sum(CASE WHEN bd.date BETWEEN a.as_of_date - 13 AND a.as_of_date THEN bd.budget_mwh END), 0)
                                                                                                     AS performance_14d
    FROM asof a
    JOIN budget_daily bd ON bd.date BETWEEN a.as_of_date - 13 AND last_day(a.month_start)
    LEFT JOIN park_daily pd ON pd.park_code = bd.park_code AND pd.reading_date = bd.date
    GROUP BY ALL
),
spot14 AS (
    SELECT a.as_of_date, avg(s.price_ars_mwh / dd.fx_ars_usd) AS spot_14d_usd_mwh
    FROM asof a
    JOIN ${silver}.spot_prices s ON s.price_date BETWEEN a.as_of_date - 13 AND a.as_of_date
    JOIN ${gold}.dim_date dd ON dd.date = s.price_date
    GROUP BY a.as_of_date
),
claims AS (
    SELECT c.*, sum(c.claim_mwh) OVER (PARTITION BY c.park_code, c.month_start) AS park_total_claim_mwh
    FROM ${gold}.v_contract_park_month c
),
proj AS (
    SELECT c.contract_id, c.client_name, c.contract_key, p.as_of_date, p.month_start, p.days_elapsed, p.days_in_month,
           c.committed_mwh_month, c.tolerance_pct, c.penalty_usd_mwh, c.price_usd_mwh,
           c.claim_mwh * p.days_elapsed / p.days_in_month
               * least(1, coalesce(p.mtd_mwh, 0) / (c.park_total_claim_mwh * p.days_elapsed / p.days_in_month)) AS mtd_alloc_mwh,
           c.claim_mwh * least(1, (coalesce(p.mtd_mwh, 0) + coalesce(p.remaining_budget_mwh, 0)
                                   * coalesce(p.performance_14d, 1)) / c.park_total_claim_mwh)              AS proj_alloc_mwh
    FROM claims c
    JOIN park_asof p ON p.park_code = c.park_code AND p.month_start = c.month_start
)
SELECT
    cast(date_format(p.as_of_date, 'yyyyMMdd') AS INT)                       AS date_key,
    p.as_of_date,
    p.month_start,
    date_format(p.month_start, 'yyyy-MM')                                    AS year_month,
    p.contract_key,
    p.contract_id,
    p.client_name,
    p.days_elapsed,
    p.days_in_month,
    round(max(p.committed_mwh_month), 2)                                     AS committed_mwh,
    round(max(p.committed_mwh_month) * (1 - max(p.tolerance_pct)), 2)        AS min_required_mwh,
    round(sum(p.mtd_alloc_mwh), 2)                                           AS delivered_mtd_mwh,
    round(sum(p.proj_alloc_mwh), 2)                                          AS projected_mwh,
    round(sum(p.proj_alloc_mwh) / max(p.committed_mwh_month), 4)             AS projected_compliance_pct,
    round(greatest(0, max(p.committed_mwh_month) * (1 - max(p.tolerance_pct)) - sum(p.proj_alloc_mwh)), 2) AS projected_shortfall_mwh,
    round(max(s.spot_14d_usd_mwh), 2)                                        AS spot_14d_usd_mwh,
    max(p.penalty_usd_mwh)                                                   AS penalty_usd_mwh,
    round(greatest(0, max(p.committed_mwh_month) * (1 - max(p.tolerance_pct)) - sum(p.proj_alloc_mwh))
          * max(s.spot_14d_usd_mwh) * 1.05, 2)                               AS spot_cover_cost_usd,
    round(greatest(0, max(p.committed_mwh_month) * (1 - max(p.tolerance_pct)) - sum(p.proj_alloc_mwh))
          * max(p.penalty_usd_mwh), 2)                                       AS penalty_cost_usd,
    CASE
        WHEN sum(p.proj_alloc_mwh) >= max(p.committed_mwh_month) * (1 - max(p.tolerance_pct)) THEN 'EN_CAMINO'
        WHEN max(s.spot_14d_usd_mwh) * 1.05 < max(p.penalty_usd_mwh) THEN 'COMPRAR_SPOT'
        ELSE 'PAGAR_PENALIDAD'
    END                                                                      AS recommendation
FROM proj p
LEFT JOIN spot14 s USING (as_of_date)
GROUP BY p.as_of_date, p.month_start, p.days_elapsed, p.days_in_month, p.contract_key, p.contract_id, p.client_name;
