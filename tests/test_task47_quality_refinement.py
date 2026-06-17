from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_1_analysis.analyze_task47_quality_refinement import (
    analyze_task47,
    classify_row,
    extract_numeric_answer,
    normalize_numeric,
    summarize_classifications,
    write_summary,
)


def _row(condition: str = "Baseline-AR", **overrides):
    row = {
        "condition": condition,
        "prompt_id": 1,
        "expected_answer": "42",
        "generated_text": "Reasoning. Final answer: 42",
        "output_tokens": 20,
        "max_new_tokens": 128,
    }
    row.update(overrides)
    return row


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _quality_summary(path: Path) -> dict:
    return {
        "path": str(path),
        "status": "PASS",
        "quality": {},
    }


def test_normalize_numeric_handles_currency_commas_decimals_and_signs():
    assert normalize_numeric("$1,230.00") == "1230"
    assert normalize_numeric("+42") == "42"
    assert normalize_numeric("-17.50") == "-17.5"
    assert normalize_numeric("answer is 0.0") == "0"
    assert normalize_numeric("no number") is None


def test_extract_numeric_answer_prefers_final_markers():
    extraction = extract_numeric_answer("We saw 10 and 20. Final answer: $1,234.00")

    assert extraction.answer == "1234"
    assert extraction.source == "marked_final_answer"
    assert extraction.ambiguous is False


def test_extract_numeric_answer_prefers_final_answer_over_gsm8k_marker():
    extraction = extract_numeric_answer("Work says #### 41\nCorrection. Final answer: 42")

    assert extraction.answer == "42"
    assert extraction.source == "marked_final_answer"


def test_extract_numeric_answer_supports_gsm8k_marker_and_ambiguous_markers():
    assert extract_numeric_answer("Work\n#### -12").answer == "-12"
    extraction = extract_numeric_answer("Answer: 5. Later correction: final answer: 6")

    assert extraction.answer == "6"
    assert extraction.ambiguous is True
    assert extraction.candidates == ["5", "6"]


def test_classify_row_no_answer_and_truncated_cases():
    no_answer = classify_row(
        _row(generated_text="There is no numeric final answer here."),
        row_index=1,
        condition="Baseline-AR",
        artifact="artifact.jsonl",
    )
    truncated = classify_row(
        _row(generated_text="We start reasoning but never finish", output_tokens=128, max_new_tokens=128),
        row_index=2,
        condition="Baseline-AR",
        artifact="artifact.jsonl",
    )

    assert no_answer["failure_type"] == "no_final_answer_found"
    assert truncated["failure_type"] == "truncated_or_stopped_early"


def test_classify_row_exact_numeric_wrong_and_ambiguous():
    exact = classify_row(_row(expected_answer="42", generated_text="The answer is exactly 42."), row_index=1, condition="Baseline-AR", artifact="a")
    numeric = classify_row(_row(expected_answer="42 dollars", generated_text="Final answer: $42"), row_index=2, condition="Baseline-AR", artifact="a")
    wrong = classify_row(_row(expected_answer="42", generated_text="Final answer: 41"), row_index=3, condition="Baseline-AR", artifact="a")
    ambiguous = classify_row(_row(expected_answer="42", generated_text="Answer: 41. Final answer: 42"), row_index=4, condition="Baseline-AR", artifact="a")

    assert exact["failure_type"] == "exact_match"
    assert numeric["failure_type"] == "numeric_match"
    assert wrong["failure_type"] == "extracted_but_wrong"
    assert ambiguous["failure_type"] == "parse_ambiguous"


def test_summarize_classifications_counts_rates_without_division_by_zero():
    assert summarize_classifications([])["numeric_match_rate"] == 0.0
    rows = [
        classify_row(_row(expected_answer="42", generated_text="42"), row_index=1, condition="Baseline-AR", artifact="a"),
        classify_row(_row(expected_answer="42", generated_text="Final answer: 42"), row_index=2, condition="Baseline-AR", artifact="a"),
        classify_row(_row(expected_answer="42", generated_text="Final answer: 41"), row_index=3, condition="Baseline-AR", artifact="a"),
    ]
    summary = summarize_classifications(rows)

    assert summary["rows"] == 3
    assert summary["exact_match_count"] == 2
    assert summary["numeric_match_count"] == 2
    assert summary["extracted_but_wrong_count"] == 1
    assert summary["numeric_match_rate"] == 2 / 3


def test_analyze_task47_reads_temporary_artifacts(tmp_path: Path):
    paths = {
        "Baseline-AR": tmp_path / "baseline.jsonl",
        "DFlash-R1": tmp_path / "dflash.jsonl",
        "LLMLingua-AR-R2": tmp_path / "ar.jsonl",
        "CC-LLM-R2": tmp_path / "cc.jsonl",
    }
    _write_jsonl(paths["Baseline-AR"], [_row("Baseline-AR"), _row("Baseline-AR", generated_text="Final answer: 41")])
    _write_jsonl(paths["DFlash-R1"], [_row("DFlash-R1"), _row("DFlash-R1", generated_text="no number")])
    _write_jsonl(paths["LLMLingua-AR-R2"], [_row("LLMLingua-AR-R2"), _row("LLMLingua-AR-R2", generated_text="Final answer: 41")])
    _write_jsonl(paths["CC-LLM-R2"], [_row("CC-LLM-R2"), _row("CC-LLM-R2", generated_text="Answer: 5. Final answer: 42")])
    audit = {
        "status": "PASS",
        "artifacts": {condition: _quality_summary(path) for condition, path in paths.items()},
    }
    pareto = {"status": "PASS"}
    audit_path = tmp_path / "audit.json"
    pareto_path = tmp_path / "pareto.json"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    pareto_path.write_text(json.dumps(pareto), encoding="utf-8")

    summary = analyze_task47(audit_path=audit_path, pareto_path=pareto_path, fixture_path=None)

    assert summary["status"] == "PASS"
    assert set(summary["conditions"]) == set(paths)
    assert summary["conditions"]["Baseline-AR"]["rows"] == 2
    assert summary["conditions"]["CC-LLM-R2"]["ambiguous_count"] == 1
    assert "claim_policy" in summary

    output = tmp_path / "summary.json"
    write_summary(summary, output)
    assert json.loads(output.read_text())["status"] == "PASS"
