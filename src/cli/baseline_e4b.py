from __future__ import annotations

import argparse

from benchmarks.baseline_e4b import run_e4b_baseline
from config import load_config
from runtime.vllm_adapter import VllmGenerationAdapter, VllmModelHandle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Gemma E4B autoregressive baseline")
    parser.add_argument("--config", required=True)
    parser.add_argument("--fixtures")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    handle = VllmModelHandle.from_config(config.gemma_e4b_baseline)
    llm = handle.load()
    run_e4b_baseline(
        generation_adapter=VllmGenerationAdapter(handle),
        tokenizer=llm.get_tokenizer(),
        fixture_path=args.fixtures or config.benchmark.fixture_path,
        output_path=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
