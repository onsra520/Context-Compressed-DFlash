from scripts.phase_1_analysis.analyze_task73_qmsum_concise_policy import analyze_comparisons


def _row(
    *,
    prompt_id: int,
    condition: str = "LLMLingua-AR-R2",
    generated_text: str = "The answer is supported by the meeting.",
    expected_answer: str = "The meeting answer is supported.",
    output_tokens: int = 10,
    max_new_tokens: int = 384,
    generation_time_s: float = 1.0,
    t_compress_ms: float = 100.0,
    policy_preserved: bool | None = None,
):
    row = {
        "prompt_id": prompt_id,
        "benchmark_prompt_index": prompt_id,
        "condition": condition,
        "dataset_name": "qmsum_meeting_qa_long",
        "expected_answer": expected_answer,
        "generated_text": generated_text,
        "output_tokens": output_tokens,
        "max_new_tokens": max_new_tokens,
        "generation_time_s": generation_time_s,
        "tok_per_sec": output_tokens / generation_time_s,
        "t_compress_ms": t_compress_ms,
        "R_actual": 2.0,
        "compression_ratio": 2.0,
        "original_input_tokens": 100,
        "compressed_input_tokens": 50,
        "vram_allocated_gib": 1.0,
        "vram_reserved_gib": 2.0,
    }
    if policy_preserved is not None:
        row["qmsum_concise_policy_preserved"] = policy_preserved
    return row


def test_analyze_comparisons_reports_cap_and_proxy_changes():
    before = {
        "LLMLingua-AR-R2": [
            _row(prompt_id=1, output_tokens=384, generated_text="meeting answer", expected_answer="meeting answer"),
            _row(prompt_id=2, output_tokens=20, generated_text="weak", expected_answer="important answer"),
        ]
    }
    after = {
        "LLMLingua-AR-R2": [
            _row(
                prompt_id=1,
                output_tokens=30,
                generated_text="meeting answer",
                expected_answer="meeting answer",
                policy_preserved=True,
            ),
            _row(
                prompt_id=2,
                output_tokens=20,
                generated_text="important answer",
                expected_answer="important answer",
                policy_preserved=True,
            ),
        ]
    }

    summary, table, cases = analyze_comparisons(before, after)

    comparison = summary["comparisons"]["LLMLingua-AR-R2"]
    assert comparison["before"]["hit_cap_count"] == 1
    assert comparison["after"]["hit_cap_count"] == 0
    assert comparison["cap_to_noncap_prompt_ids"] == [1]
    assert comparison["policy_preservation_rate"] == 1.0
    assert comparison["proxy_improved_prompt_ids"] == [2]
    assert comparison["proxy_degraded_prompt_ids"] == []
    assert summary["decisions"]["qmsum_n100_justified"] is False
    assert len(table) == 2
    assert any(case["change_type"] == "cap_to_noncap" for case in cases)
