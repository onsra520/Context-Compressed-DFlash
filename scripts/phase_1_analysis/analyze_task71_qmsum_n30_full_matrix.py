from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_task70_qmsum_diagnostic_audit import (
    _compare,
    _condition_summary,
    load_jsonl,
)


DEFAULT_ARTIFACTS = {
    "Baseline-AR": Path("results/task71_qmsum_long_baseline_ar_n30_mnt384.jsonl"),
    "DFlash-R1": Path("results/task71_qmsum_long_dflash_r1_n30_mnt384.jsonl"),
    "LLMLingua-AR-R2": Path("results/task71_qmsum_long_llmlingua_ar_r2_n30_mnt384.jsonl"),
    "CC-DFlash-R2": Path("results/task71_qmsum_long_cc_dflash_r2_n30_mnt384.jsonl"),
}
DEFAULT_TASK70_SUMMARY = Path("results/task70_qmsum_diagnostic_summary.json")
DEFAULT_SUMMARY_OUTPUT = Path("results/task71_qmsum_n30_full_matrix_summary.json")
DEFAULT_TABLE_OUTPUT = Path("results/task71_qmsum_n30_full_matrix_table.csv")
DEFAULT_CASES_OUTPUT = Path("results/task71_qmsum_n30_failure_samples.jsonl")


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _load_task70_cap_rate(path: Path = DEFAULT_TASK70_SUMMARY) -> float | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    conditions = data.get("by_condition", {})
    rates: list[float] = []
    for item in conditions.values():
        value = item.get("hit_cap_rate")
        if isinstance(value, (int, float)):
            rates.append(float(value))
    return _mean(rates) if rates else None


def _cap_decision(table: list[dict[str, Any]], old_cap_rate: float | None) -> dict[str, Any]:
    current_rate = _mean([float(row.get("hit_cap_rate", 0.0)) for row in table])
    max_new_values = sorted({value for row in table for value in row.get("max_new_tokens_values", [])})
    if old_cap_rate is None:
        reduced = current_rate < 1.0 and max_new_values == [384]
    else:
        reduced = current_rate < old_cap_rate
    return {
        "old_task70_avg_hit_cap_rate": old_cap_rate,
        "task71_avg_hit_cap_rate": round(current_rate, 6),
        "max_new_tokens_values": max_new_values,
        "mnt384_reduced_cap_pressure": reduced,
        "interpretation": (
            "mnt384 reduced cap pressure versus Task 51/70 mnt32"
            if reduced
            else "mnt384 did not eliminate cap pressure; inspect long-answer output policy before n=100"
        ),
    }


def _n100_decision(table: list[dict[str, Any]]) -> dict[str, Any]:
    avg_cap_rate = _mean([float(row.get("hit_cap_rate", 0.0)) for row in table])
    compressed_rows = [row for row in table if row["condition"] in {"LLMLingua-AR-R2", "CC-DFlash-R2"}]
    compressed_overlap = _mean([float(row.get("avg_answer_token_overlap", 0.0)) for row in compressed_rows])
    has_n30_matrix = all(int(row.get("rows", 0)) >= 30 for row in table)
    justified = has_n30_matrix and avg_cap_rate <= 0.10 and compressed_overlap >= 0.20
    return {
        "justified_next": justified,
        "has_n30_matrix": has_n30_matrix,
        "reason": (
            "Cap pressure is low enough for a larger QMSum follow-up"
            if justified
            else "Do not jump to QMSum n=100; cap pressure/proxy quality still needs interpretation"
        ),
    }


