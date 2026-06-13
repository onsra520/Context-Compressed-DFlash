from scripts.analyze_task76_qmsum_evidence_error_taxonomy import (
    analyze_evidence_errors,
    classify_case,
)


def _case(
    *,
    condition: str = "LLMLingua-AR-R2",
    prompt_id: int = 1,
    expected: str = "Alice approved Program Phoenix with a 25 million euro budget because it reduced support costs.",
    generated: str = "Alice approved Program Phoenix with a 25 million euro budget because it reduced support costs.",
    old_label: str = "STILL_TOO_SHORT",
) -> dict:
    return {
        "condition": condition,
        "prompt_id": prompt_id,
        "fixture_id": f"qmsum_{prompt_id}",
        "expected_answer": expected,
        "balanced_generated_snippet": generated,
        "label": old_label,
        "balanced_diagnostics": {
            "unigram_overlap": 0.5,
            "keyword_overlap": 0.5,
            "numeric_entity_overlap": 0.5,
            "reference_answer_coverage": 0.5,
        },
        "balanced_output_tokens": 48,
        "balanced_hit_cap": False,
        "qmsum_answer_policy_preserved": True,
    }


def test_classify_case_detects_wrong_negative():
    result = classify_case(
        _case(
            expected="Maya said the 25 euro price was approved after the budget review.",
            generated="The meeting does not mention the price or whether it was approved.",
        )
    )

    assert result["evidence_error_label"] == "WRONG_NEGATIVE"
    assert result["wrong_negative"] is True


def test_classify_case_detects_missing_entity_or_number():
    result = classify_case(
        _case(
            expected="Maya approved Program Phoenix with a 25 million euro budget.",
            generated="The team approved the program after discussing the budget.",
        )
    )

    assert result["evidence_error_label"] == "MISSING_ENTITY_OR_NUMBER"
    assert "Maya" in result["missing_entities_or_numbers"]
    assert "25" in result["missing_entities_or_numbers"]


def test_analyze_evidence_errors_reports_shared_prompt_labels():
    cases = [
        _case(condition="LLMLingua-AR-R2", prompt_id=1, generated="The meeting does not mention the budget."),
        _case(condition="CC-DFlash-R2", prompt_id=1, generated="The meeting does not mention the budget."),
        _case(condition="LLMLingua-AR-R2", prompt_id=2),
        _case(condition="CC-DFlash-R2", prompt_id=2, generated="The group generally discussed the proposal."),
    ]

    summary, table, output_cases = analyze_evidence_errors(cases)

    assert summary["total_rows"] == 4
    assert summary["total_label_counts"]["WRONG_NEGATIVE"] == 2
    assert summary["shared_prompt_ids_same_label"]["WRONG_NEGATIVE"] == [1]
    assert summary["acceptable_prompt_ids"]
    assert len(table) == 2
    assert len(output_cases) == 4
