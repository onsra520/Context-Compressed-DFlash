"""Legacy noncanonical Rec-T04B runner; cannot create Rec-T06B artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ccdf.artifacts.writer import write_json, write_jsonl_atomic
from ccdf.config import resolve_config
from ccdf.compression.llmlingua import LLMLinguaCompressor
from ccdf.compression.passthrough import PassthroughCompressor
from ccdf.compression.schemas import CompressionConfig, CompressionResult
from ccdf.compression.validation import prompt_invariants, token_scope_audit
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
from ccdf.prompts.renderer import render_prompt
from ccdf.prompts.schemas import PromptParts


def _git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], check=True, text=True, capture_output=True).stdout.strip()


def _fixture_path(dataset: str) -> Path:
    return Path("data/eval") / dataset / f"{dataset}_n30.jsonl"


def _parts(fixture: dict[str, Any]) -> PromptParts:
    pp = fixture["prompt_parts"]
    return PromptParts(
        context=pp["context"],
        question=pp["question"],
        instruction=pp["instruction"],
        system=pp.get("system"),
    )


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
    prompt: str,
    pre_prompt: str,
    prompt_audit: dict[str, Any],
    compression: CompressionResult | None,
    token_audit: dict[str, Any] | None,
    result: GenerationResult,
    model_init_ms: float,
    dataset_manifest_hash: str,
    source_commit: str,
    resolved_config_hash: str,
    canonical: bool,
) -> dict[str, Any]:
    cap_hit = result.stop_reason == "max_new_tokens"
    quality = _quality(dataset, result.generated_text, fixture["reference_answer"], cap_hit)
    verification_calls = result.verification_calls
    tokens_advanced = sum(result.acceptance_lengths)
    accepted_draft_tokens = tokens_advanced - verification_calls if verification_calls else 0
    compression_data = asdict(compression) if compression else {}
    token_data = token_audit or {}
    row = {
        "run_id": run_id,
        "task_id": "Rec-T04B",
        "dataset": dataset,
        "dataset_manifest_hash": dataset_manifest_hash,
        "fixture_id": fixture["fixture_id"],
        "fixture_content_hash": fixture["content_hash"],
        "condition": condition,
        "source_commit": source_commit,
        "resolved_config_hash": resolved_config_hash,
        "canonical": canonical,
        "prompt_policy_id": condition["prompt_policy_id"],
        "structured_prompt_parts_hash": hash_json(fixture["prompt_parts"]),
        "precompression_prompt_hash": hash_text(pre_prompt),
        "final_prompt_hash": hash_text(prompt),
        "input_tokens_precompression": token_data.get("precompression_target_prompt_tokens", result.prompt_token_count),
        "input_tokens_final": token_data.get("final_target_prompt_tokens", result.prompt_token_count),
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
        "compression": compression_data,
        "token_scope": token_data,
        "prompt_fairness": {
            key: prompt_audit[key]
            for key in [
                "question_occurrence",
                "instruction_occurrence",
                "meeting_marker_preserved",
                "question_marker_preserved",
                "only_context_changed",
            ]
        },
    }
    try:
        import torch

        if torch.cuda.is_available():
            row["peak_allocated_bytes"] = int(torch.cuda.max_memory_allocated())
            row["peak_reserved_bytes"] = int(torch.cuda.max_memory_reserved())
    except Exception:
        pass
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

    fixtures = read_jsonl(_fixture_path(dataset))[:30]
    resolved = resolve_config(
        dataset=dataset, subset="n30", condition_id=condition_id,
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
    drafter = load_drafter_model(DRAFTER_PATH) if condition_id in {"dflash-r1", "cc-dflash-r2"} else None
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    model_init_ms = (time.perf_counter() - start) * 1000
    compressor_init_ms = 0.0
    compressor = None
    if condition_id == "cc-dflash-r2" and dataset != "gsm8k":
        c_init = time.perf_counter()
        compressor = LLMLinguaCompressor(
            model_path=Path(resolved.data["models"]["compression"]["path"]),
            device_map=resolved.data["models"]["compression"]["device"],
        )
        compressor_init_ms = (time.perf_counter() - c_init) * 1000

    rows = []
    for fixture in fixtures:
        parts = _parts(fixture)
        pre_prompt = render_prompt(parts)
        compression = None
        token_audit = None
        compression_time = 0.0
        if condition_id == "cc-dflash-r2":
            c_start = time.perf_counter()
            if dataset == "gsm8k":
                compression = PassthroughCompressor().compress(
                    context=parts.context,
                    question=parts.question,
                    config=CompressionConfig(compression_enabled=False),
                )
            else:
                compression = compressor.compress(
                    context=parts.context,
                    question=parts.question,
                    config=CompressionConfig(
                        keep_rate=resolved.data["compression"]["keep_rate"],
                        min_context_tokens=resolved.data["compression"]["min_context_tokens"],
                        chunk_max_words=resolved.data["compression"]["chunk_max_words"],
                        device_map=resolved.data["models"]["compression"]["device"],
                    ),
                )
            compression_time = (time.perf_counter() - c_start) * 1000
            final_parts = PromptParts(
                context=compression.compressed_context,
                question=parts.question,
                instruction=parts.instruction,
                system=parts.system,
            )
            prompt = render_prompt(final_parts)
            prompt_audit = prompt_invariants(parts, compression.compressed_context)
            token_audit = token_scope_audit(parts, compression)
        else:
            prompt = pre_prompt
            prompt_audit = prompt_invariants(parts, parts.context)
        if condition_id == "baseline-ar":
            result = generate_baseline(target, tokenizer, prompt, config)
        else:
            result = generate_dflash_r1(target, drafter, tokenizer, prompt, config)
        if compression is not None:
            result.compressor_init_ms = compressor_init_ms
            result.compression_total_ms = compression_time
        row = _row(
            run_id=run_id,
            dataset=dataset,
            fixture=fixture,
            condition=condition,
            prompt=prompt,
            pre_prompt=pre_prompt,
            prompt_audit=prompt_audit,
            compression=compression,
            token_audit=token_audit,
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
    del target, drafter, compressor
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return {"dataset": dataset, "condition": condition_id, "rows": len(rows), "output": str(output)}


def _read_all(run_files: dict[tuple[str, str], Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in run_files.values():
        rows.extend(read_jsonl(path))
    return rows


def write_summaries(output_dir: Path, run_files: dict[tuple[str, str], Path], process_records: list[dict[str, Any]], max_new_tokens: int) -> dict[str, Any]:
    rows = _read_all(run_files)
    summary_rows = []
    compression_rows = []
    acceptance_rows = []
    runtime_rows = []
    for dataset in ["gsm8k", "qmsum"]:
        for condition in ["baseline-ar", "dflash-r1", "cc-dflash-r2"]:
            cr = [row for row in rows if row["dataset"] == dataset and row["condition"]["condition_id"] == condition]
            tau = aggregate_tau(cr)
            summary_rows.append(
                {
                    "dataset": dataset,
                    "condition": condition,
                    "rows": len(cr),
                    "success_count": sum(1 for row in cr if row["success"]),
                    "cap_hits": sum(1 for row in cr if row["cap_hit"]),
                    "mean_request_e2e_ms": sum(row["request_e2e_ms"] for row in cr) / len(cr),
                    "mean_target_prefill_ms": sum(row["target_prefill_ms"] for row in cr) / len(cr),
                    "mean_decode_total_ms": sum(row["decode_total_ms"] for row in cr) / len(cr),
                    "mean_compression_total_ms": sum(row["compression_total_ms"] for row in cr) / len(cr),
                    **tau,
                }
            )
            runtime_rows.extend(
                {
                    "dataset": dataset,
                    "condition": condition,
                    "fixture_id": row["fixture_id"],
                    "target_prefill_ms": row["target_prefill_ms"],
                    "decode_total_ms": row["decode_total_ms"],
                    "request_e2e_ms": row["request_e2e_ms"],
                    "compression_total_ms": row["compression_total_ms"],
                    "peak_allocated_bytes": row["peak_allocated_bytes"],
                    "peak_reserved_bytes": row["peak_reserved_bytes"],
                }
                for row in cr
            )
            if condition in {"dflash-r1", "cc-dflash-r2"}:
                acceptance_rows.extend(
                    {
                        "dataset": dataset,
                        "condition": condition,
                        "fixture_id": row["fixture_id"],
                        "verification_calls": row["verification_calls"],
                        "tau": row["tau_tokens_advanced_per_verification"],
                        "draft_acceptance_rate": row["draft_acceptance_rate"],
                        "rollback_tokens": row["rollback_tokens"],
                    }
                    for row in cr
                )
            if condition == "cc-dflash-r2":
                compression_rows.extend(
                    {
                        "dataset": dataset,
                        "fixture_id": row["fixture_id"],
                        "segment_original_tokens": row["compression"].get("segment_original_tokens"),
                        "segment_compressed_tokens": row["compression"].get("segment_compressed_tokens"),
                        "segment_reduction_pct": row["compression"].get("reduction_pct"),
                        "full_prompt_reduction_pct": row["token_scope"].get("full_prompt_reduction_pct"),
                        "chunk_count": row["compression"].get("chunk_count"),
                        "bypassed": row["compression"].get("bypassed"),
                        "compression_total_ms": row["compression_total_ms"],
                    }
                    for row in cr
                )

    _write_csv(output_dir / "summary.csv", summary_rows)
    _write_csv(output_dir / "runtime_decomposition.csv", runtime_rows)
    _write_csv(output_dir / "compression_metrics.csv", compression_rows)
    _write_csv(output_dir / "dflash_acceptance_comparison.csv", acceptance_rows)
    quality = _quality_summary(rows)
    write_json(output_dir / "quality_summary.json", quality)
    failure_samples = _failure_samples(rows)
    from ccdf.datasets.io import write_jsonl

    write_jsonl(output_dir / "failure_samples.jsonl", failure_samples)
    claim = _claim_boundary(summary_rows, compression_rows)
    write_json(output_dir / "claim_boundary.json", claim)
    decision = _gate(summary_rows, rows, process_records, max_new_tokens)
    write_json(output_dir / "gate_decision.json", decision)
    return decision


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _quality_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for dataset in ["gsm8k", "qmsum"]:
        result[dataset] = {}
        for condition in ["baseline-ar", "dflash-r1", "cc-dflash-r2"]:
            cr = [row for row in rows if row["dataset"] == dataset and row["condition"]["condition_id"] == condition]
            result[dataset][condition] = {
                "cap_hits": sum(1 for row in cr if row["cap_hit"]),
                "semantic_correctness": "NOT_CLAIMED" if dataset == "qmsum" else "numeric_proxy_only",
                "mean_reference_recall": sum(row["quality"].get("reference_recall", 0.0) for row in cr)
                / len(cr),
                "labels": _labels(cr),
            }
    return result


def _labels(rows: list[dict[str, Any]]) -> dict[str, int]:
    labels: dict[str, int] = {}
    for row in rows:
        label = row["quality"].get("label", "proxy")
        labels[label] = labels.get(label, 0) + 1
    return labels


def _failure_samples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    samples = []
    by_fixture: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_fixture.setdefault((row["dataset"], row["fixture_id"]), {})[
            row["condition"]["condition_id"]
        ] = row
    for (dataset, fixture_id), grouped in by_fixture.items():
        cc = grouped.get("cc-dflash-r2")
        df = grouped.get("dflash-r1")
        if not cc or not df:
            continue
        cc_score = cc["quality"].get("reference_recall", 0.0)
        df_score = df["quality"].get("reference_recall", 0.0)
        if cc_score > df_score:
            bucket = "cc_better"
        elif cc_score < df_score:
            bucket = "cc_worse"
        else:
            bucket = "unchanged"
        if cc["cap_hit"] or df["cap_hit"] or bucket != "unchanged":
            samples.append(
                {
                    "dataset": dataset,
                    "fixture_id": fixture_id,
                    "bucket": bucket,
                    "cc_cap_hit": cc["cap_hit"],
                    "dflash_cap_hit": df["cap_hit"],
                    "cc_recall": cc_score,
                    "dflash_recall": df_score,
                    "cc_output_tokens": cc["output_tokens"],
                    "dflash_output_tokens": df["output_tokens"],
                }
            )
    return samples


def _claim_boundary(summary_rows: list[dict[str, Any]], compression_rows: list[dict[str, Any]]) -> dict[str, Any]:
    gsm_bypass = sum(1 for row in compression_rows if row["dataset"] == "gsm8k" and row["bypassed"])
    qmsum_reduction = [
        row["full_prompt_reduction_pct"]
        for row in compression_rows
        if row["dataset"] == "qmsum" and row["full_prompt_reduction_pct"] is not None
    ]
    return {
        "gsm8k": {
            "decision": "Short-context compression is not worthwhile; bypass is preferred.",
            "bypass_count": gsm_bypass,
        },
        "qmsum": {
            "semantic_correctness": "NOT_CLAIMED",
            "mean_full_prompt_reduction_pct": sum(qmsum_reduction) / len(qmsum_reduction)
            if qmsum_reduction
            else 0.0,
            "benefit_rule": "compression_total_ms < prefill_saved_ms + decode_saved_ms required for runtime benefit",
        },
    }


def _gate(summary_rows: list[dict[str, Any]], rows: list[dict[str, Any]], process_records: list[dict[str, Any]], max_new_tokens: int | None) -> dict[str, Any]:
    rows_total = sum(row["rows"] for row in summary_rows)
    process_ok = all(record["returncode"] == 0 for record in process_records)
    prompt_ok = all(
        row["prompt_fairness"]["question_occurrence"] == 1
        and row["prompt_fairness"]["instruction_occurrence"] == 1
        and row["prompt_fairness"]["meeting_marker_preserved"]
        and row["prompt_fairness"]["question_marker_preserved"]
        for row in rows
    )
    token_scope_ok = all(
        row["condition"]["condition_id"] != "cc-dflash-r2"
        or row["token_scope"].get("tokenizer_scopes_separate", False)
        for row in rows
    )
    dflash_ok = all(
        row["verification_calls"] == len(row["acceptance_lengths"])
        for row in rows
        if row["condition"]["condition_id"] in {"dflash-r1", "cc-dflash-r2"}
    )
    if rows_total != 180 or not process_ok:
        gate = "INSUFFICIENT_EVIDENCE"
    elif not prompt_ok or not token_scope_ok:
        gate = "FAIL_COMPRESSION_CORRECTNESS"
    elif not dflash_ok:
        gate = "FAIL_METRIC_CONTRACT"
    else:
        gate = "PASS_WITH_SHORT_CONTEXT_BYPASS"
    return {
        "gate_decision": gate,
        "rows_total": rows_total,
        "max_new_tokens": max_new_tokens if max_new_tokens is not None else {"gsm8k": 256, "qmsum": 384},
        "process_isolation": process_records,
        "prompt_fairness_pass": prompt_ok,
        "token_scope_pass": token_scope_ok,
        "dflash_invariants_pass": dflash_ok,
        "qmsum_semantic_correctness": "NOT_CLAIMED",
    }


def run_matrix(output_dir: Path, *, max_new_tokens: int | None = None) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "runs").mkdir(exist_ok=True)
    (output_dir / "logs").mkdir(exist_ok=True)
    configs = {
        f"{dataset}:{condition}": resolve_config(dataset=dataset, subset="n30", condition_id=condition).data
        for dataset in ["gsm8k", "qmsum"] for condition in ["baseline-ar", "dflash-r1", "cc-dflash-r2"]
    }
    write_json(output_dir / "resolved_config.json", configs)
    (output_dir / "resolved_config.sha256").write_text(hash_json(configs) + "\n", encoding="utf-8")
    run_id = f"rec-t04b-{int(time.time())}"
    run_files = {
        (dataset, condition): output_dir / "runs" / f"{dataset}_{condition.replace('-', '_')}.jsonl"
        for dataset in ["gsm8k", "qmsum"]
        for condition in ["baseline-ar", "dflash-r1", "cc-dflash-r2"]
    }
    process_records = []
    for (dataset, condition), path in run_files.items():
        log = output_dir / "logs" / f"{dataset}_{condition}.log"
        err = output_dir / "logs" / f"{dataset}_{condition}.err"
        cmd = [
            sys.executable,
            "-m",
            "ccdf.benchmark.rec_t04b",
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
    return write_summaries(output_dir, run_files, process_records, max_new_tokens)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    matrix = sub.add_parser("matrix")
    matrix.add_argument("--output-dir", default="results/Rec-T04B")
    matrix.add_argument("--max-new-tokens", type=int)
    condition = sub.add_parser("condition")
    condition.add_argument("--dataset", required=True, choices=["gsm8k", "qmsum"])
    condition.add_argument("--condition", required=True, choices=["baseline-ar", "dflash-r1", "cc-dflash-r2"])
    condition.add_argument("--output", required=True)
    condition.add_argument("--max-new-tokens", type=int)
    condition.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.command == "matrix":
        result = run_matrix(Path(args.output_dir), max_new_tokens=args.max_new_tokens)
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
