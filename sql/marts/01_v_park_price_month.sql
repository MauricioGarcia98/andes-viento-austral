-- =============================================================================
-- v_contract_park_month: qué contrato "reclama" cuánta energía de cada parque, cada mes
-- v_park_price_month:    precio de realización del parque (PPA ponderado por volumen)
-- -----------------------------------------------------------------------------
-- Regla de negocio (Comercial PPA): cada contrato reparte su volumen comprometido en
-- partes iguales entre sus parques de origen. Se usa la versión del contrato (SCD2)
-- vigente al cierre del mes: si hubo adenda en el mes, manda la adenda.
-- =============================================================================
CREATE OR REPLACE VIEW ${gold}.v_contract_park_month
COMMENT 'Volumen comprometido de cada contrato PPA asignado a cada parque de origen, por mes'
AS
WITH months AS (
    SELECT DISTINCT month_start, last_day(month_start) AS month_end, days_in_month
    FROM ${gold}.dim_date
    WHERE date <= (SELECT max(date) FROM ${gold}.dim_date)
)
SELECT
    m.month_start,
    m.month_end,
    c.contract_key,
    c.contract_id,
    c.client_name,
    c.sector,
    c.price_usd_mwh,
    c.penalty_usd_mwh,
    c.tolerance_pct,
    c.committed_mwh_month,
    size(c.source_parks)                              AS n_source_parks,
    p.park_code,
    c.committed_mwh_month / size(c.source_parks)      AS claim_mwh
FROM months m
JOIN ${gold}.dim_contract c
  ON  c.contract_key <> -1
  AND m.month_start >= trunc(c.start_date, 'MM')
  AND m.month_start <= c.end_date
  AND to_timestamp(m.month_end) + INTERVAL 1 DAY > c.effective_from
  AND to_timestamp(m.month_end) + INTERVAL 1 DAY <= c.effective_to
  AND NOT c.is_deleted
LATERAL VIEW explode(c.source_parks) p AS park_code;

CREATE OR REPLACE VIEW ${gold}.v_park_price_month
COMMENT 'Precio de realización por parque y mes: precio PPA promedio ponderado por volumen comprometido'
AS
SELECT
    park_code,
    month_start,
    round(sum(price_usd_mwh * claim_mwh) / sum(claim_mwh), 2) AS ppa_price_usd_mwh,
    round(sum(claim_mwh), 1)                                   AS committed_claim_mwh,
    count(*)                                                   AS contracts
FROM ${gold}.v_contract_park_month
GROUP BY park_code, month_start;
