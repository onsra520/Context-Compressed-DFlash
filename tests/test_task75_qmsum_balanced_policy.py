from scripts.phase_1_analysis.analyze_task75_qmsum_balanced_policy import analyze_policy_stages


def _row(
    *,
    prompt_id: int = 1,
    condition: str = "LLMLingua-AR-R2",
    generated: str,
    expected: str = "The team approved the launch plan after budget review and assigned Maya to coordinate the release.",
    output_tokens: int = 40,
    max_new_tokens: int = 384,
    policy_preserved: bool | None = None,
) -> dict:
    row = {
        "condition": condition,
        "prompt_id": prompt_id,
        "benchmark_prompt_index": prompt_id,
        "dataset_name": "qmsum_meeting_qa_long",
        "fixture_id": f"qmsum_{prompt_id}",
        "expected_answer": expected,
        "generated_text": generated,
        "output_tokens": output_tokens,
        "max_new_tokens": max_new_tokens,
        "generation_time_s": 2.0,
        "tok_per_sec": output_tokens / 2.0,
        "t_compress_ms": 1000.0,
        "R_actual": 2.0,
    }
    if policy_preserved is not None:
        row["qmsum_answer_policy_preserved"] = policy_preserved
        row["qmsum_answer_policy_type"] = "balanced"
    return row


def test_analyze_policy_stages_labels_balanced_detail_recovery():
    original = _row(
        generated=(
            "The team approved the launch plan after budget review and assigned Maya to coordinate "
            "the release. The decision was tied to the budget review."
        ),
        output_tokens=384,
    )
    terse = _row(generated="The team approved the launch plan.", output_tokens=18)
    balanced = _row(
        generated=(
            "The team approved the launch plan after budget review. Maya was assigned to coordinate "
            "the release, and the answer omits unrelated meeting details."
        ),
        output_tokens=44,
        policy_preserved=True,
    )

    summary, table, cases = analyze_policy_stages(
        {"LLMLingua-AR-R2": [original]},
        {"LLMLingua-AR-R2": [terse]},
        {"LLMLingua-AR-R2": [balanced]},
    )

    condition = summary["by_condition"]["LLMLingua-AR-R2"]
    assert condition["stage_summaries"]["balanced"]["qmsum_answer_policy_preservation_rate"] == 1.0
    assert condition["label_counts"]["BALANCED_RECOVERS_DETAILS"] == 1
    assert summary["decisions"]["keep_balanced_policy_as_qmsum_candidate"] is True
    assert summary["decisions"]["qmsum_n100_justified"] is False
    assert table[0]["stage"] == "original"
    assert cases[0]["label"] == "BALANCED_RECOVERS_DETAILS"


def test_analyze_policy_stages_detects_cap_pressure_returning():
    original = _row(generated="Original answer with useful meeting detail.", output_tokens=384)
    terse = _row(generated="Short answer.", output_tokens=12)
    balanced = _row(
        generated="Long answer that still runs into the token cap without reaching a clean ending",
        output_tokens=384,
        policy_preserved=True,
    )

    summary, _table, cases = analyze_policy_stages(
        {"CC-DFlash-R2": [original]},
        {"CC-DFlash-R2": [terse]},
        {"CC-DFlash-R2": [balanced]},
    )

    assert summary["by_condition"]["CC-DFlash-R2"]["balanced_cap_hits"] == 1
    assert cases[0]["label"] == "CAP_PRESSURE_RETURNED"
    assert summary["decisions"]["mnt512_needed"] is True
