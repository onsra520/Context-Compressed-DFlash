from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis.task95a_analysis_and_failure_row_audit import (
    analyze,
    build_recommendation,
    pair_rows,
)


def _row(
    sample_id: str,
    expected: str,
    generated: str,
    *,
    prompt_id: int = 1,
    profile: str = "large",
    output_tokens: int = 12,
    max_new_tokens: int = 128,
) -> dict[str, object]:
    return {
        "fixture_id": sample_id,
        "dataset_id": sample_id,
        "prompt_id": prompt_id,
        "expected_answer": expected,
        "generated_text": generated,
        "compressor_profile": profile,
        "t_compress_ms": 10.0 if profile == "large" else 5.0,
        "R_actual": 2.5 if profile == "large" else 2.0,
        "tau_mean": 6.0 if profile == "large" else 5.0,
        "output_tokens": output_tokens,
        "max_new_tokens": max_new_tokens,
        "compressed_prompt_preview": "compressed preview with question facts",
        "final_prompt_tail_preview": "End with exactly one line: Final answer: <number>",
        "protected_suffix_preserved": True,
        "question_preserved": True,
        "local_files_only": True,
        "compressor_path": f"models/{profile}",
        "resolved_compressor_path": f"models/{profile}",
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_pair_rows_prefers_shared_id() -> None:
    large = [_row("a", "1", "Final answer: 1"), _row("b", "2", "Final answer: 2")]
    light = [_row("b", "2", "Final answer: 2", profile="light"), _row("a", "1", "Final answer: 1", profile="light")]

    paired = pair_rows(large, light)

    assert paired["pairing_method"] == "fixture_id"
    assert [pair["sample_id"] for pair in paired["pairs"]] == ["a", "b"]


def test_pair_rows_falls_back_to_order_without_shared_key() -> None:
    large = [{"expected_answer": "1", "generated_text": "Final answer: 1"}]
    light = [{"expected_answer": "1", "generated_text": "Final answer: 1"}]

    paired = pair_rows(large, light)

    assert paired["pairing_method"] == "row_order"
    assert paired["caveats"]


def test_analyze_groups_correctness_patterns(tmp_path: Path) -> None:
    large_path = tmp_path / "large.jsonl"
    light_path = tmp_path / "light.jsonl"
    _write_jsonl(
        large_path,
        [
            _row("both", "4", "Final answer: 4", prompt_id=1),
            _row("large_only", "5", "Final answer: 5", prompt_id=2),
            _row("both_wrong", "6", "Final answer: 7", prompt_id=3),
        ],
    )
    _write_jsonl(
        light_path,
        [
            _row("both", "4", "Final answer: 4", prompt_id=1, profile="light"),
            _row("large_only", "5", "Final answer: 9", prompt_id=2, profile="light"),
            _row("both_wrong", "6", "Final answer: 8", prompt_id=3, profile="light"),
        ],
    )

    summary = analyze(large_path, light_path, tmp_path / "out")

    assert summary["outcome_group_counts"] == {
        "both_correct": 1,
        "large_correct_light_wrong": 1,
        "large_wrong_light_correct": 0,
        "both_wrong": 1,
        "proxy_uncertain": 0,
    }
    assert summary["failure_taxonomy_counts"]["arithmetic_wrong"] == 1


def test_missing_fields_are_safe_and_proxy_uncertain(tmp_path: Path) -> None:
    large_path = tmp_path / "large.jsonl"
    light_path = tmp_path / "light.jsonl"
    _write_jsonl(large_path, [{"fixture_id": "x", "generated_text": "Final answer: 4"}])
    _write_jsonl(light_path, [{"fixture_id": "x", "generated_text": ""}])

    summary = analyze(large_path, light_path, tmp_path / "out")

    assert summary["outcome_group_counts"]["proxy_uncertain"] == 1
    assert "expected_answer" in summary["missing_metadata"]["large"]


def test_recommendation_prefers_t95b_for_proxy_uncertainty() -> None:
    recommendation = build_recommendation(
        outcome_group_counts={"proxy_uncertain": 1, "large_correct_light_wrong": 1},
        failure_taxonomy_counts={"format_or_extraction_issue": 1},
        has_compressed_prompt_text=False,
    )

    assert recommendation["next_task"] == "T95B"


def test_recommendation_uses_t95c_when_quality_loss_looks_real() -> None:
    recommendation = build_recommendation(
        outcome_group_counts={"proxy_uncertain": 0, "large_correct_light_wrong": 2},
        failure_taxonomy_counts={"arithmetic_wrong": 2},
        has_compressed_prompt_text=True,
    )

    assert recommendation["next_task"] == "T95C"
    assert "tuning" in recommendation["rationale"].lower()
