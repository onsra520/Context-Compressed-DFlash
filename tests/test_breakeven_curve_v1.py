from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_1_system_build_and_evaluation.analysis.breakeven_curve_v1 import (
    analyze_breakeven_curve_v1,
    summarize_condition,
    summarize_prefill_reference,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_summarize_prefill_reference_reads_task39_fields(tmp_path: Path):
    path = tmp_path / "prefill.jsonl"
    _write_jsonl(
        path,
        [
            {
                "condition": "Baseline-AR",
                "input_tokens": 20,
                "t_prefill_ms": 100.0,
                "t_prefill_mode": "cuda_synchronized",
                "prefill_vram_allocated_gib": 2.0,
                "prefill_vram_reserved_gib": 2.5,
            }
        ],
    )

    summary = summarize_prefill_reference(path)

    assert summary["rows"] == 1
    assert summary["condition"] == "Baseline-AR"
    assert summary["avg_t_prefill_ms"] == 100.0
    assert summary["avg_input_tokens"] == 20.0
    assert summary["max_prefill_vram_allocated_gib"] == 2.0
    assert summary["t_prefill_modes"] == ["cuda_synchronized"]


def test_summarize_condition_labels_missing_compressed_t_prefill(tmp_path: Path):
    path = tmp_path / "cc.jsonl"
    _write_jsonl(
        path,
        [
            {
                "condition": "CC-LLM-R2",
                "input_tokens": 50,
                "t_compress_ms": 75.0,
                "R_actual": 2.0,
                "keep_rate": 0.5,
                "N_original": 40,
                "N_compressed": 20,
            }
        ],
    )
    reference = {"avg_t_prefill_ms": 100.0, "avg_input_tokens": 20.0}

    summary = summarize_condition("CC-LLM-R2", path, reference)

    assert summary["data_status"] == "insufficient_measured_compressed_t_prefill"
    assert summary["rows_with_t_prefill_ms"] == 0
    assert summary["saved_prefill_fraction_model"] == 0.75
    assert summary["required_full_prefill_ms_for_breakeven"] == 100.0
    assert summary["reference_prefill_saved_ms"] == 75.0
    assert summary["reference_prefill_margin_ms"] == 0.0
    assert summary["estimated_original_prefill_ms_from_quadratic_scaling"] == 400.0
    assert summary["estimated_saved_prefill_ms_from_quadratic_scaling"] == 300.0
    assert summary["estimated_margin_ms_from_quadratic_scaling"] == 225.0


def test_analyze_breakeven_curve_v1_is_partial_when_compressed_prefill_missing(tmp_path: Path):
    prefill = tmp_path / "prefill.jsonl"
    cc = tmp_path / "cc.jsonl"
    _write_jsonl(
        prefill,
        [
            {
                "condition": "Baseline-AR",
                "input_tokens": 20,
                "t_prefill_ms": 100.0,
                "t_prefill_mode": "cuda_synchronized",
            }
        ],
    )
    _write_jsonl(
        cc,
        [
            {
                "condition": "CC-LLM-R2",
                "input_tokens": 50,
                "t_compress_ms": 75.0,
                "R_actual": 2.0,
                "keep_rate": 0.5,
                "N_original": 40,
                "N_compressed": 20,
            }
        ],
    )

    summary = analyze_breakeven_curve_v1(
        prefill_artifact=prefill,
        condition_artifacts={"CC-LLM-R2": cc},
    )

    assert summary["status"] == "PARTIAL"
    assert summary["interpretation"]["measured_compressed_t_prefill_available"] is False
    assert summary["interpretation"]["insufficient_conditions"] == ["CC-LLM-R2"]
