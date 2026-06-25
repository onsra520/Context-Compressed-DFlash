from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task105c_benchmark_scope_claim_closure as t105c


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_inputs(tmp_path: Path) -> dict[str, Path]:
    base = tmp_path / "inputs"
    t105a_matrix = base / "task105a_matrix_summary.json"
    t105a_conditions = base / "task105a_condition_metrics.json"
    t105a_ranking = base / "task105a_speed_ranking.json"
    t105b_matrix = base / "task105b_matrix_summary.json"
    t105b_conditions = base / "task105b_condition_metrics.json"
    t105b_ranking = base / "task105b_runtime_ranking.json"
    qmsum_caveat = base / "task104_qmsum_caveat_carryforward.json"

    _write_json(
        t105a_matrix,
        {
            "decision": "PASS_WITH_CAVEAT",
            "controlled_matrix_complete": True,
            "expected_n": 100,
            "dataset": "gsm8k_short",
        },
    )
    _write_json(
        t105a_conditions,
        {
            "Baseline-AR": {
                "row_count": 100,
                "row_count_ok": True,
                "metadata_ok": True,
                "strict_correct_count": 85,
                "avg_e2e_time_s": 4.641074,
            },
            "DFlash-R1": {
                "row_count": 100,
                "row_count_ok": True,
                "metadata_ok": True,
                "strict_correct_count": 84,
                "avg_e2e_time_s": 2.650564,
            },
            "CC-DFlash-R2 Light GPU": {
                "row_count": 100,
                "row_count_ok": True,
                "metadata_ok": True,
                "strict_correct_count": 79,
                "cap_limited_incomplete_count": 15,
                "avg_e2e_time_s": 2.896622,
                "avg_t_compress_ms": 17.249677,
                "avg_R_actual": 2.0,
                "max_vram_reserved_gib": 4.431641,
            },
        },
    )
    _write_json(
        t105a_ranking,
        {
            "ranked_conditions": [
                {"condition": "DFlash-R1", "avg_e2e_time_s": 2.650564},
                {"condition": "CC-DFlash-R2 Light GPU", "avg_e2e_time_s": 2.896622},
                {"condition": "Baseline-AR", "avg_e2e_time_s": 4.641074},
            ]
        },
    )
    _write_json(
        t105b_matrix,
        {
            "decision": "PASS_WITH_CAVEAT",
            "controlled_matrix_complete": True,
            "expected_n": 30,
            "dataset": "qmsum_meeting_qa_long",
        },
    )
    _write_json(
        t105b_conditions,
        {
            "Baseline-AR": {
                "row_count": 30,
                "row_count_ok": True,
                "metadata_ok": True,
                "avg_e2e_time_s": 3.770054,
                "empty_or_malformed_output_count": 0,
                "cap_limited_or_incomplete_count": 0,
            },
            "DFlash-R1": {
                "row_count": 30,
                "row_count_ok": True,
                "metadata_ok": True,
                "avg_e2e_time_s": 5.188113,
                "empty_or_malformed_output_count": 0,
                "cap_limited_or_incomplete_count": 0,
            },
            "CC-DFlash-R2 Light GPU": {
                "row_count": 30,
                "row_count_ok": True,
                "metadata_ok": True,
                "avg_e2e_time_s": 5.23531,
                "avg_t_compress_ms": 129.03806,
                "avg_R_actual": 2.192619,
                "max_vram_reserved_gib": 5.414062,
                "empty_or_malformed_output_count": 0,
                "cap_limited_or_incomplete_count": 0,
            },
        },
    )
    _write_json(
        t105b_ranking,
        {
            "optimized_vs_baseline_ar": {"optimized_is_faster": False},
            "optimized_vs_dflash_r1": {"optimized_is_faster": False},
        },
    )
    _write_json(
        qmsum_caveat,
        {
            "mandatory": True,
            "qmsum_deep_fix_status": "CLOSED_WITH_PERSISTENT_RESIDUAL_RISK",
            "qmsum_semantic_correctness": "NOT_CLAIMED",
            "qmsum_quality_risk_eliminated": "NO",
            "human_review_label_counts": {
                "correct_supported": 0,
                "partially_correct_or_incomplete": 2,
                "unsupported_or_wrong": 1,
                "cannot_determine_from_available_context": 3,
            },
            "required_wording": "QMSum runtime feasibility is measured, but QMSum semantic correctness is not claimed.",
        },
    )
    return {
        "t105a_matrix": t105a_matrix,
        "t105a_conditions": t105a_conditions,
        "t105a_ranking": t105a_ranking,
        "t105b_matrix": t105b_matrix,
        "t105b_conditions": t105b_conditions,
        "t105b_ranking": t105b_ranking,
        "qmsum_caveat": qmsum_caveat,
    }


