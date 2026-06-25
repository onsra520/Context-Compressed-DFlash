from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task105c_benchmark_scope_claim_closure"
)

DEFAULT_T105A_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task105a_gsm8k_controlled_speed_matrix/summary"
)
DEFAULT_T105B_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task105b_qmsum_controlled_runtime_matrix/summary"
)
DEFAULT_T104_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task104_reference_alignment_for_speed_claim"
)

DEFAULT_T105A_MATRIX = DEFAULT_T105A_DIR / "task105a_matrix_summary.json"
DEFAULT_T105A_CONDITIONS = DEFAULT_T105A_DIR / "task105a_condition_metrics.json"
DEFAULT_T105A_RANKING = DEFAULT_T105A_DIR / "task105a_speed_ranking.json"
DEFAULT_T105B_MATRIX = DEFAULT_T105B_DIR / "task105b_matrix_summary.json"
DEFAULT_T105B_CONDITIONS = DEFAULT_T105B_DIR / "task105b_condition_metrics.json"
DEFAULT_T105B_RANKING = DEFAULT_T105B_DIR / "task105b_runtime_ranking.json"
DEFAULT_QMSUM_CAVEAT = DEFAULT_T104_DIR / "task104_qmsum_caveat_carryforward.json"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["dataset", "claim_area", "status", "allowed", "blocked"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _condition_complete(condition: dict[str, Any]) -> bool:
    return (
        condition.get("row_count_ok") is True
        and condition.get("metadata_ok") is True
        and condition.get("oom_or_cuda_failure") is not True
    )


def _matrix_complete(matrix: dict[str, Any], conditions: dict[str, Any]) -> bool:
    return bool(matrix.get("controlled_matrix_complete", True)) and all(
        isinstance(summary, dict) and _condition_complete(summary) for summary in conditions.values()
    )


def _gt(left: Any, right: Any) -> bool:
    return isinstance(left, (int, float)) and isinstance(right, (int, float)) and left > right


def _lt(left: Any, right: Any) -> bool:
    return isinstance(left, (int, float)) and isinstance(right, (int, float)) and left < right


def _build_gsm8k_claim(
    *,
    matrix: dict[str, Any],
    conditions: dict[str, Any],
    ranking: dict[str, Any],
) -> dict[str, Any]:
    baseline = conditions["Baseline-AR"]
    dflash = conditions["DFlash-R1"]
    optimized = conditions["CC-DFlash-R2 Light GPU"]
    optimized_faster_baseline = _lt(optimized.get("avg_e2e_time_s"), baseline.get("avg_e2e_time_s"))
    optimized_faster_dflash = _lt(optimized.get("avg_e2e_time_s"), dflash.get("avg_e2e_time_s"))
    optimized_quality_at_least_refs = (
        _gt(optimized.get("strict_correct_count"), baseline.get("strict_correct_count"))
        or optimized.get("strict_correct_count") == baseline.get("strict_correct_count")
    ) and (
        _gt(optimized.get("strict_correct_count"), dflash.get("strict_correct_count"))
        or optimized.get("strict_correct_count") == dflash.get("strict_correct_count")
    )
    return {
        "dataset": "gsm8k_short",
        "evidence_task": "T105A",
        "matrix_complete": _matrix_complete(matrix, conditions),
        "n": matrix.get("expected_n", 100),
        "max_new_tokens": 256,
        "optimized_avg_e2e_time_s": optimized.get("avg_e2e_time_s"),
        "baseline_ar_avg_e2e_time_s": baseline.get("avg_e2e_time_s"),
        "dflash_r1_avg_e2e_time_s": dflash.get("avg_e2e_time_s"),
        "optimized_strict_correct": optimized.get("strict_correct_count"),
        "baseline_ar_strict_correct": baseline.get("strict_correct_count"),
        "dflash_r1_strict_correct": dflash.get("strict_correct_count"),
        "optimized_cap_limited": optimized.get("cap_limited_incomplete_count"),
        "optimized_t_compress_ms": optimized.get("avg_t_compress_ms"),
        "optimized_R_actual": optimized.get("avg_R_actual"),
        "optimized_max_vram_reserved_gib": optimized.get("max_vram_reserved_gib"),
        "optimized_faster_than_baseline_ar": optimized_faster_baseline,
        "optimized_faster_than_dflash_r1": optimized_faster_dflash,
        "optimized_quality_proxy_at_least_references": optimized_quality_at_least_refs,
        "ranking": ranking.get("ranked_conditions", []),
        "allowed_status": "bounded_faster_than_baseline_only"
        if optimized_faster_baseline and not optimized_faster_dflash and not optimized_quality_at_least_refs
        else "requires_manual_review",
        "allowed_wording": (
            "In the controlled GSM8K n100 matrix, optimized CC-DFlash-R2 Light GPU was faster than "
            "Baseline-AR on average e2e time but slower than DFlash-R1."
        ),
        "blocked_wording": (
            "Do not claim faster-than-DFlash-R1, all-reference speed win, or quality-preserved "
            "speed win for GSM8K."
        ),
    }


def _build_qmsum_claim(
    *,
    matrix: dict[str, Any],
    conditions: dict[str, Any],
    ranking: dict[str, Any],
    qmsum_caveat: dict[str, Any],
) -> dict[str, Any]:
    baseline = conditions["Baseline-AR"]
    dflash = conditions["DFlash-R1"]
    optimized = conditions["CC-DFlash-R2 Light GPU"]
    empty_count = int(optimized.get("empty_or_malformed_output_count") or 0)
    cap_count = int(optimized.get("cap_limited_or_incomplete_count") or 0)
    return {
        "dataset": "qmsum_meeting_qa_long",
        "evidence_task": "T105B",
        "matrix_complete": _matrix_complete(matrix, conditions),
        "n": matrix.get("expected_n", 30),
        "max_new_tokens": matrix.get("max_new_tokens", 384),
        "optimized_avg_e2e_time_s": optimized.get("avg_e2e_time_s"),
        "baseline_ar_avg_e2e_time_s": baseline.get("avg_e2e_time_s"),
        "dflash_r1_avg_e2e_time_s": dflash.get("avg_e2e_time_s"),
        "optimized_t_compress_ms": optimized.get("avg_t_compress_ms"),
        "optimized_R_actual": optimized.get("avg_R_actual"),
        "optimized_max_vram_reserved_gib": optimized.get("max_vram_reserved_gib"),
        "optimized_empty_or_malformed_count": empty_count,
        "optimized_cap_limited_or_incomplete_count": cap_count,
        "optimized_completed_all_rows": optimized.get("row_count_ok") is True,
        "optimized_faster_than_baseline_ar": _lt(optimized.get("avg_e2e_time_s"), baseline.get("avg_e2e_time_s")),
        "optimized_faster_than_dflash_r1": _lt(optimized.get("avg_e2e_time_s"), dflash.get("avg_e2e_time_s")),
        "ranking": ranking.get("ranked_conditions", []),
        "semantic_correctness_claim": "blocked",
        "semantic_caveat": qmsum_caveat.get("required_wording"),
        "human_review_label_counts": qmsum_caveat.get("human_review_label_counts", {}),
        "allowed_status": "runtime_feasibility_only",
        "allowed_wording": (
            "In the controlled QMSum n30 runtime matrix, optimized CC-DFlash-R2 Light GPU completed "
            "all rows but did not beat Baseline-AR or DFlash-R1 on average e2e time."
        ),
        "blocked_wording": (
            "Do not claim QMSum speed win, semantic correctness, or residual-risk elimination."
        ),
    }


def _supported_claims() -> dict[str, Any]:
    return {
        "claims": [
            "Phase 2 reduced compressor overhead substantially with the light compressor and GPU placement.",
            "In the controlled GSM8K n100 matrix, optimized CC-DFlash-R2 Light GPU was faster than Baseline-AR but slower than DFlash-R1.",
            "In the controlled QMSum n30 runtime matrix, optimized CC-DFlash-R2 Light GPU completed all rows but did not beat Baseline-AR or DFlash-R1 on average e2e time.",
            "QMSum remains runtime/feasibility and residual-risk evidence, not semantic-correctness proof.",
            "Final claims remain benchmark-scoped and condition-scoped.",
        ],
        "scope": "Benchmark-scoped closure using T105A and T105B only.",
    }


def _blocked_claims() -> dict[str, Any]:
    return {
        "claims": [
            "Optimized CC-DFlash wins the full benchmark.",
            "Optimized CC-DFlash is faster than all references.",
            "Optimized CC-DFlash preserves quality while improving speed across datasets.",
            "QMSum semantic correctness is proven.",
            "QMSum residual risk is eliminated.",
            "Universal 8GB deployment readiness is proven.",
            "The optimized Light GPU path should become the default.",
            "DFlash-R1 is broken or invalid.",
        ],
        "scope": "Blocked for final report/demo language unless a future explicit task proves otherwise.",
    }


def _cross_dataset_interpretation(
    *,
    gsm8k: dict[str, Any],
    qmsum: dict[str, Any],
    qmsum_caveat: dict[str, Any],
) -> dict[str, Any]:
    return {
        "phase2_overall_status": "benchmark_scoped_candidate_evidence_only",
        "compressor_overhead_reduction": "supported",
        "local_feasibility": "supported",
        "final_benchmark_wide_speed_win": "blocked",
        "quality_preserved_speed_win": "blocked",
        "default_optimized_switch": "blocked_until_t106",
        "gsm8k_summary": gsm8k["allowed_wording"],
        "qmsum_summary": qmsum["allowed_wording"],
        "qmsum_caveat_required": True,
        "qmsum_human_review_label_counts": qmsum_caveat.get("human_review_label_counts", {}),
    }


def _t106_unblock_requirements() -> dict[str, Any]:
    return {
        "next_task": "T106 — Optimized Default Candidate Decision",
        "recommended_t106_posture": "candidate_only_not_default_winner",
        "must_not_switch_defaults_automatically": True,
        "must_preserve": [
            "GSM8K faster-than-Baseline only",
            "not faster-than-DFlash on GSM8K",
            "not faster-than-any-reference on QMSum",
            "QMSum semantic caveat",
            "no universal 8GB deployment readiness",
        ],
        "likely_options": [
            "Candidate path for specific Baseline-AR comparison",
            "Experimental optimized path",
            "Not default winner",
            "Defer default switch",
        ],
    }


def _table_rows(dataset_claim_matrix: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "dataset": "GSM8K",
            "claim_area": "speed_quality",
            "status": dataset_claim_matrix["GSM8K"]["allowed_status"],
            "allowed": dataset_claim_matrix["GSM8K"]["allowed_wording"],
            "blocked": dataset_claim_matrix["GSM8K"]["blocked_wording"],
        },
        {
            "dataset": "QMSum",
            "claim_area": "runtime_semantic_caveat",
            "status": dataset_claim_matrix["QMSum"]["allowed_status"],
            "allowed": dataset_claim_matrix["QMSum"]["allowed_wording"],
            "blocked": dataset_claim_matrix["QMSum"]["blocked_wording"],
        },
        {
            "dataset": "Cross-dataset",
            "claim_area": "benchmark_scope",
            "status": "candidate_evidence_only",
            "allowed": "Final claims remain benchmark-scoped and condition-scoped.",
            "blocked": "Do not claim full-benchmark win, quality-preserved win, or default switch.",
        },
    ]


