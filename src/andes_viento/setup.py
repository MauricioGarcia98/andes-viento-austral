"""Creación de esquemas (capas), volumen de aterrizaje y tablas de `ops`.

El CATÁLOGO no se crea acá en Databricks Free Edition: con Default Storage la API del
bundle no puede crearlo ("Metastore storage root URL does not exist"). Se crea UNA vez
por SQL (`CREATE CATALOG IF NOT EXISTS andes_viento_dev`), ver docs/05_despliegue.md.
Igual se intenta, por si el workspace tiene un metastore con storage root.
"""

from __future__ import annotations

from pyspark.sql import SparkSession

from andes_viento.config import LAYERS, ProjectConfig, is_databricks

LAYER_COMMENTS = {
    "landing": "Zona de aterrizaje: archivos crudos (JSON/CSV) de SCADA, CMMS, CAMMESA, clima y Finanzas",
    "bronze": "Copia fiel e incremental de las fuentes + linaje (Auto Loader). Sin limpieza.",
    "silver": "Datos limpios, tipados, deduplicados, con relojes corregidos y SCD2. Fuente de verdad.",
    "gold": "Modelo dimensional (Kimball), marts por caso de negocio y metric views para Genie.",
    "ops": "Auditoría de ejecuciones, watermarks, resultados de calidad, cuarentena y accesos por parque.",
}


def create_namespace(spark: SparkSession, cfg: ProjectConfig) -> None:
    if is_databricks():  # pragma: no cover
        try:
            spark.sql(f"CREATE CATALOG IF NOT EXISTS {cfg.catalog} COMMENT 'Andes Viento Austral'")
        except Exception as exc:  # Free Edition / sin permisos: el catálogo se crea a mano por SQL
            print(f"No se pudo crear el catálogo {cfg.catalog} ({str(exc)[:120]}). Se asume que ya existe.")
    for layer in LAYERS:
        if is_databricks():  # pragma: no cover
            spark.sql(f"CREATE SCHEMA IF NOT EXISTS {cfg.schema(layer)} COMMENT '{LAYER_COMMENTS[layer]}'")
        else:
            spark.sql(f"CREATE DATABASE IF NOT EXISTS {cfg.schema(layer)}")
    ensure_ops_tables(spark, cfg)
    if is_databricks():  # pragma: no cover
        spark.sql(
            f"CREATE VOLUME IF NOT EXISTS {cfg.schema('landing')}.{cfg.volume} "
            "COMMENT 'Archivos crudos que llegan de SCADA, CMMS, CAMMESA, el proveedor de clima y Finanzas'"
        )


def ensure_ops_tables(spark: SparkSession, cfg: ProjectConfig) -> None:
    """Crea las tablas de `ops` antes de que las tasks paralelas escriban en ellas.

    Si dos tasks del for_each intentan crear la misma tabla a la vez, una falla
    con TABLE_ALREADY_EXISTS. Crearlas acá evita esa carrera.
    """
    from andes_viento.quality.expectations import DQ_RESULTS_SCHEMA
    from andes_viento.utils.audit import RUNS_SCHEMA, WATERMARK_SCHEMA

    quarantine = "table_name STRING, quarantined_at TIMESTAMP, failed_rules ARRAY<STRING>, record STRING"
    # quién ve qué parque (lo usa el row filter de gold). '*' = todos los parques.
    access = "principal STRING, park_code STRING, area STRING, granted_at TIMESTAMP"
    for name, schema in [("pipeline_runs", RUNS_SCHEMA), ("watermarks", WATERMARK_SCHEMA),
                         ("dq_results", DQ_RESULTS_SCHEMA), ("quarantine", quarantine), ("park_access", access)]:
        full = cfg.table("ops", name)
        if not spark.catalog.tableExists(full):
            spark.createDataFrame([], schema).write.format("delta").saveAsTable(full)
