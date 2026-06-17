from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_system_build_and_evaluation.analysis.t47_quality_refinement import classify_row


COMPRESSED_CONDITIONS = ["LLMLingua-AR-R2", "CC-DFlash-R2"]
TASK60_PATHS = {
    "LLMLingua-AR-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task60_gsm8k_short_llmlingua_ar_r2_n10_mnt256_suffixfix.jsonl"),
    "CC-DFlash-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task60_gsm8k_short_cc_dflash_r2_n10_mnt256_suffixfix.jsonl"),
}
TASK61B_PATHS = {
    "LLMLingua-AR-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task61b_gsm8k_short_llmlingua_ar_r2_n10_mnt256_k067.jsonl"),
    "CC-DFlash-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task61b_gsm8k_short_cc_dflash_r2_n10_mnt256_k067.jsonl"),
}
DEFAULT_JSON_OUTPUT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task61b_keep_rate67_calibration_summary.json")
DEFAULT_CSV_OUTPUT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task61b_keep_rate67_calibration_table.csv")
DEFAULT_CHANGED_OUTPUT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task61b_keep_rate67_changed_outcomes.jsonl")

FINAL_ANSWER_INSTRUCTION_RE = re.compile(
    r"end\s+with\s+exactly\s+one\s+line|final\s+answer\s*:\s*<number>",
    re.IGNORECASE,
)
FINAL_ANSWER_MARKER_RE = re.compile(
    r"final\s+(?:numeric\s+)?answer\s*(?:is|=|:|：)\s*[-+]?\$?\d[\d,]*(?:\.\d+)?",
    re.IGNORECASE,
)
COMPRESSED_METADATA_FIELDS = [
    "protected_suffix_preserved",
    "protected_suffix_preview",
    "final_prompt_preview",
    "final_prompt_tail_preview",
    "compressed_prompt_preview",
    "question_preserved",
    "original_input_tokens",
    "compressed_input_tokens",
    "keep_rate",
    "t_compress_ms",
]
REQUESTED_KEEP_RATE_FIELDS = ["requested_keep_rate_percent", "requested_keep_rate"]


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


def _unique_numeric_values(rows: list[dict[str, Any]], field_name: str) -> list[float]:
    values = {
        round(float(row[field_name]), 8)
        for row in rows
        if isinstance(row.get(field_name), (int, float)) and not isinstance(row.get(field_name), bool)
    }
    return sorted(values)


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _has_final_answer_instruction(text: Any) -> bool:
    return isinstance(text, str) and bool(FINAL_ANSWER_INSTRUCTION_RE.search(text))


def _has_generated_final_answer_marker(text: Any) -> bool:
    return isinstance(text, str) and bool(FINAL_ANSWER_MARKER_RE.search(text))


def _hit_max_new_tokens(row: dict[str, Any]) -> bool:
    output_tokens = row.get("output_tokens")
    max_new_tokens = row.get("max_new_tokens")
    return (
        isinstance(output_tokens, (int, float))
        and not isinstance(output_tokens, bool)
        and isinstance(max_new_tokens, (int, float))
        and not isinstance(max_new_tokens, bool)
        and output_tokens >= max_new_tokens
    )


def _kept_token_ratios(rows: list[dict[str, Any]]) -> list[float]:
    ratios: list[float] = []
    for row in rows:
        original = row.get("original_input_tokens")
        compressed = row.get("compressed_input_tokens")
        if (
            isinstance(original, (int, float))
            and not isinstance(original, bool)
            and original > 0
            and isinstance(compressed, (int, float))
            and not isinstance(compressed, bool)
        ):
            ratios.append(float(compressed) / float(original))
    return ratios


def _compression_metadata_complete(row: dict[str, Any], *, require_requested: bool) -> bool:
    fields = [*COMPRESSED_METADATA_FIELDS, *(REQUESTED_KEEP_RATE_FIELDS if require_requested else [])]
    if not all(field in row and row.get(field) is not None for field in fields):
        return False
    return row.get("actual_compression_ratio") is not None or row.get("compression_ratio") is not None


def _metadata_missing_by_field(rows: list[dict[str, Any]], *, require_requested: bool) -> dict[str, int]:
    fields = [*COMPRESSED_METADATA_FIELDS, *(REQUESTED_KEEP_RATE_FIELDS if require_requested else [])]
    missing = {
        field: sum(1 for row in rows if field not in row or row.get(field) is None)
        for field in fields
    }
    missing["actual_compression_ratio_or_compression_ratio"] = sum(
        1
        for row in rows
        if row.get("actual_compression_ratio") is None and row.get("compression_ratio") is None
    )
    return missing


