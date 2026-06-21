from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task100a_phase2_supported_evidence_summary as t100a


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _input_paths(tmp_path: Path) -> dict[str, Path]:
    base = tmp_path / "inputs"
    task96 = base / "task96_summary.json"
    task99r = base / "task99r_summary.json"
    _write_json(
        task96,
        {
            "profiles": {
                "seed42_large_n30_mnt256": {
                    "strict_correct_count": 22,
                    "row_count": 30,
                    "cap_limited_incomplete_count": 5,
                    "avg_t_compress_ms": 1201.57527,
                    "avg_e2e_time_s": 3.967615,
                    "avg_R_actual": 2.666667,
                },
                "seed42_light_n30_mnt256": {
                    "strict_correct_count": 22,
                    "row_count": 30,
                    "cap_limited_incomplete_count": 5,
                    "avg_t_compress_ms": 363.459377,
                    "avg_e2e_time_s": 3.225521,
                    "avg_R_actual": 2.0,
                },
            },
            "method": {
                "condition": "CC-DFlash-R2",
                "dataset": "gsm8k_short",
                "max_new_tokens": 256,
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
                "cap_limited_incomplete_count": 1,
                "avg_t_compress_ms": 25.568672,
                "avg_e2e_time_s": 2.668067,
                "avg_tokens_per_second": 62.740802,
                "avg_R_actual": 2.0,
                "avg_vram_reserved_gib": 4.363477,
                "compressor_profile": "light",
                "compressor_device_map": "cuda",
                "requested_compressor_device_map": "cuda",
                "failure_flags": {"oom_or_cuda_failure": False},
            },
            "references": {
                "dflash_historical": {
                    "source_task": "Task88",
                    "condition": "DFlash-R1",
                    "row_count": 30,
                    "max_new_tokens": 512,
                    "historical_only": True,
                    "comparison_note": "Historical-only DFlash-R1 reference.",
                }
            },
        },
    )
    return {"task96": task96, "task99r": task99r}


def test_task100a_packaging_writes_expected_artifacts(tmp_path: Path) -> None:
    paths = _input_paths(tmp_path)
    output_dir = tmp_path / "out"

    result = t100a.analyze(
        output_dir=output_dir,
        task96_summary=paths["task96"],
        task99r_summary=paths["task99r"],
    )

    assert result["decision"] == "PASS"
    assert (output_dir / "task100a_supported_evidence_summary.json").exists()
    assert (output_dir / "task100a_supported_evidence_table.csv").exists()
    assert (output_dir / "task100a_candidate_status.json").exists()
    assert (output_dir / "task100a_next_step_plan.json").exists()
    assert (output_dir / "task100a_claim_language.json").exists()


def test_task100a_classifies_candidates_and_claims(tmp_path: Path) -> None:
    paths = _input_paths(tmp_path)
    output_dir = tmp_path / "out"
    t100a.analyze(output_dir=output_dir, task96_summary=paths["task96"], task99r_summary=paths["task99r"])

    summary = json.loads((output_dir / "task100a_supported_evidence_summary.json").read_text(encoding="utf-8"))
    assert summary["evidence_classes"]["supported_controlled_result"]["name"] == "CC-DFlash-R2 Light CPU"
    assert summary["evidence_classes"]["supported_controlled_result"]["status"] == "supported controlled Phase 2 CPU path"
    assert summary["evidence_classes"]["historical_control_reference"]["name"] == "CC-DFlash-R2 Large CPU"
    assert "superseded" in summary["evidence_classes"]["historical_control_reference"]["status"]
    assert summary["evidence_classes"]["promising_bounded_candidate"]["name"] == "CC-DFlash-R2 Light GPU"
    assert summary["evidence_classes"]["promising_bounded_candidate"]["is_default"] is False
    assert summary["evidence_classes"]["historical_dflash_reference"]["historical_only"] is True

    candidate_status = json.loads((output_dir / "task100a_candidate_status.json").read_text(encoding="utf-8"))
    assert candidate_status["large_cpu"]["retained_as_reference"] is True
    assert candidate_status["light_gpu"]["deployment_ready"] is False

    claim_language = json.loads((output_dir / "task100a_claim_language.json").read_text(encoding="utf-8"))
    assert "The light CPU compressor path is the supported controlled Phase 2 result." in claim_language["allowed"]
    assert "Light GPU is the default." in claim_language["blocked"]


def test_task100a_next_step_plan_blocks_full_matrix_and_tuning(tmp_path: Path) -> None:
    paths = _input_paths(tmp_path)
    output_dir = tmp_path / "out"
    t100a.analyze(output_dir=output_dir, task96_summary=paths["task96"], task99r_summary=paths["task99r"])

    plan = json.loads((output_dir / "task100a_next_step_plan.json").read_text(encoding="utf-8"))
    assert plan["next_gated_task"] == "T100B — Light GPU n100 Controlled Run"
    assert plan["scope"]["n"] == 100
    assert plan["scope"]["compressor_device_map"] == "cuda"
    assert plan["blocked_actions"]["large_cpu_n100"] is True
    assert plan["blocked_actions"]["full_matrix"] is True
    assert plan["blocked_actions"]["qmsum"] is True
    assert plan["blocked_actions"]["keep_rate_tuning"] is True
    assert plan["framing"]["not_final_benchmark"] is True


def test_task100a_script_has_no_model_loading() -> None:
    source = inspect.getsource(t100a)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "cuda" not in source.lower() or "compressor_device_map" in source
