from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task95d_bounded_mnt256_confirmation as t95d


def _row(
    fixture_id: str,
    expected: str,
    generated: str,
    *,
    profile: str,
    seed: int,
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
        "max_new_tokens": 256,
        "seed": seed,
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


def test_analyzer_summarizes_independent_confirmation_and_writes_outputs(tmp_path: Path) -> None:
    previous_large = tmp_path / "previous_large.jsonl"
    previous_light = tmp_path / "previous_light.jsonl"
    confirm_large = tmp_path / "confirm_large.jsonl"
    confirm_light = tmp_path / "confirm_light.jsonl"
    output_dir = tmp_path / "task95d"

    _write_jsonl(
        previous_large,
        [
            _row(f"seed42_{index}", str(index), f"Final answer: {index}", profile="large", seed=42)
            for index in range(10)
        ],
    )
    _write_jsonl(
        previous_light,
        [
            _row(f"seed42_{index}", str(index), f"Final answer: {index}", profile="light", seed=42, t_compress_ms=5.0)
            for index in range(10)
        ],
    )
    _write_jsonl(
        confirm_large,
        [
            *[
                _row(f"seed43_pass_{index}", str(index), f"Final answer: {index}", profile="large", seed=43, t_compress_ms=12.0)
                for index in range(9)
            ],
            _row("seed43_cap", "99", "99 +", profile="large", seed=43, output_tokens=256, t_compress_ms=12.0),
        ],
    )
    _write_jsonl(
        confirm_light,
        [
            _row(f"seed43_pass_{index}", str(index), f"Final answer: {index}", profile="light", seed=43, t_compress_ms=4.0)
            for index in range(10)
        ],
    )

    summary = t95d.analyze(previous_large, previous_light, confirm_large, confirm_light, output_dir)

    assert summary["fixture_overlap"]["overlap_count"] == 0
    assert summary["fixture_overlap"]["independent_confirmation_sample"] is True
    assert summary["profiles"]["seed43_large_256"]["strict_correct_count"] == 9
    assert summary["profiles"]["seed43_light_256"]["strict_correct_count"] == 10
    assert summary["profiles"]["seed43_large_256"]["cap_limited_incomplete_count"] == 1
    assert summary["comparisons"]["seed43_large_vs_light_256"]["strict_correct_delta"] == 1
    assert summary["recommendation"]["decision"] == "PASS_WITH_CAVEAT"
    assert summary["recommendation"]["n30_recommended_now"] is True
    assert (output_dir / "summary" / "task95d_bounded_confirmation_summary.json").exists()
    assert (output_dir / "summary" / "task95d_recommendation.json").exists()
    assert (output_dir / "summary" / "task95d_row_labels.jsonl").exists()
    assert (output_dir / "tables" / "task95d_bounded_confirmation_table.csv").exists()


def test_duplicate_sample_is_partial_not_independent_confirmation(tmp_path: Path) -> None:
    previous_large = tmp_path / "previous_large.jsonl"
    previous_light = tmp_path / "previous_light.jsonl"
    confirm_large = tmp_path / "confirm_large.jsonl"
    confirm_light = tmp_path / "confirm_light.jsonl"
    output_dir = tmp_path / "task95d"

    rows_large = [_row("same_a", "1", "Final answer: 1", profile="large", seed=42)]
    rows_light = [_row("same_a", "1", "Final answer: 1", profile="light", seed=42)]
    _write_jsonl(previous_large, rows_large)
    _write_jsonl(previous_light, rows_light)
    _write_jsonl(confirm_large, [_row("same_a", "1", "Final answer: 1", profile="large", seed=43)])
    _write_jsonl(confirm_light, [_row("same_a", "1", "Final answer: 1", profile="light", seed=43)])

    summary = t95d.analyze(previous_large, previous_light, confirm_large, confirm_light, output_dir)

    assert summary["fixture_overlap"]["duplicate_sample"] is True
    assert summary["recommendation"]["decision"] == "PARTIAL"
    assert summary["recommendation"]["reason_code"] == "BLOCKED_DUPLICATE_SAMPLE"
    assert summary["recommendation"]["n30_recommended_now"] is False


def test_regressed_seed43_recommends_tail_or_keep_rate_triage() -> None:
    recommendation = t95d.build_recommendation(
        {
            "fixture_overlap": {"independent_confirmation_sample": True, "duplicate_sample": False},
            "profiles": {
                "seed43_large_256": {"row_count": 10, "strict_correct_count": 8, "cap_limited_incomplete_count": 1},
                "seed43_light_256": {
                    "row_count": 10,
                    "strict_correct_count": 4,
                    "cap_limited_incomplete_count": 5,
                    "avg_e2e_time_s": 3.0,
                },
            },
            "comparisons": {"seed43_large_vs_light_256": {"avg_e2e_time_s_delta": -0.4}},
            "metadata_ok": True,
        }
    )

    assert recommendation["decision"] == "PASS_WITH_CAVEAT"
    assert recommendation["n30_recommended_now"] is False
    assert recommendation["next_task"] == "T95E_or_T96_light_tail_keep_rate_triage"


def test_missing_fields_are_handled_safely(tmp_path: Path) -> None:
    path = tmp_path / "minimal.jsonl"
    _write_jsonl(path, [{"fixture_id": "x", "generated_text": "", "expected_answer": "1"}])

    summary = t95d.summarize_artifact(path, profile="large", seed=43)

    assert summary["row_count"] == 1
    assert summary["invalid_or_empty_output_count"] == 1
    assert summary["avg_t_compress_ms"] is None
    assert summary["metadata_sanity"]["rows_missing_compressor_profile"] == 1


def test_no_model_loading_imports() -> None:
    source = inspect.getsource(t95d)

    assert "from transformers" not in source
    assert "import transformers" not in source
    assert "AutoModel" not in source
    assert "torch.cuda" not in source
