from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_task47_quality_refinement import classify_row


TASK63_PATHS = {
    "LLMLingua-AR-R2": Path("results/task63_gsm8k_short_llmlingua_ar_r2_n30_mnt256.jsonl"),
    "CC-DFlash-R2": Path("results/task63_gsm8k_short_cc_dflash_r2_n30_mnt256.jsonl"),
}
TASK65_PATHS = {
    "LLMLingua-AR-R2": Path("results/task65_gsm8k_short_llmlingua_ar_r2_n30_mnt384.jsonl"),
    "CC-DFlash-R2": Path("results/task65_gsm8k_short_cc_dflash_r2_n30_mnt384.jsonl"),
}
DEFAULT_TASK64_CASES = Path("results/task64_cap_hit_cases.jsonl")
DEFAULT_SUMMARY_OUTPUT = Path("results/task65_mnt384_calibration_summary.json")
DEFAULT_CSV_OUTPUT = Path("results/task65_mnt384_calibration_table.csv")
DEFAULT_CHANGED_OUTPUT = Path("results/task65_mnt384_changed_outcomes.jsonl")

FINAL_ANSWER_MARKER_RE = re.compile(
    r"final\s+(?:numeric\s+)?answer\s*(?:is|=|:|：)\s*[-+]?\$?\d[\d,]*(?:\.\d+)?",
    re.IGNORECASE,
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: line {line_number} is not valid JSON ({exc})") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}: line {line_number} is not a JSON object")
        rows.append(row)
    return rows


def _prompt_key(row: dict[str, Any]) -> str:
    for field_name in ("dataset_id", "fixture_id", "benchmark_prompt_index", "prompt_id"):
        value = row.get(field_name)
        if value is not None:
            return str(value)
    return ""