def analyze(
    *,
    t105a_matrix: Path = DEFAULT_T105A_MATRIX,
    t105a_conditions: Path = DEFAULT_T105A_CONDITIONS,
    t105a_ranking: Path = DEFAULT_T105A_RANKING,
    t105b_matrix: Path = DEFAULT_T105B_MATRIX,
    t105b_conditions: Path = DEFAULT_T105B_CONDITIONS,
    t105b_ranking: Path = DEFAULT_T105B_RANKING,
    qmsum_caveat: Path = DEFAULT_QMSUM_CAVEAT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    t105a_matrix_payload = _read_json(t105a_matrix)
    t105a_conditions_payload = _read_json(t105a_conditions)
    t105a_ranking_payload = _read_json(t105a_ranking)
    t105b_matrix_payload = _read_json(t105b_matrix)
    t105b_conditions_payload = _read_json(t105b_conditions)
    t105b_ranking_payload = _read_json(t105b_ranking)
    qmsum_caveat_payload = _read_json(qmsum_caveat)

    t105a_complete = _matrix_complete(t105a_matrix_payload, t105a_conditions_payload)
    t105b_complete = _matrix_complete(t105b_matrix_payload, t105b_conditions_payload)
    decision = "PASS_WITH_CAVEAT" if t105a_complete and t105b_complete else "PARTIAL"

    gsm8k = _build_gsm8k_claim(
        matrix=t105a_matrix_payload,
        conditions=t105a_conditions_payload,
        ranking=t105a_ranking_payload,
    )
    qmsum = _build_qmsum_claim(
        matrix=t105b_matrix_payload,
        conditions=t105b_conditions_payload,
        ranking=t105b_ranking_payload,
        qmsum_caveat=qmsum_caveat_payload,
    )
    dataset_claim_matrix = {"GSM8K": gsm8k, "QMSum": qmsum}
    supported_claims = _supported_claims()
    blocked_claims = _blocked_claims()
    cross_dataset = _cross_dataset_interpretation(gsm8k=gsm8k, qmsum=qmsum, qmsum_caveat=qmsum_caveat_payload)
    t106_requirements = _t106_unblock_requirements()
    next_task_decision = {
        "next_task": "T106 — Optimized Default Candidate Decision"
        if decision == "PASS_WITH_CAVEAT"
        else "T105C-R — Benchmark-Scope Claim Closure Repair",
        "reason": "T105A and T105B closure artifacts are complete."
        if decision == "PASS_WITH_CAVEAT"
        else "One or more T105 closure inputs are incomplete or inconsistent.",
        "default_switch_authorized": False,
        "extra_benchmark_authorized": False,
    }
    closure_summary = {
        "task": "T105C",
        "decision": decision,
        "t105a_complete": t105a_complete,
        "t105b_complete": t105b_complete,
        "qmsum_caveat_mandatory": qmsum_caveat_payload.get("mandatory") is True,
        "scope": "Static benchmark-scope claim closure only.",
        "no_benchmark_run": True,
        "no_model_inference": True,
        "no_qmsum_n100": True,
        "no_full_matrix": True,
        "no_default_switch": True,
    }

    summary_dir = output_dir / "summary"
    tables_dir = output_dir / "tables"
    _write_json(summary_dir / "task105c_closure_summary.json", closure_summary)
    _write_json(summary_dir / "task105c_dataset_claim_matrix.json", dataset_claim_matrix)
    _write_json(summary_dir / "task105c_supported_claims.json", supported_claims)
    _write_json(summary_dir / "task105c_blocked_claims.json", blocked_claims)
    _write_json(summary_dir / "task105c_cross_dataset_interpretation.json", cross_dataset)
    _write_json(summary_dir / "task105c_t106_unblock_requirements.json", t106_requirements)
    _write_json(summary_dir / "task105c_next_task_decision.json", next_task_decision)
    _write_csv(tables_dir / "task105c_benchmark_scope_claim_table.csv", _table_rows(dataset_claim_matrix))

    return {
        "decision": decision,
        "closure_summary": closure_summary,
        "dataset_claim_matrix": dataset_claim_matrix,
        "supported_claims": supported_claims,
        "blocked_claims": blocked_claims,
        "cross_dataset_interpretation": cross_dataset,
        "t106_unblock_requirements": t106_requirements,
        "next_task_decision": next_task_decision,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Close T105C benchmark-scope claims from T105A/T105B evidence.")
    parser.add_argument("--t105a-matrix", type=Path, default=DEFAULT_T105A_MATRIX)
    parser.add_argument("--t105a-conditions", type=Path, default=DEFAULT_T105A_CONDITIONS)
    parser.add_argument("--t105a-ranking", type=Path, default=DEFAULT_T105A_RANKING)
    parser.add_argument("--t105b-matrix", type=Path, default=DEFAULT_T105B_MATRIX)
    parser.add_argument("--t105b-conditions", type=Path, default=DEFAULT_T105B_CONDITIONS)
    parser.add_argument("--t105b-ranking", type=Path, default=DEFAULT_T105B_RANKING)
    parser.add_argument("--qmsum-caveat", type=Path, default=DEFAULT_QMSUM_CAVEAT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = analyze(
        t105a_matrix=args.t105a_matrix,
        t105a_conditions=args.t105a_conditions,
        t105a_ranking=args.t105a_ranking,
        t105b_matrix=args.t105b_matrix,
        t105b_conditions=args.t105b_conditions,
        t105b_ranking=args.t105b_ranking,
        qmsum_caveat=args.qmsum_caveat,
        output_dir=args.output_dir,
    )
    print(json.dumps(result["closure_summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
