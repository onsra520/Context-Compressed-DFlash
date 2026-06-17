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

from scripts.phase_1_system_build_and_evaluation.analysis.t70_qmsum_diagnostic_audit import (
    _condition_summary,
    _hit_cap,
    load_jsonl,
    normalized_token_overlap,
)

BEFORE_ARTIFACTS = {
    "LLMLingua-AR-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task71_qmsum_long_llmlingua_ar_r2_n30_mnt384.jsonl"),
    "CC-DFlash-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task71_qmsum_long_cc_dflash_r2_n30_mnt384.jsonl"),
}
AFTER_ARTIFACTS = {
    "LLMLingua-AR-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task73_qmsum_long_llmlingua_ar_r2_n30_mnt384_concise.jsonl"),
    "CC-DFlash-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task73_qmsum_long_cc_dflash_r2_n30_mnt384_concise.jsonl"),
}
DEFAULT_SUMMARY_OUTPUT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task73_qmsum_concise_policy_summary.json")
DEFAULT_TABLE_OUTPUT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task73_qmsum_concise_policy_table.csv")
DEFAULT_CASES_OUTPUT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task73_qmsum_concise_policy_cases.jsonl")
IMPROVEMENT_THRESHOLD = 0.05


def _by_prompt(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        value = row.get("benchmark_prompt_index", row.get("prompt_id"))
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        result[value] = row
    return result


def _policy_rate(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return sum(row.get("qmsum_concise_policy_preserved") is True for row in rows) / len(rows)


def _summary(condition: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary, _cases = _condition_summary(condition, rows)
    summary["qmsum_concise_policy_preserved_count"] = sum(
        row.get("qmsum_concise_policy_preserved") is True for row in rows
    )
    summary["qmsum_concise_policy_preservation_rate"] = _policy_rate(rows)
    return summary


def _case_record(
    *,
    condition: str,
    prompt_id: int,
    change_type: str,
    before_row: dict[str, Any],
    after_row: dict[str, Any],
    before_overlap: float,
    after_overlap: float,
) -> dict[str, Any]:
    return {
        "condition": condition,
        "prompt_id": prompt_id,
        "fixture_id": after_row.get("fixture_id") or before_row.get("fixture_id"),
        "change_type": change_type,
        "before_output_tokens": before_row.get("output_tokens"),
        "after_output_tokens": after_row.get("output_tokens"),
        "before_hit_cap": _hit_cap(before_row),
        "after_hit_cap": _hit_cap(after_row),
        "before_overlap": round(before_overlap, 6),
        "after_overlap": round(after_overlap, 6),
        "policy_preserved": after_row.get("qmsum_concise_policy_preserved"),
        "expected_answer": str(after_row.get("expected_answer") or before_row.get("expected_answer") or "")[:240],
        "before_generated_snippet": " ".join(str(before_row.get("generated_text") or "").split())[:320],
        "after_generated_snippet": " ".join(str(after_row.get("generated_text") or "").split())[:320],
    }


def _compare_condition(
    condition: str,
    before_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    before_by_id = _by_prompt(before_rows)
    after_by_id = _by_prompt(after_rows)
    shared_ids = sorted(set(before_by_id) & set(after_by_id))

    cap_to_noncap: list[int] = []
    noncap_to_cap: list[int] = []
    proxy_improved: list[int] = []
    proxy_degraded: list[int] = []
    cases: list[dict[str, Any]] = []

    for prompt_id in shared_ids:
        before_row = before_by_id[prompt_id]
        after_row = after_by_id[prompt_id]
        before_overlap = normalized_token_overlap(before_row.get("expected_answer"), before_row.get("generated_text"))
        after_overlap = normalized_token_overlap(after_row.get("expected_answer"), after_row.get("generated_text"))
        before_cap = _hit_cap(before_row)
        after_cap = _hit_cap(after_row)

        if before_cap and not after_cap:
            cap_to_noncap.append(prompt_id)
            cases.append(
                _case_record(
                    condition=condition,
                    prompt_id=prompt_id,
                    change_type="cap_to_noncap",
                    before_row=before_row,
                    after_row=after_row,
                    before_overlap=before_overlap,
                    after_overlap=after_overlap,
                )
            )
        if not before_cap and after_cap:
            noncap_to_cap.append(prompt_id)
            cases.append(
                _case_record(
                    condition=condition,
                    prompt_id=prompt_id,
                    change_type="noncap_to_cap",
                    before_row=before_row,
                    after_row=after_row,
                    before_overlap=before_overlap,
                    after_overlap=after_overlap,
                )
            )
        if after_overlap - before_overlap >= IMPROVEMENT_THRESHOLD:
            proxy_improved.append(prompt_id)
            cases.append(
                _case_record(
                    condition=condition,
                    prompt_id=prompt_id,
                    change_type="proxy_improved",
                    before_row=before_row,
                    after_row=after_row,
                    before_overlap=before_overlap,
                    after_overlap=after_overlap,
                )
            )
        if before_overlap - after_overlap >= IMPROVEMENT_THRESHOLD:
            proxy_degraded.append(prompt_id)
            cases.append(
                _case_record(
                    condition=condition,
                    prompt_id=prompt_id,
                    change_type="proxy_degraded",
                    before_row=before_row,
                    after_row=after_row,
                    before_overlap=before_overlap,
                    after_overlap=after_overlap,
                )
            )

    before_summary = _summary(condition, before_rows)
    after_summary = _summary(condition, after_rows)
    comparison = {
        "condition": condition,
        "shared_prompt_count": len(shared_ids),
        "before": before_summary,
        "after": after_summary,
        "cap_hit_delta": after_summary["hit_cap_count"] - before_summary["hit_cap_count"],
        "avg_output_tokens_delta": after_summary["avg_output_tokens"] - before_summary["avg_output_tokens"],
        "avg_overlap_delta": after_summary["avg_answer_token_overlap"] - before_summary["avg_answer_token_overlap"],
        "avg_e2e_latency_s_delta": after_summary["avg_e2e_latency_s"] - before_summary["avg_e2e_latency_s"],
        "cap_to_noncap_prompt_ids": cap_to_noncap,
        "noncap_to_cap_prompt_ids": noncap_to_cap,
        "proxy_improved_prompt_ids": proxy_improved,
        "proxy_degraded_prompt_ids": proxy_degraded,
        "policy_preservation_rate": after_summary["qmsum_concise_policy_preservation_rate"],
    }
    return comparison, cases


def _decision(comparisons: dict[str, dict[str, Any]]) -> dict[str, Any]:
    total_before_caps = sum(item["before"]["hit_cap_count"] for item in comparisons.values())
    total_after_caps = sum(item["after"]["hit_cap_count"] for item in comparisons.values())
    degraded = sum(len(item["proxy_degraded_prompt_ids"]) for item in comparisons.values())
    improved = sum(len(item["proxy_improved_prompt_ids"]) for item in comparisons.values())
    all_policy_preserved = all(item["policy_preservation_rate"] == 1.0 for item in comparisons.values())
    substantial_cap_drop = total_before_caps > 0 and total_after_caps <= max(1, total_before_caps // 4)
    avg_overlap_delta = sum(item["avg_overlap_delta"] for item in comparisons.values()) / len(comparisons)
    material_proxy_degradation = avg_overlap_delta < -0.05 or degraded > improved * 2

    return {
        "keep_concise_policy_as_qmsum_default": bool(
            all_policy_preserved and substantial_cap_drop and not material_proxy_degradation
        ),
        "mnt512_still_needed": bool(total_after_caps > 0),
        "qmsum_n100_justified": False,
        "qmsum_n100_reason": "Still blocked unless explicitly framed as speed-only and quality proxy policy is accepted.",
        "all_policy_preserved": all_policy_preserved,
        "total_before_cap_hits": total_before_caps,
        "total_after_cap_hits": total_after_caps,
        "total_proxy_improved": improved,
        "total_proxy_degraded": degraded,
        "average_overlap_delta": avg_overlap_delta,
        "material_proxy_degradation": material_proxy_degradation,
    }


def analyze_comparisons(
    before_rows_by_condition: dict[str, list[dict[str, Any]]],
    after_rows_by_condition: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    comparisons: dict[str, dict[str, Any]] = {}
    cases: list[dict[str, Any]] = []
    table: list[dict[str, Any]] = []

    for condition in sorted(set(before_rows_by_condition) & set(after_rows_by_condition)):
        comparison, condition_cases = _compare_condition(
            condition,
            before_rows_by_condition[condition],
            after_rows_by_condition[condition],
        )
        comparisons[condition] = comparison
        cases.extend(condition_cases)
        for phase in ("before", "after"):
            summary = comparison[phase]
            table.append(
                {
                    "condition": condition,
                    "phase": phase,
                    "rows": summary["rows"],
                    "hit_cap_count": summary["hit_cap_count"],
                    "avg_output_tokens": summary["avg_output_tokens"],
                    "avg_answer_token_overlap": summary["avg_answer_token_overlap"],
                    "normalized_containment_count": summary["normalized_containment_count"],
                    "repetition_count": summary["repetition_count"],
                    "empty_output_count": summary["empty_output_count"],
                    "avg_e2e_latency_s": summary["avg_e2e_latency_s"],
                    "e2e_tok_per_sec_weighted": summary["e2e_tok_per_sec_weighted"],
                    "avg_t_compress_ms": summary["avg_t_compress_ms"],
                    "avg_compression_ratio": summary["avg_compression_ratio"],
                    "policy_preservation_rate": summary["qmsum_concise_policy_preservation_rate"],
                }
            )

    summary = {
        "task": "73-qmsum-concise-policy",
        "status": "PASS_WITH_NOTES",
        "comparisons": comparisons,
        "decisions": _decision(comparisons),
        "claim_policy": "preliminary only; no final speedup, correctness, deployment, or end-to-end benefit claim",
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
    parser = argparse.ArgumentParser(description="Analyze Task 73 QMSum concise-policy calibration")
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--table-output", type=Path, default=DEFAULT_TABLE_OUTPUT)
    parser.add_argument("--cases-output", type=Path, default=DEFAULT_CASES_OUTPUT)
    args = parser.parse_args()

    before = {condition: load_jsonl(path) for condition, path in BEFORE_ARTIFACTS.items()}
    after = {condition: load_jsonl(path) for condition, path in AFTER_ARTIFACTS.items()}
    summary, table, cases = analyze_comparisons(before, after)

    _write_json(args.summary_output, summary)
    _write_csv(args.table_output, table)
    _write_jsonl(args.cases_output, cases)

    print(
        json.dumps(
            {
                "status": summary["status"],
                "keep_concise_policy_as_qmsum_default": summary["decisions"][
                    "keep_concise_policy_as_qmsum_default"
                ],
                "mnt512_still_needed": summary["decisions"]["mnt512_still_needed"],
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