def _numeric_values(rows: list[dict[str, Any]], *field_names: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        for field_name in field_names:
            value = row.get(field_name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(float(value))
                break
    return values


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _has_final_answer_marker(text: Any) -> bool:
    return isinstance(text, str) and bool(FINAL_ANSWER_MARKER_RE.search(text))


def _hit_token_cap(row: dict[str, Any]) -> bool:
    output_tokens = row.get("output_tokens")
    max_new_tokens = row.get("max_new_tokens")
    return (
        isinstance(output_tokens, (int, float))
        and not isinstance(output_tokens, bool)
        and isinstance(max_new_tokens, (int, float))
        and not isinstance(max_new_tokens, bool)
        and output_tokens >= max_new_tokens
    )


def _classifications(condition: str, path: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        classify_row(row, row_index=row_index, condition=condition, artifact=str(path))
        for row_index, row in enumerate(rows, start=1)
    ]


def summarize_artifact(stage: str, condition: str, path: Path) -> dict[str, Any]:
    rows = load_jsonl(path)
    classified = _classifications(condition, path, rows)
    generation_times = _numeric_values(rows, "generation_time_s")
    e2e_times = [
        float(row.get("generation_time_s", 0.0)) + float(row.get("t_compress_ms", 0.0)) / 1000.0
        for row in rows
        if isinstance(row.get("generation_time_s"), (int, float))
    ]
    total_output_tokens = sum(_numeric_values(rows, "output_tokens"))
    total_generation_time = sum(generation_times)
    total_e2e_time = sum(e2e_times)
    numeric_matches = sum(1 for item in classified if item.get("numeric_match"))
    exact_matches = sum(1 for item in classified if item.get("exact_match"))
    cap_hit_failures = sum(
        1
        for row, item in zip(rows, classified, strict=True)
        if _hit_token_cap(row) and not item.get("numeric_match")
    )
    non_cap_failures = sum(
        1
        for row, item in zip(rows, classified, strict=True)
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


def _compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "numeric_extraction_match_count",
        "exact_containment_count",
        "final_answer_marker_count",
        "hit_token_cap_count",
        "cap_hit_failure_count",
        "non_cap_failure_count",
        "generated_text_present_count",
        "protected_suffix_preserved_count",
        "question_preserved_count",
    )
    comparison = {
        "condition": after["condition"],
        "task63_rows": before["rows"],
        "task65_rows": after["rows"],
        "task63_numeric_extraction_rate": before["numeric_extraction_rate"],
        "task65_numeric_extraction_rate": after["numeric_extraction_rate"],
        "numeric_extraction_rate_delta": round(
            after["numeric_extraction_rate"] - before["numeric_extraction_rate"],
            6,
        ),
    }
    comparison.update({f"{field}_delta": after[field] - before[field] for field in fields})
    comparison["numeric_extraction_match_delta"] = comparison["numeric_extraction_match_count_delta"]
    comparison["exact_containment_delta"] = comparison["exact_containment_count_delta"]
    comparison["final_answer_marker_delta"] = comparison["final_answer_marker_count_delta"]
    comparison["hit_token_cap_delta"] = comparison["hit_token_cap_count_delta"]
    for field in (
        "avg_output_tokens",
        "avg_generation_latency_s",
        "avg_e2e_latency_s",
        "avg_t_compress_ms",
        "avg_tok_per_sec",
        "generation_tok_per_sec_weighted",
        "e2e_tok_per_sec_weighted",
        "avg_actual_compression_ratio",
    ):
        comparison[f"{field}_delta"] = round(after[field] - before[field], 6)
    comparison["cap_hits_reduced"] = comparison["hit_token_cap_count_delta"] < 0
    comparison["numeric_accuracy_improved"] = comparison["numeric_extraction_match_count_delta"] > 0
    comparison["pass_to_fail_present"] = False
    return comparison


def _outcome_label(before_success: bool, after_success: bool) -> str:
    if before_success and after_success:
        return "SAME_PASS"
    if before_success and not after_success:
        return "PASS_TO_FAIL"
    if not before_success and after_success:
        return "FAIL_TO_PASS"
    return "SAME_FAIL"


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
                "task63_numeric_match": before_success,
                "task65_numeric_match": after_success,
                "outcome_label": _outcome_label(before_success, after_success),
                "task63_extracted_answer": before_classified.get("extracted_answer"),
                "task65_extracted_answer": after_classified.get("extracted_answer"),
                "task63_output_tokens": before_row.get("output_tokens"),
                "task65_output_tokens": after_row.get("output_tokens"),
                "task63_hit_cap": _hit_token_cap(before_row),
                "task65_hit_cap": _hit_token_cap(after_row),
                "task63_final_answer_marker": _has_final_answer_marker(before_row.get("generated_text")),
                "task65_final_answer_marker": _has_final_answer_marker(after_row.get("generated_text")),
                "task63_generation_time_s": before_row.get("generation_time_s"),
                "task65_generation_time_s": after_row.get("generation_time_s"),
                "task63_t_compress_ms": before_row.get("t_compress_ms"),
                "task65_t_compress_ms": after_row.get("t_compress_ms"),
            }
        )
    return rows


