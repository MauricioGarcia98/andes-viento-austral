"""Copia las instrucciones y las skills de Genie Code a tu carpeta del workspace.

    python scripts/install_assistant_files.py            # a /Users/<vos>/
    python scripts/install_assistant_files.py --workspace  # a /Workspace (para todo el workspace; requiere admin)

Genie Code lee `.assistant_instructions.md` (usuario) / `.assistant_workspace_instructions.md` (workspace)
y las skills de `.assistant/skills/<nombre>/SKILL.md`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.workspace import ImportFormat

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", action="store_true")
    args = ap.parse_args()
    w = WorkspaceClient()
    base = "/Workspace" if args.workspace else f"/Users/{w.current_user.me().user_name}"
    name = ".assistant_workspace_instructions.md" if args.workspace else ".assistant_instructions.md"
    files = {f"{base}/{name}": ROOT / ".assistant_instructions.md"}
    for skill in (ROOT / ".assistant" / "skills").glob("*/SKILL.md"):
        files[f"{base}/.assistant/skills/{skill.parent.name}/SKILL.md"] = skill
    for target, src in files.items():
        w.workspace.mkdirs(str(Path(target).parent))
        w.workspace.upload(target, src.read_bytes(), format=ImportFormat.AUTO, overwrite=True)
        print("subido", target)


if __name__ == "__main__":
    main()
