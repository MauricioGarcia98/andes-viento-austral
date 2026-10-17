"""Evalúa los Genie Agents contra sus benchmarks (respuesta esperada = SQL del YAML).

    python scripts/genie_eval.py --target dev                  # los 4 agents
    python scripts/genie_eval.py --target dev --only 03_comercial_ppa --limit 5
    python scripts/genie_eval.py --target dev --expected-only  # sólo calcula las respuestas esperadas

Para cada benchmark:
  1. corre el SQL esperado en el warehouse (Statement Execution API) -> respuesta esperada,
  2. le hace la misma pregunta a Genie (Conversation API) -> respuesta de Genie,
  3. compara: mismos valores (números con 1 % de tolerancia, textos sin mayúsculas/acentos).
Escribe docs/genie/resultados_benchmarks.md (y un JSON con el detalle).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from pathlib import Path

import yaml
from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from andes_viento.genie.conversation import GenieClient  # noqa: E402

CATALOGS = {"dev": "andes_viento_dev", "prod": "andes_viento"}


def run_sql(w: WorkspaceClient, warehouse: str, sql: str) -> tuple[list[str], list[list]]:
    r = w.statement_execution.execute_statement(statement=sql, warehouse_id=warehouse, wait_timeout="50s")
    while r.status.state.value in ("PENDING", "RUNNING"):
        time.sleep(2)
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state.value != "SUCCEEDED":
        raise RuntimeError(r.status.error.message if r.status.error else r.status.state.value)
    cols = [c.name for c in r.manifest.schema.columns]
    return cols, (r.result.data_array or []) if r.result else []


def _norm(v) -> str:
    s = "" if v is None else str(v).strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def values_match(expected: list[list], got: list[list]) -> bool:
    """¿La respuesta de Genie contiene los valores esperados? (orden de columnas libre)."""
    if not expected:
        return not got
    exp_vals = [v for row in expected[:20] for v in row]
    got_vals = [v for row in got[:200] for v in row]
    got_nums = [x for x in (_num(v) for v in got_vals) if x is not None]
    got_txt = {_norm(v) for v in got_vals}
    for v in exp_vals:
        n = _num(v)
        if n is not None:
            # Genie puede devolver el % como 18.4 en vez de 0.184: se aceptan las dos escalas
            if not any(abs(g - k) <= max(abs(k) * 0.01, 0.051) for g in got_nums for k in (n, n * 100, n / 100)):
                return False
        elif _norm(v) not in got_txt:
            return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="dev", choices=list(CATALOGS))
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--expected-only", action="store_true")
    ap.add_argument("--warehouse", default="Serverless Starter Warehouse")
    args = ap.parse_args()
    w = WorkspaceClient()
    wh = next(x.id for x in w.warehouses.list() if x.name == args.warehouse)
    deployed = {}
    dep = ROOT / "genie" / f"deployed_{args.target}.json"
    if dep.exists():
        deployed = json.loads(dep.read_text())
    catalog = CATALOGS[args.target]
    results = []
    for path in sorted((ROOT / "genie" / "src").glob("*.yml")):
        slug = path.stem
        if args.only and slug not in args.only:
            continue
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        bms = spec["benchmarks"][: args.limit or None]
        client = GenieClient(w, deployed[slug]) if (slug in deployed and not args.expected_only) else None
        for b in bms:
            sql = b["sql"].replace("${catalog}", catalog)
            rec = {"agent": slug, "question": b["q"], "expected_sql": sql}
            try:
                _, rows = run_sql(w, wh, sql)
                rec["expected"] = rows[:5]
            except Exception as exc:
                rec["expected_error"] = str(exc)[:300]
                results.append(rec)
                print(f"❌ SQL esperado falla · {slug} · {b['q']}: {rec['expected_error']}")
                continue
            if client:
                ans = client.ask(b["q"])
                rec.update(genie_status=ans.status, genie_sql=ans.sql, genie_rows=ans.rows[:5], genie_text=ans.text)
                rec["match"] = ans.status == "COMPLETED" and values_match(rows, ans.rows)
                time.sleep(3)  # la API de Genie tiene límite de preguntas por minuto
            results.append(rec)
            print(f"{'✅' if rec.get('match') else '·' if client is None else '❌'} {slug} · {b['q']} -> {rec['expected'][:1]}")
    out = ROOT / "docs" / "genie"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"resultados_benchmarks_{args.target}.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    lines = ["# Resultados de los benchmarks de Genie", "",
             f"Target `{args.target}` · generado por `scripts/genie_eval.py`.", "",
             "| agent | pregunta | respuesta esperada | Genie |", "|---|---|---|---|"]
    by_agent: dict[str, list] = {}
    for r in results:
        by_agent.setdefault(r["agent"], []).append(r)
        exp = r.get("expected_error") or ", ".join(str(v) for v in (r.get("expected") or [[]])[0])
        mark = "—" if "match" not in r else ("✅" if r["match"] else "❌")
        lines.append(f"| {r['agent']} | {r['question']} | `{exp[:80]}` | {mark} |")
    lines += ["", "| agent | benchmarks | aciertos |", "|---|---|---|"]
    for a, rs in by_agent.items():
        ok = sum(1 for r in rs if r.get("match"))
        lines.append(f"| {a} | {len(rs)} | {ok if any('match' in r for r in rs) else '—'} |")
    (out / "resultados_benchmarks.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nResultados en {out / 'resultados_benchmarks.md'}")


if __name__ == "__main__":
    main()
