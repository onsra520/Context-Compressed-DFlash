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


TASK60_PATHS = {
    "LLMLingua-AR-R2": Path("results/task60_gsm8k_short_llmlingua_ar_r2_n10_mnt256_suffixfix.jsonl"),
    "CC-DFlash-R2": Path("results/task60_gsm8k_short_cc_dflash_r2_n10_mnt256_suffixfix.jsonl"),
}
TASK63_PATHS = {
    "LLMLingua-AR-R2": Path("results/task63_gsm8k_short_llmlingua_ar_r2_n30_mnt256.jsonl"),
    "CC-DFlash-R2": Path("results/task63_gsm8k_short_cc_dflash_r2_n30_mnt256.jsonl"),
}
DEFAULT_JSON_OUTPUT = Path("results/task63_n30_stability_summary.json")
DEFAULT_CSV_OUTPUT = Path("results/task63_n30_stability_table.csv")

FINAL_ANSWER_MARKER_RE = re.compile(
    r"final\s+(?:numeric\s+)?answer\s*(?:is|=|:|：)\s*[-+]?\$?\d[\d,]*(?:\.\d+)?",
    re.IGNORECASE,
)
STABILITY_MARGIN = 0.10


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


def _has_final_answer_marker(text: Any) -> bool:
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
    generated_text_present = sum(
        1 for row in rows if isinstance(row.get("generated_text"), str) and bool(row["generated_text"].strip())
    )

    return {
        "stage": stage,
        "condition": condition,
        "artifact": str(path),
        "rows": len(rows),
        "max_new_tokens": rows[0].get("max_new_tokens") if rows else None,
        "generated_text_present_count": generated_text_present,
        "numeric_extraction_match_count": numeric_matches,
        "numeric_extraction_rate": round(numeric_matches / len(rows), 6) if rows else 0.0,
        "exact_containment_count": exact_matches,
        "exact_containment_rate": round(exact_matches / len(rows), 6) if rows else 0.0,
        "final_answer_marker_count": sum(1 for row in rows if _has_final_answer_marker(row.get("generated_text"))),
        "hit_token_cap_count": sum(1 for row in rows if _hit_max_new_tokens(row)),
        "protected_suffix_preserved_count": sum(1 for row in rows if row.get("protected_suffix_preserved") is True),
        "question_preserved_count": sum(1 for row in rows if row.get("question_preserved") is True),
        "avg_generation_latency_s": _mean(generation_times),
        "avg_e2e_latency_s": _mean(e2e_times),
        "avg_t_compress_ms": _mean(_numeric_values(rows, "t_compress_ms")),
        "avg_tok_per_sec": _mean(_numeric_values(rows, "tok_per_sec", "tok_per_s", "tokens_per_second")),
        "generation_tok_per_sec_weighted": total_output_tokens / total_generation_time if total_generation_time else 0.0,
        "e2e_tok_per_sec_weighted": total_output_tokens / total_e2e_time if total_e2e_time else 0.0,
        "avg_output_tokens": _mean(_numeric_values(rows, "output_tokens")),
        "avg_input_tokens": _mean(_numeric_values(rows, "input_tokens")),
        "avg_actual_compression_ratio": _mean(_numeric_values(rows, "actual_compression_ratio", "compression_ratio", "R_actual")),
    }


def _classify_stability(before: dict[str, Any], after: dict[str, Any]) -> str:
    if after["rows"] < 30 or after["generated_text_present_count"] < after["rows"]:
        return "INCONCLUSIVE"
    delta = after["numeric_extraction_rate"] - before["numeric_extraction_rate"]
    if delta > STABILITY_MARGIN:
        return "IMPROVED"
    if delta < -STABILITY_MARGIN:
        return "DEGRADED"
    return "STABLE"


