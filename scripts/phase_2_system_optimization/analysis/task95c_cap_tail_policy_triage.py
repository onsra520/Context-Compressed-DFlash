from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_2_system_optimization.analysis import task95b_quality_proxy_calibration as t95b


DEFAULT_LARGE_128 = Path(
    "results/phase_2_system_optimization/compressor_comparison/"
    "task94_light_vs_large_compressor_controlled_comparison/runs/"
    "20260620_192758_cc_dflash_r2_large_n10.jsonl"
)
DEFAULT_LIGHT_128 = Path(
    "results/phase_2_system_optimization/compressor_comparison/"
    "task94_light_vs_large_compressor_controlled_comparison/runs/"
    "20260620_192904_cc_dflash_r2_light_n10.jsonl"
)
DEFAULT_SUMMARY_DIR = Path(
    "results/phase_2_system_optimization/quality_and_latency_audits/"
    "task95c_cap_tail_policy_triage/summary"
)
DEFAULT_TABLE_DIR = Path(
    "results/phase_2_system_optimization/quality_and_latency_audits/"
    "task95c_cap_tail_policy_triage/tables"
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
    return t95b.load_jsonl(path)


def _avg(values: list[Any]) -> float | None:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return round(mean(numeric), 6) if numeric else None


def _e2e_time(row: dict[str, Any]) -> float | None:
    value = row.get("e2e_time_s", row.get("end_to_end_time_s"))
    if isinstance(value, (int, float)):
        return float(value)
    generation = row.get("generation_time_s")
    t_compress_ms = row.get("t_compress_ms")
    if isinstance(generation, (int, float)) and isinstance(t_compress_ms, (int, float)):
        return float(generation) + float(t_compress_ms) / 1000.0
    return None


def _output_length(row: dict[str, Any]) -> int | None:
    text = row.get("generated_text")
    return len(text) if isinstance(text, str) else None


def _profile_key(profile: str, max_new_tokens_setting: int) -> str:
    return f"{profile}_{max_new_tokens_setting}"


def _count(labels: list[dict[str, Any]], label: str) -> int:
    return sum(1 for row in labels if row.get("calibrated_label") == label)


def _metadata_sanity(rows: list[dict[str, Any]], *, profile: str, max_new_tokens_setting: int) -> dict[str, Any]:
    wrong_profile = 0
    wrong_max_new_tokens = 0
    missing_profile = 0
    missing_local_only = 0
    missing_compressor_path = 0
    missing_resolved_path = 0
    keep_rates: set[Any] = set()
    conditions: set[Any] = set()

    for row in rows:
        row_profile = row.get("compressor_profile")
        if row_profile in (None, ""):
            missing_profile += 1
        elif row_profile != profile:
            wrong_profile += 1
        if row.get("max_new_tokens") != max_new_tokens_setting:
            wrong_max_new_tokens += 1
        if row.get("local_files_only") is not True:
            missing_local_only += 1
        if not row.get("compressor_path"):
            missing_compressor_path += 1
        if not row.get("resolved_compressor_path"):
            missing_resolved_path += 1
        if row.get("keep_rate") not in (None, ""):
            keep_rates.add(row.get("keep_rate"))
        if row.get("condition") not in (None, ""):
            conditions.add(row.get("condition"))

    return {
        "expected_profile": profile,
        "expected_max_new_tokens": max_new_tokens_setting,
        "rows_wrong_compressor_profile": wrong_profile,
        "rows_wrong_max_new_tokens": wrong_max_new_tokens,
        "rows_missing_compressor_profile": missing_profile,
        "rows_missing_or_false_local_files_only": missing_local_only,
        "rows_missing_compressor_path": missing_compressor_path,
        "rows_missing_resolved_compressor_path": missing_resolved_path,
        "observed_keep_rates": sorted(str(value) for value in keep_rates),
        "observed_conditions": sorted(str(value) for value in conditions),
        "metadata_ok": (
            wrong_profile == 0
            and wrong_max_new_tokens == 0
            and missing_profile == 0
            and missing_local_only == 0
            and missing_compressor_path == 0
            and missing_resolved_path == 0
        ),
    }


def summarize_artifact(path: Path, *, profile: str, max_new_tokens_setting: int) -> dict[str, Any]:
    rows = load_jsonl(path)
    labels = [
        t95b.calibrate_row(row, profile=profile, row_index=index, artifact=path)
        for index, row in enumerate(rows, start=1)
    ]
    label_counts = {label: _count(labels, label) for label in LABELS}
    output_lengths = [_output_length(row) for row in rows]
    key = _profile_key(profile, max_new_tokens_setting)
    return {
        "key": key,
        "profile": profile,
        "max_new_tokens": max_new_tokens_setting,
        "artifact": str(path),
        "row_count": len(rows),
        "avg_t_compress_ms": _avg([row.get("t_compress_ms") for row in rows]),
        "avg_R_actual": _avg([row.get("R_actual", row.get("actual_compression_ratio")) for row in rows]),
        "avg_e2e_time_s": _avg([_e2e_time(row) for row in rows]),
        "avg_tokens_per_second": _avg([row.get("tokens_per_second", row.get("tok_per_sec")) for row in rows]),
        "avg_tau_mean": _avg([row.get("tau_mean") for row in rows]),
        "strict_correct_count": sum(1 for row in labels if row["strict_correct"]),
        "cap_limited_incomplete_count": label_counts["cap_limited_incomplete"],
        "strict_wrong_numeric_count": label_counts["strict_wrong_numeric"],
        "final_answer_marker_count": sum(1 for row in labels if row["final_answer_marker_present"]),
        "exact_containment_count": sum(1 for row in labels if row["exact_containment"]),
        "invalid_or_empty_output_count": sum(
            1 for row in rows if not isinstance(row.get("generated_text"), str) or not row.get("generated_text", "").strip()
        ),
        "avg_output_length_chars": _avg(output_lengths),
        "calibrated_label_counts": label_counts,
        "compressor_metadata_sanity": _metadata_sanity(
            rows,
            profile=profile,
            max_new_tokens_setting=max_new_tokens_setting,
        ),
        "labels": labels,
    }


def _delta(after: dict[str, Any], before: dict[str, Any], field: str) -> float | int | None:
    left = after.get(field)
    right = before.get(field)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        value = left - right
        return round(value, 6) if isinstance(value, float) else value
    return None


def _comparison(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    field_names = {
        "strict_correct_count": "strict_correct_delta",
        "cap_limited_incomplete_count": "cap_limited_incomplete_delta",
        "strict_wrong_numeric_count": "strict_wrong_numeric_delta",
        "final_answer_marker_count": "final_answer_marker_delta",
        "avg_t_compress_ms": "avg_t_compress_ms_delta",
        "avg_R_actual": "avg_R_actual_delta",
        "avg_e2e_time_s": "avg_e2e_time_s_delta",
        "avg_tokens_per_second": "avg_tokens_per_second_delta",
        "avg_tau_mean": "avg_tau_mean_delta",
        "avg_output_length_chars": "avg_output_length_chars_delta",
    }
    return {output_key: _delta(after, before, field) for field, output_key in field_names.items()}


def _row_id(row: dict[str, Any]) -> Any:
    return row.get("fixture_id") or row.get("dataset_id") or row.get("prompt_id") or row.get("row_index")


def build_row_delta_analysis(profiles: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    labels_by_key = {
        key: {_row_id(label): label for label in summary["labels"]}
        for key, summary in profiles.items()
    }
    all_ids = sorted({row_id for labels in labels_by_key.values() for row_id in labels}, key=str)
    for row_id in all_ids:
        item: dict[str, Any] = {"row_id": row_id}
        for key, labels in labels_by_key.items():
            label = labels.get(row_id)
            if label is None:
                item[f"{key}_label"] = None
                item[f"{key}_strict_correct"] = None
                item[f"{key}_cap_limited"] = None
                item[f"{key}_final_marker"] = None
                continue
            item[f"{key}_label"] = label["calibrated_label"]
            item[f"{key}_strict_correct"] = label["strict_correct"]
            item[f"{key}_cap_limited"] = label["calibrated_label"] == "cap_limited_incomplete"
            item[f"{key}_final_marker"] = label["final_answer_marker_present"]
        rows.append(item)
    return rows


def build_recommendation(
    summary: dict[str, Any],
    *,
    runs_complete: bool,
    analyzer_complete: bool,
    gpu_blocked: bool = False,
) -> dict[str, Any]:
    if gpu_blocked or not runs_complete:
        return {
            "decision": "PARTIAL",
            "reason": "GPU/run gate blocked before Task95C mnt256 benchmark execution.",
            "gpu_blocked": bool(gpu_blocked),
            "runs_complete": bool(runs_complete),
            "analyzer_complete": bool(analyzer_complete),
            "n30_recommended_now": False,
            "keep_rate_tuning_in_this_task": False,
            "next_task": "restore_gpu_then_rerun_bounded_T95C_only",
        }
    if not analyzer_complete:
        return {
            "decision": "PARTIAL",
            "reason": "Benchmark rows exist but analyzer did not complete safely.",
            "gpu_blocked": False,
            "runs_complete": True,
            "analyzer_complete": False,
            "n30_recommended_now": False,
            "keep_rate_tuning_in_this_task": False,
            "next_task": "repair_Task95C_analyzer_before_any_larger_run",
        }

    profiles = summary.get("profiles", {})
    comparisons = summary.get("comparisons", {})
    large256 = profiles.get("large_256", {})
    light256 = profiles.get("light_256", {})
    light_delta = comparisons.get("light_128_vs_256", {})
    light_quality_gap = large256.get("strict_correct_count", 0) - light256.get("strict_correct_count", 0)
    light_improved = light_delta.get("strict_correct_delta", 0) > 0
    cap_reduced = light_delta.get("cap_limited_incomplete_delta", 0) < 0
    e2e_delta = light_delta.get("avg_e2e_time_s_delta")
    e2e_cost_large = isinstance(e2e_delta, (int, float)) and e2e_delta > 0.75
    light_tcompress_advantage = (
        isinstance(large256.get("avg_t_compress_ms"), (int, float))
        and isinstance(light256.get("avg_t_compress_ms"), (int, float))
        and light256["avg_t_compress_ms"] < large256["avg_t_compress_ms"]
    )

    if light_improved and cap_reduced and light_quality_gap <= 1 and not e2e_cost_large:
        next_task = "bounded_confirmation_only"
        rationale = "mnt256 strongly improved light and reduced cap-limited rows; confirm boundedly before n=30."
    elif cap_reduced and light_quality_gap > 1:
        next_task = "T95D_or_T96_keep_rate_tail_policy_triage"
        rationale = "mnt256 reduced cap pressure but light strict correctness remains meaningfully worse."
    elif e2e_cost_large and light_quality_gap > 0:
        next_task = "stop_light_default_or_tune_policy_before_larger_runs"
        rationale = "mnt256 increased e2e cost while light quality remains weak."
    else:
        next_task = "T95D_or_T96_keep_rate_tail_policy_triage"
        rationale = "mnt256 did not clearly repair the light-quality gap."

    return {
        "decision": "PASS_WITH_CAVEAT",
        "reason": rationale,
        "gpu_blocked": False,
        "runs_complete": True,
        "analyzer_complete": True,
        "n30_recommended_now": False,
        "keep_rate_tuning_in_this_task": False,
        "next_task": next_task,
        "light_quality_gap_large256_minus_light256": light_quality_gap,
        "light_strict_correct_improved": bool(light_improved),
        "light_cap_limited_reduced": bool(cap_reduced),
        "light_tcompress_advantage_remains": bool(light_tcompress_advantage),
    }


def _table_rows(profiles: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("large_128", "light_128", "large_256", "light_256"):
        summary = profiles[key]
        rows.append(
            {
                "setting": key,
                "profile": summary["profile"],
                "max_new_tokens": summary["max_new_tokens"],
                "row_count": summary["row_count"],
                "strict_correct_count": summary["strict_correct_count"],
                "cap_limited_incomplete_count": summary["cap_limited_incomplete_count"],
                "strict_wrong_numeric_count": summary["strict_wrong_numeric_count"],
                "final_answer_marker_count": summary["final_answer_marker_count"],
                "exact_containment_count": summary["exact_containment_count"],
                "avg_t_compress_ms": summary["avg_t_compress_ms"],
                "avg_R_actual": summary["avg_R_actual"],
                "avg_e2e_time_s": summary["avg_e2e_time_s"],
                "avg_tokens_per_second": summary["avg_tokens_per_second"],
                "avg_tau_mean": summary["avg_tau_mean"],
                "avg_output_length_chars": summary["avg_output_length_chars"],
                "metadata_ok": summary["compressor_metadata_sanity"]["metadata_ok"],
                "artifact": summary["artifact"],
            }
        )
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = sorted({field for row in rows for field in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def analyze(
    large128_jsonl: Path,
    light128_jsonl: Path,
    large256_jsonl: Path,
    light256_jsonl: Path,
    summary_dir: Path,
    table_dir: Path,
) -> dict[str, Any]:
    profiles = {
        "large_128": summarize_artifact(large128_jsonl, profile="large", max_new_tokens_setting=128),
        "light_128": summarize_artifact(light128_jsonl, profile="light", max_new_tokens_setting=128),
        "large_256": summarize_artifact(large256_jsonl, profile="large", max_new_tokens_setting=256),
        "light_256": summarize_artifact(light256_jsonl, profile="light", max_new_tokens_setting=256),
    }
    comparisons = {
        "large_128_vs_256": _comparison(profiles["large_128"], profiles["large_256"]),
        "light_128_vs_256": _comparison(profiles["light_128"], profiles["light_256"]),
        "large_256_vs_light_256": _comparison(profiles["large_256"], profiles["light_256"]),
    }
    row_deltas = build_row_delta_analysis(profiles)

    serializable_profiles = {
        key: {k: v for k, v in value.items() if k != "labels"}
        for key, value in profiles.items()
    }
    summary = {
        "task": "Task95C",
        "title": "Cap/Tail Policy Triage",
        "method": {
            "condition": "CC-DFlash-R2",
            "dataset": "gsm8k_short",
            "seed": 42,
            "n": 10,
            "only_changed_max_new_tokens": "128_to_256",
            "keep_rate_tuning": False,
            "n30_run": False,
            "n100_run": False,
            "llm_judge": False,
            "model_loading_in_analyzer": False,
            "strict_policy_source": "Task95B calibrated policy",
        },
        "profiles": serializable_profiles,
        "comparisons": comparisons,
        "claim_boundary": {
            "no_final_speedup_claim": True,
            "no_final_quality_claim": True,
            "no_deployment_or_8gb_claim": True,
            "no_qmsum_semantic_correctness_claim": True,
            "no_full_benchmark_claim": True,
            "deterministic_proxy_only": True,
        },
    }
    recommendation = build_recommendation(summary, runs_complete=True, analyzer_complete=True)
    summary["recommendation"] = recommendation

    _write_json(summary_dir / "task95c_cap_tail_summary.json", summary)
    _write_jsonl(summary_dir / "task95c_row_delta_analysis.jsonl", row_deltas)
    _write_json(summary_dir / "task95c_recommendation.json", recommendation)
    _write_csv(table_dir / "task95c_cap_tail_table.csv", _table_rows(profiles))
    return summary


def write_blocked_outputs(
    summary_dir: Path,
    table_dir: Path,
    *,
    static_audit: dict[str, Any],
    gpu_gate: dict[str, Any],
) -> dict[str, Any]:
    recommendation = build_recommendation({}, runs_complete=False, analyzer_complete=False, gpu_blocked=True)
    summary = {
        "task": "Task95C",
        "title": "Cap/Tail Policy Triage",
        "decision": "PARTIAL",
        "blocked_reason": "GPU unavailable before bounded mnt256 benchmark execution.",
        "static_cap_audit": static_audit,
        "gpu_gate": gpu_gate,
        "recommendation": recommendation,
        "claim_boundary": {
            "no_final_speedup_claim": True,
            "no_final_quality_claim": True,
            "no_deployment_or_8gb_claim": True,
            "no_qmsum_semantic_correctness_claim": True,
            "no_full_benchmark_claim": True,
            "no_n30_or_n100_run": True,
        },
    }
    _write_json(summary_dir / "task95c_cap_tail_summary.json", summary)
    _write_json(summary_dir / "task95c_recommendation.json", recommendation)
    _write_jsonl(summary_dir / "task95c_row_delta_analysis.jsonl", [])
    _write_csv(table_dir / "task95c_cap_tail_table.csv", [{"decision": "PARTIAL", "reason": summary["blocked_reason"]}])
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task95C cap/tail policy triage artifacts")
    parser.add_argument("--large128-jsonl", type=Path, default=DEFAULT_LARGE_128)
    parser.add_argument("--light128-jsonl", type=Path, default=DEFAULT_LIGHT_128)
    parser.add_argument("--large256-jsonl", type=Path, required=True)
    parser.add_argument("--light256-jsonl", type=Path, required=True)
    parser.add_argument("--summary-dir", type=Path, default=DEFAULT_SUMMARY_DIR)
    parser.add_argument("--table-dir", type=Path, default=DEFAULT_TABLE_DIR)
    args = parser.parse_args()

    summary = analyze(
        args.large128_jsonl,
        args.light128_jsonl,
        args.large256_jsonl,
        args.light256_jsonl,
        args.summary_dir,
        args.table_dir,
    )
    recommendation = summary["recommendation"]
    print(f"status={recommendation['decision']}")
    print(f"n30_recommended_now={recommendation['n30_recommended_now']}")
    print(f"next_task={recommendation['next_task']}")
    print(f"wrote_summary={args.summary_dir / 'task95c_cap_tail_summary.json'}")
    print(f"wrote_table={args.table_dir / 'task95c_cap_tail_table.csv'}")


if __name__ == "__main__":
    main()