def _compressed_metadata_summary(by_condition: dict[str, dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for condition in ("LLMLingua-AR-R2", "CC-DFlash-R2"):
        item = by_condition[condition]
        schema = item["schema_presence"]
        summary[condition] = {
            "rows": item["rows"],
            "keep_rate_present": schema.get("keep_rate", 0),
            "t_compress_ms_present": schema.get("t_compress_ms", 0),
            "original_input_tokens_present": schema.get("original_input_tokens", 0),
            "compressed_input_tokens_present": schema.get("compressed_input_tokens", 0),
            "compression_ratio_present": schema.get("R_actual", 0),
            "generated_text_present": item["generated_text_present_count"],
            "avg_compression_ratio": item["avg_compression_ratio"],
            "avg_original_input_tokens": item["avg_original_input_tokens"],
            "avg_compressed_input_tokens": item["avg_compressed_input_tokens"],
        }
    return summary


def analyze_rows(
    rows_by_condition: dict[str, list[dict[str, Any]]],
    *,
    task70_summary_path: Path = DEFAULT_TASK70_SUMMARY,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    by_condition: dict[str, dict[str, Any]] = {}
    cases: list[dict[str, Any]] = []
    for condition in ("Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-DFlash-R2"):
        condition_summary, condition_cases = _condition_summary(condition, rows_by_condition[condition])
        by_condition[condition] = condition_summary
        cases.extend(condition_cases)

    table = [by_condition[condition] for condition in ("Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-DFlash-R2")]
    old_cap_rate = _load_task70_cap_rate(task70_summary_path)
    comparisons = _compare(by_condition)
    compressed_pair = comparisons["compressed_pair"]
    quality_gap = comparisons["uncompressed_vs_compressed"]
    cc_beats_llm_e2e = compressed_pair["cc_dflash_e2e_speedup_ratio"] > 1.0
    cc_quality_similar = abs(compressed_pair["cc_dflash_overlap_delta"]) <= 0.05

    summary = {
        "task": "Task 71 QMSum n=30 full matrix",
        "status": "PASS_WITH_NOTES",
        "by_condition": by_condition,
        "comparisons": comparisons,
        "compressed_metadata": _compressed_metadata_summary(by_condition),
        "old_mnt32_problem": _cap_decision(table, old_cap_rate),
        "gsm8k_style_failure_assessment": {
            "qmsum_shows_gsm8k_arithmetic_failure_pattern": False,
            "assessment": (
                "QMSum is non-math long-answer meeting QA. It can reveal truncation, output sanity, overlap, "
                "and long-context speed behavior, but not GSM8K-style arithmetic failures."
            ),
        },
        "cc_dflash_vs_llmlingua_ar": {
            "cc_dflash_beats_llmlingua_ar_on_e2e_speed": cc_beats_llm_e2e,
            "cc_dflash_e2e_speedup_ratio": compressed_pair["cc_dflash_e2e_speedup_ratio"],
            "cc_dflash_matches_llmlingua_ar_proxy_quality": cc_quality_similar,
            "overlap_delta": compressed_pair["cc_dflash_overlap_delta"],
        },
        "compressed_vs_uncompressed_quality_proxy_gap": quality_gap,
        "n100_decision": _n100_decision(table),
        "claim_policy": "Preliminary QMSum diagnostic only; no final speedup or semantic correctness claim.",
    }
    return summary, table, cases


def _load_default_rows() -> dict[str, list[dict[str, Any]]]:
    rows_by_condition: dict[str, list[dict[str, Any]]] = {}
    for condition, path in DEFAULT_ARTIFACTS.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing Task 71 artifact for {condition}: {path}")
        rows_by_condition[condition] = load_jsonl(path)
    return rows_by_condition


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "condition",
        "rows",
        "avg_answer_token_overlap",
        "normalized_containment_count",
        "empty_output_count",
        "repetition_count",
        "hit_cap_count",
        "avg_input_tokens",
        "avg_output_tokens",
        "avg_generation_latency_s",
        "avg_e2e_latency_s",
        "avg_t_compress_ms",
        "avg_t_prefill_ms",
        "generation_tok_per_sec_weighted",
        "e2e_tok_per_sec_weighted",
        "avg_tau_mean",
        "avg_compression_ratio",
        "avg_original_input_tokens",
        "avg_compressed_input_tokens",
        "max_vram_allocated_gib",
        "max_vram_reserved_gib",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze Task 71 QMSum n=30 full matrix artifacts.")
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--table-output", type=Path, default=DEFAULT_TABLE_OUTPUT)
    parser.add_argument("--cases-output", type=Path, default=DEFAULT_CASES_OUTPUT)
    args = parser.parse_args(argv)

    summary, table, cases = analyze_rows(_load_default_rows())
    _write_json(args.summary_output, summary)
    _write_csv(args.table_output, table)
    _write_jsonl(args.cases_output, cases)
    print(json.dumps(
        {
            "status": summary["status"],
            "n100_justified_next": summary["n100_decision"]["justified_next"],
            "cc_beats_llmlingua_ar_e2e": summary["cc_dflash_vs_llmlingua_ar"]["cc_dflash_beats_llmlingua_ar_on_e2e_speed"],
            "cc_matches_llmlingua_proxy_quality": summary["cc_dflash_vs_llmlingua_ar"]["cc_dflash_matches_llmlingua_ar_proxy_quality"],
            "summary_output": str(args.summary_output),
            "table_output": str(args.table_output),
            "cases_output": str(args.cases_output),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
