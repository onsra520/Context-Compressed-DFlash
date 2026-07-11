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
from ccdf.benchmark.workflow import evaluate_run_dir, run_benchmark
from ccdf.prompts.schemas import PromptParts
from ccdf.runtime import RuntimeRequest, execute_request


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


def _build_prompt(args: argparse.Namespace) -> tuple[str | None, PromptParts | None, str, str | None, str, str, str]:
    if args.dataset and args.fixture_id:
        fixture = _find_fixture(args.dataset, args.fixture_id)
        return (
            None,
            PromptParts(**fixture["prompt_parts"]),
            fixture["dataset"],
            fixture["reference_answer"],
            fixture["fixture_id"],
            fixture["content_hash"],
            fixture["_subset"],
        )
    if args.prompt:
        return args.prompt, None, "gsm8k", None, "ad_hoc_prompt", hash_text(args.prompt), "n10"
    if args.context_file and args.question:
        context = Path(args.context_file).read_text(encoding="utf-8")
        parts = PromptParts(context=context, question=args.question, instruction="")
        return None, parts, "qmsum", None, "ad_hoc_context_question", hash_text(context + args.question), "n10"
    raise ValueError("provide --prompt, or --context-file with --question, or --dataset with --fixture-id")


def run_command(args: argparse.Namespace) -> int:
    measurement_mode = "profiling" if args.profile else "benchmark"
    prompt, prompt_parts, dataset, reference, fixture_id, fixture_hash, subset = _build_prompt(args)
    resolved = resolve_config(
        dataset=dataset,
        subset=subset,
        condition_id=args.condition,
        execution_mode="profiling" if args.profile else "benchmark",
    )
    if prompt_parts is not None and not prompt_parts.instruction:
        prompt_parts = PromptParts(context=prompt_parts.context, question=prompt_parts.question, instruction=resolved.data["prompt_policy"]["text"])
    result = execute_request(RuntimeRequest(resolved=resolved, prompt=prompt, prompt_parts=prompt_parts, reference_answer=reference, measurement_mode=measurement_mode))
    condition = resolved.data["condition"]
    payload = {
        "cli_contract_version": "rec-t02b1.cli.v1",
        "condition": condition,
        "dataset": dataset,
        "fixture_id": fixture_id,
        "fixture_content_hash": fixture_hash,
        "measurement_mode": measurement_mode,
        "prompt_hash": hash_text(result["final_prompt"]),
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
        print(f"Input tokens: {payload['input_tokens']}")
        print(f"Output tokens: {payload['output_tokens']}")
        print(f"Total latency: {timing['request_e2e_ms']:.1f} ms")
        print(f"Target prefill: {timing['target_prefill_ms']:.1f} ms")
        print(f"Generation: {timing['decode_total_ms']:.1f} ms")
        print(f"Generation tok/s: {tok_s:.2f}")
        print(f"Stop reason: {payload['stop_reason']}")
        print(f"Cap hit: {payload['cap_hit']}")
        print(f"Peak allocated GPU memory: {payload['vram']['peak_allocated_bytes'] / 2**20:.1f} MiB")
        print(f"Peak reserved GPU memory: {payload['vram']['peak_reserved_bytes'] / 2**20:.1f} MiB")
        if args.condition != "baseline-ar":
            dflash = payload["dflash"]
            print(f"Verification calls: {dflash['verification_calls']}")
            print(f"Accepted draft tokens: {dflash['accepted_draft_tokens']}")
            print(f"Draft tokens proposed: {dflash['draft_tokens_proposed']}")
            print(f"Rollback tokens: {dflash['rollback_tokens']}")
        if args.condition == "cc-dflash-r2":
            compression = payload["compression"]
            print(f"Compression bypassed: {compression['bypassed']}")
            print(f"Compression bypass reason: {compression['bypass_reason']}")
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
    benchmark = sub.add_parser("benchmark")
    benchmark.add_argument("--dataset", required=True, choices=["gsm8k", "qmsum"])
    benchmark.add_argument("--subset", required=True, choices=["n10", "n30", "n100"])
    benchmark.add_argument("--conditions", required=True)
    benchmark.add_argument("--output", required=True)
    benchmark.add_argument("--evaluate", action="store_true")
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return run_command(args)
        if args.command == "benchmark":
            result = run_benchmark(dataset=args.dataset, subset=args.subset, conditions=args.conditions.split(","), output_dir=Path(args.output))
            if args.evaluate:
                result["evaluation"] = evaluate_run_dir(Path(args.output))
            print(canonical_json(result))
            return 0
        if args.command == "evaluate":
            print(canonical_json(evaluate_run_dir(Path(args.run_dir))))
            return 0
    except Exception as exc:
        print(f"ccdf: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
