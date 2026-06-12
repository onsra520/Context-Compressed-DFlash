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

from scripts.analyze_task47_quality_refinement import classify_row


COMPRESSED_CONDITIONS = ["LLMLingua-AR-R2", "CC-DFlash-R2"]
TASK56_PATHS = {
    "LLMLingua-AR-R2": Path("results/task56_gsm8k_short_llmlingua_ar_r2_n10_mnt192.jsonl"),
    "CC-DFlash-R2": Path("results/task56_gsm8k_short_cc_dflash_r2_n10_mnt192.jsonl"),
}
TASK59_PATHS = {
    "LLMLingua-AR-R2": Path("results/task59_gsm8k_short_llmlingua_ar_r2_n10_mnt192_suffixfix.jsonl"),
    "CC-DFlash-R2": Path("results/task59_gsm8k_short_cc_dflash_r2_n10_mnt192_suffixfix.jsonl"),
}
DEFAULT_JSON_OUTPUT = Path("results/task59_suffix_verification_summary.json")
DEFAULT_CSV_OUTPUT = Path("results/task59_suffix_verification_table.csv")

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


def _compression_metadata_complete(row: dict[str, Any]) -> bool:
    if not all(field in row and row.get(field) is not None for field in COMPRESSED_METADATA_FIELDS):
        return False
    return row.get("actual_compression_ratio") is not None or row.get("compression_ratio") is not None


def _metadata_missing_by_field(rows: list[dict[str, Any]]) -> dict[str, int]:
    missing = {
        field: sum(1 for row in rows if field not in row or row.get(field) is None)
        for field in COMPRESSED_METADATA_FIELDS
    }
    missing["actual_compression_ratio_or_compression_ratio"] = sum(
        1
        for row in rows
        if row.get("actual_compression_ratio") is None and row.get("compression_ratio") is None
    )
    return missing


def summarize_artifact(stage: str, condition: str, path: Path) -> dict[str, Any]:
    rows = load_jsonl(path)
    classifications: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows, start=1):
        classifications.append(
            classify_row(row, row_index=row_index, condition=condition, artifact=str(path))
        )

    generation_times = _numeric_values(rows, "generation_time_s")
    e2e_times = [
        float(row.get("generation_time_s", 0.0)) + float(row.get("t_compress_ms", 0.0)) / 1000.0
        for row in rows
        if isinstance(row.get("generation_time_s"), (int, float))
    ]

    protected_suffix_count = sum(1 for row in rows if row.get("protected_suffix_preserved") is True)
    final_preview_count = sum(1 for row in rows if _has_final_answer_instruction(row.get("final_prompt_preview")))
    final_tail_count = sum(1 for row in rows if _has_final_answer_instruction(row.get("final_prompt_tail_preview")))
    compressed_preview_count = sum(
        1 for row in rows if _has_final_answer_instruction(row.get("compressed_prompt_preview"))
    )
    generated_marker_count = sum(1 for row in rows if _has_generated_final_answer_marker(row.get("generated_text")))
    generated_present_count = sum(
        1 for row in rows if isinstance(row.get("generated_text"), str) and bool(row["generated_text"].strip())
    )
    metadata_complete_rows = sum(1 for row in rows if _compression_metadata_complete(row))

    return {
        "stage": stage,
        "condition": condition,
        "artifact": str(path),
        "rows": len(rows),
        "max_new_tokens": rows[0].get("max_new_tokens") if rows else None,
        "generated_text_present_count": generated_present_count,
        "protected_suffix_preserved_count": protected_suffix_count,
        "protected_suffix_preserved_rate": protected_suffix_count / len(rows) if rows else 0.0,
        "final_prompt_preview_has_instruction_count": final_preview_count,
        "final_prompt_tail_has_instruction_count": final_tail_count,
        "compressed_prompt_preview_has_instruction_count": compressed_preview_count,
        "generated_final_answer_marker_present_count": generated_marker_count,
        "numeric_extraction_match_count": sum(1 for item in classifications if item.get("numeric_match")),
        "exact_containment_count": sum(1 for item in classifications if item.get("exact_match")),
        "hit_max_new_tokens_count": sum(1 for row in rows if _hit_max_new_tokens(row)),
        "avg_output_tokens": _mean(_numeric_values(rows, "output_tokens")),
        "avg_generation_time_s": _mean(generation_times),
        "avg_e2e_time_s": _mean(e2e_times),
        "avg_t_compress_ms": _mean(_numeric_values(rows, "t_compress_ms")),
        "avg_tok_per_sec": _mean(_numeric_values(rows, "tok_per_sec", "tokens_per_second")),
        "avg_actual_compression_ratio": _mean(_numeric_values(rows, "actual_compression_ratio", "compression_ratio")),
        "compressed_metadata_complete_rows": metadata_complete_rows,
        "compressed_metadata_complete_rate": metadata_complete_rows / len(rows) if rows else 0.0,
        "metadata_missing_by_field": _metadata_missing_by_field(rows),
        "all_questions_preserved": all(row.get("question_preserved") is True for row in rows) if rows else False,
    }


