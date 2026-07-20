"""
Worker subprocess entry point.

Runs inside its own process, isolated from the FastAPI server.
Prints exactly one JSON line to stdout (success or error).
stderr is for diagnostics (torch warnings, etc.) — not used for failure detection.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback

from .runtime_adapter import run_demo_condition
from .metric_normalizer import normalize_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="CC-DFlash demo worker")
    parser.add_argument("--context", type=str, default="")
    parser.add_argument("--question", type=str, required=True)
    parser.add_argument("--condition", type=str, required=True)
    args = parser.parse_args()

    try:
        raw_result = run_demo_condition(
            context=args.context,
            question=args.question,
            condition_id=args.condition,
        )
        normalized = normalize_metrics(raw_result)
        # Single JSON line on stdout — orchestrator scans for this.
        sys.stdout.write(json.dumps({"status": "success", "data": normalized}) + "\n")
        sys.stdout.flush()
    except Exception as exc:
        # Still a single JSON line; returncode will be 1.
        sys.stdout.write(
            json.dumps(
                {
                    "status": "error",
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )
            + "\n"
        )
        sys.stdout.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()
