#!/usr/bin/env python3
"""Independent integrity, metric, fairness, and claim audit for frozen n20 raw evidence."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/final-benchmark-n20"
CONDITIONS = ("C1", "C2", "C3", "C4")
FINAL_NUMERIC = re.compile(r"Final answer:\s*([-+]?\$?[\d,]+(?:\.\d+)?)\.?\s*$", re.I)
WORD = re.compile(r"[A-Za-z0-9]+")
QMSUM_MAX_MEAN_F1_DROP = 0.01


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def canonical_row_hash(row: dict[str, Any]) -> str:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def describe(values: list[float]) -> dict[str, float | int] | None:
    if not values:
        return None
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def normalize_numeric(value: str) -> str | None:
    try:
        number = Decimal(value.replace("$", "").replace(",", "").strip())
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    normalized = format(number.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return "0" if normalized in {"-0", "+0", ""} else normalized


def gsm_eval(text: str, reference: str) -> dict[str, Any]:
    if not text.strip():
        parsed, status = None, "empty_output"
    else:
        match = FINAL_NUMERIC.search(text)
        parsed = normalize_numeric(match.group(1)) if match else None
        status = "parsed" if parsed is not None else "missing_final_answer_line"
    expected = normalize_numeric(reference)
    return {"parsed_answer": parsed, "parser_status": status, "quality_score": float(parsed == expected)}


def qmsum_eval(text: str, reference: str) -> dict[str, Any]:
    prediction = [m.group(0).lower() for m in WORD.finditer(text)]
    truth = [m.group(0).lower() for m in WORD.finditer(reference)]
    previous = [0] * (len(truth) + 1)
    for token in prediction:
        current = [0]
        for index, truth_token in enumerate(truth, start=1):
            current.append(previous[index - 1] + 1 if token == truth_token else max(previous[index], current[-1]))
        previous = current
    lcs = previous[-1]
    precision = lcs / len(prediction) if prediction else 0.0
    recall = lcs / len(truth) if truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "quality_score": f1,
        "rouge_l_precision": precision,
        "rouge_l_recall": recall,
        "rouge_l_f1": f1,
        "lcs_tokens": lcs,
        "prediction_tokens": len(prediction),
        "reference_tokens": len(truth),
        "empty_output": not prediction,
    }


def row_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (row["condition_id"], row["sample_id"], row["phase"], row["repetition"], row["request_index"])


def checksum_gate(dataset_dir: Path, rows_by_condition: dict[str, list[dict[str, Any]]]) -> bool:
    for condition, rows in rows_by_condition.items():
        sidecar = read_jsonl(dataset_dir / f"checkpoints/{condition}.jsonl.checksums.jsonl")
        if len(sidecar) != len(rows):
            return False
        for row, checksum in zip(rows, sidecar, strict=True):
            if tuple(checksum["key"]) != row_key(row) or checksum["row_sha256"] != canonical_row_hash(row):
                return False
    return True


def cache_checksum_gate(dataset_dir: Path, cache: list[dict[str, Any]]) -> bool:
    sidecar = read_jsonl(dataset_dir / "compression-cache.jsonl.checksums.jsonl")
    return len(sidecar) == len(cache) and all(
        checkpoint["sample_id"] == row["sample_id"]
        and checkpoint["row_sha256"] == canonical_row_hash(row)
        for row, checkpoint in zip(cache, sidecar, strict=True)
    )


def summarize_condition(dataset: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    measured = [row for row in rows if row["phase"] == "measured"]
    success = [row for row in measured if row["status"] == "success"]
    result: dict[str, Any] = {
        "measured_rows": len(measured),
        "successful_rows": len(success),
        "failed_rows": len(measured) - len(success),
        "quality": describe([float(row["quality_score"]) for row in success]),
        "empty_outputs": sum(not str(row["decoded_output"]).strip() for row in success),
        "generation_latency_ms": describe([float(row["generation_warm_e2e_time_ms"]) for row in success]),
        "decode_tok_s": describe([float(row["decode_tok_s"]) for row in success]),
        "compressor_latency_ms": describe([float(row["compressor_latency_ms"]) for row in success if row["compressor_latency_ms"] is not None]),
        "pipeline_e2e_latency_ms": describe([float(row["pipeline_warm_e2e_time_ms"]) for row in success]),
        "pipeline_e2e_tok_s": describe([float(row["pipeline_e2e_tok_s"]) for row in success]),
        "target_user_original_tokens": describe([float(row["target_user_original_tokens"]) for row in success]),
        "target_user_compressed_tokens": describe([float(row["target_user_compressed_tokens"]) for row in success]),
        "target_full_original_tokens": describe([float(row["target_full_original_tokens"]) for row in success]),
        "target_full_compressed_tokens": describe([float(row["target_full_compressed_tokens"]) for row in success]),
        "target_user_keep_rate": describe([float(row["target_user_keep_rate"]) for row in success]),
        "target_full_keep_rate": describe([float(row["target_full_keep_rate"]) for row in success]),
        "fallback_count": sum(row["compression_status"] == "FACT_SAFETY_FALLBACK" for row in success),
    }
    if dataset == "gsm8k":
        result["numeric_em"] = statistics.fmean(float(row["quality_score"]) for row in success) if success else 0.0
        result["correct"] = sum(float(row["quality_score"]) == 1.0 for row in success)
        result["parser_failures"] = sum(row["parser_status"] != "parsed" for row in success)
    else:
        result["rouge_l_precision"] = describe([float(row["quality_details"]["rouge_l_precision"]) for row in success])
        result["rouge_l_recall"] = describe([float(row["quality_details"]["rouge_l_recall"]) for row in success])
        result["rouge_l_f1"] = result["quality"]
    return result


def comparison(metrics: dict[str, Any], left: str, right: str) -> dict[str, Any]:
    left_latency = metrics[left]["pipeline_e2e_latency_ms"]["mean"]
    right_latency = metrics[right]["pipeline_e2e_latency_ms"]["mean"]
    left_decode = metrics[left]["decode_tok_s"]["mean"]
    right_decode = metrics[right]["decode_tok_s"]["mean"]
    left_pipeline = metrics[left]["pipeline_e2e_tok_s"]["mean"]
    right_pipeline = metrics[right]["pipeline_e2e_tok_s"]["mean"]
    delta = right_latency - left_latency
    return {
        "left": left,
        "right": right,
        "pipeline_e2e_latency_delta_ms": delta,
        "pipeline_e2e_latency_delta_percent": delta / left_latency * 100,
        "decode_tok_s_delta": right_decode - left_decode,
        "decode_tok_s_delta_percent": (right_decode - left_decode) / left_decode * 100,
        "pipeline_e2e_tok_s_delta": right_pipeline - left_pipeline,
        "pipeline_e2e_tok_s_delta_percent": (right_pipeline - left_pipeline) / left_pipeline * 100,
    }


def audit_dataset(dataset: str, sample_manifest: dict[str, Any], environment: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    dataset_dir = OUT / dataset
    samples = read_jsonl(ROOT / sample_manifest["datasets"][dataset]["sample_file"])
    sample_by_id = {row["sample_id"]: row for row in samples}
    manifest = read_json(dataset_dir / "run-manifest.json")
    cache = read_jsonl(dataset_dir / "compression-cache.jsonl")
    compressor = read_json(dataset_dir / "compressor-audit.json")
    generic = read_json(dataset_dir / "generic-audit/audit.json")
    rows_by_condition = {condition: read_jsonl(dataset_dir / f"checkpoints/{condition}.jsonl") for condition in CONDITIONS}
    all_rows = [row for condition in CONDITIONS for row in rows_by_condition[condition]]
    measured = {condition: [row for row in rows_by_condition[condition] if row["phase"] == "measured"] for condition in CONDITIONS}
    write_jsonl(dataset_dir / "raw.jsonl", all_rows)

    recompute_failures = []
    for row in all_rows:
        if row["status"] != "success":
            continue
        expected = gsm_eval(row["decoded_output"], row["reference_text"]) if dataset == "gsm8k" else qmsum_eval(row["decoded_output"], row["reference_text"])
        fields = ["quality_score"]
        if dataset == "gsm8k":
            fields += ["parsed_answer", "parser_status"]
        for field in fields:
            actual = row[field]
            wanted = expected[field]
            equal = math.isclose(float(actual), float(wanted), rel_tol=1e-12, abs_tol=1e-12) if isinstance(wanted, float) else actual == wanted
            if not equal:
                recompute_failures.append({"key": row_key(row), "field": field, "actual": actual, "expected": wanted})
        if dataset == "qmsum":
            for field in ("rouge_l_precision", "rouge_l_recall", "rouge_l_f1", "lcs_tokens", "prediction_tokens", "reference_tokens", "empty_output"):
                actual, wanted = row["quality_details"][field], expected[field]
                equal = math.isclose(float(actual), float(wanted), rel_tol=1e-12, abs_tol=1e-12) if isinstance(wanted, float) else actual == wanted
                if not equal:
                    recompute_failures.append({"key": row_key(row), "field": f"quality_details.{field}", "actual": actual, "expected": wanted})

    metrics = {condition: summarize_condition(dataset, rows_by_condition[condition]) for condition in CONDITIONS}
    comparisons = {
        "C1_vs_C2_dflash_uncompressed": comparison(metrics, "C1", "C2"),
        "C3_vs_C4_dflash_compressed": comparison(metrics, "C3", "C4"),
        "C1_vs_C3_compression_on_ar": comparison(metrics, "C1", "C3"),
        "C2_vs_C4_cc_dflash_vs_dflash": comparison(metrics, "C2", "C4"),
    }
    cache_by_id = {row["sample_id"]: row for row in cache}
    ids = [row["sample_id"] for row in samples]
    expected_raw_keys = {
        (condition, row["sample_id"], phase, repetition, request_index)
        for condition in CONDITIONS
        for request_index, (phase, repetition, row) in enumerate(
            [("warmup", None, samples[0]), *[("measured", 0, sample) for sample in samples]]
        )
    }
    actual_keys = [row_key(row) for row in all_rows]
    parity: dict[str, list[dict[str, Any]]] = {"C1_C2": [], "C3_C4": []}
    for name, left, right in (("C1_C2", "C1", "C2"), ("C3_C4", "C3", "C4")):
        left_by_id = {row["sample_id"]: row for row in measured[left]}
        right_by_id = {row["sample_id"]: row for row in measured[right]}
        for sample_id in ids:
            lhs, rhs = left_by_id[sample_id], right_by_id[sample_id]
            mismatch = next(
                (index for index in range(min(len(lhs["generated_token_ids"]), len(rhs["generated_token_ids"]))) if lhs["generated_token_ids"][index] != rhs["generated_token_ids"][index]),
                min(len(lhs["generated_token_ids"]), len(rhs["generated_token_ids"])) if len(lhs["generated_token_ids"]) != len(rhs["generated_token_ids"]) else None,
            )
            parity[name].append({
                "sample_id": sample_id,
                "exact_token_parity": mismatch is None,
                "first_mismatch_index": mismatch,
                "left_parsed_answer": lhs["parsed_answer"],
                "right_parsed_answer": rhs["parsed_answer"],
                "left_quality_score": lhs["quality_score"],
                "right_quality_score": rhs["quality_score"],
            })

    source_unchanged = all(
        sha256(ROOT / path) == digest for path, digest in environment["source_sha256"].items()
    )
    hard = {
        "deterministic_n20_selection": len(ids) == len(set(ids)) == 20 and manifest["workload"]["sample_ids"] == ids,
        "raw_complete": set(actual_keys) == expected_raw_keys and len(actual_keys) == 84,
        "raw_unique": len(actual_keys) == len(set(actual_keys)),
        "row_checksums_valid": checksum_gate(dataset_dir, rows_by_condition),
        "compression_checksums_valid": cache_checksum_gate(dataset_dir, cache),
        "metric_recomputation_match": not recompute_failures and generic["gates"]["independent_metric_recomputation"],
        "c1_c2_prompt_fairness": all(a["input_prompt_sha256"] == b["input_prompt_sha256"] for a, b in zip(measured["C1"], measured["C2"], strict=True)),
        "c3_c4_cache_fairness": all(a["input_prompt_sha256"] == b["input_prompt_sha256"] == cache_by_id[a["sample_id"]]["compressed_prompt_sha256"] for a, b in zip(measured["C3"], measured["C4"], strict=True)),
        "same_samples_references_all_conditions": all([row["sample_id"] for row in measured[condition]] == ids and all(row["reference_text"] == sample_by_id[row["sample_id"]]["reference"] for row in measured[condition]) for condition in CONDITIONS),
        "compressor_cuda": compressor["status"] == "success" and compressor["resolved_device"].startswith("cuda") and compressor["silent_cpu_fallback"] is False,
        "fresh_single_cache_run": len({row["compression_run_id"] for row in cache}) == 1 and len(cache) == len(cache_by_id) == 20 and [row["sample_id"] for row in cache] == ids,
        "parser_and_output_health": all(metrics[condition]["empty_outputs"] == 0 for condition in CONDITIONS) and (dataset != "gsm8k" or all(metrics[condition]["parser_failures"] == 0 for condition in CONDITIONS)),
        "config_runtime_consistency": manifest["config_sha256"] == environment["config_sha256"] == sha256(OUT / "CONFIG-SNAPSHOT.yml") and all(row["seed"] == 42 and row["runtime"]["determinism"]["seed"] == 42 and row["runtime"]["determinism"]["sdpa_kernel_policy"] == "math" for row in all_rows if row["status"] == "success"),
        "source_snapshot_unchanged_since_preflight": source_unchanged,
        "generic_validity_gates": all(value for name, value in generic["gates"].items() if name != "original_generated_token_parity"),
    }
    if dataset == "qmsum":
        hard["qmsum_selector_deterministic_and_shared"] = all(generic["gates"][name] for name in ("qmsum_context_selection_accounting", "qmsum_selected_context_shared", "qmsum_compressed_context_shared")) and sample_manifest["reference_used_for_selection"] is False
    quality = {
        "gsm8k_c3_not_below_c1": dataset != "gsm8k" or metrics["C3"]["numeric_em"] >= metrics["C1"]["numeric_em"],
        "gsm8k_c4_not_below_c2": dataset != "gsm8k" or metrics["C4"]["numeric_em"] >= metrics["C2"]["numeric_em"],
        "qmsum_c3_mean_f1_drop_le_0_01": dataset != "qmsum" or metrics["C3"]["quality"]["mean"] >= metrics["C1"]["quality"]["mean"] - QMSUM_MAX_MEAN_F1_DROP,
        "qmsum_c4_mean_f1_drop_le_0_01": dataset != "qmsum" or metrics["C4"]["quality"]["mean"] >= metrics["C2"]["quality"]["mean"] - QMSUM_MAX_MEAN_F1_DROP,
    }
    audit = {
        "schema": "ccdf.final-benchmark-n20.dataset-audit.v1",
        "dataset": dataset,
        "benchmark_name": "QMSum query-aware budgeted-context benchmark" if dataset == "qmsum" else "GSM8K n=20",
        "hard_validity_pass": all(hard.values()),
        "quality_preservation_pass": all(quality.values()),
        "hard_gates": hard,
        "quality_gates": quality,
        "recompute_failures": recompute_failures,
        "generic_audit_conclusion": generic["conclusion"],
        "generic_failed_gates": [name for name, value in generic["gates"].items() if not value],
        "fallback_count": compressor["fallback_samples"],
        "fallback_rate": compressor["fallback_rate"],
        "compression_run_id": cache[0]["compression_run_id"],
    }
    metrics_payload = {
        "schema": "ccdf.final-benchmark-n20.metrics.v1",
        "dataset": dataset,
        "conditions": metrics,
        "comparisons": comparisons,
        "compression": generic["compression"],
    }
    return metrics_payload, audit, parity


def main() -> int:
    sample_manifest = read_json(OUT / "SAMPLE-MANIFEST.json")
    environment = read_json(OUT / "ENVIRONMENT.json")
    results = {}
    parity = {}
    for dataset in ("gsm8k", "qmsum"):
        metrics, audit, dataset_parity = audit_dataset(dataset, sample_manifest, environment)
        write_json(OUT / dataset / "metrics.json", metrics)
        write_json(OUT / dataset / "audit.json", audit)
        results[dataset] = {"metrics": metrics, "audit": audit}
        parity[dataset] = dataset_parity

    qmsum_samples = {row["sample_id"]: row for row in read_jsonl(ROOT / sample_manifest["datasets"]["qmsum"]["sample_file"])}
    qmsum_cache = {row["sample_id"]: row for row in read_jsonl(OUT / "qmsum/compression-cache.jsonl")}
    selection_rows = []
    for sample_id in sample_manifest["datasets"]["qmsum"]["samples"]:
        sid = sample_id["sample_id"]
        sample, cache = qmsum_samples[sid], qmsum_cache[sid]
        evidence = sample["metadata"]["context_selection"]
        selection_rows.append({
            "schema": "ccdf.final-benchmark-n20.qmsum-selection.v1",
            "sample_id": sid,
            "source_fingerprint": sample["source_fingerprint"],
            "meeting_index": sample["source_index"],
            "query_index": sample["metadata"]["query_index"],
            "full_transcript_target_tokens": evidence["full_transcript_token_count"],
            "chunk_count": evidence["full_chunk_count"],
            "selected_chunk_ids": evidence["selected_chunk_ids"],
            "selected_source_ranges": evidence["selected_source_ranges"],
            "selected_context_target_tokens": evidence["selected_context_token_count"],
            "selection_keep_rate": evidence["selection_keep_rate"],
            "query_term_coverage": evidence["query_term_coverage"],
            "selected_context_sha256": evidence["selected_context_sha256"],
            "compressed_context_sha256": cache["compressed_context_sha256"],
            "llmlingua_keep_rate": cache["llmlingua_keep_rate"],
            "overall_keep_rate": cache["overall_keep_rate"],
            "reference_used_for_selection": False,
        })
    write_jsonl(OUT / "qmsum/selection.jsonl", selection_rows)
    write_json(OUT / "parity-diagnostics.json", {"schema": "ccdf.final-benchmark-n20.parity.v1", "datasets": parity, "policy_changed": False})
    recomputed = {
        "schema": "ccdf.final-benchmark-n20.recomputed-metrics.v1",
        "pass": all(results[dataset]["audit"]["hard_gates"]["metric_recomputation_match"] for dataset in results),
        "datasets": {
            dataset: {
                "recompute_failures": results[dataset]["audit"]["recompute_failures"],
                "condition_quality_means": {condition: results[dataset]["metrics"]["conditions"][condition]["quality"]["mean"] for condition in CONDITIONS},
            }
            for dataset in results
        },
    }
    write_json(OUT / "recomputed-metrics.json", recomputed)
    hard_pass = all(results[dataset]["audit"]["hard_validity_pass"] for dataset in results)
    quality_pass = all(results[dataset]["audit"]["quality_preservation_pass"] for dataset in results)
    decision = "FINAL_RESULTS_FROZEN" if hard_pass and quality_pass else "FINAL_BENCHMARK_COMPLETE_WITH_FAILED_CLAIMS" if hard_pass else "FINAL_BENCHMARK_INVALID"
    final = {
        "schema": "ccdf.final-benchmark-n20.final-decision.v1",
        "decision": decision,
        "hard_validity_pass": hard_pass,
        "quality_preservation_pass": quality_pass,
        "datasets": {dataset: {"hard_validity_pass": results[dataset]["audit"]["hard_validity_pass"], "quality_preservation_pass": results[dataset]["audit"]["quality_preservation_pass"]} for dataset in results},
    }
    write_json(OUT / "final-decision.json", final)
    report = [
        "# Final benchmark n=20", "", f"Final status: **{decision}**", "",
        "The QMSum workload is the **QMSum query-aware budgeted-context benchmark**, not full-context QMSum. Its ROUGE-L score is a lexical proxy; semantic correctness is not claimed.", "",
        "## Condition quality", "", "| Dataset | C1 | C2 | C3 | C4 |", "|---|---:|---:|---:|---:|",
    ]
    for dataset in ("gsm8k", "qmsum"):
        values = results[dataset]["metrics"]["conditions"]
        report.append(f"| {dataset} | " + " | ".join(f"{values[c]['quality']['mean']:.6f}" for c in CONDITIONS) + " |")
    report += ["", "## Gate summary", "", "| Dataset | Hard validity | Quality preservation | Generic audit failed gates |", "|---|:---:|:---:|---|"]
    for dataset in ("gsm8k", "qmsum"):
        audit = results[dataset]["audit"]
        report.append(f"| {dataset} | {'PASS' if audit['hard_validity_pass'] else 'FAIL'} | {'PASS' if audit['quality_preservation_pass'] else 'FAIL'} | {', '.join(audit['generic_failed_gates']) or 'none'} |")
    report += [
        "", "## Claim boundaries", "",
        "- Exact generated-token parity is diagnostic and is preserved in `parity-diagnostics.json`; verifier policy was not changed.",
        "- Pipeline E2E determines performance interpretation. Decode throughput alone is not a CC-DFlash speedup claim.",
        "- QMSum reduction is separated into transcript selection, LLMLingua-on-selected-context, and full-transcript-to-compressed-context stages.",
        "- Timing is a single local RTX 4070 Laptop GPU run with one warmup and one measured repetition per sample; it is environment-specific.",
        "- Detailed per-condition latency, throughput, token, fallback, reduction, and four-way comparison metrics are in each dataset's `metrics.json`.",
    ]
    (OUT / "final-report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(final, sort_keys=True))
    return 0 if hard_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
