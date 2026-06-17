from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_analysis.analyze_task47_quality_refinement import classify_row
from scripts.phase_1_analysis.analyze_task65_mnt384_calibration import (
    _has_final_answer_marker,
    _hit_token_cap,
    _numeric_values,
    _prompt_key,
    load_jsonl,
)


TASK65_PATHS = {
    "LLMLingua-AR-R2": Path("results/task65_gsm8k_short_llmlingua_ar_r2_n30_mnt384.jsonl"),
    "CC-DFlash-R2": Path("results/task65_gsm8k_short_cc_dflash_r2_n30_mnt384.jsonl"),
}
TASK66_PATHS = {
    "LLMLingua-AR-R2": Path("results/task66_gsm8k_short_llmlingua_ar_r2_n30_mnt384_rerun.jsonl"),
    "CC-DFlash-R2": Path("results/task66_gsm8k_short_cc_dflash_r2_n30_mnt384_rerun.jsonl"),
}
DEFAULT_SUMMARY_OUTPUT = Path("results/task66_mnt384_rerun_reproducibility_summary.json")
DEFAULT_CSV_OUTPUT = Path("results/task66_mnt384_rerun_reproducibility_table.csv")
DEFAULT_CHANGED_OUTPUT = Path("results/task66_mnt384_rerun_changed_outcomes.jsonl")
NOISY_RELATIVE_THRESHOLD = 0.25


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _outcome_label(before_success: bool, after_success: bool) -> str:
    if before_success and after_success:
        return "SAME_PASS"
    if before_success and not after_success:
        return "PASS_TO_FAIL"
    if not before_success and after_success:
        return "FAIL_TO_PASS"
    return "SAME_FAIL"


def summarize_artifact(stage: str, condition: str, path: Path) -> dict[str, Any]:
    rows = load_jsonl(path)
    classifications = [
        classify_row(row, row_index=row_index, condition=condition, artifact=str(path))
        for row_index, row in enumerate(rows, start=1)
    ]
    generation_times = _numeric_values(rows, "generation_time_s")
    e2e_times = [
        float(row.get("generation_time_s", 0.0)) + float(row.get("t_compress_ms", 0.0)) / 1000.0
        for row in rows
        if isinstance(row.get("generation_time_s"), (int, float))
    ]
    total_output_tokens = sum(_numeric_values(rows, "output_tokens"))
    total_generation_time = sum(generation_times)
    total_e2e_time = sum(e2e_times)
    numeric_matches = sum(1 for item in classifications if item.get("numeric_match"))
    exact_matches = sum(1 for item in classifications if item.get("exact_match"))
    cap_hit_failures = sum(
        1
        for row, item in zip(rows, classifications, strict=True)
        if _hit_token_cap(row) and not item.get("numeric_match")
    )
    non_cap_failures = sum(
        1
        for row, item in zip(rows, classifications, strict=True)
        if not _hit_token_cap(row) and not item.get("numeric_match")
    )
    return {
        "stage": stage,
        "condition": condition,
        "artifact": str(path),
        "rows": len(rows),
        "max_new_tokens": rows[0].get("max_new_tokens") if rows else None,
        "numeric_extraction_match_count": numeric_matches,
        "numeric_extraction_rate": round(numeric_matches / len(rows), 6) if rows else 0.0,
        "exact_containment_count": exact_matches,
        "exact_containment_rate": round(exact_matches / len(rows), 6) if rows else 0.0,
        "final_answer_marker_count": sum(1 for row in rows if _has_final_answer_marker(row.get("generated_text"))),
        "hit_token_cap_count": sum(1 for row in rows if _hit_token_cap(row)),
        "cap_hit_failure_count": cap_hit_failures,
        "non_cap_failure_count": non_cap_failures,
        "generated_text_present_count": sum(
            1 for row in rows if isinstance(row.get("generated_text"), str) and bool(row["generated_text"].strip())
        ),
        "protected_suffix_preserved_count": sum(1 for row in rows if row.get("protected_suffix_preserved") is True),
        "question_preserved_count": sum(1 for row in rows if row.get("question_preserved") is True),
        "avg_output_tokens": _mean(_numeric_values(rows, "output_tokens")),
        "avg_input_tokens": _mean(_numeric_values(rows, "input_tokens")),
        "avg_generation_latency_s": _mean(generation_times),
        "avg_e2e_latency_s": _mean(e2e_times),
        "avg_t_compress_ms": _mean(_numeric_values(rows, "t_compress_ms")),
        "avg_tok_per_sec": _mean(_numeric_values(rows, "tok_per_sec", "tok_per_s", "tokens_per_second")),
        "generation_tok_per_sec_weighted": total_output_tokens / total_generation_time if total_generation_time else 0.0,
        "e2e_tok_per_sec_weighted": total_output_tokens / total_e2e_time if total_e2e_time else 0.0,
        "avg_actual_compression_ratio": _mean(
            _numeric_values(rows, "actual_compression_ratio", "compression_ratio", "R_actual")
        ),
    }


