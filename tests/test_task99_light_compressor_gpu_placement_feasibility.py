from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task99_light_compressor_gpu_placement_feasibility as t99


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _gpu_row(
    fixture_id: str,
    expected_answer: str,
    generated_text: str,
    *,
    output_tokens: int = 120,
    t_compress_ms: float = 200.0,
    generation_time_s: float = 2.0,
    prefill_ms: float = 100.0,
    tok_per_sec: float = 60.0,
    tau_mean: float = 5.0,
) -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "prompt_id": 1,
        "condition": "CC-DFlash-R2",
        "prompt_source": "dataset",
        "dataset_name": "gsm8k_short",
        "expected_answer": expected_answer,
        "generated_text": generated_text,
        "compressor_profile": "light",
        "compressor_path": "models/light",
        "resolved_compressor_path": "/repo/models/light",
        "compressor_device_map": "cuda",
        "local_files_only": True,
        "max_new_tokens": 256,
        "keep_rate": 0.5,
        "output_tokens": output_tokens,
        "generated_token_count": output_tokens,
        "t_compress_ms": t_compress_ms,
        "R_actual": 2.0,
        "generation_time_s": generation_time_s,
        "t_prefill_ms": prefill_ms,
        "tokens_per_second": tok_per_sec,
        "tau_mean": tau_mean,
        "vram_allocated_gib": 5.5,
        "vram_reserved_gib": 6.2,
        "prefill_vram_allocated_gib": 5.2,
        "prefill_vram_reserved_gib": 6.0,
    }


def _reference_summary(tmp_path: Path) -> dict[str, Path]:
    base = tmp_path / "refs"
    base.mkdir(parents=True, exist_ok=True)
    cpu_light = base / "task96_light.json"
    cpu_large = base / "task96_large.json"
    dflash = base / "task88_dflash.json"
    gpu = base / "gpu.jsonl"
    _write_jsonl(
        gpu,
        [
            _gpu_row("a", "4", "Reasoning\nFinal answer: 4"),
            _gpu_row("b", "5", "Reasoning\nFinal answer: 5"),
            _gpu_row("c", "6", "unfinished output +", output_tokens=256),
        ],
    )
    cpu_light.write_text(
        json.dumps(
            {
                "profile": "light_cpu_task96",
                "source_task": "Task96",
                "comparison_role": "controlled_cpu_reference",
                "dataset": "gsm8k_short",
                "condition": "CC-DFlash-R2",
                "seed": 42,
                "n": 30,
                "max_new_tokens": 256,
                "strict_correct_count": 22,
                "row_count": 30,
                "cap_limited_incomplete_count": 5,
                "strict_wrong_numeric_count": 3,
                "final_answer_marker_count": 25,
                "avg_t_compress_ms": 363.459377,
                "avg_e2e_time_s": 3.225521,
                "avg_R_actual": 2.0,
                "avg_tokens_per_second": 59.755617,
                "avg_tau_mean": 5.565157,
                "avg_t_prefill_ms": 101.308951,
            }
        ),
        encoding="utf-8",
    )
    cpu_large.write_text(
        json.dumps(
            {
                "profile": "large_cpu_task96",
                "source_task": "Task96",
                "comparison_role": "controlled_cpu_reference",
                "dataset": "gsm8k_short",
                "condition": "CC-DFlash-R2",
                "seed": 42,
                "n": 30,
                "max_new_tokens": 256,
                "strict_correct_count": 22,
                "row_count": 30,
                "cap_limited_incomplete_count": 5,
                "strict_wrong_numeric_count": 3,
                "final_answer_marker_count": 25,
                "avg_t_compress_ms": 1201.57527,
                "avg_e2e_time_s": 3.967615,
                "avg_R_actual": 2.666667,
                "avg_tokens_per_second": 58.293439,
                "avg_tau_mean": 5.456126,
                "avg_t_prefill_ms": 105.152591,
            }
        ),
        encoding="utf-8",
    )
    dflash.write_text(
        json.dumps(
            {
                "profile": "dflash_r1_task88",
                "source_task": "Task88",
                "comparison_role": "historical_reference",
                "dataset": "gsm8k_short",
                "condition": "DFlash-R1",
                "seed": 42,
                "n": 30,
                "max_new_tokens": 512,
                "numeric_match_count": 25,
                "numeric_match_rate": 0.833333,
                "avg_t_compress_ms": 0.0,
                "avg_e2e_time_s": 3.219465,
                "avg_tokens_per_second": 52.441431,
                "avg_tau_mean": 5.21,
                "avg_t_prefill_ms": 110.607617,
            }
        ),
        encoding="utf-8",
    )
    return {
        "gpu_jsonl": gpu,
        "task96_light_json": cpu_light,
        "task96_large_json": cpu_large,
        "task88_dflash_json": dflash,
    }


def test_task99_analyzer_writes_outputs_and_marks_historical_reference(tmp_path: Path) -> None:
    refs = _reference_summary(tmp_path)
    output_dir = tmp_path / "out"

    summary = t99.analyze(
        gpu_artifact=refs["gpu_jsonl"],
        output_dir=output_dir,
        task96_light_reference=refs["task96_light_json"],
        task96_large_reference=refs["task96_large_json"],
        dflash_reference=refs["task88_dflash_json"],
    )

    assert summary["gpu_run"]["compressor_device_map"] == "cuda"
    assert summary["gpu_run"]["row_count"] == 3
    assert summary["gpu_run"]["strict_correct_count"] == 2
    assert summary["references"]["dflash_historical"]["historical_only"] is True
    assert summary["recommendation"]["automatic_default_gpu_switch"] is False
    assert (output_dir / "summary" / "task99_gpu_placement_summary.json").exists()
    assert (output_dir / "summary" / "task99_reference_comparison.json").exists()
    assert (output_dir / "summary" / "task99_recommendation.json").exists()
    assert (output_dir / "tables" / "task99_gpu_placement_table.csv").exists()


def test_task99_analyzer_handles_blocked_gpu_result(tmp_path: Path) -> None:
    refs = _reference_summary(tmp_path)
    blocked = tmp_path / "blocked.jsonl"
    _write_jsonl(
        blocked,
        [
            {
                "condition": "CC-DFlash-R2",
                "dataset_name": "gsm8k_short",
                "compressor_profile": "light",
                "compressor_device_map": "cuda",
                "task99_gpu_failure": "CUDA out of memory",
                "task99_gpu_failure_type": "oom",
            }
        ],
    )

    summary = t99.analyze(
        gpu_artifact=blocked,
        output_dir=tmp_path / "out_blocked",
        task96_light_reference=refs["task96_light_json"],
        task96_large_reference=refs["task96_large_json"],
        dflash_reference=refs["task88_dflash_json"],
    )

    assert summary["decision"] in {"PARTIAL", "FAIL"}
    assert summary["gpu_run"]["failure_flags"]["oom_or_cuda_failure"] is True
    assert summary["recommendation"]["keep_cpu_light_supported_path"] is True
    assert summary["comparisons"]["light_gpu_vs_task96_light_cpu"]["comparisons"]["strict_correct_delta"] is None


def test_no_model_loading_in_task99_analyzer() -> None:
    source = inspect.getsource(t99)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
