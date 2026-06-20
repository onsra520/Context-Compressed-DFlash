from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task96_n30_controlled_mnt256_comparison as t96


def _row(
    fixture_id: str,
    expected: str,
    generated: str,
    *,
    profile: str,
    output_tokens: int = 20,
    t_compress_ms: float = 100.0,
    r_actual: float = 2.0,
    generation_time_s: float = 1.0,
    tokens_per_second: float = 20.0,
    tau_mean: float = 5.0,
) -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "prompt_id": 1,
        "condition": "CC-DFlash-R2",
        "prompt_source": "dataset",
        "dataset_name": "gsm8k_short",
        "expected_answer": expected,
        "generated_text": generated,
        "compressor_profile": profile,
        "max_new_tokens": 256,
        "output_tokens": output_tokens,
        "generated_token_count": output_tokens,
        "t_compress_ms": t_compress_ms,
        "R_actual": r_actual,
        "generation_time_s": generation_time_s,
        "tokens_per_second": tokens_per_second,
        "tau_mean": tau_mean,
        "t_prefill_ms": 25.0,
        "local_files_only": True,
        "compressor_path": f"models/{profile}",
        "resolved_compressor_path": f"/repo/models/{profile}",
        "keep_rate": 0.5,
        "vram_allocated_gib": 3.5,
        "vram_reserved_gib": 3.8,
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_analyzer_writes_task96_outputs_and_passes_bounded_policy(tmp_path: Path) -> None:
    large = tmp_path / "large.jsonl"
    light = tmp_path / "light.jsonl"
    output_dir = tmp_path / "task96"

    _write_jsonl(
        large,
        [
            *[
                _row(f"item_{index}", str(index), f"Reasoning\nFinal answer: {index}", profile="large")
                for index in range(28)
            ],
            _row("large_wrong", "99", "Reasoning\nFinal answer: 98", profile="large"),
            _row("large_cap", "100", "This unfinished response keeps going +", profile="large", output_tokens=256),
        ],
    )
    _write_jsonl(
        light,
        [
            *[
                _row(
                    f"item_{index}",
                    str(index),
                    f"Reasoning\nFinal answer: {index}",
                    profile="light",
                    t_compress_ms=30.0,
                    generation_time_s=0.9,
                    tokens_per_second=22.0,
                )
                for index in range(27)
            ],
            _row("light_wrong", "99", "Reasoning\nFinal answer: 98", profile="light", t_compress_ms=30.0),
            _row("light_cap", "100", "This unfinished response keeps going +", profile="light", output_tokens=256, t_compress_ms=30.0),
            _row("light_cap_2", "101", "Still calculating +", profile="light", output_tokens=256, t_compress_ms=30.0),
        ],
    )

    summary = t96.analyze(large, light, output_dir)

    assert summary["profiles"]["seed42_large_n30_mnt256"]["row_count"] == 30
    assert summary["profiles"]["seed42_light_n30_mnt256"]["row_count"] == 30
    assert summary["profiles"]["seed42_large_n30_mnt256"]["strict_correct_count"] == 28
    assert summary["profiles"]["seed42_light_n30_mnt256"]["strict_correct_count"] == 27
    assert summary["profiles"]["seed42_light_n30_mnt256"]["cap_limited_incomplete_count"] == 2
    assert summary["comparisons"]["light_vs_large"]["strict_correct_delta"] == -1
    assert summary["comparisons"]["light_vs_large"]["cap_limited_incomplete_delta"] == 1
    assert summary["comparisons"]["light_vs_large"]["avg_t_compress_ms_delta"] == -70.0
    assert summary["recommendation"]["decision"] == "PASS_WITH_CAVEAT"
    assert summary["recommendation"]["next_task"] == "T97_packaging_controlled_evidence_summary"
    assert summary["method"]["n100_run"] is False
    assert (output_dir / "summary" / "task96_n30_controlled_summary.json").exists()
    assert (output_dir / "summary" / "task96_recommendation.json").exists()
    assert (output_dir / "summary" / "task96_row_labels.jsonl").exists()
    assert (output_dir / "tables" / "task96_n30_controlled_table.csv").exists()


def test_metadata_failures_are_fail_not_interpretable(tmp_path: Path) -> None:
    large = tmp_path / "large.jsonl"
    light = tmp_path / "light.jsonl"

    _write_jsonl(large, [_row("a", "1", "Final answer: 1", profile="large") for _ in range(30)])
    bad_light = [_row("b", "1", "Final answer: 1", profile="light") for _ in range(30)]
    bad_light[0]["max_new_tokens"] = 1024
    _write_jsonl(light, bad_light)

    summary = t96.analyze(large, light, tmp_path / "out")

    assert summary["metadata_ok"] is False
    assert summary["recommendation"]["decision"] == "FAIL"
    assert summary["recommendation"]["reason_code"] == "METADATA_FAILED"


def test_quality_regression_is_partial() -> None:
    recommendation = t96.build_recommendation(
        {
            "metadata_ok": True,
            "profiles": {
                "seed42_large_n30_mnt256": {
                    "row_count": 30,
                    "strict_correct_count": 28,
                    "cap_limited_incomplete_count": 1,
                    "avg_t_compress_ms": 100.0,
                },
                "seed42_light_n30_mnt256": {
                    "row_count": 30,
                    "strict_correct_count": 24,
                    "cap_limited_incomplete_count": 5,
                    "avg_t_compress_ms": 30.0,
                },
            },
            "comparisons": {"light_vs_large": {"avg_t_compress_ms_delta": -70.0}},
        }
    )

    assert recommendation["decision"] == "PARTIAL"
    assert recommendation["reason_code"] == "LIGHT_QUALITY_REGRESSION"
    assert recommendation["next_task"] == "T96A_light_tail_policy_triage_before_scaling"


def test_no_model_loading_imports() -> None:
    source = inspect.getsource(t96)

    assert "from transformers" not in source
    assert "import transformers" not in source
    assert "AutoModel" not in source
    assert "torch.cuda" not in source
