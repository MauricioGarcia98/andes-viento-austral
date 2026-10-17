"""Ejecuta los scripts SQL de `sql/` sustituyendo `${catalogo.esquema}`.

Los marts, el gobierno y la capa semántica están escritos en SQL puro a propósito: es el
lenguaje que usan los analistas, Databricks SQL y Genie. Python sólo orquesta.
"""

from __future__ import annotations

import re
from pathlib import Path

from pyspark.sql import SparkSession

from andes_viento.config import LAYERS, ProjectConfig

SQL_DIR = Path(__file__).resolve().parents[3] / "sql"


def render(sql: str, cfg: ProjectConfig) -> str:
    for layer in LAYERS:
        sql = sql.replace("${" + layer + "}", cfg.schema(layer))
    return sql.replace("${catalog}", cfg.catalog)


def split_statements(sql: str) -> list[str]:
    """Separa por ';' de fin de sentencia ignorando comentarios de línea."""
    no_comments = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in no_comments.split(";") if s.strip()]


def run_sql_file(spark: SparkSession, cfg: ProjectConfig, path: Path) -> None:
    for stmt in split_statements(render(path.read_text(encoding="utf-8"), cfg)):
        spark.sql(stmt)


def run_sql_folder(spark: SparkSession, cfg: ProjectConfig, folder: str, skip_errors: bool = False) -> list[str]:
    """Corre todos los .sql de `sql/<folder>` en orden alfabético (01_, 02_, ...)."""
    done = []
    for path in sorted((SQL_DIR / folder).glob("*.sql")):
        try:
            run_sql_file(spark, cfg, path)
            done.append(path.stem)
        except Exception as exc:  # gobierno/semántica: algunas features no existen en Spark OSS local
            if not skip_errors:
                raise
            print(f"{path.name}: omitido ({str(exc).splitlines()[0][:160]})")
    return done


def build_marts(spark: SparkSession, cfg: ProjectConfig, sql_dir: Path | None = None) -> list[str]:
    folder = (sql_dir or SQL_DIR) / "marts"
    done = []
    for path in sorted(folder.glob("*.sql")):
        run_sql_file(spark, cfg, path)
        done.append(path.stem)
    return done

