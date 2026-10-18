-- =============================================================================
-- LDP · SILVER (declarativo): tipado + EXPECTATIONS + SCD2 con AUTO CDC
--
--  EXPECT ... (sin acción)       -> se registra en las métricas del pipeline (warn)
--  EXPECT ... ON VIOLATION DROP ROW -> la fila no entra (cuarentena implícita)
--  EXPECT ... ON VIOLATION FAIL UPDATE -> se corta el pipeline
--
-- Lo que el estilo declarativo NO hace fácil (y sí la versión imperativa): estimar el desfase
-- del reloj de cada turbina con un percentil por día de recepción. Acá se redondea al slot y listo.
-- =============================================================================

CREATE OR REFRESH STREAMING TABLE scada_clean (
  CONSTRAINT turbina_informada   EXPECT (turbine IS NOT NULL)         ON VIOLATION DROP ROW,
  CONSTRAINT fecha_parseable     EXPECT (ts_utc IS NOT NULL)          ON VIOLATION DROP ROW,
  CONSTRAINT viento_posible      EXPECT (wind_ms IS NULL OR wind_ms BETWEEN 0 AND 60),
  CONSTRAINT temperatura_posible EXPECT (gearbox_bearing_c IS NULL OR gearbox_bearing_c < 200),
  CONSTRAINT potencia_en_rango   EXPECT (power_kw IS NULL OR power_kw <= 6000)
)
COMMENT 'SCADA tipado, en UTC, con potencia en kW y slot de 10 minutos'
TBLPROPERTIES ('quality' = 'silver')
AS
WITH t AS (
  SELECT *,
         coalesce(
           timestamp_millis(ts_epoch_ms),
           try_to_timestamp(ts, "yyyy-MM-dd'T'HH:mm:ssXXX"),
           to_utc_timestamp(try_to_timestamp(ts, 'dd/MM/yyyy HH:mm:ss'), 'America/Argentina/Buenos_Aires')
         ) AS device_ts,
         CASE WHEN fw LIKE 'PEI%' THEN 3000 WHEN fw LIKE 'HT%' THEN 4500 ELSE 3600 END AS rated_kw
  FROM STREAM(scada_raw)
)
SELECT
  site                                                                AS park_code,
  upper(turbine)                                                      AS turbine,
  timestamp_seconds(round(unix_timestamp(device_ts) / 600) * 600)     AS ts_utc,
  to_date(from_utc_timestamp(timestamp_seconds(round(unix_timestamp(device_ts) / 600) * 600),
                             'America/Argentina/Buenos_Aires'))       AS reading_date,
  status,
  CASE WHEN sensors.wind_ms > 60 THEN NULL ELSE sensors.wind_ms END   AS wind_ms,
  CASE
    WHEN sensors.power_unit = 'MW' THEN sensors.active_power * 1000
    WHEN sensors.power_unit = 'kW' THEN sensors.active_power
    WHEN abs(sensors.active_power) < rated_kw / 1000 * 1.6 AND sensors.wind_ms >= 4 THEN sensors.active_power * 1000
    ELSE sensors.active_power
  END                                                                 AS power_kw,
  sensors.gearbox_bearing_c,
  setpoint_kw,
  try_to_timestamp(received_at, "yyyy-MM-dd'T'HH:mm:ss'Z'")           AS received_ts,
  _ingested_at
FROM t;

CREATE OR REFRESH MATERIALIZED VIEW dispatch_clean
COMMENT 'Última versión vigente de cada instrucción de CAMMESA (sin anuladas)'
AS SELECT * EXCEPT (rn) FROM (
  SELECT agent_code, instruction_id, version, status, reason, limit_mw,
         try_to_timestamp(valid_from, "yyyy-MM-dd'T'HH:mm:ssXXX") AS valid_from_ts,
         try_to_timestamp(valid_to, "yyyy-MM-dd'T'HH:mm:ssXXX")   AS valid_to_ts,
         row_number() OVER (PARTITION BY instruction_id ORDER BY version DESC) AS rn
  FROM dispatch_raw
) WHERE rn = 1 AND status <> 'ANULADA';

CREATE OR REFRESH STREAMING TABLE assets_clean (
  CONSTRAINT id_presente EXPECT (asset_id IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Cambios del registro de activos, tipados'
AS SELECT
  asset_id, upper(asset_tag) AS asset_tag, asset_type, park_code, model, try_cast(rated_kw AS DOUBLE) AS rated_kw,
  gearbox_serial, main_bearing_serial, generator_serial, firmware,
  to_utc_timestamp(coalesce(try_to_timestamp(updated_at, 'yyyy-MM-dd HH:mm:ss'),
                            try_to_timestamp(updated_at, 'dd/MM/yyyy HH:mm')), 'America/Argentina/Buenos_Aires') AS updated_at,
  upper(op) AS op
FROM STREAM(assets_raw);

-- SCD Tipo 2 declarativo: lo que en silver/scd2.py son 100 líneas, acá son 8.
CREATE OR REFRESH STREAMING TABLE assets_scd2
COMMENT 'Historia SCD2 de activos generada con AUTO CDC (__START_AT / __END_AT)';

CREATE FLOW assets_scd2_flow AS AUTO CDC INTO assets_scd2
FROM STREAM(assets_clean)
KEYS (asset_id)
APPLY AS DELETE WHEN op = 'D'
SEQUENCE BY updated_at
COLUMNS * EXCEPT (op)
STORED AS SCD TYPE 2;

CREATE OR REFRESH MATERIALIZED VIEW budget_clean
COMMENT 'Presupuesto P50 aprobado (v1) por parque y mes'
AS SELECT upper(parque) AS park_code, make_date(cast(anio AS INT), cast(mes AS INT), 1) AS month_start,
          cast(energia_p50_mwh AS DOUBLE) AS budget_p50_mwh
FROM budget_raw WHERE version LIKE '%-v1';
