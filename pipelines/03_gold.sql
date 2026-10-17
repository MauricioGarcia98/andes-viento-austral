-- =============================================================================
-- LDP · GOLD (declarativo): vistas materializadas que se recalculan incrementalmente
-- cuando el motor puede (Enzyme) y por completo cuando no.
-- =============================================================================

CREATE OR REFRESH MATERIALIZED VIEW scada_dedup
COMMENT 'Una fila por turbina y slot (la primera copia recibida gana)'
AS SELECT * EXCEPT (rn) FROM (
  SELECT *, row_number() OVER (PARTITION BY turbine, ts_utc ORDER BY received_ts) AS rn FROM scada_clean
) WHERE rn = 1;

CREATE OR REFRESH MATERIALIZED VIEW generation_daily
COMMENT 'Generación diaria por parque (MWh) y horas limitadas por la red'
AS SELECT
  park_code, reading_date,
  round(sum(greatest(power_kw, 0)) / 6 / 1000, 3) AS generated_mwh,
  count(DISTINCT turbine)                         AS turbines_reporting,
  sum(CASE WHEN status = 4 THEN 1 ELSE 0 END) / 6 AS curtailed_turbine_hours
FROM scada_dedup
GROUP BY park_code, reading_date;

CREATE OR REFRESH MATERIALIZED VIEW curtailment_instructions_daily
COMMENT 'Instrucciones de CAMMESA por parque y día (horas con tope de potencia)'
AS SELECT
  agent_code,
  to_date(from_utc_timestamp(valid_from_ts, 'America/Argentina/Buenos_Aires')) AS instruction_date,
  count(*)                                                                      AS instructions,
  round(sum((unix_timestamp(valid_to_ts) - unix_timestamp(valid_from_ts)) / 3600), 1) AS limited_hours,
  min(limit_mw)                                                                 AS min_limit_mw
FROM dispatch_clean
GROUP BY ALL;

CREATE OR REFRESH MATERIALIZED VIEW generation_vs_budget_monthly
COMMENT 'Real vs. presupuesto P50 por parque eólico y mes (versión declarativa simplificada)'
AS SELECT
  g.park_code,
  trunc(g.reading_date, 'MM')                                   AS month_start,
  round(sum(g.generated_mwh), 1)                                AS generated_mwh,
  max(b.budget_p50_mwh)                                         AS budget_p50_mwh,
  round(sum(g.generated_mwh) / max(b.budget_p50_mwh) - 1, 4)    AS variance_pct
FROM generation_daily g
LEFT JOIN budget_clean b ON b.park_code = g.park_code AND b.month_start = trunc(g.reading_date, 'MM')
GROUP BY ALL;
