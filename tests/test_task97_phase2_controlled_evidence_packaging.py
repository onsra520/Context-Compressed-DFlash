from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task97_phase2_controlled_evidence_packaging as t97


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _input_paths(tmp_path: Path) -> dict[str, Path]:
    base = tmp_path / "inputs"
    base.mkdir(parents=True, exist_ok=True)

    paths = {name: base / f"{name}.json" for name in t97.DEFAULT_INPUTS}
    _write_json(
        paths["task93"],
        {
            "profiles": {
                "large": {"avg_R_actual": 2.6666667, "avg_t_compress_ms": 1326.8266},
                "light": {"avg_R_actual": 2.0, "avg_t_compress_ms": 426.7625},
            }
        },
    )
    _write_json(
        paths["task94"],
        {
            "comparison": {"decision": {"status": "PASS_WITH_CAVEAT"}},
            "profiles": {
                "large": {
                    "numeric_extraction_match_count": 6,
                    "rows": 10,
                    "avg_t_compress_ms": 1190.11,
                    "avg_e2e_time_s": 3.10,
                    "avg_R_actual": 2.666667,
                },
                "light": {
                    "numeric_extraction_match_count": 2,
                    "rows": 10,
                    "avg_t_compress_ms": 406.39,
                    "avg_e2e_time_s": 2.46,
                    "avg_R_actual": 2.0,
                },
            },
        },
    )
    _write_json(
        paths["task95a"],
        {
            "outcome_group_counts": {"large_correct_light_wrong": 3},
            "failure_taxonomy_counts": {"truncation_or_cap_issue": 3, "format_or_extraction_issue": 1},
        },
    )
    _write_json(
        paths["task95b"],
        {
            "profiles": {
                "large": {"strict_correct_count": 5, "rows": 10, "cap_limited_count": 5},
                "light": {"strict_correct_count": 2, "rows": 10, "cap_limited_count": 7},
            },
            "recommendation": {"proxy_uncertainty_explains_gap": False},
        },
    )
    _write_json(
        paths["task95c"],
        {
            "decision": "PARTIAL",
            "gpu_gate": {"cuda_available": False},
            "static_cap_audit": {
                "large": {"strict_calibrated_correct": 5, "rows": 10, "cap_limited_incomplete": 5},
                "light": {"strict_calibrated_correct": 2, "rows": 10, "cap_limited_incomplete": 7},
            },
        },
    )
    _write_json(
        paths["task95c_r"],
        {
            "profiles": {
                "large_256": {
                    "strict_correct_count": 8,
                    "row_count": 10,
                    "cap_limited_incomplete_count": 1,
                    "avg_t_compress_ms": 1272.62,
                    "avg_e2e_time_s": 3.78,
                    "avg_R_actual": 2.666667,
                },
                "light_256": {
                    "strict_correct_count": 8,
                    "row_count": 10,
                    "cap_limited_incomplete_count": 1,
                    "avg_t_compress_ms": 412.97,
                    "avg_e2e_time_s": 3.09,
                    "avg_R_actual": 2.0,
                },
            }
        },
    )
    _write_json(
        paths["task95d"],
        {
            "fixture_overlap": {"overlap_count": 0, "confirmation_count": 10},
            "profiles": {
                "seed43_large_256": {
                    "strict_correct_count": 7,
                    "row_count": 10,
                    "cap_limited_incomplete_count": 3,
                    "avg_t_compress_ms": 1159.84,
                    "avg_e2e_time_s": 4.20,
                    "avg_R_actual": 2.666667,
                },
                "seed43_light_256": {
                    "strict_correct_count": 8,
                    "row_count": 10,
                    "cap_limited_incomplete_count": 2,
                    "avg_t_compress_ms": 362.78,
                    "avg_e2e_time_s": 3.41,
                    "avg_R_actual": 2.0,
                },
            },
        },
    )
    _write_json(
        paths["task96"],
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
            }
        },
    )
    return paths


def test_task97_analyze_writes_expected_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    result = t97.analyze(output_dir, _input_paths(tmp_path))

    summary = result["summary"]
    assert summary["decision"] == "PASS"
    assert summary["main_controlled_result"]["large"]["strict_correct"] == "22/30"
    assert summary["main_controlled_result"]["light"]["avg_t_compress_ms"] == 363.46
    assert summary["recommended_next_tasks"][0] == "T98 optional n100 go/no-go decision"
    assert len(summary["evidence_chain"]) == 8

    claim_boundary = json.loads((output_dir / "task97_claim_boundary.json").read_text(encoding="utf-8"))
    assert "no automatic n100 authorization" in claim_boundary["blocked_claims"]

    roadmap_update = json.loads((output_dir / "task97_roadmap_plan_update.json").read_text(encoding="utf-8"))
    t99 = next(row for row in roadmap_update["future_plan"] if row["task"] == "T99")
    assert t99["status"] == "PLANNED / GATED"
    assert "gpu placement feasibility" in t99["title"].lower()

    table_text = (output_dir / "task97_phase2_evidence_table.csv").read_text(encoding="utf-8")
    assert "T96" in table_text
    assert "22/30" in table_text


def test_no_model_loading_or_cuda_imports() -> None:
    source = inspect.getsource(t97)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "torch.cuda" not in source
