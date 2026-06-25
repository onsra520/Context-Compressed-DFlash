from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task106c_optimized_default_candidate_decision as t106c


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _minimal_inputs(root: Path) -> dict[str, Path]:
    t105c = root / "task105c" / "summary"
    t106a = root / "task106a" / "summary"
    t106b = root / "task106b" / "summary"
    _write_json(
        t105c / "task105c_closure_summary.json",
        {
            "decision": "PASS_WITH_CAVEAT",
            "no_default_switch": True,
            "qmsum_caveat_mandatory": True,
        },
    )
    _write_json(
        t105c / "task105c_t106_unblock_requirements.json",
        {
            "must_not_switch_defaults_automatically": True,
            "must_preserve": [
                "GSM8K faster-than-Baseline only",
                "not faster-than-DFlash on GSM8K",
                "not faster-than-any-reference on QMSum",
                "QMSum semantic caveat",
            ],
        },
    )
    _write_json(
        t106a / "task106a_audit_summary.json",
        {
            "decision": "PASS_WITH_CAVEAT",
            "cap_limited_fixture_overlap": {
                "cc_cap_limited_count": 15,
                "cc_only_count": 9,
                "shared_by_all_three_count": 6,
            },
            "attribution_counts": {
                "tag_counts": {
                    "final_answer_marker_missing": 15,
                    "verbose_or_long_reasoning_near_cap": 15,
                }
            },
        },
    )
    _write_json(
        t106b / "task106b_fix_summary.json",
        {
            "decision": "PASS_WITH_CAVEAT",
            "fix_interpretation": "cap_fix_supported_with_caveat",
            "metadata_audit": {"valid": True},
            "quality_proxy_delta": {
                "before_strict_correct_count": 79,
                "fixed_strict_correct_count": 88,
                "strict_correct_delta": 9,
                "before_strict_wrong_numeric_count": 6,
                "fixed_strict_wrong_numeric_count": 10,
                "strict_wrong_numeric_delta": 4,
                "before_final_answer_marker_count": 85,
                "fixed_final_answer_marker_count": 98,
            },
            "cap_limited_delta": {
                "before_cap_limited_count": 15,
                "fixed_cap_limited_count": 2,
                "cap_limited_delta": -13,
            },
            "runtime_delta": {
                "before_avg_e2e_time_s": 2.896622,
                "fixed_avg_e2e_time_s": 2.145689,
                "avg_e2e_time_s_delta": -0.750933,
                "fixed_avg_t_compress_ms": 17.45762,
                "fixed_max_vram_reserved_gib": 4.439453,
            },
            "policy": {
                "policy_name": "gsm8k_concise_final_answer_v1",
                "default_behavior_changed": False,
            },
        },
    )
    return {
        "t105c_summary": t105c / "task105c_closure_summary.json",
        "t105c_unblock": t105c / "task105c_t106_unblock_requirements.json",
        "t106a_summary": t106a / "task106a_audit_summary.json",
        "t106b_summary": t106b / "task106b_fix_summary.json",
    }


def test_analyzer_writes_decision_artifacts_and_blocks_default_switch(tmp_path: Path) -> None:
    paths = _minimal_inputs(tmp_path)
    out = tmp_path / "out"

    result = t106c.analyze(output_dir=out, **paths)

    assert result["decision_summary"]["decision"] == "PASS_WITH_CAVEAT"
    assert result["decision_summary"]["optimized_path_status"] == "SCOPED_GSM8K_CANDIDATE"
    assert result["decision_summary"]["default_switch"] == "NO"
    assert result["decision_summary"]["qmsum_default_support"] == "NO"
    assert result["decision_summary"]["production_ready"] == "NO"
    assert result["decision_summary"]["needs_reference_policy_fairness_rerun_for_final_all_reference_win"] == "YES"
    assert result["next_task_decision"]["next_task"].startswith("T107")
    for relative in t106c.OUTPUT_RELATIVE_PATHS:
        assert (out / relative).exists()


def test_supported_claims_are_bounded_and_blocked_claims_cover_reference_wins(tmp_path: Path) -> None:
    paths = _minimal_inputs(tmp_path)
    result = t106c.analyze(output_dir=tmp_path / "out", **paths)

    supported_text = " ".join(result["supported_candidate_claims"]["claims"])
    blocked_text = " ".join(result["blocked_default_claims"]["claims"])

    assert "scoped GSM8K candidate" in supported_text
    assert "QMSum semantic correctness is proven" in blocked_text
    assert "Optimized CC-DFlash wins all references" in blocked_text
    assert "No default switch is authorized" in supported_text
    assert "default winner" not in supported_text.lower()


def test_fairness_caveats_require_reference_policy_rerun(tmp_path: Path) -> None:
    paths = _minimal_inputs(tmp_path)
    result = t106c.analyze(output_dir=tmp_path / "out", **paths)

    caveats = result["fairness_caveats"]

    assert caveats["reference_policy_fairness_rerun_required"] is True
    assert any("Baseline-AR" in item for item in caveats["caveats"])
    assert any("DFlash-R1" in item for item in caveats["caveats"])
    assert any("Wrong numeric increased" in item for item in caveats["caveats"])


def test_candidate_policy_matrix_preserves_qmsum_and_global_boundaries(tmp_path: Path) -> None:
    paths = _minimal_inputs(tmp_path)
    result = t106c.analyze(output_dir=tmp_path / "out", **paths)

    matrix = {item["claim_area"]: item for item in result["candidate_policy_matrix"]}

    assert matrix["GSM8K optimized path"]["status"] == "SCOPED_CANDIDATE"
    assert matrix["Global default switch"]["status"] == "BLOCKED"
    assert matrix["QMSum semantics"]["status"] == "BLOCKED"
    assert matrix["Reference fairness"]["status"] == "INCOMPLETE"


def test_missing_or_invalid_input_keeps_default_switch_blocked(tmp_path: Path) -> None:
    paths = _minimal_inputs(tmp_path)
    bad = json.loads(paths["t106b_summary"].read_text(encoding="utf-8"))
    bad["metadata_audit"]["valid"] = False
    paths["t106b_summary"].write_text(json.dumps(bad), encoding="utf-8")

    result = t106c.analyze(output_dir=tmp_path / "out", **paths)

    assert result["decision_summary"]["decision"] == "PARTIAL"
    assert result["decision_summary"]["default_switch"] == "NO"
    assert result["next_task_decision"]["next_task"].startswith("T107")
    assert result["next_task_decision"]["requires_manual_caveat_review"] is True


def test_task106c_analyzer_does_not_import_model_or_cuda_libraries() -> None:
    source = inspect.getsource(t106c)

    assert "import torch" not in source
    assert "from torch" not in source
    assert "transformers" not in source
    assert "AutoModel" not in source
