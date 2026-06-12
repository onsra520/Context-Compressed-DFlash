from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_INPUTS = {
    "task60_mnt256": Path("results/task60_mnt256_calibration_summary.json"),
    "task61b_keep_rate67": Path("results/task61b_keep_rate67_calibration_summary.json"),
    "task62_k67_triage": Path("results/task62_changed_outcome_triage_summary.json"),
    "task63_n30_mnt256": Path("results/task63_n30_stability_summary.json"),
    "task66_mnt384": Path("results/task66_mnt384_rerun_reproducibility_summary.json"),
    "task67_failure_triage": Path("results/task67_persistent_mnt384_failure_summary.json"),
}
DEFAULT_SUMMARY_OUTPUT = Path("results/task68_gsm8k_final_settings_summary.json")
DEFAULT_TABLE_OUTPUT = Path("results/task68_gsm8k_final_settings_table.csv")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return data


def _nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def _task66_condition(data: dict[str, Any], condition: str) -> dict[str, Any]:
    return _nested(data, "artifacts", "task66_mnt384_rerun", condition, default={}) or {}


def _condition_rows(summaries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for condition in ("LLMLingua-AR-R2", "CC-DFlash-R2"):
        task63 = _nested(summaries["task63_n30_mnt256"], "comparisons", condition, default={}) or {}
        task63_artifact = _nested(summaries["task63_n30_mnt256"], "artifacts", "task63_n30", condition, default={}) or {}
        task66 = _nested(summaries["task66_mnt384"], "comparisons", condition, default={}) or {}
        task66_artifact = _task66_condition(summaries["task66_mnt384"], condition)
        task67 = _nested(summaries["task67_failure_triage"], "by_condition", condition, default={}) or {}
        rows.extend(
            [
                {
                    "setting": "speed_oriented",
                    "condition": condition,
                    "keep_rate": 0.50,
                    "max_new_tokens": 256,
                    "rows": task63_artifact.get("rows") or task63.get("task63_rows"),
                    "numeric_rate": task63_artifact.get("numeric_extraction_rate")
                    or task63.get("task63_numeric_extraction_rate"),
                    "numeric_matches": task63_artifact.get("numeric_extraction_match_count"),
                    "cap_hits": task63_artifact.get("hit_token_cap_count"),
                    "source": "Task 63 n=30 mnt256 stability summary",
                },
                {
                    "setting": "quality_oriented",
                    "condition": condition,
                    "keep_rate": 0.50,
                    "max_new_tokens": 384,
                    "rows": task66.get("task66_rows") or task66_artifact.get("rows"),
                    "numeric_rate": task66.get("task66_numeric_extraction_rate"),
                    "numeric_matches": task66.get("task66_numeric_extraction_match_count")
                    or task66_artifact.get("numeric_extraction_match_count"),
                    "cap_hits": task67.get("cap_hits") or task66_artifact.get("hit_token_cap_count"),
                    "source": "Task 66 rerun + Task 67 failure triage",
                },
            ]
        )
    return rows


def synthesize_final_settings(summaries: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    task61b_changed = summaries.get("task61b_keep_rate67", {}).get("changed_outcome_counts", {})
    task62 = summaries.get("task62_k67_triage", {})
    task67_labels = _nested(summaries["task67_failure_triage"], "overall", "label_counts", default={}) or {}

    table = _condition_rows(summaries)
    summary = {
        "task": "Task 68 freeze final GSM8K settings and n=100 gate plan",
        "status": "PASS",
        "claim_policy": "read-only synthesis; no benchmark execution and no final correctness or speedup claim",
        "evidence_path": {
            "task53_54_failure": "compressed GSM8K quality remained weak before suffix/prompt metadata fixes",
            "task58_suffix_fix": "protected final-answer suffix moved outside compression",
            "task60_mnt256": "mnt256 improved compressed numeric extraction and reduced cap hits in n=10 calibration",
            "task63_n30_stability": "mnt256 default-R2 signal stayed stable at n=30 but exposed cap hits",
            "task66_mnt384_reproducibility": "mnt384 quality reproduced at 24/30 and Task 65 latency was noisy",
            "task67_failure_triage": "remaining mnt384 failures split between truncation and reasoning",
        },
        "final_settings": {
            "speed_oriented": {
                "keep_rate": 0.50,
                "max_new_tokens": 256,
                "protected_suffix_enabled": True,
                "purpose": "speed/throughput tradeoff for compressed GSM8K",
            },
            "quality_oriented": {
                "keep_rate": 0.50,
                "max_new_tokens": 384,
                "protected_suffix_enabled": True,
                "purpose": "quality upper-bound / quality calibration for compressed GSM8K",
            },
        },
        "rejections": {
            "keep_rate_0_67": {
                "decision": "REJECT_AS_DEFAULT",
                "reason": "Task 61B did not improve net numeric accuracy and introduced PASS_TO_FAIL instability",
                "changed_outcome_counts": task61b_changed,
            },
            "keep_rate_0_75_0_80": {
                "decision": "DEFER",
                "reason": "Task 62 found no direct evidence that k67 repaired compression loss and explicitly did not recommend k80 next",
                "task62_test_keep_rate_80_next": task62.get("test_keep_rate_80_next"),
            },
            "max_new_tokens_512": {
                "decision": "DEFER",
                "reason": "Task 67 failures are not truncation-dominated; they split evenly between remaining truncation and reasoning failures",
                "task67_labels": task67_labels,
            },
        },
        "n100_gate": {
            "status": "NOT_NEXT",
            "reason": "compressed-only mnt256/mnt384 evidence is useful, but a comparable full GSM8K matrix is still missing before n=100",
        },
        "next_real_run_plan": {
            "selected_option": "Option C",
            "name": "n=30 full GSM8K matrix with comparable settings before n=100",
            "reason": "The project has compressed-only n=30 evidence; Baseline-AR and DFlash-R1 should be run at comparable GSM8K settings before expanding to n=100.",
            "recommended_next_task": "Task 69 n=30 full GSM8K matrix using frozen settings, starting with quality-oriented max_new_tokens=384 and unique resume-safe artifacts",
        },
        "conservative_report_interpretation": (
            "CC-DFlash GSM8K evidence is preliminary. Use mnt256 for speed-oriented compressed comparison and "
            "mnt384 for quality-oriented compressed comparison; do not claim final correctness, final speedup, "
            "or proven end-to-end compression benefit."
        ),
    }
    return summary, table


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "setting",
        "condition",
        "keep_rate",
        "max_new_tokens",
        "rows",
        "numeric_rate",
        "numeric_matches",
        "cap_hits",
        "source",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthesize final GSM8K compressed settings and n=100 gate plan")
    parser.add_argument("--summary-output", default=str(DEFAULT_SUMMARY_OUTPUT))
    parser.add_argument("--table-output", default=str(DEFAULT_TABLE_OUTPUT))
    args = parser.parse_args()

    summaries = {name: load_json(path) for name, path in DEFAULT_INPUTS.items()}
    summary, table = synthesize_final_settings(summaries)
    summary["inputs"] = {name: str(path) for name, path in DEFAULT_INPUTS.items()}

    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(Path(args.table_output), table)

    print(f"status={summary['status']}")
    print(f"speed_setting={summary['final_settings']['speed_oriented']}")
    print(f"quality_setting={summary['final_settings']['quality_oriented']}")
    print(f"n100_gate={summary['n100_gate']['status']}")
    print(f"next={summary['next_real_run_plan']['recommended_next_task']}")


if __name__ == "__main__":
    main()
