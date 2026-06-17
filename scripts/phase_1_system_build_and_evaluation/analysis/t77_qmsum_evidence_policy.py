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

from scripts.phase_1_system_build_and_evaluation.analysis.t70_qmsum_diagnostic_audit import _hit_cap, has_repetition, load_jsonl
from scripts.phase_1_system_build_and_evaluation.analysis.t74_qmsum_proxy_case_triage import lexical_diagnostics
from scripts.phase_1_system_build_and_evaluation.analysis.t76_qmsum_evidence_error_taxonomy import classify_case

TASK71_ARTIFACTS = {
    "LLMLingua-AR-R2": Path("results/task71_qmsum_long_llmlingua_ar_r2_n30_mnt384.jsonl"),
    "CC-DFlash-R2": Path("results/task71_qmsum_long_cc_dflash_r2_n30_mnt384.jsonl"),
}
TASK73_ARTIFACTS = {
    "LLMLingua-AR-R2": Path("results/task73_qmsum_long_llmlingua_ar_r2_n30_mnt384_concise.jsonl"),
    "CC-DFlash-R2": Path("results/task73_qmsum_long_cc_dflash_r2_n30_mnt384_concise.jsonl"),
}
TASK75_ARTIFACTS = {
    "LLMLingua-AR-R2": Path("results/task75_qmsum_long_llmlingua_ar_r2_n30_mnt384_balanced.jsonl"),
    "CC-DFlash-R2": Path("results/task75_qmsum_long_cc_dflash_r2_n30_mnt384_balanced.jsonl"),
}
TASK77_ARTIFACTS = {
    "LLMLingua-AR-R2": Path("results/task77_qmsum_long_llmlingua_ar_r2_n30_mnt384_evidence.jsonl"),
    "CC-DFlash-R2": Path("results/task77_qmsum_long_cc_dflash_r2_n30_mnt384_evidence.jsonl"),
}
TASK76_CASES = Path("results/task76_qmsum_evidence_error_cases.jsonl")
DEFAULT_SUMMARY_OUTPUT = Path("results/task77_qmsum_evidence_policy_summary.json")
DEFAULT_TABLE_OUTPUT = Path("results/task77_qmsum_evidence_policy_table.csv")
DEFAULT_CASES_OUTPUT = Path("results/task77_qmsum_evidence_policy_cases.jsonl")

IMPROVED_LABELS = {
    "ACCEPTABLE_EVIDENCE_FOCUSED_ANSWER",
    "PROXY_WEAKNESS",
}
ERROR_LABELS = {
    "EVIDENCE_MISSING_OR_MISFOCUSED",
    "WRONG_NEGATIVE",
    "MISSING_ENTITY_OR_NUMBER",
    "ANSWER_TOO_GENERAL",
    "STILL_TOO_SHORT",
    "UNCLEAR",
    "POSSIBLE_COMPRESSION_EVIDENCE_LOSS",
}


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def _compact(text: Any, limit: int = 420) -> str:
    if not isinstance(text, str):
        return ""
    clean = " ".join(text.split())
    return clean[:limit] + ("..." if len(clean) > limit else "")


def _numeric(row: dict[str, Any], field: str) -> float:
    value = row.get(field)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _e2e(row: dict[str, Any]) -> float:
    return _numeric(row, "generation_time_s") + (_numeric(row, "t_compress_ms") / 1000.0)


