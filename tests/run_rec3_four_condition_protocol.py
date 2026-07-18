"""Smoke wrapper for the tracked, config-driven REC-3 orchestration."""

from __future__ import annotations

import argparse
import json

from ccdf.config import load_config
from ccdf.protocols import run_active_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the active REC-3 config profile")
    parser.add_argument("--config", required=True, help="Trusted config.yml path")
    args = parser.parse_args()
    source_config = load_config(args.config)
    summary = run_active_profile(source_config)
    print(json.dumps(summary, sort_keys=True))
    if not summary["overall_pass"]:
        raise SystemExit("REC-3 active profile has failing hard gates")


if __name__ == "__main__":
    main()
