"""Preguntarle a un Genie Agent desde la consola (ejemplo de la Conversation API).

    python scripts/genie_ask.py --agent 01_operacion_parques "¿Por qué Cañadón León generó menos en julio 2025?"
    python scripts/genie_ask.py --space <space_id> "¿Qué turbinas tienen riesgo alto hoy?" --follow "¿Y en Santa Cruz?"

El space se toma de genie/deployed_<target>.json (lo escribe scripts/deploy_genie.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from andes_viento.genie.conversation import GenieClient  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--agent", default="01_operacion_parques")
    ap.add_argument("--space")
    ap.add_argument("--target", default="dev")
    ap.add_argument("--follow", action="append", default=[], help="Repreguntas en la misma conversación")
    args = ap.parse_args()
    space = args.space or json.loads((ROOT / "genie" / f"deployed_{args.target}.json").read_text())[args.agent]
    client = GenieClient(WorkspaceClient(), space)
    conv = None
    for q in [args.question, *args.follow]:
        ans = client.ask(q, conv)
        conv = ans.conversation_id
        print(f"\n🙋 {q}\n🧞 [{ans.status}] {ans.text}")
        if ans.sql:
            print(f"\n-- SQL generado por Genie --\n{ans.sql}\n")
            print(" | ".join(ans.columns))
            for row in ans.rows[:15]:
                print(" | ".join("" if v is None else str(v) for v in row))
        if ans.error:
            print("⚠️", ans.error)


if __name__ == "__main__":
    main()
