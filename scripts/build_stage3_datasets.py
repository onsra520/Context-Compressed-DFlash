#!/usr/bin/env python3
"""Build and audit the deterministic Stage 3 n=10 datasets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ccdf.datasets import build_dataset_pipeline
from ccdf.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument(
        "--selection",
        type=Path,
        default=Path("data/manifests/dataset_smoke_selection.json"),
    )
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--config", default="config.yml")
    args = parser.parse_args()
    result = build_dataset_pipeline(
        data_root=args.data_root,
        selection_path=args.selection,
        config=load_config(args.config),
        audit_path=args.audit,
    )
    print(json.dumps({"pass": result["pass"], "datasets": result["datasets"]}, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