def _compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    comparison = {
        "condition": after["condition"],
        "task60_rows": before["rows"],
        "task63_rows": after["rows"],
        "task60_numeric_extraction_rate": before["numeric_extraction_rate"],
        "task63_numeric_extraction_rate": after["numeric_extraction_rate"],
        "numeric_extraction_rate_delta": round(after["numeric_extraction_rate"] - before["numeric_extraction_rate"], 6),
        "numeric_extraction_match_delta": after["numeric_extraction_match_count"] - before["numeric_extraction_match_count"],
        "exact_containment_rate_delta": round(after["exact_containment_rate"] - before["exact_containment_rate"], 6),
        "final_answer_marker_count_delta": after["final_answer_marker_count"] - before["final_answer_marker_count"],
        "hit_token_cap_count_delta": after["hit_token_cap_count"] - before["hit_token_cap_count"],
        "avg_generation_latency_s_delta": round(after["avg_generation_latency_s"] - before["avg_generation_latency_s"], 6),
        "avg_e2e_latency_s_delta": round(after["avg_e2e_latency_s"] - before["avg_e2e_latency_s"], 6),
        "avg_t_compress_ms_delta": round(after["avg_t_compress_ms"] - before["avg_t_compress_ms"], 6),
        "generation_tok_per_sec_weighted_delta": round(
            after["generation_tok_per_sec_weighted"] - before["generation_tok_per_sec_weighted"],
            6,
        ),
        "e2e_tok_per_sec_weighted_delta": round(
            after["e2e_tok_per_sec_weighted"] - before["e2e_tok_per_sec_weighted"],
            6,
        ),
    }
    comparison["stability_classification"] = _classify_stability(before, after)
    return comparison


def analyze_paths(
    *,
    task60_paths: dict[str, Path] | None = None,
    task63_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    task60_paths = task60_paths or TASK60_PATHS
    task63_paths = task63_paths or TASK63_PATHS
    before = {
        condition: summarize_artifact("task60_n10", condition, task60_paths[condition])
        for condition in task60_paths
    }
    after = {
        condition: summarize_artifact("task63_n30", condition, task63_paths[condition])
        for condition in task63_paths
    }
    comparisons = {
        condition: _compare(before[condition], after[condition])
        for condition in sorted(set(before) & set(after))
    }
    status = "PASS"
    if any(item["stability_classification"] == "INCONCLUSIVE" for item in comparisons.values()):
        status = "PARTIAL"

    return {
        "task": "Task 63 GSM8K n=30 stability verification",
        "status": status,
        "claim_policy": "preliminary n=30 compressed-only GSM8K stability check; no final correctness or speedup claim",
        "stability_margin": STABILITY_MARGIN,
        "artifacts": {
            "task60_n10": before,
            "task63_n30": after,
        },
        "comparisons": comparisons,
    }


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
        "avg_generation_latency_s",
        "avg_e2e_latency_s",
        "avg_t_compress_ms",
        "avg_tok_per_sec",
        "generation_tok_per_sec_weighted",
        "e2e_tok_per_sec_weighted",
        "avg_output_tokens",
        "avg_input_tokens",
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 63 n=30 GSM8K compressed stability artifacts")
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
                f"numeric={artifact['numeric_extraction_match_count']} "
                f"rate={artifact['numeric_extraction_rate']:.3f} "
                f"markers={artifact['final_answer_marker_count']} "
                f"hit_cap={artifact['hit_token_cap_count']} "
                f"avg_e2e={artifact['avg_e2e_latency_s']:.2f} "
                f"gen_tok_s={artifact['generation_tok_per_sec_weighted']:.2f} "
                f"e2e_tok_s={artifact['e2e_tok_per_sec_weighted']:.2f}"
            )
    for condition, comparison in summary["comparisons"].items():
        print(
            f"compare {condition}: classification={comparison['stability_classification']} "
            f"rate_delta={comparison['numeric_extraction_rate_delta']:.3f} "
            f"hit_cap_delta={comparison['hit_token_cap_count_delta']}"
        )


if __name__ == "__main__":
    main()
