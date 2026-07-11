"""User-facing validation workflow backed by the shared RuntimeEngine.

Canonical process isolation/provenance v2 remains deferred to Rec-T06B. This
module nevertheless emits truthful Rec-T06A3 structural and output-health data.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from ccdf.artifacts.writer import write_json, write_jsonl_atomic
from ccdf.config import resolve_config
from ccdf.datasets.hashing import hash_file, hash_json, hash_text
from ccdf.datasets.io import read_jsonl
from ccdf.metrics.dflash import validate_dflash_invariants
from ccdf.prompts.schemas import PromptParts
from ccdf.runtime import RuntimeEngine, RuntimeRequest


def _git_state(root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
        )
        return proc.stdout.strip() if proc.returncode == 0 else "unavailable"

    status = run("status", "--short")
    return {
        "source_commit": run("rev-parse", "HEAD"),
        "dirty": bool(status and status != "unavailable"),
        "status_short": status,
    }


def _row(
    *,
    task_id: str,
    run_id: str,
    resolved,
    fixture: dict[str, Any],
    result: dict[str, Any],
    git_state: dict[str, Any],
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
        "resolved_config_hash": resolved.sha256,
        "canonical": False,
        "canonical_reason": "Rec-T06A3 validation; process-isolated provenance deferred to Rec-T06B",
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
    task_id: str = "Rec-T06A3",
) -> dict[str, Any]:
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
    config_bundle: dict[str, Any] = {}
    run_id = f"{task_id.lower()}-{int(time.time())}"

    for condition_id in conditions:
        resolved = resolve_config(
            dataset=dataset,
            subset=subset,
            condition_id=condition_id,
            execution_mode=execution_mode,
        )
        config_bundle[condition_id] = resolved.data
        engine = RuntimeEngine(resolved)
        rows: list[dict[str, Any]] = []
        try:
            for fixture in fixtures:
                result = engine.execute(
                    RuntimeRequest(
                        resolved=resolved,
                        prompt_parts=PromptParts(**fixture["prompt_parts"]),
                        reference_answer=fixture["reference_answer"],
                        measurement_mode=execution_mode,
                    )
                )
                rows.append(
                    _row(
                        task_id=task_id,
                        run_id=run_id,
                        resolved=resolved,
                        fixture=fixture,
                        result=result,
                        git_state=git_state,
                    )
                )
        finally:
            engine.close()
        write_jsonl_atomic(
            output_dir / "runs" / f"{condition_id.replace('-', '_')}.jsonl", rows
        )

    write_json(output_dir / "resolved_config.json", config_bundle)
    (output_dir / "resolved_config.sha256").write_text(
        hash_json(config_bundle) + "\n", encoding="utf-8"
    )
    run_hashes = {
        path.name: hash_file(path) for path in sorted((output_dir / "runs").glob("*.jsonl"))
    }
    manifest = {
        "task_id": task_id,
        "dataset": dataset,
        "subset": subset,
        "row_limit": limit,
        "fixture_ids": [row["fixture_id"] for row in fixtures],
        "dataset_manifest_path": first.data["dataset_manifest"],
        "dataset_manifest_hash": first.data["dataset_manifest_hash"],
        "fixture_file_hash": first.data["fixture_file_hash"],
        "conditions": conditions,
        "runtime": "ccdf.runtime.engine.RuntimeEngine",
        "canonical": False,
        "git_state": git_state,
        "run_file_hashes": run_hashes,
    }
    write_json(output_dir / "benchmark_manifest.json", manifest)
    return manifest


def evaluate_run_dir(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "benchmark_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    actual_hashes: dict[str, str] = {}
    for path in sorted((run_dir / "runs").glob("*.jsonl")):
        actual_hashes[path.name] = hash_file(path)
        rows.extend(read_jsonl(path))
    if actual_hashes != manifest.get("run_file_hashes"):
        raise ValueError("run-file hashes do not match benchmark manifest")

    summary: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for condition in manifest["conditions"]:
        selected = [row for row in rows if row["condition"]["condition_id"] == condition]
        if not selected:
            raise ValueError(f"missing rows for condition: {condition}")
        strict = sum(row["quality"].get("label") == "strict_correct" for row in selected)
        target_calls = sum(int(row.get("total_target_forward_calls", 0)) for row in selected)
        output_tokens = sum(int(row["output_tokens"]) for row in selected)
        summary.append(
            {
                "condition": condition,
                "rows": len(selected),
                "success": sum(bool(row["success"]) for row in selected),
                "cap_hits": sum(bool(row["cap_hit"]) for row in selected),
                "repetition": sum(bool(row["repetition_detected"]) for row in selected),
                "instruction_echo": sum(bool(row["instruction_echo_detected"]) for row in selected),
                "gsm8k_strict_correct": strict if manifest["dataset"] == "gsm8k" else None,
                "mean_generation_e2e_ms": sum(row["generation_request_e2e_ms"] for row in selected) / len(selected),
                "mean_warm_e2e_ms": sum(row["warm_request_e2e_ms"] for row in selected) / len(selected),
                "global_target_forwards_per_output_token": target_calls / output_tokens if output_tokens else 0.0,
                "semantic_correctness": "NOT_CLAIMED" if manifest["dataset"] == "qmsum" else "numeric",
            }
        )
        failures.extend(
            row
            for row in selected
            if row["cap_hit"]
            or row["repetition_detected"]
            or row["instruction_echo_detected"]
            or not row["success"]
        )

    quality = {
        "dataset": manifest["dataset"],
        "rows": len(rows),
        "semantic_correctness": "NOT_CLAIMED" if manifest["dataset"] == "qmsum" else "numeric",
        "conditions": summary,
    }
    write_json(run_dir / "quality_summary.json", quality)
    write_jsonl_atomic(run_dir / "failure_samples.jsonl", failures)
    evaluation_manifest = {
        "source_benchmark_manifest": str(manifest_path),
        "source_benchmark_manifest_hash": hash_file(manifest_path),
        "run_file_hashes": actual_hashes,
        "models_loaded": False,
        "evaluator": "stored runtime quality fields",
    }
    write_json(run_dir / "evaluation_manifest.json", evaluation_manifest)
    with (run_dir / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    return {"rows": len(rows), "conditions": summary}
