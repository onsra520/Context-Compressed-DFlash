#!/usr/bin/env python3
"""Validation-only canonical command-stack runner."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "audit" / "canonical-freeze"
ARTIFACTS = ROOT / "docs" / "artifacts"


def run(label: str, command: list[str], environment: dict[str, str]) -> dict[str, object]:
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=ROOT, env=environment, text=True, capture_output=True, check=False)
    return {
        "label": label, "command": command, "exit_code": completed.returncode,
        "stdout": completed.stdout, "stderr": completed.stderr,
        "duration_seconds": time.perf_counter() - started,
    }


def main() -> int:
    AUDIT.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update({"PROJECT_ROOT": str(ROOT), "PYTHONHASHSEED": "42", "CUBLAS_WORKSPACE_CONFIG": ":4096:8"})
    python = ROOT / ".venv/bin/python"
    pytest = ROOT / ".venv/bin/pytest"
    commands = [
        ("compileall", [str(python), "-m", "compileall", "-q", "src", "scripts", "tests"]),
        ("pytest", [str(pytest), "-q"]),
    ]
    records = [run(label, command, environment) for label, command in commands]
    payload = {"commands": records, "pass": all(record["exit_code"] == 0 for record in records)}
    (AUDIT / "command-logs.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": payload["pass"], "exit_codes": {record["label"]: record["exit_code"] for record in records}}))
    return 0 if payload["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
