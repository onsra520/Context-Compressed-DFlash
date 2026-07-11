"""CCDF command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ccdf.artifacts.writer import write_json
from ccdf.datasets.hashing import canonical_json, hash_text
from ccdf.datasets.io import read_jsonl
from ccdf.config import resolve_config, write_resolved_config
from ccdf.runtime import execute_request


def _find_fixture(dataset: str, fixture_id: str) -> dict[str, Any]:
    for subset in ["n10", "n30", "n100"]:
        path = Path("data/eval") / dataset / f"{dataset}_{subset}.jsonl"
        if not path.exists():
            continue
        for row in read_jsonl(path):
            if row["fixture_id"] == fixture_id:
                row["_subset"] = subset
                return row
    raise ValueError(f"fixture not found: {dataset}/{fixture_id}")


def _build_prompt(args: argparse.Namespace) -> tuple[str, str, str | None, str, str, str]:
    if args.dataset and args.fixture_id:
        fixture = _find_fixture(args.dataset, args.fixture_id)
        return (
            fixture["prompt"],
            fixture["dataset"],
            fixture["reference_answer"],
            fixture["fixture_id"],
            fixture["content_hash"],
            fixture["_subset"],
        )
    if args.prompt:
        return args.prompt, "gsm8k", None, "ad_hoc_prompt", hash_text(args.prompt), "n10"
    if args.context_file and args.question:
        context = Path(args.context_file).read_text(encoding="utf-8")
        prompt = (
            "Meeting transcript:\n"
            f"{context}\n\n"
            "Question:\n"
            f"{args.question}\n\n"
            "Answer using only the meeting transcript. A concise answer is enough."
        )
        return prompt, "qmsum", None, "ad_hoc_context_question", hash_text(prompt), "n10"
    raise ValueError("provide --prompt, or --context-file with --question, or --dataset with --fixture-id")


def run_command(args: argparse.Namespace) -> int:
    measurement_mode = "profiling" if args.profile else "benchmark"
    prompt, dataset, reference, fixture_id, fixture_hash, subset = _build_prompt(args)
    resolved = resolve_config(
        dataset=dataset,
        subset=subset,
        condition_id=args.condition,
        execution_mode="profiling" if args.profile else "benchmark",
    )
    result = execute_request(
        condition_id=args.condition,
        dataset=dataset,
        prompt=prompt,
        reference_answer=reference,
        measurement_mode=measurement_mode,
    )
    condition = resolved.data["condition"]
    payload = {
        "cli_contract_version": "rec-t02b1.cli.v1",
        "condition": condition,
        "dataset": dataset,
        "fixture_id": fixture_id,
        "fixture_content_hash": fixture_hash,
        "measurement_mode": measurement_mode,
        "prompt_hash": hash_text(prompt),
        "resolved_config_hash": resolved.sha256,
        **result,
    }
    if args.save:
        out_dir = Path("results/Rec-T02B1")
        out_dir.mkdir(parents=True, exist_ok=True)
        write_resolved_config(out_dir, resolved)
        save_path = out_dir / f"{args.condition}_{dataset}_{fixture_id}_{measurement_mode}.json"
        write_json(save_path, payload)
        payload["saved_path"] = str(save_path)
    if args.format == "json":
        print(canonical_json(payload))
    else:
        timing = payload["timing"]
        tok_s = payload["output_tokens"] / (timing["request_e2e_ms"] / 1000.0)
        print(f"Condition: {args.condition}")
        print(f"Answer: {payload['generated_text']}")
        print(f"Input tokens: {len(prompt.split())}")
        print(f"Output tokens: {payload['output_tokens']}")
        print(f"Request latency: {timing['request_e2e_ms']:.1f} ms")
        print(f"Generation tok/s: {tok_s:.2f}")
        print(f"Stop reason: {payload['stop_reason']}")
        if args.profile:
            print("Measurement mode: profiling")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ccdf")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--condition", required=True, choices=["baseline-ar", "dflash-r1", "cc-dflash-r2"])
    run.add_argument("--prompt")
    run.add_argument("--context-file")
    run.add_argument("--question")
    run.add_argument("--dataset", choices=["gsm8k", "qmsum"])
    run.add_argument("--fixture-id")
    run.add_argument("--profile", action="store_true")
    run.add_argument("--save", action="store_true")
    run.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return run_command(args)
    except Exception as exc:
        print(f"ccdf: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
