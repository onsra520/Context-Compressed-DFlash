from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task95b_quality_proxy_calibration as t95b


def _row(
    fixture_id: str,
    expected: str,
    generated: str,
    *,
    profile: str = "large",
    output_tokens: int = 20,
    max_new_tokens: int = 128,
    prompt_id: int = 1,
) -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "prompt_id": prompt_id,
        "expected_answer": expected,
        "generated_text": generated,
        "compressor_profile": profile,
        "output_tokens": output_tokens,
        "max_new_tokens": max_new_tokens,
        "output_path": f"runs/{profile}.jsonl",
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_strict_correct_with_final_answer_marker() -> None:
    label = t95b.calibrate_row(_row("a", "12", "Work shown.\nFinal answer: 12"), profile="large", row_index=1)

    assert label["calibrated_label"] == "strict_correct"
    assert label["strict_correct"] is True
    assert label["strict_extracted_answer"] == "12"
    assert label["final_answer_marker_present"] is True


def test_wrong_numeric_final_answer_stays_wrong() -> None:
    label = t95b.calibrate_row(_row("a", "12", "Work shown.\nFinal answer: 10"), profile="large", row_index=1)

    assert label["calibrated_label"] == "strict_wrong_numeric"
    assert label["strict_correct"] is False
    assert label["strict_extracted_answer"] == "10"


def test_cap_limited_incomplete_output_is_not_rescued_by_fallback_number() -> None:
    label = t95b.calibrate_row(
        _row("a", "5", "35 divided by 7 =", profile="light", output_tokens=128, max_new_tokens=128),
        profile="light",
        row_index=1,
    )

    assert label["calibrated_label"] == "cap_limited_incomplete"
    assert label["cap_limited"] is True
    assert label["strict_correct"] is False


def test_exact_containment_does_not_automatically_count_as_correct() -> None:
    label = t95b.calibrate_row(
        _row("a", "5", "The number 5 appears in setup.\nFinal answer: 7"),
        profile="large",
        row_index=1,
    )

    assert label["exact_containment"] is True
    assert label["calibrated_label"] == "strict_wrong_numeric"
    assert label["strict_correct"] is False


def test_format_or_extraction_sensitive_case_is_flagged_separately() -> None:
    label = t95b.calibrate_row(
        _row("a", "5", "The daily requirement is 5 pounds per day. The week has 7 days."),
        profile="light",
        row_index=1,
    )

    assert label["exact_containment"] is True
    assert label["strict_extracted_answer"] == "7"
    assert label["calibrated_label"] == "format_or_extraction_sensitive"
    assert label["strict_correct"] is False


def test_pairing_prefers_fixture_id() -> None:
    large = [_row("a", "1", "Final answer: 1"), _row("b", "2", "Final answer: 2")]
    light = [
        _row("b", "2", "Final answer: 2", profile="light"),
        _row("a", "1", "Final answer: 1", profile="light"),
    ]

    paired = t95b.pair_rows(large, light)

    assert paired["pairing_method"] == "fixture_id"
    assert [pair["pair_id"] for pair in paired["pairs"]] == ["a", "b"]


def test_analyze_writes_summary_and_recommends_t95c_when_gap_remains(tmp_path: Path) -> None:
    large_path = tmp_path / "large.jsonl"
    light_path = tmp_path / "light.jsonl"
    output_dir = tmp_path / "out"
    _write_jsonl(
        large_path,
        [
            _row("a", "1", "Final answer: 1", profile="large"),
            _row("b", "2", "Final answer: 2", profile="large"),
        ],
    )
    _write_jsonl(
        light_path,
        [
            _row("a", "1", "Final answer: 1", profile="light"),
            _row("b", "2", "2 + 2 =", profile="light", output_tokens=128, max_new_tokens=128),
        ],
    )

    summary = t95b.analyze(large_path, light_path, None, output_dir)

    assert summary["profiles"]["large"]["strict_correct_count"] == 2
    assert summary["profiles"]["light"]["strict_correct_count"] == 1
    assert summary["profiles"]["light"]["calibrated_label_counts"]["cap_limited_incomplete"] == 1
    recommendation = json.loads((output_dir / "task95b_recommendation.json").read_text(encoding="utf-8"))
    assert recommendation["decision"] == "A"
    assert recommendation["next_task"] == "T95C"


def test_no_model_loading_imports() -> None:
    source = inspect.getsource(t95b)

    assert "from transformers" not in source
    assert "import transformers" not in source
    assert "AutoModel" not in source
    assert "torch.cuda" not in source
