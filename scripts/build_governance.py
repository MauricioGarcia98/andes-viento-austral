"""Genera el SQL de gobierno y el diccionario de datos desde governance/data_dictionary.yml.

    python scripts/build_governance.py

Salidas (versionadas en el repo; el Job ejecuta el SQL en la task `governance`):
    sql/governance/01_comments.sql
    sql/governance/02_constraints.sql
    sql/governance/03_tags.sql
    docs/04_diccionario_de_datos.md
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DICT = ROOT / "governance" / "data_dictionary.yml"
HEADER = "-- GENERADO por scripts/build_governance.py desde governance/data_dictionary.yml. No editar a mano.\n"


def q(text: str) -> str:
    return text.replace("'", "\\'")


def col_parts(spec) -> tuple[str, dict]:
    if isinstance(spec, list):
        return spec[0], (spec[1] if len(spec) > 1 else {})
    return spec, {}


def build(tables: dict) -> tuple[str, str, str, str]:
    comments, constraints, tags = [HEADER], [HEADER], [HEADER]
    doc = ["# 04 · Diccionario de datos (gold)", "",
           "> Generado desde `governance/data_dictionary.yml`. Data Steward: Florencia Paz.", "",
           "| tabla | dominio | dueño | grano |", "|---|---|---|---|"]
    for name, t in tables.items():
        doc.append(f"| [`{name}`](#{name}) | {t['domain']} | {t['owner']} | {t['grain']} |")
    doc.append("")
    for name, t in tables.items():
        full = "${gold}." + name
        comments.append(f"COMMENT ON TABLE {full} IS '{q(t['comment'])} Grano: {q(t['grain'])}.';")
        doc += [f"## {name}", "", t["comment"], "", f"**Grano:** {t['grain']} · **Dueño:** {t['owner']}", ""]
        if t.get("pk"):
            doc.append(f"**PK:** `{', '.join(t['pk'])}`  ")
        if t.get("fks"):
            doc.append("**FK:** " + ", ".join(f"`{c}` → `{r}`" for c, r in t["fks"].items() if r) + "  ")
        doc += ["", "| columna | descripción | etiquetas |", "|---|---|---|"]
        for col, spec in t.get("columns", {}).items():
            text, ctags = col_parts(spec)
            comments.append(f"ALTER TABLE {full} ALTER COLUMN {col} COMMENT '{q(text)}';")
            if ctags:
                kv = ", ".join(f"'{k}' = '{v}'" for k, v in ctags.items())
                tags.append(f"ALTER TABLE {full} ALTER COLUMN {col} SET TAGS ({kv});")
            doc.append(f"| `{col}` | {text} | {', '.join(f'{k}={v}' for k, v in ctags.items())} |")
        doc.append("")
        ttags = {"dominio": t["domain"], "duenio": t["owner"].split(" (")[0], **t.get("tags", {})}
        tags.append(f"ALTER TABLE {full} SET TAGS ({', '.join(f'{chr(39)}{k}{chr(39)} = {chr(39)}{q(v)}{chr(39)}' for k, v in ttags.items())});")
        if t.get("pk") and not name.startswith("mart_"):
            for c in t["pk"]:
                constraints.append(f"ALTER TABLE {full} ALTER COLUMN {c} SET NOT NULL;")
            constraints.append(f"ALTER TABLE {full} DROP CONSTRAINT IF EXISTS pk_{name} CASCADE;")
            rely = " RELY" if name.startswith("dim_") else ""
            constraints.append(f"ALTER TABLE {full} ADD CONSTRAINT pk_{name} PRIMARY KEY ({', '.join(t['pk'])}){rely};")
    for name, t in tables.items():
        for col, ref in (t.get("fks") or {}).items():
            if not ref:
                continue
            rt, rc = ref.split(".")
            constraints.append(f"ALTER TABLE ${{gold}}.{name} DROP CONSTRAINT IF EXISTS fk_{name}_{col};")
            constraints.append(f"ALTER TABLE ${{gold}}.{name} ADD CONSTRAINT fk_{name}_{col} FOREIGN KEY ({col}) "
                               f"REFERENCES ${{gold}}.{rt} ({rc});")
    return "\n".join(comments) + "\n", "\n".join(constraints) + "\n", "\n".join(tags) + "\n", "\n".join(doc) + "\n"


def main() -> None:
    tables = yaml.safe_load(DICT.read_text(encoding="utf-8"))["tables"]
    c, k, t, d = build(tables)
    out = ROOT / "sql" / "governance"
    out.mkdir(parents=True, exist_ok=True)
    (out / "01_comments.sql").write_text(c, encoding="utf-8")
    (out / "02_constraints.sql").write_text(k, encoding="utf-8")
    (out / "03_tags.sql").write_text(t, encoding="utf-8")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "04_diccionario_de_datos.md").write_text(d, encoding="utf-8")
    print(f"{len(tables)} tablas -> sql/governance/ y docs/04_diccionario_de_datos.md")


if __name__ == "__main__":
    main()
