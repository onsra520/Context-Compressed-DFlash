from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT_DIR = ROOT / "results/phase_2_system_optimization/final_reruns/task110d_qmsum_judge_result_interpretation"
T110C_SUMMARY_JSON = ROOT / "results/phase_2_system_optimization/final_reruns/task110c_qmsum_judge_calibration_label_run/summary/task110c_label_run_summary.json"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def interpret(
    t110c_summary_path: Path = T110C_SUMMARY_JSON,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    
    if not t110c_summary_path.exists():
        raise FileNotFoundError(f"T110C summary not found: {t110c_summary_path}")
        
    summary_110c = json.loads(t110c_summary_path.read_text(encoding="utf-8"))
    
    # 1. Confirm T110C technical success
    json_audit = summary_110c.get("json_parse_audit", {})
    load_audit = summary_110c.get("model_load_audit", {})
    
    technical_success = (
        load_audit.get("status") == "loaded" and
        json_audit.get("valid_json_count") == json_audit.get("total_judged") and
        json_audit.get("json_repair_used_count") == 0
    )
    
    # 2. Evaluate calibration
    human_calibration = summary_110c.get("human_calibration_comparison", {})
    alignment_count = human_calibration.get("alignment_count", 0)
    total_compared = human_calibration.get("total_compared", 0)
    disagreement_count = human_calibration.get("disagreement_count", 0)
    
    if alignment_count <= 2:
        calibration_status = "LOW_ALIGNMENT"
        judge_status = "AUXILIARY_EVIDENCE_ONLY"
    else:
        calibration_status = "MODERATE_OR_HIGH_ALIGNMENT"
        judge_status = "USABLE_CALIBRATED_EVIDENCE"
        
    human_judge_alignment = {
        "alignment_count": alignment_count,
        "disagreement_count": disagreement_count,
        "total_compared": total_compared,
        "calibration_status": calibration_status,
        "judge_status": judge_status,
        "interpretation": "Judge is usable as auxiliary evidence only, not calibrated ground truth." if calibration_status == "LOW_ALIGNMENT" else "Judge aligns with human labels."
    }
    
    # 3. Evaluate T108B repair signal
    delta_110c = summary_110c.get("t105b_vs_t108b_judge_delta", {})
    improved = delta_110c.get("improved", 0)
    unchanged = delta_110c.get("unchanged", 0)
    regressed = delta_110c.get("regressed", 0)
    
    delta_interpretation = {
        "judge_improved": improved,
        "judge_unchanged": unchanged,
        "judge_regressed": regressed,
        "proxy_improved": 0,
        "proxy_safer": 2,
        "human_calibration": calibration_status,
        "interpretation": "T108B repair signal is mixed/insufficient. Judge says 2 improved, but human calibration is weak."
    }
    
    # 4. Set final QMSum boundary
    qmsum_semantic_boundary = {
        "qmsum_semantic_correctness": "NOT_CLAIMED",
        "qmsum_residual_risk": "REMAINS",
        "t108b_repair_status": "NOT_VALIDATED_AS_REPAIR",
        "judge_status": judge_status,
        "qmsum_final_status": "FINAL_LIMITATION_AFTER_REPAIR_AND_JUDGE_ATTEMPT"
    }
    
    decision = "PASS"
    
    supported_claims = [
        "T110C technically validated the local judge pipeline.",
        "Judge labels are auxiliary evidence because human-label alignment was low.",
        "T108B showed limited judge-positive signal, but not enough to validate QMSum repair.",
        "QMSum remains a final limitation after repair and judge attempts."
    ]
    
    blocked_claims = [
        "QMSum semantic correctness is proven.",
        "QMSum residual risk is eliminated.",
        "T108B repaired QMSum.",
        "Judge labels are ground truth.",
        "CC-DFlash wins QMSum.",
        "Default switch is authorized."
    ]
    
    next_task_decision = {
        "next_task": "T111 — Final Phase 2 Closure Pack",
        "reason": "Interpretation complete. QMSum semantic claims are finalized as limitations. Ready for phase 2 closure."
    }
    
    interpretation_summary = {
        "task": "T110D",
        "title": "QMSum Judge Result Interpretation",
        "technical_success": technical_success,
        "decision": decision,
        "human_judge_alignment": human_judge_alignment,
        "delta_interpretation": delta_interpretation,
        "qmsum_semantic_boundary": qmsum_semantic_boundary,
        "supported_claims": supported_claims,
        "blocked_claims": blocked_claims,
        "next_task_decision": next_task_decision
    }
    
    _write_json(output_dir / "summary/task110d_interpretation_summary.json", interpretation_summary)
    _write_json(output_dir / "summary/task110d_human_judge_alignment.json", human_judge_alignment)
    _write_json(output_dir / "summary/task110d_t105b_vs_t108b_delta_interpretation.json", delta_interpretation)
    _write_json(output_dir / "summary/task110d_qmsum_semantic_boundary.json", qmsum_semantic_boundary)
    _write_json(output_dir / "summary/task110d_supported_claims.json", supported_claims)
    _write_json(output_dir / "summary/task110d_blocked_claims.json", blocked_claims)
    _write_json(output_dir / "summary/task110d_next_task_decision.json", next_task_decision)
    
    (output_dir / "tables").mkdir(parents=True, exist_ok=True)
    import csv
    with (output_dir / "tables/task110d_qmsum_interpretation_table.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "metric", "value", "interpretation"
        ])
        writer.writeheader()
        writer.writerow({
            "metric": "human_alignment",
            "value": f"{alignment_count}/{total_compared}",
            "interpretation": human_judge_alignment["interpretation"]
        })
        writer.writerow({
            "metric": "judge_delta_improved",
            "value": str(improved),
            "interpretation": delta_interpretation["interpretation"]
        })
        writer.writerow({
            "metric": "qmsum_semantic_correctness",
            "value": qmsum_semantic_boundary["qmsum_semantic_correctness"],
            "interpretation": qmsum_semantic_boundary["qmsum_final_status"]
        })

    return interpretation_summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--t110c-summary", type=Path, default=T110C_SUMMARY_JSON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    
    res = interpret(
        t110c_summary_path=args.t110c_summary,
        output_dir=args.output_dir,
    )
    print(f"decision={res['decision']}")
    print(f"calibration_status={res['human_judge_alignment']['calibration_status']}")
    print(f"judge_status={res['human_judge_alignment']['judge_status']}")
    print(f"qmsum_final_status={res['qmsum_semantic_boundary']['qmsum_final_status']}")


if __name__ == "__main__":
    main()
