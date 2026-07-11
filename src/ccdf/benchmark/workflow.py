"""User-facing benchmark and evaluation workflow backed by RuntimeEngine."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

from ccdf.artifacts.writer import write_json, write_jsonl_atomic
from ccdf.config import resolve_config, write_resolved_config
from ccdf.datasets.hashing import hash_json, hash_text
from ccdf.datasets.io import read_jsonl
from ccdf.evaluation import gsm8k, qmsum
from ccdf.metrics.dflash import validate_dflash_invariants
from ccdf.prompts.schemas import PromptParts
from ccdf.runtime import RuntimeEngine, RuntimeRequest


def _quality(dataset: str, text: str, reference: str, cap_hit: bool) -> dict[str, Any]:
    return gsm8k.evaluate(text, reference, cap_hit=cap_hit) if dataset == "gsm8k" else qmsum.evaluate(text, reference, cap_hit=cap_hit)


def run_benchmark(*, dataset: str, subset: str, conditions: list[str], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "runs").mkdir(exist_ok=True)
    fixtures = read_jsonl(Path(f"data/eval/{dataset}/{dataset}_{subset}.jsonl"))
    manifests: dict[str, str] = {}
    config_bundle: dict[str, Any] = {}
    run_id = f"benchmark-{int(time.time())}"
    for condition_id in conditions:
        resolved = resolve_config(dataset=dataset, subset=subset, condition_id=condition_id)
        manifests[condition_id] = resolved.data["dataset_manifest_hash"]
        config_bundle[condition_id] = resolved.data
        engine = RuntimeEngine(resolved)
        rows = []
        try:
            for fixture in fixtures:
                parts = PromptParts(**fixture["prompt_parts"])
                result = engine.execute(RuntimeRequest(resolved=resolved, prompt_parts=parts, reference_answer=fixture["reference_answer"]))
                dflash = result["dflash"]
                accepted = dflash["accepted_draft_tokens"]
                proposed = dflash["draft_tokens_proposed"]
                row = {
                    "run_id": run_id, "task_id": "Rec-T05B", "dataset": dataset,
                    "dataset_manifest_hash": resolved.data["dataset_manifest_hash"], "fixture_id": fixture["fixture_id"], "fixture_content_hash": fixture["content_hash"],
                    "condition": resolved.data["condition"], "source_commit": _git_commit(), "resolved_config_hash": resolved.sha256, "canonical": resolved.canonical,
                    "prompt_policy_id": resolved.data["prompt_policy"]["id"], "structured_prompt_parts_hash": hash_json(fixture["prompt_parts"]),
                    "precompression_prompt_hash": hash_text(result["precompression_prompt"]), "final_prompt_hash": hash_text(result["final_prompt"]),
                    "input_tokens_precompression": result["compression"]["token_scope"].get("precompression_target_prompt_tokens", result["input_tokens"]) if result["compression"]["token_scope"] else result["input_tokens"],
                    "input_tokens_final": result["input_tokens"], "generated_text": result["generated_text"], "generated_text_hash": hash_text(result["generated_text"]), "output_token_ids_hash": hash_json(result["output_token_ids"]),
                    "output_tokens": result["output_tokens"], "stop_reason": result["stop_reason"], "cap_hit": result["cap_hit"], "success": result["success"], "error": result["error"],
                    "model_init_ms": result["timing"]["model_init_ms"], "compressor_init_ms": result["timing"]["compressor_init_ms"], "compression_total_ms": result["timing"]["compression_total_ms"], "target_prefill_ms": result["timing"]["target_prefill_ms"], "draft_prefill_ms": result["timing"]["draft_prefill_ms"], "decode_total_ms": result["timing"]["decode_total_ms"], "request_e2e_ms": result["timing"]["request_e2e_ms"],
                    "peak_allocated_bytes": result["vram"]["peak_allocated_bytes"], "peak_reserved_bytes": result["vram"]["peak_reserved_bytes"], "measurement_scope": result["vram"]["measurement_scope"], "measurement_mode": "benchmark",
                    "verification_calls": dflash["verification_calls"], "acceptance_lengths": dflash["acceptance_lengths"], "tau_tokens_advanced_per_verification": sum(dflash["acceptance_lengths"]) / dflash["verification_calls"] if dflash["verification_calls"] else 0.0,
                    "draft_tokens_proposed": proposed, "accepted_draft_tokens": accepted, "draft_acceptance_rate": accepted / proposed if proposed else 0.0, "rollback_tokens": dflash["rollback_tokens"],
                    "quality": _quality(dataset, result["generated_text"], fixture["reference_answer"], result["cap_hit"]), "compression": result["compression"],
                }
                if condition_id != "baseline-ar":
                    validate_dflash_invariants(row)
                rows.append(row)
        finally:
            engine.close()
        write_jsonl_atomic(output_dir / "runs" / f"{condition_id.replace('-', '_')}.jsonl", rows)
    write_json(output_dir / "resolved_config.json", config_bundle)
    (output_dir / "resolved_config.sha256").write_text(hash_json(config_bundle) + "\n", encoding="utf-8")
    manifest = {"dataset": dataset, "subset": subset, "fixture_ids": [row["fixture_id"] for row in fixtures], "dataset_manifest_hashes": manifests, "conditions": conditions, "runtime": "ccdf.runtime.engine.RuntimeEngine"}
    write_json(output_dir / "benchmark_manifest.json", manifest)
    return manifest


def evaluate_run_dir(run_dir: Path) -> dict[str, Any]:
    manifest = json.loads((run_dir / "benchmark_manifest.json").read_text(encoding="utf-8"))
    rows = []
    for path in sorted((run_dir / "runs").glob("*.jsonl")):
        rows.extend(read_jsonl(path))
    summary = []
    failures = []
    for condition in manifest["conditions"]:
        selected = [row for row in rows if row["condition"]["condition_id"] == condition]
        correct = sum(row["quality"].get("label") == "strict_correct" for row in selected)
        summary.append({"condition": condition, "rows": len(selected), "success": sum(row["success"] for row in selected), "cap_hits": sum(row["cap_hit"] for row in selected), "gsm8k_strict_correct": correct if manifest["dataset"] == "gsm8k" else None, "mean_e2e_ms": sum(row["request_e2e_ms"] for row in selected) / len(selected), "semantic_correctness": "NOT_CLAIMED" if manifest["dataset"] == "qmsum" else "numeric_proxy_only"})
        failures.extend(row for row in selected if row["cap_hit"] or not row["success"])
    write_json(run_dir / "quality_summary.json", {"dataset": manifest["dataset"], "rows": len(rows), "semantic_correctness": "NOT_CLAIMED" if manifest["dataset"] == "qmsum" else "numeric_proxy_only", "conditions": summary})
    write_jsonl_atomic(run_dir / "failure_samples.jsonl", failures)
    write_json(run_dir / "evaluation_manifest.json", {"source_benchmark_manifest": str(run_dir / "benchmark_manifest.json"), "models_loaded": False, "evaluator": "configured"})
    with (run_dir / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader(); writer.writerows(summary)
    return {"rows": len(rows), "conditions": summary}


def _git_commit() -> str:
    import subprocess
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
