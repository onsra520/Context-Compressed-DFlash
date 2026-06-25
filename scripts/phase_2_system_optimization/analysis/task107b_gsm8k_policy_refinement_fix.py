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
DEFAULT_OUTPUT_DIR = DEFAULT_BASE / "task107b_gsm8k_policy_refinement_fix"
DEFAULT_T105A_JSONL = DEFAULT_T105A_DIR / "runs/cc_dflash_r2_light_gpu_gsm8k_short_seed42_n100_mnt256.jsonl"
DEFAULT_T106B_JSONL = (
    DEFAULT_T106B_DIR / "runs/cc_dflash_r2_light_gpu_gsm8k_seed42_n100_mnt256_concise_final_answer.jsonl"
)
DEFAULT_REFINED_JSONL = DEFAULT_OUTPUT_DIR / (
    "runs/cc_dflash_r2_light_gpu_gsm8k_seed42_n100_mnt256_minimal_arithmetic_verify.jsonl"
)
DEFAULT_BASELINE_JSONL = DEFAULT_T105A_DIR / "runs/baseline_ar_gsm8k_short_seed42_n100_mnt256.jsonl"
DEFAULT_DFLASH_JSONL = DEFAULT_T105A_DIR / "runs/dflash_r1_gsm8k_short_seed42_n100_mnt256.jsonl"

POLICY_NAME = "gsm8k_minimal_arithmetic_verify_v1"
POLICY_SUFFIX = (
    "Show only the necessary arithmetic. Verify the calculation once. End with exactly one line "
    "in the format: Final answer: <number>. Do not continue after the final answer."
)
T106B_POLICY_NAME = "gsm8k_concise_final_answer_v1"

