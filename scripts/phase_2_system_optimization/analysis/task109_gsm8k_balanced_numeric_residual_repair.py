from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_2_system_optimization.analysis import task95b_quality_proxy_calibration as t95b


DEFAULT_BASE = Path("results/phase_2_system_optimization/final_reruns")
DEFAULT_T105A_DIR = DEFAULT_BASE / "task105a_gsm8k_controlled_speed_matrix"
DEFAULT_T106B_DIR = DEFAULT_BASE / "task106b_gsm8k_cap_limited_fix"
DEFAULT_T107B_DIR = DEFAULT_BASE / "task107b_gsm8k_policy_refinement_fix"
DEFAULT_OUTPUT_DIR = DEFAULT_BASE / "task109_gsm8k_balanced_numeric_residual_repair"

DEFAULT_T105A_JSONL = DEFAULT_T105A_DIR / "runs/cc_dflash_r2_light_gpu_gsm8k_short_seed42_n100_mnt256.jsonl"
DEFAULT_T106B_JSONL = DEFAULT_T106B_DIR / "runs/cc_dflash_r2_light_gpu_gsm8k_seed42_n100_mnt256_concise_final_answer.jsonl"
DEFAULT_T107B_JSONL = DEFAULT_T107B_DIR / "runs/cc_dflash_r2_light_gpu_gsm8k_seed42_n100_mnt256_minimal_arithmetic_verify.jsonl"
DEFAULT_T109_JSONL = DEFAULT_OUTPUT_DIR / "runs/cc_dflash_r2_light_gpu_gsm8k_seed42_n100_mnt256_numeric_detail_preserve.jsonl"
DEFAULT_BASELINE_JSONL = DEFAULT_T105A_DIR / "runs/baseline_ar_gsm8k_short_seed42_n100_mnt256.jsonl"
DEFAULT_DFLASH_JSONL = DEFAULT_T105A_DIR / "runs/dflash_r1_gsm8k_short_seed42_n100_mnt256.jsonl"

POLICY_NAME = "gsm8k_numeric_detail_preserve_v1"
POLICY_SUFFIX = (
    "Use only the numbers and conditions given in the problem. Keep the reasoning concise but "
    "include all necessary arithmetic steps. Do not skip units or constraints. End with exactly "
    "one line in the format: Final answer: <number>. Do not continue after the final answer."
)
T106B_POLICY_NAME = "gsm8k_concise_final_answer_v1"
T107B_POLICY_NAME = "gsm8k_minimal_arithmetic_verify_v1"

OUTPUT_RELATIVE_PATHS = (
    "summary/task109_repair_summary.json",
    "summary/task109_wrong_numeric_audit.json",
    "summary/task109_policy_decision.json",
    "summary/task109_condition_metrics.json",
    "summary/task109_comparison_vs_t106b_t107b.json",
    "summary/task109_balanced_candidate_decision.json",
    "summary/task109_claim_update.json",
    "summary/task109_next_task_decision.json",
    "tables/task109_gsm8k_balanced_comparison.csv",
)

