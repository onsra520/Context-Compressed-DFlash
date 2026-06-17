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


TASK51_PATHS = {
    "Baseline-AR": Path("results/task51_gsm8k_short_baseline_ar_n10.jsonl"),
    "DFlash-R1": Path("results/task51_gsm8k_short_dflash_r1_n10.jsonl"),
    "LLMLingua-AR-R2": Path("results/task51_gsm8k_short_llmlingua_ar_r2_n10.jsonl"),
    "CC-DFlash-R2": Path("results/task51_gsm8k_short_cc_dflash_r2_n10.jsonl"),
}
TASK53_PATHS = {
    "Baseline-AR": Path("results/task53_gsm8k_short_baseline_ar_n10_mnt128.jsonl"),
    "DFlash-R1": Path("results/task53_gsm8k_short_dflash_r1_n10_mnt128.jsonl"),
    "LLMLingua-AR-R2": Path("results/task53_gsm8k_short_llmlingua_ar_r2_n10_mnt128.jsonl"),
    "CC-DFlash-R2": Path("results/task53_gsm8k_short_cc_dflash_r2_n10_mnt128.jsonl"),
}
DEFAULT_JSON_OUTPUT = Path("results/task53_gsm8k_quality_calibration_summary.json")
DEFAULT_CSV_OUTPUT = Path("results/task53_gsm8k_quality_calibration_table.csv")


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


def summarize_artifact(stage: str, condition: str, path: Path) -> dict[str, Any]:
    rows = load_jsonl(path)
    labels: Counter[str] = Counter()
    classifications: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows, start=1):
        classified = classify_row(
            row,
            row_index=row_index,
            condition=condition,
            artifact=str(path),
        )
        classifications.append(classified)
        labels[classified["failure_type"]] += 1

    exact_count = sum(1 for item in classifications if item["exact_match"])
    numeric_count = sum(1 for item in classifications if item["numeric_match"])
    truncated_count = sum(1 for item in classifications if item["truncated_or_stopped_early"])
    generated_present = sum(1 for row in rows if isinstance(row.get("generated_text"), str) and row["generated_text"].strip())
    t_compress_values = numeric_values(rows, "t_compress_ms")
    generation_times = numeric_values(rows, "generation_time_s")
    output_tokens = numeric_values(rows, "output_tokens")
    e2e_times = [
        float(row.get("generation_time_s", 0.0)) + float(row.get("t_compress_ms", 0.0)) / 1000.0
        for row in rows
        if isinstance(row.get("generation_time_s"), (int, float))
    ]

    return {
        "stage": stage,
        "condition": condition,
        "artifact": str(path),
        "rows": len(rows),
        "max_new_tokens": rows[0].get("max_new_tokens") if rows else None,
        "generated_text_present": generated_present,
        "exact_match_count": exact_count,
        "numeric_match_count": numeric_count,
        "truncated_or_stopped_early_count": truncated_count,
        "failure_type_counts": dict(sorted(labels.items())),
        "avg_output_tokens": mean(output_tokens),
        "avg_generation_time_s": mean(generation_times),
        "avg_tok_per_sec": mean(numeric_values(rows, "tok_per_sec")),
        "avg_e2e_time_s": mean(e2e_times),
        "e2e_tok_per_sec": sum(output_tokens) / sum(e2e_times) if e2e_times and sum(e2e_times) else 0.0,
        "avg_t_compress_ms": mean(t_compress_values),
        "avg_t_prefill_ms": mean(numeric_values(rows, "t_prefill_ms")),
        "avg_tau_mean": mean(numeric_values(rows, "tau_mean")),
        "max_vram_reserved_gib": max(numeric_values(rows, "vram_reserved_gib"), default=0.0),
    }


def analyze() -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    for condition, path in TASK51_PATHS.items():
        artifacts.append(summarize_artifact("task51_mnt32", condition, path))
    for condition, path in TASK53_PATHS.items():
        artifacts.append(summarize_artifact("task53_mnt128", condition, path))

    by_stage_condition = {(item["stage"], item["condition"]): item for item in artifacts}
    comparisons: dict[str, dict[str, Any]] = {}
    for condition in TASK53_PATHS:
        old = by_stage_condition[("task51_mnt32", condition)]
        new = by_stage_condition[("task53_mnt128", condition)]
        comparisons[condition] = {
            "exact_match_delta": new["exact_match_count"] - old["exact_match_count"],
            "numeric_match_delta": new["numeric_match_count"] - old["numeric_match_count"],
            "truncated_count_delta": new["truncated_or_stopped_early_count"] - old["truncated_or_stopped_early_count"],
            "avg_output_tokens_delta": new["avg_output_tokens"] - old["avg_output_tokens"],
            "avg_generation_time_ratio": (
                new["avg_generation_time_s"] / old["avg_generation_time_s"]
                if old["avg_generation_time_s"]
                else None
            ),
            "avg_e2e_time_ratio": new["avg_e2e_time_s"] / old["avg_e2e_time_s"] if old["avg_e2e_time_s"] else None,
        }

    return {
        "task": "Task 53 GSM8K quality calibration",
        "status": "PASS",
        "claim_policy": "preliminary smoke-level calibration only; no final correctness or speedup claim",
        "artifacts": artifacts,
        "comparisons": comparisons,
    }


def write_csv(summary: dict[str, Any], path: Path) -> None:
    fields = [
        "stage",
        "condition",
        "rows",
        "max_new_tokens",
        "exact_match_count",
        "numeric_match_count",
        "truncated_or_stopped_early_count",
        "avg_output_tokens",
        "avg_generation_time_s",
        "avg_tok_per_sec",
        "avg_e2e_time_s",
        "e2e_tok_per_sec",
        "avg_t_compress_ms",
        "avg_t_prefill_ms",
        "avg_tau_mean",
        "max_vram_reserved_gib",
        "artifact",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for artifact in summary["artifacts"]:
            writer.writerow({field: artifact.get(field) for field in fields})


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Task 51 GSM8K max_new_tokens=32 to Task 53 max_new_tokens=128")
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
            f"max_new_tokens={artifact['max_new_tokens']} exact={artifact['exact_match_count']} "
            f"numeric={artifact['numeric_match_count']} truncated={artifact['truncated_or_stopped_early_count']} "
            f"avg_generation_time_s={artifact['avg_generation_time_s']:.2f}"
        )
    for condition, comparison in summary["comparisons"].items():
        print(
            f"compare {condition}: exact_delta={comparison['exact_match_delta']} "
            f"numeric_delta={comparison['numeric_match_delta']} "
            f"generation_time_ratio={comparison['avg_generation_time_ratio']:.2f}"
        )


if __name__ == "__main__":
    main()
