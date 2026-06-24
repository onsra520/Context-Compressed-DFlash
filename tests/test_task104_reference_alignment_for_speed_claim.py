from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from scripts.phase_2_system_optimization.analysis import task104_reference_alignment_for_speed_claim as t104


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _inputs(tmp_path: Path) -> t104.AlignmentInputs:
    root = tmp_path / "inputs"
    task96 = root / "task96.json"
    task99r = root / "task99r.json"
    task100b = root / "task100b.json"
    task102 = root / "task102.json"
    task103d = root / "task103d.json"

    _write_json(
        task96,
        {
            "method": {"dataset": "gsm8k_short", "n": 30, "max_new_tokens": 256},
            "profiles": {
                "seed42_large_n30_mnt256": {
                    "profile": "large",
                    "strict_correct_count": 22,
                    "row_count": 30,
                    "avg_t_compress_ms": 1201.58,
                    "avg_e2e_time_s": 3.97,
                    "avg_R_actual": 2.67,
                },
                "seed42_light_n30_mnt256": {
                    "profile": "light",
                    "strict_correct_count": 22,
                    "row_count": 30,
                    "avg_t_compress_ms": 363.46,
                    "avg_e2e_time_s": 3.23,
                    "avg_R_actual": 2.0,
                },
            },
            "comparisons": {
                "light_vs_large": {
                    "strict_correct_delta": 0,
                    "avg_t_compress_ms_delta": -838.12,
                    "avg_e2e_time_s_delta": -0.74,
                }
            },
        },
    )
    _write_json(
        task99r,
        {
            "decision": "PASS_WITH_CAVEAT",
            "gpu_run": {
                "row_count": 10,
                "strict_correct_count": 8,
                "avg_t_compress_ms": 25.57,
                "avg_e2e_time_s": 2.67,
                "max_vram_reserved_gib": 4.36,
            },
        },
    )
    _write_json(
        task100b,
        {
            "run": {
                "row_count": 100,
                "strict_correct_count": 79,
                "cap_limited_incomplete_count": 15,
                "avg_t_compress_ms": 17.35,
                "avg_e2e_time_s": 2.88,
                "avg_tokens_per_second": 59.83,
                "avg_R_actual": 2.0,
                "max_vram_reserved_gib": 4.43,
            },
            "comparisons": {
                "light_gpu_n100_vs_dflash_r1_historical": {
                    "comparison_class": "historical_reference",
                    "settings_match": False,
                }
            },
        },
    )
    _write_json(
        task102,
        {
            "dataset": "qmsum_meeting_qa_long",
            "max_new_tokens": 384,
            "run_status": {
                "n30": {
                    "row_count": 30,
                    "stats": {
                        "t_compress_ms": {"avg": 125.26},
                        "e2e_time_s": {"avg": 5.00},
                        "tokens_per_second": {"avg": 21.34},
                        "R_actual": {"avg": 2.19},
                        "vram_reserved_gib": {"max": 5.41},
                    },
                }
            },
        },
    )
    _write_json(
        task103d,
        {
            "decision": "PASS_WITH_CAVEAT",
            "qmsum_deep_fix_status": "CLOSED_WITH_PERSISTENT_RESIDUAL_RISK",
            "qmsum_semantic_correctness": "NOT_CLAIMED",
            "qmsum_quality_risk_eliminated": "NO",
            "t104_allowed": "YES_WITH_MANDATORY_QMSUM_CAVEAT",
            "human_review_label_counts": {
                "correct_supported": 0,
                "partially_correct_or_incomplete": 2,
                "unsupported_or_wrong": 1,
                "cannot_determine_from_available_context": 3,
            },
        },
    )
    return t104.AlignmentInputs(
        task96_summary=task96,
        task99r_summary=task99r,
        task100b_summary=task100b,
        task102_summary=task102,
        task103d_summary=task103d,
    )


def test_reference_alignment_writes_expected_outputs(tmp_path: Path) -> None:
    result = t104.run_reference_alignment(inputs=_inputs(tmp_path), output_dir=tmp_path / "out")

    assert result["speed_reference_summary"]["decision"] == "PASS_WITH_CAVEAT"
    assert result["next_task_decision"]["next_task"] == "T105 — Controlled Full Matrix / Benchmark-Scope Claim Closure"
    assert (tmp_path / "out" / "task104_speed_reference_summary.json").exists()
    assert (tmp_path / "out" / "task104_comparator_map.json").exists()
    assert (tmp_path / "out" / "tables" / "task104_speed_reference_alignment_table.csv").exists()


def test_comparator_map_uses_required_classes(tmp_path: Path) -> None:
    result = t104.run_reference_alignment(inputs=_inputs(tmp_path), output_dir=tmp_path / "out")
    by_id = {row["comparison_id"]: row for row in result["comparator_map"]["comparisons"]}

    assert by_id["t96_large_cpu_vs_light_cpu_gsm8k_n30"]["comparison_class"] == "controlled_comparison"
    assert by_id["t100b_light_gpu_gsm8k_n100"]["comparison_class"] == "single_condition_observation"
    assert by_id["t102_qmsum_light_gpu_n30"]["comparison_class"] == "single_condition_observation"
    assert by_id["older_baseline_dflash_matrix"]["comparison_class"] == "historical_reference_only"
    assert by_id["final_speed_ranking"]["comparison_class"] == "requires_t105_matrix"


def test_supported_and_blocked_claims_are_bounded(tmp_path: Path) -> None:
    result = t104.run_reference_alignment(inputs=_inputs(tmp_path), output_dir=tmp_path / "out")

    supported = " ".join(result["supported_speed_claims"]["supported_claims"])
    blocked = " ".join(result["blocked_speed_claims"]["blocked_claims"])
    assert "Light compressor reduced T_compress" in supported
    assert "configuration-scoped" in supported
    assert "CC-DFlash is finally faster than Baseline-AR" in blocked
    assert "QMSum semantic correctness is proven" in blocked
    assert "Universal 8GB deployment readiness is proven" in blocked


def test_qmsum_caveat_is_mandatory_and_carries_t103d_counts(tmp_path: Path) -> None:
    result = t104.run_reference_alignment(inputs=_inputs(tmp_path), output_dir=tmp_path / "out")

    caveat = result["qmsum_caveat_carryforward"]
    assert caveat["mandatory"] is True
    assert caveat["qmsum_semantic_correctness"] == "NOT_CLAIMED"
    assert caveat["human_review_label_counts"]["correct_supported"] == 0
    assert caveat["human_review_label_counts"]["cannot_determine_from_available_context"] == 3


def test_t105_requirements_include_controlled_matrix_fields(tmp_path: Path) -> None:
    result = t104.run_reference_alignment(inputs=_inputs(tmp_path), output_dir=tmp_path / "out")

    requirements = " ".join(result["t105_unblock_requirements"]["minimum_requirements"])
    assert "same dataset" in requirements
    assert "same n" in requirements
    assert "same max_new_tokens" in requirements
    assert "Baseline-AR" in requirements
    assert "DFlash-R1" in requirements
    assert "optimized CC-DFlash-R2 Light GPU" in requirements


def test_t104_rejects_missing_qmsum_caveat_gate(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write_json(inputs.task103d_summary, {"decision": "PASS_WITH_CAVEAT", "t104_allowed": "NO"})

    with pytest.raises(ValueError, match="T103D"):
        t104.run_reference_alignment(inputs=inputs, output_dir=tmp_path / "out")


def test_no_model_loading_in_task104_script() -> None:
    source = inspect.getsource(t104)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
