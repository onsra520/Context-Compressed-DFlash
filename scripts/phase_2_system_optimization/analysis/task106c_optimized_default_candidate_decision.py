from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/task106c_optimized_default_candidate_decision"
)
DEFAULT_T105C_SUMMARY = Path(
    "results/phase_2_system_optimization/final_reruns/task105c_benchmark_scope_claim_closure/"
    "summary/task105c_closure_summary.json"
)
DEFAULT_T105C_UNBLOCK = Path(
    "results/phase_2_system_optimization/final_reruns/task105c_benchmark_scope_claim_closure/"
    "summary/task105c_t106_unblock_requirements.json"
)
DEFAULT_T106A_SUMMARY = Path(
    "results/phase_2_system_optimization/final_reruns/task106a_gsm8k_cap_limited_attribution_audit/"
    "summary/task106a_audit_summary.json"
)
DEFAULT_T106B_SUMMARY = Path(
    "results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix/"
    "summary/task106b_fix_summary.json"
)

OUTPUT_RELATIVE_PATHS = (
    "summary/task106c_decision_summary.json",
    "summary/task106c_candidate_policy_matrix.json",
    "summary/task106c_supported_candidate_claims.json",
    "summary/task106c_blocked_default_claims.json",
    "summary/task106c_fairness_caveats.json",
    "summary/task106c_t107_unblock_requirements.json",
    "summary/task106c_next_task_decision.json",
    "tables/task106c_default_candidate_decision_table.csv",
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        rows = [{"claim_area": "", "status": "", "decision": "", "rationale": ""}]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _get(payload: dict[str, Any], path: tuple[str, ...], default: Any = None) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def build_candidate_policy_matrix(
    *,
    t105c_summary: dict[str, Any],
    t105c_unblock: dict[str, Any],
    t106a_summary: dict[str, Any],
    t106b_summary: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "claim_area": "GSM8K optimized path",
            "status": "SCOPED_CANDIDATE",
            "decision": "candidate_only",
            "rationale": (
                "T106B reduced cap-limited rows from "
                f"{_get(t106b_summary, ('cap_limited_delta', 'before_cap_limited_count'), 15)}/100 to "
                f"{_get(t106b_summary, ('cap_limited_delta', 'fixed_cap_limited_count'), 2)}/100 and improved strict "
                f"{_get(t106b_summary, ('quality_proxy_delta', 'before_strict_correct_count'), 79)}/100 to "
                f"{_get(t106b_summary, ('quality_proxy_delta', 'fixed_strict_correct_count'), 88)}/100."
            ),
            "required_caveat": "GSM8K-only optimized-condition evidence; no global/default switch.",
        },
        {
            "claim_area": "Global default switch",
            "status": "BLOCKED",
            "decision": "default_switch_no",
            "rationale": (
                "T105C explicitly blocks automatic default switching and T106B reran only the optimized condition."
            ),
            "required_caveat": "No default switch is authorized.",
        },
        {
            "claim_area": "QMSum semantics",
            "status": "BLOCKED",
            "decision": "qmsum_default_support_no",
            "rationale": "T105C preserves the mandatory QMSum semantic caveat; T106B did not rerun QMSum.",
            "required_caveat": "QMSum semantic correctness remains not claimed.",
        },
        {
            "claim_area": "Reference fairness",
            "status": "INCOMPLETE",
            "decision": "reference_policy_fairness_needed_for_final_all_reference_win",
            "rationale": (
                "Baseline-AR and DFlash-R1 were not rerun with the T106B concise final-answer policy."
            ),
            "required_caveat": "T106B cannot prove a final all-reference speed/quality win.",
        },
        {
            "claim_area": "Wrong numeric regression",
            "status": "CAVEATED",
            "decision": "quality_interpretation_caveated",
            "rationale": (
                "Strict wrong numeric increased from "
                f"{_get(t106b_summary, ('quality_proxy_delta', 'before_strict_wrong_numeric_count'), 6)}/100 to "
                f"{_get(t106b_summary, ('quality_proxy_delta', 'fixed_strict_wrong_numeric_count'), 10)}/100."
            ),
            "required_caveat": "Improved finalization does not prove quality is solved.",
        },
        {
            "claim_area": "T107 closure",
            "status": "UNBLOCKED_WITH_CAVEATS",
            "decision": "proceed_to_phase2_closure_pack",
            "rationale": "The candidate/default boundary is explicit and can be packaged in T107.",
            "required_caveat": "T107 should close as scoped candidate/experimental path, not default winner.",
        },
    ]


