from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_system_build_and_evaluation.analysis.t47_quality_refinement import classify_row
from scripts.phase_1_system_build_and_evaluation.analysis.t70_qmsum_diagnostic_audit import (
    normalized_token_overlap,
)


CONDITIONS = ["Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-DFlash-R2"]
DATASETS = ["gsm8k_short", "qmsum_meeting_qa_long"]
EXPECTED_ROWS = 30
MAX_NEW_TOKENS = 384
SUMMARY_OUTPUT = Path("results/task80a_final_two_dataset_rerun_summary.json")
TABLE_OUTPUT = Path("results/task80a_final_two_dataset_rerun_table.csv")
DELTA_OUTPUT = Path("results/task80a_condition_delta_vs_task80.csv")
MANIFEST_OUTPUT = Path("results/task80a_run_manifest.json")
TASK80_SUMMARY = Path("results/task80_cross_dataset_final_summary.json")

ARTIFACTS = {
    ("gsm8k_short", "Baseline-AR"): Path("results/task80a_gsm8k_short_baseline_ar_n30_mnt384.jsonl"),
    ("gsm8k_short", "DFlash-R1"): Path("results/task80a_gsm8k_short_dflash_r1_n30_mnt384.jsonl"),
    ("gsm8k_short", "LLMLingua-AR-R2"): Path("results/task80a_gsm8k_short_llmlingua_ar_r2_n30_mnt384.jsonl"),
    ("gsm8k_short", "CC-DFlash-R2"): Path("results/task80a_gsm8k_short_cc_dflash_r2_n30_mnt384.jsonl"),
    ("qmsum_meeting_qa_long", "Baseline-AR"): Path("results/task80a_qmsum_long_baseline_ar_n30_mnt384.jsonl"),
    ("qmsum_meeting_qa_long", "DFlash-R1"): Path("results/task80a_qmsum_long_dflash_r1_n30_mnt384.jsonl"),
    ("qmsum_meeting_qa_long", "LLMLingua-AR-R2"): Path("results/task80a_qmsum_long_llmlingua_ar_r2_n30_mnt384.jsonl"),
    ("qmsum_meeting_qa_long", "CC-DFlash-R2"): Path("results/task80a_qmsum_long_cc_dflash_r2_n30_mnt384.jsonl"),
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
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


def _number(row: dict[str, Any], *field_names: str) -> float | None:
    for field_name in field_names:
        value = row.get(field_name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _numbers(rows: list[dict[str, Any]], *field_names: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = _number(row, *field_names)
        if value is not None:
            values.append(value)
    return values


def _hit_cap(row: dict[str, Any]) -> bool:
    output_tokens = _number(row, "output_tokens")
    max_new_tokens = _number(row, "max_new_tokens")
    return output_tokens is not None and max_new_tokens is not None and output_tokens >= max_new_tokens


def _e2e_times(rows: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for row in rows:
        generation_s = _number(row, "generation_time_s")
        if generation_s is None:
            continue
        t_compress_ms = _number(row, "t_compress_ms") or 0.0
        values.append(generation_s + t_compress_ms / 1000.0)
    return values


def _weighted_tok_s(rows: list[dict[str, Any]], *, include_compression: bool) -> float:
    output_tokens = sum(_numbers(rows, "output_tokens"))
    generation_time = sum(_numbers(rows, "generation_time_s"))
    compression_time = sum(_numbers(rows, "t_compress_ms")) / 1000.0 if include_compression else 0.0
    denom = generation_time + compression_time
    return output_tokens / denom if denom else 0.0


def summarize_condition(
    dataset: str,
    condition: str,
    rows: list[dict[str, Any]],
    *,
    expected_rows: int = EXPECTED_ROWS,
) -> dict[str, Any]:
    status = "completed" if len(rows) == expected_rows else ("missing" if not rows else "failed_partial")
    major_shift_reasons: list[str] = []
    if len(rows) != expected_rows:
        major_shift_reasons.append("row_count_incomplete")

    e2e_times = _e2e_times(rows)
    output_tokens = _numbers(rows, "output_tokens")
    generated_text_count = sum(1 for row in rows if isinstance(row.get("generated_text"), str) and row["generated_text"].strip())
    compressed = condition in {"LLMLingua-AR-R2", "CC-DFlash-R2"}
    summary: dict[str, Any] = {
        "dataset": dataset,
        "dataset_role": "short-context numeric quality" if dataset == "gsm8k_short" else "long-context diagnostic behavior",
        "condition": condition,
        "status": status,
        "row_count": len(rows),
        "n": len(rows),
        "expected_rows": expected_rows,
        "max_new_tokens": int(_numbers(rows, "max_new_tokens")[0]) if _numbers(rows, "max_new_tokens") else MAX_NEW_TOKENS,
        "uses_dflash": condition in {"DFlash-R1", "CC-DFlash-R2"},
        "compression": "llmlingua" if compressed else "none",
        "keep_rate": _number(rows[0], "keep_rate") if rows else (0.5 if compressed else 1.0),
        "avg_input_tokens": round(_mean(_numbers(rows, "input_tokens")), 6),
        "avg_output_tokens": round(_mean(output_tokens), 6),
        "cap_hit_count": sum(1 for row in rows if _hit_cap(row)),
        "avg_generation_latency_s": round(_mean(_numbers(rows, "generation_time_s")), 6),
        "avg_e2e_latency_s": round(_mean(e2e_times), 6),
        "generation_tok_s": round(_weighted_tok_s(rows, include_compression=False), 6),
        "e2e_tok_s": round(_weighted_tok_s(rows, include_compression=True), 6),
        "avg_t_compress_ms": round(_mean(_numbers(rows, "t_compress_ms")), 6),
        "avg_t_prefill_ms": round(_mean(_numbers(rows, "t_prefill_ms")), 6),
        "compression_ratio": round(_mean(_numbers(rows, "actual_compression_ratio", "compression_ratio", "R_actual")), 6),
        "avg_input_tokens_original": round(_mean(_numbers(rows, "original_input_tokens", "N_original")), 6),
        "avg_input_tokens_compressed": round(_mean(_numbers(rows, "compressed_input_tokens", "N_compressed")), 6),
        "avg_tau_mean": round(_mean(_numbers(rows, "tau_mean")), 6),
        "peak_vram_allocated_gib": round(max(_numbers(rows, "vram_allocated_gib"), default=0.0), 6),
        "peak_vram_reserved_gib": round(max(_numbers(rows, "vram_reserved_gib"), default=0.0), 6),
        "generated_text_present_count": generated_text_count,
        "major_shift_reasons": major_shift_reasons,
    }
    if dataset == "gsm8k_short":
        classifications = [
            classify_row(row, row_index=index, condition=condition, artifact=f"{condition}.jsonl")
            for index, row in enumerate(rows, start=1)
        ]
        numeric_matches = sum(1 for item in classifications if item.get("numeric_match"))
        exact_matches = sum(1 for item in classifications if item.get("exact_match"))
        invalid_output_count = sum(
            1
            for row in rows
            if not isinstance(row.get("generated_text"), str) or not row["generated_text"].strip()
        )
        summary.update(
            {
                "numeric_match_count": numeric_matches,
                "numeric_accuracy": round(numeric_matches / len(rows), 6) if rows else 0.0,
                "exact_containment_count": exact_matches,
                "invalid_output_count": invalid_output_count,
                "final_answer_suffix_preserved_count": sum(
                    1 for row in rows if row.get("protected_suffix_preserved") is True
                )
                if compressed
                else len(rows),
                "main_interpretation": "GSM8K deterministic numeric proxy; still preliminary n=30.",
            }
        )
    else:
        overlaps = [normalized_token_overlap(row.get("expected_answer"), row.get("generated_text")) for row in rows]
        question_preserved_count = sum(1 for row in rows if row.get("question_preserved") is True)
        protected_suffix_count = sum(1 for row in rows if row.get("protected_suffix_preserved") is True)
        summary.update(
            {
                "avg_overlap_proxy": round(_mean(overlaps), 6),
                "normalized_containment_count": 0,
                "semantic_correctness_claim": False,
                "question_preserved_count": question_preserved_count,
                "protected_suffix_preserved_count": protected_suffix_count,
                "qmsum_policy_preserved_count": protected_suffix_count,
                "main_diagnostic_interpretation": "QMSum is diagnostic only; not semantic correctness evidence.",
            }
        )
    return summary


def _task80_reference_map(path: Path = TASK80_SUMMARY) -> dict[tuple[str, str], dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    refs: dict[tuple[str, str], dict[str, Any]] = {}
    gsm8k = data.get("datasets", {}).get("gsm8k_short", {}).get("conditions", {})
    for condition, item in gsm8k.items():
        refs[("gsm8k_short", condition)] = {
            "row_count": item.get("n"),
            "numeric_accuracy": item.get("numeric_accuracy"),
            "numeric_match_count": item.get("numeric_matches"),
            "avg_e2e_latency_s": item.get("avg_e2e_latency_s"),
            "e2e_tok_s": item.get("e2e_tok_per_sec"),
            "avg_t_compress_ms": item.get("avg_t_compress_ms"),
            "compression_ratio": item.get("compression_ratio"),
            "cap_hit_count": item.get("cap_hits"),
        }
    qmsum = data.get("datasets", {}).get("qmsum_meeting_qa_long", {}).get("task71_by_condition", {})
    for condition, item in qmsum.items():
        refs[("qmsum_meeting_qa_long", condition)] = {
            "row_count": item.get("rows"),
            "avg_overlap_proxy": item.get("avg_answer_token_overlap"),
            "avg_e2e_latency_s": item.get("avg_e2e_latency_s"),
            "e2e_tok_s": item.get("e2e_tok_per_sec_weighted"),
            "avg_t_compress_ms": item.get("avg_t_compress_ms"),
            "compression_ratio": item.get("avg_compression_ratio"),
            "cap_hit_count": item.get("hit_cap_count"),
        }
    return refs


def _relative_delta(old: Any, new: Any) -> float | None:
    if not isinstance(old, (int, float)) or not isinstance(new, (int, float)) or old == 0:
        return None
    return round((float(new) - float(old)) / abs(float(old)) * 100.0, 6)


def _delta_severity(dataset: str, condition: str, metric: str, old: Any, new: Any) -> tuple[str, str]:
    if metric == "row_count" and new != old:
        return "major_shift", "Incomplete or changed row count versus Task 80 reference."
    if old is None or new is None:
        return "watch", "Missing comparison value."
    if dataset == "gsm8k_short" and metric == "numeric_match_count" and isinstance(old, (int, float)) and isinstance(new, (int, float)):
        if float(new) < float(old) - 3:
            return "major_shift", "GSM8K numeric matches dropped by more than 3/30."
    if metric in {"avg_e2e_latency_s", "e2e_tok_s"} and isinstance(old, (int, float)) and isinstance(new, (int, float)):
        rel = abs(float(new) - float(old)) / abs(float(old)) if old else 0.0
        if rel >= 0.5:
            return "watch", "Timing shifted by at least 50%; likely runtime noise or backend variance."
    return "ok", ""


def build_delta_rows(
    task80: dict[tuple[str, str], dict[str, Any]],
    task80a: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    metrics = [
        "row_count",
        "numeric_match_count",
        "numeric_accuracy",
        "avg_overlap_proxy",
        "avg_e2e_latency_s",
        "e2e_tok_s",
        "avg_t_compress_ms",
        "compression_ratio",
        "cap_hit_count",
    ]
    rows: list[dict[str, Any]] = []
    for key in sorted(set(task80) | set(task80a)):
        old_item = task80.get(key, {})
        new_item = task80a.get(key, {})
        dataset, condition = key
        for metric in metrics:
            if metric not in old_item and metric not in new_item:
                continue
            old = old_item.get(metric)
            new = new_item.get(metric)
            severity, note = _delta_severity(dataset, condition, metric, old, new)
            rows.append(
                {
                    "dataset": dataset,
                    "condition": condition,
                    "metric": metric,
                    "task80_value": old,
                    "task80a_value": new,
                    "delta": round(float(new) - float(old), 6)
                    if isinstance(old, (int, float)) and isinstance(new, (int, float))
                    else "",
                    "relative_delta_percent": _relative_delta(old, new),
                    "severity": severity,
                    "note": note,
                }
            )
    return rows


def _condition_command(dataset: str, condition: str, output: Path) -> str:
    return (
        "PYTHONPATH=src .venv/bin/python scripts/run_mvp.py "
        f"--prompt-source dataset --dataset {dataset} --condition {condition} "
        f"--n 30 --seed 42 --max-new-tokens 384 --output {output} "
        "--resume --store-generated-text"
    )


def build_run_manifest(
    *,
    commit_before_run: str,
    run_status: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for condition in CONDITIONS:
            output = ARTIFACTS[(dataset, condition)]
            status = run_status.get((dataset, condition), {})
            entries.append(
                {
                    "date": "2026-06-14",
                    "commit_before_run": commit_before_run,
                    "dataset": dataset,
                    "condition": condition,
                    "output_path": str(output),
                    "command_used": _condition_command(dataset, condition, output),
                    "n": EXPECTED_ROWS,
                    "max_new_tokens": MAX_NEW_TOKENS,
                    "keep_rate": 0.5 if condition in {"LLMLingua-AR-R2", "CC-DFlash-R2"} else 1.0,
                    "compression_mode": "llmlingua" if condition in {"LLMLingua-AR-R2", "CC-DFlash-R2"} else "none",
                    "uses_dflash": condition in {"DFlash-R1", "CC-DFlash-R2"},
                    "resume_used": True,
                    "status": status.get("status", "missing"),
                    "row_count": status.get("row_count", 0),
                    "notes": status.get("notes", ""),
                }
            )
    return entries


def _current_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _task80a_map(summaries: dict[str, dict[str, dict[str, Any]]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (dataset, condition): item
        for dataset, conditions in summaries.items()
        for condition, item in conditions.items()
    }


def _run_status_from_summaries(summaries: dict[str, dict[str, dict[str, Any]]]) -> dict[tuple[str, str], dict[str, Any]]:
    statuses: dict[tuple[str, str], dict[str, Any]] = {}
    for dataset, conditions in summaries.items():
        for condition, item in conditions.items():
            status = item["status"]
            notes = ""
            if dataset == "qmsum_meeting_qa_long" and condition == "DFlash-R1" and status == "failed_partial":
                notes = "Stopped at prompt_id=3 after prolonged no-progress interval with GPU active; last completed row prompt_id=2."
            elif dataset == "qmsum_meeting_qa_long" and condition in {"LLMLingua-AR-R2", "CC-DFlash-R2"} and status == "missing":
                status = "skipped"
                notes = "Skipped after QMSum DFlash-R1 stalled/was interrupted by safety rule."
            statuses[(dataset, condition)] = {
                "status": status,
                "row_count": item["row_count"],
                "notes": notes,
            }
    return statuses


def build_summary() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_dataset: dict[str, dict[str, dict[str, Any]]] = {}
    for dataset in DATASETS:
        by_dataset[dataset] = {}
        for condition in CONDITIONS:
            rows = load_jsonl(ARTIFACTS[(dataset, condition)])
            by_dataset[dataset][condition] = summarize_condition(dataset, condition, rows)

    task80_ref = _task80_reference_map()
    task80a_ref = _task80a_map(by_dataset)
    delta_rows = build_delta_rows(task80_ref, task80a_ref)
    major = [row for row in delta_rows if row["severity"] == "major_shift"]
    watch = [row for row in delta_rows if row["severity"] == "watch"]
    commit = _current_head()
    run_status = _run_status_from_summaries(by_dataset)
    manifest = build_run_manifest(commit_before_run=commit, run_status=run_status)

    gsm8k = by_dataset["gsm8k_short"]
    qmsum = by_dataset["qmsum_meeting_qa_long"]
    summary = {
        "task": "Task 80A final two-dataset rerun / recompute package",
        "date": datetime.now(timezone.utc).date().isoformat(),
        "status": "BLOCKED" if any(item["status"] in {"failed_partial", "missing"} for item in qmsum.values()) else "PASS_WITH_NOTES",
        "commit_before_run": commit,
        "claim_policy": "Preliminary n=30 rerun only; no final speedup, QMSum semantic correctness, deployment, or 8 GB claim.",
        "datasets": by_dataset,
        "major_shift_count": len(major),
        "watch_count": len(watch),
        "major_shift_items": major,
        "watch_items": watch,
        "gsm8k_summary": {
            "baseline_numeric": f"{gsm8k['Baseline-AR']['numeric_match_count']}/{gsm8k['Baseline-AR']['row_count']}",
            "dflash_numeric": f"{gsm8k['DFlash-R1']['numeric_match_count']}/{gsm8k['DFlash-R1']['row_count']}",
            "llmlingua_numeric": f"{gsm8k['LLMLingua-AR-R2']['numeric_match_count']}/{gsm8k['LLMLingua-AR-R2']['row_count']}",
            "cc_dflash_numeric": f"{gsm8k['CC-DFlash-R2']['numeric_match_count']}/{gsm8k['CC-DFlash-R2']['row_count']}",
            "cc_dflash_faster_than_llmlingua_ar": gsm8k["CC-DFlash-R2"]["e2e_tok_s"]
            > gsm8k["LLMLingua-AR-R2"]["e2e_tok_s"],
            "dflash_faster_than_baseline": gsm8k["DFlash-R1"]["e2e_tok_s"]
            > gsm8k["Baseline-AR"]["e2e_tok_s"],
        },
        "qmsum_summary": {
            "completed_conditions": [
                condition for condition, item in qmsum.items() if item["status"] == "completed"
            ],
            "failed_partial_conditions": [
                condition for condition, item in qmsum.items() if item["status"] == "failed_partial"
            ],
            "skipped_conditions": [
                condition for condition, item in run_status.items()
                if condition[0] == "qmsum_meeting_qa_long" and item["status"] == "skipped"
            ],
            "semantic_correctness_claim": False,
        },
        "task80b_recommendation": (
            "Task 80B should analyze the QMSum DFlash/long-context runtime issue before proceeding to final consistency audit."
            if major
            else "Task 80B can proceed to final consistency audit."
        ),
    }
    table_rows = [item for conditions in by_dataset.values() for item in conditions.values()]
    return summary, table_rows, delta_rows, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze Task 80A final two-dataset rerun artifacts.")
    parser.add_argument("--summary-output", type=Path, default=SUMMARY_OUTPUT)
    parser.add_argument("--table-output", type=Path, default=TABLE_OUTPUT)
    parser.add_argument("--delta-output", type=Path, default=DELTA_OUTPUT)
    parser.add_argument("--manifest-output", type=Path, default=MANIFEST_OUTPUT)
    args = parser.parse_args(argv)

    summary, table_rows, delta_rows, manifest = build_summary()
    _write_json(args.summary_output, summary)
    _write_csv(args.table_output, table_rows)
    _write_csv(args.delta_output, delta_rows)
    _write_json(args.manifest_output, manifest)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "summary_output": str(args.summary_output),
                "table_output": str(args.table_output),
                "delta_output": str(args.delta_output),
                "manifest_output": str(args.manifest_output),
                "major_shift_count": summary["major_shift_count"],
                "watch_count": summary["watch_count"],
                "task80b_recommendation": summary["task80b_recommendation"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
