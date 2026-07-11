#!/usr/bin/env python3
"""Manual coupled GSM8K/QMSum validation runner for Rec-T06A3.

This intentionally runs one condition at a time through the shared
RuntimeEngine. Rec-T06B will replace it with canonical subprocess isolation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ccdf.benchmark.workflow import evaluate_run_dir, run_benchmark


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["n3", "n10"], required=True)
    parser.add_argument("--output-root", default="results/Rec-T06A3")
    args = parser.parse_args()
    limit = 3 if args.stage == "n3" else None
    subset = "n10"
    root = Path(args.output_root) / args.stage
    # n3 proves integration for all three conditions. n10 keeps the A3 gate
    # focused and faster: Baseline versus efficient DFlash. CC-DFlash n10 and
    # canonical timing/provenance belong to the resumed Rec-T06B/D workflow.
    matrix = (
        {
            "gsm8k": ["baseline-ar", "dflash-r1", "cc-dflash-r2"],
            "qmsum": ["baseline-ar", "dflash-r1", "cc-dflash-r2"],
        }
        if args.stage == "n3"
        else {
            "gsm8k": ["baseline-ar", "dflash-r1"],
            "qmsum": ["baseline-ar", "dflash-r1"],
        }
    )
    for dataset, conditions in matrix.items():
        output = root / dataset
        run_benchmark(
            dataset=dataset,
            subset=subset,
            conditions=conditions,
            output_dir=output,
            limit=limit,
            execution_mode="smoke" if limit else "benchmark",
            task_id="Rec-T06A3",
        )
        evaluate_run_dir(output)
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
