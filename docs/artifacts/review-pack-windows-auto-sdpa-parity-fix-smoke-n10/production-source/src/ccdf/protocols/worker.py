"""Single-condition worker for the isolated four-condition protocol."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..config import load_config
from .orchestrator import _run_condition, _write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(f"resume is disabled; worker output exists: {args.output}")
    source = load_config(args.config)
    profile = source.resolve_active_protocol_profile()
    condition_spec = next(
        item for item in profile.require("conditions")
        if str(item["name"]) == args.condition
    )
    prepared = json.loads(args.prepared.read_text(encoding="utf-8"))
    lifecycle: list[dict] = []
    condition_run = _run_condition(
        condition_spec=condition_spec,
        prepared=prepared,
        config=profile.config,
        lifecycle=lifecycle,
        dataset=str(profile.require("dataset")),
    )
    _write_json(args.output, {
        "condition": args.condition,
        "condition_run": condition_run,
        "lifecycle": lifecycle,
    })


if __name__ == "__main__":
    main()
