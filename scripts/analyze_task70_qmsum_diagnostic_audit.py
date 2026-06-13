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


DEFAULT_ARTIFACTS = {
    "Baseline-AR": Path("results/task51_qmsum_long_baseline_ar_n10.jsonl"),
    "DFlash-R1": Path("results/task51_qmsum_long_dflash_r1_n10.jsonl"),
    "LLMLingua-AR-R2": Path("results/task51_qmsum_long_llmlingua_ar_r2_n10.jsonl"),
    "CC-DFlash-R2": Path("results/task51_qmsum_long_cc_dflash_r2_n10.jsonl"),
}
DEFAULT_SUMMARY_OUTPUT = Path("results/task70_qmsum_diagnostic_summary.json")
DEFAULT_TABLE_OUTPUT = Path("results/task70_qmsum_diagnostic_table.csv")
DEFAULT_CASES_OUTPUT = Path("results/task70_qmsum_failure_samples.jsonl")
WORD_RE = re.compile(r"[a-z0-9]+")


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


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def _numeric_values(rows: list[dict[str, Any]], *field_names: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        for field_name in field_names:
            value = row.get(field_name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(float(value))
                break
    return values


def _tokens(text: Any) -> list[str]:
    if not isinstance(text, str):
        return []
    return WORD_RE.findall(text.lower())


def normalized_token_overlap(expected: Any, generated: Any) -> float:
    expected_tokens = {token for token in _tokens(expected) if len(token) > 2}
    generated_tokens = {token for token in _tokens(generated) if len(token) > 2}
    if not expected_tokens:
        return 0.0
    return len(expected_tokens & generated_tokens) / len(expected_tokens)


def _normalized_contains(expected: Any, generated: Any) -> bool:
    expected_norm = " ".join(_tokens(expected))
    generated_norm = " ".join(_tokens(generated))
    if not expected_norm or not generated_norm:
        return False
    return expected_norm in generated_norm


def has_repetition(text: Any) -> bool:
    tokens = _tokens(text)
    if len(tokens) < 8:
        return False
    counts = Counter(tokens)
    most_common_rate = counts.most_common(1)[0][1] / len(tokens)
    unique_rate = len(counts) / len(tokens)
    return most_common_rate >= 0.45 or unique_rate <= 0.25


def _hit_cap(row: dict[str, Any]) -> bool:
    output_tokens = row.get("output_tokens")
    max_new_tokens = row.get("max_new_tokens")
    return (
        isinstance(output_tokens, (int, float))
        and not isinstance(output_tokens, bool)
        and isinstance(max_new_tokens, (int, float))
        and not isinstance(max_new_tokens, bool)
        and output_tokens >= max_new_tokens
    )


def _compact(text: Any, limit: int = 320) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def _e2e_times(rows: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for row in rows:
        generation_time = row.get("generation_time_s")
        if not isinstance(generation_time, (int, float)) or isinstance(generation_time, bool):
            continue
        compress_ms = row.get("t_compress_ms")
        compress_s = float(compress_ms) / 1000.0 if isinstance(compress_ms, (int, float)) else 0.0
        values.append(float(generation_time) + compress_s)
    return values


def _schema_presence(rows: list[dict[str, Any]]) -> dict[str, int]:
    fields = [
        "dataset_name",
        "condition",
        "prompt_id",
        "fixture_id",
        "expected_answer",
        "generated_text",
        "max_new_tokens",
        "output_tokens",
        "generation_time_s",
        "tok_per_sec",
        "tokens_per_second",
        "t_compress_ms",
        "t_prefill_ms",
        "R_actual",
        "original_input_tokens",
        "compressed_input_tokens",
    ]
    return {field: sum(1 for row in rows if field in row and row.get(field) is not None) for field in fields}


def _condition_summary(condition: str, rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    overlaps = [normalized_token_overlap(row.get("expected_answer"), row.get("generated_text")) for row in rows]
    hit_cap_count = sum(1 for row in rows if _hit_cap(row))
    empty_count = sum(
        1 for row in rows if not isinstance(row.get("generated_text"), str) or not row["generated_text"].strip()
    )
    repetition_count = sum(1 for row in rows if has_repetition(row.get("generated_text")))
    containment_count = sum(1 for row in rows if _normalized_contains(row.get("expected_answer"), row.get("generated_text")))
    low_overlap_count = sum(1 for overlap in overlaps if overlap < 0.2)
    malformed_count = sum(
        1
        for row in rows
        if not isinstance(row.get("generated_text"), str)
        or len(_tokens(row.get("generated_text"))) < 5
    )
    output_tokens = _numeric_values(rows, "output_tokens")
    generation_times = _numeric_values(rows, "generation_time_s")
    e2e_times = _e2e_times(rows)
    total_output = sum(output_tokens)
    total_generation_time = sum(generation_times)
    total_e2e_time = sum(e2e_times)
    max_new_values = sorted({int(v) for v in _numeric_values(rows, "max_new_tokens")})

    cases: list[dict[str, Any]] = []
    for row, overlap in zip(rows, overlaps, strict=True):
        case_types: list[str] = []
        if not isinstance(row.get("generated_text"), str) or not row["generated_text"].strip():
            case_types.append("EMPTY_OUTPUT")
        if overlap < 0.2:
            case_types.append("LOW_OVERLAP")
        if has_repetition(row.get("generated_text")):
            case_types.append("REPETITION")
        if _hit_cap(row):
            case_types.append("HIT_CAP")
        for case_type in case_types:
            cases.append(
                {
                    "case_type": case_type,
                    "condition": condition,
                    "prompt_id": row.get("prompt_id"),
                    "fixture_id": row.get("fixture_id"),
                    "expected_answer": _compact(row.get("expected_answer"), 220),
                    "generated_text_snippet": _compact(row.get("generated_text"), 360),
                    "overlap": round(overlap, 6),
                    "output_tokens": row.get("output_tokens"),
                    "max_new_tokens": row.get("max_new_tokens"),
                }
            )

    summary = {
        "condition": condition,
        "rows": len(rows),
        "schema_presence": _schema_presence(rows),
        "dataset_names": sorted({row.get("dataset_name") for row in rows if row.get("dataset_name")}),
        "generated_text_present_count": len(rows) - empty_count,
        "max_new_tokens_values": max_new_values,
        "empty_output_count": empty_count,
        "repetition_count": repetition_count,
        "malformed_output_count": malformed_count,
        "hit_cap_count": hit_cap_count,
        "hit_cap_rate": round(hit_cap_count / len(rows), 6) if rows else 0.0,
        "normalized_containment_count": containment_count,
        "normalized_containment_rate": round(containment_count / len(rows), 6) if rows else 0.0,
        "low_overlap_count": low_overlap_count,
        "avg_answer_token_overlap": round(_mean(overlaps), 6),
        "median_answer_token_overlap": round(_median(overlaps), 6),
        "avg_input_tokens": _mean(_numeric_values(rows, "input_tokens")),
        "avg_output_tokens": _mean(output_tokens),
        "avg_generation_latency_s": _mean(generation_times),
        "avg_e2e_latency_s": _mean(e2e_times),
        "avg_t_compress_ms": _mean(_numeric_values(rows, "t_compress_ms")),
        "avg_t_prefill_ms": _mean(_numeric_values(rows, "t_prefill_ms")),
        "avg_tok_per_sec": _mean(_numeric_values(rows, "tok_per_sec", "tokens_per_second")),
        "generation_tok_per_sec_weighted": total_output / total_generation_time if total_generation_time else 0.0,
        "e2e_tok_per_sec_weighted": total_output / total_e2e_time if total_e2e_time else 0.0,
        "avg_tau_mean": _mean(_numeric_values(rows, "tau_mean")),
        "avg_compression_ratio": _mean(_numeric_values(rows, "actual_compression_ratio", "compression_ratio", "R_actual")),
        "avg_original_input_tokens": _mean(_numeric_values(rows, "original_input_tokens")),
        "avg_compressed_input_tokens": _mean(_numeric_values(rows, "compressed_input_tokens")),
        "max_vram_allocated_gib": max(_numeric_values(rows, "vram_allocated_gib"), default=0.0),
        "max_vram_reserved_gib": max(_numeric_values(rows, "vram_reserved_gib"), default=0.0),
    }
    return summary, cases


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _compare(by_condition: dict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline = by_condition["Baseline-AR"]
    dflash = by_condition["DFlash-R1"]
    llm = by_condition["LLMLingua-AR-R2"]
    cc = by_condition["CC-DFlash-R2"]
    return {
        "baseline_vs_dflash": {
            "dflash_overlap_delta": round(
                dflash["avg_answer_token_overlap"] - baseline["avg_answer_token_overlap"], 6
            ),
            "dflash_hit_cap_delta": dflash["hit_cap_count"] - baseline["hit_cap_count"],
            "dflash_generation_speedup_ratio": _ratio(
                dflash["generation_tok_per_sec_weighted"], baseline["generation_tok_per_sec_weighted"]
            ),
            "dflash_e2e_speedup_ratio": _ratio(
                dflash["e2e_tok_per_sec_weighted"], baseline["e2e_tok_per_sec_weighted"]
            ),
        },
        "compressed_pair": {
            "cc_dflash_overlap_delta": round(
                cc["avg_answer_token_overlap"] - llm["avg_answer_token_overlap"], 6
            ),
            "cc_dflash_hit_cap_delta": cc["hit_cap_count"] - llm["hit_cap_count"],
            "cc_dflash_generation_speedup_ratio": _ratio(
                cc["generation_tok_per_sec_weighted"], llm["generation_tok_per_sec_weighted"]
            ),
            "cc_dflash_e2e_speedup_ratio": _ratio(
                cc["e2e_tok_per_sec_weighted"], llm["e2e_tok_per_sec_weighted"]
            ),
        },
        "uncompressed_vs_compressed": {
            "baseline_overlap_minus_llmlingua": round(
                baseline["avg_answer_token_overlap"] - llm["avg_answer_token_overlap"], 6
            ),
            "dflash_overlap_minus_cc_dflash": round(
                dflash["avg_answer_token_overlap"] - cc["avg_answer_token_overlap"], 6
            ),
            "compressed_avg_t_compress_ms": _mean([llm["avg_t_compress_ms"], cc["avg_t_compress_ms"]]),
        },
    }


def _readiness(by_condition: dict[str, dict[str, Any]]) -> dict[str, Any]:
    conditions_present = set(by_condition)
    full_matrix = conditions_present == {"Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-DFlash-R2"}
    row_counts = {condition: item["rows"] for condition, item in by_condition.items()}
    generated_text_complete = all(
        item["generated_text_present_count"] == item["rows"] for item in by_condition.values()
    )
    max_new_complete = all(
        item["schema_presence"]["max_new_tokens"] == item["rows"] for item in by_condition.values()
    )
    max_new_values = sorted(
        {value for item in by_condition.values() for value in item.get("max_new_tokens_values", [])}
    )
    n10_only = full_matrix and all(count == 10 for count in row_counts.values())
    stale_mnt32 = max_new_values == [32]
    if not generated_text_complete or not max_new_complete:
        reason = "MISSING_GENERATED_TEXT_OR_MNT_METADATA"
    elif n10_only and stale_mnt32:
        reason = "STALE_MNT32_AND_N10_ONLY"
    elif n10_only:
        reason = "N10_ONLY"
    else:
        reason = "SUFFICIENT_FOR_DIAGNOSTIC"
    return {
        "has_full_task51_n10_matrix": full_matrix and all(count >= 10 for count in row_counts.values()),
        "row_counts": row_counts,
        "generated_text_complete": generated_text_complete,
        "max_new_tokens_complete": max_new_complete,
        "max_new_tokens_values": max_new_values,
        "sufficient_for_read_only_diagnostic": generated_text_complete and max_new_complete and full_matrix,
        "sufficient_for_current_qmsum_benchmark_policy": reason == "SUFFICIENT_FOR_DIAGNOSTIC",
        "fresh_qmsum_n30_needed": reason != "SUFFICIENT_FOR_DIAGNOSTIC",
        "reason": reason,
    }


def _inventory() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(Path("results").glob("*qmsum*jsonl")):
        rows = load_jsonl(path)
        items.append(
            {
                "path": str(path),
                "rows": len(rows),
                "conditions": sorted({row.get("condition") for row in rows if row.get("condition")}),
                "max_new_tokens_values": sorted({int(v) for v in _numeric_values(rows, "max_new_tokens")}),
                "generated_text_present_count": sum(
                    1 for row in rows if isinstance(row.get("generated_text"), str) and row["generated_text"].strip()
                ),
            }
        )
    return items


def analyze_rows(rows_by_condition: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    by_condition: dict[str, dict[str, Any]] = {}
    cases: list[dict[str, Any]] = []
    for condition in ("Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-DFlash-R2"):
        condition_summary, condition_cases = _condition_summary(condition, rows_by_condition[condition])
        by_condition[condition] = condition_summary
        cases.extend(condition_cases)
    table = [by_condition[condition] for condition in ("Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-DFlash-R2")]
    readiness = _readiness(by_condition)
    gsm8k_style = {
        "qmsum_tests_gsm8k_arithmetic_failure": False,
        "assessment": (
            "QMSum-style meeting QA is long-answer summarization/lookup, not numeric arithmetic. "
            "It can audit long-context generation health, truncation, overlap, and speed, but not GSM8K-style math failure."
        ),
    }
    recommendation = (
        "Run fresh Task 71 QMSum n=30 with stored generated_text and a larger output budget before larger runs."
        if readiness["fresh_qmsum_n30_needed"]
        else "Existing artifacts are enough for the current diagnostic; no immediate rerun required."
    )
    summary = {
        "task": "Task 70 QMSum diagnostic audit",
        "status": "PASS_WITH_NOTES",
        "artifact_inventory": _inventory(),
        "by_condition": by_condition,
        "artifact_readiness": readiness,
        "comparisons": _compare(by_condition),
        "gsm8k_style_failure_assessment": gsm8k_style,
        "fresh_qmsum_run_needed": readiness["fresh_qmsum_n30_needed"],
        "recommended_task71_plan": recommendation,
        "claim_policy": "Smoke/preliminary diagnostic only; no final speedup or semantic correctness claim.",
    }
    return summary, table, cases


def _load_default_rows() -> dict[str, list[dict[str, Any]]]:
    rows_by_condition: dict[str, list[dict[str, Any]]] = {}
    for condition, path in DEFAULT_ARTIFACTS.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing required Task 51 QMSum artifact: {path}")
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
        "avg_compression_ratio",
        "max_vram_allocated_gib",
        "max_vram_reserved_gib",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit existing QMSum smoke artifacts for Task 70.")
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--table-output", type=Path, default=DEFAULT_TABLE_OUTPUT)
    parser.add_argument("--cases-output", type=Path, default=DEFAULT_CASES_OUTPUT)
    args = parser.parse_args(argv)

    rows_by_condition = _load_default_rows()
    summary, table, cases = analyze_rows(rows_by_condition)
    _write_json(args.summary_output, summary)
    _write_csv(args.table_output, table)
    _write_jsonl(args.cases_output, cases)

    print(json.dumps(
        {
            "status": summary["status"],
            "fresh_qmsum_run_needed": summary["fresh_qmsum_run_needed"],
            "readiness_reason": summary["artifact_readiness"]["reason"],
            "summary_output": str(args.summary_output),
            "table_output": str(args.table_output),
            "cases_output": str(args.cases_output),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
