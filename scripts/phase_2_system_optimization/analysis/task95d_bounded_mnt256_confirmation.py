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


DEFAULT_PREVIOUS_LARGE = Path(
    "results/phase_2_system_optimization/quality_and_latency_audits/"
    "task95c_cap_tail_policy_triage/resume_mnt256/runs/"
    "20260621_024734_cc_dflash_r2_large_n10_mnt256.jsonl"
)
DEFAULT_PREVIOUS_LIGHT = Path(
    "results/phase_2_system_optimization/quality_and_latency_audits/"
    "task95c_cap_tail_policy_triage/resume_mnt256/runs/"
    "20260621_024839_cc_dflash_r2_light_n10_mnt256.jsonl"
)
DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/quality_and_latency_audits/"
    "task95d_bounded_mnt256_confirmation"
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


def _row_id(row: dict[str, Any]) -> Any:
    return row.get("fixture_id") or row.get("dataset_id") or row.get("prompt_id") or row.get("row_index")


def _output_length(row: dict[str, Any]) -> int | None:
    text = row.get("generated_text")
    return len(text) if isinstance(text, str) else None


def _count(labels: list[dict[str, Any]], label: str) -> int:
    return sum(1 for row in labels if row.get("calibrated_label") == label)


def _metadata_sanity(rows: list[dict[str, Any]], *, profile: str, seed: int) -> dict[str, Any]:
    wrong_profile = 0
    wrong_max_new_tokens = 0
    missing_profile = 0
    missing_local_only = 0
    missing_compressor_path = 0
    missing_resolved_path = 0
    observed_seeds: set[Any] = set()
    observed_keep_rates: set[Any] = set()
    observed_conditions: set[Any] = set()

    for row in rows:
        row_profile = row.get("compressor_profile")
        if row_profile in (None, ""):
            missing_profile += 1
        elif row_profile != profile:
            wrong_profile += 1
        if row.get("max_new_tokens") != 256:
            wrong_max_new_tokens += 1
        if row.get("local_files_only") is not True:
            missing_local_only += 1
        if not row.get("compressor_path"):
            missing_compressor_path += 1
        if not row.get("resolved_compressor_path"):
            missing_resolved_path += 1
        if row.get("seed") not in (None, ""):
            observed_seeds.add(row.get("seed"))
        if row.get("keep_rate") not in (None, ""):
            observed_keep_rates.add(row.get("keep_rate"))
        if row.get("condition") not in (None, ""):
            observed_conditions.add(row.get("condition"))

    seed_ok = not observed_seeds or observed_seeds == {seed}
    metadata_ok = (
        wrong_profile == 0
        and wrong_max_new_tokens == 0
        and missing_profile == 0
        and missing_local_only == 0
        and missing_compressor_path == 0
        and missing_resolved_path == 0
        and seed_ok
    )
    return {
        "expected_profile": profile,
        "expected_seed": seed,
        "expected_max_new_tokens": 256,
        "rows_wrong_compressor_profile": wrong_profile,
        "rows_wrong_max_new_tokens": wrong_max_new_tokens,
        "rows_missing_compressor_profile": missing_profile,
        "rows_missing_or_false_local_files_only": missing_local_only,
        "rows_missing_compressor_path": missing_compressor_path,
        "rows_missing_resolved_compressor_path": missing_resolved_path,
        "observed_seeds": sorted(str(value) for value in observed_seeds),
        "observed_keep_rates": sorted(str(value) for value in observed_keep_rates),
        "observed_conditions": sorted(str(value) for value in observed_conditions),
        "metadata_ok": metadata_ok,
    }


def summarize_artifact(path: Path, *, profile: str, seed: int) -> dict[str, Any]:
    rows = load_jsonl(path)
    labels = [
        t95b.calibrate_row(row, profile=profile, row_index=index, artifact=path)
        for index, row in enumerate(rows, start=1)
    ]
    label_counts = {label: _count(labels, label) for label in LABELS}
    output_lengths = [_output_length(row) for row in rows]
    return {
        "profile": profile,
        "seed": seed,
        "max_new_tokens": 256,
        "artifact": str(path),
        "row_count": len(rows),
        "fixture_ids": [str(_row_id(row)) for row in rows],
        "avg_t_compress_ms": _avg([row.get("t_compress_ms") for row in rows]),
        "avg_R_actual": _avg([row.get("R_actual", row.get("actual_compression_ratio")) for row in rows]),
        "avg_e2e_time_s": _avg([_e2e_time(row) for row in rows]),
        "avg_tokens_per_second": _avg([row.get("tokens_per_second", row.get("tok_per_sec")) for row in rows]),
        "avg_tau_mean": _avg([row.get("tau_mean") for row in rows]),
        "avg_output_length_chars": _avg(output_lengths),
        "strict_correct_count": sum(1 for row in labels if row["strict_correct"]),
        "cap_limited_incomplete_count": label_counts["cap_limited_incomplete"],
        "strict_wrong_numeric_count": label_counts["strict_wrong_numeric"],
        "final_answer_marker_count": sum(1 for row in labels if row["final_answer_marker_present"]),
        "exact_containment_count": sum(1 for row in labels if row["exact_containment"]),
        "invalid_or_empty_output_count": sum(
            1 for row in rows if not isinstance(row.get("generated_text"), str) or not row.get("generated_text", "").strip()
        ),
        "calibrated_label_counts": label_counts,
        "metadata_sanity": _metadata_sanity(rows, profile=profile, seed=seed),
        "labels": labels,
    }


