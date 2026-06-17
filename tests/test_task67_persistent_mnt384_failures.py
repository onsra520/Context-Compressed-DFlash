from scripts.phase_1_system_build_and_evaluation.analysis.t67_persistent_mnt384_failures import (
    label_failure_case,
    summarize_condition_rows,
)


def _row(**overrides):
    row = {
        "condition": "LLMLingua-AR-R2",
        "prompt_id": 1,
        "dataset_id": "gsm8k_test_1",
        "expected_answer": "42",
        "generated_text": "We calculate carefully. Final answer: 41",
        "output_tokens": 120,
        "max_new_tokens": 384,
        "protected_suffix_preserved": True,
        "question_preserved": True,
        "final_prompt_tail_preview": "End with exactly one line:\nFinal answer: <number>",
        "compressed_prompt_preview": "Question: How many are left?",
    }
    row.update(overrides)
    return row


def test_labels_cap_hit_unfinished_as_remaining_truncation():
    label, rationale = label_failure_case(
        _row(
            generated_text="We need to solve this step by step. First,",
            output_tokens=384,
        ),
        numeric_match=False,
        extracted_answer=None,
        expected_answer="42",
    )

    assert label == "TRUNCATION_REMAINING"
    assert "cap" in rationale.lower()


def test_labels_completed_wrong_final_answer_as_reasoning_fail():
    label, _ = label_failure_case(
        _row(generated_text="Final answer: 41"),
        numeric_match=False,
        extracted_answer="41",
        expected_answer="42",
    )

    assert label == "REASONING_FAIL"


def test_summary_counts_failures_and_cap_overlap():
    rows = [
        _row(prompt_id=1, expected_answer="42", generated_text="Final answer: 42"),
        _row(prompt_id=2, expected_answer="9", generated_text="Working...", output_tokens=384),
        _row(prompt_id=3, expected_answer="12", generated_text="Final answer: 10"),
    ]

    summary, cases = summarize_condition_rows(
        condition="LLMLingua-AR-R2",
        artifact="memory.jsonl",
        rows=rows,
    )

    assert summary["rows"] == 3
    assert summary["numeric_matches"] == 1
    assert summary["numeric_failures"] == 2
    assert summary["cap_hits"] == 1
    assert summary["cap_hit_failures"] == 1
    assert summary["label_counts"] == {
        "REASONING_FAIL": 1,
        "TRUNCATION_REMAINING": 1,
    }
    assert len(cases) == 2
