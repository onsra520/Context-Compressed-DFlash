from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_analysis.analyze_task47_quality_refinement import classify_row
from scripts.phase_1_analysis.analyze_task69_gsm8k_full_matrix import load_jsonl


GSM8K_ARTIFACTS = {
    "Baseline-AR": Path("results/task69_gsm8k_short_baseline_ar_n30_mnt384.jsonl"),
    "DFlash-R1": Path("results/task69_gsm8k_short_dflash_r1_n30_mnt384.jsonl"),
    "LLMLingua-AR-R2": Path("results/task66_gsm8k_short_llmlingua_ar_r2_n30_mnt384_rerun.jsonl"),
    "CC-DFlash-R2": Path("results/task66_gsm8k_short_cc_dflash_r2_n30_mnt384_rerun.jsonl"),
}
QMSUM_DECISION = Path("results/task79_qmsum_reporting_decision.json")
QMSUM_RETENTION = Path("results/task78_qmsum_evidence_retention_summary.json")
QMSUM_FULL_MATRIX = Path("results/task71_qmsum_n30_full_matrix_summary.json")
QMSUM_POLICY_SUMMARIES = {
    "task73_terse": Path("results/task73_qmsum_concise_policy_summary.json"),
    "task75_balanced": Path("results/task75_qmsum_balanced_policy_summary.json"),
    "task77_evidence_focused": Path("results/task77_qmsum_evidence_policy_summary.json"),
}
DEFAULT_SUMMARY_OUTPUT = Path("results/task80_cross_dataset_final_summary.json")
DEFAULT_TABLE_OUTPUT = Path("results/task80_cross_dataset_final_table.csv")
DEFAULT_CLAIMS_OUTPUT = Path("results/task80_cross_dataset_claims_matrix.csv")
DEFAULT_KEY_POINTS_OUTPUT = Path("results/task80_final_report_key_points.json")


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


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_gsm8k_condition(condition: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    classifications = [
        classify_row(row, row_index=index, condition=condition, artifact=f"{condition}.jsonl")
        for index, row in enumerate(rows, start=1)
    ]
    output_tokens = _numbers(rows, "output_tokens")
    generation_times = _numbers(rows, "generation_time_s")
    e2e_times = [
        float(row.get("generation_time_s", 0.0)) + float(row.get("t_compress_ms", 0.0)) / 1000.0
        for row in rows
        if isinstance(row.get("generation_time_s"), (int, float))
    ]
    total_output = sum(output_tokens)
    total_generation_time = sum(generation_times)
    total_e2e_time = sum(e2e_times)
    numeric_matches = sum(1 for item in classifications if item.get("numeric_match"))
    exact_matches = sum(1 for item in classifications if item.get("exact_match"))
    compressed = condition in {"LLMLingua-AR-R2", "CC-DFlash-R2"}
    avg_compression_ratio = _mean(_numbers(rows, "actual_compression_ratio", "compression_ratio", "R_actual"))
    summary = {
        "condition": condition,
        "dataset_role": "short-context numeric quality",
        "n": len(rows),
        "max_new_tokens": int(_numbers(rows, "max_new_tokens")[0]) if rows and _numbers(rows, "max_new_tokens") else None,
        "keep_rate": _number(rows[0], "keep_rate") if rows else None,
        "compression": compressed,
        "uses_dflash": condition in {"DFlash-R1", "CC-DFlash-R2"},
        "numeric_matches": numeric_matches,
        "numeric_accuracy": round(numeric_matches / len(rows), 6) if rows else 0.0,
        "exact_containment_matches": exact_matches,
        "exact_containment_rate": round(exact_matches / len(rows), 6) if rows else 0.0,
        "cap_hits": sum(1 for row in rows if _hit_cap(row)),
        "avg_input_tokens": round(_mean(_numbers(rows, "input_tokens")), 6),
        "avg_output_tokens": round(_mean(output_tokens), 6),
        "avg_generation_latency_s": round(_mean(generation_times), 6),
        "avg_e2e_latency_s": round(_mean(e2e_times), 6),
        "generation_tok_per_sec": round(total_output / total_generation_time, 6) if total_generation_time else 0.0,
        "e2e_tok_per_sec": round(total_output / total_e2e_time, 6) if total_e2e_time else 0.0,
        "avg_t_compress_ms": round(_mean(_numbers(rows, "t_compress_ms")), 6),
        "avg_t_prefill_ms": round(_mean(_numbers(rows, "t_prefill_ms")), 6),
        "avg_tau_mean": round(_mean(_numbers(rows, "tau_mean")), 6),
        "compression_ratio": round(avg_compression_ratio, 6) if avg_compression_ratio else 0.0,
        "avg_original_input_tokens": round(_mean(_numbers(rows, "original_input_tokens")), 6),
        "avg_compressed_input_tokens": round(_mean(_numbers(rows, "compressed_input_tokens")), 6),
    }
    if condition == "Baseline-AR":
        summary["main_interpretation"] = "Strongest or near-strongest short-context numeric quality; speed is secondary."
    elif condition == "DFlash-R1":
        summary["main_interpretation"] = "Improves decoding speed strongly while preserving comparable n=30 numeric quality."
    elif condition == "LLMLingua-AR-R2":
        summary["main_interpretation"] = "Compression-only attribution baseline; compression overhead dominates e2e latency on GSM8K."
    else:
        summary["main_interpretation"] = "Matches compressed AR quality and improves e2e latency versus LLMLingua-AR-R2 in n=30."
    return summary


def build_claims_matrix() -> list[dict[str, str]]:
    return [
        {
            "claim": "CC-DFlash improves e2e over LLMLingua-AR-R2 on GSM8K n30.",
            "status": "allowed_with_caveat",
            "reason": "Task 69/66 artifacts show CC-DFlash-R2 has higher e2e tok/s than LLMLingua-AR-R2 at the same n=30 quality setting.",
            "evidence_source": "Task 69 GSM8K matrix and Task 66 compressed rerun artifacts",
            "suggested_wording": "In the bounded GSM8K n=30 setting, CC-DFlash-R2 improved e2e latency versus LLMLingua-AR-R2 while matching compressed-path numeric quality.",
        },
        {
            "claim": "DFlash-R1 is fastest on GSM8K n30.",
            "status": "allowed_with_caveat",
            "reason": "DFlash-R1 has the highest e2e tok/s in the GSM8K n=30 matrix, but this is not a universal claim.",
            "evidence_source": "Task 69 GSM8K matrix",
            "suggested_wording": "DFlash-R1 was the fastest GSM8K n=30 condition in this local run.",
        },
        {
            "claim": "Compression always improves e2e latency.",
            "status": "forbidden",
            "reason": "LLMLingua compression overhead can dominate e2e latency, especially on short-context GSM8K.",
            "evidence_source": "Task 69/66 GSM8K artifacts",
            "suggested_wording": "Avoid this claim.",
        },
        {
            "claim": "QMSum proves semantic correctness.",
            "status": "forbidden",
            "reason": "QMSum quality is only lexical/normalized-text proxy quality without manual or semantic judging.",
            "evidence_source": "Task 79B reporting decision",
            "suggested_wording": "Avoid this claim.",
        },
        {
            "claim": "QMSum is useful as long-context diagnostic benchmark.",
            "status": "allowed",
            "reason": "QMSum stresses long-context latency, prefill, compression overhead, compression ratio, and proxy quality.",
            "evidence_source": "Tasks 71-79B",
            "suggested_wording": "QMSum is used as a long-context diagnostic benchmark, not as final semantic correctness proof.",
        },
        {
            "claim": "Task 78 proves compression never deletes evidence.",
            "status": "forbidden",
            "reason": "Task 78 audited selected cases only and uses lexical evidence heuristics.",
            "evidence_source": "Task 78 evidence-retention audit",
            "suggested_wording": "Avoid this claim.",
        },
        {
            "claim": "Task 78 did not support broad compressed-evidence deletion as main explanation in selected audited cases.",
            "status": "allowed_with_caveat",
            "reason": "Selected reconstructed cases showed retained/partial evidence, source/reference mismatch, and unclear cases, with no broad missing-compressed-evidence label.",
            "evidence_source": "Task 78 evidence-retention audit",
            "suggested_wording": "Task 78 did not support broad compressed-evidence deletion as the main explanation in selected audited QMSum cases.",
        },
        {
            "claim": "Remaining QMSum failures are consistent with constrained local target-model evidence-grounding limitations.",
            "status": "allowed_with_caveat",
            "reason": "Task 78 found retained evidence in some failed cases and Task 79B freezes QMSum as diagnostic only.",
            "evidence_source": "Tasks 76-79B",
            "suggested_wording": "Remaining QMSum failures are consistent with constrained local evidence-location/grounding limits, possible source mismatch, and lexical proxy limits.",
        },
        {
            "claim": "Final system is deployment ready.",
            "status": "forbidden",
            "reason": "No deployment readiness evaluation was performed.",
            "evidence_source": "Project claim policy",
            "suggested_wording": "Avoid this claim.",
        },
        {
            "claim": "8 GB deployment is confirmed.",
            "status": "forbidden",
            "reason": "The project has not proven deployment readiness or confirmed 8 GB fit.",
            "evidence_source": "Project claim policy",
            "suggested_wording": "Avoid this claim.",
        },
        {
            "claim": "CC-DFlash is universally better than Baseline.",
            "status": "forbidden",
            "reason": "Results are conditional and dataset-dependent; DFlash-R1 is faster on short-context GSM8K.",
            "evidence_source": "Task 69 GSM8K matrix and Task 79B QMSum decision",
            "suggested_wording": "Avoid this claim.",
        },
        {
            "claim": "CC-DFlash is useful only under conditions where compression and DFlash gains outweigh compression overhead.",
            "status": "allowed",
            "reason": "This is the conservative system-level tradeoff supported by the evidence.",
            "evidence_source": "Cross-dataset synthesis",
            "suggested_wording": "CC-DFlash should be treated as a conditional system-level tradeoff.",
        },
    ]


def build_cross_dataset_package(
    *,
    gsm8k_rows_by_condition: dict[str, list[dict[str, Any]]],
    qmsum_decision: dict[str, Any],
    qmsum_retention_summary: dict[str, Any],
    qmsum_full_matrix_summary: dict[str, Any],
    qmsum_policy_summaries: dict[str, Any],
) -> dict[str, Any]:
    gsm8k_by_condition = {
        condition: summarize_gsm8k_condition(condition, rows)
        for condition, rows in gsm8k_rows_by_condition.items()
    }
    baseline = gsm8k_by_condition["Baseline-AR"]
    dflash = gsm8k_by_condition["DFlash-R1"]
    llm = gsm8k_by_condition["LLMLingua-AR-R2"]
    cc = gsm8k_by_condition["CC-DFlash-R2"]
    qmsum_task71 = qmsum_full_matrix_summary.get("by_condition", {})
    package = {
        "status": "PASS_WITH_NOTES",
        "claim_policy": "Conservative final packaging only; no final speedup, semantic correctness, deployment, or 8 GB claim.",
        "datasets": {
            "gsm8k_short": {
                "role": "short-context numeric quality",
                "quality_metric": "numeric exact-match proxy",
                "conditions": gsm8k_by_condition,
                "summary": {
                    "baseline_numeric": f"{baseline['numeric_matches']}/{baseline['n']}",
                    "dflash_numeric": f"{dflash['numeric_matches']}/{dflash['n']}",
                    "llmlingua_ar_numeric": f"{llm['numeric_matches']}/{llm['n']}",
                    "cc_dflash_numeric": f"{cc['numeric_matches']}/{cc['n']}",
                    "dflash_e2e_speedup_vs_baseline": round(
                        dflash["e2e_tok_per_sec"] / baseline["e2e_tok_per_sec"], 6
                    )
                    if baseline["e2e_tok_per_sec"]
                    else 0.0,
                    "cc_dflash_e2e_speedup_vs_llmlingua_ar": round(
                        cc["e2e_tok_per_sec"] / llm["e2e_tok_per_sec"], 6
                    )
                    if llm["e2e_tok_per_sec"]
                    else 0.0,
                    "dflash_fastest": dflash["e2e_tok_per_sec"]
                    == max(item["e2e_tok_per_sec"] for item in gsm8k_by_condition.values()),
                    "compressed_quality_comparable": cc["numeric_matches"] == llm["numeric_matches"],
                },
            },
            "qmsum_meeting_qa_long": {
                "role": "long-context diagnostic behavior",
                "quality_metric": "lexical/normalized-text proxy only",
                "semantic_correctness_claimed": False,
                "final_role_decision": qmsum_decision.get("qmsum_final_role"),
                "n100_justified": qmsum_decision.get("qmsum_n100_justified"),
                "mnt512_needed": qmsum_decision.get("mnt512_needed"),
                "more_suffix_tuning_justified": qmsum_decision.get("more_suffix_tuning_justified"),
                "task71_by_condition": {
                    condition: {
                        "rows": data.get("rows"),
                        "avg_answer_token_overlap": data.get("avg_answer_token_overlap"),
                        "hit_cap_count": data.get("hit_cap_count"),
                        "avg_e2e_latency_s": data.get("avg_e2e_latency_s"),
                        "e2e_tok_per_sec_weighted": data.get("e2e_tok_per_sec_weighted"),
                        "avg_t_compress_ms": data.get("avg_t_compress_ms"),
                        "avg_t_prefill_ms": data.get("avg_t_prefill_ms"),
                        "avg_compression_ratio": data.get("avg_compression_ratio"),
                    }
                    for condition, data in qmsum_task71.items()
                },
                "task78_evidence_retention_labels": qmsum_retention_summary.get(
                    "count_by_evidence_retention_label", {}
                ),
                "task79_decision": {
                    "quality_claim_level": qmsum_decision.get("qmsum_quality_claim_level"),
                    "speed_claim_level": qmsum_decision.get("qmsum_speed_claim_level"),
                    "recommended_next_task": qmsum_decision.get("recommended_next_task"),
                },
                "policy_summary_sources": sorted(qmsum_policy_summaries),
            },
        },
        "cross_dataset_conclusion": {
            "hypothesis_status": "partially_supported_conditionally",
            "english": (
                "The project partially supports the CC-DFlash hypothesis under bounded local evaluation. "
                "DFlash improves decoding speed, and CC-DFlash can recover part of that speed on compressed prompts "
                "while keeping GSM8K numeric quality comparable to compressed AR. However, LLMLingua compression "
                "overhead can dominate e2e latency, and long-context QMSum quality remains diagnostic rather than semantic."
            ),
            "vietnamese": (
                "Kết quả hỗ trợ một phần giả thuyết CC-DFlash trong phạm vi đánh giá local có giới hạn. "
                "DFlash cải thiện tốc độ decoding, và CC-DFlash có thể giữ lại một phần lợi ích tốc độ đó trên "
                "compressed prompts trong khi chất lượng GSM8K tương đương compressed AR. Tuy nhiên, overhead của "
                "LLMLingua có thể chi phối latency end-to-end, và chất lượng QMSum long-context chỉ nên được xem "
                "là diagnostic chứ không phải semantic correctness."
            ),
        },
        "claims_matrix": build_claims_matrix(),
    }
    return package


def final_table_rows(package: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for condition, item in package["datasets"]["gsm8k_short"]["conditions"].items():
        rows.append(
            {
                "dataset": "gsm8k_short",
                "role": "short-context numeric quality",
                "condition": condition,
                "n": item["n"],
                "quality_metric": "numeric exact-match proxy",
                "quality_result": f"{item['numeric_matches']}/{item['n']}",
                "avg_e2e_latency_s": item["avg_e2e_latency_s"],
                "e2e_tok_per_sec": item["e2e_tok_per_sec"],
                "avg_t_compress_ms": item["avg_t_compress_ms"],
                "compression_ratio": item["compression_ratio"],
                "interpretation": item["main_interpretation"],
            }
        )
    qmsum = package["datasets"]["qmsum_meeting_qa_long"]
    for condition, item in qmsum["task71_by_condition"].items():
        rows.append(
            {
                "dataset": "qmsum_meeting_qa_long",
                "role": "long-context diagnostic behavior",
                "condition": condition,
                "n": item.get("rows"),
                "quality_metric": "lexical/normalized-text proxy only",
                "quality_result": item.get("avg_answer_token_overlap"),
                "avg_e2e_latency_s": item.get("avg_e2e_latency_s"),
                "e2e_tok_per_sec": item.get("e2e_tok_per_sec_weighted"),
                "avg_t_compress_ms": item.get("avg_t_compress_ms"),
                "compression_ratio": item.get("avg_compression_ratio"),
                "interpretation": "Diagnostic only; not semantic correctness proof.",
            }
        )
    return rows


def final_key_points(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": package["status"],
        "final_hypothesis_wording_en": package["cross_dataset_conclusion"]["english"],
        "final_hypothesis_wording_vi": package["cross_dataset_conclusion"]["vietnamese"],
        "gsm8k_key_points": [
            "GSM8K is the stronger quality dataset because numeric extraction is deterministic enough for a proxy.",
            "DFlash-R1 is the fastest GSM8K n=30 condition in this local run.",
            "CC-DFlash-R2 matches LLMLingua-AR-R2 numeric quality and improves e2e latency versus LLMLingua-AR-R2 in n=30.",
            "LLMLingua compression overhead can dominate e2e latency on short-context GSM8K.",
        ],
        "qmsum_key_points": [
            "QMSum is retained as a long-context diagnostic benchmark.",
            "QMSum quality is lexical/normalized-text proxy only, not semantic correctness.",
            "Task 78 did not support broad compressed-evidence deletion as the main explanation in selected audited cases.",
            "QMSum n=100, mnt512, and further suffix tuning are not justified before final packaging.",
        ],
        "next_task": "Task 81 final report v2 drafting / final report structure packaging",
    }


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Task 80 cross-dataset final package artifacts")
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--table-output", type=Path, default=DEFAULT_TABLE_OUTPUT)
    parser.add_argument("--claims-output", type=Path, default=DEFAULT_CLAIMS_OUTPUT)
    parser.add_argument("--key-points-output", type=Path, default=DEFAULT_KEY_POINTS_OUTPUT)
    args = parser.parse_args()

    gsm8k_rows = {condition: load_jsonl(path) for condition, path in GSM8K_ARTIFACTS.items()}
    qmsum_policy_summaries = {
        name: _load_json(path, default={}) for name, path in QMSUM_POLICY_SUMMARIES.items() if path.exists()
    }
    package = build_cross_dataset_package(
        gsm8k_rows_by_condition=gsm8k_rows,
        qmsum_decision=_load_json(QMSUM_DECISION, default={}),
        qmsum_retention_summary=_load_json(QMSUM_RETENTION, default={}),
        qmsum_full_matrix_summary=_load_json(QMSUM_FULL_MATRIX, default={}),
        qmsum_policy_summaries=qmsum_policy_summaries,
    )
    _write_json(args.summary_output, package)
    _write_csv(args.table_output, final_table_rows(package))
    _write_csv(args.claims_output, package["claims_matrix"])
    _write_json(args.key_points_output, final_key_points(package))
    print(
        json.dumps(
            {
                "status": package["status"],
                "summary_output": str(args.summary_output),
                "table_output": str(args.table_output),
                "claims_output": str(args.claims_output),
                "key_points_output": str(args.key_points_output),
                "next_task": final_key_points(package)["next_task"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
