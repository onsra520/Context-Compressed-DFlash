"""User-facing validation workflow backed by the shared RuntimeEngine.

Canonical process isolation/provenance v2 remains deferred to Rec-T06B. This
module nevertheless emits truthful Rec-T06A3 structural and output-health data.
"""

from __future__ import annotations

import csv
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from ccdf.artifacts.writer import write_json, write_jsonl_atomic
from ccdf.config import resolve_config
from ccdf.datasets.hashing import canonical_json, hash_file, hash_json, hash_text
from ccdf.datasets.io import read_jsonl
from ccdf.evaluation import gsm8k, qmsum
from ccdf.metrics.dflash import validate_dflash_invariants
from ccdf.prompts.schemas import PromptParts
from ccdf.runtime import RuntimeEngine, RuntimeRequest

TRUSTED_CONDITIONS = (
    "baseline-ar",
    "dflash-r1",
    "llmlingua-ar-r2",
    "cc-dflash-r2",
)
LEGACY_REC_T06B1_CONDITIONS = ("baseline-ar", "dflash-r1", "cc-dflash-r2")


def _trusted_conditions(task_id: str) -> tuple[str, ...]:
    return TRUSTED_CONDITIONS if task_id == "Rec-T06D" else LEGACY_REC_T06B1_CONDITIONS


