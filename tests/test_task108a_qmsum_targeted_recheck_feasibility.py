from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task108a_qmsum_targeted_recheck_feasibility as t108a


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _minimal_inputs(root: Path) -> dict[str, Path]:
    t103d = root / "task103d"
    t105b = root / "task105b" / "summary"
    t107b = root / "task107b" / "summary"
    _write_json(
        t103d / "task103d_closure_summary.json",
        {
            "decision": "PASS_WITH_CAVEAT",
            "qmsum_deep_fix_status": "CLOSED_WITH_PERSISTENT_RESIDUAL_RISK",
            "qmsum_semantic_correctness": "NOT_CLAIMED",
            "qmsum_quality_risk_eliminated": "NO",
            "t103b_default_next": "NO",
            "t104_allowed": "YES_WITH_MANDATORY_QMSUM_CAVEAT",
            "human_review_label_counts": {
                "correct_supported": 0,
                "partially_correct_or_incomplete": 2,
                "unsupported_or_wrong": 1,
                "cannot_determine_from_available_context": 3,
            },
        },
    )
    _write_json(
        t103d / "task103d_human_review_summary.json",
        {
            "review_complete": True,
            "row_count": 6,
            "status": "HUMAN_REVIEW_EXECUTED",
            "validated_labels_path": "task103cr_validated_human_labels.jsonl",
            "label_counts": {
                "correct_supported": 0,
                "partially_correct_or_incomplete": 2,
                "unsupported_or_wrong": 1,
                "cannot_determine_from_available_context": 3,
            },
        },
    )
    _write_json(
        t105b / "task105b_condition_metrics.json",
        {
            "Baseline-AR": {
                "row_count": 30,
                "avg_e2e_time_s": 3.770054,
                "empty_or_malformed_output_count": 0,
                "cap_limited_or_incomplete_count": 0,
                "low_reference_overlap_count": 15,
                "avg_reference_recall": 0.195936,
                "max_vram_reserved_gib": 4.308594,
                "row_count_ok": True,
                "metadata_ok": True,
                "oom_or_cuda_failure": False,
            },
            "DFlash-R1": {
                "row_count": 30,
                "avg_e2e_time_s": 5.188113,
                "empty_or_malformed_output_count": 0,
                "cap_limited_or_incomplete_count": 0,
                "low_reference_overlap_count": 15,
                "avg_reference_recall": 0.204572,
                "max_vram_reserved_gib": 5.361328,
                "row_count_ok": True,
                "metadata_ok": True,
                "oom_or_cuda_failure": False,
            },
            "CC-DFlash-R2 Light GPU": {
                "row_count": 30,
                "avg_e2e_time_s": 5.23531,
                "avg_t_compress_ms": 129.03806,
                "avg_R_actual": 2.192619,
                "empty_or_malformed_output_count": 0,
                "cap_limited_or_incomplete_count": 0,
                "low_reference_overlap_count": 14,
                "avg_reference_recall": 0.210261,
                "max_vram_reserved_gib": 5.414062,
                "row_count_ok": True,
                "metadata_ok": True,
                "oom_or_cuda_failure": False,
            },
        },
    )
    _write_json(
        t105b / "task105b_output_completeness_summary.json",
        {
            "conditions": {
                "Baseline-AR": {"empty_or_malformed_output_count": 0, "cap_limited_or_incomplete_count": 0},
                "DFlash-R1": {"empty_or_malformed_output_count": 0, "cap_limited_or_incomplete_count": 0},
                "CC-DFlash-R2 Light GPU": {
                    "empty_or_malformed_output_count": 0,
                    "cap_limited_or_incomplete_count": 0,
                },
            },
        },
    )
    _write_json(
        t107b / "task107b_fix_summary.json",
        {
            "decision": "PASS_WITH_CAVEAT",
            "best_scoped_gsm8k_candidate": "T106B",
            "t107b_adopted": False,
            "quality_proxy_delta": {
                "before_strict_correct_count": 88,
                "fixed_strict_correct_count": 85,
                "before_strict_wrong_numeric_count": 10,
                "fixed_strict_wrong_numeric_count": 13,
            },
            "cap_limited_delta": {
                "before_cap_limited_count": 2,
                "fixed_cap_limited_count": 2,
            },
            "runtime_delta": {
                "fixed_avg_e2e_time_s": 1.910664,
            },
        },
    )
    return {
        "t103d_closure": t103d / "task103d_closure_summary.json",
        "t103d_human_review": t103d / "task103d_human_review_summary.json",
        "t105b_condition_metrics": t105b / "task105b_condition_metrics.json",
        "t105b_output_completeness": t105b / "task105b_output_completeness_summary.json",
        "t107b_summary": t107b / "task107b_fix_summary.json",
    }