def summarize_artifact(stage: str, condition: str, path: Path) -> dict[str, Any]:
    rows = load_jsonl(path)
    require_requested = stage == "task61b_keep_rate67"
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
    metadata_complete_rows = sum(
        1 for row in rows if _compression_metadata_complete(row, require_requested=require_requested)
    )

    return {
        "stage": stage,
        "condition": condition,
        "artifact": str(path),
        "rows": len(rows),
        "max_new_tokens": rows[0].get("max_new_tokens") if rows else None,
        "requested_keep_rate_percent_values": _unique_numeric_values(rows, "requested_keep_rate_percent"),
        "requested_keep_rate_values": _unique_numeric_values(rows, "requested_keep_rate"),
        "avg_keep_rate": _mean(_numeric_values(rows, "keep_rate")),
        "avg_kept_token_ratio": _mean(_kept_token_ratios(rows)),
        "avg_original_input_tokens": _mean(_numeric_values(rows, "original_input_tokens")),
        "avg_compressed_input_tokens": _mean(_numeric_values(rows, "compressed_input_tokens")),
        "avg_actual_compression_ratio": _mean(_numeric_values(rows, "actual_compression_ratio", "compression_ratio", "R_actual")),
        "protected_suffix_preserved_count": sum(1 for row in rows if row.get("protected_suffix_preserved") is True),
        "final_prompt_preview_has_instruction_count": sum(
            1 for row in rows if _has_final_answer_instruction(row.get("final_prompt_preview"))
        ),
        "final_prompt_tail_has_instruction_count": sum(
            1 for row in rows if _has_final_answer_instruction(row.get("final_prompt_tail_preview"))
        ),
        "compressed_prompt_preview_has_instruction_count": sum(
            1 for row in rows if _has_final_answer_instruction(row.get("compressed_prompt_preview"))
        ),
        "generated_text_present_count": sum(
            1 for row in rows if isinstance(row.get("generated_text"), str) and bool(row["generated_text"].strip())
        ),
        "generated_final_answer_marker_present_count": sum(
            1 for row in rows if _has_generated_final_answer_marker(row.get("generated_text"))
        ),
        "numeric_extraction_match_count": sum(1 for item in classifications if item.get("numeric_match")),
        "exact_containment_count": sum(1 for item in classifications if item.get("exact_match")),
        "hit_max_new_tokens_count": sum(1 for row in rows if _hit_max_new_tokens(row)),
        "avg_output_tokens": _mean(_numeric_values(rows, "output_tokens")),
        "avg_generation_time_s": _mean(generation_times),
        "avg_e2e_time_s": _mean(e2e_times),
        "avg_t_compress_ms": _mean(_numeric_values(rows, "t_compress_ms")),
        "avg_tok_per_sec": _mean(_numeric_values(rows, "tok_per_sec", "tok_per_s", "tokens_per_second")),
        "gen_tok_per_sec_weighted": total_output_tokens / total_generation_time if total_generation_time else 0.0,
        "e2e_tok_per_sec_weighted": total_output_tokens / total_e2e_time if total_e2e_time else 0.0,
        "compressed_metadata_complete_rows": metadata_complete_rows,
        "compressed_metadata_complete_rate": metadata_complete_rows / len(rows) if rows else 0.0,
        "metadata_missing_by_field": _metadata_missing_by_field(rows, require_requested=require_requested),
        "all_questions_preserved": all(row.get("question_preserved") is True for row in rows) if rows else False,
    }


