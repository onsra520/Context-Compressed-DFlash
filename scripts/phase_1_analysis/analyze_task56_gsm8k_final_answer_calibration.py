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

from scripts.phase_1_analysis.analyze_task47_quality_refinement import classify_row, extract_numeric_answer


CONDITIONS = ["Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-DFlash-R2"]
TASK53_PATHS = {
    "Baseline-AR": Path("results/task53_gsm8k_short_baseline_ar_n10_mnt128.jsonl"),
    "DFlash-R1": Path("results/task53_gsm8k_short_dflash_r1_n10_mnt128.jsonl"),
    "LLMLingua-AR-R2": Path("results/task53_gsm8k_short_llmlingua_ar_r2_n10_mnt128.jsonl"),
    "CC-DFlash-R2": Path("results/task53_gsm8k_short_cc_dflash_r2_n10_mnt128.jsonl"),
}
TASK56_PATHS = {
    "Baseline-AR": Path("results/task56_gsm8k_short_baseline_ar_n10_mnt192.jsonl"),
    "DFlash-R1": Path("results/task56_gsm8k_short_dflash_r1_n10_mnt192.jsonl"),
    "LLMLingua-AR-R2": Path("results/task56_gsm8k_short_llmlingua_ar_r2_n10_mnt192.jsonl"),
    "CC-DFlash-R2": Path("results/task56_gsm8k_short_cc_dflash_r2_n10_mnt192.jsonl"),
}
DEFAULT_JSON_OUTPUT = Path("results/task56_gsm8k_final_answer_calibration_summary.json")
DEFAULT_CSV_OUTPUT = Path("results/task56_gsm8k_final_answer_calibration_table.csv")
FINAL_ANSWER_RE = re.compile(
    r"final\s+(?:numeric\s+)?answer\s*(?:is|=|:|：)\s*([-+]?\$?\d[\d,]*(?:\.\d+)?)",
    re.IGNORECASE,
)
COMPRESSED_CONDITIONS = {"LLMLingua-AR-R2", "CC-DFlash-R2"}
COMPRESSED_METADATA_FIELDS = [
    "keep_rate",
    "t_compress_ms",
    "N_original",
    "N_compressed",
    "R_actual",
    "original_input_tokens",
    "compressed_input_tokens",
    "compression_ratio",
    "actual_compression_ratio",
    "question_preserved",
    "original_context_preview",
    "compressed_context_preview",
    "original_prompt_preview",
    "compressed_prompt_preview",
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


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def numeric_values(rows: list[dict[str, Any]], field_name: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(field_name)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _has_final_answer_marker(text: str | None) -> bool:
    return isinstance(text, str) and bool(FINAL_ANSWER_RE.search(text))


def _final_answer_parse_success(text: str | None) -> bool:
    if not isinstance(text, str):
        return False
    if not FINAL_ANSWER_RE.search(text):
        return False
    extraction = extract_numeric_answer(text)
    return extraction.answer is not None and extraction.source == "marked_final_answer"


def _hit_max_new_tokens(row: dict[str, Any]) -> bool:
    output_tokens = row.get("output_tokens")
    max_new_tokens = row.get("max_new_tokens")
    return isinstance(output_tokens, (int, float)) and isinstance(max_new_tokens, (int, float)) and output_tokens >= max_new_tokens


def _metadata_presence(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "required_fields": COMPRESSED_METADATA_FIELDS,
            "complete_rows": 0,
            "complete_rate": 0.0,
            "missing_by_field": {field: 0 for field in COMPRESSED_METADATA_FIELDS},
        }
    missing_by_field = {
        field: sum(1 for row in rows if field not in row or row.get(field) is None)
        for field in COMPRESSED_METADATA_FIELDS
    }
    complete_rows = sum(
        1 for row in rows if all(field in row and row.get(field) is not None for field in COMPRESSED_METADATA_FIELDS)
    )
    return {
        "required_fields": COMPRESSED_METADATA_FIELDS,
        "complete_rows": complete_rows,
        "complete_rate": complete_rows / len(rows),
        "missing_by_field": missing_by_field,
        "all_questions_preserved": all(row.get("question_preserved") is True for row in rows),
    }


def summarize_artifact(stage: str, condition: str, path: Path) -> dict[str, Any]:
    rows = load_jsonl(path)
    classifications: list[dict[str, Any]] = []
    failure_counts: Counter[str] = Counter()
    marker_present_count = 0
    marker_parse_success_count = 0
    hit_cap_count = 0
    generated_present_count = 0

    for row_index, row in enumerate(rows, start=1):
        classified = classify_row(
            row,
            row_index=row_index,
            condition=condition,
            artifact=str(path),
        )
        classifications.append(classified)
        failure_counts[str(classified.get("failure_type"))] += 1
        generated_text = row.get("generated_text")
        generated_present_count += int(isinstance(generated_text, str) and bool(generated_text.strip()))
        marker_present_count += int(_has_final_answer_marker(generated_text))
        marker_parse_success_count += int(_final_answer_parse_success(generated_text))
        hit_cap_count += int(_hit_max_new_tokens(row))

    output_tokens = numeric_values(rows, "output_tokens")
    generation_times = numeric_values(rows, "generation_time_s")
    e2e_times = [
        float(row.get("generation_time_s", 0.0)) + float(row.get("t_compress_ms", 0.0)) / 1000.0
        for row in rows
        if isinstance(row.get("generation_time_s"), (int, float))
    ]
    total_output_tokens = sum(output_tokens)
    total_generation_time = sum(generation_times)
    total_e2e_time = sum(e2e_times)

    exact_count = sum(1 for item in classifications if item.get("exact_match"))
    numeric_count = sum(1 for item in classifications if item.get("numeric_match"))
    metadata_presence = _metadata_presence(rows) if condition in COMPRESSED_CONDITIONS else None

    return {
        "stage": stage,
        "condition": condition,
        "artifact": str(path),
        "rows": len(rows),
        "max_new_tokens": rows[0].get("max_new_tokens") if rows else None,
        "generated_text_present_count": generated_present_count,
        "exact_containment_count": exact_count,
        "numeric_extraction_match_count": numeric_count,
        "final_answer_marker_present_count": marker_present_count,
        "final_answer_marker_parse_success_count": marker_parse_success_count,
        "hit_max_new_tokens_count": hit_cap_count,
        "failure_type_counts": dict(sorted(failure_counts.items())),
        "avg_output_tokens": mean(output_tokens),
        "avg_generation_time_s": mean(generation_times),
        "avg_e2e_time_s": mean(e2e_times),
        "avg_tok_per_sec": mean(numeric_values(rows, "tok_per_sec")),
        "gen_tok_per_sec_weighted": total_output_tokens / total_generation_time if total_generation_time else 0.0,
        "e2e_tok_per_sec_weighted": total_output_tokens / total_e2e_time if total_e2e_time else 0.0,
        "avg_t_compress_ms": mean(numeric_values(rows, "t_compress_ms")),
        "avg_t_prefill_ms": mean(numeric_values(rows, "t_prefill_ms")),
        "avg_tau_mean": mean(numeric_values(rows, "tau_mean")),
        "avg_R_actual": mean(numeric_values(rows, "R_actual")),
        "avg_actual_compression_ratio": mean(numeric_values(rows, "actual_compression_ratio")),
        "max_vram_allocated_gib": max(numeric_values(rows, "vram_allocated_gib"), default=0.0),
        "max_vram_reserved_gib": max(numeric_values(rows, "vram_reserved_gib"), default=0.0),
        "compressed_metadata_presence": metadata_presence,
    }


def analyze() -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        artifacts.append(summarize_artifact("task53_mnt128", condition, TASK53_PATHS[condition]))
    for condition in CONDITIONS:
        artifacts.append(summarize_artifact("task56_mnt192", condition, TASK56_PATHS[condition]))

    by_key = {(item["stage"], item["condition"]): item for item in artifacts}
    comparisons: dict[str, dict[str, Any]] = {}
    for condition in CONDITIONS:
        old = by_key[("task53_mnt128", condition)]
        new = by_key[("task56_mnt192", condition)]
        comparisons[condition] = {
            "exact_containment_delta": new["exact_containment_count"] - old["exact_containment_count"],
            "numeric_extraction_match_delta": (
                new["numeric_extraction_match_count"] - old["numeric_extraction_match_count"]
            ),
            "final_answer_marker_present_delta": (
                new["final_answer_marker_present_count"] - old["final_answer_marker_present_count"]
            ),
            "final_answer_marker_parse_success_delta": (
                new["final_answer_marker_parse_success_count"] - old["final_answer_marker_parse_success_count"]
            ),
            "hit_max_new_tokens_delta": new["hit_max_new_tokens_count"] - old["hit_max_new_tokens_count"],
            "avg_output_tokens_delta": new["avg_output_tokens"] - old["avg_output_tokens"],
            "avg_generation_time_ratio": (
                new["avg_generation_time_s"] / old["avg_generation_time_s"]
                if old["avg_generation_time_s"]
                else None
            ),
            "avg_e2e_time_ratio": new["avg_e2e_time_s"] / old["avg_e2e_time_s"] if old["avg_e2e_time_s"] else None,
            "compressed_metadata_complete_rate": (
                new["compressed_metadata_presence"]["complete_rate"]
                if new["compressed_metadata_presence"] is not None
                else None
            ),
        }

    compressed_metadata_status = {
        condition: by_key[("task56_mnt192", condition)]["compressed_metadata_presence"]
        for condition in COMPRESSED_CONDITIONS
    }

    return {
        "task": "Task 56 GSM8K final-answer prompt calibration",
        "status": "PASS",
        "claim_policy": "preliminary n=10 GSM8K calibration only; no final correctness or speedup claim",
        "artifacts": artifacts,
        "comparisons": comparisons,
        "compressed_metadata_status": compressed_metadata_status,
    }


def write_csv(summary: dict[str, Any], path: Path) -> None:
    fields = [
        "stage",
        "condition",
        "rows",
        "max_new_tokens",
        "exact_containment_count",
        "numeric_extraction_match_count",
        "final_answer_marker_present_count",
        "final_answer_marker_parse_success_count",
        "hit_max_new_tokens_count",
        "avg_output_tokens",
        "avg_generation_time_s",
        "avg_e2e_time_s",
        "avg_tok_per_sec",
        "gen_tok_per_sec_weighted",
        "e2e_tok_per_sec_weighted",
        "avg_t_compress_ms",
        "avg_t_prefill_ms",
        "avg_tau_mean",
        "avg_R_actual",
        "avg_actual_compression_ratio",
        "max_vram_allocated_gib",
        "max_vram_reserved_gib",
        "compressed_metadata_complete_rate",
        "artifact",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for artifact in summary["artifacts"]:
            metadata = artifact.get("compressed_metadata_presence")
            row = dict(artifact)
            row["compressed_metadata_complete_rate"] = metadata["complete_rate"] if metadata else None
            writer.writerow({field: row.get(field) for field in fields})


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 56 GSM8K final-answer calibration artifacts")
    parser.add_argument("--output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_OUTPUT))
    args = parser.parse_args()

    summary = analyze()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(summary, Path(args.csv))

    print(f"status={summary['status']}")
    for artifact in summary["artifacts"]:
        print(
            f"{artifact['stage']} {artifact['condition']} rows={artifact['rows']} "
            f"max_new_tokens={artifact['max_new_tokens']} exact={artifact['exact_containment_count']} "
            f"numeric={artifact['numeric_extraction_match_count']} "
            f"final_marker={artifact['final_answer_marker_present_count']} "
            f"final_parse={artifact['final_answer_marker_parse_success_count']} "
            f"hit_cap={artifact['hit_max_new_tokens_count']} "
            f"avg_e2e_time_s={artifact['avg_e2e_time_s']:.2f}"
        )
    for condition, comparison in summary["comparisons"].items():
        print(
            f"compare {condition}: exact_delta={comparison['exact_containment_delta']} "
            f"numeric_delta={comparison['numeric_extraction_match_delta']} "
            f"final_marker_delta={comparison['final_answer_marker_present_delta']} "
            f"hit_cap_delta={comparison['hit_max_new_tokens_delta']}"
        )
    for condition, metadata in sorted(summary["compressed_metadata_status"].items()):
        print(
            f"metadata {condition}: complete_rows={metadata['complete_rows']} "
            f"complete_rate={metadata['complete_rate']:.2f} "
            f"questions_preserved={metadata['all_questions_preserved']}"
        )


if __name__ == "__main__":
    main()
