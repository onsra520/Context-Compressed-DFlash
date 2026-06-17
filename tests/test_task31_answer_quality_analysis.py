from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_1_analysis.analyze_task31_answer_quality import (
    ScorerCategory,
    analyze_artifact,
    extract_final_numeric_answer,
    score_row,
    summarize_rows,
)


def _row(**overrides):
    row = {
        "condition": "CC-LLM-R2",
        "expected_answer": "410 dollars",
        "generated_text": "The final answer is 410 dollars.",
        "generated_token_count": 8,
        "output_tokens": 8,
        "generation_time_s": 2.0,
        "tok_per_sec": 4.0,
        "tau_mean": 2.0,
        "t_compress_ms": 500.0,
        "R_actual": 2.0,
    }
    row.update(overrides)
    return row


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_score_row_separates_exact_normalized_no_containment_and_not_evaluable():
    assert score_row(_row()).category is ScorerCategory.EXACT_CONTAINMENT
    assert (
        score_row(_row(generated_text="The final answer is 410   dollars!!!")).category
        is ScorerCategory.NORMALIZED_CONTAINMENT
    )
    assert score_row(_row(generated_text="The final answer is 409 dollars.")).category is ScorerCategory.NO_CONTAINMENT

    missing = _row()
    missing.pop("generated_text")
    assert score_row(missing).category is ScorerCategory.NOT_EVALUABLE


def test_extract_final_numeric_answer_supports_common_final_answer_patterns():
    assert extract_final_numeric_answer("Reasoning...\nFinal answer: 42") == "42"
    assert extract_final_numeric_answer("Answer: -17.5") == "-17.5"
    assert extract_final_numeric_answer("Work shown\n#### 1,234") == "1234"
    assert extract_final_numeric_answer("The count is 12, then 18, so Answer: 30.") == "30"
    assert extract_final_numeric_answer("No numeric answer here.") is None


def test_score_row_matches_extracted_numeric_answer_when_containment_misses():
    score = score_row(_row(expected_answer="410 dollars", generated_text="Reasoning...\nFinal answer: 410"))

    assert score.category is ScorerCategory.NO_CONTAINMENT
    assert score.extracted_answer == "410"
    assert score.extracted_answer_match is True


def test_summarize_rows_computes_counts_rates_and_e2e_time():
    summary = summarize_rows(
        "CC-LLM-R2",
        [
            _row(),
            _row(generated_text="The final answer is 410   dollars!!!", generation_time_s=1.0),
            _row(generated_text="No matching answer.", generation_time_s=3.0),
            _row(generated_text="", generation_time_s=4.0),
        ],
    )

    assert summary["rows"] == 4
    assert summary["generated_text_present"] == 3
    assert summary["exact_containment_count"] == 1
    assert summary["normalized_containment_count"] == 2
    assert summary["normalized_only_count"] == 1
    assert summary["no_containment_count"] == 1
    assert summary["not_evaluable_count"] == 1
    assert summary["extracted_answer_match_count"] == 2
    assert summary["extracted_answer_match_rate"] == 0.5
    assert summary["exact_rate"] == 0.25
    assert summary["normalized_rate"] == 0.5
    assert summary["avg_generated_token_count"] == 8.0
    assert summary["avg_output_tokens"] == 8.0
    assert summary["avg_e2e_time_s"] == 3.0
    assert summary["avg_tok_per_sec"] == 4.0
    assert summary["avg_tau_mean"] == 2.0
    assert summary["avg_r_actual"] == 2.0


def test_analyze_artifact_reads_rows_and_exports_row_scores(tmp_path: Path):
    path = tmp_path / "artifact.jsonl"
    _write_jsonl(path, [_row(), _row(generated_text="No matching answer.")])

    analysis = analyze_artifact(path)

    assert analysis["summary"]["condition"] == "CC-LLM-R2"
    assert analysis["summary"]["rows"] == 2
    assert [row["score_category"] for row in analysis["rows"]] == [
        "EXACT_CONTAINMENT",
        "NO_CONTAINMENT",
    ]