def _compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    count_fields = [
        "protected_suffix_preserved_count",
        "final_prompt_tail_has_instruction_count",
        "compressed_prompt_preview_has_instruction_count",
        "generated_final_answer_marker_present_count",
        "numeric_extraction_match_count",
        "exact_containment_count",
        "hit_max_new_tokens_count",
        "compressed_metadata_complete_rows",
    ]
    comparison = {f"{field.removesuffix('_count')}_delta": after[field] - before[field] for field in count_fields}
    for field in (
        "avg_keep_rate",
        "avg_kept_token_ratio",
        "avg_original_input_tokens",
        "avg_compressed_input_tokens",
        "avg_actual_compression_ratio",
        "avg_output_tokens",
        "avg_generation_time_s",
        "avg_e2e_time_s",
        "avg_t_compress_ms",
        "avg_tok_per_sec",
        "gen_tok_per_sec_weighted",
        "e2e_tok_per_sec_weighted",
    ):
        comparison[f"{field}_delta"] = round(after[field] - before[field], 10)
    comparison["numeric_extraction_improved"] = comparison["numeric_extraction_match_delta"] > 0
    comparison["hit_cap_reduced"] = comparison["hit_max_new_tokens_delta"] < 0
    comparison["suffix_survival_verified"] = after["protected_suffix_preserved_count"] == after["rows"] and after["rows"] > 0
    comparison["requested_keep_rate_percent_verified"] = after["requested_keep_rate_percent_values"] == [67.0]
    comparison["resolved_keep_rate_verified"] = after["requested_keep_rate_values"] == [0.67] and round(after["avg_keep_rate"], 8) == 0.67
    return comparison


def _outcome_label(before_success: bool, after_success: bool) -> str:
    if before_success and after_success:
        return "SAME_PASS"
    if before_success and not after_success:
        return "PASS_TO_FAIL"
    if not before_success and after_success:
        return "FAIL_TO_PASS"
    return "SAME_FAIL"


def changed_outcomes(*, condition: str, before_path: Path, after_path: Path) -> list[dict[str, Any]]:
    before_rows = {_prompt_key(row): row for row in load_jsonl(before_path)}
    after_rows = {_prompt_key(row): row for row in load_jsonl(after_path)}
    rows: list[dict[str, Any]] = []
    for key in sorted(set(before_rows) & set(after_rows)):
        before_row = before_rows[key]
        after_row = after_rows[key]
        before_classified = classify_row(
            before_row,
            row_index=int(before_row.get("prompt_id") or 0),
            condition=condition,
            artifact=str(before_path),
        )
        after_classified = classify_row(
            after_row,
            row_index=int(after_row.get("prompt_id") or 0),
            condition=condition,
            artifact=str(after_path),
        )
        before_success = bool(before_classified.get("numeric_match"))
        after_success = bool(after_classified.get("numeric_match"))
        rows.append(
            {
                "condition": condition,
                "prompt_key": key,
                "prompt_id": after_row.get("prompt_id"),
                "dataset_id": after_row.get("dataset_id"),
                "expected_answer": after_row.get("expected_answer") or before_row.get("expected_answer"),
                "task60_numeric_match": before_success,
                "task61b_numeric_match": after_success,
                "outcome_label": _outcome_label(before_success, after_success),
                "task60_output_tokens": before_row.get("output_tokens"),
                "task61b_output_tokens": after_row.get("output_tokens"),
                "task60_hit_cap": _hit_max_new_tokens(before_row),
                "task61b_hit_cap": _hit_max_new_tokens(after_row),
                "task60_generated_marker": _has_generated_final_answer_marker(before_row.get("generated_text")),
                "task61b_generated_marker": _has_generated_final_answer_marker(after_row.get("generated_text")),
                "task60_extracted_answer": before_classified.get("extracted_answer"),
                "task61b_extracted_answer": after_classified.get("extracted_answer"),
                "task60_keep_rate": before_row.get("keep_rate"),
                "task61b_keep_rate": after_row.get("keep_rate"),
                "task61b_requested_keep_rate_percent": after_row.get("requested_keep_rate_percent"),
                "task60_compressed_input_tokens": before_row.get("compressed_input_tokens"),
                "task61b_compressed_input_tokens": after_row.get("compressed_input_tokens"),
                "task60_actual_compression_ratio": before_row.get("actual_compression_ratio") or before_row.get("compression_ratio"),
                "task61b_actual_compression_ratio": after_row.get("actual_compression_ratio") or after_row.get("compression_ratio"),
            }
        )
    return rows


def _changed_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        condition = str(row["condition"])
        label = str(row["outcome_label"])
        counts.setdefault(condition, {})
        counts[condition][label] = counts[condition].get(label, 0) + 1
    return counts