def _latency_reproducibility(before: float, after: float, threshold: float) -> tuple[str, bool]:
    if before <= 0:
        return "INSUFFICIENT_DATA", False
    relative_delta = (after - before) / before
    if relative_delta <= -threshold:
        return "TASK65_NOISY_TASK66_LOWER", True
    if relative_delta >= threshold:
        return "TASK66_SLOWER", False
    return "REPRODUCIBLE_WITHIN_THRESHOLD", False


def _compare(before: dict[str, Any], after: dict[str, Any], threshold: float) -> dict[str, Any]:
    latency_label, task65_noisy = _latency_reproducibility(
        before["avg_e2e_latency_s"],
        after["avg_e2e_latency_s"],
        threshold,
    )
    relative_delta = (
        (after["avg_e2e_latency_s"] - before["avg_e2e_latency_s"]) / before["avg_e2e_latency_s"]
        if before["avg_e2e_latency_s"]
        else 0.0
    )
    comparison = {
        "condition": after["condition"],
        "task65_rows": before["rows"],
        "task66_rows": after["rows"],
        "task65_numeric_extraction_match_count": before["numeric_extraction_match_count"],
        "task66_numeric_extraction_match_count": after["numeric_extraction_match_count"],
        "numeric_extraction_match_delta": after["numeric_extraction_match_count"] - before["numeric_extraction_match_count"],
        "task65_numeric_extraction_rate": before["numeric_extraction_rate"],
        "task66_numeric_extraction_rate": after["numeric_extraction_rate"],
        "numeric_extraction_rate_delta": round(after["numeric_extraction_rate"] - before["numeric_extraction_rate"], 6),
        "exact_containment_delta": after["exact_containment_count"] - before["exact_containment_count"],
        "final_answer_marker_delta": after["final_answer_marker_count"] - before["final_answer_marker_count"],
        "hit_token_cap_delta": after["hit_token_cap_count"] - before["hit_token_cap_count"],
        "cap_hit_failure_delta": after["cap_hit_failure_count"] - before["cap_hit_failure_count"],
        "non_cap_failure_delta": after["non_cap_failure_count"] - before["non_cap_failure_count"],
        "avg_generation_latency_s_delta": round(after["avg_generation_latency_s"] - before["avg_generation_latency_s"], 6),
        "avg_e2e_latency_s_delta": round(after["avg_e2e_latency_s"] - before["avg_e2e_latency_s"], 6),
        "avg_e2e_latency_relative_delta": round(relative_delta, 6),
        "avg_t_compress_ms_delta": round(after["avg_t_compress_ms"] - before["avg_t_compress_ms"], 6),
        "generation_tok_per_sec_weighted_delta": round(
            after["generation_tok_per_sec_weighted"] - before["generation_tok_per_sec_weighted"],
            6,
        ),
        "e2e_tok_per_sec_weighted_delta": round(
            after["e2e_tok_per_sec_weighted"] - before["e2e_tok_per_sec_weighted"],
            6,
        ),
        "latency_reproducibility": latency_label,
        "task65_latency_appears_noisy": task65_noisy,
    }
    return comparison


def changed_outcomes(condition: str, before_path: Path, after_path: Path) -> list[dict[str, Any]]:
    before_rows = {_prompt_key(row): row for row in load_jsonl(before_path)}
    after_rows = {_prompt_key(row): row for row in load_jsonl(after_path)}
    rows: list[dict[str, Any]] = []
    for key in sorted(set(before_rows) & set(after_rows), key=lambda item: (len(item), item)):
        before_row = before_rows[key]
        after_row = after_rows[key]
        before_classified = classify_row(before_row, row_index=int(before_row.get("prompt_id") or 0), condition=condition, artifact=str(before_path))
        after_classified = classify_row(after_row, row_index=int(after_row.get("prompt_id") or 0), condition=condition, artifact=str(after_path))
        before_success = bool(before_classified.get("numeric_match"))
        after_success = bool(after_classified.get("numeric_match"))
        rows.append(
            {
                "condition": condition,
                "prompt_key": key,
                "prompt_id": after_row.get("prompt_id"),
                "dataset_id": after_row.get("dataset_id"),
                "expected_answer": after_row.get("expected_answer") or before_row.get("expected_answer"),
                "task65_numeric_match": before_success,
                "task66_numeric_match": after_success,
                "outcome_label": _outcome_label(before_success, after_success),
                "task65_extracted_answer": before_classified.get("extracted_answer"),
                "task66_extracted_answer": after_classified.get("extracted_answer"),
                "task65_output_tokens": before_row.get("output_tokens"),
                "task66_output_tokens": after_row.get("output_tokens"),
                "task65_hit_cap": _hit_token_cap(before_row),
                "task66_hit_cap": _hit_token_cap(after_row),
                "task65_generation_time_s": before_row.get("generation_time_s"),
                "task66_generation_time_s": after_row.get("generation_time_s"),
                "task65_t_compress_ms": before_row.get("t_compress_ms"),
                "task66_t_compress_ms": after_row.get("t_compress_ms"),
            }
        )
    return rows