def fixture_overlap(previous: dict[str, Any], confirmation: dict[str, Any]) -> dict[str, Any]:
    previous_ids = set(previous.get("fixture_ids", []))
    confirmation_ids = set(confirmation.get("fixture_ids", []))
    overlap = sorted(previous_ids & confirmation_ids)
    duplicate_sample = bool(previous_ids) and previous_ids == confirmation_ids
    return {
        "previous_count": len(previous_ids),
        "confirmation_count": len(confirmation_ids),
        "overlap_count": len(overlap),
        "overlap_ids": overlap,
        "duplicate_sample": duplicate_sample,
        "independent_confirmation_sample": not duplicate_sample and len(overlap) == 0,
    }


def _delta(after: dict[str, Any], before: dict[str, Any], field: str) -> float | int | None:
    left = after.get(field)
    right = before.get(field)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        value = left - right
        return round(value, 6) if isinstance(value, float) else value
    return None


def _comparison(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    fields = {
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
    return {output: _delta(right, left, field) for field, output in fields.items()}


def build_recommendation(summary: dict[str, Any]) -> dict[str, Any]:
    overlap = summary.get("fixture_overlap", {})
    profiles = summary.get("profiles", {})
    large = profiles.get("seed43_large_256", {})
    light = profiles.get("seed43_light_256", {})
    comparison = summary.get("comparisons", {}).get("seed43_large_vs_light_256", {})

    if overlap.get("duplicate_sample"):
        return {
            "decision": "PARTIAL",
            "reason_code": "BLOCKED_DUPLICATE_SAMPLE",
            "reason": "Seed43 repeated the seed42 fixture set, so this is not an independent confirmation.",
            "n30_recommended_now": False,
            "keep_rate_tuning_in_this_task": False,
            "next_task": "add_or_select_supported_sample_offset",
        }

    metadata_ok = bool(summary.get("metadata_ok"))
    runs_complete = large.get("row_count") == 10 and light.get("row_count") == 10
    if not runs_complete:
        return {
            "decision": "PARTIAL",
            "reason_code": "RUNS_INCOMPLETE",
            "reason": "Both seed43 confirmation jobs did not complete with 10 rows.",
            "n30_recommended_now": False,
            "keep_rate_tuning_in_this_task": False,
            "next_task": "complete_bounded_Task95D_before_larger_runs",
        }
    if not metadata_ok:
        return {
            "decision": "FAIL",
            "reason_code": "METADATA_FAILED",
            "reason": "One or more artifacts failed metadata/path/local-only checks.",
            "n30_recommended_now": False,
            "keep_rate_tuning_in_this_task": False,
            "next_task": "repair_artifact_metadata_before_interpretation",
        }
    if not overlap.get("independent_confirmation_sample"):
        return {
            "decision": "PARTIAL",
            "reason_code": "SAMPLE_OVERLAP",
            "reason": "Seed43 overlaps seed42, so the confirmation is not fully independent.",
            "n30_recommended_now": False,
            "keep_rate_tuning_in_this_task": False,
            "next_task": "add_or_select_supported_sample_offset",
        }

    strict_gap = int(large.get("strict_correct_count", 0)) - int(light.get("strict_correct_count", 0))
    cap_low = int(light.get("cap_limited_incomplete_count", 10)) <= 2
    light_near_large = strict_gap <= 1
    e2e_delta = comparison.get("avg_e2e_time_s_delta")
    light_e2e_lower = isinstance(e2e_delta, (int, float)) and e2e_delta < 0

    if light_near_large and cap_low and light_e2e_lower:
        return {
            "decision": "PASS_WITH_CAVEAT",
            "reason_code": "CONFIRMED",
            "reason": "Seed43 confirms light near large on calibrated strict correctness, keeps cap-limited rows low, and preserves lower e2e time.",
            "n30_recommended_now": True,
            "keep_rate_tuning_in_this_task": False,
            "next_task": "T96_n30_controlled_mnt256_comparison",
            "light_quality_gap_large_minus_light": strict_gap,
        }

    return {
        "decision": "PASS_WITH_CAVEAT",
        "reason_code": "REGRESSED_OR_WEAK_CONFIRMATION",
        "reason": "Seed43 does not clearly confirm the Task95C-R light-quality repair.",
        "n30_recommended_now": False,
        "keep_rate_tuning_in_this_task": False,
        "next_task": "T95E_or_T96_light_tail_keep_rate_triage",
        "light_quality_gap_large_minus_light": strict_gap,
    }


def _table_rows(profiles: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("seed42_large_256", "seed42_light_256", "seed43_large_256", "seed43_light_256"):
        summary = profiles[key]
        rows.append(
            {
                "setting": key,
                "profile": summary["profile"],
                "seed": summary["seed"],
                "row_count": summary["row_count"],
                "strict_correct_count": summary["strict_correct_count"],
                "cap_limited_incomplete_count": summary["cap_limited_incomplete_count"],
                "strict_wrong_numeric_count": summary["strict_wrong_numeric_count"],
                "final_answer_marker_count": summary["final_answer_marker_count"],
                "avg_t_compress_ms": summary["avg_t_compress_ms"],
                "avg_R_actual": summary["avg_R_actual"],
                "avg_e2e_time_s": summary["avg_e2e_time_s"],
                "avg_tokens_per_second": summary["avg_tokens_per_second"],
                "avg_tau_mean": summary["avg_tau_mean"],
                "metadata_ok": summary["metadata_sanity"]["metadata_ok"],
                "artifact": summary["artifact"],
            }
        )
    return rows


def _row_labels(profiles: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, summary in profiles.items():
        for label in summary["labels"]:
            rows.append(
                {
                    "setting": key,
                    "fixture_id": _row_id(label),
                    "profile": summary["profile"],
                    "seed": summary["seed"],
                    "calibrated_label": label["calibrated_label"],
                    "strict_correct": label["strict_correct"],
                    "final_answer_marker_present": label["final_answer_marker_present"],
                    "exact_containment": label["exact_containment"],
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
    fieldnames = sorted({field for row in rows for field in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def analyze(
    previous_large_jsonl: Path,
    previous_light_jsonl: Path,
    confirmation_large_jsonl: Path,
    confirmation_light_jsonl: Path,
    output_dir: Path,
) -> dict[str, Any]:
    profiles = {
        "seed42_large_256": summarize_artifact(previous_large_jsonl, profile="large", seed=42),
        "seed42_light_256": summarize_artifact(previous_light_jsonl, profile="light", seed=42),
        "seed43_large_256": summarize_artifact(confirmation_large_jsonl, profile="large", seed=43),
        "seed43_light_256": summarize_artifact(confirmation_light_jsonl, profile="light", seed=43),
    }
    overlap = fixture_overlap(profiles["seed42_large_256"], profiles["seed43_large_256"])
    metadata_ok = all(profile["metadata_sanity"]["metadata_ok"] for profile in profiles.values())
    comparisons = {
        "seed43_large_vs_light_256": _comparison(profiles["seed43_large_256"], profiles["seed43_light_256"]),
        "large_seed42_vs_seed43_256": _comparison(profiles["seed42_large_256"], profiles["seed43_large_256"]),
        "light_seed42_vs_seed43_256": _comparison(profiles["seed42_light_256"], profiles["seed43_light_256"]),
    }
    serializable_profiles = {
        key: {k: v for k, v in value.items() if k != "labels"}
        for key, value in profiles.items()
    }
    summary = {
        "task": "Task95D",
        "title": "Bounded mnt256 Confirmation",
        "method": {
            "condition": "CC-DFlash-R2",
            "dataset": "gsm8k_short",
            "previous_seed": 42,
            "confirmation_seed": 43,
            "n": 10,
            "max_new_tokens": 256,
            "keep_rate_tuning": False,
            "n30_run": False,
            "n100_run": False,
            "llm_judge": False,
            "strict_policy_source": "Task95B calibrated policy",
        },
        "fixture_overlap": overlap,
        "metadata_ok": metadata_ok,
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
    recommendation = build_recommendation(summary)
    summary["recommendation"] = recommendation

    summary_dir = output_dir / "summary"
    table_dir = output_dir / "tables"
    _write_json(summary_dir / "task95d_bounded_confirmation_summary.json", summary)
    _write_json(summary_dir / "task95d_recommendation.json", recommendation)
    _write_jsonl(summary_dir / "task95d_row_labels.jsonl", _row_labels(profiles))
    _write_csv(table_dir / "task95d_bounded_confirmation_table.csv", _table_rows(profiles))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task95D bounded mnt256 confirmation artifacts")
    parser.add_argument("--previous-large-jsonl", type=Path, default=DEFAULT_PREVIOUS_LARGE)
    parser.add_argument("--previous-light-jsonl", type=Path, default=DEFAULT_PREVIOUS_LIGHT)
    parser.add_argument("--confirmation-large-jsonl", type=Path, required=True)
    parser.add_argument("--confirmation-light-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    summary = analyze(
        args.previous_large_jsonl,
        args.previous_light_jsonl,
        args.confirmation_large_jsonl,
        args.confirmation_light_jsonl,
        args.output_dir,
    )
    recommendation = summary["recommendation"]
    print(f"status={recommendation['decision']}")
    print(f"reason_code={recommendation['reason_code']}")
    print(f"n30_recommended_now={recommendation['n30_recommended_now']}")
    print(f"next_task={recommendation['next_task']}")
    print(f"fixture_overlap_count={summary['fixture_overlap']['overlap_count']}")
    print(f"wrote_summary={args.output_dir / 'summary' / 'task95d_bounded_confirmation_summary.json'}")
    print(f"wrote_table={args.output_dir / 'tables' / 'task95d_bounded_confirmation_table.csv'}")


if __name__ == "__main__":
    main()
