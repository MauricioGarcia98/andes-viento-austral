"""Capa BRONZE: ingesta incremental de archivos crudos a tablas Delta.

Principios:
  * "Lo que llegó, tal cual llegó": no se limpia ni se deduplica.
  * Linaje técnico: archivo origen, fecha de modificación, momento de ingesta.
  * Nunca se pierde un registro: lo que no encaja en el esquema va a `_rescued_data`.
  * Incremental: cada corrida procesa sólo archivos nuevos (checkpoint).

En Databricks se usa **Auto Loader** (`cloudFiles`). En local, el *file streaming
source* de Spark OSS (misma semántica: checkpoint + trigger availableNow).

Dos lecciones aprendidas en NovaMart (y aplicadas desde el día 1 acá):
  1. CSV + `schemaEvolutionMode=addNewColumns` NO admite `.schema()`: el contrato va
     por `cloudFiles.schemaHints` (error CF_ADD_NEW_NOT_SUPPORTED).
  2. Cuando aparece una columna nueva, Auto Loader guarda el esquema ampliado y DETIENE
     el stream con UNKNOWN_FIELD_EXCEPTION. Es esperado: se reinicia en código, no con
     los reintentos del job (que son para fallas de infraestructura).
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T

from andes_viento.config import ProjectConfig, is_databricks

_S = T.StringType()
_SCHEMA_EVOLUTION_RESTARTS = 3

# Contratos de los CSV: en CSV todo es texto y el orden manda. Los tipos se aplican en silver.
CSV_CONTRACTS = {
    "inverter_5min": ["plant", "inverter", "timestamp", "poa_irradiance_wm2", "module_temp_c", "ambient_temp_c",
                      "dc_power_kw", "ac_power_kw", "status"],
    "cmms_assets": ["asset_id", "asset_tag", "asset_type", "park_code", "manufacturer", "model", "rated_kw",
                    "dc_kwp", "panels", "gearbox_serial", "main_bearing_serial", "generator_serial", "firmware",
                    "commissioning_date", "status", "op", "updated_at"],
    "cmms_crews": ["crew_id", "base", "leader_name", "leader_phone", "members", "specialty", "op", "updated_at"],
    "cammesa_spot_prices": ["FECHA", "HORA", "NODO", "PRECIO_ARS_MWH", "TIPO"],
    "ppa_contracts": ["contract_id", "client_name", "sector", "client_cuit", "contact_name", "contact_email",
                      "contact_phone", "start_date", "end_date", "price_usd_mwh", "committed_mwh_month",
                      "penalty_usd_mwh", "tolerance_pct", "source_parks", "status", "op", "updated_at"],
    "fx_rates": ["FECHA", "MONEDA", "TIPO", "VALOR"],
    "generation_budget": ["anio", "mes", "parque", "version", "energia_p50_mwh", "energia_p90_mwh",
                          "disponibilidad_supuesta", "curtailment_supuesto", "publicado"],
}
# Columnas que aparecen después (schema drift): en local se declaran para que el contrato no falle.
CSV_LATE_COLUMNS = {"inverter_5min": ["soiling_sensor_pct"]}

SOURCE_FORMATS = {
    "scada_turbine": "json",
    "inverter_5min": "csv",
    "cmms_assets": "csv",
    "cmms_work_orders": "json",
    "cmms_crews": "csv",
    "cammesa_dispatch": "json",
    "cammesa_spot_prices": "csv",
    "ppa_contracts": "csv",
    "weather": "json",
    "fx_rates": "csv",
    "generation_budget": "csv",
}
CSV_SEPARATOR = {"cammesa_spot_prices": ";", "fx_rates": ";"}

# JSON: tipos que la inferencia puede adivinar mal. Ej.: si los primeros archivos de órdenes sólo
# traen `parts: []`, Auto Loader infiere ARRAY<STRING> y después no puede leer los repuestos.
JSON_SCHEMA_HINTS = {
    "cmms_work_orders": {
        "parts": "ARRAY<STRUCT<part_code: STRING, description: STRING, qty: BIGINT, unit_cost_usd: DOUBLE>>",
        "water_m3": "DOUBLE", "water_cost_usd": "DOUBLE", "crane_cost_usd": "DOUBLE", "labor_cost_ars": "DOUBLE",
        "access_delay_h": "DOUBLE",
    },
    "scada_turbine": {"setpoint_kw": "DOUBLE", "ts_epoch_ms": "BIGINT"},
    "weather": {"snow_cm": "DOUBLE", "dust_aod": "DOUBLE", "precip_prob_pct": "BIGINT"},
}


def json_schema_hints(name: str) -> str | None:
    hints = JSON_SCHEMA_HINTS.get(name)
    return ", ".join(f"`{k}` {v}" for k, v in hints.items()) if hints else None


def csv_schema(name: str) -> T.StructType:
    cols = CSV_CONTRACTS[name] + CSV_LATE_COLUMNS.get(name, [])
    fields = [T.StructField(c, _S) for c in cols]
    fields.append(T.StructField("ingest_date", T.DateType()))  # columna de partición (carpeta)
    return T.StructType(fields)


def csv_schema_hints(name: str) -> str:
    """El contrato en formato DDL para `cloudFiles.schemaHints` (sin las columnas tardías:
    esas las descubre Auto Loader y disparan la evolución de esquema, como en la vida real)."""
    return ", ".join([f"`{c}` STRING" for c in CSV_CONTRACTS[name]] + ["ingest_date DATE"])


def read_landing_stream(spark: SparkSession, cfg: ProjectConfig, name: str) -> DataFrame:
    fmt = SOURCE_FORMATS[name]
    path = cfg.landing_path(name)
    if is_databricks():  # pragma: no cover - Auto Loader sólo existe en Databricks
        reader = (
            spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", fmt)
            .option("cloudFiles.schemaLocation", cfg.schema_location(name))
            .option("cloudFiles.inferColumnTypes", "true")
            .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
            .option("cloudFiles.partitionColumns", "ingest_date")
            .option("cloudFiles.maxFilesPerTrigger", 500)
            .option("rescuedDataColumn", "_rescued_data")
        )
        if fmt == "csv":
            # Auto Loader no admite .schema() con addNewColumns: el contrato va como schemaHints
            reader = (reader.option("cloudFiles.inferColumnTypes", "false")
                      .option("cloudFiles.schemaHints", csv_schema_hints(name)))
        elif json_schema_hints(name):
            reader = reader.option("cloudFiles.schemaHints", json_schema_hints(name))
    else:
        reader = spark.readStream.format(fmt).option("maxFilesPerTrigger", 500)
        if fmt == "json":
            reader = reader.option("columnNameOfCorruptRecord", "_rescued_data")
        if fmt == "csv":
            reader = reader.schema(csv_schema(name))
    if fmt == "csv":
        reader = (reader.option("header", "true").option("mode", "PERMISSIVE")
                  .option("sep", CSV_SEPARATOR.get(name, ",")))
    return reader.load(path)


def add_lineage(df: DataFrame) -> DataFrame:
    """Columnas técnicas de linaje: ¿de qué archivo vino y cuándo lo cargamos?"""
    return (
        df.withColumn("_source_file", F.col("_metadata.file_path"))
        .withColumn("_file_modification_time", F.col("_metadata.file_modification_time"))
        .withColumn("_ingested_at", F.current_timestamp())
    )


def _json_schema_local(spark: SparkSession, cfg: ProjectConfig, name: str) -> T.StructType:
    """En local el file source de JSON necesita un esquema: se infiere de lo que hay (como Auto Loader)."""
    sample = spark.read.json(cfg.landing_path(name)).schema
    hints = {k: T._parse_datatype_string(v.replace(": ", ":")) for k, v in JSON_SCHEMA_HINTS.get(name, {}).items()}
    fields = [T.StructField(f.name, hints.pop(f.name, f.dataType)) for f in sample.fields]
    fields += [T.StructField(k, v) for k, v in hints.items()]
    if "_rescued_data" not in sample.fieldNames():
        fields.append(T.StructField("_rescued_data", _S))
    return T.StructType(fields)


def ingest_source(spark: SparkSession, cfg: ProjectConfig, name: str) -> int:
    """Ingesta incremental landing/<name> -> bronze.<name>. Devuelve filas nuevas."""
    target = cfg.table("bronze", name)
    before = spark.table(target).count() if spark.catalog.tableExists(target) else 0
    for attempt in range(_SCHEMA_EVOLUTION_RESTARTS + 1):
        stream = read_landing_stream(spark, cfg, name) if (is_databricks() or SOURCE_FORMATS[name] != "json") \
            else (spark.readStream.schema(_json_schema_local(spark, cfg, name))
                  .option("columnNameOfCorruptRecord", "_rescued_data").json(cfg.landing_path(name)))
        query = (
            add_lineage(stream)
            .writeStream.format("delta")
            .option("checkpointLocation", cfg.checkpoint_path(f"bronze_{name}"))
            .option("mergeSchema", "true")  # acepta columnas nuevas (schema evolution)
            .trigger(availableNow=True)
            .toTable(target)
        )
        try:
            query.awaitTermination()
            break
        except Exception as exc:
            # Auto Loader (addNewColumns) detiene el stream al detectar columnas nuevas,
            # después de guardar el esquema ampliado: reiniciarlo retoma con ese esquema.
            if "UNKNOWN_FIELD_EXCEPTION" not in str(exc) or attempt == _SCHEMA_EVOLUTION_RESTARTS:
                raise
            print(f"{name}: columnas nuevas detectadas, reiniciando el stream ({attempt + 1})")
    return spark.table(target).count() - before


def ingest_all(spark: SparkSession, cfg: ProjectConfig, sources: list[str] | None = None) -> dict[str, int]:
    out = {}
    for name in sources or list(SOURCE_FORMATS):
        try:
            out[name] = ingest_source(spark, cfg, name)
        except Exception as exc:
            if "PATH_NOT_FOUND" in str(exc) or "does not exist" in str(exc):
                out[name] = 0  # la fuente todavía no mandó ningún archivo
            else:
                raise
    return out