def _resolve_task64_cases(
    *,
    condition: str,
    task64_cases_path: Path,
    task65_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not task64_cases_path.exists():
        return {
            "condition": condition,
            "task64_cases": 0,
            "fixed_numeric_match_count": 0,
            "still_hit_cap_count": 0,
            "final_answer_marker_count": 0,
        }, []
    task64_cases = [
        row for row in load_jsonl(task64_cases_path)
        if row.get("condition") == condition and row.get("failure_label") == "TRUNCATION_DOMINANT"
    ]
    after_rows = {_prompt_key(row): row for row in load_jsonl(task65_path)}
    resolved: list[dict[str, Any]] = []
    for case in task64_cases:
        key = _prompt_key(case)
        after_row = after_rows.get(key)
        if after_row is None:
            continue
        classified = classify_row(after_row, row_index=int(after_row.get("prompt_id") or 0), condition=condition, artifact=str(task65_path))
        resolved.append(
            {
                "condition": condition,
                "prompt_key": key,
                "prompt_id": after_row.get("prompt_id"),
                "dataset_id": after_row.get("dataset_id"),
                "task64_failure_label": case.get("failure_label"),
                "task64_hit_cap": case.get("hit_cap"),
                "task64_numeric_match": bool(case.get("numeric_match")),
                "task65_numeric_match": bool(classified.get("numeric_match")),
                "task65_extracted_answer": classified.get("extracted_answer"),
                "task65_hit_cap": _hit_token_cap(after_row),
                "task65_final_answer_marker": _has_final_answer_marker(after_row.get("generated_text")),
                "task65_output_tokens": after_row.get("output_tokens"),
            }
        )
    summary = {
        "condition": condition,
        "task64_cases": len(resolved),
        "previous_numeric_failure_count": sum(1 for row in resolved if not row["task64_numeric_match"]),
        "previous_failure_fixed_count": sum(
            1 for row in resolved if not row["task64_numeric_match"] and row["task65_numeric_match"]
        ),
        "numeric_match_after_count": sum(1 for row in resolved if row["task65_numeric_match"]),
        "still_hit_cap_count": sum(1 for row in resolved if row["task65_hit_cap"]),
        "final_answer_marker_count": sum(1 for row in resolved if row["task65_final_answer_marker"]),
    }
    return summary, resolved


def analyze_paths(
    *,
    task63_paths: dict[str, Path] | None = None,
    task65_paths: dict[str, Path] | None = None,
    task64_cases_path: Path = DEFAULT_TASK64_CASES,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    task63_paths = task63_paths or TASK63_PATHS
    task65_paths = task65_paths or TASK65_PATHS
    before = {
        condition: summarize_artifact("task63_mnt256", condition, path)
        for condition, path in task63_paths.items()
    }
    after = {
        condition: summarize_artifact("task65_mnt384", condition, path)
        for condition, path in task65_paths.items()
    }
    comparisons = {
        condition: _compare(before[condition], after[condition])
        for condition in sorted(set(before) & set(after))
    }
    changed: list[dict[str, Any]] = []
    cap_resolution: dict[str, Any] = {}
    cap_rows: list[dict[str, Any]] = []
    for condition in sorted(set(before) & set(after)):
        condition_changed = changed_outcomes(condition, task63_paths[condition], task65_paths[condition])
        changed.extend(condition_changed)
        comparisons[condition]["pass_to_fail_present"] = any(
            row["outcome_label"] == "PASS_TO_FAIL" for row in condition_changed
        )
        cap_summary, resolved_rows = _resolve_task64_cases(
            condition=condition,
            task64_cases_path=task64_cases_path,
            task65_path=task65_paths[condition],
        )
        cap_resolution[condition] = cap_summary
        cap_rows.extend(resolved_rows)

    outcome_counts = Counter(row["outcome_label"] for row in changed)
    status = "PASS"
    if any(artifact["rows"] < 30 for artifact in after.values()):
        status = "PARTIAL"
    recommendation = (
        "Use max_new_tokens=384 for compressed GSM8K only if cap hits fall and numeric extraction improves without "
        "PASS_TO_FAIL instability; otherwise inspect remaining reasoning failures before n=100."
    )
    summary = {
        "task": "Task 65 GSM8K compressed-only max_new_tokens=384 calibration",
        "status": status,
        "claim_policy": "preliminary compressed-only GSM8K calibration; no final correctness or speedup claim",
        "artifacts": {
            "task63_mnt256": before,
            "task65_mnt384": after,
        },
        "comparisons": comparisons,
        "changed_outcome_counts": dict(sorted(outcome_counts.items())),
        "task64_cap_hit_case_resolution": cap_resolution,
        "task64_cap_hit_case_rows": cap_rows,
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
    parser = argparse.ArgumentParser(description="Analyze Task 65 GSM8K mnt384 compressed calibration artifacts")
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
        before = summary["artifacts"]["task63_mnt256"][condition]
        after = summary["artifacts"]["task65_mnt384"][condition]
        comparison = summary["comparisons"][condition]
        cap = summary["task64_cap_hit_case_resolution"][condition]
        print(
            f"{condition}: task63={before['numeric_extraction_match_count']}/{before['rows']} "
            f"task65={after['numeric_extraction_match_count']}/{after['rows']} "
            f"caps {before['hit_token_cap_count']}->{after['hit_token_cap_count']} "
            f"cap_failures {before['cap_hit_failure_count']}->{after['cap_hit_failure_count']} "
            f"delta={comparison['numeric_extraction_match_count_delta']} "
            f"task64_fixed={cap['previous_failure_fixed_count']}/{cap['previous_numeric_failure_count']} "
            f"pass_to_fail={comparison['pass_to_fail_present']}"
        )
    print(f"changed_outcomes={summary['changed_outcome_counts']}")


if __name__ == "__main__":
    main()
