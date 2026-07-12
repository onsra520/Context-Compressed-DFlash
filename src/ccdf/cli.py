"""CCDF command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ccdf.artifacts.writer import write_json
from ccdf.benchmark.workflow import evaluate_run_dir, run_benchmark
from ccdf.config import resolve_config, write_resolved_config
from ccdf.datasets.hashing import canonical_json, hash_text
from ccdf.datasets.io import read_jsonl
from ccdf.paths import find_shared_root, find_worktree_root, logical_path_metadata
from ccdf.prompts.schemas import PromptParts
from ccdf.runtime import RuntimeRequest, execute_request


def _find_fixture(dataset: str, fixture_id: str) -> dict[str, Any]:
    for subset in ["n10", "n30", "n100"]:
        resolved = resolve_config(dataset=dataset, subset=subset, condition_id="baseline-ar")
        path = Path(resolved.data["fixture_path"])
        for row in read_jsonl(path):
            if row["fixture_id"] == fixture_id:
                row["_subset"] = subset
                return row
    raise ValueError(f"fixture not found: {dataset}/{fixture_id}")


def _build_prompt(args: argparse.Namespace):
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
        execution_mode=measurement_mode,
    )
    result = execute_request(
        RuntimeRequest(
            resolved=resolved,
            prompt=prompt,
            prompt_parts=prompt_parts,
            reference_answer=reference,
            measurement_mode=measurement_mode,
        )
    )
    payload = {
        "cli_contract_version": "rec-t06a3.cli.v2",
        "condition": resolved.data["condition"],
        "dataset": dataset,
        "fixture_id": fixture_id,
        "fixture_content_hash": fixture_hash,
        "measurement_mode": measurement_mode,
        "prompt_hash": result["prompt"]["input_ids_hash"],
        "resolved_config_hash": resolved.sha256,
        **result,
    }
    if args.save:
        out_dir = Path(resolved.data["artifacts"]["root"]) / "Rec-T06A3" / "cli"
        out_dir.mkdir(parents=True, exist_ok=True)
        write_resolved_config(out_dir, resolved)
        save_path = out_dir / f"{args.condition}_{dataset}_{fixture_id}_{measurement_mode}.json"
        write_json(save_path, payload)
        payload["saved_path"] = str(save_path)
    if args.format == "json":
        print(canonical_json(payload))
        return 0

    timing = payload["timing"]
    generation_tok_s = payload["output_tokens"] / max(timing["decode_total_ms"] / 1000.0, 1e-9)
    print(f"Condition: {args.condition}")
    print(f"Answer: {payload['generated_text']}")
    if payload.get("validated_answer") is not None:
        print(f"Validated answer: {payload['validated_answer']}")
    print(f"Input tokens: {payload['input_tokens']}")
    print(f"Output tokens: {payload['output_tokens']}")
    print(f"Warm end-to-end: {timing['warm_request_e2e_ms']:.1f} ms")
    print(f"Generation-only request: {timing['generation_request_e2e_ms']:.1f} ms")
    print(f"Compression: {timing['compression_total_ms']:.1f} ms")
    print(f"Target prefill: {timing['target_prefill_ms']:.1f} ms")
    print(f"Decode: {timing['decode_total_ms']:.1f} ms")
    print(f"Generation tok/s: {generation_tok_s:.2f}")
    print(f"Stop reason: {payload['stop_reason']}")
    print(f"Cap hit: {payload['cap_hit']}")
    print(f"Repetition detected: {payload['repetition_detected']}")
    print(f"Instruction echo: {payload['instruction_echo_detected']}")
    print(f"Peak allocated GPU memory: {payload['vram']['peak_allocated_bytes'] / 2**30:.2f} GiB")
    print(f"Resource composition: {payload['resource_composition']}")
    if args.condition != "baseline-ar":
        dflash = payload["dflash"]
        print(f"Target block verifications: {dflash['target_block_verification_calls']}")
        print(f"Total target forwards: {dflash['total_target_forward_calls']}")
        print(f"Draft forwards: {dflash['draft_forward_calls']}")
        print(f"Effective tau: {dflash['effective_tau']:.3f}")
        print(f"Draft acceptance rate: {dflash['draft_acceptance_rate']:.3f}")
        print("Exact cached-AR token equivalence: NOT_CLAIMED")
    if args.condition == "cc-dflash-r2":
        compression = payload["compression"]
        print(f"Compression bypassed: {compression['bypassed']}")
        print(f"Compression bypass reason: {compression['bypass_reason']}")
        print(f"Full prompt reduction: {compression['token_scope']['full_prompt_reduction_pct']:.2f}%")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ccdf")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run")
    run.add_argument("--condition", required=True, choices=["baseline-ar", "dflash-r1", "llmlingua-ar-r2", "cc-dflash-r2"])
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
    benchmark.add_argument("--limit", type=int)
    benchmark.add_argument("--evaluate", action="store_true")
    benchmark.add_argument("--task-id", default="Rec-T06B1")
    benchmark.add_argument("--execution-mode", choices=["benchmark", "profiling", "smoke"], default="benchmark")

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--run-dir", required=True)

    sub.add_parser("paths")
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return run_command(args)
        if args.command == "benchmark":
            result = run_benchmark(
                dataset=args.dataset,
                subset=args.subset,
                conditions=args.conditions.split(","),
                output_dir=Path(args.output),
                limit=args.limit,
                execution_mode=args.execution_mode,
                task_id=args.task_id,
            )
            if args.evaluate:
                result["evaluation"] = evaluate_run_dir(Path(args.output))
            print(canonical_json(result))
            return 0
        if args.command == "evaluate":
            print(canonical_json(evaluate_run_dir(Path(args.run_dir))))
            return 0
        if args.command == "paths":
            worktree = find_worktree_root()
            print(canonical_json(logical_path_metadata(worktree, find_shared_root(worktree))))
            return 0
    except Exception as exc:
        print(f"ccdf: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
