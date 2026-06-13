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


DEFAULT_ARTIFACTS = {
    "Baseline-AR": Path("results/task69_gsm8k_short_baseline_ar_n30_mnt384.jsonl"),
    "DFlash-R1": Path("results/task69_gsm8k_short_dflash_r1_n30_mnt384.jsonl"),
    "LLMLingua-AR-R2": Path("results/task66_gsm8k_short_llmlingua_ar_r2_n30_mnt384_rerun.jsonl"),
    "CC-DFlash-R2": Path("results/task66_gsm8k_short_cc_dflash_r2_n30_mnt384_rerun.jsonl"),
}
DEFAULT_SUMMARY_OUTPUT = Path("results/task69_gsm8k_full_matrix_summary.json")
DEFAULT_TABLE_OUTPUT = Path("results/task69_gsm8k_full_matrix_table.csv")
DEFAULT_FAILURE_OUTPUT = Path("results/task69_gsm8k_full_matrix_failure_samples.jsonl")
FINAL_ANSWER_RE = re.compile(r"final\s+(?:numeric\s+)?answer\s*(?:is|=|:|：)\s*[-+]?\$?\d", re.IGNORECASE)


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


def _numeric_values(rows: list[dict[str, Any]], *field_names: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        for field_name in field_names:
            value = row.get(field_name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(float(value))
                break
    return values


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


def _has_final_answer_marker(row: dict[str, Any]) -> bool:
    text = row.get("generated_text")
    return isinstance(text, str) and bool(FINAL_ANSWER_RE.search(text))


def _compact(text: Any, limit: int = 360) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def _condition_summary(condition: str, rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    classifications = [
        classify_row(row, row_index=index, condition=condition, artifact=f"{condition}.jsonl")
        for index, row in enumerate(rows, start=1)
    ]
    output_tokens = _numeric_values(rows, "output_tokens")
    generation_times = _numeric_values(rows, "generation_time_s")
    e2e_times = [
        float(row.get("generation_time_s", 0.0)) + float(row.get("t_compress_ms", 0.0)) / 1000.0
        for row in rows
        if isinstance(row.get("generation_time_s"), (int, float))
    ]
    total_output = sum(output_tokens)
    total_gen_time = sum(generation_times)
    total_e2e_time = sum(e2e_times)
    numeric_matches = sum(1 for item in classifications if item.get("numeric_match"))
    exact_matches = sum(1 for item in classifications if item.get("exact_match"))
    failures: list[dict[str, Any]] = []
    for row, classified in zip(rows, classifications, strict=True):
        if not classified.get("numeric_match"):
            failures.append(
                {
                    "condition": condition,
                    "prompt_id": row.get("prompt_id"),
                    "dataset_id": row.get("dataset_id"),
                    "expected_answer": row.get("expected_answer"),
                    "extracted_answer": classified.get("extracted_answer"),
                    "numeric_match": False,
                    "exact_match": bool(classified.get("exact_match")),
                    "hit_cap": _hit_cap(row),
                    "output_tokens": row.get("output_tokens"),
                    "max_new_tokens": row.get("max_new_tokens"),
                    "generated_text_snippet": _compact(row.get("generated_text")),
                }
            )
    compressed = condition in {"LLMLingua-AR-R2", "CC-DFlash-R2"}
    summary = {
        "condition": condition,
        "rows": len(rows),
        "numeric_matches": numeric_matches,
        "numeric_match_rate": round(numeric_matches / len(rows), 6) if rows else 0.0,
        "exact_containment_matches": exact_matches,
        "exact_containment_rate": round(exact_matches / len(rows), 6) if rows else 0.0,
        "final_answer_marker_count": sum(1 for row in rows if _has_final_answer_marker(row)),
        "hit_cap_count": sum(1 for row in rows if _hit_cap(row)),
        "avg_input_tokens": _mean(_numeric_values(rows, "input_tokens")),
        "avg_output_tokens": _mean(output_tokens),
        "avg_generation_latency_s": _mean(generation_times),
        "avg_e2e_latency_s": _mean(e2e_times),
        "avg_t_compress_ms": _mean(_numeric_values(rows, "t_compress_ms")),
        "avg_tau_mean": _mean(_numeric_values(rows, "tau_mean")),
        "avg_tok_per_sec": _mean(_numeric_values(rows, "tok_per_sec", "tok_per_s", "tokens_per_second")),
        "generation_tok_per_sec_weighted": total_output / total_gen_time if total_gen_time else 0.0,
        "e2e_tok_per_sec_weighted": total_output / total_e2e_time if total_e2e_time else 0.0,
        "avg_compression_ratio": _mean(_numeric_values(rows, "actual_compression_ratio", "compression_ratio", "R_actual")),
        "avg_original_input_tokens": _mean(_numeric_values(rows, "original_input_tokens")),
        "avg_compressed_input_tokens": _mean(_numeric_values(rows, "compressed_input_tokens")),
        "protected_suffix_preserved_count": sum(1 for row in rows if row.get("protected_suffix_preserved") is True),
        "question_preserved_count": sum(1 for row in rows if row.get("question_preserved") is True),
        "compressed_condition": compressed,
        "generated_text_present_count": sum(
            1 for row in rows if isinstance(row.get("generated_text"), str) and bool(row["generated_text"].strip())
        ),
    }
    return summary, failures


def _compare(summary: dict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline = summary["Baseline-AR"]
    dflash = summary["DFlash-R1"]
    llm = summary["LLMLingua-AR-R2"]
    cc = summary["CC-DFlash-R2"]
    uncompressed_best_rate = max(baseline["numeric_match_rate"], dflash["numeric_match_rate"])
    compressed_best_rate = max(llm["numeric_match_rate"], cc["numeric_match_rate"])
    if compressed_best_rate >= uncompressed_best_rate:
        acceptability = "MATCHES_OR_EXCEEDS_UNCOMPRESSED_BEST"
    elif compressed_best_rate >= uncompressed_best_rate - 0.10:
        acceptability = "WITHIN_10_POINTS_OF_UNCOMPRESSED_BEST"
    else:
        acceptability = "BELOW_UNCOMPRESSED_BEST"
    return {
        "baseline_vs_dflash": {
            "dflash_numeric_delta": dflash["numeric_matches"] - baseline["numeric_matches"],
            "dflash_e2e_speedup_ratio": (
                dflash["e2e_tok_per_sec_weighted"] / baseline["e2e_tok_per_sec_weighted"]
                if baseline["e2e_tok_per_sec_weighted"]
                else 0.0
            ),
            "dflash_generation_speedup_ratio": (
                dflash["generation_tok_per_sec_weighted"] / baseline["generation_tok_per_sec_weighted"]
                if baseline["generation_tok_per_sec_weighted"]
                else 0.0
            ),
        },
        "compressed_pair": {
            "cc_dflash_numeric_delta": cc["numeric_matches"] - llm["numeric_matches"],
            "quality_match": cc["numeric_matches"] == llm["numeric_matches"],
            "cc_dflash_beats_llmlingua_ar_on_e2e_speed": cc["e2e_tok_per_sec_weighted"] > llm["e2e_tok_per_sec_weighted"],
            "cc_dflash_e2e_speedup_ratio": (
                cc["e2e_tok_per_sec_weighted"] / llm["e2e_tok_per_sec_weighted"]
                if llm["e2e_tok_per_sec_weighted"]
                else 0.0
            ),
            "cc_dflash_generation_speedup_ratio": (
                cc["generation_tok_per_sec_weighted"] / llm["generation_tok_per_sec_weighted"]
                if llm["generation_tok_per_sec_weighted"]
                else 0.0
            ),
        },
        "quality_gap": {
            "uncompressed_best_numeric_rate": uncompressed_best_rate,
            "compressed_best_numeric_rate": compressed_best_rate,
            "compressed_quality_gap_to_best": round(compressed_best_rate - uncompressed_best_rate, 6),
            "compressed_quality_acceptability": acceptability,
        },
        "dflash_vs_cc_dflash": {
            "cc_dflash_numeric_delta_vs_dflash": cc["numeric_matches"] - dflash["numeric_matches"],
            "cc_dflash_e2e_speed_ratio_vs_dflash": (
                cc["e2e_tok_per_sec_weighted"] / dflash["e2e_tok_per_sec_weighted"]
                if dflash["e2e_tok_per_sec_weighted"]
                else 0.0
            ),
        },
    }


def analyze_rows(rows_by_condition: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    by_condition: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    for condition in ("Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-DFlash-R2"):
        condition_summary, condition_failures = _condition_summary(condition, rows_by_condition[condition])
        by_condition[condition] = condition_summary
        failures.extend(condition_failures)
    table = [by_condition[condition] for condition in ("Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-DFlash-R2")]
    comparisons = _compare(by_condition)
    n100_justified = (
        comparisons["compressed_pair"]["quality_match"]
        and comparisons["compressed_pair"]["cc_dflash_beats_llmlingua_ar_on_e2e_speed"]
        and comparisons["quality_gap"]["compressed_quality_acceptability"] != "BELOW_UNCOMPRESSED_BEST"
    )
    summary = {
        "task": "Task 69 GSM8K n=30 full matrix with frozen quality setting",
        "status": "PASS",
        "claim_policy": "preliminary n=30 matrix; no final speedup or correctness claim",
        "by_condition": by_condition,
        "comparisons": comparisons,
        "n100_gate": {
            "justified_next": n100_justified,
            "reason": (
                "n=100 is justified only if compressed quality is close to uncompressed and CC-DFlash improves e2e speed over LLMLingua-AR."
                if n100_justified
                else "n=100 is not automatic; review quality gap and failure samples before expanding."
            ),
        },
    }
    return summary, table, failures


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "condition",
        "rows",
        "numeric_matches",
        "numeric_match_rate",
        "exact_containment_matches",
        "final_answer_marker_count",
        "hit_cap_count",
        "avg_output_tokens",
        "avg_generation_latency_s",
        "avg_e2e_latency_s",
        "avg_t_compress_ms",
        "avg_tau_mean",
        "generation_tok_per_sec_weighted",
        "e2e_tok_per_sec_weighted",
        "avg_compression_ratio",
        "avg_original_input_tokens",
        "avg_compressed_input_tokens",
        "protected_suffix_preserved_count",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 69 GSM8K n=30 full matrix")
    parser.add_argument("--summary-output", default=str(DEFAULT_SUMMARY_OUTPUT))
    parser.add_argument("--table-output", default=str(DEFAULT_TABLE_OUTPUT))
    parser.add_argument("--failure-output", default=str(DEFAULT_FAILURE_OUTPUT))
    args = parser.parse_args()

    rows_by_condition = {condition: load_jsonl(path) for condition, path in DEFAULT_ARTIFACTS.items()}
    summary, table, failures = analyze_rows(rows_by_condition)
    summary["inputs"] = {condition: str(path) for condition, path in DEFAULT_ARTIFACTS.items()}
    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(Path(args.table_output), table)
    write_jsonl(Path(args.failure_output), failures)

    print(f"status={summary['status']}")
    for condition, item in summary["by_condition"].items():
        print(
            f"{condition}: rows={item['rows']} numeric={item['numeric_matches']}/{item['rows']} "
            f"e2e_tok_s={item['e2e_tok_per_sec_weighted']:.2f} cap_hits={item['hit_cap_count']}"
        )
    print(f"compressed_pair={summary['comparisons']['compressed_pair']}")
    print(f"quality_gap={summary['comparisons']['quality_gap']}")
    print(f"n100_gate={summary['n100_gate']}")


if __name__ == "__main__":
    main()
