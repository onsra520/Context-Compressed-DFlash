from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_1_system_build_and_evaluation.analysis.t62_changed_outcome_triage import analyze_paths


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _row(
    *,
    condition: str,
    dataset_id: str,
    expected_answer: str,
    generated_text: str,
    extracted_answer: str,
    output_tokens: int,
    max_new_tokens: int,
    compressed_preview: str,
    compressed_input_tokens: int,
    keep_rate: float,
) -> dict:
    return {
        "condition": condition,
        "prompt_id": 1,
        "benchmark_prompt_index": 1,
        "dataset_id": dataset_id,
        "fixture_id": dataset_id,
        "expected_answer": expected_answer,
        "generated_text": generated_text,
        "output_tokens": output_tokens,
        "max_new_tokens": max_new_tokens,
        "original_input_tokens": 100,
        "compressed_input_tokens": compressed_input_tokens,
        "actual_compression_ratio": 100 / compressed_input_tokens,
        "compression_ratio": 100 / compressed_input_tokens,
        "keep_rate": keep_rate,
        "protected_suffix_preserved": True,
        "question_preserved": True,
        "final_prompt_tail_preview": "Question text. End with exactly one line: Final answer: <number>",
        "compressed_prompt_preview": compressed_preview,
        "final_prompt_preview": compressed_preview,
        "extracted_answer": extracted_answer,
    }


def test_analyze_paths_labels_changed_outcomes(tmp_path: Path):
    before = tmp_path / "task60.jsonl"
    after = tmp_path / "task61b.jsonl"
    changed = tmp_path / "changed.jsonl"

    _write_jsonl(
        before,
        [
            _row(
                condition="LLMLingua-AR-R2",
                dataset_id="case_helped",
                expected_answer="42",
                generated_text="Final answer: 7",
                extracted_answer="7",
                output_tokens=40,
                max_new_tokens=256,
                compressed_preview="Question without the critical relation",
                compressed_input_tokens=50,
                keep_rate=0.5,
            ),
            _row(
                condition="LLMLingua-AR-R2",
                dataset_id="case_truncated",
                expected_answer="6",
                generated_text="Working through the arithmetic",
                extracted_answer="2",
                output_tokens=256,
                max_new_tokens=256,
                compressed_preview="All critical numbers appear",
                compressed_input_tokens=50,
                keep_rate=0.5,
            ),
        ],
    )
    _write_jsonl(
        after,
        [
            _row(
                condition="LLMLingua-AR-R2",
                dataset_id="case_helped",
                expected_answer="42",
                generated_text="Final answer: 42",
                extracted_answer="42",
                output_tokens=38,
                max_new_tokens=256,
                compressed_preview="Question includes critical 42 relation",
                compressed_input_tokens=67,
                keep_rate=0.67,
            ),
            _row(
                condition="LLMLingua-AR-R2",
                dataset_id="case_truncated",
                expected_answer="6",
                generated_text="Still working through the arithmetic",
                extracted_answer="300",
                output_tokens=256,
                max_new_tokens=256,
                compressed_preview="All critical numbers appear",
                compressed_input_tokens=67,
                keep_rate=0.67,
            ),
        ],
    )
    _write_jsonl(
        changed,
        [
            {
                "condition": "LLMLingua-AR-R2",
                "dataset_id": "case_helped",
                "prompt_key": "case_helped",
                "outcome_label": "FAIL_TO_PASS",
            },
            {
                "condition": "LLMLingua-AR-R2",
                "dataset_id": "case_truncated",
                "prompt_key": "case_truncated",
                "outcome_label": "SAME_FAIL",
            },
        ],
    )

    summary, cases = analyze_paths(
        task60_paths={"LLMLingua-AR-R2": before},
        task61b_paths={"LLMLingua-AR-R2": after},
        changed_outcomes_path=changed,
    )

    assert summary["total_cases"] == 2
    assert summary["label_counts"] == {
        "K67_HELPED_COMPRESSION_LOSS": 1,
        "TRUNCATION_REMAINING": 1,
    }
    assert cases[0]["triage_label"] == "K67_HELPED_COMPRESSION_LOSS"
    assert cases[0]["k67_restored_expected_answer_in_preview"] is True
    assert cases[1]["triage_label"] == "TRUNCATION_REMAINING"
