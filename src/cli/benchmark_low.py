"""Command-line interface for Low Tier batch benchmarks."""

from __future__ import annotations

import argparse
import sys

from benchmarks.low_tier import run_low_tier_benchmark
from cli.generate import _build_engine
from cli.run_logging import RunLogSession
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

    command_argv = list(sys.argv[1:] if argv is None else argv)
    with RunLogSession("htfsd-benchmark-low", command_argv) as run_log:
        args = build_parser().parse_args(command_argv)
        run_log.record_cli_args(args)
        run_log.record_artifact("benchmark_output_path", args.output)
        run_log.record_metadata(decoding_mode=args.decoding, fixture_path=args.fixtures)

        validate_benchmark_decoding(args.decoding)
        config = load_config(args.config)
        run_log.record_config(config, config_path=args.config)
        engine = _build_engine(config)
        run_low_tier_benchmark(
            engine=engine,
            fixture_path=args.fixtures or config.benchmark.fixture_path,
            output_path=args.output,
            decoding=args.decoding,
        )
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
