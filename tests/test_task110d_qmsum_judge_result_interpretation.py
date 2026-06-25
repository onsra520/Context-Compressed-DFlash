from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase_2_system_optimization.analysis import task110d_qmsum_judge_result_interpretation as t110d


def test_t110d_interpretation(tmp_path: Path) -> None:
    t110c_summary_path = tmp_path / "task110c_summary.json"
    out_dir = tmp_path / "out"
    
    t110c_data = {
        "json_parse_audit": {
            "status": "loaded",
            "total_judged": 12,
            "valid_json_count": 12,
            "json_repair_used_count": 0
        },
        "model_load_audit": {
            "status": "loaded"
        },
        "human_calibration_comparison": {
            "alignment_count": 1,
            "total_compared": 6,
            "disagreement_count": 5
        },
        "t105b_vs_t108b_judge_delta": {
            "improved": 2,
            "unchanged": 4,
            "regressed": 0
        }
    }
    
    t110d._write_json(t110c_summary_path, t110c_data)
    
    res = t110d.interpret(t110c_summary_path=t110c_summary_path, output_dir=out_dir)
    
    assert res["decision"] == "PASS"
    assert res["technical_success"] is True
    assert res["human_judge_alignment"]["calibration_status"] == "LOW_ALIGNMENT"
    assert res["human_judge_alignment"]["judge_status"] == "AUXILIARY_EVIDENCE_ONLY"
    assert res["qmsum_semantic_boundary"]["qmsum_final_status"] == "FINAL_LIMITATION_AFTER_REPAIR_AND_JUDGE_ATTEMPT"
    assert res["delta_interpretation"]["judge_improved"] == 2
    
    assert (out_dir / "summary/task110d_interpretation_summary.json").exists()
    assert (out_dir / "tables/task110d_qmsum_interpretation_table.csv").exists()
