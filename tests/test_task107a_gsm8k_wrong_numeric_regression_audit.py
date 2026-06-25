from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task107a_gsm8k_wrong_numeric_regression_audit as t107a


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _row(
    fixture_id: str,
    generated_text: str,
    expected: str = "42",
    *,
    condition: str = "CC-DFlash-R2",
    output_tokens: int = 80,
    max_new_tokens: int = 256,
    compressed_preview: str = "question detail 42",
) -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "condition": condition,
        "dataset_name": "gsm8k_short",
        "expected_answer": expected,
        "generated_text": generated_text,
        "output_tokens": output_tokens,
        "generated_token_count": output_tokens,
        "max_new_tokens": max_new_tokens,
        "compressed_prompt_preview": compressed_preview,
        "final_prompt_preview": compressed_preview,
        "t_compress_ms": 17.0,
        "R_actual": 2.0,
    }


def test_analyzer_writes_outputs_and_detects_wrong_numeric_overlap(tmp_path: Path) -> None:
    before = tmp_path / "before.jsonl"
    fixed = tmp_path / "fixed.jsonl"
    baseline = tmp_path / "baseline.jsonl"
    dflash = tmp_path / "dflash.jsonl"
    out = tmp_path / "out"

    _write_jsonl(
        before,
        [
            _row("same_wrong", "Work. Final answer: 41"),
            _row("new_wrong_from_cap", "Long reasoning without final answer " * 30, output_tokens=256),
            _row("fixed_wrong", "Bad. Final answer: 40"),
            _row("correct", "Work. Final answer: 42"),
        ],
    )
    _write_jsonl(
        fixed,
        [
            _row("same_wrong", "Work. Final answer: 41"),
            _row("new_wrong_from_cap", "Too short. Final answer: 41", output_tokens=40),
            _row("fixed_wrong", "Corrected. Final answer: 42"),
            _row("correct", "Work. Final answer: 42"),
        ],
    )
    _write_jsonl(
        baseline,
        [
            _row("same_wrong", "Work. Final answer: 41", condition="Baseline-AR"),
            _row("new_wrong_from_cap", "Work. Final answer: 42", condition="Baseline-AR"),
            _row("fixed_wrong", "Work. Final answer: 42", condition="Baseline-AR"),
            _row("correct", "Work. Final answer: 42", condition="Baseline-AR"),
        ],
    )
    _write_jsonl(
        dflash,
        [
            _row("same_wrong", "Work. Final answer: 41", condition="DFlash-R1"),
            _row("new_wrong_from_cap", "Work. Final answer: 42", condition="DFlash-R1"),
            _row("fixed_wrong", "Work. Final answer: 42", condition="DFlash-R1"),
            _row("correct", "Work. Final answer: 42", condition="DFlash-R1"),
        ],
    )

    result = t107a.analyze(
        before_jsonl=before,
        fixed_jsonl=fixed,
        baseline_jsonl=baseline,
        dflash_jsonl=dflash,
        output_dir=out,
    )

    overlap = result["wrong_numeric_fixture_overlap"]
    assert overlap["before_wrong_numeric_count"] == 2
    assert overlap["fixed_wrong_numeric_count"] == 2
    assert overlap["wrong_in_both_count"] == 1
    assert overlap["newly_wrong_after_t106b_count"] == 1
    assert overlap["fixed_wrong_from_t105a_count"] == 1
    assert overlap["wrong_shared_with_baseline_count"] == 1
    assert overlap["cc_only_wrong_after_t106b_count"] == 1
    assert result["next_task_decision"]["next_task"].startswith("T107B")
    for relative in t107a.OUTPUT_RELATIVE_PATHS:
        assert (out / relative).exists()


