"""Command-line interface for Low Tier batch benchmarks."""

from __future__ import annotations

import argparse

from benchmarks.low_tier import run_low_tier_benchmark
from cli.generate import _build_engine
from config import load_config, validate_benchmark_decoding


def build_parser() -> argparse.ArgumentParser:
    """Build the Low Tier benchmark argument parser."""

    parser = argparse.ArgumentParser(description="Run Low Tier batch benchmark")
    parser.add_argument("--config", required=True)
    parser.add_argument("--fixtures")
    parser.add_argument("--output", required=True)
    parser.add_argument("--decoding", default="greedy")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Low Tier benchmark CLI."""

    args = build_parser().parse_args(argv)
    validate_benchmark_decoding(args.decoding)
    config = load_config(args.config)
    engine = _build_engine(config)
    run_low_tier_benchmark(
        engine=engine,
        fixture_path=args.fixtures or config.benchmark.fixture_path,
        output_path=args.output,
        decoding=args.decoding,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
