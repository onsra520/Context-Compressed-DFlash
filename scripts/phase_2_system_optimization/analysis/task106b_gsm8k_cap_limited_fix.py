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


DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix"
)
DEFAULT_BEFORE_JSONL = Path(
    "results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/"
    "runs/cc_dflash_r2_light_gpu_gsm8k_short_seed42_n100_mnt256.jsonl"
)
DEFAULT_FIXED_JSONL = DEFAULT_OUTPUT_DIR / (
    "runs/cc_dflash_r2_light_gpu_gsm8k_seed42_n100_mnt256_concise_final_answer.jsonl"
)
DEFAULT_BASELINE_JSONL = Path(
    "results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/"
    "runs/baseline_ar_gsm8k_short_seed42_n100_mnt256.jsonl"
)
DEFAULT_DFLASH_JSONL = Path(
    "results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/"
    "runs/dflash_r1_gsm8k_short_seed42_n100_mnt256.jsonl"
)

POLICY_NAME = "gsm8k_concise_final_answer_v1"
OUTPUT_RELATIVE_PATHS = (
    "summary/task106b_fix_summary.json",
    "summary/task106b_condition_metrics.json",
    "summary/task106b_before_after_comparison.json",
    "summary/task106b_cap_limited_delta.json",
    "summary/task106b_quality_proxy_delta.json",
    "summary/task106b_runtime_delta.json",
    "summary/task106b_metadata_audit.json",
    "summary/task106b_claim_update.json",
    "summary/task106b_next_task_decision.json",
    "tables/task106b_gsm8k_cap_limited_fix_comparison.csv",
)
LABELS = (
    "strict_correct",
    "strict_wrong_numeric",
    "cap_limited_incomplete",
    "format_or_extraction_sensitive",
    "answer_missing",
    "proxy_uncertain",
)


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
    if not rows:
        rows = [{"metric": "", "before": "", "fixed": "", "delta": ""}]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
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
    for key in ("fixture_id", "dataset_id", "sample_id", "id", "question_id"):
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
        "answer_missing_count": label_counts["answer_missing"],
        "proxy_uncertain_count": label_counts["proxy_uncertain"],
        "format_or_extraction_sensitive_count": label_counts["format_or_extraction_sensitive"],
        "final_answer_marker_count": sum(1 for item in calibrated if item["final_answer_marker_present"]),
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
            errors.append(f"{prefix}: gsm8k answer policy type mismatch")
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
        "policy_override_rows": sum(1 for row in rows if row.get("gsm8k_policy_suffix_override") is True),
        "policy_preserved_rows": sum(1 for row in rows if row.get("gsm8k_answer_policy_preserved") is True),
        "failure_flags": flags,
    }


def _delta(before: dict[str, Any], fixed: dict[str, Any], field: str) -> float | int | None:
    left = before.get(field)
    right = fixed.get(field)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        value = right - left
        if isinstance(left, int) and isinstance(right, int):
            return int(value)
        return round(float(value), 6)
    return None


def _cap_delta(before: dict[str, Any], fixed: dict[str, Any]) -> dict[str, Any]:
    before_ids = set(before["cap_limited_fixture_ids"])
    fixed_ids = set(fixed["cap_limited_fixture_ids"])
    return {
        "before_cap_limited_count": before["cap_limited_incomplete_count"],
        "fixed_cap_limited_count": fixed["cap_limited_incomplete_count"],
        "cap_limited_delta": _delta(before, fixed, "cap_limited_incomplete_count"),
        "resolved_cap_limited_ids": sorted(before_ids - fixed_ids),
        "new_cap_limited_ids": sorted(fixed_ids - before_ids),
        "persistent_cap_limited_ids": sorted(before_ids & fixed_ids),
    }


def _quality_delta(before: dict[str, Any], fixed: dict[str, Any]) -> dict[str, Any]:
    return {
        "before_strict_correct_count": before["strict_correct_count"],
        "fixed_strict_correct_count": fixed["strict_correct_count"],
        "strict_correct_delta": _delta(before, fixed, "strict_correct_count"),
        "before_strict_wrong_numeric_count": before["strict_wrong_numeric_count"],
        "fixed_strict_wrong_numeric_count": fixed["strict_wrong_numeric_count"],
        "strict_wrong_numeric_delta": _delta(before, fixed, "strict_wrong_numeric_count"),
        "before_answer_missing_count": before["answer_missing_count"],
        "fixed_answer_missing_count": fixed["answer_missing_count"],
        "answer_missing_delta": _delta(before, fixed, "answer_missing_count"),
        "before_final_answer_marker_count": before["final_answer_marker_count"],
        "fixed_final_answer_marker_count": fixed["final_answer_marker_count"],
        "final_answer_marker_delta": _delta(before, fixed, "final_answer_marker_count"),
    }


