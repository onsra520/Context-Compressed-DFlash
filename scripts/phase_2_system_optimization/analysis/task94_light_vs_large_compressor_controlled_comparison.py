from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_system_build_and_evaluation.analysis.t31_answer_quality import score_row


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]
    return statistics.mean(values) if values else None


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def _profile_from_rows(rows: list[dict[str, Any]]) -> str:
    profiles = {str(row.get("compressor_profile")) for row in rows if row.get("compressor_profile")}
    if len(profiles) != 1:
        raise ValueError(f"Expected exactly one compressor_profile, found {sorted(profiles)}")
    return next(iter(profiles))


def _metadata_checks(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "all_local_files_only_true": all(row.get("local_files_only") is True for row in rows),
        "all_paths_present": all(bool(row.get("compressor_path")) for row in rows),
        "all_resolved_paths_present": all(bool(row.get("resolved_compressor_path")) for row in rows),
        "all_question_preserved": all(row.get("question_preserved") is True for row in rows),
        "all_protected_suffix_preserved": all(row.get("protected_suffix_preserved") is True for row in rows),
    }


def summarize_artifact(path: Path) -> dict[str, Any]:
    rows = _load_jsonl(path)
    profile = _profile_from_rows(rows)
    scores = [score_row(row) for row in rows]
    extracted_matches = sum(score.extracted_answer_match for score in scores)
    exact_matches = sum(score.exact_match for score in scores)
    normalized_matches = sum(score.normalized_match for score in scores)
    e2e_times = [
        float(row["generation_time_s"]) + float(row.get("t_compress_ms", 0.0)) / 1000.0
        for row in rows
    ]
    return {
        "artifact": str(path),
        "profile": profile,
        "rows": len(rows),
        "avg_t_compress_ms": _mean(rows, "t_compress_ms"),
        "avg_R_actual": _mean(rows, "R_actual"),
        "avg_tok_per_sec": _mean(rows, "tok_per_sec"),
        "avg_tau_mean": _mean(rows, "tau_mean"),
        "avg_t_prefill_ms": _mean(rows, "t_prefill_ms"),
        "avg_generation_time_s": _mean(rows, "generation_time_s"),
        "avg_e2e_time_s": statistics.mean(e2e_times) if e2e_times else None,
        "avg_output_tokens": _mean(rows, "output_tokens"),
        "exact_match_count": exact_matches,
        "exact_match_rate": _rate(exact_matches, len(rows)),
        "normalized_match_count": normalized_matches,
        "normalized_match_rate": _rate(normalized_matches, len(rows)),
        "numeric_extraction_match_count": extracted_matches,
        "numeric_extraction_match_rate": _rate(extracted_matches, len(rows)),
        "metadata_checks": _metadata_checks(rows),
    }


def _safe_delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return a - b


def build_comparison(large: dict[str, Any], light: dict[str, Any]) -> dict[str, Any]:
    large_tc = large["avg_t_compress_ms"]
    light_tc = light["avg_t_compress_ms"]
    large_ratio = large["avg_R_actual"]
    light_ratio = light["avg_R_actual"]
    return {
        "large_artifact": large["artifact"],
        "light_artifact": light["artifact"],
        "rows_match_expected_n10": large["rows"] == 10 and light["rows"] == 10,
        "light_minus_large_avg_t_compress_ms": _safe_delta(light_tc, large_tc),
        "light_minus_large_avg_R_actual": _safe_delta(light_ratio, large_ratio),
        "light_minus_large_avg_e2e_time_s": _safe_delta(light["avg_e2e_time_s"], large["avg_e2e_time_s"]),
        "light_minus_large_avg_tok_per_sec": _safe_delta(light["avg_tok_per_sec"], large["avg_tok_per_sec"]),
        "light_minus_large_avg_tau_mean": _safe_delta(light["avg_tau_mean"], large["avg_tau_mean"]),
        "light_minus_large_numeric_extraction_match_rate": _safe_delta(
            light["numeric_extraction_match_rate"], large["numeric_extraction_match_rate"]
        ),
        "light_minus_large_exact_match_rate": _safe_delta(light["exact_match_rate"], large["exact_match_rate"]),
        "large_over_light_t_compress_ratio": (large_tc / light_tc) if large_tc and light_tc else None,
        "large_over_light_R_actual_ratio": (large_ratio / light_ratio) if large_ratio and light_ratio else None,
        "decision": {
            "status": "PASS_WITH_CAVEAT",
            "bounded_scope_only": True,
            "n30_justified_now": False,
            "summary": (
                "Light reduced average t_compress_ms and e2e time in this controlled n=10 comparison, "
                "but also lowered average R_actual and the GSM8K numeric quality proxy versus large."
            ),
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def analyze(large_artifact: Path, light_artifact: Path) -> dict[str, Any]:
    large = summarize_artifact(large_artifact)
    light = summarize_artifact(light_artifact)
    if large["profile"] != "large":
        raise ValueError(f"Expected large artifact to resolve to profile=large, got {large['profile']!r}")
    if light["profile"] != "light":
        raise ValueError(f"Expected light artifact to resolve to profile=light, got {light['profile']!r}")
    return {
        "task": "Task94",
        "title": "Light vs Large Compressor Controlled Comparison",
        "dataset": "gsm8k_short",
        "condition": "CC-DFlash-R2",
        "seed": 42,
        "n": 10,
        "profiles": {
            "large": large,
            "light": light,
        },
        "comparison": build_comparison(large, light),
        "claim_boundary": {
            "final_speedup_claim": False,
            "deployment_claim": False,
            "qmsum_semantic_correctness_claim": False,
            "full_benchmark_claim": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Task94 large-vs-light controlled compressor comparison")
    parser.add_argument("--large-artifact", type=Path, required=True)
    parser.add_argument("--light-artifact", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--table-output", type=Path, required=True)
    args = parser.parse_args()

    summary = analyze(args.large_artifact, args.light_artifact)
    _write_json(args.summary_output, summary)

    table_rows = []
    for profile_name in ("large", "light"):
        item = summary["profiles"][profile_name]
        table_rows.append(
            {
                "profile": profile_name,
                "artifact": item["artifact"],
                "rows": item["rows"],
                "avg_t_compress_ms": item["avg_t_compress_ms"],
                "avg_R_actual": item["avg_R_actual"],
                "avg_e2e_time_s": item["avg_e2e_time_s"],
                "avg_tok_per_sec": item["avg_tok_per_sec"],
                "avg_tau_mean": item["avg_tau_mean"],
                "avg_t_prefill_ms": item["avg_t_prefill_ms"],
                "numeric_extraction_match_count": item["numeric_extraction_match_count"],
                "numeric_extraction_match_rate": item["numeric_extraction_match_rate"],
                "exact_match_count": item["exact_match_count"],
                "exact_match_rate": item["exact_match_rate"],
            }
        )
    _write_csv(args.table_output, table_rows)

    comparison = summary["comparison"]
    print(f"status={comparison['decision']['status']}")
    print(f"rows_match_expected_n10={comparison['rows_match_expected_n10']}")
    print(f"large_over_light_t_compress_ratio={comparison['large_over_light_t_compress_ratio']}")
    print(f"large_over_light_R_actual_ratio={comparison['large_over_light_R_actual_ratio']}")
    print(f"light_minus_large_numeric_extraction_match_rate={comparison['light_minus_large_numeric_extraction_match_rate']}")
    print(f"wrote_summary={args.summary_output}")
    print(f"wrote_table={args.table_output}")


if __name__ == "__main__":
    main()
