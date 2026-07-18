"""CLI for raw dataset fetching and deterministic preprocessing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import DatasetBuildConfig, build_datasets, fetch_sources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "build"])
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sample-size", type=int, default=10)
    args = parser.parse_args()
    if args.command == "fetch":
        print(json.dumps({key: str(value) for key, value in fetch_sources(args.raw_root).items()}, sort_keys=True))
        return
    if args.output_root is None:
        parser.error("--output-root is required for build")
    print(json.dumps(build_datasets(DatasetBuildConfig(args.raw_root, args.output_root, args.seed, args.sample_size)), sort_keys=True))


if __name__ == "__main__":
    main()
