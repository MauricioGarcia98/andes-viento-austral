"""Ejecuta los scripts SQL de `sql/` sustituyendo `${catalogo.esquema}`.

Los marts, el gobierno y la capa semántica están escritos en SQL puro a propósito: es el
lenguaje que usan los analistas, Databricks SQL y Genie. Python sólo orquesta.
"""

from __future__ import annotations

import hashlib
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
    """Separa un script en sentencias por `;`, respetando strings ('...', "..."), identificadores
    (`...`), bloques $$...$$ (YAML de metric views) y comentarios `--` (que se descartan).

    Error real (bitácora): la versión anterior cortaba por cualquier `;` y rompía los COMMENT
    del diccionario que tienen punto y coma adentro.
    """
    out, buf, i, n = [], [], 0, len(sql)
    quote: str | None = None
    while i < n:
        ch = sql[i]
        if quote:
            buf.append(ch)
            if quote == "$$" and sql.startswith("$$", i):
                buf.append("$")
                i += 2
                quote = None
                continue
            if quote in ("'", '"') and ch == "\\" and i + 1 < n:
                buf.append(sql[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j == -1 else j
            continue
        if sql.startswith("$$", i):
            quote = "$$"
            buf.append("$$")
            i += 2
            continue
        if ch in ("'", '"', "`"):
            quote = ch
        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
        else:
            buf.append(ch)
        i += 1
    stmt = "".join(buf).strip()
    if stmt:
        out.append(stmt)
    return out


_VIEW_RE = re.compile(r"^\s*CREATE\s+OR\s+REPLACE\s+VIEW\s+([\w.`]+)", re.IGNORECASE)


def view_name(stmt: str) -> str | None:
    """Nombre de la vista si la sentencia es un CREATE OR REPLACE VIEW (también metric views)."""
    m = _VIEW_RE.match(stmt)
    return m.group(1).replace("`", "") if m else None


def fingerprint(stmt: str) -> str:
    return hashlib.sha256(" ".join(stmt.split()).encode("utf-8")).hexdigest()


def run_sql_file(spark: SparkSession, cfg: ProjectConfig, path: Path) -> None:
    """Corre un script. Las vistas sólo se recrean si cambió su definición.

    Error real (bitácora R14): cada CREATE OR REPLACE VIEW crea un objeto nuevo y deja el viejo
    "borrado" ~7 días, y Unity Catalog lo cuenta en la cuota de 500 tablas de Free Edition.
    Con 10 vistas y un job diario eso eran ~70 objetos fantasma por target.
    """
    fp_table = cfg.table("ops", "sql_fingerprints")
    known: dict[str, str] | None = None
    for stmt in split_statements(render(path.read_text(encoding="utf-8"), cfg)):
        name = view_name(stmt)
        if name is None:
            spark.sql(stmt)
            continue
        if known is None:
            spark.sql(f"CREATE TABLE IF NOT EXISTS {fp_table} (object_name STRING, sha256 STRING, updated_at TIMESTAMP) USING DELTA")
            known = {r.object_name: r.sha256 for r in spark.table(fp_table).collect()}
        sha = fingerprint(stmt)
        if known.get(name) == sha and spark.catalog.tableExists(name):
            continue
        spark.sql(stmt)
        spark.sql(f"DELETE FROM {fp_table} WHERE object_name = '{name}'")
        spark.sql(f"INSERT INTO {fp_table} VALUES ('{name}', '{sha}', current_timestamp())")
        known[name] = sha


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