LABELS = (
    "strict_correct",
    "strict_wrong_numeric",
    "cap_limited_incomplete",
    "format_or_extraction_sensitive",
    "answer_missing",
    "proxy_uncertain",
)
ID_KEYS = ("fixture_id", "dataset_id", "sample_id", "id", "question_id")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: line {line_number} is not a JSON object")
        rows.append(payload)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["metric", "t105a_optimized", "t106b_concise_final_answer", "t107b_minimal_arithmetic_verify", "t109_numeric_detail_preserve"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _numeric(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _avg(values: list[float | None]) -> float | None:
    numeric = [value for value in values if isinstance(value, (int, float))]
    return round(mean(numeric), 6) if numeric else None


def _max(values: list[float | None]) -> float | None:
    numeric = [value for value in values if isinstance(value, (int, float))]
    return round(max(numeric), 6) if numeric else None


def _rate(count: int, total: int) -> float | None:
    return round(count / total, 6) if total else None


def _fixture_id(row: dict[str, Any], index: int) -> str:
    for key in ID_KEYS:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return f"row_{index:04d}"


def _e2e(row: dict[str, Any]) -> float | None:
    direct = _numeric(row, "e2e_time_s", "end_to_end_time_s")
    if direct is not None:
        return direct
    generation = _numeric(row, "generation_time_s")
    if generation is None:
        return None
    return generation + ((_numeric(row, "t_compress_ms") or 0.0) / 1000.0)


def _failure_flags(rows: list[dict[str, Any]]) -> dict[str, Any]:
    messages: list[str] = []
    for row in rows:
        for key, value in row.items():
            lowered = str(key).lower()
            if not any(token in lowered for token in ("failure", "error", "oom", "cuda")):
                continue
            if value in (None, "", False):
                continue
            if lowered in {"compressor_device_map", "requested_compressor_device_map"} and str(value).startswith("cuda"):
                continue
            messages.append(f"{key}={value}")
    lowered_messages = [message.lower() for message in messages]
    return {
        "messages": messages,
        "oom_or_cuda_failure": any("oom" in message or "cuda" in message for message in lowered_messages),
    }


def _calibrate_rows(rows: list[dict[str, Any]], path: Path, label: str) -> list[dict[str, Any]]:
    calibrated: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        item = t95b.calibrate_row(row, profile=label, row_index=index, pair_id=_fixture_id(row, index), artifact=path)
        item["fixture_id"] = _fixture_id(row, index)
        item["raw_row"] = row
        calibrated.append(item)
    return calibrated


def _summarize_rows(rows: list[dict[str, Any]], path: Path, label: str) -> dict[str, Any]:
    if not rows:
        return {"row_count": 0}
    calibrated = _calibrate_rows(rows, path, label)
    label_counts = {
        label_name: sum(1 for item in calibrated if item["calibrated_label"] == label_name)
        for label_name in LABELS
    }
    e2e_values = [_e2e(row) for row in rows]
    flags = _failure_flags(rows)
    return {
        "label": label,
        "artifact": str(path),
        "row_count": len(rows),
        "strict_correct_count": sum(1 for item in calibrated if item["strict_correct"]),
        "strict_correct_rate": _rate(sum(1 for item in calibrated if item["strict_correct"]), len(rows)),
        "cap_limited_incomplete_count": label_counts["cap_limited_incomplete"],
        "cap_limited_incomplete_rate": _rate(label_counts["cap_limited_incomplete"], len(rows)),
        "strict_wrong_numeric_count": label_counts["strict_wrong_numeric"],
        "strict_wrong_numeric_rate": _rate(label_counts["strict_wrong_numeric"], len(rows)),
        "answer_missing_count": label_counts["answer_missing"],
        "proxy_uncertain_count": label_counts["proxy_uncertain"],
        "format_or_extraction_sensitive_count": label_counts["format_or_extraction_sensitive"],
        "final_answer_marker_count": sum(1 for item in calibrated if item["final_answer_marker_present"]),
        "final_answer_marker_rate": _rate(
            sum(1 for item in calibrated if item["final_answer_marker_present"]), len(rows)
        ),
        "exact_containment_diagnostic_count": sum(1 for item in calibrated if item["exact_containment"]),
        "cap_limited_fixture_ids": sorted(
            str(item["fixture_id"]) for item in calibrated if item["calibrated_label"] == "cap_limited_incomplete"
        ),
        "strict_wrong_numeric_fixture_ids": sorted(
            str(item["fixture_id"]) for item in calibrated if item["calibrated_label"] == "strict_wrong_numeric"
        ),
        "avg_e2e_time_s": _avg(e2e_values),
        "avg_generation_time_s": _avg([_numeric(row, "generation_time_s") for row in rows]),
        "avg_tokens_per_second": _avg([_numeric(row, "tokens_per_second", "tok_per_sec") for row in rows]),
        "avg_tau_mean": _avg([_numeric(row, "tau_mean") for row in rows]),
        "avg_t_prefill_ms": _avg([_numeric(row, "t_prefill_ms") for row in rows]),
        "avg_t_compress_ms": _avg([_numeric(row, "t_compress_ms") for row in rows]),
        "avg_R_actual": _avg([_numeric(row, "R_actual", "actual_compression_ratio", "compression_ratio") for row in rows]),
        "avg_output_tokens": _avg([_numeric(row, "output_tokens", "generated_token_count") for row in rows]),
        "max_vram_reserved_gib": _max([_numeric(row, "vram_reserved_gib") for row in rows]),
        "max_prefill_vram_reserved_gib": _max([_numeric(row, "prefill_vram_reserved_gib") for row in rows]),
        "failure_flags": flags,
        "oom_or_cuda_failure": flags["oom_or_cuda_failure"],
    }


def audit_metadata(rows: list[dict[str, Any]], expected_n: int) -> dict[str, Any]:
    errors: list[str] = []
    if len(rows) != expected_n:
        errors.append(f"expected {expected_n} rows, found {len(rows)}")
    for index, row in enumerate(rows, start=1):
        prefix = f"row {index}"
        if row.get("condition") != "CC-DFlash-R2":
            errors.append(f"{prefix}: condition is not CC-DFlash-R2")
        if row.get("dataset_name") != "gsm8k_short":
            errors.append(f"{prefix}: dataset_name is not gsm8k_short")
        if row.get("prompt_source") != "dataset":
            errors.append(f"{prefix}: prompt_source is not dataset")
        if row.get("max_new_tokens") != 256:
            errors.append(f"{prefix}: max_new_tokens is not 256")
        if row.get("compressor_profile") != "light":
            errors.append(f"{prefix}: compressor_profile is not light")
        if str(row.get("compressor_device_map")) not in {"cuda", "cuda:0"}:
            errors.append(f"{prefix}: compressor_device_map is not cuda")
        if str(row.get("requested_compressor_device_map")) not in {"cuda", "cuda:0"}:
            errors.append(f"{prefix}: requested_compressor_device_map is not cuda")
        if row.get("local_files_only") is not True:
            errors.append(f"{prefix}: local_files_only is not true")
        if row.get("gsm8k_policy_suffix_override") is not True:
            errors.append(f"{prefix}: gsm8k policy override missing")
        if row.get("gsm8k_answer_policy_enabled") is not True:
            errors.append(f"{prefix}: gsm8k answer policy metadata missing")
        if row.get("gsm8k_answer_policy_type") != POLICY_NAME:
            errors.append(f"{prefix}: policy type mismatch")
        if row.get("gsm8k_answer_policy_preserved") is not True:
            errors.append(f"{prefix}: gsm8k answer policy not preserved")
    flags = _failure_flags(rows)
    if flags["oom_or_cuda_failure"]:
        errors.append("OOM/CUDA failure flag detected")
    return {
        "valid": not errors,
        "errors": errors,
        "row_count": len(rows),
        "expected_row_count": expected_n,
        "policy_name": POLICY_NAME,
        "policy_suffix": POLICY_SUFFIX,
        "policy_override_rows": sum(1 for row in rows if row.get("gsm8k_policy_suffix_override") is True),
        "policy_preserved_rows": sum(1 for row in rows if row.get("gsm8k_answer_policy_preserved") is True),
        "failure_flags": flags,
    }


def _delta(left: dict[str, Any], right: dict[str, Any], field: str) -> float | int | None:
    left_value = left.get(field)
    right_value = right.get(field)
    if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)):
        value = right_value - left_value
        if isinstance(left_value, int) and isinstance(right_value, int):
            return int(value)
        return round(float(value), 6)
    return None


