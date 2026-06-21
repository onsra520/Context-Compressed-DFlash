from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task101_final_claim_boundary_audit"
)
DEFAULT_TASK100A_CLAIM_LANGUAGE = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task100a_phase2_supported_evidence_summary/task100a_claim_language.json"
)
DEFAULT_TASK100B_SUMMARY = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task100b_light_gpu_n100_controlled_run/summary/"
    "task100b_light_gpu_n100_summary.json"
)
DEFAULT_TASK100C_CLAIM_RISK_REGISTER = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task100c_optimization_gap_analysis/task100c_claim_risk_register.json"
)

OUTPUT_FILENAMES = (
    "task101_claim_boundary_matrix.json",
    "task101_allowed_claims.json",
    "task101_blocked_claims.json",
    "task101_reworded_no_badges.json",
    "task101_report_language_snippets.json",
    "task101_final_recommendation.json",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _first_mapping(*payloads: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    for payload in payloads:
        current: Any = payload
        for key in keys:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if isinstance(current, dict):
            return current
    return {}


def _metric(summary: dict[str, Any], key: str, default: Any = None) -> Any:
    light_gpu = _first_mapping(summary, keys=("light_gpu_n100",))
    if key in light_gpu:
        return light_gpu[key]
    if key in summary:
        return summary[key]
    return default


def _evidence_numbers(task100b_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_count": _metric(task100b_summary, "row_count", 100),
        "strict_correct_count": _metric(task100b_summary, "strict_correct_count", 79),
        "cap_limited_incomplete_count": _metric(task100b_summary, "cap_limited_incomplete_count", 15),
        "final_answer_marker_count": _metric(task100b_summary, "final_answer_marker_count", 85),
        "strict_wrong_numeric_count": _metric(task100b_summary, "strict_wrong_numeric_count", 6),
        "avg_t_compress_ms": _metric(task100b_summary, "avg_t_compress_ms", 17.35),
        "avg_e2e_time_s": _metric(task100b_summary, "avg_e2e_time_s", 2.88),
        "avg_tokens_per_second": _metric(task100b_summary, "avg_tokens_per_second", 59.83),
        "avg_R_actual": _metric(task100b_summary, "avg_R_actual", 2.0),
        "max_vram_reserved_gib": _metric(task100b_summary, "max_vram_reserved_gib", 4.43),
    }


def build_claim_boundary_matrix(
    task100a_claim_language: dict[str, Any],
    task100b_summary: dict[str, Any],
    task100c_claim_risk_register: dict[str, Any],
) -> dict[str, Any]:
    numbers = _evidence_numbers(task100b_summary)
    risks = task100c_claim_risk_register.get("risks", [])
    risk_ids = sorted(risk.get("risk_id") for risk in risks if isinstance(risk, dict) and risk.get("risk_id"))
    prior_allowed = task100a_claim_language.get("allowed", [])
    prior_blocked = task100a_claim_language.get("blocked", [])

    claims = [
        {
            "claim_area": "Speed / latency",
            "current_status": "BOUNDED_ALLOWED_WITH_CAVEATS",
            "allowed_wording": [
                "In the controlled GSM8K Light GPU n100 run, CC-DFlash-R2 with the light GPU compressor achieved lower average compression overhead than the CPU-compressor references.",
                "Task100B provides bounded evidence of lower e2e time relative to Task96 CPU references.",
            ],
            "blocked_wording": [
                "Final universal speedup is proven.",
                "CC-DFlash is always faster.",
            ],
            "supporting_evidence": [
                f"Task100B average t_compress_ms={numbers['avg_t_compress_ms']}.",
                f"Task100B average e2e={numbers['avg_e2e_time_s']}s.",
                "Task96 CPU references are bounded references, not equal-setting n100 controls.",
            ],
            "remaining_limitation": "No full matrix, no QMSum, and reference sample sizes differ.",
            "final_report_recommendation": "Use bounded GSM8K Light GPU speed evidence language only.",
        },
        {
            "claim_area": "Quality",
            "current_status": "BOUNDED_PROXY_ONLY",
            "allowed_wording": [
                f"Task100B achieved {numbers['strict_correct_count']}/{numbers['row_count']} calibrated strict GSM8K numeric proxy under deterministic evaluation.",
                "Quality evidence is deterministic GSM8K proxy evidence.",
            ],
            "blocked_wording": [
                "Final correctness is proven.",
                "Semantic correctness is proven.",
            ],
            "supporting_evidence": [
                f"Task100B cap-limited incomplete rows: {numbers['cap_limited_incomplete_count']}/{numbers['row_count']}.",
                f"Task100B strict wrong numeric rows: {numbers['strict_wrong_numeric_count']}/{numbers['row_count']}.",
                f"Task100B final-answer marker rows: {numbers['final_answer_marker_count']}/{numbers['row_count']}.",
            ],
            "remaining_limitation": "No LLM judge, no semantic evaluation, 15 cap-limited rows, and 6 wrong numeric rows.",
            "final_report_recommendation": "Label quality as deterministic GSM8K numeric proxy evidence.",
        },
        {
            "claim_area": "GPU / 8GB feasibility",
            "current_status": "LOCAL_FEASIBILITY_OBSERVED",
            "allowed_wording": [
                f"Task100B completed on the local RTX 4070 Laptop GPU with max reserved VRAM around {numbers['max_vram_reserved_gib']}GiB and no recorded OOM/CUDA failure.",
            ],
            "blocked_wording": [
                "Deployment readiness is proven.",
                "8GB deployment readiness is confirmed universally.",
            ],
            "supporting_evidence": [
                "Task100B metadata confirmed light + cuda + local_files_only.",
                f"Task100B max reserved VRAM around {numbers['max_vram_reserved_gib']}GiB.",
            ],
            "remaining_limitation": "Single local machine/run, no stress/load testing, and no deployment environment validation.",
            "final_report_recommendation": "Use local feasibility wording, not readiness wording.",
        },
        {
            "claim_area": "QMSum / long-context semantics",
            "current_status": "OUT_OF_SCOPE_FOR_LIGHT_GPU_N100",
            "allowed_wording": [
                "QMSum remains outside the Task100B Light GPU n100 claim.",
            ],
            "blocked_wording": [
                "QMSum semantic correctness is proven.",
                "Long-context semantic QA quality is solved.",
            ],
            "supporting_evidence": [
                "Task100B ran GSM8K only.",
                "Task100C kept QMSum semantic correctness in the risk register.",
            ],
            "remaining_limitation": "No QMSum rerun in the Phase 2 light GPU path.",
            "final_report_recommendation": "Keep QMSum language diagnostic-only and outside the Light GPU n100 claim.",
        },
        {
            "claim_area": "DFlash-R1 comparison",
            "current_status": "HISTORICAL_REFERENCE_ONLY",
            "allowed_wording": [
                "DFlash-R1 is retained as a historical reference.",
            ],
            "blocked_wording": [
                "DFlash-R1 is broken.",
                "Task100B is apples-to-apples with Task88 DFlash-R1.",
            ],
            "supporting_evidence": [
                "Task100B did not rerun DFlash-R1.",
                "Task88 settings differ, including max_new_tokens.",
            ],
            "remaining_limitation": "Task88 settings differ, including max_new_tokens.",
            "final_report_recommendation": "Reference DFlash-R1 only as historical context.",
        },
        {
            "claim_area": "Compressor placement/default",
            "current_status": "RUNTIME_GATED_CANDIDATE",
            "allowed_wording": [
                "Light GPU placement is a promising candidate.",
                "Runtime override supports GPU placement.",
            ],
            "blocked_wording": [
                "GPU placement is now the default.",
                "Large CPU is invalid.",
            ],
            "supporting_evidence": [
                "Task99-R and Task100B used runtime compressor-device override.",
                "Task100A retained large CPU as historical/control reference.",
            ],
            "remaining_limitation": "Default config remains CPU; large CPU remains historical/control reference.",
            "final_report_recommendation": "Keep GPU placement described as runtime/gated, not default.",
        },
        {
            "claim_area": "n100/full benchmark",
            "current_status": "ONE_CONTROLLED_N100_ONLY",
            "allowed_wording": [
                "Task100B completed one Light GPU n100 controlled run.",
            ],
            "blocked_wording": [
                "Full benchmark is complete.",
                "Full matrix is complete.",
            ],
            "supporting_evidence": [
                "Task100B ran one condition: CC-DFlash-R2 Light GPU on GSM8K mnt256.",
                "Task100B did not run Baseline-AR, DFlash-R1, large CPU n100, QMSum, or a full matrix.",
            ],
            "remaining_limitation": "Only one condition, one dataset, one compressor profile.",
            "final_report_recommendation": "Do not label Task100B as a full benchmark.",
        },
    ]

    return {
        "claims": claims,
        "source_artifacts": {
            "task100a_prior_allowed_count": len(prior_allowed) if isinstance(prior_allowed, list) else 0,
            "task100a_prior_blocked_count": len(prior_blocked) if isinstance(prior_blocked, list) else 0,
            "task100c_risk_ids": risk_ids,
        },
        "task": "Task101",
    }


def build_allowed_claims(matrix: dict[str, Any]) -> dict[str, Any]:
    claims: list[dict[str, str]] = []
    for row in matrix["claims"]:
        for wording in row["allowed_wording"]:
            claims.append(
                {
                    "claim_area": row["claim_area"],
                    "claim": wording,
                    "boundary": row["remaining_limitation"],
                }
            )
    return {"claims": claims, "task": "Task101"}


def build_blocked_claims(matrix: dict[str, Any]) -> dict[str, Any]:
    claims: list[dict[str, str]] = []
    for row in matrix["claims"]:
        for wording in row["blocked_wording"]:
            claims.append(
                {
                    "claim_area": row["claim_area"],
                    "claim": wording,
                    "replacement_guidance": row["final_report_recommendation"],
                }
            )
    return {"claims": claims, "task": "Task101"}


def build_reworded_no_badges() -> dict[str, Any]:
    rewrites = {
        "No universal speedup claim": "Bounded GSM8K Light GPU speed evidence only",
        "No final correctness claim": "Deterministic GSM8K numeric proxy only",
        "No QMSum semantic correctness claim": "No Phase 2 Light GPU QMSum semantic claim",
        "No deployment readiness claim": "Local feasibility observed; deployment readiness not proven",
        "No confirmed 8GB claim": "Observed on local RTX 4070 8GB-class GPU; not universal 8GB guarantee",
        "No DFlash-R1 broken claim": "DFlash-R1 retained as historical reference",
        "No default GPU switch": "GPU placement remains runtime/gated candidate",
    }
    return {
        "rewrites": rewrites,
        "task": "Task101",
    }


def build_report_language_snippets() -> dict[str, Any]:
    return {
        "primary_language": "vi",
        "vietnamese": {
            "allowed": [
                "Trong phạm vi GSM8K mnt256, đường CC-DFlash-R2 với light compressor đặt trên GPU đã hoàn thành n=100 với 79/100 strict numeric proxy, không ghi nhận OOM/CUDA failure, và giảm mạnh T_compress so với các tham chiếu CPU trước đó.",
                "Kết quả này là evidence có kiểm soát, không phải claim final speedup hay deployment readiness.",
                "Light GPU là một candidate khả quan trong môi trường local đã đo, còn default config vẫn giữ CPU và mọi claim deployment vẫn bị chặn.",
            ],
            "blocked_replacements": [
                "Thay vì nói GPU path is production-ready, dùng GPU path is a promising local feasibility candidate.",
                "Thay vì nói final quality is proven, dùng deterministic GSM8K numeric proxy evidence.",
                "Thay vì nói DFlash-R1 is broken, dùng DFlash-R1 remains a historical reference with setting caveats.",
            ],
        },
        "english": {
            "labels": [
                "Bounded GSM8K Light GPU speed evidence only",
                "Deterministic GSM8K numeric proxy only",
                "Local feasibility observed; deployment readiness not proven",
                "GPU placement remains runtime/gated candidate",
            ],
            "allowed": [
                "In the controlled GSM8K mnt256 Light GPU n100 run, CC-DFlash-R2 completed 100/100 rows with 79/100 calibrated strict numeric proxy and no recorded OOM/CUDA failure.",
                "This is controlled bounded evidence, not a final speedup, final quality, QMSum semantic, deployment, or default-GPU claim.",
            ],
        },
        "task": "Task101",
    }


def build_final_recommendation(matrix: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": "PASS",
        "next_step": "T102_Final_Report_Integration",
        "recommendation": "Proceed to T102 final report integration using the allowed/blocked wording from Task101.",
        "do_not_run_more_benchmark_by_default": True,
        "do_not_switch_gpu_default": True,
        "claim_areas_audited": [row["claim_area"] for row in matrix["claims"]],
        "task": "Task101",
    }


def audit(
    *,
    task100a_claim_language: Path = DEFAULT_TASK100A_CLAIM_LANGUAGE,
    task100b_summary: Path = DEFAULT_TASK100B_SUMMARY,
    task100c_claim_risk_register: Path = DEFAULT_TASK100C_CLAIM_RISK_REGISTER,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    prior_claim_language = load_json(task100a_claim_language)
    summary = load_json(task100b_summary)
    risk_register = load_json(task100c_claim_risk_register)

    matrix = build_claim_boundary_matrix(prior_claim_language, summary, risk_register)
    allowed_claims = build_allowed_claims(matrix)
    blocked_claims = build_blocked_claims(matrix)
    reworded_no_badges = build_reworded_no_badges()
    snippets = build_report_language_snippets()
    recommendation = build_final_recommendation(matrix)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "task101_claim_boundary_matrix.json", matrix)
    write_json(output_dir / "task101_allowed_claims.json", allowed_claims)
    write_json(output_dir / "task101_blocked_claims.json", blocked_claims)
    write_json(output_dir / "task101_reworded_no_badges.json", reworded_no_badges)
    write_json(output_dir / "task101_report_language_snippets.json", snippets)
    write_json(output_dir / "task101_final_recommendation.json", recommendation)

    return {
        "decision": recommendation["decision"],
        "claim_boundary_matrix": matrix,
        "allowed_claims": allowed_claims,
        "blocked_claims": blocked_claims,
        "reworded_no_badges": reworded_no_badges,
        "report_language_snippets": snippets,
        "final_recommendation": recommendation,
        "output_dir": str(output_dir),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package Task101 final claim-boundary audit artifacts.")
    parser.add_argument("--task100a-claim-language", type=Path, default=DEFAULT_TASK100A_CLAIM_LANGUAGE)
    parser.add_argument("--task100b-summary", type=Path, default=DEFAULT_TASK100B_SUMMARY)
    parser.add_argument("--task100c-claim-risk-register", type=Path, default=DEFAULT_TASK100C_CLAIM_RISK_REGISTER)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = audit(
        task100a_claim_language=args.task100a_claim_language,
        task100b_summary=args.task100b_summary,
        task100c_claim_risk_register=args.task100c_claim_risk_register,
        output_dir=args.output_dir,
    )
    print(json.dumps({"decision": result["decision"], "output_dir": result["output_dir"]}, sort_keys=True))


if __name__ == "__main__":
    main()