def _by_prompt(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        value = row.get("benchmark_prompt_index", row.get("prompt_id"))
        if isinstance(value, int) and not isinstance(value, bool):
            result[value] = row
    return result


def _task76_lookup(cases: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    lookup: dict[tuple[str, int], dict[str, Any]] = {}
    for case in cases:
        condition = case.get("condition")
        prompt_id = case.get("prompt_id")
        if isinstance(condition, str) and isinstance(prompt_id, int) and not isinstance(prompt_id, bool):
            lookup[(condition, prompt_id)] = case
    return lookup


def _classify_task77_row(row: dict[str, Any]) -> dict[str, Any]:
    expected = str(row.get("expected_answer") or "")
    generated = str(row.get("generated_text") or "")
    diagnostics = lexical_diagnostics(expected, generated)
    return classify_case(
        {
            **row,
            "balanced_generated_snippet": generated,
            "label": row.get("task75_balanced_label", ""),
            "balanced_diagnostics": diagnostics,
            "balanced_output_tokens": row.get("output_tokens"),
            "balanced_e2e_latency_s": _e2e(row),
            "balanced_hit_cap": _hit_cap(row),
        }
    )


def _stage_summary(stage: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    overlaps = [lexical_diagnostics(row.get("expected_answer"), row.get("generated_text"))["unigram_overlap"] for row in rows]
    output_tokens = [_numeric(row, "output_tokens") for row in rows]
    e2e_times = [_e2e(row) for row in rows]
    total_output = sum(output_tokens)
    total_e2e = sum(e2e_times)
    return {
        "stage": stage,
        "rows": len(rows),
        "cap_hits": sum(1 for row in rows if _hit_cap(row)),
        "avg_normalized_overlap": round(_mean(overlaps), 6),
        "median_normalized_overlap": round(_median(overlaps), 6),
        "avg_output_tokens": round(_mean(output_tokens), 6),
        "avg_e2e_latency_s": round(_mean(e2e_times), 6),
        "e2e_tok_s_weighted": round(total_output / total_e2e, 6) if total_e2e > 0 else 0.0,
    }


def _condition_summary(condition: str, rows: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    labels = Counter(case["task77_evidence_error_label"] for case in cases)
    overlaps = [case["task77_overlap"] for case in cases]
    keyword_overlaps = [case["task77_keyword_overlap"] for case in cases]
    entity_overlaps = [case["task77_numeric_entity_overlap"] for case in cases]
    coverage = [case["task77_reference_answer_coverage"] for case in cases]
    output_tokens = [_numeric(row, "output_tokens") for row in rows]
    e2e_times = [_e2e(row) for row in rows]
    compress_ms = [_numeric(row, "t_compress_ms") for row in rows]
    prefill_ms = [_numeric(row, "t_prefill_ms") for row in rows]
    total_output = sum(output_tokens)
    total_generation = sum(_numeric(row, "generation_time_s") for row in rows)
    total_e2e = sum(e2e_times)
    policy_preserved = sum(1 for row in rows if row.get("qmsum_answer_policy_preserved") is True)
    return {
        "condition": condition,
        "rows": len(rows),
        "cap_hits": sum(1 for row in rows if _hit_cap(row)),
        "policy_preserved_count": policy_preserved,
        "policy_preservation_rate": round(policy_preserved / len(rows), 6) if rows else 0.0,
        "avg_normalized_overlap": round(_mean(overlaps), 6),
        "median_normalized_overlap": round(_median(overlaps), 6),
        "avg_output_tokens": round(_mean(output_tokens), 6),
        "avg_e2e_latency_s": round(_mean(e2e_times), 6),
        "e2e_tok_s_weighted": round(total_output / total_e2e, 6) if total_e2e > 0 else 0.0,
        "generation_tok_s_weighted": round(total_output / total_generation, 6) if total_generation > 0 else 0.0,
        "avg_t_compress_ms": round(_mean(compress_ms), 6),
        "avg_t_prefill_ms": round(_mean(prefill_ms), 6),
        "avg_keyword_overlap": round(_mean(keyword_overlaps), 6),
        "avg_numeric_entity_overlap": round(_mean(entity_overlaps), 6),
        "avg_reference_answer_coverage": round(_mean(coverage), 6),
        "low_overlap_count": sum(1 for value in overlaps if value < 0.20),
        "empty_output_count": sum(1 for row in rows if not str(row.get("generated_text") or "").strip()),
        "malformed_output_count": sum(1 for row in rows if len(str(row.get("generated_text") or "").split()) < 5),
        "repetition_count": sum(1 for row in rows if has_repetition(row.get("generated_text"))),
        "wrong_negative_count": labels["WRONG_NEGATIVE"],
        "evidence_misfocused_count": labels["EVIDENCE_MISSING_OR_MISFOCUSED"],
        "missing_entity_number_count": labels["MISSING_ENTITY_OR_NUMBER"],
        "answer_too_general_count": labels["ANSWER_TOO_GENERAL"],
        "acceptable_evidence_focused_count": labels["ACCEPTABLE_EVIDENCE_FOCUSED_ANSWER"],
        "proxy_weakness_count": labels["PROXY_WEAKNESS"],
        "unclear_count": labels["UNCLEAR"],
        "label_counts": dict(sorted(labels.items())),
    }


def _case_record(
    row: dict[str, Any],
    *,
    task76_case: dict[str, Any] | None,
) -> dict[str, Any]:
    classified = _classify_task77_row(row)
    task76_label = task76_case.get("evidence_error_label") if task76_case else None
    task77_label = classified["evidence_error_label"]
    diagnostics = lexical_diagnostics(row.get("expected_answer"), row.get("generated_text"))
    label_change = f"{task76_label}->{task77_label}" if task76_label else None
    return {
        "condition": row.get("condition"),
        "prompt_id": row.get("benchmark_prompt_index", row.get("prompt_id")),
        "fixture_id": row.get("fixture_id"),
        "expected_answer": _compact(row.get("expected_answer"), 520),
        "task75_balanced_label": task76_case.get("original_task75_label") if task76_case else None,
        "task76_evidence_error_label": task76_label,
        "task77_evidence_error_label": task77_label,
        "task77_generated_snippet": _compact(row.get("generated_text"), 520),
        "task77_output_tokens": row.get("output_tokens"),
        "task77_hit_cap": _hit_cap(row),
        "task77_policy_preserved": row.get("qmsum_answer_policy_preserved") is True,
        "task77_overlap": round(diagnostics["unigram_overlap"], 6),
        "task77_keyword_overlap": round(diagnostics["keyword_overlap"], 6),
        "task77_numeric_entity_overlap": round(diagnostics["numeric_entity_overlap"], 6),
        "task77_reference_answer_coverage": round(diagnostics["reference_answer_coverage"], 6),
        "task77_e2e_latency_s": round(_e2e(row), 6),
        "label_change_from_task76": label_change,
        "improvement_vs_task75_label": bool(task76_label in ERROR_LABELS and task77_label in IMPROVED_LABELS),
        "short_rationale": classified["short_rationale"],
        "missing_entities_or_numbers": classified["missing_entities_or_numbers"],
        "wrong_negative": classified["wrong_negative"],
        "evidence_misfocused": classified["evidence_misfocused"],
    }


def analyze_evidence_policy(
    task77_rows: dict[str, list[dict[str, Any]]],
    *,
    task76_cases: list[dict[str, Any]],
    task71_rows: dict[str, list[dict[str, Any]]] | None = None,
    task73_rows: dict[str, list[dict[str, Any]]] | None = None,
    task75_rows: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    task76 = _task76_lookup(task76_cases)
    output_cases: list[dict[str, Any]] = []
    by_condition: dict[str, dict[str, Any]] = {}
    table: list[dict[str, Any]] = []

    for condition, rows in sorted(task77_rows.items()):
        condition_cases: list[dict[str, Any]] = []
        for row in rows:
            prompt_id = row.get("benchmark_prompt_index", row.get("prompt_id"))
            task76_case = task76.get((condition, prompt_id)) if isinstance(prompt_id, int) else None
            case = _case_record(row, task76_case=task76_case)
            condition_cases.append(case)
            output_cases.append(case)

        summary = _condition_summary(condition, rows, condition_cases)
        stage_summaries = {
            "task77_evidence": _stage_summary("task77_evidence", rows),
        }
        for stage, source in (
            ("task71_original", task71_rows or {}),
            ("task73_terse", task73_rows or {}),
            ("task75_balanced", task75_rows or {}),
        ):
            if condition in source:
                stage_summaries[stage] = _stage_summary(stage, source[condition])
        summary["stage_summaries"] = stage_summaries
        by_condition[condition] = summary
        table.append({key: value for key, value in summary.items() if key not in {"stage_summaries", "label_counts"}})

    label_counts = Counter(case["task77_evidence_error_label"] for case in output_cases)
    task76_counts = Counter(case.get("task76_evidence_error_label") for case in output_cases if case.get("task76_evidence_error_label"))
    acceptable = label_counts["ACCEPTABLE_EVIDENCE_FOCUSED_ANSWER"] + label_counts["PROXY_WEAKNESS"]
    dominant_errors = (
        label_counts["EVIDENCE_MISSING_OR_MISFOCUSED"]
        + label_counts["WRONG_NEGATIVE"]
        + label_counts["MISSING_ENTITY_OR_NUMBER"]
        + label_counts["ANSWER_TOO_GENERAL"]
    )
    cap_hits = sum(case["task77_hit_cap"] for case in output_cases)
    policy_rate = _mean([summary["policy_preservation_rate"] for summary in by_condition.values()])
    keep_candidate = policy_rate == 1.0 and cap_hits == 0 and acceptable > dominant_errors
    summary = {
        "status": "PASS_WITH_NOTES",
        "total_rows": len(output_cases),
        "by_condition": by_condition,
        "task76_label_counts_for_matched_cases": dict(sorted(task76_counts.items())),
        "task77_label_counts": dict(sorted(label_counts.items())),
        "specific_prompt_checks": {
            str(prompt_id): [
                case
                for case in output_cases
                if case.get("prompt_id") == prompt_id
            ]
            for prompt_id in [14, 20, 23, 27, 28, 30]
        },
        "decisions": {
            "freeze_evidence_focused_policy": bool(keep_candidate),
            "revise_policy_again": bool(not keep_candidate and dominant_errors > acceptable),
            "move_to_compressed_prompt_context_audit": bool(not keep_candidate and dominant_errors > acceptable),
            "mnt512_needed": bool(cap_hits > 0),
            "qmsum_n100_justified": False,
            "recommended_next_task": (
                "Task 78 QMSum policy/proxy decision gate"
                if keep_candidate
                else "Task 78 compressed-prompt evidence-retention audit"
            ),
        },
    }
    return summary, table, output_cases


def _read_artifact_map(paths: dict[str, Path]) -> dict[str, list[dict[str, Any]]]:
    return {condition: load_jsonl(path) for condition, path in paths.items()}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 77 QMSum evidence-focused policy artifacts")
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--table-output", type=Path, default=DEFAULT_TABLE_OUTPUT)
    parser.add_argument("--cases-output", type=Path, default=DEFAULT_CASES_OUTPUT)
    args = parser.parse_args()

    summary, table, cases = analyze_evidence_policy(
        _read_artifact_map(TASK77_ARTIFACTS),
        task76_cases=load_jsonl(TASK76_CASES),
        task71_rows=_read_artifact_map(TASK71_ARTIFACTS),
        task73_rows=_read_artifact_map(TASK73_ARTIFACTS),
        task75_rows=_read_artifact_map(TASK75_ARTIFACTS),
    )
    summary["summary_output"] = str(args.summary_output)
    summary["table_output"] = str(args.table_output)
    summary["cases_output"] = str(args.cases_output)

    _write_json(args.summary_output, summary)
    _write_csv(args.table_output, table)
    _write_jsonl(args.cases_output, cases)
    print(json.dumps({
        "status": summary["status"],
        "total_rows": summary["total_rows"],
        "task77_label_counts": summary["task77_label_counts"],
        "decisions": summary["decisions"],
        "summary_output": str(args.summary_output),
        "table_output": str(args.table_output),
        "cases_output": str(args.cases_output),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
