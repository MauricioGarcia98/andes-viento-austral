-- =============================================================================
-- LDP · BRONZE (declarativo)
-- Lo mismo que hace ingestion/bronze.py, pero el motor se ocupa del checkpoint,
-- de la evolución de esquema (reinicia el flujo solo ante columnas nuevas) y del linaje.
-- =============================================================================

CREATE OR REFRESH STREAMING TABLE scada_raw
COMMENT 'SCADA de aerogeneradores tal cual llega (JSON gz, 3 formatos de fecha según fabricante)'
TBLPROPERTIES ('quality' = 'bronze')
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${landing_path}/scada_turbine',
  format => 'json',
  partitionColumns => 'ingest_date',
  schemaHints => 'setpoint_kw DOUBLE, ts_epoch_ms BIGINT',
  schemaEvolutionMode => 'addNewColumns'
);

CREATE OR REFRESH STREAMING TABLE dispatch_raw
COMMENT 'Instrucciones de despacho de CAMMESA (curtailment), con versiones y anulaciones'
TBLPROPERTIES ('quality' = 'bronze')
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${landing_path}/cammesa_dispatch', format => 'json', partitionColumns => 'ingest_date');

-- CSV: el contrato va como schemaHints y todo entra como texto (se tipa en silver)
CREATE OR REFRESH STREAMING TABLE assets_raw
COMMENT 'Registro de activos del CMMS (CDC con op I/U/D)'
TBLPROPERTIES ('quality' = 'bronze')
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${landing_path}/cmms_assets', format => 'csv', header => true,
                       partitionColumns => 'ingest_date', inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE budget_raw
COMMENT 'Presupuesto P50 mensual de Finanzas'
TBLPROPERTIES ('quality' = 'bronze')
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('${landing_path}/generation_budget', format => 'csv', header => true,
                       partitionColumns => 'ingest_date', inferColumnTypes => false);
