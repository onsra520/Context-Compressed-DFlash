from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase_2_system_optimization.analysis import task111_final_phase_2_closure_pack as t111


def test_t111_closure_pack(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    res = t111.generate_closure_pack(output_dir=out_dir)
    
    assert res["phase_2_status"]["phase_2_status"] == "COMPLETE_WITH_CAVEATS"
    assert res["gsm8k_final"]["optimized_gsm8k_candidate"] == "T106B_gsm8k_concise_final_answer_v1"
    assert res["qmsum_final"]["qmsum_semantic_correctness"] == "NOT_CLAIMED"
    assert res["validation_model"]["validation_model_status"] == "LOCAL_JUDGE_PIPELINE_AVAILABLE_BUT_AUXILIARY_ONLY"
    
    assert len(res["supported_claims"]) == 5
    assert len(res["blocked_claims"]) == 8
    
    assert (out_dir / "summary/task111_phase_2_final_status.json").exists()
    assert (out_dir / "tables/task111_phase_2_result_table.csv").exists()
    assert (out_dir / "tables/task111_claim_boundary_table.csv").exists()