def analyze_paths(
    *,
    before_paths: dict[str, Path] | None = None,
    after_paths: dict[str, Path] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    before_paths = before_paths or TASK60_PATHS
    after_paths = after_paths or TASK61B_PATHS
    before = {
        condition: summarize_artifact("task60_keep_rate50", condition, before_paths[condition])
        for condition in before_paths
    }
    after = {
        condition: summarize_artifact("task61b_keep_rate67", condition, after_paths[condition])
        for condition in after_paths
    }
    comparisons = {
        condition: _compare(before[condition], after[condition])
        for condition in sorted(set(before) & set(after))
    }
    changed: list[dict[str, Any]] = []
    for condition in sorted(set(before_paths) & set(after_paths)):
        changed.extend(changed_outcomes(condition=condition, before_path=before_paths[condition], after_path=after_paths[condition]))

    status = "PASS"
    if not all(item["suffix_survival_verified"] for item in comparisons.values()):
        status = "PARTIAL"
    if not all(item["requested_keep_rate_percent_verified"] and item["resolved_keep_rate_verified"] for item in comparisons.values()):
        status = "PARTIAL"

    summary = {
        "task": "Task 61B tiny compressed-only GSM8K keep_rate_percent=67 calibration",
        "status": status,
        "claim_policy": "preliminary n=10 compressed-only GSM8K calibration; no final correctness or speedup claim",
        "artifacts": {
            "task60_keep_rate50": before,
            "task61b_keep_rate67": after,
        },
        "comparisons": comparisons,
        "changed_outcome_counts": _changed_counts(changed),
    }
    return summary, changed


def write_csv(summary: dict[str, Any], path: Path) -> None:
    fields = [
        "stage",
        "condition",
        "rows",
        "max_new_tokens",
        "requested_keep_rate_percent_values",
        "requested_keep_rate_values",
        "avg_keep_rate",
        "avg_kept_token_ratio",
        "avg_original_input_tokens",
        "avg_compressed_input_tokens",
        "avg_actual_compression_ratio",
        "protected_suffix_preserved_count",
        "final_prompt_tail_has_instruction_count",
        "generated_final_answer_marker_present_count",
        "numeric_extraction_match_count",
        "exact_containment_count",
        "hit_max_new_tokens_count",
        "avg_output_tokens",
        "avg_generation_time_s",
        "avg_e2e_time_s",
        "avg_t_compress_ms",
        "avg_tok_per_sec",
        "gen_tok_per_sec_weighted",
        "e2e_tok_per_sec_weighted",
        "compressed_metadata_complete_rows",
        "all_questions_preserved",
        "artifact",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for artifacts in summary["artifacts"].values():
            for artifact in artifacts.values():
                writer.writerow({field: artifact.get(field) for field in fields})


def write_changed(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 61B GSM8K keep_rate_percent=67 calibration artifacts")
    parser.add_argument("--output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_OUTPUT))
    parser.add_argument("--changed", default=str(DEFAULT_CHANGED_OUTPUT))
    args = parser.parse_args()

    summary, changed = analyze_paths()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(summary, Path(args.csv))
    write_changed(changed, Path(args.changed))

    print(f"status={summary['status']}")
    for stage, artifacts in summary["artifacts"].items():
        for condition, artifact in artifacts.items():
            print(
                f"{stage} {condition} rows={artifact['rows']} max_new_tokens={artifact['max_new_tokens']} "
                f"requested_percent={artifact['requested_keep_rate_percent_values']} "
                f"keep_rate={artifact['avg_keep_rate']:.4f} "
                f"kept_ratio={artifact['avg_kept_token_ratio']:.4f} "
                f"ratio={artifact['avg_actual_compression_ratio']:.4f} "
                f"suffix={artifact['protected_suffix_preserved_count']} "
                f"tail_instruction={artifact['final_prompt_tail_has_instruction_count']} "
                f"generated_marker={artifact['generated_final_answer_marker_present_count']} "
                f"numeric={artifact['numeric_extraction_match_count']} "
                f"hit_cap={artifact['hit_max_new_tokens_count']} "
                f"avg_e2e_time_s={artifact['avg_e2e_time_s']:.2f}"
            )
    for condition, comparison in summary["comparisons"].items():
        print(
            f"compare {condition}: numeric_delta={comparison['numeric_extraction_match_delta']} "
            f"hit_cap_delta={comparison['hit_max_new_tokens_delta']} "
            f"kept_ratio_delta={comparison['avg_kept_token_ratio_delta']:.4f} "
            f"e2e_delta={comparison['avg_e2e_time_s_delta']:.2f} "
            f"requested_verified={comparison['requested_keep_rate_percent_verified']}"
        )
    for condition, counts in summary["changed_outcome_counts"].items():
        print(f"outcomes {condition}: {counts}")


if __name__ == "__main__":
    main()