def analyze(
    t105a_jsonl: Path = DEFAULT_T105A_JSONL,
    t106b_jsonl: Path = DEFAULT_T106B_JSONL,
    t107b_jsonl: Path = DEFAULT_T107B_JSONL,
    t109_jsonl: Path = DEFAULT_T109_JSONL,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    expected_n: int = 100,
    baseline_jsonl: Path = DEFAULT_BASELINE_JSONL,
    dflash_jsonl: Path = DEFAULT_DFLASH_JSONL,
) -> dict[str, Any]:
    t105a_rows = load_jsonl(t105a_jsonl)
    t106b_rows = load_jsonl(t106b_jsonl)
    t107b_rows = load_jsonl(t107b_jsonl)
    t109_rows = load_jsonl(t109_jsonl)
    
    t105a = _summarize_rows(t105a_rows, t105a_jsonl, "T105A CC-DFlash-R2 Light GPU optimized")
    t106b = _summarize_rows(t106b_rows, t106b_jsonl, "T106B CC-DFlash-R2 Light GPU concise")
    t107b = _summarize_rows(t107b_rows, t107b_jsonl, "T107B CC-DFlash-R2 Light GPU minimal arithmetic verify")
    
    baseline_rows = load_jsonl(baseline_jsonl)
    dflash_rows = load_jsonl(dflash_jsonl)
    
    baseline_summary = _summarize_rows(baseline_rows, baseline_jsonl, "T105A Baseline-AR context") if baseline_rows else None
    dflash_summary = _summarize_rows(dflash_rows, dflash_jsonl, "T105A DFlash-R1 context") if dflash_rows else None

    # Perform T106B wrong-numeric audit
    t106b_wrong_ids = set(t106b.get("strict_wrong_numeric_fixture_ids", []))
    t105a_wrong_ids = set(t105a.get("strict_wrong_numeric_fixture_ids", []))
    t107b_wrong_ids = set(t107b.get("strict_wrong_numeric_fixture_ids", []))
    baseline_wrong_ids = set(baseline_summary.get("strict_wrong_numeric_fixture_ids", [])) if baseline_summary else set()
    dflash_wrong_ids = set(dflash_summary.get("strict_wrong_numeric_fixture_ids", [])) if dflash_summary else set()
    t105a_cap_ids = set(t105a.get("cap_limited_fixture_ids", []))
    
    row_attributions = []
    cc_only_count = 0
    ref_shared_count = 0
    
    for fid in t106b_wrong_ids:
        in_base = fid in baseline_wrong_ids
        in_dflash = fid in dflash_wrong_ids
        in_ref = in_base or in_dflash
        was_cap = fid in t105a_cap_ids
        
        if in_ref:
            cat = "reference_also_wrong"
            ref_shared_count += 1
        elif was_cap:
            cat = "resolved_cap_but_wrong_number"
            cc_only_count += 1
        else:
            cat = "cc_only_wrong"
            cc_only_count += 1
            
        row_attributions.append({
            "fixture_id": fid,
            "cause_category": cat,
            "in_baseline": in_base,
            "in_dflash": in_dflash,
            "was_cap_limited_t105a": was_cap
        })
        
    wrong_numeric_audit = {
        "t106b_wrong_numeric_count": len(t106b_wrong_ids),
        "t106b_wrong_numeric_fixture_ids": sorted(list(t106b_wrong_ids)),
        "persistent_from_t105a": sorted(list(t106b_wrong_ids & t105a_wrong_ids)),
        "persistent_in_t107b": sorted(list(t106b_wrong_ids & t107b_wrong_ids)),
        "resolved_by_t107b": sorted(list(t106b_wrong_ids - t107b_wrong_ids)),
        "new_in_t107b": sorted(list(t107b_wrong_ids - t106b_wrong_ids)),
        "shared_with_baseline_ar": sorted(list(t106b_wrong_ids & baseline_wrong_ids)),
        "shared_with_dflash_r1": sorted(list(t106b_wrong_ids & dflash_wrong_ids)),
        "row_attributions": row_attributions,
        "cc_only_wrong_count": cc_only_count,
        "reference_shared_count": ref_shared_count
    }
    
    rerun_justified = cc_only_count >= 2
    policy_decision = {
        "rerun_justified": rerun_justified,
        "reason": "CC-only wrong-numeric rows present that may benefit from numeric-detail preservation" if rerun_justified else "Most wrong-numeric rows are reference-shared; policy change unlikely to help"
    }
    
    t109 = None
    metadata = {"valid": False}
    
    if t109_rows:
        t109 = _summarize_rows(t109_rows, t109_jsonl, "T109 CC-DFlash-R2 Light GPU numeric detail preserve")
        metadata = audit_metadata(t109_rows, expected_n)
        
        t109_strict = t109.get("strict_correct_count", 0)
        t106b_strict = t106b.get("strict_correct_count", 0)
        t109_wrong = t109.get("strict_wrong_numeric_count", 100)
        t106b_wrong = t106b.get("strict_wrong_numeric_count", 100)
        t109_cap = t109.get("cap_limited_incomplete_count", 100)
        
        if t109_strict >= 88 and t109_cap <= 2 and t109_wrong < 10:
            candidate = "T109"
            reason = "Strict >= 88, cap <= 2, wrong numeric < 10"
            cand_dict = {
                "candidate": "T109 CC-DFlash-R2 Light GPU numeric detail preserve policy",
                "candidate_policy_name": POLICY_NAME,
                "strict_correct_count": t109_strict,
                "cap_limited_incomplete_count": t109_cap,
                "strict_wrong_numeric_count": t109_wrong,
                "default_switch_authorized": False,
            }
        elif t109_strict < t106b_strict or t109_wrong > t106b_wrong:
            candidate = "T106B"
            reason = "Strict dropped or wrong numeric increased compared to T106B"
            cand_dict = {
                "candidate": "T106B CC-DFlash-R2 Light GPU concise final-answer policy",
                "candidate_policy_name": T106B_POLICY_NAME,
                "strict_correct_count": t106b_strict,
                "cap_limited_incomplete_count": t106b.get("cap_limited_incomplete_count"),
                "strict_wrong_numeric_count": t106b_wrong,
                "default_switch_authorized": False,
            }
        else:
            candidate = "T106B"
            reason = "Did not meet strict improvement threshold"
            cand_dict = {
                "candidate": "T106B CC-DFlash-R2 Light GPU concise final-answer policy",
                "candidate_policy_name": T106B_POLICY_NAME,
                "strict_correct_count": t106b_strict,
                "cap_limited_incomplete_count": t106b.get("cap_limited_incomplete_count"),
                "strict_wrong_numeric_count": t106b_wrong,
                "default_switch_authorized": False,
            }
            
        balanced_candidate_decision = {
            "selected_candidate": candidate,
            "reason": reason,
            **cand_dict
        }
        decision = "PASS_WITH_CAVEAT" if metadata["valid"] else "PARTIAL"
        if t109.get("oom_or_cuda_failure"):
            decision = "FAIL"
    else:
        balanced_candidate_decision = {
            "selected_candidate": "T106B",
            "reason": "no_rerun_data_audit_only",
            "candidate": "T106B CC-DFlash-R2 Light GPU concise final-answer policy",
            "candidate_policy_name": T106B_POLICY_NAME,
            "strict_correct_count": t106b.get("strict_correct_count"),
            "cap_limited_incomplete_count": t106b.get("cap_limited_incomplete_count"),
            "strict_wrong_numeric_count": t106b.get("strict_wrong_numeric_count"),
            "default_switch_authorized": False,
        }
        decision = "AUDIT_ONLY"

    claim_update = {
        "allowed_claims": [
            "T109 balances the GSM8K candidate after T106B/T107B.",
            "It selects the best scoped GSM8K policy based on strict, cap-limited, wrong-numeric, and E2E metrics, without authorizing default switch."
        ],
        "blocked_claims": [
            "Quality is fully solved.",
            "Optimized CC-DFlash becomes default.",
            "QMSum semantic risk is resolved."
        ],
        "default_switch_claim": "blocked",
        "qmsum_claim_change": "none",
        "best_gsm8k_candidate_policy": balanced_candidate_decision["candidate_policy_name"],
    }
    
    next_task = {
        "next_task": "T110 — QMSum Semantic Validation / Judge Protocol",
        "reason": "Proceeding to QMSum validation after closing GSM8K policy branch.",
        "automatic_default_switch": False,
        "automatic_full_matrix": False,
    }
    
    condition_metrics = {
        "t105a_optimized_cc_dflash_r2_light_gpu": t105a,
        "t106b_concise_final_answer": t106b,
        "t107b_minimal_arithmetic_verify": t107b,
    }
    if baseline_summary: condition_metrics["t105a_baseline_ar_context"] = baseline_summary
    if dflash_summary: condition_metrics["t105a_dflash_r1_context"] = dflash_summary
    if t109: condition_metrics["t109_numeric_detail_preserve"] = t109
    
    comparison_vs_t106b_t107b = {
        "t106b_concise_artifact": str(t106b_jsonl),
        "t107b_refined_artifact": str(t107b_jsonl),
        "t109_balanced_artifact": str(t109_jsonl) if t109 else None,
        "strict_correct_counts": {
            "t106b_concise": t106b.get("strict_correct_count"),
            "t107b_refined": t107b.get("strict_correct_count"),
            "t109_balanced": t109.get("strict_correct_count") if t109 else None,
        },
        "cap_limited_counts": {
            "t106b_concise": t106b.get("cap_limited_incomplete_count"),
            "t107b_refined": t107b.get("cap_limited_incomplete_count"),
            "t109_balanced": t109.get("cap_limited_incomplete_count") if t109 else None,
        },
        "strict_wrong_numeric_counts": {
            "t106b_concise": t106b.get("strict_wrong_numeric_count"),
            "t107b_refined": t107b.get("strict_wrong_numeric_count"),
            "t109_balanced": t109.get("strict_wrong_numeric_count") if t109 else None,
        },
        "avg_e2e_time_s": {
            "t106b_concise": t106b.get("avg_e2e_time_s"),
            "t107b_refined": t107b.get("avg_e2e_time_s"),
            "t109_balanced": t109.get("avg_e2e_time_s") if t109 else None,
        }
    }
    
    summary = {
        "task": "T109",
        "title": "GSM8K Balanced Numeric Residual Repair",
        "decision": decision,
        "policy": {
            "policy_name": POLICY_NAME,
            "policy_suffix": POLICY_SUFFIX,
            "scope": "GSM8K-only runtime override for optimized CC-DFlash-R2 Light GPU",
        },
        "expected_n": expected_n,
        "wrong_numeric_audit": wrong_numeric_audit,
        "policy_decision": policy_decision,
        "balanced_candidate_decision": balanced_candidate_decision,
        "claim_update": claim_update,
        "next_task_decision": next_task,
        "metadata_audit": metadata,
        "condition_metrics": condition_metrics,
        "comparison_vs_t106b_t107b": comparison_vs_t106b_t107b,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "summary/task109_repair_summary.json", summary)
    _write_json(output_dir / "summary/task109_wrong_numeric_audit.json", wrong_numeric_audit)
    _write_json(output_dir / "summary/task109_policy_decision.json", policy_decision)
    _write_json(output_dir / "summary/task109_condition_metrics.json", condition_metrics)
    _write_json(output_dir / "summary/task109_comparison_vs_t106b_t107b.json", comparison_vs_t106b_t107b)
    _write_json(output_dir / "summary/task109_balanced_candidate_decision.json", balanced_candidate_decision)
    _write_json(output_dir / "summary/task109_claim_update.json", claim_update)
    _write_json(output_dir / "summary/task109_next_task_decision.json", next_task)
    
    csv_rows = []
    metrics = (
        "strict_correct_count",
        "cap_limited_incomplete_count",
        "strict_wrong_numeric_count",
        "answer_missing_count",
        "final_answer_marker_count",
        "avg_e2e_time_s",
        "avg_generation_time_s",
        "avg_tokens_per_second",
        "avg_t_compress_ms",
        "avg_R_actual",
        "avg_output_tokens",
        "max_vram_reserved_gib",
    )
    for metric in metrics:
        csv_rows.append({
            "metric": metric,
            "t105a_optimized": t105a.get(metric),
            "t106b_concise_final_answer": t106b.get(metric),
            "t107b_minimal_arithmetic_verify": t107b.get(metric),
            "t109_numeric_detail_preserve": t109.get(metric) if t109 else None,
            "delta_t109_minus_t106b": _delta(t106b, t109, metric) if t109 else None,
        })
    _write_csv(output_dir / "tables/task109_gsm8k_balanced_comparison.csv", csv_rows)
    
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze T109 GSM8K policy refinement result")
    parser.add_argument("--t105a-jsonl", type=Path, default=DEFAULT_T105A_JSONL)
    parser.add_argument("--t106b-jsonl", type=Path, default=DEFAULT_T106B_JSONL)
    parser.add_argument("--t107b-jsonl", type=Path, default=DEFAULT_T107B_JSONL)
    parser.add_argument("--t109-jsonl", type=Path, default=DEFAULT_T109_JSONL)
    parser.add_argument("--baseline-jsonl", type=Path, default=DEFAULT_BASELINE_JSONL)
    parser.add_argument("--dflash-jsonl", type=Path, default=DEFAULT_DFLASH_JSONL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--expected-n", type=int, default=100)
    args = parser.parse_args()
    
    result = analyze(
        t105a_jsonl=args.t105a_jsonl,
        t106b_jsonl=args.t106b_jsonl,
        t107b_jsonl=args.t107b_jsonl,
        t109_jsonl=args.t109_jsonl,
        output_dir=args.output_dir,
        expected_n=args.expected_n,
        baseline_jsonl=args.baseline_jsonl,
        dflash_jsonl=args.dflash_jsonl,
    )
    
    comp = result["comparison_vs_t106b_t107b"]
    cand = result["balanced_candidate_decision"]
    print(f"status={result['decision']}")
    print(f"rerun_justified={result['policy_decision']['rerun_justified']}")
    print(f"best_candidate={cand['candidate_policy_name']}")
    
    if result["decision"] != "AUDIT_ONLY":
        print(f"strict={comp['strict_correct_counts']['t106b_concise']}->{comp['strict_correct_counts']['t109_balanced']}")
        print(f"wrong_numeric={comp['strict_wrong_numeric_counts']['t106b_concise']}->{comp['strict_wrong_numeric_counts']['t109_balanced']}")
        print(f"cap_limited={comp['cap_limited_counts']['t106b_concise']}->{comp['cap_limited_counts']['t109_balanced']}")
    
    print(f"next_task={result['next_task_decision']['next_task']}")
    print(f"wrote={args.output_dir}")


if __name__ == "__main__":
    main()