def _compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "protected_suffix_preserved_count",
        "final_prompt_tail_has_instruction_count",
        "compressed_prompt_preview_has_instruction_count",
        "generated_final_answer_marker_present_count",
        "numeric_extraction_match_count",
        "exact_containment_count",
        "hit_max_new_tokens_count",
        "compressed_metadata_complete_rows",
    ]
    comparison = {f"{field.removesuffix('_count')}_delta": after[field] - before[field] for field in fields}
    comparison["avg_output_tokens_delta"] = after["avg_output_tokens"] - before["avg_output_tokens"]
    comparison["avg_generation_time_s_delta"] = after["avg_generation_time_s"] - before["avg_generation_time_s"]
    comparison["avg_e2e_time_s_delta"] = after["avg_e2e_time_s"] - before["avg_e2e_time_s"]
    comparison["numeric_extraction_improved"] = comparison["numeric_extraction_match_delta"] > 0
    comparison["suffix_survival_verified"] = after["protected_suffix_preserved_count"] == after["rows"] and after["rows"] > 0
    return comparison


def analyze_paths(
    *,
    before_paths: dict[str, Path] | None = None,
    after_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    before_paths = before_paths or TASK56_PATHS
    after_paths = after_paths or TASK59_PATHS

    before = {
        condition: summarize_artifact("task56_before_suffix_fix", condition, before_paths[condition])
        for condition in before_paths
    }
    after = {
        condition: summarize_artifact("task59_after_suffix_fix", condition, after_paths[condition])
        for condition in after_paths
    }
    comparisons = {
        condition: _compare(before[condition], after[condition])
        for condition in sorted(set(before) & set(after))
    }

    return {
        "task": "Task 59 tiny compressed GSM8K suffix verification",
        "status": "PASS" if all(item["suffix_survival_verified"] for item in comparisons.values()) else "PARTIAL",
        "claim_policy": "preliminary n=10 compressed-only GSM8K verification; no final correctness or speedup claim",
        "artifacts": {
            "task56_before_suffix_fix": before,
            "task59_after_suffix_fix": after,
        },
        "comparisons": comparisons,
    }


def write_csv(summary: dict[str, Any], path: Path) -> None:
    fields = [
        "stage",
        "condition",
        "rows",
        "protected_suffix_preserved_count",
        "final_prompt_tail_has_instruction_count",
        "compressed_prompt_preview_has_instruction_count",
        "generated_final_answer_marker_present_count",
        "numeric_extraction_match_count",
        "exact_containment_count",
        "hit_max_new_tokens_count",
        "avg_output_tokens",
        "avg_generation_time_s",
        "avg_e2e_time_s",
        "avg_t_compress_ms",
        "avg_tok_per_sec",
        "avg_actual_compression_ratio",
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 59 GSM8K suffix verification artifacts")
    parser.add_argument("--output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_OUTPUT))
    args = parser.parse_args()

    summary = analyze_paths()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(summary, Path(args.csv))

    print(f"status={summary['status']}")
    for stage, artifacts in summary["artifacts"].items():
        for condition, artifact in artifacts.items():
            print(
                f"{stage} {condition} rows={artifact['rows']} "
                f"suffix={artifact['protected_suffix_preserved_count']} "
                f"tail_instruction={artifact['final_prompt_tail_has_instruction_count']} "
                f"generated_marker={artifact['generated_final_answer_marker_present_count']} "
                f"numeric={artifact['numeric_extraction_match_count']} "
                f"hit_cap={artifact['hit_max_new_tokens_count']} "
                f"metadata_complete={artifact['compressed_metadata_complete_rows']}"
            )
    for condition, comparison in summary["comparisons"].items():
        print(
            f"compare {condition}: suffix_delta={comparison['protected_suffix_preserved_delta']} "
            f"generated_marker_delta={comparison['generated_final_answer_marker_present_delta']} "
            f"numeric_delta={comparison['numeric_extraction_match_delta']} "
            f"hit_cap_delta={comparison['hit_max_new_tokens_delta']}"
        )


if __name__ == "__main__":
    main()
