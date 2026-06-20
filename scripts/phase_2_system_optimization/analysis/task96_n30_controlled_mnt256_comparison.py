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


DEFAULT_LARGE = Path(
    "results/phase_2_system_optimization/compressor_comparison/"
    "task96_n30_controlled_mnt256_comparison/runs/"
    "20260621_032109_cc_dflash_r2_large_seed42_n30_mnt256.jsonl"
)
DEFAULT_LIGHT = Path(
    "results/phase_2_system_optimization/compressor_comparison/"
    "task96_n30_controlled_mnt256_comparison/runs/"
    "20260621_032329_cc_dflash_r2_light_seed42_n30_mnt256.jsonl"
)
DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/compressor_comparison/"
    "task96_n30_controlled_mnt256_comparison"
)

LABELS = (
    "strict_correct",
    "strict_wrong_numeric",
    "cap_limited_incomplete",
    "format_or_extraction_sensitive",
    "answer_missing",
    "proxy_uncertain",
)
NUMERIC_FIELDS = (
    "t_compress_ms",
    "R_actual",
    "e2e_time_s",
    "tokens_per_second",
    "tau_mean",
    "t_prefill_ms",
    "vram_allocated_gib",
    "vram_reserved_gib",
    "prefill_vram_allocated_gib",
    "prefill_vram_reserved_gib",
    "output_tokens",
    "generated_token_count",
    "output_length_chars",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return t95b.load_jsonl(path)


def _row_id(row: dict[str, Any]) -> Any:
    return row.get("fixture_id") or row.get("dataset_id") or row.get("prompt_id") or row.get("row_index")


def _numeric(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _e2e_time(row: dict[str, Any]) -> float | None:
    direct = _numeric(row, "e2e_time_s", "end_to_end_time_s")
    if direct is not None:
        return direct
    generation = _numeric(row, "generation_time_s")
    t_compress_ms = _numeric(row, "t_compress_ms")
    if generation is not None and t_compress_ms is not None:
        return generation + t_compress_ms / 1000.0
    return None


def _output_length(row: dict[str, Any]) -> int | None:
    text = row.get("generated_text")
    return len(text) if isinstance(text, str) else None


def _stats(values: list[Any]) -> dict[str, float | None]:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric:
        return {"avg": None, "min": None, "max": None}
    return {
        "avg": round(mean(numeric), 6),
        "min": round(min(numeric), 6),
        "max": round(max(numeric), 6),
    }


def _label_count(labels: list[dict[str, Any]], label: str) -> int:
    return sum(1 for row in labels if row.get("calibrated_label") == label)


def _metadata_sanity(rows: list[dict[str, Any]], *, profile: str) -> dict[str, Any]:
    wrong_profile = 0
    wrong_max_new_tokens = 0
    wrong_condition = 0
    wrong_dataset = 0
    wrong_prompt_source = 0
    missing_profile = 0
    missing_local_only = 0
    missing_compressor_path = 0
    missing_resolved_path = 0
    observed_keep_rates: set[Any] = set()
    observed_conditions: set[Any] = set()
    observed_datasets: set[Any] = set()
    observed_max_new_tokens: set[Any] = set()

    for row in rows:
        row_profile = row.get("compressor_profile")
        if row_profile in (None, ""):
            missing_profile += 1
        elif row_profile != profile:
            wrong_profile += 1
        if row.get("max_new_tokens") != 256:
            wrong_max_new_tokens += 1
        if row.get("condition") != "CC-DFlash-R2":
            wrong_condition += 1
        if row.get("dataset_name") != "gsm8k_short":
            wrong_dataset += 1
        if row.get("prompt_source") != "dataset":
            wrong_prompt_source += 1
        if row.get("local_files_only") is not True:
            missing_local_only += 1
        if not row.get("compressor_path"):
            missing_compressor_path += 1
        if not row.get("resolved_compressor_path"):
            missing_resolved_path += 1
        if row.get("keep_rate") not in (None, ""):
            observed_keep_rates.add(row.get("keep_rate"))
        if row.get("condition") not in (None, ""):
            observed_conditions.add(row.get("condition"))
        if row.get("dataset_name") not in (None, ""):
            observed_datasets.add(row.get("dataset_name"))
        if row.get("max_new_tokens") not in (None, ""):
            observed_max_new_tokens.add(row.get("max_new_tokens"))

    metadata_ok = (
        wrong_profile == 0
        and wrong_max_new_tokens == 0
        and wrong_condition == 0
        and wrong_dataset == 0
        and wrong_prompt_source == 0
        and missing_profile == 0
        and missing_local_only == 0
        and missing_compressor_path == 0
        and missing_resolved_path == 0
    )
    return {
        "expected_profile": profile,
        "expected_condition": "CC-DFlash-R2",
        "expected_dataset": "gsm8k_short",
        "expected_prompt_source": "dataset",
        "expected_max_new_tokens": 256,
        "rows_wrong_compressor_profile": wrong_profile,
        "rows_wrong_max_new_tokens": wrong_max_new_tokens,
        "rows_wrong_condition": wrong_condition,
        "rows_wrong_dataset": wrong_dataset,
        "rows_wrong_prompt_source": wrong_prompt_source,
        "rows_missing_compressor_profile": missing_profile,
        "rows_missing_or_false_local_files_only": missing_local_only,
        "rows_missing_compressor_path": missing_compressor_path,
        "rows_missing_resolved_compressor_path": missing_resolved_path,
        "observed_keep_rates": sorted(str(value) for value in observed_keep_rates),
        "observed_conditions": sorted(str(value) for value in observed_conditions),
        "observed_datasets": sorted(str(value) for value in observed_datasets),
        "observed_max_new_tokens": sorted(str(value) for value in observed_max_new_tokens),
        "metadata_ok": metadata_ok,
    }


def summarize_artifact(path: Path, *, profile: str) -> dict[str, Any]:
    rows = load_jsonl(path)
    labels = [
        t95b.calibrate_row(row, profile=profile, row_index=index, artifact=path)
        for index, row in enumerate(rows, start=1)
    ]
    values_by_field = {
        "t_compress_ms": [_numeric(row, "t_compress_ms") for row in rows],
        "R_actual": [_numeric(row, "R_actual", "actual_compression_ratio", "compression_ratio") for row in rows],
        "e2e_time_s": [_e2e_time(row) for row in rows],
        "tokens_per_second": [_numeric(row, "tokens_per_second", "tok_per_sec") for row in rows],
        "tau_mean": [_numeric(row, "tau_mean") for row in rows],
        "t_prefill_ms": [_numeric(row, "t_prefill_ms") for row in rows],
        "vram_allocated_gib": [_numeric(row, "vram_allocated_gib") for row in rows],
        "vram_reserved_gib": [_numeric(row, "vram_reserved_gib") for row in rows],
        "prefill_vram_allocated_gib": [_numeric(row, "prefill_vram_allocated_gib") for row in rows],
        "prefill_vram_reserved_gib": [_numeric(row, "prefill_vram_reserved_gib") for row in rows],
        "output_tokens": [_numeric(row, "output_tokens") for row in rows],
        "generated_token_count": [_numeric(row, "generated_token_count") for row in rows],
        "output_length_chars": [_output_length(row) for row in rows],
    }
    stats = {field: _stats(values) for field, values in values_by_field.items()}
    label_counts = {label: _label_count(labels, label) for label in LABELS}
    return {
        "profile": profile,
        "seed": 42,
        "n": 30,
        "max_new_tokens": 256,
        "artifact": str(path),
        "row_count": len(rows),
        "fixture_ids": [str(_row_id(row)) for row in rows],
        "strict_correct_count": sum(1 for row in labels if row["strict_correct"]),
        "cap_limited_incomplete_count": label_counts["cap_limited_incomplete"],
        "strict_wrong_numeric_count": label_counts["strict_wrong_numeric"],
        "answer_missing_count": label_counts["answer_missing"],
        "proxy_uncertain_count": label_counts["proxy_uncertain"],
        "final_answer_marker_count": sum(1 for row in labels if row["final_answer_marker_present"]),
        "exact_containment_count": sum(1 for row in labels if row["exact_containment"]),
        "invalid_or_empty_output_count": sum(
            1 for row in rows if not isinstance(row.get("generated_text"), str) or not row.get("generated_text", "").strip()
        ),
        "calibrated_label_counts": label_counts,
        "metric_stats": stats,
        "avg_t_compress_ms": stats["t_compress_ms"]["avg"],
        "avg_R_actual": stats["R_actual"]["avg"],
        "avg_e2e_time_s": stats["e2e_time_s"]["avg"],
        "avg_tokens_per_second": stats["tokens_per_second"]["avg"],
        "avg_tau_mean": stats["tau_mean"]["avg"],
        "avg_t_prefill_ms": stats["t_prefill_ms"]["avg"],
        "avg_output_tokens": stats["output_tokens"]["avg"],
        "avg_generated_token_count": stats["generated_token_count"]["avg"],
        "avg_output_length_chars": stats["output_length_chars"]["avg"],
        "metadata_sanity": _metadata_sanity(rows, profile=profile),
        "labels": labels,
    }


def _delta(light: dict[str, Any], large: dict[str, Any], field: str) -> float | int | None:
    left = light.get(field)
    right = large.get(field)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        value = left - right
        return round(value, 6) if isinstance(value, float) else value
    return None


def _comparison(large: dict[str, Any], light: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "strict_correct_count": "strict_correct_delta",
        "cap_limited_incomplete_count": "cap_limited_incomplete_delta",
        "strict_wrong_numeric_count": "strict_wrong_numeric_delta",
        "answer_missing_count": "answer_missing_delta",
        "proxy_uncertain_count": "proxy_uncertain_delta",
        "final_answer_marker_count": "final_answer_marker_delta",
        "exact_containment_count": "exact_containment_delta",
        "avg_t_compress_ms": "avg_t_compress_ms_delta",
        "avg_R_actual": "avg_R_actual_delta",
        "avg_e2e_time_s": "avg_e2e_time_s_delta",
        "avg_tokens_per_second": "avg_tokens_per_second_delta",
        "avg_tau_mean": "avg_tau_mean_delta",
        "avg_t_prefill_ms": "avg_t_prefill_ms_delta",
        "avg_output_tokens": "avg_output_tokens_delta",
        "avg_generated_token_count": "avg_generated_token_count_delta",
        "avg_output_length_chars": "avg_output_length_chars_delta",
    }
    return {output: _delta(light, large, field) for field, output in fields.items()}


def build_recommendation(summary: dict[str, Any]) -> dict[str, Any]:
    profiles = summary.get("profiles", {})
    large = profiles.get("seed42_large_n30_mnt256", {})
    light = profiles.get("seed42_light_n30_mnt256", {})
    comparison = summary.get("comparisons", {}).get("light_vs_large", {})

    runs_complete = large.get("row_count") == 30 and light.get("row_count") == 30
    if not runs_complete:
        return {
            "decision": "PARTIAL",
            "reason_code": "RUNS_INCOMPLETE",
            "reason": "Both Task96 artifacts must contain exactly 30 measured rows.",
            "bounded_confirmation_holds_at_n30": False,
            "n100_recommended_now": False,
            "keep_rate_tuning_in_this_task": False,
            "next_task": "complete_Task96_n30_before_scaling",
        }
    if not summary.get("metadata_ok"):
        return {
            "decision": "FAIL",
            "reason_code": "METADATA_FAILED",
            "reason": "One or more artifacts failed Task96 condition, dataset, max-new-token, local-only, or compressor metadata checks.",
            "bounded_confirmation_holds_at_n30": False,
            "n100_recommended_now": False,
            "keep_rate_tuning_in_this_task": False,
            "next_task": "repair_Task96_artifact_metadata_before_interpretation",
        }

    strict_gap = int(large.get("strict_correct_count", 0)) - int(light.get("strict_correct_count", 0))
    cap_delta = int(light.get("cap_limited_incomplete_count", 0)) - int(large.get("cap_limited_incomplete_count", 0))
    t_compress_delta = comparison.get("avg_t_compress_ms_delta")
    light_t_compress_advantage = isinstance(t_compress_delta, (int, float)) and t_compress_delta < 0
    light_quality_near_large = strict_gap <= 2 and cap_delta <= 2

    if light_quality_near_large and light_t_compress_advantage:
        return {
            "decision": "PASS_WITH_CAVEAT",
            "reason_code": "BOUNDED_N30_CONFIRMED",
            "reason": "At n=30, light remains within the bounded quality envelope while preserving a clear compression-time advantage.",
            "bounded_confirmation_holds_at_n30": True,
            "n100_recommended_now": False,
            "keep_rate_tuning_in_this_task": False,
            "next_task": "T97_packaging_controlled_evidence_summary",
            "light_quality_gap_large_minus_light": strict_gap,
            "light_cap_delta_vs_large": cap_delta,
        }

    return {
        "decision": "PARTIAL",
        "reason_code": "LIGHT_QUALITY_REGRESSION",
        "reason": "The n=30 light run does not stay within the bounded quality envelope relative to large.",
        "bounded_confirmation_holds_at_n30": False,
        "n100_recommended_now": False,
        "keep_rate_tuning_in_this_task": False,
        "next_task": "T96A_light_tail_policy_triage_before_scaling",
        "light_quality_gap_large_minus_light": strict_gap,
        "light_cap_delta_vs_large": cap_delta,
    }


def _table_rows(profiles: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("seed42_large_n30_mnt256", "seed42_light_n30_mnt256"):
        summary = profiles[key]
        row: dict[str, Any] = {
            "setting": key,
            "profile": summary["profile"],
            "seed": summary["seed"],
            "n": summary["n"],
            "row_count": summary["row_count"],
            "strict_correct_count": summary["strict_correct_count"],
            "cap_limited_incomplete_count": summary["cap_limited_incomplete_count"],
            "strict_wrong_numeric_count": summary["strict_wrong_numeric_count"],
            "answer_missing_count": summary["answer_missing_count"],
            "proxy_uncertain_count": summary["proxy_uncertain_count"],
            "final_answer_marker_count": summary["final_answer_marker_count"],
            "exact_containment_count": summary["exact_containment_count"],
            "metadata_ok": summary["metadata_sanity"]["metadata_ok"],
            "artifact": summary["artifact"],
        }
        for field in NUMERIC_FIELDS:
            field_stats = summary["metric_stats"][field]
            row[f"avg_{field}"] = field_stats["avg"]
            row[f"min_{field}"] = field_stats["min"]
            row[f"max_{field}"] = field_stats["max"]
        rows.append(row)
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
                    "cap_limited": label["cap_limited"],
                    "final_answer_marker_present": label["final_answer_marker_present"],
                    "exact_containment": label["exact_containment"],
                    "strict_extracted_answer": label["strict_extracted_answer"],
                    "expected_numeric": label["expected_numeric"],
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


def analyze(large_jsonl: Path, light_jsonl: Path, output_dir: Path) -> dict[str, Any]:
    profiles = {
        "seed42_large_n30_mnt256": summarize_artifact(large_jsonl, profile="large"),
        "seed42_light_n30_mnt256": summarize_artifact(light_jsonl, profile="light"),
    }
    metadata_ok = all(profile["metadata_sanity"]["metadata_ok"] for profile in profiles.values())
    comparisons = {
        "light_vs_large": _comparison(
            profiles["seed42_large_n30_mnt256"],
            profiles["seed42_light_n30_mnt256"],
        )
    }
    serializable_profiles = {
        key: {k: v for k, v in value.items() if k != "labels"}
        for key, value in profiles.items()
    }
    summary = {
        "task": "Task96",
        "title": "n=30 Controlled mnt256 Comparison",
        "method": {
            "condition": "CC-DFlash-R2",
            "dataset": "gsm8k_short",
            "seed": 42,
            "n": 30,
            "max_new_tokens": 256,
            "warmup_prompts": 0,
            "resume": True,
            "store_generated_text": True,
            "profiles": ["large", "light"],
            "keep_rate_tuning": False,
            "n100_run": False,
            "full_benchmark_run": False,
            "baseline_ar_run": False,
            "dflash_r1_run": False,
            "qmsum_run": False,
            "llm_judge": False,
            "strict_policy_source": "Task95B calibrated policy",
        },
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
    _write_json(summary_dir / "task96_n30_controlled_summary.json", summary)
    _write_json(summary_dir / "task96_recommendation.json", recommendation)
    _write_jsonl(summary_dir / "task96_row_labels.jsonl", _row_labels(profiles))
    _write_csv(table_dir / "task96_n30_controlled_table.csv", _table_rows(profiles))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task96 n=30 controlled mnt256 comparison artifacts")
    parser.add_argument("--large-jsonl", type=Path, default=DEFAULT_LARGE)
    parser.add_argument("--light-jsonl", type=Path, default=DEFAULT_LIGHT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    summary = analyze(args.large_jsonl, args.light_jsonl, args.output_dir)
    recommendation = summary["recommendation"]
    comparison = summary["comparisons"]["light_vs_large"]
    print(f"status={recommendation['decision']}")
    print(f"reason_code={recommendation['reason_code']}")
    print(f"bounded_confirmation_holds_at_n30={recommendation['bounded_confirmation_holds_at_n30']}")
    print(f"next_task={recommendation['next_task']}")
    print(f"strict_correct_delta={comparison['strict_correct_delta']}")
    print(f"cap_limited_incomplete_delta={comparison['cap_limited_incomplete_delta']}")
    print(f"avg_t_compress_ms_delta={comparison['avg_t_compress_ms_delta']}")
    print(f"wrote_summary={args.output_dir / 'summary' / 'task96_n30_controlled_summary.json'}")
    print(f"wrote_table={args.output_dir / 'tables' / 'task96_n30_controlled_table.csv'}")


if __name__ == "__main__":
    main()