def analyze_paths(
    *,
    task65_paths: dict[str, Path] | None = None,
    task66_paths: dict[str, Path] | None = None,
    noisy_threshold: float = NOISY_RELATIVE_THRESHOLD,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    task65_paths = task65_paths or TASK65_PATHS
    task66_paths = task66_paths or TASK66_PATHS
    before = {
        condition: summarize_artifact("task65_mnt384", condition, path)
        for condition, path in task65_paths.items()
    }
    after = {
        condition: summarize_artifact("task66_mnt384_rerun", condition, path)
        for condition, path in task66_paths.items()
    }
    comparisons = {
        condition: _compare(before[condition], after[condition], noisy_threshold)
        for condition in sorted(set(before) & set(after))
    }
    changed: list[dict[str, Any]] = []
    for condition in sorted(set(before) & set(after)):
        changed.extend(changed_outcomes(condition, task65_paths[condition], task66_paths[condition]))

    outcome_counts = Counter(row["outcome_label"] for row in changed)
    any_noisy = any(item["task65_latency_appears_noisy"] for item in comparisons.values())
    status = "PASS"
    if any(artifact["rows"] < 30 for artifact in after.values()):
        status = "PARTIAL"
    recommendation = (
        "Use Task 66 rather than Task 65 for mnt384 latency interpretation if Task 65 is marked noisy; "
        "mnt384 remains a quality calibration setting, not a speed default, while cap-hit failures remain."
    )
    summary = {
        "task": "Task 66 GSM8K compressed-only mnt384 latency reproducibility check",
        "status": status,
        "claim_policy": "preliminary compressed-only rerun; no final correctness or speedup claim",
        "noisy_relative_threshold": noisy_threshold,
        "task65_latency_appears_noisy_overall": any_noisy,
        "artifacts": {
            "task65_mnt384": before,
            "task66_mnt384_rerun": after,
        },
        "comparisons": comparisons,
        "changed_outcome_counts": dict(sorted(outcome_counts.items())),
        "recommendation": recommendation,
    }
    return summary, changed


def write_csv(summary: dict[str, Any], path: Path) -> None:
    fields = [
        "stage",
        "condition",
        "rows",
        "max_new_tokens",
        "numeric_extraction_match_count",
        "numeric_extraction_rate",
        "exact_containment_count",
        "exact_containment_rate",
        "final_answer_marker_count",
        "hit_token_cap_count",
        "cap_hit_failure_count",
        "non_cap_failure_count",
        "avg_output_tokens",
        "avg_input_tokens",
        "avg_generation_latency_s",
        "avg_e2e_latency_s",
        "avg_t_compress_ms",
        "avg_tok_per_sec",
        "generation_tok_per_sec_weighted",
        "e2e_tok_per_sec_weighted",
        "avg_actual_compression_ratio",
        "protected_suffix_preserved_count",
        "question_preserved_count",
        "generated_text_present_count",
        "artifact",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for artifacts in summary["artifacts"].values():
            for artifact in artifacts.values():
                writer.writerow({field: artifact.get(field) for field in fields})


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 66 mnt384 rerun reproducibility artifacts")
    parser.add_argument("--output", default=str(DEFAULT_SUMMARY_OUTPUT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_OUTPUT))
    parser.add_argument("--changed-output", default=str(DEFAULT_CHANGED_OUTPUT))
    args = parser.parse_args()

    summary, changed = analyze_paths()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(summary, Path(args.csv))
    write_jsonl(changed, Path(args.changed_output))

    print(f"status={summary['status']}")
    for condition in sorted(summary["comparisons"]):
        before = summary["artifacts"]["task65_mnt384"][condition]
        after = summary["artifacts"]["task66_mnt384_rerun"][condition]
        comparison = summary["comparisons"][condition]
        print(
            f"{condition}: task65={before['numeric_extraction_match_count']}/{before['rows']} "
            f"task66={after['numeric_extraction_match_count']}/{after['rows']} "
            f"e2e {before['avg_e2e_latency_s']:.2f}s->{after['avg_e2e_latency_s']:.2f}s "
            f"rel_delta={comparison['avg_e2e_latency_relative_delta']:.3f} "
            f"latency={comparison['latency_reproducibility']} "
            f"caps {before['hit_token_cap_count']}->{after['hit_token_cap_count']}"
        )
    print(f"changed_outcomes={summary['changed_outcome_counts']}")


if __name__ == "__main__":
    main()