def _runtime_delta(before: dict[str, Any], fixed: dict[str, Any]) -> dict[str, Any]:
    avg_e2e_delta = _delta(before, fixed, "avg_e2e_time_s")
    e2e_regression_rate = None
    if isinstance(avg_e2e_delta, (int, float)) and isinstance(before.get("avg_e2e_time_s"), (int, float)):
        e2e_regression_rate = round(avg_e2e_delta / before["avg_e2e_time_s"], 6)
    return {
        "before_avg_e2e_time_s": before["avg_e2e_time_s"],
        "fixed_avg_e2e_time_s": fixed["avg_e2e_time_s"],
        "avg_e2e_time_s_delta": avg_e2e_delta,
        "avg_e2e_regression_rate": e2e_regression_rate,
        "before_avg_t_compress_ms": before["avg_t_compress_ms"],
        "fixed_avg_t_compress_ms": fixed["avg_t_compress_ms"],
        "avg_t_compress_ms_delta": _delta(before, fixed, "avg_t_compress_ms"),
        "before_avg_tokens_per_second": before["avg_tokens_per_second"],
        "fixed_avg_tokens_per_second": fixed["avg_tokens_per_second"],
        "avg_tokens_per_second_delta": _delta(before, fixed, "avg_tokens_per_second"),
        "before_max_vram_reserved_gib": before["max_vram_reserved_gib"],
        "fixed_max_vram_reserved_gib": fixed["max_vram_reserved_gib"],
        "max_vram_reserved_gib_delta": _delta(before, fixed, "max_vram_reserved_gib"),
    }


def _interpretation(cap_delta: dict[str, Any], quality_delta: dict[str, Any], runtime_delta: dict[str, Any]) -> str:
    cap_improved = cap_delta["fixed_cap_limited_count"] < cap_delta["before_cap_limited_count"]
    strict_improved = quality_delta["fixed_strict_correct_count"] > quality_delta["before_strict_correct_count"]
    e2e_regression_rate = runtime_delta.get("avg_e2e_regression_rate")
    large_e2e_regression = isinstance(e2e_regression_rate, (int, float)) and e2e_regression_rate > 0.10
    if cap_improved and strict_improved and not large_e2e_regression:
        return "cap_fix_supported_with_caveat"
    if cap_improved and not strict_improved:
        return "cap_fix_mixed_proxy_no_strict_gain"
    if strict_improved and large_e2e_regression:
        return "quality_speed_tradeoff"
    if not cap_improved and not strict_improved:
        return "fix_not_supported"
    return "mixed_result_preserve_caveat"


def _claim_update(interpretation: str) -> dict[str, Any]:
    return {
        "allowed_claims": [
            "T106B tested a narrow GSM8K final-answer/cap-limited fix for optimized CC-DFlash-R2 Light GPU.",
            "The fix result is limited to the matched GSM8K n100 setup.",
            "The fix may be described only by its measured cap-limited, strict-proxy, and runtime deltas.",
        ],
        "blocked_claims": [
            "Quality is fully preserved.",
            "Optimized CC-DFlash becomes default.",
            "Full benchmark speed claim is closed.",
            "QMSum semantic risk is resolved.",
            "The fix generalizes beyond GSM8K n100.",
        ],
        "quality_preserved_claim": "blocked",
        "default_switch_claim": "blocked",
        "qmsum_claim_change": "none",
        "interpretation": interpretation,
    }


def _next_task_decision() -> dict[str, Any]:
    return {
        "next_task": "T106C — Optimized Default Candidate Decision",
        "reason": "T106B is an optional narrow fix test; default-candidate language must be decided separately.",
        "automatic_default_switch": False,
    }