def _write_failure_samples(path: Path, failures: list[dict[str, Any]]) -> None:
    """Write evaluator diagnostic records without applying the run-row schema."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for failure in failures:
            handle.write(canonical_json(failure) + "\n")
    os.replace(tmp, path)


def _git_state(root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
        )
        return proc.stdout.strip() if proc.returncode == 0 else "unavailable"

    tracked_diff = run("diff", "--binary", "--", "src", "configs", "tests", "scripts", "docs", "pyproject.toml")
    untracked = run("ls-files", "--others", "--exclude-standard")
    relevant_untracked = [line for line in untracked.splitlines() if line.startswith(("src/", "configs/", "tests/", "scripts/", "docs/"))]
    return {
        "source_commit": run("rev-parse", "HEAD"),
        "dirty": bool(tracked_diff or relevant_untracked),
        "tracked_diff_sha256": hash_text(tracked_diff),
        "relevant_untracked_source_config_inventory_sha256": hash_json(relevant_untracked),
    }


def _row(
    *,
    task_id: str,
    run_id: str,
    resolved,
    fixture: dict[str, Any],
    result: dict[str, Any],
    git_state: dict[str, Any],
    canonical: bool | None = None,
    canonical_reason: str | None = None,
) -> dict[str, Any]:
    dflash = result["dflash"]
    timing = result["timing"]
    token_scope = result["compression"]["token_scope"]
    row = {
        "run_id": run_id,
        "task_id": task_id,
        "dataset": resolved.data["dataset"],
        "subset": resolved.data["subset"],
        "dataset_manifest_path": resolved.data["dataset_manifest"],
        "dataset_manifest_hash": resolved.data["dataset_manifest_hash"],
        "fixture_file_hash": resolved.data["fixture_file_hash"],
        "fixture_id": fixture["fixture_id"],
        "fixture_content_hash": fixture["content_hash"],
        "condition": resolved.data["condition"],
        "source_commit": git_state["source_commit"],
        "source_dirty": git_state["dirty"],
        "source_tracked_diff_sha256": git_state["tracked_diff_sha256"],
        "source_untracked_inventory_sha256": git_state["relevant_untracked_source_config_inventory_sha256"],
        "resolved_config_hash": resolved.sha256,
        "task_id": task_id,
        "canonical": bool(canonical),
        "canonical_reason": canonical_reason or "parent canonical decision",
        "prompt_policy_id": resolved.data["prompt_policy"]["id"],
        "structured_prompt_parts_hash": hash_json(fixture["prompt_parts"]),
        "precompression_prompt_hash": hash_text(result["precompression_prompt"]),
        "final_prompt_hash": hash_text(result["final_prompt"]),
        "model_input_ids_hash": result["prompt"]["input_ids_hash"],
        "input_tokens_precompression": token_scope["precompression_target_prompt_tokens"],
        "input_tokens_final": token_scope["final_target_prompt_tokens"],
        "generated_text": result["generated_text"],
        "raw_generated_text": result["raw_generated_text"],
        "validated_answer": result["validated_answer"],
        "reference_answer": fixture["reference_answer"],
        "generated_text_hash": hash_text(result["generated_text"]),
        "output_token_ids_hash": hash_json(result["output_token_ids"]),
        "generated_token_ids_hash": hash_json(result["generated_token_ids"]),
        "output_tokens": result["output_tokens"],
        "stop_reason": result["stop_reason"],
        "eos_hit": result["eos_hit"],
        "output_contract_hit": result["output_contract_hit"],
        "cap_hit": result["cap_hit"],
        "repetition_detected": result["repetition_detected"],
        "instruction_echo_detected": result["instruction_echo_detected"],
        "output_health": result["output_health"],
        "success": result["success"],
        "error": result["error"],
        **timing,
        "peak_allocated_bytes": result["vram"]["peak_allocated_bytes"],
        "peak_reserved_bytes": result["vram"]["peak_reserved_bytes"],
        "resource": result.get("resource", {}),
        "measurement_scope": result["vram"]["measurement_scope"],
        "measurement_mode": result["measurement_mode"],
        **dflash,
        "quality": result["quality"],
        "compression": result["compression"],
        "claim_boundary": result["claim_boundary"],
    }
    if resolved.data["condition_id"] != "baseline-ar":
        validate_dflash_invariants(row)
    return row


def run_benchmark(
    *,
    dataset: str,
    subset: str,
    conditions: list[str],
    output_dir: Path,
    limit: int | None = None,
    execution_mode: str = "benchmark",
    task_id: str = "Rec-T06B1",
) -> dict[str, Any]:
    expected_conditions = _trusted_conditions(task_id)
    if conditions != list(expected_conditions):
        raise ValueError("canonical benchmark requires the exact ordered unique trusted condition matrix")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "runs").mkdir(exist_ok=True)

    first = resolve_config(
        dataset=dataset,
        subset=subset,
        condition_id=conditions[0],
        execution_mode=execution_mode,
    )
    fixtures = read_jsonl(Path(first.data["fixture_path"]))
    if limit is not None:
        fixtures = fixtures[:limit]
    git_state = _git_state(Path(first.data["path_context"]["worktree_root"]))
    canonical_parent = bool(execution_mode == "benchmark" and not git_state["dirty"] and limit is None and conditions == list(expected_conditions))
    canonical_reason = "clean complete benchmark run" if canonical_parent else "noncanonical validation: limited, dirty, incomplete, or non-benchmark execution"
    config_bundle: dict[str, Any] = {}
    run_id = f"{task_id.lower()}-{int(time.time())}"

    worker_manifests: dict[str, dict[str, Any]] = {}
    for condition_id in conditions:
        resolved = resolve_config(dataset=dataset, subset=subset, condition_id=condition_id, execution_mode=execution_mode)
        config_bundle[condition_id] = {**resolved.data, "benchmark_identity": {"task_id": task_id, "execution_mode": execution_mode, "canonical": canonical_parent, "canonical_reason": canonical_reason, "worker_resolved_config_sha256": resolved.sha256}}
        run_path = output_dir / "runs" / f"{condition_id.replace('-', '_')}.jsonl"
        condition_config_hash = resolved.sha256
        fixture_ids_hash = hash_json([row["fixture_id"] for row in fixtures])
        command = [sys.executable, "-m", "ccdf.benchmark.worker", "--dataset", dataset, "--subset", subset, "--condition", condition_id, "--output", str(run_path), "--task-id", task_id, "--execution-mode", execution_mode, "--canonical", str(canonical_parent).lower(), "--canonical-reason", canonical_reason, "--expected-config-hash", condition_config_hash, "--expected-fixture-ids-hash", fixture_ids_hash, "--expected-source-commit", git_state["source_commit"], "--expected-source-dirty", str(git_state["dirty"]).lower(), "--expected-tracked-diff-hash", git_state["tracked_diff_sha256"], "--expected-untracked-inventory-hash", git_state["relevant_untracked_source_config_inventory_sha256"]]
        if limit is not None:
            command.extend(["--limit", str(limit)])
        proc = subprocess.run(command, cwd=str(first.data["path_context"]["worktree_root"]), text=True, capture_output=True)
        worker_path = run_path.with_suffix(".worker.json")
        if proc.returncode:
            raise RuntimeError(f"worker failed for {condition_id}: {proc.stderr.strip()}")
        worker_manifests[condition_id] = json.loads(worker_path.read_text(encoding="utf-8"))
        worker = worker_manifests[condition_id]
        if worker.get("task_id") != task_id or worker.get("execution_mode") != execution_mode or worker.get("resolved_config_sha256") != condition_config_hash or worker.get("canonical") != canonical_parent or worker.get("canonical_reason") != canonical_reason or worker.get("git_state") != git_state:
            raise ValueError(f"worker identity mismatch for {condition_id}")

    write_json(output_dir / "resolved_config.json", config_bundle)
    (output_dir / "resolved_config.sha256").write_text(
        hash_file(output_dir / "resolved_config.json") + "\n", encoding="utf-8"
    )
    run_hashes = {
        path.name: hash_file(path) for path in sorted((output_dir / "runs").glob("*.jsonl"))
    }
    manifest = {
        "task_id": task_id,
        "execution_mode": execution_mode,
        "dataset": dataset,
        "subset": subset,
        "row_limit": limit,
        "fixture_ids": [row["fixture_id"] for row in fixtures],
        "dataset_manifest_path": first.data["dataset_manifest"],
        "dataset_manifest_hash": first.data["dataset_manifest_hash"],
        "fixture_file_hash": first.data["fixture_file_hash"],
        "conditions": conditions,
        "runtime": "ccdf.runtime.engine.RuntimeEngine",
        "canonical": canonical_parent and all(worker.get("canonical") for worker in worker_manifests.values()),
        "canonical_reason": canonical_reason,
        "git_state": git_state,
        "run_file_hashes": run_hashes,
        "resolved_config_file_sha256": hash_file(output_dir / "resolved_config.json"),
        "ordered_fixture_ids_sha256": hash_json([row["fixture_id"] for row in fixtures]),
        "canonical_config_file_sha256": hash_file(Path(first.data["config_path"])),
        "resolved_condition_config_sha256": {key: value["benchmark_identity"]["worker_resolved_config_sha256"] for key, value in config_bundle.items()},
        "prompt_policy_sha256": hash_json(first.data["prompt_policy"]),
        "evaluator_implementation_config_sha256": hash_file(Path(first.data["path_context"]["worktree_root"]) / "src" / "ccdf" / "evaluation" / f"{dataset}.py"),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "worker_manifests": worker_manifests,
        "worker_manifest_hashes": {condition: hash_file(output_dir / "runs" / f"{condition.replace('-', '_')}.worker.json") for condition in conditions},
    }
    write_json(output_dir / "benchmark_manifest.json", manifest)
    return manifest


def evaluate_run_dir(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "benchmark_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest.get("task_id"), str) or not manifest["task_id"]:
        raise ValueError("missing task identity")
    if manifest.get("execution_mode") not in {"benchmark", "smoke", "profiling"}:
        raise ValueError("missing execution mode")
    if manifest.get("conditions") != list(_trusted_conditions(manifest["task_id"])):
        raise ValueError("invalid trusted condition matrix")
    resolved_path = run_dir / "resolved_config.json"
    resolved_hash_path = run_dir / "resolved_config.sha256"
    if not resolved_path.is_file() or hash_file(resolved_path) != manifest.get("resolved_config_file_sha256"):
        raise ValueError("resolved config hash mismatch")
    if resolved_hash_path.read_text(encoding="utf-8").strip() != hash_file(resolved_path):
        raise ValueError("resolved_config.sha256 mismatch")
    bundle = json.loads(resolved_path.read_text(encoding="utf-8"))
    if manifest.get("resolved_condition_config_sha256") != {condition: bundle[condition].get("benchmark_identity", {}).get("worker_resolved_config_sha256") for condition in manifest["conditions"]}:
        raise ValueError("condition config hash mismatch")
    fixture_path = Path(bundle[manifest["conditions"][0]]["fixture_path"])
    if not fixture_path.is_file() or hash_file(fixture_path) != manifest.get("fixture_file_hash"):
        raise ValueError("fixture path/hash mismatch")
    manifest_path_input = Path(manifest["dataset_manifest_path"])
    if not manifest_path_input.is_file() or hash_file(manifest_path_input) != manifest.get("dataset_manifest_hash"):
        raise ValueError("dataset manifest path/hash mismatch")
    # Benchmark provenance records the evaluator used when rows were produced.
    # Evaluation itself is intentionally refreshable without a model rerun, so
    # its current implementation is recorded in evaluation_manifest.json below
    # rather than rejecting an otherwise intact raw artifact after an evaluator
    # hotfix.
    for condition in manifest["conditions"]:
        worker_path = run_dir / "runs" / f"{condition.replace('-', '_')}.worker.json"
        if not worker_path.is_file() or hash_file(worker_path) != manifest.get("worker_manifest_hashes", {}).get(condition):
            raise ValueError("worker manifest hash mismatch")
        worker = json.loads(worker_path.read_text(encoding="utf-8"))
        if manifest.get("worker_manifests", {}).get(condition) != worker:
            raise ValueError("worker manifest snapshot mismatch")
        if worker.get("git_state") != manifest.get("git_state"):
            raise ValueError("worker source-state mismatch")
        if worker.get("task_id") != manifest["task_id"] or worker.get("execution_mode") != manifest["execution_mode"] or worker.get("canonical") != manifest.get("canonical") or worker.get("canonical_reason") != manifest.get("canonical_reason"):
            raise ValueError("worker task or mode mismatch")
        if worker.get("resolved_config_sha256") != manifest.get("resolved_condition_config_sha256", {}).get(condition):
            raise ValueError("worker condition config mismatch")
    rows: list[dict[str, Any]] = []
    actual_hashes: dict[str, str] = {}
    fixture_order: list[str] | None = None
    for path in sorted((run_dir / "runs").glob("*.jsonl")):
        actual_hashes[path.name] = hash_file(path)
        file_rows = read_jsonl(path)
        expected_condition = path.stem.replace("_", "-")
        if expected_condition not in manifest["conditions"]:
            raise ValueError("undeclared condition file")
        if [row["fixture_id"] for row in file_rows] != manifest["fixture_ids"]:
            raise ValueError("fixture IDs are missing, duplicate, or reordered")
        for row in file_rows:
            if row.get("condition", {}).get("condition_id") != expected_condition:
                raise ValueError("condition file/row binding mismatch")
            if row.get("source_tracked_diff_sha256") != manifest["git_state"]["tracked_diff_sha256"] or row.get("source_untracked_inventory_sha256") != manifest["git_state"]["relevant_untracked_source_config_inventory_sha256"]:
                raise ValueError("row source-state mismatch")
            if row.get("task_id") != manifest["task_id"] or row.get("measurement_mode") != manifest["execution_mode"] or row.get("canonical") != manifest.get("canonical") or row.get("canonical_reason") != manifest.get("canonical_reason") or row.get("source_commit") != manifest["git_state"]["source_commit"] or row.get("source_dirty") != manifest["git_state"]["dirty"]:
                raise ValueError("row task or measurement identity mismatch")
            if row.get("resolved_config_hash") != manifest.get("resolved_condition_config_sha256", {}).get(expected_condition):
                raise ValueError("row resolved config hash mismatch")
        rows.extend(file_rows)
    if manifest.get("ordered_fixture_ids_sha256") != hash_json(manifest["fixture_ids"]):
        raise ValueError("fixture order hash mismatch")
    if actual_hashes != manifest.get("run_file_hashes"):
        raise ValueError("run-file hashes do not match benchmark manifest")
    expected_names = {f"{condition.replace('-', '_')}.jsonl" for condition in manifest["conditions"]}
    if set(actual_hashes) != expected_names:
        raise ValueError("missing, extra, or stale expected-condition run artifact")
    actual_workers = {path.name for path in (run_dir / "runs").glob("*.worker.json")}
    expected_workers = {f"{condition.replace('-', '_')}.worker.json" for condition in manifest["conditions"]}
    if actual_workers != expected_workers:
        raise ValueError("missing or extra worker manifest artifact")

    summary: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for condition in manifest["conditions"]:
        selected = [row for row in rows if row["condition"]["condition_id"] == condition]
        if not selected:
            raise ValueError(f"missing rows for condition: {condition}")
        if any(row["condition"]["condition_id"] != condition for row in selected):
            raise ValueError("mixed condition rows in run artifact")
        recomputed = []
        for row in selected:
            if manifest["dataset"] == "gsm8k":
                quality = gsm8k.evaluate(row["raw_generated_text"], row["reference_answer"], cap_hit=row["cap_hit"], repetition_detected=row["repetition_detected"])
            else:
                health = row.get("output_health", {})
                quality = qmsum.evaluate(row["raw_generated_text"], row["reference_answer"], cap_hit=row["cap_hit"], repetition_detected=row["repetition_detected"], instruction_echo_detected=row["instruction_echo_detected"], answer_prefix_count=int(health.get("answer_prefix_count", 0)), repeated_ngram_ratio=float(health.get("repeated_ngram_ratio", 0.0)))
            recomputed.append(quality)
        strict = sum(item.get("label") == "strict_correct" for item in recomputed)
        target_calls = sum(int(row.get("total_target_forward_calls", 0)) for row in selected)
        output_tokens = sum(int(row["output_tokens"]) for row in selected)
        verification_calls = sum(int(row.get("target_block_verification_calls", 0)) for row in selected)
        emitted_block_tokens = sum(sum(int(value) for value in row.get("emitted_acceptance_lengths", [])) for row in selected)
        proposed_tokens = sum(int(row.get("draft_tokens_proposed", 0)) for row in selected)
        accepted_tokens = sum(int(row.get("accepted_draft_tokens", 0)) for row in selected)
        summary.append(
            {
                "condition": condition,
                "rows": len(selected),
                "success": sum(bool(row["success"]) for row in selected),
                "cap_hits": sum(bool(row["cap_hit"]) for row in selected),
                "repetition": sum(bool(row["repetition_detected"]) for row in selected),
                "instruction_echo": sum(bool(row["instruction_echo_detected"]) for row in selected),
                "gsm8k_strict_correct": strict if manifest["dataset"] == "gsm8k" else None,
                "gsm8k_wrong_numeric": sum(item.get("label") == "wrong_numeric" for item in recomputed) if manifest["dataset"] == "gsm8k" else None,
                "gsm8k_no_final_answer": sum(item.get("label") == "no_final_answer" for item in recomputed) if manifest["dataset"] == "gsm8k" else None,
                "mean_generation_e2e_ms": sum(row["generation_request_e2e_ms"] for row in selected) / len(selected),
                "mean_warm_e2e_ms": sum(row["warm_request_e2e_ms"] for row in selected) / len(selected),
                "mean_cold_start_e2e_ms": sum(row["cold_start_e2e_ms"] for row in selected) / len(selected),
                "mean_compression_total_ms": sum(row["compression_total_ms"] for row in selected) / len(selected),
                "mean_target_prefill_ms": sum(row["target_prefill_ms"] for row in selected) / len(selected),
                "mean_decode_total_ms": sum(row["decode_total_ms"] for row in selected) / len(selected),
                "generation_tok_s": output_tokens / max(sum(row["generation_request_e2e_ms"] for row in selected) / 1000, 1e-9),
                "warm_request_tok_s": output_tokens / max(sum(row["warm_request_e2e_ms"] for row in selected) / 1000, 1e-9),
                "peak_cuda_allocated_bytes": max(row["peak_allocated_bytes"] for row in selected),
                "peak_cuda_reserved_bytes": max(row["peak_reserved_bytes"] for row in selected),
                "cpu_compressor_memory_delta_bytes": max(int(row.get("resource", {}).get("cpu_compressor_memory_delta_bytes", 0)) for row in selected),
                "global_target_forwards_per_output_token": target_calls / output_tokens if output_tokens else 0.0,
                "effective_tau": emitted_block_tokens / verification_calls if verification_calls else 0.0,
                "draft_acceptance_rate": accepted_tokens / proposed_tokens if proposed_tokens else 0.0,
                "rollback_tokens": sum(int(row.get("rollback_tokens", 0)) for row in selected),
                "correction_tokens": sum(int(row.get("correction_tokens", 0)) for row in selected),
                "bonus_target_tokens": sum(int(row.get("bonus_target_tokens", 0)) for row in selected),
                "seed_aware_output_accounting_pass": all(int(row["output_tokens"]) == int(row.get("target_seed_tokens", 0)) + sum(int(value) for value in row.get("emitted_acceptance_lengths", [])) for row in selected if row["condition"]["condition_id"] != "baseline-ar"),
                "model_composition": selected[0].get("resource", {}).get("model_composition", "unsupported"),
                "semantic_correctness": "NOT_CLAIMED" if manifest["dataset"] == "qmsum" else "numeric",
                "reference_recall": sum(float(item.get("reference_recall", 0.0)) for item in recomputed) / len(recomputed) if manifest["dataset"] == "qmsum" else None,
                "reference_precision": sum(float(item.get("reference_precision", 0.0)) for item in recomputed) / len(recomputed) if manifest["dataset"] == "qmsum" else None,
                "invalid_outputs": sum(item.get("label") == "invalid" for item in recomputed),
                "empty_outputs": sum(not str(row["raw_generated_text"]).strip() for row in selected),
            }
        )
        for row, recomputed_quality in zip(selected, recomputed):
            label = recomputed_quality.get("label")
            invalid = bool(recomputed_quality.get("invalid"))
            reason = label if label in {"wrong_numeric", "no_final_answer", "invalid", "cap_limited", "repetition_invalid"} else "evaluator_invalid" if invalid else None
            if reason is None and row["cap_hit"]:
                reason = "cap_hit"
            if reason is None and row["repetition_detected"]:
                reason = "repetition"
            if reason is None and row["instruction_echo_detected"]:
                reason = "instruction_echo"
            if reason is None and not row["success"]:
                reason = "runtime_failure"
            if reason is not None:
                failures.append({"condition": condition, "fixture_id": row["fixture_id"], "reference_answer": row["reference_answer"], "generated_text": row["generated_text"], "generated_text_hash": row["generated_text_hash"], "quality_label": label, "failure_reason": reason})

    quality = {
        "dataset": manifest["dataset"],
        "rows": len(rows),
        "semantic_correctness": "NOT_CLAIMED" if manifest["dataset"] == "qmsum" else "numeric",
        "conditions": summary,
    }
    by_condition = {item["condition"]: item for item in summary}
    baseline_warm = by_condition.get("baseline-ar", {}).get("mean_warm_e2e_ms")
    dflash_warm = by_condition.get("dflash-r1", {}).get("mean_warm_e2e_ms")
    llmlingua_ar_warm = by_condition.get("llmlingua-ar-r2", {}).get("mean_warm_e2e_ms")
    for item in summary:
        item["warm_e2e_delta_vs_baseline_ms"] = item["mean_warm_e2e_ms"] - baseline_warm if baseline_warm is not None else None
        item["warm_e2e_delta_vs_dflash_ms"] = item["mean_warm_e2e_ms"] - dflash_warm if dflash_warm is not None else None
        item["warm_e2e_delta_vs_llmlingua_ar_ms"] = item["mean_warm_e2e_ms"] - llmlingua_ar_warm if llmlingua_ar_warm is not None else None
        selected = [row for row in rows if row["condition"]["condition_id"] == item["condition"]]
        item["mean_input_tokens_precompression"] = sum(row["input_tokens_precompression"] for row in selected) / len(selected)
        item["mean_input_tokens_final"] = sum(row["input_tokens_final"] for row in selected) / len(selected)
        item["full_prompt_reduction_tokens"] = item["mean_input_tokens_precompression"] - item["mean_input_tokens_final"]
        item["full_prompt_reduction_pct"] = (item["full_prompt_reduction_tokens"] / item["mean_input_tokens_precompression"] * 100) if item["mean_input_tokens_precompression"] else 0.0
        item["compression_bypass_count"] = sum(bool(row.get("compression", {}).get("bypassed")) for row in selected)
        item["compression_bypass_reasons"] = sorted({str(row.get("compression", {}).get("bypass_reason")) for row in selected if row.get("compression", {}).get("bypass_reason")})
    if manifest.get("canonical") and (manifest.get("execution_mode") != "benchmark" or manifest.get("row_limit") is not None or manifest.get("git_state", {}).get("dirty") or any(not row.get("canonical") for row in rows)):
        raise ValueError("canonical artifact does not satisfy canonical requirements")
    write_json(run_dir / "quality_summary.json", quality)
    write_json(run_dir / "performance_summary.json", {"dataset": manifest["dataset"], "conditions": summary, "comparison_latency": "warm_request_e2e_ms includes compression"})
    write_json(run_dir / "resource_summary.json", {"dataset": manifest["dataset"], "conditions": [{"condition": item["condition"], "peak_cuda_allocated_bytes": item["peak_cuda_allocated_bytes"], "peak_cuda_reserved_bytes": item["peak_cuda_reserved_bytes"], "cpu_compressor_memory_delta_bytes": item["cpu_compressor_memory_delta_bytes"], "model_composition": item["model_composition"], "unsupported_resource_fields": sorted({field for row in rows if row["condition"]["condition_id"] == item["condition"] for field in row.get("resource", {}).get("unsupported_fields", [])}), "current_rss_before_compressor_bytes": max([row.get("resource", {}).get("process_rss_before_compressor_bytes") or 0 for row in rows if row["condition"]["condition_id"] == item["condition"]], default=0), "current_rss_after_compressor_bytes": max([row.get("resource", {}).get("process_rss_after_compressor_bytes") or 0 for row in rows if row["condition"]["condition_id"] == item["condition"]], default=0), "process_peak_rss_bytes": max([row.get("resource", {}).get("process_peak_rss_bytes") or 0 for row in rows if row["condition"]["condition_id"] == item["condition"]], default=0)} for item in summary]})
    write_json(run_dir / "dflash_summary.json", {"conditions": [{"condition": item["condition"], "target_forwards_per_emitted_token": item["global_target_forwards_per_output_token"], "effective_tau": item["effective_tau"], "draft_acceptance_rate": item["draft_acceptance_rate"], "rollback_tokens": item["rollback_tokens"], "correction_tokens": item["correction_tokens"], "bonus_target_tokens": item["bonus_target_tokens"]} for item in summary]})
    write_json(run_dir / "compression_summary.json", {"conditions": [{"condition": item["condition"], "mean_precompression_prompt_tokens": item["mean_input_tokens_precompression"], "mean_final_prompt_tokens": item["mean_input_tokens_final"], "full_prompt_reduction_tokens": item["full_prompt_reduction_tokens"], "full_prompt_reduction_pct": item["full_prompt_reduction_pct"], "mean_compression_total_ms": item["mean_compression_total_ms"], "mean_target_prefill_ms": item["mean_target_prefill_ms"], "prefill_saving_vs_dflash_ms": by_condition.get("dflash-r1", {}).get("mean_target_prefill_ms", 0) - item["mean_target_prefill_ms"], "warm_e2e_delta_vs_baseline_ms": item["warm_e2e_delta_vs_baseline_ms"], "warm_e2e_delta_vs_dflash_ms": item["warm_e2e_delta_vs_dflash_ms"], "warm_e2e_delta_vs_llmlingua_ar_ms": item["warm_e2e_delta_vs_llmlingua_ar_ms"], "compression_bypass_count": item["compression_bypass_count"], "compression_bypass_reasons": item["compression_bypass_reasons"]} for item in summary]})
    _write_failure_samples(run_dir / "failure_samples.jsonl", failures)
    with (run_dir / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary)
    evaluation_manifest = {
        "source_benchmark_manifest": str(manifest_path),
        "source_benchmark_manifest_hash": hash_file(manifest_path),
        "run_file_hashes": actual_hashes,
        "models_loaded": False,
        "runtime_engine_instantiated": False,
        "evaluator": "quality recomputed from raw output and stored reference answers",
        "source_binding": "parent-bound worker and row source state verified",
        "consumed_input_hashes": {"benchmark_manifest.json": hash_file(manifest_path), "resolved_config.json": hash_file(resolved_path), "resolved_config.sha256": hash_file(resolved_hash_path), "fixture_file": hash_file(fixture_path), "dataset_manifest": hash_file(manifest_path_input), **{f"condition_configs/{condition}": hash_json(bundle[condition]) for condition in manifest["conditions"]}, **{f"runs/{name}": digest for name, digest in actual_hashes.items()}, **{f"runs/{condition.replace('-', '_')}.worker.json": hash_file(run_dir / "runs" / f"{condition.replace('-', '_')}.worker.json") for condition in manifest["conditions"]}},
        "produced_summary_hashes": {},
    }
    root = Path(bundle[manifest["conditions"][0]]["path_context"]["worktree_root"])
    dependencies = {
        f"evaluation/{manifest['dataset']}.py": hash_file(root / "src" / "ccdf" / "evaluation" / f"{manifest['dataset']}.py"),
        "benchmark/workflow.py": hash_file(root / "src" / "ccdf" / "benchmark" / "workflow.py"),
        "inference/output_contract.py": hash_file(root / "src" / "ccdf" / "inference" / "output_contract.py"),
        "benchmark/schemas.py": hash_file(root / "src" / "ccdf" / "benchmark" / "schemas.py"),
        "evaluator_identity": hash_text(bundle[manifest["conditions"][0]]["evaluator_identity"]),
    }
    evaluation_manifest["evaluator_dependency_hashes"] = dependencies
    evaluation_manifest["evaluator_bundle_sha256"] = hash_json(dependencies)
    produced = ["summary.csv", "quality_summary.json", "performance_summary.json", "resource_summary.json", "dflash_summary.json", "compression_summary.json", "failure_samples.jsonl"]
    evaluation_manifest["consumed_input_hashes"].update({f"evaluator_dependencies/{name}": digest for name, digest in dependencies.items()})
    evaluation_manifest["produced_summary_hashes"] = {name: hash_file(run_dir / name) for name in produced}
    write_json(run_dir / "evaluation_manifest.json", evaluation_manifest)
    return {"rows": len(rows), "conditions": summary}