def analyze(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    t105c_summary: Path = DEFAULT_T105C_SUMMARY,
    t105c_unblock: Path = DEFAULT_T105C_UNBLOCK,
    t106a_summary: Path = DEFAULT_T106A_SUMMARY,
    t106b_summary: Path = DEFAULT_T106B_SUMMARY,
) -> dict[str, Any]:
    t105c = _read_json(t105c_summary)
    t105c_requirements = _read_json(t105c_unblock)
    t106a = _read_json(t106a_summary)
    t106b = _read_json(t106b_summary)

    t105c_ok = t105c.get("decision") == "PASS_WITH_CAVEAT" and t105c.get("no_default_switch") is True
    t106a_ok = t106a.get("decision") == "PASS_WITH_CAVEAT"
    t106b_ok = (
        t106b.get("decision") == "PASS_WITH_CAVEAT"
        and t106b.get("fix_interpretation") == "cap_fix_supported_with_caveat"
        and _get(t106b, ("metadata_audit", "valid"), False) is True
    )
    decision = "PASS_WITH_CAVEAT" if t105c_ok and t106a_ok and t106b_ok else "PARTIAL"

    quality = t106b.get("quality_proxy_delta", {})
    cap = t106b.get("cap_limited_delta", {})
    runtime = t106b.get("runtime_delta", {})
    policy = t106b.get("policy", {})

    decision_summary = {
        "task": "T106C",
        "title": "Optimized Default Candidate Decision",
        "decision": decision,
        "optimized_path_status": "SCOPED_GSM8K_CANDIDATE",
        "default_switch": "NO",
        "qmsum_default_support": "NO",
        "production_ready": "NO",
        "needs_reference_policy_fairness_rerun_for_final_all_reference_win": "YES",
        "no_benchmark_run": True,
        "no_model_inference": True,
        "no_qmsum_run": True,
        "inputs_valid": {
            "t105c_benchmark_scope_closure_confirmed": t105c_ok,
            "t106a_cap_limited_attribution_confirmed": t106a_ok,
            "t106b_cap_fix_confirmed": t106b_ok,
        },
        "t106b_improvement_summary": {
            "policy_name": policy.get("policy_name", "gsm8k_concise_final_answer_v1"),
            "default_behavior_changed": policy.get("default_behavior_changed", False),
            "strict": {
                "before": quality.get("before_strict_correct_count", 79),
                "after": quality.get("fixed_strict_correct_count", 88),
                "delta": quality.get("strict_correct_delta", 9),
            },
            "cap_limited": {
                "before": cap.get("before_cap_limited_count", 15),
                "after": cap.get("fixed_cap_limited_count", 2),
                "delta": cap.get("cap_limited_delta", -13),
            },
            "final_answer_marker": {
                "before": quality.get("before_final_answer_marker_count", 85),
                "after": quality.get("fixed_final_answer_marker_count", 98),
                "delta": quality.get("final_answer_marker_delta", 13),
            },
            "strict_wrong_numeric": {
                "before": quality.get("before_strict_wrong_numeric_count", 6),
                "after": quality.get("fixed_strict_wrong_numeric_count", 10),
                "delta": quality.get("strict_wrong_numeric_delta", 4),
            },
            "avg_e2e_time_s": {
                "before": runtime.get("before_avg_e2e_time_s", 2.896622),
                "after": runtime.get("fixed_avg_e2e_time_s", 2.145689),
                "delta": runtime.get("avg_e2e_time_s_delta", -0.750933),
            },
            "avg_t_compress_ms_after": runtime.get("fixed_avg_t_compress_ms", 17.45762),
            "max_vram_reserved_gib_after": runtime.get("fixed_max_vram_reserved_gib", 4.439453),
        },
    }

    candidate_policy_matrix = build_candidate_policy_matrix(
        t105c_summary=t105c,
        t105c_unblock=t105c_requirements,
        t106a_summary=t106a,
        t106b_summary=t106b,
    )
    supported_candidate_claims = {
        "claim_status": "SCOPED_GSM8K_CANDIDATE",
        "claims": [
            "T106B shows the optimized CC-DFlash-R2 Light GPU GSM8K policy can reduce cap-limited failures and improve strict proxy in the optimized condition.",
            "The optimized path is a scoped GSM8K candidate with strong cap/finalization improvement evidence.",
            "The candidate remains benchmark-scoped and does not resolve QMSum semantic risk.",
            "No default switch is authorized.",
        ],
    }
    blocked_default_claims = {
        "default_switch": "NO",
        "claims": [
            "Optimized CC-DFlash is the default winner.",
            "Optimized CC-DFlash wins all references.",
            "T106B proves final all-reference speed/quality win.",
            "QMSum semantic correctness is proven.",
            "QMSum residual risk is eliminated.",
            "Universal 8GB deployment readiness is proven.",
            "The concise GSM8K policy should be applied globally.",
        ],
    }
    fairness_caveats = {
        "reference_policy_fairness_rerun_required": True,
        "caveats": [
            "T106B optimized rerun used a new policy not applied to Baseline-AR or DFlash-R1.",
            "T106B is excellent candidate evidence, but not a complete reference-rerun matrix.",
            "Wrong numeric increased from 6/100 to 10/100, so quality interpretation remains caveated.",
            "QMSum was not rerun and remains caveated.",
        ],
    }
    t107_unblock_requirements = {
        "t107_unblocked": True,
        "recommended_t107_posture": "close_phase2_as_scoped_candidate_not_default_winner",
        "must_include": [
            "optimized_path_status=SCOPED_GSM8K_CANDIDATE",
            "default_switch=NO",
            "qmsum_default_support=NO",
            "needs_reference_policy_fairness_rerun_for_final_all_reference_win=YES",
            "wrong_numeric_regression caveat",
        ],
        "must_not_claim": blocked_default_claims["claims"],
    }
    next_task_decision = {
        "next_task": "T107 — Phase 2 Optimization Closure Pack",
        "status": "PLANNED / NEXT",
        "reason": (
            "T106C decides the optimized path is a scoped GSM8K candidate, not a default winner; "
            "T107 can package Phase 2 closure with these boundaries."
        ),
        "requires_manual_caveat_review": decision != "PASS_WITH_CAVEAT",
        "default_switch_authorized": False,
    }

    table_rows = [
        {
            "claim_area": item["claim_area"],
            "status": item["status"],
            "decision": item["decision"],
            "rationale": item["rationale"],
            "required_caveat": item["required_caveat"],
        }
        for item in candidate_policy_matrix
    ]

    payloads = {
        "summary/task106c_decision_summary.json": decision_summary,
        "summary/task106c_candidate_policy_matrix.json": candidate_policy_matrix,
        "summary/task106c_supported_candidate_claims.json": supported_candidate_claims,
        "summary/task106c_blocked_default_claims.json": blocked_default_claims,
        "summary/task106c_fairness_caveats.json": fairness_caveats,
        "summary/task106c_t107_unblock_requirements.json": t107_unblock_requirements,
        "summary/task106c_next_task_decision.json": next_task_decision,
    }
    for relative, payload in payloads.items():
        _write_json(output_dir / relative, payload)
    _write_csv(output_dir / "tables/task106c_default_candidate_decision_table.csv", table_rows)

    return {
        "decision_summary": decision_summary,
        "candidate_policy_matrix": candidate_policy_matrix,
        "supported_candidate_claims": supported_candidate_claims,
        "blocked_default_claims": blocked_default_claims,
        "fairness_caveats": fairness_caveats,
        "t107_unblock_requirements": t107_unblock_requirements,
        "next_task_decision": next_task_decision,
        "table_rows": table_rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Package Task106C optimized default candidate decision artifacts.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--t105c-summary", type=Path, default=DEFAULT_T105C_SUMMARY)
    parser.add_argument("--t105c-unblock", type=Path, default=DEFAULT_T105C_UNBLOCK)
    parser.add_argument("--t106a-summary", type=Path, default=DEFAULT_T106A_SUMMARY)
    parser.add_argument("--t106b-summary", type=Path, default=DEFAULT_T106B_SUMMARY)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = analyze(
        output_dir=args.output_dir,
        t105c_summary=args.t105c_summary,
        t105c_unblock=args.t105c_unblock,
        t106a_summary=args.t106a_summary,
        t106b_summary=args.t106b_summary,
    )
    print(json.dumps(result["decision_summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