def test_analyzer_writes_all_expected_artifacts_and_recommends_t109(tmp_path: Path) -> None:
    paths = _minimal_inputs(tmp_path)
    out = tmp_path / "out"

    result = t108a.analyze(output_dir=out, **paths)

    assert result["feasibility_summary"]["decision"] == "PASS_WITH_CAVEAT"
    assert result["t108b_recommendation"]["recommended_option"] == "NO_RERUN_KEEP_CAVEAT"
    assert result["t108b_recommendation"]["t108b_justified"] is False
    assert result["next_task_decision"]["next_task"].startswith("T109")
    for relative in t108a.OUTPUT_RELATIVE_PATHS:
        assert (out / relative).exists()


def test_status_snapshot_preserves_qmsum_runtime_and_residual_risk(tmp_path: Path) -> None:
    paths = _minimal_inputs(tmp_path)
    result = t108a.analyze(output_dir=tmp_path / "out", **paths)

    snapshot = result["qmsum_status_snapshot"]
    cc = snapshot["qmsum_runtime_matrix"]["CC-DFlash-R2 Light GPU"]

    assert cc["row_count"] == 30
    assert cc["empty_or_malformed_output_count"] == 0
    assert cc["cap_limited_or_incomplete_count"] == 0
    assert cc["avg_e2e_time_s"] == 5.23531
    assert snapshot["semantic_residual_risk"]["qmsum_deep_fix_status"] == "CLOSED_WITH_PERSISTENT_RESIDUAL_RISK"
    assert snapshot["semantic_residual_risk"]["human_review_label_counts"]["correct_supported"] == 0


def test_fix_candidate_matrix_blocks_unjustified_mechanical_reruns(tmp_path: Path) -> None:
    paths = _minimal_inputs(tmp_path)
    result = t108a.analyze(output_dir=tmp_path / "out", **paths)

    matrix = {item["candidate"]: item for item in result["fix_candidate_matrix"]["candidates"]}

    assert matrix["NO_RERUN_KEEP_CAVEAT"]["recommendation"] == "PRIMARY"
    assert matrix["SMALL_TARGETED_QMSUM_POLICY_RECHECK"]["feasibility"] == "WEAK_OR_NOT_JUSTIFIED"
    assert matrix["QMSUM_FULL_RERUN_OR_N100"]["feasibility"] == "BLOCKED"
    assert matrix["QUERY_AWARE_COMPRESSION_EXPERIMENT"]["feasibility"] == "RESERVED_NOT_DEFAULT"


def test_claim_update_blocks_semantic_and_speed_overclaims(tmp_path: Path) -> None:
    paths = _minimal_inputs(tmp_path)
    result = t108a.analyze(output_dir=tmp_path / "out", **paths)

    claim_update = result["claim_update"]
    blocked = " ".join(claim_update["blocked_claims"])
    allowed = " ".join(claim_update["allowed_claims"])

    assert "QMSum semantic correctness is proven" in blocked
    assert "QMSum residual risk is eliminated" in blocked
    assert "CC-DFlash wins QMSum runtime" in blocked
    assert "QMSum n100 or full rerun is authorized automatically" in blocked
    assert "runtime/feasibility and residual-risk evidence" in allowed


def test_clear_mechanical_failure_can_recommend_scoped_t108b(tmp_path: Path) -> None:
    paths = _minimal_inputs(tmp_path)
    metrics = json.loads(paths["t105b_condition_metrics"].read_text(encoding="utf-8"))
    metrics["CC-DFlash-R2 Light GPU"]["cap_limited_or_incomplete_count"] = 6
    paths["t105b_condition_metrics"].write_text(json.dumps(metrics), encoding="utf-8")

    result = t108a.analyze(output_dir=tmp_path / "out", **paths)

    assert result["t108b_recommendation"]["recommended_option"] == "SCOPED_TARGETED_RECHECK_ONLY"
    assert result["t108b_recommendation"]["t108b_justified"] is True
    assert result["next_task_decision"]["next_task"].startswith("T108B")


def test_task108a_analyzer_does_not_import_model_or_cuda_libraries() -> None:
    source = inspect.getsource(t108a)

    assert "import torch" not in source
    assert "from torch" not in source
    assert "transformers" not in source
    assert "AutoModel" not in source
