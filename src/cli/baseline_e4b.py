"""Command-line interface for the Gemma E4B baseline benchmark."""

from __future__ import annotations

import argparse
import sys

from benchmarks.baseline_e4b import run_e4b_baseline
from cli.run_logging import RunLogSession
from config import load_config
from runtime.vllm_adapter import VllmGenerationAdapter, VllmModelHandle


def build_parser() -> argparse.ArgumentParser:
    """Build the Gemma E4B baseline argument parser."""

    parser = argparse.ArgumentParser(description="Run Gemma E4B autoregressive baseline")
    parser.add_argument("--config", required=True)
    parser.add_argument("--fixtures")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Gemma E4B baseline CLI."""

    command_argv = list(sys.argv[1:] if argv is None else argv)
    with RunLogSession("htfsd-baseline-e4b", command_argv) as run_log:
        args = build_parser().parse_args(command_argv)
        run_log.record_cli_args(args)
        run_log.record_artifact("baseline_output_path", args.output)
        run_log.record_metadata(fixture_path=args.fixtures)

        config = load_config(args.config)
        run_log.record_config(config, config_path=args.config)
        handle = VllmModelHandle.from_config(config.gemma_e4b_baseline)
        llm = handle.load()
        run_e4b_baseline(
            generation_adapter=VllmGenerationAdapter(handle),
            tokenizer=llm.get_tokenizer(),
            fixture_path=args.fixtures or config.benchmark.fixture_path,
            output_path=args.output,
        )
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
