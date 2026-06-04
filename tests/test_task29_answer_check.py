from __future__ import annotations

import json
from pathlib import Path

from scripts.check_task29_answers import check_artifact, normalize_text


def _base_row(**overrides):
    row = {
        "condition": "CC-LLM-R2",
        "prompt_source": "fixture",
        "fixture_id": "case_a",
        "domain": "finance",
        "expected_answer": "410 dollars",
        "evidence": "The paid amount was 410 dollars.",
        "approximate_context_words": 130,
        "question_preserved": True,
        "generated_text": "The answer is 410 dollars.",
    }
    row.update(overrides)
    return row


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_normalize_text_lowercases_collapses_spaces_and_strips_punctuation():
    assert normalize_text("  Hello,   WORLD! ") == "hello world"


def test_check_artifact_counts_exact_and_normalized_matches(tmp_path: Path):
    path = tmp_path / "matches.jsonl"
    _write_jsonl(
        path,
        [
            _base_row(generated_text="410 dollars"),
            _base_row(generated_text="The answer is 410   dollars!!!"),
        ],
    )

    result = check_artifact(path)

    assert result.status == "PASS"
    assert result.rows == 2
    assert result.exact_matches == 1
    assert result.normalized_matches == 2


def test_missing_generated_text_warns_not_fails(tmp_path: Path):
    path = tmp_path / "missing_text.jsonl"
    row = _base_row()
    row.pop("generated_text")
    _write_jsonl(path, [row])

    result = check_artifact(path)

    assert result.status == "WARN"
    assert result.generated_text_missing == 1
    assert any(issue.level == "WARN" and "generated text" in issue.message for issue in result.issues)


def test_missing_fixture_metadata_fails(tmp_path: Path):
    path = tmp_path / "missing_metadata.jsonl"
    row = _base_row()
    row.pop("fixture_id")
    _write_jsonl(path, [row])

    result = check_artifact(path)

    assert result.status == "FAIL"
    assert any(issue.level == "FAIL" and "fixture_id" in issue.message for issue in result.issues)


def test_compressed_row_with_question_not_preserved_fails(tmp_path: Path):
    path = tmp_path / "bad_question.jsonl"
    _write_jsonl(path, [_base_row(question_preserved=False)])

    result = check_artifact(path)

    assert result.status == "FAIL"
    assert any("question_preserved" in issue.message for issue in result.issues)
