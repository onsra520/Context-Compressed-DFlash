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

from scripts.phase_1_analysis.analyze_task70_qmsum_diagnostic_audit import (
    _condition_summary as base_condition_summary,
    _hit_cap,
    _tokens,
    has_repetition,
    load_jsonl,
    normalized_token_overlap,
)
from scripts.phase_1_analysis.analyze_task74_qmsum_proxy_case_triage import lexical_diagnostics

ORIGINAL_ARTIFACTS = {
    "LLMLingua-AR-R2": Path("results/task71_qmsum_long_llmlingua_ar_r2_n30_mnt384.jsonl"),
    "CC-DFlash-R2": Path("results/task71_qmsum_long_cc_dflash_r2_n30_mnt384.jsonl"),
}
TERSE_ARTIFACTS = {
    "LLMLingua-AR-R2": Path("results/task73_qmsum_long_llmlingua_ar_r2_n30_mnt384_concise.jsonl"),
    "CC-DFlash-R2": Path("results/task73_qmsum_long_cc_dflash_r2_n30_mnt384_concise.jsonl"),
}
BALANCED_ARTIFACTS = {
    "LLMLingua-AR-R2": Path("results/task75_qmsum_long_llmlingua_ar_r2_n30_mnt384_balanced.jsonl"),
    "CC-DFlash-R2": Path("results/task75_qmsum_long_cc_dflash_r2_n30_mnt384_balanced.jsonl"),
}
DEFAULT_SUMMARY_OUTPUT = Path("results/task75_qmsum_balanced_policy_summary.json")
DEFAULT_TABLE_OUTPUT = Path("results/task75_qmsum_balanced_policy_table.csv")
DEFAULT_CASES_OUTPUT = Path("results/task75_qmsum_balanced_policy_cases.jsonl")


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _by_prompt(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        value = row.get("benchmark_prompt_index", row.get("prompt_id"))
        if isinstance(value, int) and not isinstance(value, bool):
            result[value] = row
    return result


def _compact(text: Any, limit: int = 420) -> str:
    if not isinstance(text, str):
        return ""
    clean = " ".join(text.split())
    return clean[:limit] + ("..." if len(clean) > limit else "")


def _e2e(row: dict[str, Any]) -> float:
    generation = row.get("generation_time_s")
    compress = row.get("t_compress_ms")
    generation_s = float(generation) if isinstance(generation, (int, float)) and not isinstance(generation, bool) else 0.0
    compress_s = float(compress) / 1000.0 if isinstance(compress, (int, float)) and not isinstance(compress, bool) else 0.0
    return generation_s + compress_s


def _policy_preserved(row: dict[str, Any]) -> bool:
    return row.get("qmsum_answer_policy_preserved") is True


def _stage_summary(condition: str, stage: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary, _cases = base_condition_summary(condition, rows)
    policy_count = sum(1 for row in rows if _policy_preserved(row))
    summary.update(
        {
            "stage": stage,
            "qmsum_answer_policy_preserved_count": policy_count,
            "qmsum_answer_policy_preservation_rate": round(policy_count / len(rows), 6) if rows else 0.0,
            "qmsum_answer_policy_types": sorted(
                {str(row.get("qmsum_answer_policy_type")) for row in rows if row.get("qmsum_answer_policy_type")}
            ),
        }
    )
    return summary


def _answers_naturally(row: dict[str, Any]) -> bool:
    text = str(row.get("generated_text") or "").strip()
    if not text:
        return False
    if has_repetition(text):
        return False
    tokens = _tokens(text)
    if len(tokens) < 8:
        return False
    return text[-1] in ".!?"


def _label_case(
    original_row: dict[str, Any],
    terse_row: dict[str, Any],
    balanced_row: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    expected = balanced_row.get("expected_answer") or terse_row.get("expected_answer") or original_row.get("expected_answer")
    original_diag = lexical_diagnostics(expected, original_row.get("generated_text"))
    terse_diag = lexical_diagnostics(expected, terse_row.get("generated_text"))
    balanced_diag = lexical_diagnostics(expected, balanced_row.get("generated_text"))
    balanced_cap = _hit_cap(balanced_row)
    terse_cap = _hit_cap(terse_row)
    original_cap = _hit_cap(original_row)

    overlap_gain_vs_terse = balanced_diag["unigram_overlap"] - terse_diag["unigram_overlap"]
    keyword_gain_vs_terse = balanced_diag["keyword_overlap"] - terse_diag["keyword_overlap"]
    overlap_gap_vs_original = original_diag["unigram_overlap"] - balanced_diag["unigram_overlap"]
    balanced_direct = _answers_naturally(balanced_row)

    if balanced_cap:
        label = "CAP_PRESSURE_RETURNED"
    elif (
        overlap_gain_vs_terse >= 0.05
        and keyword_gain_vs_terse >= 0.05
        and balanced_diag["keyword_overlap"] >= 0.45
    ):
        label = "BALANCED_RECOVERS_DETAILS"
    elif balanced_direct and balanced_diag["keyword_overlap"] >= 0.45 and balanced_diag["unigram_overlap"] >= 0.25:
        label = "ACCEPTABLE_BALANCED_ANSWER"
    elif balanced_direct and balanced_diag["keyword_overlap"] < 0.35:
        label = "STILL_TOO_SHORT"
    elif overlap_gap_vs_original >= 0.12 and balanced_diag["unigram_overlap"] < 0.30:
        label = "TRUE_QUALITY_DEGRADATION_POSSIBLE"
    elif balanced_direct and overlap_gap_vs_original >= 0.08 and balanced_diag["keyword_overlap"] >= 0.40:
        label = "PROXY_WEAKNESS"
    else:
        label = "UNCLEAR"

    diagnostics = {
        "original_hit_cap": original_cap,
        "terse_hit_cap": terse_cap,
        "balanced_hit_cap": balanced_cap,
        "original_diagnostics": original_diag,
        "terse_diagnostics": terse_diag,
        "balanced_diagnostics": balanced_diag,
        "balanced_overlap_gain_vs_terse": round(overlap_gain_vs_terse, 6),
        "balanced_keyword_gain_vs_terse": round(keyword_gain_vs_terse, 6),
        "balanced_overlap_gap_vs_original": round(overlap_gap_vs_original, 6),
        "balanced_answers_naturally": balanced_direct,
    }
    return label, diagnostics


def _case_record(
    condition: str,
    prompt_id: int,
    original_row: dict[str, Any],
    terse_row: dict[str, Any],
    balanced_row: dict[str, Any],
) -> dict[str, Any]:
    label, diagnostics = _label_case(original_row, terse_row, balanced_row)
    return {
        "condition": condition,
        "prompt_id": prompt_id,
        "fixture_id": balanced_row.get("fixture_id") or terse_row.get("fixture_id") or original_row.get("fixture_id"),
        "label": label,
        "expected_answer": _compact(
            balanced_row.get("expected_answer") or terse_row.get("expected_answer") or original_row.get("expected_answer"),
            300,
        ),
        "original_generated_snippet": _compact(original_row.get("generated_text")),
        "terse_generated_snippet": _compact(terse_row.get("generated_text")),
        "balanced_generated_snippet": _compact(balanced_row.get("generated_text")),
        "original_output_tokens": original_row.get("output_tokens"),
        "terse_output_tokens": terse_row.get("output_tokens"),
        "balanced_output_tokens": balanced_row.get("output_tokens"),
        "original_e2e_latency_s": round(_e2e(original_row), 6),
        "terse_e2e_latency_s": round(_e2e(terse_row), 6),
        "balanced_e2e_latency_s": round(_e2e(balanced_row), 6),
        "qmsum_answer_policy_preserved": balanced_row.get("qmsum_answer_policy_preserved"),
        "qmsum_answer_policy_type": balanced_row.get("qmsum_answer_policy_type"),
        **diagnostics,
    }


def _condition_case_summary(condition: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    labels = Counter(case["label"] for case in cases)
    return {
        "condition": condition,
        "rows": len(cases),
        "original_cap_hits": sum(1 for case in cases if case["original_hit_cap"]),
        "terse_cap_hits": sum(1 for case in cases if case["terse_hit_cap"]),
        "balanced_cap_hits": sum(1 for case in cases if case["balanced_hit_cap"]),
        "avg_original_overlap": round(_mean([case["original_diagnostics"]["unigram_overlap"] for case in cases]), 6),
        "avg_terse_overlap": round(_mean([case["terse_diagnostics"]["unigram_overlap"] for case in cases]), 6),
        "avg_balanced_overlap": round(_mean([case["balanced_diagnostics"]["unigram_overlap"] for case in cases]), 6),
        "avg_original_e2e_latency_s": round(_mean([case["original_e2e_latency_s"] for case in cases]), 6),
        "avg_terse_e2e_latency_s": round(_mean([case["terse_e2e_latency_s"] for case in cases]), 6),
        "avg_balanced_e2e_latency_s": round(_mean([case["balanced_e2e_latency_s"] for case in cases]), 6),
        "label_counts": dict(sorted(labels.items())),
    }


def _decision(by_condition: dict[str, dict[str, Any]]) -> dict[str, Any]:
    labels = Counter()
    total_balanced_caps = 0
    total_rows = 0
    all_policy_preserved = True
    avg_terse_to_balanced_delta: list[float] = []
    avg_original_to_balanced_delta: list[float] = []
    for summary in by_condition.values():
        labels.update(summary["label_counts"])
        total_balanced_caps += int(summary["balanced_cap_hits"])
        total_rows += int(summary["cases"]["rows"])
        stage_summaries = summary["stage_summaries"]
        all_policy_preserved = (
            all_policy_preserved
            and stage_summaries["balanced"]["qmsum_answer_policy_preservation_rate"] == 1.0
        )
        avg_terse_to_balanced_delta.append(
            stage_summaries["balanced"]["avg_answer_token_overlap"]
            - stage_summaries["terse"]["avg_answer_token_overlap"]
        )
        avg_original_to_balanced_delta.append(
            stage_summaries["balanced"]["avg_answer_token_overlap"]
            - stage_summaries["original"]["avg_answer_token_overlap"]
        )

    recovered = labels["BALANCED_RECOVERS_DETAILS"] + labels["ACCEPTABLE_BALANCED_ANSWER"]
    concerning = labels["CAP_PRESSURE_RETURNED"] + labels["STILL_TOO_SHORT"] + labels["TRUE_QUALITY_DEGRADATION_POSSIBLE"]
    avg_recovery_delta = _mean(avg_terse_to_balanced_delta)
    avg_gap_delta = _mean(avg_original_to_balanced_delta)
    keep_candidate = (
        all_policy_preserved
        and total_balanced_caps <= max(1, total_rows // 10)
        and avg_recovery_delta > 0
        and recovered >= concerning
    )
    revise_shorter = total_balanced_caps > max(1, total_rows // 5)
    revise_for_detail = labels["STILL_TOO_SHORT"] > recovered or labels["TRUE_QUALITY_DEGRADATION_POSSIBLE"] > 0
    return {
        "label_counts": dict(sorted(labels.items())),
        "all_balanced_policy_preserved": all_policy_preserved,
        "total_balanced_cap_hits": total_balanced_caps,
        "average_overlap_delta_balanced_vs_terse": round(avg_recovery_delta, 6),
        "average_overlap_delta_balanced_vs_original": round(avg_gap_delta, 6),
        "keep_balanced_policy_as_qmsum_candidate": bool(keep_candidate),
        "revise_balanced_policy_shorter": bool(revise_shorter),
        "revise_balanced_policy_for_more_detail": bool(revise_for_detail and not keep_candidate),
        "reject_balanced_policy": bool(total_balanced_caps > total_rows // 2 if total_rows else False),
        "mnt512_needed": bool(total_balanced_caps > 0),
        "qmsum_n100_justified": False,
        "qmsum_n100_reason": (
            "Balanced policy can become a candidate, but this calibration alone should not launch QMSum n=100."
            if keep_candidate
            else "Blocked until QMSum balanced policy and proxy behavior are accepted."
        ),
    }


def analyze_policy_stages(
    original_rows_by_condition: dict[str, list[dict[str, Any]]],
    terse_rows_by_condition: dict[str, list[dict[str, Any]]],
    balanced_rows_by_condition: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    conditions = sorted(set(original_rows_by_condition) & set(terse_rows_by_condition) & set(balanced_rows_by_condition))
    by_condition: dict[str, dict[str, Any]] = {}
    table: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []

    for condition in conditions:
        stage_rows = {
            "original": original_rows_by_condition[condition],
            "terse": terse_rows_by_condition[condition],
            "balanced": balanced_rows_by_condition[condition],
        }
        stage_summaries = {
            stage: _stage_summary(condition, stage, rows)
            for stage, rows in stage_rows.items()
        }
        for stage, stage_summary in stage_summaries.items():
            table.append(
                {
                    "condition": condition,
                    "stage": stage,
                    "rows": stage_summary["rows"],
                    "hit_cap_count": stage_summary["hit_cap_count"],
                    "avg_output_tokens": round(stage_summary["avg_output_tokens"], 6),
                    "avg_answer_token_overlap": stage_summary["avg_answer_token_overlap"],
                    "normalized_containment_count": stage_summary["normalized_containment_count"],
                    "empty_output_count": stage_summary["empty_output_count"],
                    "repetition_count": stage_summary["repetition_count"],
                    "malformed_output_count": stage_summary["malformed_output_count"],
                    "avg_e2e_latency_s": round(stage_summary["avg_e2e_latency_s"], 6),
                    "e2e_tok_per_sec_weighted": round(stage_summary["e2e_tok_per_sec_weighted"], 6),
                    "avg_t_compress_ms": round(stage_summary["avg_t_compress_ms"], 6),
                    "avg_compression_ratio": round(stage_summary["avg_compression_ratio"], 6),
                    "qmsum_answer_policy_preservation_rate": stage_summary[
                        "qmsum_answer_policy_preservation_rate"
                    ],
                }
            )

        by_stage_prompt = {stage: _by_prompt(rows) for stage, rows in stage_rows.items()}
        prompt_ids = sorted(set(by_stage_prompt["original"]) & set(by_stage_prompt["terse"]) & set(by_stage_prompt["balanced"]))
        condition_cases = [
            _case_record(
                condition,
                prompt_id,
                by_stage_prompt["original"][prompt_id],
                by_stage_prompt["terse"][prompt_id],
                by_stage_prompt["balanced"][prompt_id],
            )
            for prompt_id in prompt_ids
        ]
        cases.extend(condition_cases)
        by_condition[condition] = {
            "condition": condition,
            "stage_summaries": stage_summaries,
            "cases": _condition_case_summary(condition, condition_cases),
            "label_counts": _condition_case_summary(condition, condition_cases)["label_counts"],
            "balanced_cap_hits": stage_summaries["balanced"]["hit_cap_count"],
        }

    summary = {
        "task": "75-qmsum-balanced-policy",
        "status": "PASS_WITH_NOTES",
        "by_condition": by_condition,
        "decisions": _decision(by_condition),
        "claim_policy": "preliminary QMSum policy calibration only; no final speedup/correctness/deployment claim",
    }
    return summary, table, cases


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 75 QMSum balanced-policy calibration")
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--table-output", type=Path, default=DEFAULT_TABLE_OUTPUT)
    parser.add_argument("--cases-output", type=Path, default=DEFAULT_CASES_OUTPUT)
    args = parser.parse_args()

    original = {condition: load_jsonl(path) for condition, path in ORIGINAL_ARTIFACTS.items()}
    terse = {condition: load_jsonl(path) for condition, path in TERSE_ARTIFACTS.items()}
    balanced = {condition: load_jsonl(path) for condition, path in BALANCED_ARTIFACTS.items()}
    summary, table, cases = analyze_policy_stages(original, terse, balanced)
    _write_json(args.summary_output, summary)
    _write_csv(args.table_output, table)
    _write_jsonl(args.cases_output, cases)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "keep_balanced_policy_as_qmsum_candidate": summary["decisions"][
                    "keep_balanced_policy_as_qmsum_candidate"
                ],
                "mnt512_needed": summary["decisions"]["mnt512_needed"],
                "qmsum_n100_justified": summary["decisions"]["qmsum_n100_justified"],
                "summary_output": str(args.summary_output),
                "table_output": str(args.table_output),
                "cases_output": str(args.cases_output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
