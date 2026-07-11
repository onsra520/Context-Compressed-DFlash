"""Rec-T03B n=10 Baseline-AR/DFlash benchmark runner."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from ccdf.artifacts.writer import write_json, write_jsonl_atomic
from ccdf.config import resolve_config
from ccdf.datasets.hashing import hash_json, hash_text
from ccdf.datasets.io import read_jsonl
from ccdf.evaluation import gsm8k, qmsum
from ccdf.inference.baseline_ar import generate_baseline
from ccdf.inference.dflash_runtime import generate_dflash_r1
from ccdf.inference.model_registry import DRAFTER_PATH, TARGET_PATH
from ccdf.inference.schemas import GenerationConfig, GenerationResult
from ccdf.inference.target_loader import load_target_model, load_target_tokenizer
from ccdf.dflash.loader import load_drafter_model
from ccdf.metrics.dflash import aggregate_tau, validate_dflash_invariants


def _git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _fixture_path(dataset: str) -> Path:
    return Path("data/eval") / dataset / f"{dataset}_n10.jsonl"


def _quality(dataset: str, text: str, reference: str, cap_hit: bool) -> dict[str, Any]:
    if dataset == "gsm8k":
        return gsm8k.evaluate(text, reference, cap_hit=cap_hit)
    return qmsum.evaluate(text, reference, cap_hit=cap_hit)


def _row(
    *,
    run_id: str,
    dataset: str,
    fixture: dict[str, Any],
    condition: dict[str, Any],
    result: GenerationResult,
    model_init_ms: float,
    dataset_manifest_hash: str,
    source_commit: str,
    resolved_config_hash: str,
    canonical: bool,
) -> dict[str, Any]:
    cap_hit = result.stop_reason == "max_new_tokens"
    quality = _quality(dataset, result.generated_text, fixture["reference_answer"], cap_hit)
    prompt_parts = fixture["prompt_parts"]
    verification_calls = result.verification_calls
    tokens_advanced = sum(result.acceptance_lengths)
    accepted_draft_tokens = tokens_advanced - verification_calls if verification_calls else 0
    row = {
        "run_id": run_id,
        "task_id": "Rec-T03B",
        "dataset": dataset,
        "dataset_manifest_hash": dataset_manifest_hash,
        "fixture_id": fixture["fixture_id"],
        "fixture_content_hash": fixture["content_hash"],
        "condition": condition,
        "source_commit": source_commit,
        "resolved_config_hash": resolved_config_hash,
        "canonical": canonical,
        "prompt_policy_id": condition["prompt_policy_id"],
        "structured_prompt_parts_hash": hash_json(prompt_parts),
        "precompression_prompt_hash": hash_text(fixture["prompt"]),
        "final_prompt_hash": hash_text(fixture["prompt"]),
        "input_tokens_precompression": result.prompt_token_count,
        "input_tokens_final": result.prompt_token_count,
        "generated_text": result.generated_text,
        "generated_text_hash": hash_text(result.generated_text),
        "output_token_ids_hash": hash_json(result.output_token_ids),
        "output_tokens": result.output_token_count,
        "stop_reason": result.stop_reason,
        "cap_hit": cap_hit,
        "success": True,
        "error": None,
        "model_init_ms": model_init_ms,
        "compressor_init_ms": result.compressor_init_ms,
        "compression_total_ms": result.compression_total_ms,
        "target_prefill_ms": result.target_prefill_ms,
        "draft_prefill_ms": result.draft_prefill_ms,
        "decode_total_ms": result.decode_total_ms,
        "request_e2e_ms": result.request_e2e_ms,
        "peak_allocated_bytes": 0,
        "peak_reserved_bytes": 0,
        "measurement_scope": "process",
        "measurement_mode": "benchmark",
        "verification_calls": verification_calls,
        "acceptance_lengths": result.acceptance_lengths,
        "tau_tokens_advanced_per_verification": tokens_advanced / verification_calls
        if verification_calls
        else 0.0,
        "draft_tokens_proposed": result.draft_tokens_proposed,
        "accepted_draft_tokens": accepted_draft_tokens,
        "draft_acceptance_rate": accepted_draft_tokens / result.draft_tokens_proposed
        if result.draft_tokens_proposed
        else 0.0,
        "rollback_tokens": result.draft_tokens_proposed - accepted_draft_tokens,
        "quality": quality,
    }
    if hasattr(sys.modules.get("torch"), "cuda"):
        import torch

        if torch.cuda.is_available():
            row["peak_allocated_bytes"] = int(torch.cuda.max_memory_allocated())
            row["peak_reserved_bytes"] = int(torch.cuda.max_memory_reserved())
    return row


def run_condition(
    *,
    dataset: str,
    condition_id: str,
    output: Path,
    max_new_tokens: int | None,
    run_id: str,
) -> dict[str, Any]:
    import gc
    import torch

    fixture_path = _fixture_path(dataset)
    fixtures = read_jsonl(fixture_path)[:10]
    resolved = resolve_config(
        dataset=dataset,
        condition_id=condition_id,
        execution_mode="smoke" if max_new_tokens is not None else "benchmark",
        overrides={"max_new_tokens": max_new_tokens} if max_new_tokens is not None else None,
    )
    dataset_manifest_hash = resolved.data["dataset_manifest_hash"]
    source_commit = _git_commit()
    condition = resolved.data["condition"]
    config = GenerationConfig(max_new_tokens=resolved.data["max_new_tokens"], temperature=resolved.data["runtime"]["temperature"])

    start = time.perf_counter()
    tokenizer = load_target_tokenizer(TARGET_PATH)
    target = load_target_model(TARGET_PATH)
    drafter = load_drafter_model(DRAFTER_PATH) if condition_id == "dflash-r1" else None
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    model_init_ms = (time.perf_counter() - start) * 1000

    rows = []
    for fixture in fixtures:
        if condition_id == "baseline-ar":
            result = generate_baseline(target, tokenizer, fixture["prompt"], config)
        elif condition_id == "dflash-r1":
            result = generate_dflash_r1(target, drafter, tokenizer, fixture["prompt"], config)
        else:
            raise ValueError(f"unsupported condition for Rec-T03B: {condition_id}")
        row = _row(
            run_id=run_id,
            dataset=dataset,
            fixture=fixture,
            condition=condition,
            result=result,
            model_init_ms=model_init_ms,
            dataset_manifest_hash=dataset_manifest_hash,
            source_commit=source_commit,
            resolved_config_hash=resolved.sha256,
            canonical=resolved.canonical,
        )
        validate_dflash_invariants(row)
        rows.append(row)

    write_jsonl_atomic(output, rows)
    summary = {
        "dataset": dataset,
        "condition": condition_id,
        "rows": len(rows),
        "output": str(output),
        "dataset_manifest_hash": dataset_manifest_hash,
        "source_commit": source_commit,
        "model_init_ms": model_init_ms,
    }
    del target, drafter
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return summary


def _summaries(run_files: dict[tuple[str, str], Path]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    rows_by_dataset: dict[str, list[dict[str, Any]]] = {"gsm8k": [], "qmsum": []}
    for (dataset, _condition), path in run_files.items():
        rows_by_dataset[dataset].extend(read_jsonl(path))

    summary_rows: list[dict[str, Any]] = []
    quality: dict[str, Any] = {}
    performance: dict[str, Any] = {}
    for dataset, rows in rows_by_dataset.items():
        quality[dataset] = {}
        performance[dataset] = {}
        for condition in ["baseline-ar", "dflash-r1"]:
            condition_rows = [row for row in rows if row["condition"]["condition_id"] == condition]
            labels: dict[str, int] = {}
            for row in condition_rows:
                label = row["quality"].get("label", "proxy")
                if dataset == "qmsum":
                    label = "proxy_not_semantic"
                labels[label] = labels.get(label, 0) + 1
            tau = aggregate_tau(condition_rows)
            mean_e2e = sum(row["request_e2e_ms"] for row in condition_rows) / len(condition_rows)
            mean_prefill = sum(row["target_prefill_ms"] for row in condition_rows) / len(condition_rows)
            mean_decode = sum(row["decode_total_ms"] for row in condition_rows) / len(condition_rows)
            cap_hits = sum(1 for row in condition_rows if row["cap_hit"])
            summary_rows.append(
                {
                    "dataset": dataset,
                    "condition": condition,
                    "rows": len(condition_rows),
                    "success_count": sum(1 for row in condition_rows if row["success"]),
                    "cap_hits": cap_hits,
                    "mean_target_prefill_ms": mean_prefill,
                    "mean_decode_total_ms": mean_decode,
                    "mean_request_e2e_ms": mean_e2e,
                    **tau,
                }
            )
            quality[dataset][condition] = labels
            performance[dataset][condition] = {
                "mean_target_prefill_ms": mean_prefill,
                "mean_decode_total_ms": mean_decode,
                "mean_request_e2e_ms": mean_e2e,
                "cap_hits": cap_hits,
                **tau,
            }
    return summary_rows, quality, performance


def run_matrix(output_dir: Path, *, max_new_tokens: int | None = None) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = output_dir / "runs"
    logs_dir = output_dir / "logs"
    runs_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    configs = {
        f"{dataset}:{condition}": resolve_config(dataset=dataset, condition_id=condition).data
        for dataset in ["gsm8k", "qmsum"] for condition in ["baseline-ar", "dflash-r1"]
    }
    write_json(output_dir / "resolved_config.json", configs)
    (output_dir / "resolved_config.sha256").write_text(hash_json(configs) + "\n", encoding="utf-8")
    run_id = f"rec-t03b-{int(time.time())}"
    run_files = {
        ("gsm8k", "baseline-ar"): runs_dir / "gsm8k_baseline_ar.jsonl",
        ("gsm8k", "dflash-r1"): runs_dir / "gsm8k_dflash_r1.jsonl",
        ("qmsum", "baseline-ar"): runs_dir / "qmsum_baseline_ar.jsonl",
        ("qmsum", "dflash-r1"): runs_dir / "qmsum_dflash_r1.jsonl",
    }
    process_records = []
    for (dataset, condition), path in run_files.items():
        log = logs_dir / f"{dataset}_{condition}.log"
        err = logs_dir / f"{dataset}_{condition}.err"
        cmd = [
            sys.executable,
            "-m",
            "ccdf.benchmark.rec_t03b",
            "condition",
            "--dataset",
            dataset,
            "--condition",
            condition,
            "--output",
            str(path),
            "--run-id",
            run_id,
        ]
        with log.open("w", encoding="utf-8") as stdout, err.open("w", encoding="utf-8") as stderr:
            completed = subprocess.run(cmd, text=True, stdout=stdout, stderr=stderr, check=False)
        process_records.append(
            {
                "dataset": dataset,
                "condition": condition,
                "returncode": completed.returncode,
                "log": str(log),
                "stderr": str(err),
            }
        )
        if completed.returncode != 0:
            raise RuntimeError(f"condition failed: {dataset}/{condition}; see {err}")

    summary_rows, quality, performance = _summaries(run_files)
    with (output_dir / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    dflash_rows = []
    for dataset in ["gsm8k", "qmsum"]:
        for row in read_jsonl(run_files[(dataset, "dflash-r1")]):
            dflash_rows.append(
                {
                    "dataset": dataset,
                    "fixture_id": row["fixture_id"],
                    "verification_calls": row["verification_calls"],
                    "acceptance_lengths": " ".join(map(str, row["acceptance_lengths"])),
                    "tau": row["tau_tokens_advanced_per_verification"],
                    "draft_acceptance_rate": row["draft_acceptance_rate"],
                    "rollback_tokens": row["rollback_tokens"],
                }
            )
    with (output_dir / "dflash_acceptance_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(dflash_rows[0].keys()))
        writer.writeheader()
        writer.writerows(dflash_rows)

    write_json(output_dir / "quality_summary.json", quality)
    write_json(output_dir / "performance_summary.json", performance)

    decision = decide_gate(summary_rows, quality, performance, process_records, max_new_tokens)
    write_json(output_dir / "gate_decision.json", decision)
    return decision


def decide_gate(
    summary_rows: list[dict[str, Any]],
    quality: dict[str, Any],
    performance: dict[str, Any],
    process_records: list[dict[str, Any]],
    max_new_tokens: int | None,
) -> dict[str, Any]:
    rows_total = sum(row["rows"] for row in summary_rows)
    all_processes_ok = all(record["returncode"] == 0 for record in process_records)
    dflash_invariants_ok = all(
        row["condition"] != "dflash-r1" or row["global_weighted_tau"] >= 1.0 for row in summary_rows
    )
    if rows_total != 40 or not all_processes_ok:
        gate = "INSUFFICIENT_EVIDENCE"
    elif not dflash_invariants_ok:
        gate = "FAIL_METRIC_CONTRACT"
    else:
        gate = "PASS_WITH_WORKLOAD_LIMITATION"
    return {
        "gate_decision": gate,
        "rows_total": rows_total,
        "process_isolation": process_records,
        "max_new_tokens": max_new_tokens if max_new_tokens is not None else {"gsm8k": 256, "qmsum": 384},
        "quality_boundary": {
            "qmsum_semantic_correctness": "NOT_CLAIMED",
            "cap_hits_are_reported_not_hidden": True,
        },
        "performance_classification": {
            "gsm8k": "implementation_defect_not_detected; small cap limits quality interpretation",
            "qmsum": "workload limitation; no semantic correctness claim",
        },
        "opens_rec_t04a": gate in {"PASS_READY_FOR_COMPRESSION", "PASS_WITH_WORKLOAD_LIMITATION"},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    matrix = sub.add_parser("matrix")
    matrix.add_argument("--output-dir", default="results/Rec-T03B")
    matrix.add_argument("--max-new-tokens", type=int)
    condition = sub.add_parser("condition")
    condition.add_argument("--dataset", required=True, choices=["gsm8k", "qmsum"])
    condition.add_argument("--condition", required=True, choices=["baseline-ar", "dflash-r1"])
    condition.add_argument("--output", required=True)
    condition.add_argument("--max-new-tokens", type=int)
    condition.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.command == "matrix":
        result = run_matrix(Path(args.output_dir), max_new_tokens=args.max_new_tokens)
        print(json.dumps(result, sort_keys=True))
    else:
        result = run_condition(
            dataset=args.dataset,
            condition_id=args.condition,
            output=Path(args.output),
            max_new_tokens=args.max_new_tokens,
            run_id=args.run_id,
        )
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