def _comparison_rows(before: dict[str, Any], fixed: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for metric in (
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
    ):
        rows.append(
            {
                "metric": metric,
                "before": before.get(metric),
                "fixed": fixed.get(metric),
                "delta": _delta(before, fixed, metric),
            }
        )
    return rows


def analyze(
    before_jsonl: Path = DEFAULT_BEFORE_JSONL,
    fixed_jsonl: Path = DEFAULT_FIXED_JSONL,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    expected_n: int = 100,
    baseline_jsonl: Path = DEFAULT_BASELINE_JSONL,
    dflash_jsonl: Path = DEFAULT_DFLASH_JSONL,
) -> dict[str, Any]:
    before_rows = load_jsonl(before_jsonl)
    fixed_rows = load_jsonl(fixed_jsonl)
    before = _summarize_rows(before_rows, before_jsonl, "T105A CC-DFlash-R2 Light GPU")
    fixed = _summarize_rows(fixed_rows, fixed_jsonl, "T106B CC-DFlash-R2 Light GPU Fixed")
    metadata = audit_metadata(fixed_rows, expected_n)
    cap_limited_delta = _cap_delta(before, fixed)
    quality_proxy_delta = _quality_delta(before, fixed)
    runtime_delta = _runtime_delta(before, fixed)
    interpretation = _interpretation(cap_limited_delta, quality_proxy_delta, runtime_delta)
    decision = "PASS_WITH_CAVEAT" if metadata["valid"] else "PARTIAL"
    if fixed["oom_or_cuda_failure"]:
        decision = "FAIL"
    claim_update = _claim_update(interpretation)
    next_task = _next_task_decision()

    condition_metrics: dict[str, Any] = {
        "before_t105a_cc_dflash_r2_light_gpu": before,
        "fixed_t106b_cc_dflash_r2_light_gpu": fixed,
    }
    for label, path in (("t105a_baseline_ar_context", baseline_jsonl), ("t105a_dflash_r1_context", dflash_jsonl)):
        if path.exists():
            condition_metrics[label] = _summarize_rows(load_jsonl(path), path, label)

    before_after = {
        "before_artifact": str(before_jsonl),
        "fixed_artifact": str(fixed_jsonl),
        "cap_limited_delta": cap_limited_delta,
        "quality_proxy_delta": quality_proxy_delta,
        "runtime_delta": runtime_delta,
        "fix_interpretation": interpretation,
    }
    summary = {
        "task": "T106B",
        "title": "Optional GSM8K Cap-Limited Fix",
        "decision": decision,
        "fix_interpretation": interpretation,
        "policy": {
            "policy_name": POLICY_NAME,
            "scope": "GSM8K-only runtime override for CC-DFlash-R2",
            "default_behavior_changed": False,
        },
        "expected_n": expected_n,
        "condition_metrics": condition_metrics,
        "before_after_comparison": before_after,
        "cap_limited_delta": cap_limited_delta,
        "quality_proxy_delta": quality_proxy_delta,
        "runtime_delta": runtime_delta,
        "metadata_audit": metadata,
        "claim_update": claim_update,
        "next_task_decision": next_task,
        "scope_guard": {
            "no_qmsum": True,
            "no_full_matrix": True,
            "no_default_switch": True,
            "no_llm_judge": True,
            "no_human_scoring": True,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "summary/task106b_fix_summary.json", summary)
    _write_json(output_dir / "summary/task106b_condition_metrics.json", condition_metrics)
    _write_json(output_dir / "summary/task106b_before_after_comparison.json", before_after)
    _write_json(output_dir / "summary/task106b_cap_limited_delta.json", cap_limited_delta)
    _write_json(output_dir / "summary/task106b_quality_proxy_delta.json", quality_proxy_delta)
    _write_json(output_dir / "summary/task106b_runtime_delta.json", runtime_delta)
    _write_json(output_dir / "summary/task106b_metadata_audit.json", metadata)
    _write_json(output_dir / "summary/task106b_claim_update.json", claim_update)
    _write_json(output_dir / "summary/task106b_next_task_decision.json", next_task)
    _write_csv(output_dir / "tables/task106b_gsm8k_cap_limited_fix_comparison.csv", _comparison_rows(before, fixed))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze T106B GSM8K cap-limited fix result")
    parser.add_argument("--before-jsonl", type=Path, default=DEFAULT_BEFORE_JSONL)
    parser.add_argument("--fixed-jsonl", type=Path, default=DEFAULT_FIXED_JSONL)
    parser.add_argument("--baseline-jsonl", type=Path, default=DEFAULT_BASELINE_JSONL)
    parser.add_argument("--dflash-jsonl", type=Path, default=DEFAULT_DFLASH_JSONL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--expected-n", type=int, default=100)
    args = parser.parse_args()
    result = analyze(
        before_jsonl=args.before_jsonl,
        fixed_jsonl=args.fixed_jsonl,
        output_dir=args.output_dir,
        expected_n=args.expected_n,
        baseline_jsonl=args.baseline_jsonl,
        dflash_jsonl=args.dflash_jsonl,
    )
    cap = result["cap_limited_delta"]
    quality = result["quality_proxy_delta"]
    print(f"status={result['decision']}")
    print(f"interpretation={result['fix_interpretation']}")
    print(f"cap_limited={cap['before_cap_limited_count']}->{cap['fixed_cap_limited_count']}")
    print(f"strict={quality['before_strict_correct_count']}->{quality['fixed_strict_correct_count']}")
    print(f"next_task={result['next_task_decision']['next_task']}")
    print(f"wrote={args.output_dir}")


if __name__ == "__main__":
    main()
