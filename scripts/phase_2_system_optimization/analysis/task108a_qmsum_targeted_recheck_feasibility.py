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
    "task108a_qmsum_targeted_recheck_feasibility"
)
DEFAULT_T103D_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task103d_qmsum_deep_fix_closure_decision"
)
DEFAULT_T105B_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task105b_qmsum_controlled_runtime_matrix/summary"
)
DEFAULT_T107B_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task107b_gsm8k_policy_refinement_fix/summary"
)

DEFAULT_T103D_CLOSURE = DEFAULT_T103D_DIR / "task103d_closure_summary.json"
DEFAULT_T103D_HUMAN_REVIEW = DEFAULT_T103D_DIR / "task103d_human_review_summary.json"
DEFAULT_T105B_CONDITION_METRICS = DEFAULT_T105B_DIR / "task105b_condition_metrics.json"
DEFAULT_T105B_OUTPUT_COMPLETENESS = DEFAULT_T105B_DIR / "task105b_output_completeness_summary.json"
DEFAULT_T107B_SUMMARY = DEFAULT_T107B_DIR / "task107b_fix_summary.json"

OUTPUT_RELATIVE_PATHS = (
    "summary/task108a_feasibility_summary.json",
    "summary/task108a_qmsum_status_snapshot.json",
    "summary/task108a_residual_risk_evidence.json",
    "summary/task108a_fix_candidate_matrix.json",
    "summary/task108a_t108b_recommendation.json",
    "summary/task108a_claim_update.json",
    "summary/task108a_next_task_decision.json",
    "tables/task108a_qmsum_fix_feasibility_table.csv",
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = (
        list(rows[0].keys())
        if rows
        else ["candidate", "feasibility", "recommendation", "evidence_basis", "blocked_scope"]
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _get(payload: dict[str, Any], path: tuple[str, ...], default: Any = None) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def _condition(metrics: dict[str, Any], name: str) -> dict[str, Any]:
    value = metrics.get(name, {})
    return value if isinstance(value, dict) else {}


def _count(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


def _qmsum_cc_metrics(condition_metrics: dict[str, Any]) -> dict[str, Any]:
    return _condition(condition_metrics, "CC-DFlash-R2 Light GPU")


def _has_clear_mechanical_target(condition_metrics: dict[str, Any]) -> bool:
    cc = _qmsum_cc_metrics(condition_metrics)
    return (
        _count(cc.get("empty_or_malformed_output_count")) > 0
        or _count(cc.get("cap_limited_or_incomplete_count")) > 0
    )


def build_qmsum_status_snapshot(
    *,
    t103d_closure: dict[str, Any],
    t103d_human_review: dict[str, Any],
    t105b_condition_metrics: dict[str, Any],
    t105b_output_completeness: dict[str, Any],
    t107b_summary: dict[str, Any],
) -> dict[str, Any]:
    conditions = {
        name: {
            "row_count": metrics.get("row_count"),
            "avg_e2e_time_s": metrics.get("avg_e2e_time_s"),
            "avg_t_compress_ms": metrics.get("avg_t_compress_ms"),
            "avg_R_actual": metrics.get("avg_R_actual"),
            "empty_or_malformed_output_count": metrics.get("empty_or_malformed_output_count"),
            "cap_limited_or_incomplete_count": metrics.get("cap_limited_or_incomplete_count"),
            "low_reference_overlap_count": metrics.get("low_reference_overlap_count"),
            "avg_reference_recall": metrics.get("avg_reference_recall"),
            "max_vram_reserved_gib": metrics.get("max_vram_reserved_gib"),
            "row_count_ok": metrics.get("row_count_ok"),
            "metadata_ok": metrics.get("metadata_ok"),
            "oom_or_cuda_failure": metrics.get("oom_or_cuda_failure"),
        }
        for name, metrics in t105b_condition_metrics.items()
        if isinstance(metrics, dict)
    }
    cc = conditions.get("CC-DFlash-R2 Light GPU", {})
    baseline = conditions.get("Baseline-AR", {})
    dflash = conditions.get("DFlash-R1", {})
    return {
        "task": "T108A",
        "qmsum_runtime_matrix": conditions,
        "qmsum_output_shape": {
            "source": "T105B",
            "cc_light_gpu_empty_or_malformed": cc.get("empty_or_malformed_output_count"),
            "cc_light_gpu_cap_limited_or_incomplete": cc.get("cap_limited_or_incomplete_count"),
            "all_conditions_completed_without_cap_or_empty": all(
                _count(item.get("empty_or_malformed_output_count")) == 0
                and _count(item.get("cap_limited_or_incomplete_count")) == 0
                for item in conditions.values()
            ),
            "output_completeness_artifact": t105b_output_completeness,
        },
        "qmsum_runtime_reference_position": {
            "cc_light_gpu_faster_than_baseline_ar": (
                isinstance(cc.get("avg_e2e_time_s"), (int, float))
                and isinstance(baseline.get("avg_e2e_time_s"), (int, float))
                and cc["avg_e2e_time_s"] < baseline["avg_e2e_time_s"]
            ),
            "cc_light_gpu_faster_than_dflash_r1": (
                isinstance(cc.get("avg_e2e_time_s"), (int, float))
                and isinstance(dflash.get("avg_e2e_time_s"), (int, float))
                and cc["avg_e2e_time_s"] < dflash["avg_e2e_time_s"]
            ),
            "interpretation": "No QMSum faster-than-reference claim is supported by T105B.",
        },
        "semantic_residual_risk": {
            "qmsum_deep_fix_status": t103d_closure.get("qmsum_deep_fix_status"),
            "qmsum_semantic_correctness": t103d_closure.get("qmsum_semantic_correctness"),
            "qmsum_quality_risk_eliminated": t103d_closure.get("qmsum_quality_risk_eliminated"),
            "human_review_complete": t103d_human_review.get("review_complete"),
            "human_review_row_count": t103d_human_review.get("row_count"),
            "human_review_label_counts": t103d_closure.get(
                "human_review_label_counts",
                t103d_human_review.get("label_counts", {}),
            ),
        },
        "gsm8k_branch_status": {
            "source": "T107B",
            "best_scoped_gsm8k_candidate": t107b_summary.get("best_scoped_gsm8k_candidate", "T106B"),
            "t107b_adopted": t107b_summary.get("t107b_adopted", False),
            "note": "GSM8K optimization branch does not create a new QMSum fix target.",
        },
    }


def build_residual_risk_evidence(
    *,
    t103d_closure: dict[str, Any],
    t105b_condition_metrics: dict[str, Any],
) -> dict[str, Any]:
    cc = _qmsum_cc_metrics(t105b_condition_metrics)
    label_counts = t103d_closure.get("human_review_label_counts", {})
    return {
        "residual_risk_status": "PERSISTENT_AND_CAVEATED",
        "evidence_items": [
            {
                "risk": "semantic_correctness_not_proven",
                "evidence": "T103D closed the deep-fix branch with persistent residual risk and semantic correctness not claimed.",
                "count_or_metric": t103d_closure.get("qmsum_semantic_correctness", "NOT_CLAIMED"),
            },
            {
                "risk": "human_review_did_not_clear_target_rows",
                "evidence": "Fixed six-row human review found no fully correct/supported target rows.",
                "count_or_metric": label_counts,
            },
            {
                "risk": "low_reference_overlap_is_not_unique_to_compression",
                "evidence": "T105B low-overlap rates were similar across Baseline-AR, DFlash-R1, and CC-DFlash-R2 Light GPU.",
                "count_or_metric": {
                    name: _condition(t105b_condition_metrics, name).get("low_reference_overlap_count")
                    for name in ("Baseline-AR", "DFlash-R1", "CC-DFlash-R2 Light GPU")
                },
            },
            {
                "risk": "no_mechanical_output_shape_target",
                "evidence": "T105B CC-DFlash-R2 Light GPU had 0 empty/malformed and 0 cap-limited/incomplete QMSum rows.",
                "count_or_metric": {
                    "empty_or_malformed": cc.get("empty_or_malformed_output_count"),
                    "cap_limited_or_incomplete": cc.get("cap_limited_or_incomplete_count"),
                },
            },
            {
                "risk": "qmsum_runtime_not_a_speed_win",
                "evidence": "T105B CC-DFlash-R2 Light GPU completed QMSum but did not beat Baseline-AR or DFlash-R1 average e2e time.",
                "count_or_metric": {
                    "cc_light_gpu_avg_e2e_time_s": cc.get("avg_e2e_time_s"),
                    "baseline_ar_avg_e2e_time_s": _condition(t105b_condition_metrics, "Baseline-AR").get(
                        "avg_e2e_time_s"
                    ),
                    "dflash_r1_avg_e2e_time_s": _condition(t105b_condition_metrics, "DFlash-R1").get(
                        "avg_e2e_time_s"
                    ),
                },
            },
        ],
    }


def build_fix_candidate_matrix(*, mechanical_target: bool) -> dict[str, Any]:
    targeted_policy_feasibility = "SCOPED_POSSIBLE" if mechanical_target else "WEAK_OR_NOT_JUSTIFIED"
    targeted_policy_recommendation = "SECONDARY_IF_EXPLICITLY_APPROVED" if mechanical_target else "DO_NOT_RUN_BY_DEFAULT"
    candidates = [
        {
            "candidate": "NO_RERUN_KEEP_CAVEAT",
            "feasibility": "SUPPORTED",
            "recommendation": "PRIMARY",
            "evidence_basis": (
                "Existing T103D/T105B evidence already supports the QMSum boundary: runtime coverage with "
                "persistent residual semantic risk."
            ),
            "allowed_next_step": "Proceed to T109 closure packaging with mandatory QMSum caveat.",
            "blocked_scope": "Does not claim QMSum semantic correctness or residual-risk elimination.",
        },
        {
            "candidate": "SMALL_TARGETED_QMSUM_POLICY_RECHECK",
            "feasibility": targeted_policy_feasibility,
            "recommendation": targeted_policy_recommendation,
            "evidence_basis": (
                "A narrow T108B would only be justified by a clear mechanical failure target; prior QMSum "
                "targeted policy, evidence selection, Baseline-AR mini-check, and human review did not close risk."
            ),
            "allowed_next_step": "Only run with explicit user approval and six-row/target-row bounds.",
            "blocked_scope": "No n100, full matrix, Large CPU, DFlash-R1, LLMLingua-AR-R2, or default switch.",
        },
        {
            "candidate": "REFERENCE_OVERLAP_PROXY_REPAIR_ONLY",
            "feasibility": "STATIC_OPTIONAL_ONLY",
            "recommendation": "NOT_REQUIRED_FOR_CLOSURE",
            "evidence_basis": "Proxy limitations are already documented and do not remove semantic uncertainty.",
            "allowed_next_step": "Can be used for wording refinement only.",
            "blocked_scope": "Cannot convert QMSum to semantic-correctness proof.",
        },
        {
            "candidate": "HUMAN_REVIEW_EXPANSION",
            "feasibility": "RESERVED_EXPLICIT_APPROVAL",
            "recommendation": "OPTIONAL_ONLY",
            "evidence_basis": "Human review exists for the fixed six rows; expanding it is a new review scope.",
            "allowed_next_step": "Only with explicit human-review approval and frozen rubric.",
            "blocked_scope": "No hidden human scoring inside automated analysis.",
        },
        {
            "candidate": "LLM_JUDGE_REVIEW",
            "feasibility": "RESERVED_EXPLICIT_APPROVAL",
            "recommendation": "NOT_DEFAULT",
            "evidence_basis": "LLM judge was explicitly out of scope for the QMSum closure branch.",
            "allowed_next_step": "Only if separately authorized as a judge task.",
            "blocked_scope": "No LLM judge is used in T108A.",
        },
        {
            "candidate": "QUERY_AWARE_COMPRESSION_EXPERIMENT",
            "feasibility": "RESERVED_NOT_DEFAULT",
            "recommendation": "DEFER",
            "evidence_basis": "Query-aware compression is a deeper algorithmic change, not a closure-pack requirement.",
            "allowed_next_step": "Reserve for future research after Phase 2 closure.",
            "blocked_scope": "No query-aware compression tuning or default change.",
        },
        {
            "candidate": "QMSUM_FULL_RERUN_OR_N100",
            "feasibility": "BLOCKED",
            "recommendation": "DO_NOT_RUN",
            "evidence_basis": "T108A is static feasibility only; QMSum full rerun/n100 is outside the current scope.",
            "allowed_next_step": "None in T108A.",
            "blocked_scope": "No QMSum n100, full matrix, or broad rerun authorization.",
        },
    ]
    return {
        "matrix_status": "NO_DEFAULT_T108B" if not mechanical_target else "T108B_ONLY_IF_APPROVED",
        "candidates": candidates,
    }


def build_t108b_recommendation(*, mechanical_target: bool, t103d_closure: dict[str, Any]) -> dict[str, Any]:
    persistent_risk = t103d_closure.get("qmsum_deep_fix_status") == "CLOSED_WITH_PERSISTENT_RESIDUAL_RISK"
    if mechanical_target:
        return {
            "recommended_option": "SCOPED_TARGETED_RECHECK_ONLY",
            "t108b_justified": True,
            "reason": (
                "A mechanical QMSum output-shape issue exists, so a small T108B can be justified only as "
                "a target-row recheck with strict bounds and explicit approval."
            ),
            "allowed_scope": [
                "target rows only",
                "no QMSum n100",
                "no full matrix",
                "no LLM judge",
                "no default switch",
            ],
        }
    return {
        "recommended_option": "NO_RERUN_KEEP_CAVEAT",
        "t108b_justified": False,
        "reason": (
            "No clear cap-limited, empty/malformed, or mechanical QMSum target remains, and the deep-fix "
            f"branch status is {t103d_closure.get('qmsum_deep_fix_status') if persistent_risk else 'not closed as persistent risk'}."
        ),
        "allowed_scope": [
            "Proceed to T109 closure packaging",
            "Keep QMSum runtime/feasibility and residual-risk wording",
            "Do not run another QMSum rerun by default",
        ],
    }


def build_claim_update() -> dict[str, Any]:
    return {
        "qmsum_claim_status": "RUNTIME_FEASIBILITY_WITH_PERSISTENT_RESIDUAL_RISK",
        "allowed_claims": [
            "QMSum remains runtime/feasibility and residual-risk evidence.",
            "T105B supports bounded QMSum output-completion/runtime observations for the controlled n30 matrix.",
            "T103D supports preserving a mandatory QMSum residual-risk caveat after failed deep-fix closure.",
            "T108A supports proceeding to closure packaging without a default QMSum rerun.",
        ],
        "blocked_claims": [
            "QMSum semantic correctness is proven.",
            "QMSum residual risk is eliminated.",
            "CC-DFlash wins QMSum runtime against Baseline-AR or DFlash-R1.",
            "QMSum n100 or full rerun is authorized automatically.",
            "Query-aware compression is ready or default.",
            "A targeted T108B rerun is required by the current evidence.",
            "The optimized Light GPU path is a default/global winner.",
        ],
    }


def analyze(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    t103d_closure: Path = DEFAULT_T103D_CLOSURE,
    t103d_human_review: Path = DEFAULT_T103D_HUMAN_REVIEW,
    t105b_condition_metrics: Path = DEFAULT_T105B_CONDITION_METRICS,
    t105b_output_completeness: Path = DEFAULT_T105B_OUTPUT_COMPLETENESS,
    t107b_summary: Path = DEFAULT_T107B_SUMMARY,
) -> dict[str, Any]:
    t103d = _read_json(t103d_closure)
    human = _read_json(t103d_human_review)
    t105b_metrics = _read_json(t105b_condition_metrics)
    t105b_completeness = _read_json(t105b_output_completeness)
    t107b = _read_json(t107b_summary)

    mechanical_target = _has_clear_mechanical_target(t105b_metrics)
    t108b_recommendation = build_t108b_recommendation(
        mechanical_target=mechanical_target,
        t103d_closure=t103d,
    )
    next_task = (
        "T108B — Optional QMSum Targeted Recheck"
        if t108b_recommendation["t108b_justified"]
        else "T109 — Phase 2 Optimization Closure Pack"
    )
    decision = "PASS_WITH_CAVEAT"
    feasibility_summary = {
        "task": "T108A",
        "title": "QMSum Targeted Recheck / Fix Feasibility",
        "decision": decision,
        "analysis_only": True,
        "no_benchmark": True,
        "no_model_inference": True,
        "no_qmsum_rerun": True,
        "no_llm_judge": True,
        "no_human_scoring": True,
        "mechanical_qmsum_fix_target_found": mechanical_target,
        "t108b_default_recommendation": t108b_recommendation["recommended_option"],
        "t108b_justified": t108b_recommendation["t108b_justified"],
        "next_task": next_task,
        "summary": (
            "T108A finds no justified default QMSum targeted rerun because T105B has no empty/malformed "
            "or cap-limited QMSum rows and T103D already closed the deep-fix branch with persistent residual risk."
            if not mechanical_target
            else "T108A finds a mechanical QMSum target that could justify a strictly scoped T108B only with approval."
        ),
    }
    qmsum_status_snapshot = build_qmsum_status_snapshot(
        t103d_closure=t103d,
        t103d_human_review=human,
        t105b_condition_metrics=t105b_metrics,
        t105b_output_completeness=t105b_completeness,
        t107b_summary=t107b,
    )
    residual_risk_evidence = build_residual_risk_evidence(
        t103d_closure=t103d,
        t105b_condition_metrics=t105b_metrics,
    )
    fix_candidate_matrix = build_fix_candidate_matrix(mechanical_target=mechanical_target)
    claim_update = build_claim_update()
    next_task_decision = {
        "next_task": next_task,
        "reason": t108b_recommendation["reason"],
        "t103b_deferred_or_reserved": True,
        "final_report_integration_deferred": True,
        "qmsum_claim_status": claim_update["qmsum_claim_status"],
    }

    outputs = {
        "feasibility_summary": feasibility_summary,
        "qmsum_status_snapshot": qmsum_status_snapshot,
        "residual_risk_evidence": residual_risk_evidence,
        "fix_candidate_matrix": fix_candidate_matrix,
        "t108b_recommendation": t108b_recommendation,
        "claim_update": claim_update,
        "next_task_decision": next_task_decision,
    }

    _write_json(output_dir / "summary/task108a_feasibility_summary.json", feasibility_summary)
    _write_json(output_dir / "summary/task108a_qmsum_status_snapshot.json", qmsum_status_snapshot)
    _write_json(output_dir / "summary/task108a_residual_risk_evidence.json", residual_risk_evidence)
    _write_json(output_dir / "summary/task108a_fix_candidate_matrix.json", fix_candidate_matrix)
    _write_json(output_dir / "summary/task108a_t108b_recommendation.json", t108b_recommendation)
    _write_json(output_dir / "summary/task108a_claim_update.json", claim_update)
    _write_json(output_dir / "summary/task108a_next_task_decision.json", next_task_decision)
    _write_csv(
        output_dir / "tables/task108a_qmsum_fix_feasibility_table.csv",
        fix_candidate_matrix["candidates"],
    )
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Package T108A QMSum targeted recheck feasibility evidence.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--t103d-closure", type=Path, default=DEFAULT_T103D_CLOSURE)
    parser.add_argument("--t103d-human-review", type=Path, default=DEFAULT_T103D_HUMAN_REVIEW)
    parser.add_argument("--t105b-condition-metrics", type=Path, default=DEFAULT_T105B_CONDITION_METRICS)
    parser.add_argument("--t105b-output-completeness", type=Path, default=DEFAULT_T105B_OUTPUT_COMPLETENESS)
    parser.add_argument("--t107b-summary", type=Path, default=DEFAULT_T107B_SUMMARY)
    args = parser.parse_args()

    result = analyze(
        output_dir=args.output_dir,
        t103d_closure=args.t103d_closure,
        t103d_human_review=args.t103d_human_review,
        t105b_condition_metrics=args.t105b_condition_metrics,
        t105b_output_completeness=args.t105b_output_completeness,
        t107b_summary=args.t107b_summary,
    )
    print(json.dumps(result["feasibility_summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