OUTPUT_RELATIVE_PATHS = (
    "summary/task107b_fix_summary.json",
    "summary/task107b_condition_metrics.json",
    "summary/task107b_policy_comparison.json",
    "summary/task107b_wrong_numeric_delta.json",
    "summary/task107b_cap_limited_delta.json",
    "summary/task107b_runtime_delta.json",
    "summary/task107b_metadata_audit.json",
    "summary/task107b_claim_update.json",
    "summary/task107b_next_task_decision.json",
    "tables/task107b_gsm8k_policy_refinement_comparison.csv",
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
    fieldnames = list(rows[0].keys()) if rows else ["metric", "t105a_optimized", "t106b_concise", "t107b_refined"]
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


def _id_delta(reference: dict[str, Any], refined: dict[str, Any], field: str) -> dict[str, Any]:
    reference_ids = set(reference[field])
    refined_ids = set(refined[field])
    return {
        "resolved_ids": sorted(reference_ids - refined_ids),
        "new_ids": sorted(refined_ids - reference_ids),
        "persistent_ids": sorted(reference_ids & refined_ids),
    }


def _wrong_numeric_delta(t106b: dict[str, Any], refined: dict[str, Any]) -> dict[str, Any]:
    ids = _id_delta(t106b, refined, "strict_wrong_numeric_fixture_ids")
    return {
        "t106b_wrong_numeric_count": t106b["strict_wrong_numeric_count"],
        "t107b_wrong_numeric_count": refined["strict_wrong_numeric_count"],
        "wrong_numeric_delta_vs_t106b": _delta(t106b, refined, "strict_wrong_numeric_count"),
        **ids,
    }


def _cap_limited_delta(t106b: dict[str, Any], refined: dict[str, Any]) -> dict[str, Any]:
    ids = _id_delta(t106b, refined, "cap_limited_fixture_ids")
    return {
        "t106b_cap_limited_count": t106b["cap_limited_incomplete_count"],
        "t107b_cap_limited_count": refined["cap_limited_incomplete_count"],
        "cap_limited_delta_vs_t106b": _delta(t106b, refined, "cap_limited_incomplete_count"),
        **ids,
    }


def _runtime_delta(t105a: dict[str, Any], t106b: dict[str, Any], refined: dict[str, Any]) -> dict[str, Any]:
    return {
        "vs_t105a_optimized": {
            "avg_e2e_time_s_delta": _delta(t105a, refined, "avg_e2e_time_s"),
            "avg_t_compress_ms_delta": _delta(t105a, refined, "avg_t_compress_ms"),
            "avg_tokens_per_second_delta": _delta(t105a, refined, "avg_tokens_per_second"),
            "max_vram_reserved_gib_delta": _delta(t105a, refined, "max_vram_reserved_gib"),
        },
        "vs_t106b_concise": {
            "avg_e2e_time_s_delta": _delta(t106b, refined, "avg_e2e_time_s"),
            "avg_t_compress_ms_delta": _delta(t106b, refined, "avg_t_compress_ms"),
            "avg_tokens_per_second_delta": _delta(t106b, refined, "avg_tokens_per_second"),
            "max_vram_reserved_gib_delta": _delta(t106b, refined, "max_vram_reserved_gib"),
        },
        "t105a_avg_e2e_time_s": t105a["avg_e2e_time_s"],
        "t106b_avg_e2e_time_s": t106b["avg_e2e_time_s"],
        "t107b_avg_e2e_time_s": refined["avg_e2e_time_s"],
        "t105a_avg_t_compress_ms": t105a["avg_t_compress_ms"],
        "t106b_avg_t_compress_ms": t106b["avg_t_compress_ms"],
        "t107b_avg_t_compress_ms": refined["avg_t_compress_ms"],
    }


def _interpretation(t106b: dict[str, Any], refined: dict[str, Any], metadata: dict[str, Any]) -> str:
    if not metadata["valid"]:
        return "metadata_incomplete_policy_not_proven"
    strict_ok = refined["strict_correct_count"] >= t106b["strict_correct_count"]
    wrong_ok = refined["strict_wrong_numeric_count"] <= t106b["strict_wrong_numeric_count"]
    cap_low = refined["cap_limited_incomplete_count"] <= max(3, t106b["cap_limited_incomplete_count"] + 1)
    cap_materially_worse = refined["cap_limited_incomplete_count"] > t106b["cap_limited_incomplete_count"] + 3
    wrong_improved = refined["strict_wrong_numeric_count"] < t106b["strict_wrong_numeric_count"]
    if strict_ok and wrong_ok and cap_low:
        return "policy_refinement_supported"
    if wrong_improved and cap_materially_worse:
        return "wrong_numeric_improved_but_cap_regressed"
    if refined["strict_correct_count"] < t106b["strict_correct_count"]:
        return "t106b_remains_better_gsm8k_candidate"
    return "policy_refinement_not_supported"


def _best_candidate(interpretation: str, t106b: dict[str, Any], refined: dict[str, Any]) -> dict[str, Any]:
    if interpretation == "policy_refinement_supported":
        return {
            "candidate": "T107B CC-DFlash-R2 Light GPU minimal arithmetic verification",
            "candidate_policy_name": POLICY_NAME,
            "strict_correct_count": refined["strict_correct_count"],
            "cap_limited_incomplete_count": refined["cap_limited_incomplete_count"],
            "strict_wrong_numeric_count": refined["strict_wrong_numeric_count"],
            "default_switch_authorized": False,
        }
    return {
        "candidate": "T106B CC-DFlash-R2 Light GPU concise final-answer policy",
        "candidate_policy_name": T106B_POLICY_NAME,
        "strict_correct_count": t106b["strict_correct_count"],
        "cap_limited_incomplete_count": t106b["cap_limited_incomplete_count"],
        "strict_wrong_numeric_count": t106b["strict_wrong_numeric_count"],
        "default_switch_authorized": False,
    }


def _claim_update(interpretation: str, best_candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "allowed_claims": [
            "T107B tested a narrow GSM8K-only arithmetic-verification policy for optimized CC-DFlash-R2 Light GPU.",
            "The result may be compared to T106B only within the matched GSM8K n100 mnt256 optimized-condition setup.",
            "The selected GSM8K candidate may be described by measured strict, cap-limited, wrong-numeric, and runtime deltas.",
        ],
        "blocked_claims": [
            "Quality is fully solved.",
            "Optimized CC-DFlash becomes default.",
            "QMSum semantic risk is resolved.",
            "The policy generalizes beyond GSM8K.",
            "Full benchmark speed or quality closure is proven.",
            "References have been policy-fairly rerun.",
        ],
        "default_switch_claim": "blocked",
        "qmsum_claim_change": "none",
        "best_gsm8k_candidate_policy": best_candidate["candidate_policy_name"],
        "interpretation": interpretation,
    }


def _next_task_decision() -> dict[str, Any]:
    return {
        "next_task": "T108A — QMSum Targeted Recheck / Fix Feasibility",
        "reason": "After the GSM8K wrong-numeric branch, QMSum targeted recheck/fix feasibility is the next active Phase 2 question.",
        "automatic_default_switch": False,
        "automatic_full_matrix": False,
    }


def _comparison_rows(
    t105a: dict[str, Any],
    t106b: dict[str, Any],
    refined: dict[str, Any],
    baseline: dict[str, Any] | None,
    dflash: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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
        rows.append(
            {
                "metric": metric,
                "t105a_optimized": t105a.get(metric),
                "t106b_concise_final_answer": t106b.get(metric),
                "t107b_minimal_arithmetic_verify": refined.get(metric),
                "delta_t107b_minus_t106b": _delta(t106b, refined, metric),
                "t105a_baseline_ar_context": baseline.get(metric) if baseline else None,
                "t105a_dflash_r1_context": dflash.get(metric) if dflash else None,
            }
        )
    return rows


def analyze(
    t105a_jsonl: Path = DEFAULT_T105A_JSONL,
    t106b_jsonl: Path = DEFAULT_T106B_JSONL,
    refined_jsonl: Path = DEFAULT_REFINED_JSONL,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    expected_n: int = 100,
    baseline_jsonl: Path = DEFAULT_BASELINE_JSONL,
    dflash_jsonl: Path = DEFAULT_DFLASH_JSONL,
) -> dict[str, Any]:
    t105a_rows = load_jsonl(t105a_jsonl)
    t106b_rows = load_jsonl(t106b_jsonl)
    refined_rows = load_jsonl(refined_jsonl)
    t105a = _summarize_rows(t105a_rows, t105a_jsonl, "T105A CC-DFlash-R2 Light GPU optimized")
    t106b = _summarize_rows(t106b_rows, t106b_jsonl, "T106B CC-DFlash-R2 Light GPU concise")
    refined = _summarize_rows(refined_rows, refined_jsonl, "T107B CC-DFlash-R2 Light GPU minimal arithmetic verify")
    metadata = audit_metadata(refined_rows, expected_n)
    wrong_delta = _wrong_numeric_delta(t106b, refined)
    cap_delta = _cap_limited_delta(t106b, refined)
    runtime_delta = _runtime_delta(t105a, t106b, refined)
    interpretation = _interpretation(t106b, refined, metadata)
    decision = "PASS_WITH_CAVEAT" if metadata["valid"] else "PARTIAL"
    if refined["oom_or_cuda_failure"]:
        decision = "FAIL"
    best_candidate = _best_candidate(interpretation, t106b, refined)
    claim_update = _claim_update(interpretation, best_candidate)
    next_task = _next_task_decision()

    condition_metrics: dict[str, Any] = {
        "t105a_optimized_cc_dflash_r2_light_gpu": t105a,
        "t106b_concise_final_answer": t106b,
        "t107b_minimal_arithmetic_verify": refined,
    }
    baseline_summary = None
    dflash_summary = None
    if baseline_jsonl.exists():
        baseline_summary = _summarize_rows(load_jsonl(baseline_jsonl), baseline_jsonl, "T105A Baseline-AR context")
        condition_metrics["t105a_baseline_ar_context"] = baseline_summary
    if dflash_jsonl.exists():
        dflash_summary = _summarize_rows(load_jsonl(dflash_jsonl), dflash_jsonl, "T105A DFlash-R1 context")
        condition_metrics["t105a_dflash_r1_context"] = dflash_summary

    policy_comparison = {
        "t105a_optimized_artifact": str(t105a_jsonl),
        "t106b_concise_artifact": str(t106b_jsonl),
        "t107b_refined_artifact": str(refined_jsonl),
        "baseline_ar_context_artifact": str(baseline_jsonl) if baseline_jsonl.exists() else None,
        "dflash_r1_context_artifact": str(dflash_jsonl) if dflash_jsonl.exists() else None,
        "strict_correct_counts": {
            "t105a_optimized": t105a["strict_correct_count"],
            "t106b_concise": t106b["strict_correct_count"],
            "t107b_refined": refined["strict_correct_count"],
            "baseline_ar_context": baseline_summary["strict_correct_count"] if baseline_summary else None,
            "dflash_r1_context": dflash_summary["strict_correct_count"] if dflash_summary else None,
        },
        "cap_limited_counts": {
            "t105a_optimized": t105a["cap_limited_incomplete_count"],
            "t106b_concise": t106b["cap_limited_incomplete_count"],
            "t107b_refined": refined["cap_limited_incomplete_count"],
            "baseline_ar_context": baseline_summary["cap_limited_incomplete_count"] if baseline_summary else None,
            "dflash_r1_context": dflash_summary["cap_limited_incomplete_count"] if dflash_summary else None,
        },
        "strict_wrong_numeric_counts": {
            "t105a_optimized": t105a["strict_wrong_numeric_count"],
            "t106b_concise": t106b["strict_wrong_numeric_count"],
            "t107b_refined": refined["strict_wrong_numeric_count"],
            "baseline_ar_context": baseline_summary["strict_wrong_numeric_count"] if baseline_summary else None,
            "dflash_r1_context": dflash_summary["strict_wrong_numeric_count"] if dflash_summary else None,
        },
        "best_gsm8k_candidate": best_candidate,
        "policy_interpretation": interpretation,
    }

    summary = {
        "task": "T107B",
        "title": "Optional GSM8K Policy Refinement Fix",
        "decision": decision,
        "policy_interpretation": interpretation,
        "policy": {
            "policy_name": POLICY_NAME,
            "policy_suffix": POLICY_SUFFIX,
            "scope": "GSM8K-only runtime override for optimized CC-DFlash-R2 Light GPU",
            "default_behavior_changed": False,
        },
        "expected_n": expected_n,
        "condition_metrics": condition_metrics,
        "policy_comparison": policy_comparison,
        "wrong_numeric_delta": wrong_delta,
        "cap_limited_delta": cap_delta,
        "runtime_delta": runtime_delta,
        "metadata_audit": metadata,
        "best_gsm8k_candidate": best_candidate,
        "claim_update": claim_update,
        "next_task_decision": next_task,
        "scope_guard": {
            "no_qmsum": True,
            "no_full_matrix": True,
            "no_default_switch": True,
            "no_llm_judge": True,
            "no_human_scoring": True,
            "no_keep_rate_tuning": True,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "summary/task107b_fix_summary.json", summary)
    _write_json(output_dir / "summary/task107b_condition_metrics.json", condition_metrics)
    _write_json(output_dir / "summary/task107b_policy_comparison.json", policy_comparison)
    _write_json(output_dir / "summary/task107b_wrong_numeric_delta.json", wrong_delta)
    _write_json(output_dir / "summary/task107b_cap_limited_delta.json", cap_delta)
    _write_json(output_dir / "summary/task107b_runtime_delta.json", runtime_delta)
    _write_json(output_dir / "summary/task107b_metadata_audit.json", metadata)
    _write_json(output_dir / "summary/task107b_claim_update.json", claim_update)
    _write_json(output_dir / "summary/task107b_next_task_decision.json", next_task)
    _write_csv(
        output_dir / "tables/task107b_gsm8k_policy_refinement_comparison.csv",
        _comparison_rows(t105a, t106b, refined, baseline_summary, dflash_summary),
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze T107B GSM8K policy refinement result")
    parser.add_argument("--t105a-jsonl", type=Path, default=DEFAULT_T105A_JSONL)
    parser.add_argument("--t106b-jsonl", type=Path, default=DEFAULT_T106B_JSONL)
    parser.add_argument("--refined-jsonl", type=Path, default=DEFAULT_REFINED_JSONL)
    parser.add_argument("--baseline-jsonl", type=Path, default=DEFAULT_BASELINE_JSONL)
    parser.add_argument("--dflash-jsonl", type=Path, default=DEFAULT_DFLASH_JSONL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--expected-n", type=int, default=100)
    args = parser.parse_args()
    result = analyze(
        t105a_jsonl=args.t105a_jsonl,
        t106b_jsonl=args.t106b_jsonl,
        refined_jsonl=args.refined_jsonl,
        output_dir=args.output_dir,
        expected_n=args.expected_n,
        baseline_jsonl=args.baseline_jsonl,
        dflash_jsonl=args.dflash_jsonl,
    )
    comparison = result["policy_comparison"]
    print(f"status={result['decision']}")
    print(f"interpretation={result['policy_interpretation']}")
    print(f"strict={comparison['strict_correct_counts']['t106b_concise']}->{comparison['strict_correct_counts']['t107b_refined']}")
    print(f"wrong_numeric={comparison['strict_wrong_numeric_counts']['t106b_concise']}->{comparison['strict_wrong_numeric_counts']['t107b_refined']}")
    print(f"cap_limited={comparison['cap_limited_counts']['t106b_concise']}->{comparison['cap_limited_counts']['t107b_refined']}")
    print(f"best_candidate={result['best_gsm8k_candidate']['candidate_policy_name']}")
    print(f"next_task={result['next_task_decision']['next_task']}")
    print(f"wrote={args.output_dir}")


if __name__ == "__main__":
    main()