def test_closure_writes_required_artifacts_and_decides_pass_with_caveat(tmp_path: Path) -> None:
    paths = _fixture_inputs(tmp_path)

    result = t105c.analyze(output_dir=tmp_path / "out", **paths)

    assert result["decision"] == "PASS_WITH_CAVEAT"
    assert result["closure_summary"]["t105a_complete"] is True
    assert result["closure_summary"]["t105b_complete"] is True
    assert result["dataset_claim_matrix"]["GSM8K"]["allowed_status"] == "bounded_faster_than_baseline_only"
    assert result["dataset_claim_matrix"]["QMSum"]["allowed_status"] == "runtime_feasibility_only"
    assert result["next_task_decision"]["next_task"].startswith("T106")
    for relpath in [
        "summary/task105c_closure_summary.json",
        "summary/task105c_dataset_claim_matrix.json",
        "summary/task105c_supported_claims.json",
        "summary/task105c_blocked_claims.json",
        "summary/task105c_cross_dataset_interpretation.json",
        "summary/task105c_t106_unblock_requirements.json",
        "summary/task105c_next_task_decision.json",
        "tables/task105c_benchmark_scope_claim_table.csv",
    ]:
        assert (tmp_path / "out" / relpath).exists()


def test_gsm8k_closure_blocks_all_reference_and_quality_preserved_win(tmp_path: Path) -> None:
    paths = _fixture_inputs(tmp_path)

    result = t105c.analyze(output_dir=tmp_path / "out", **paths)
    gsm8k = result["dataset_claim_matrix"]["GSM8K"]

    assert gsm8k["optimized_faster_than_baseline_ar"] is True
    assert gsm8k["optimized_faster_than_dflash_r1"] is False
    assert gsm8k["optimized_quality_proxy_at_least_references"] is False
    blocked = result["blocked_claims"]["claims"]
    assert "Optimized CC-DFlash is faster than all references." in blocked
    assert "Optimized CC-DFlash preserves quality while improving speed across datasets." in blocked


def test_qmsum_closure_preserves_semantic_caveat_and_blocks_speed_win(tmp_path: Path) -> None:
    paths = _fixture_inputs(tmp_path)

    result = t105c.analyze(output_dir=tmp_path / "out", **paths)
    qmsum = result["dataset_claim_matrix"]["QMSum"]

    assert qmsum["optimized_completed_all_rows"] is True
    assert qmsum["optimized_empty_or_malformed_count"] == 0
    assert qmsum["optimized_cap_limited_or_incomplete_count"] == 0
    assert qmsum["optimized_faster_than_baseline_ar"] is False
    assert qmsum["optimized_faster_than_dflash_r1"] is False
    assert qmsum["semantic_correctness_claim"] == "blocked"
    assert result["cross_dataset_interpretation"]["qmsum_human_review_label_counts"]["correct_supported"] == 0


def test_t106_requirements_keep_candidate_not_default_language(tmp_path: Path) -> None:
    paths = _fixture_inputs(tmp_path)

    result = t105c.analyze(output_dir=tmp_path / "out", **paths)
    requirements = result["t106_unblock_requirements"]

    assert requirements["recommended_t106_posture"] == "candidate_only_not_default_winner"
    assert requirements["must_not_switch_defaults_automatically"] is True
    assert "not faster-than-DFlash on GSM8K" in requirements["must_preserve"]
    assert "not faster-than-any-reference on QMSum" in requirements["must_preserve"]


def test_incomplete_input_blocks_pass_and_routes_to_repair(tmp_path: Path) -> None:
    paths = _fixture_inputs(tmp_path)
    t105b_matrix = json.loads(paths["t105b_matrix"].read_text(encoding="utf-8"))
    t105b_matrix["controlled_matrix_complete"] = False
    _write_json(paths["t105b_matrix"], t105b_matrix)

    result = t105c.analyze(output_dir=tmp_path / "out", **paths)

    assert result["decision"] == "PARTIAL"
    assert result["next_task_decision"]["next_task"].startswith("T105C-R")


def test_analyzer_module_does_not_import_model_stacks() -> None:
    source = inspect.getsource(t105c)
    assert "import torch" not in source
    assert "transformers" not in source
