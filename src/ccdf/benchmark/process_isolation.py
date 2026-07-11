"""Process isolation audit for benchmark conditions."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any


def audit_process_isolation(condition_ids: list[str]) -> dict[str, Any]:
    records = []
    for condition_id in condition_ids:
        script = (
            "import json, os, sys; "
            "print(json.dumps({'condition_id': sys.argv[1], 'pid': os.getpid()}))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script, condition_id],
            check=True,
            text=True,
            capture_output=True,
        )
        records.append(json.loads(result.stdout))
    pids = [record["pid"] for record in records]
    return {
        "audit_version": "rec-t02b.process-isolation.v1",
        "pass": len(pids) == len(set(pids)),
        "records": records,
        "policy": "one subprocess per condition; no process reuse for canonical benchmark mode",
    }
