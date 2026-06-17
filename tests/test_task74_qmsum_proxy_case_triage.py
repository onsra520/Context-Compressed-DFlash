from scripts.phase_1_system_build_and_evaluation.analysis.t74_qmsum_proxy_case_triage import (
    analyze_case_pairs,
    bigram_overlap,
    label_case,
    lexical_diagnostics,
)


def _row(
    *,
    prompt_id: int = 1,
    expected: str = "The team approved the launch plan after budget review.",
    generated: str = "The team approved the launch plan.",
    output_tokens: int = 20,
    max_new_tokens: int = 384,
    generation_time_s: float = 1.0,
    condition: str = "LLMLingua-AR-R2",
):
    return {
        "prompt_id": prompt_id,
        "benchmark_prompt_index": prompt_id,
        "condition": condition,
        "expected_answer": expected,
        "generated_text": generated,
        "output_tokens": output_tokens,
        "max_new_tokens": max_new_tokens,
        "generation_time_s": generation_time_s,
        "tok_per_sec": output_tokens / generation_time_s,
        "t_compress_ms": 100.0,
        "qmsum_concise_policy_preserved": output_tokens < max_new_tokens,
    }


def test_lexical_diagnostics_include_bigram_keyword_and_length_ratio():
    expected = "The project manager approved the launch plan after budget review."
    generated = "The manager approved the launch plan."

    diagnostics = lexical_diagnostics(expected, generated)

    assert diagnostics["unigram_overlap"] > 0.5
    assert diagnostics["bigram_overlap"] > 0.2
    assert diagnostics["keyword_overlap"] >= 0.5
    assert 0 < diagnostics["generated_to_reference_length_ratio"] < 1


def test_bigram_overlap_handles_empty_reference():
    assert bigram_overlap("", "some generated answer") == 0.0


def test_label_case_distinguishes_proxy_mismatch_and_quality_loss():
    before = _row(
        generated="The team approved the launch plan after budget review because the schedule was ready.",
        output_tokens=384,
    )
    concise = _row(generated="The team approved the launch plan.", output_tokens=14)
    unsupported = _row(generated="The team discussed unrelated audio settings.", output_tokens=12)

    assert label_case(before, concise)["label"] in {
        "PROXY_MISMATCH_CONCISE_ANSWER",
        "ACCEPTABLE_CONCISE_ANSWER",
        "TRUNCATION_FIXED",
    }
    assert label_case(before, unsupported)["label"] in {
        "TRUE_QUALITY_DEGRADATION_POSSIBLE",
        "ANSWER_TOO_SHORT_OR_UNSUPPORTED",
    }


def test_analyze_case_pairs_summarizes_condition_level_counts():
    before_rows = [
        _row(prompt_id=1, generated="The team approved the launch plan after budget review.", output_tokens=384),
        _row(prompt_id=2, expected="The budget was rejected.", generated="The budget was rejected.", output_tokens=30),
    ]
    after_rows = [
        _row(prompt_id=1, generated="The team approved the launch plan.", output_tokens=14),
        _row(prompt_id=2, expected="The budget was rejected.", generated="The audio setup changed.", output_tokens=12),
    ]

    summary, table, samples = analyze_case_pairs(
        {"LLMLingua-AR-R2": before_rows},
        {"LLMLingua-AR-R2": after_rows},
    )

    condition = summary["by_condition"]["LLMLingua-AR-R2"]
    assert condition["rows"] == 2
    assert condition["before_cap_hits"] == 1
    assert condition["after_cap_hits"] == 0
    assert condition["label_counts"]
    assert summary["decisions"]["qmsum_n100_justified"] is False
    assert len(table) == 1
    assert len(samples) == 2
