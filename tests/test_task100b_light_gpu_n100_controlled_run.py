from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task100b_light_gpu_n100_controlled_run as t100b


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _gpu_row(
    index: int,
    expected_answer: str,
    generated_text: str,
    *,
    output_tokens: int = 120,
    max_new_tokens: int = 256,
    compressor_device_map: str = "cuda",
    requested_compressor_device_map: str = "cuda",
    t_compress_ms: float = 18.0,
    generation_time_s: float = 2.7,
    tokens_per_second: float = 60.0,
    tau_mean: float = 5.6,
) -> dict[str, object]:
    fixture_id = f"gsm8k_short_test_{index:04d}"
    return {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "prompt_id": index,
        "benchmark_prompt_index": index,
        "condition": "CC-DFlash-R2",
        "prompt_source": "dataset",
        "dataset_name": "gsm8k_short",
        "expected_answer": expected_answer,
        "generated_text": generated_text,
        "compressor_profile": "light",
        "compressor_path": "models/light",
        "resolved_compressor_path": "/repo/models/light",
        "compressor_device_map": compressor_device_map,
        "requested_compressor_device_map": requested_compressor_device_map,
        "local_files_only": True,
        "max_new_tokens": max_new_tokens,
        "keep_rate": 0.5,
        "output_tokens": output_tokens,
        "generated_token_count": output_tokens,
        "t_compress_ms": t_compress_ms,
        "R_actual": 2.0,
        "generation_time_s": generation_time_s,
        "e2e_time_s": generation_time_s + (t_compress_ms / 1000.0),
        "t_prefill_ms": 95.0,
        "tokens_per_second": tokens_per_second,
        "tau_mean": tau_mean,
        "vram_allocated_gib": 4.16,
        "vram_reserved_gib": 4.43,
        "prefill_vram_allocated_gib": 4.16,
        "prefill_vram_reserved_gib": 4.43,
    }


def _complete_gpu_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(1, 101):
        rows.append(_gpu_row(index, str(index), f"Reasoning\nFinal answer: {index}"))
    return rows


