"""Run one command once and persist stdout, stderr, exit code, and duration."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a command is required after --")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = output_dir / f"{args.label}.stdout.txt"
    stderr_path = output_dir / f"{args.label}.stderr.txt"
    record_path = output_dir / f"{args.label}.json"
    environment = os.environ.copy()
    environment.update({
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "PYTHONFAULTHANDLER": "1",
    })
    started_at_utc = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    duration = time.perf_counter() - started
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    record = {
        "label": args.label,
        "command": command,
        "attempt": 1,
        "retry_count": 0,
        "resume_enabled": False,
        "exit_code": completed.returncode,
        "signal": -completed.returncode if completed.returncode < 0 else None,
        "native_crash_code": (
            f"0x{completed.returncode & 0xFFFFFFFF:08X}"
            if completed.returncode not in (0, 1, 2) else None
        ),
        "duration_seconds": duration,
        "started_at_utc": started_at_utc,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_faulthandler_environment": environment.get("PYTHONFAULTHANDLER"),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, sort_keys=True))
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
