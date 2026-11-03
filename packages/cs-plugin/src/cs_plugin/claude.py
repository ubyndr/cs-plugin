"""Running Claude Code's own `claude plugin` commands: the only code that does."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from . import project


def available() -> bool:
    return shutil.which("claude") is not None


def run(*args: str) -> subprocess.CompletedProcess:
    out = subprocess.run(["claude", *args], capture_output=True, text=True)
    if out.returncode != 0:
        raise project.ProjectError(f"claude {' '.join(args)} failed:\n{out.stdout}{out.stderr}")
    return out


def installed(cfg: project.Config, root: Path) -> dict[str, str]:
    """Plugin -> version, for this project's plugins installed in this project."""
    rows = json.loads(run("plugin", "list", "--json").stdout or "[]")
    here = str(root.resolve())
    suffix = f"@{cfg.marketplace}"
    return {r["id"][: -len(suffix)]: r.get("version", "")
            for r in rows
            if r.get("id", "").endswith(suffix) and r.get("scope") == "project"
            and str(Path(r.get("projectPath", "")).resolve()) == here}