def _refs(tmp_path: Path) -> dict[str, Path]:
    refs = tmp_path / "refs"
    refs.mkdir(parents=True, exist_ok=True)
    task99r = refs / "task99r.json"
    task96_light = refs / "task96_light.json"
    task96_large = refs / "task96_large.json"
    dflash = refs / "task88_dflash.json"
    task99r.write_text(
        json.dumps(
            {
                "task": "Task99-R",
                "gpu_run": {
                    "artifact": "task99r.jsonl",
                    "row_count": 10,
                    "max_new_tokens": 256,
                    "strict_correct_count": 8,
                    "cap_limited_incomplete_count": 1,
                    "strict_wrong_numeric_count": 1,
                    "final_answer_marker_count": 9,
                    "avg_t_compress_ms": 25.568672,
                    "avg_e2e_time_s": 2.668067,
                    "avg_R_actual": 2.0,
                    "avg_tokens_per_second": 62.740802,
                    "avg_tau_mean": 5.880314,
                    "avg_t_prefill_ms": 99.33317,
                    "avg_vram_reserved_gib": 4.363477,
                    "compressor_profile": "light",
                    "compressor_device_map": "cuda",
                    "requested_compressor_device_map": "cuda",
                },
            }
        ),
        encoding="utf-8",
    )
    task96_light.write_text(
        json.dumps(
            {
                "profile": "light_cpu_task96",
                "source_task": "Task96",
                "comparison_role": "controlled_cpu_reference",
                "dataset": "gsm8k_short",
                "condition": "CC-DFlash-R2",
                "seed": 42,
                "n": 30,
                "row_count": 30,
                "max_new_tokens": 256,
                "strict_correct_count": 22,
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
    task96_large.write_text(
        json.dumps(
            {
                "profile": "large_cpu_task96",
                "source_task": "Task96",
                "comparison_role": "controlled_cpu_reference",
                "dataset": "gsm8k_short",
                "condition": "CC-DFlash-R2",
                "seed": 42,
                "n": 30,
                "row_count": 30,
                "max_new_tokens": 256,
                "strict_correct_count": 22,
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
                "row_count": 30,
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
        "task99r": task99r,
        "task96_light": task96_light,
        "task96_large": task96_large,
        "dflash": dflash,
    }


def test_analyzer_reads_fixture_jsonl_and_writes_outputs(tmp_path: Path) -> None:
    run = tmp_path / "run.jsonl"
    _write_jsonl(run, _complete_gpu_rows())
    refs = _refs(tmp_path)

    summary = t100b.analyze(
        run_artifact=run,
        output_dir=tmp_path / "out",
        task99r_summary=refs["task99r"],
        task96_light_reference=refs["task96_light"],
        task96_large_reference=refs["task96_large"],
        dflash_reference=refs["dflash"],
    )

    assert summary["task"] == "Task100B"
    assert summary["light_gpu_n100"]["row_count"] == 100
    assert summary["light_gpu_n100"]["strict_correct_count"] == 100
    assert summary["light_gpu_n100"]["metadata_ok"] is True
    assert summary["recommendation"]["automatic_default_gpu_switch"] is False
    assert summary["recommendation"]["final_claims_allowed"] is False
    assert (tmp_path / "out" / "summary" / "task100b_light_gpu_n100_summary.json").exists()
    assert (tmp_path / "out" / "summary" / "task100b_recommendation.json").exists()
    assert (tmp_path / "out" / "summary" / "task100b_row_labels.jsonl").exists()
    assert (tmp_path / "out" / "summary" / "task100b_reference_comparison.json").exists()
    assert (tmp_path / "out" / "tables" / "task100b_light_gpu_n100_table.csv").exists()


def test_calibrated_strict_cap_and_missing_fields_are_safe(tmp_path: Path) -> None:
    run = tmp_path / "run.jsonl"
    rows = [
        _gpu_row(1, "4", "Reasoning\nFinal answer: 4"),
        _gpu_row(2, "5", "unfinished output +", output_tokens=256),
        {"condition": "CC-DFlash-R2", "dataset_name": "gsm8k_short", "expected_answer": "6"},
    ]
    _write_jsonl(run, rows)

    summary = t100b.summarize_light_gpu_run(run)

    assert summary["row_count"] == 3
    assert summary["strict_correct_count"] == 1
    assert summary["cap_limited_incomplete_count"] == 1
    assert summary["answer_missing_count"] >= 1
    assert summary["metadata_ok"] is False


def test_metadata_must_confirm_cuda_and_recommendation_blocks_wrong_device(tmp_path: Path) -> None:
    run = tmp_path / "cpu_run.jsonl"
    rows = _complete_gpu_rows()
    rows[0]["compressor_device_map"] = "cpu"
    _write_jsonl(run, rows)
    refs = _refs(tmp_path)

    summary = t100b.analyze(
        run_artifact=run,
        output_dir=tmp_path / "out",
        task99r_summary=refs["task99r"],
        task96_light_reference=refs["task96_light"],
        task96_large_reference=refs["task96_large"],
        dflash_reference=refs["dflash"],
    )

    assert summary["light_gpu_n100"]["metadata_ok"] is False
    assert summary["decision"] == "FAIL"
    assert summary["recommendation"]["automatic_default_gpu_switch"] is False


def test_oom_or_cuda_failure_flags_make_result_partial_or_fail(tmp_path: Path) -> None:
    run = tmp_path / "blocked.jsonl"
    _write_jsonl(
        run,
        [
            {
                "condition": "CC-DFlash-R2",
                "dataset_name": "gsm8k_short",
                "compressor_profile": "light",
                "compressor_device_map": "cuda",
                "requested_compressor_device_map": "cuda",
                "task100b_failure": "CUDA out of memory",
                "task100b_failure_type": "oom",
            }
        ],
    )

    summary = t100b.summarize_light_gpu_run(run)
    recommendation = t100b.build_recommendation(
        run_summary=summary,
        task99r_reference={"row_count": 10},
        task96_light_reference={"row_count": 30, "strict_correct_count": 22},
    )

    assert summary["failure_flags"]["oom_or_cuda_failure"] is True
    assert recommendation["decision"] in {"PARTIAL", "FAIL"}
    assert recommendation["keep_cpu_light_supported_path"] is True


def test_reference_comparisons_mark_bounded_and_historical_when_settings_differ(tmp_path: Path) -> None:
    run_summary = t100b.summarize_light_gpu_run_from_rows(_complete_gpu_rows(), artifact=tmp_path / "run.jsonl")
    refs = _refs(tmp_path)
    comparisons = t100b.build_reference_comparisons(
        run_summary=run_summary,
        task99r_reference=t100b.load_reference(refs["task99r"], role="bounded_gpu_reference"),
        task96_light_reference=t100b.load_reference(refs["task96_light"], role="controlled_cpu_reference"),
        task96_large_reference=t100b.load_reference(refs["task96_large"], role="controlled_cpu_reference"),
        dflash_reference=t100b.load_reference(refs["dflash"], role="historical_reference", historical_only=True),
    )

    assert comparisons["light_gpu_n100_vs_task99r_light_gpu_n10"]["settings_match"] is False
    assert comparisons["light_gpu_n100_vs_task99r_light_gpu_n10"]["comparison_class"] == "bounded_reference"
    assert comparisons["light_gpu_n100_vs_task96_light_cpu_n30"]["comparison_class"] == "bounded_reference"
    assert comparisons["light_gpu_n100_vs_dflash_r1_historical"]["historical_only"] is True


def test_recommendation_passes_only_for_complete_n100_cuda_metadata() -> None:
    good = t100b.summarize_light_gpu_run_from_rows(_complete_gpu_rows(), artifact=Path("run.jsonl"))
    good_recommendation = t100b.build_recommendation(
        run_summary=good,
        task99r_reference={"row_count": 10},
        task96_light_reference={
            "row_count": 30,
            "strict_correct_count": 22,
            "cap_limited_incomplete_count": 5,
            "avg_t_compress_ms": 363.46,
            "avg_e2e_time_s": 3.23,
        },
    )

    incomplete_rows = _complete_gpu_rows()[:99]
    incomplete = t100b.summarize_light_gpu_run_from_rows(incomplete_rows, artifact=Path("run.jsonl"))
    incomplete_recommendation = t100b.build_recommendation(
        run_summary=incomplete,
        task99r_reference={"row_count": 10},
        task96_light_reference={
            "row_count": 30,
            "strict_correct_count": 22,
            "cap_limited_incomplete_count": 5,
            "avg_t_compress_ms": 363.46,
            "avg_e2e_time_s": 3.23,
        },
    )

    assert good_recommendation["decision"] == "PASS_WITH_CAVEAT"
    assert good_recommendation["final_claims_allowed"] is False
    assert incomplete_recommendation["decision"] == "PARTIAL"


def test_no_model_loading_in_task100b_analyzer() -> None:
    source = inspect.getsource(t100b)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