def test_row_attribution_marks_resolved_cap_but_wrong_number(tmp_path: Path) -> None:
    before = tmp_path / "before.jsonl"
    fixed = tmp_path / "fixed.jsonl"
    baseline = tmp_path / "baseline.jsonl"
    dflash = tmp_path / "dflash.jsonl"
    out = tmp_path / "out"
    _write_jsonl(before, [_row("cap_to_wrong", "Verbose no marker " * 40, output_tokens=256)])
    _write_jsonl(fixed, [_row("cap_to_wrong", "Compressed. Final answer: 41", output_tokens=32)])
    _write_jsonl(baseline, [_row("cap_to_wrong", "Check. Final answer: 42", condition="Baseline-AR")])
    _write_jsonl(dflash, [_row("cap_to_wrong", "Check. Final answer: 42", condition="DFlash-R1")])

    result = t107a.analyze(
        before_jsonl=before,
        fixed_jsonl=fixed,
        baseline_jsonl=baseline,
        dflash_jsonl=dflash,
        output_dir=out,
    )
    row = result["row_audit"][0]

    assert row["fixture_id"] == "cap_to_wrong"
    assert row["primary_attribution"] == "resolved_cap_but_wrong_number"
    assert "answer_changed_after_cap_fix" in row["attribution_tags"]
    assert row["before_label"] == "cap_limited_incomplete"
    assert row["fixed_label"] == "strict_wrong_numeric"


def test_reference_shared_wrong_suppresses_t107b_recommendation(tmp_path: Path) -> None:
    before = tmp_path / "before.jsonl"
    fixed = tmp_path / "fixed.jsonl"
    baseline = tmp_path / "baseline.jsonl"
    dflash = tmp_path / "dflash.jsonl"
    out = tmp_path / "out"
    rows = [_row(f"shared_{i}", "Work. Final answer: 41") for i in range(3)]
    _write_jsonl(before, rows)
    _write_jsonl(fixed, rows)
    _write_jsonl(baseline, [_row(f"shared_{i}", "Work. Final answer: 41", condition="Baseline-AR") for i in range(3)])
    _write_jsonl(dflash, [_row(f"shared_{i}", "Work. Final answer: 41", condition="DFlash-R1") for i in range(3)])

    result = t107a.analyze(
        before_jsonl=before,
        fixed_jsonl=fixed,
        baseline_jsonl=baseline,
        dflash_jsonl=dflash,
        output_dir=out,
    )

    assert result["next_task_decision"]["t107b_recommended"] is False
    assert result["next_task_decision"]["reason"] == "wrong_numeric_mostly_shared_with_references"


def test_extractor_or_format_issue_recommends_extractor_audit(tmp_path: Path) -> None:
    before = tmp_path / "before.jsonl"
    fixed = tmp_path / "fixed.jsonl"
    baseline = tmp_path / "baseline.jsonl"
    dflash = tmp_path / "dflash.jsonl"
    out = tmp_path / "out"
    _write_jsonl(before, [_row("formatish", "Work. Final answer: 42")])
    _write_jsonl(fixed, [_row("formatish", "The correct result is 42, but I will output. Final answer: 41")])
    _write_jsonl(baseline, [_row("formatish", "Work. Final answer: 42", condition="Baseline-AR")])
    _write_jsonl(dflash, [_row("formatish", "Work. Final answer: 42", condition="DFlash-R1")])

    result = t107a.analyze(
        before_jsonl=before,
        fixed_jsonl=fixed,
        baseline_jsonl=baseline,
        dflash_jsonl=dflash,
        output_dir=out,
    )

    row = result["row_audit"][0]
    assert row["primary_attribution"] == "expected_answer_appears_but_final_wrong"
    assert result["next_task_decision"]["recommended_fix_type"] == "extractor_or_policy_audit"


def test_task107a_analyzer_does_not_import_model_or_cuda_libraries() -> None:
    source = inspect.getsource(t107a)

    assert "import torch" not in source
    assert "from torch" not in source
    assert "transformers" not in source
    assert "AutoModel" not in source
