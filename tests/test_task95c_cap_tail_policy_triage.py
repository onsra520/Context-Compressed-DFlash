from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task95c_cap_tail_policy_triage as t95c


def _row(
    fixture_id: str,
    expected: str,
    generated: str,
    *,
    profile: str,
    max_new_tokens: int,
    output_tokens: int = 20,
    t_compress_ms: float = 10.0,
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
        "expected_answer": expected,
        "generated_text": generated,
        "compressor_profile": profile,
        "max_new_tokens": max_new_tokens,
        "output_tokens": output_tokens,
        "generated_token_count": output_tokens,
        "t_compress_ms": t_compress_ms,
        "R_actual": r_actual,
        "generation_time_s": generation_time_s,
        "tokens_per_second": tokens_per_second,
        "tau_mean": tau_mean,
        "local_files_only": True,
        "compressor_path": f"models/{profile}",
        "resolved_compressor_path": f"/repo/models/{profile}",
        "keep_rate": 0.5,
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_analyzer_compares_four_artifacts_and_writes_outputs(tmp_path: Path) -> None:
    large128 = tmp_path / "large128.jsonl"
    light128 = tmp_path / "light128.jsonl"
    large256 = tmp_path / "large256.jsonl"
    light256 = tmp_path / "light256.jsonl"
    summary_dir = tmp_path / "summary"
    table_dir = tmp_path / "tables"

    _write_jsonl(
        large128,
        [
            _row("a", "1", "Final answer: 1", profile="large", max_new_tokens=128),
            _row("b", "2", "2 +", profile="large", max_new_tokens=128, output_tokens=128),
        ],
    )
    _write_jsonl(
        light128,
        [
            _row("a", "1", "Final answer: 1", profile="light", max_new_tokens=128),
            _row("b", "2", "2 +", profile="light", max_new_tokens=128, output_tokens=128),
        ],
    )
    _write_jsonl(
        large256,
        [
            _row("a", "1", "Final answer: 1", profile="large", max_new_tokens=256),
            _row("b", "2", "Final answer: 2", profile="large", max_new_tokens=256),
        ],
    )
    _write_jsonl(
        light256,
        [
            _row("a", "1", "Final answer: 1", profile="light", max_new_tokens=256),
            _row("b", "2", "Final answer: 2", profile="light", max_new_tokens=256),
        ],
    )

    result = t95c.analyze(large128, light128, large256, light256, summary_dir, table_dir)

    assert result["profiles"]["large_128"]["strict_correct_count"] == 1
    assert result["profiles"]["large_256"]["strict_correct_count"] == 2
    assert result["profiles"]["light_128"]["cap_limited_incomplete_count"] == 1
    assert result["profiles"]["light_256"]["cap_limited_incomplete_count"] == 0
    assert result["comparisons"]["light_128_vs_256"]["strict_correct_delta"] == 1
    assert result["comparisons"]["light_128_vs_256"]["cap_limited_incomplete_delta"] == -1
    assert (summary_dir / "task95c_cap_tail_summary.json").exists()
    assert (summary_dir / "task95c_row_delta_analysis.jsonl").exists()
    assert (summary_dir / "task95c_recommendation.json").exists()
    assert (table_dir / "task95c_cap_tail_table.csv").exists()


def test_recommendation_blocks_n30_and_keep_rate_when_light_quality_remains_weak(tmp_path: Path) -> None:
    summary = {
        "profiles": {
            "large_256": {"strict_correct_count": 4, "row_count": 4, "avg_e2e_time_s": 2.0, "avg_t_compress_ms": 100.0},
            "light_256": {"strict_correct_count": 1, "row_count": 4, "avg_e2e_time_s": 3.5, "avg_t_compress_ms": 50.0},
        },
        "comparisons": {
            "light_128_vs_256": {
                "strict_correct_delta": 0,
                "cap_limited_incomplete_delta": -2,
                "avg_e2e_time_s_delta": 1.5,
            }
        },
    }

    recommendation = t95c.build_recommendation(summary, runs_complete=True, analyzer_complete=True)

    assert recommendation["decision"] == "PASS_WITH_CAVEAT"
    assert recommendation["n30_recommended_now"] is False
    assert recommendation["keep_rate_tuning_in_this_task"] is False
    assert recommendation["next_task"] == "T95D_or_T96_keep_rate_tail_policy_triage"


def test_gpu_blocked_recommendation_is_partial_and_does_not_pass() -> None:
    recommendation = t95c.build_recommendation({}, runs_complete=False, analyzer_complete=False, gpu_blocked=True)

    assert recommendation["decision"] == "PARTIAL"
    assert recommendation["gpu_blocked"] is True
    assert recommendation["n30_recommended_now"] is False


def test_missing_fields_are_handled_safely(tmp_path: Path) -> None:
    path = tmp_path / "minimal.jsonl"
    _write_jsonl(path, [{"fixture_id": "a", "generated_text": "", "expected_answer": "1"}])

    summary = t95c.summarize_artifact(path, profile="large", max_new_tokens_setting=128)

    assert summary["row_count"] == 1
    assert summary["invalid_or_empty_output_count"] == 1
    assert summary["avg_t_compress_ms"] is None
    assert summary["compressor_metadata_sanity"]["rows_missing_compressor_profile"] == 1


def test_no_model_loading_imports() -> None:
    source = inspect.getsource(t95c)

    assert "from transformers" not in source
    assert "import transformers" not in source
    assert "AutoModel" not in source
    assert "torch.cuda" not in source
