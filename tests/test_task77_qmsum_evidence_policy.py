from __future__ import annotations

from scripts.analyze_task77_qmsum_evidence_policy import analyze_evidence_policy


def _row(
    *,
    condition: str = "LLMLingua-AR-R2",
    prompt_id: int = 1,
    expected: str = "Maya approved Project Phoenix with a 25 million euro budget after board review.",
    generated: str = "Maya approved Project Phoenix with a 25 million euro budget after board review.",
    output_tokens: int = 80,
    max_new_tokens: int = 384,
    policy_preserved: bool = True,
) -> dict:
    return {
        "condition": condition,
        "prompt_id": prompt_id,
        "benchmark_prompt_index": prompt_id,
        "fixture_id": f"qmsum_{prompt_id}",
        "dataset_name": "qmsum_meeting_qa_long",
        "expected_answer": expected,
        "generated_text": generated,
        "output_tokens": output_tokens,
        "max_new_tokens": max_new_tokens,
        "generation_time_s": 2.0,
        "tok_per_sec": output_tokens / 2.0,
        "t_compress_ms": 1000.0,
        "t_prefill_ms": 50.0,
        "R_actual": 2.0,
        "qmsum_answer_policy_preserved": policy_preserved,
        "qmsum_answer_policy_type": "evidence_focused",
        "qmsum_evidence_focus_enabled": True,
        "qmsum_evidence_focus_version": "task77",
    }


def _task76_case(
    *,
    condition: str = "LLMLingua-AR-R2",
    prompt_id: int = 1,
    label: str = "EVIDENCE_MISSING_OR_MISFOCUSED",
) -> dict:
    return {
        "condition": condition,
        "prompt_id": prompt_id,
        "fixture_id": f"qmsum_{prompt_id}",
        "expected_answer": "Maya approved Project Phoenix with a 25 million euro budget after board review.",
        "evidence_error_label": label,
    }


def test_analyze_evidence_policy_tracks_policy_preservation_and_label_change():
    task77 = {
        "LLMLingua-AR-R2": [
            _row(),
            _row(
                prompt_id=2,
                expected="The meeting described 550 MHz IBM processors and 800 MB memory.",
                generated="The meeting does not mention the processor or memory details.",
            ),
        ]
    }
    task76_cases = [
        _task76_case(prompt_id=1, label="EVIDENCE_MISSING_OR_MISFOCUSED"),
        _task76_case(prompt_id=2, label="MISSING_ENTITY_OR_NUMBER"),
    ]

    summary, table, cases = analyze_evidence_policy(task77, task76_cases=task76_cases)

    condition = summary["by_condition"]["LLMLingua-AR-R2"]
    assert condition["rows"] == 2
    assert condition["policy_preserved_count"] == 2
    assert condition["policy_preservation_rate"] == 1.0
    assert condition["label_counts"]["ACCEPTABLE_EVIDENCE_FOCUSED_ANSWER"] == 1
    assert condition["label_counts"]["WRONG_NEGATIVE"] == 1
    assert cases[0]["task76_evidence_error_label"] == "EVIDENCE_MISSING_OR_MISFOCUSED"
    assert cases[0]["label_change_from_task76"] == "EVIDENCE_MISSING_OR_MISFOCUSED->ACCEPTABLE_EVIDENCE_FOCUSED_ANSWER"
    assert cases[0]["improvement_vs_task75_label"] is True
    assert table[0]["condition"] == "LLMLingua-AR-R2"


def test_analyze_evidence_policy_keeps_qmsum_n100_blocked_when_errors_remain():
    task77 = {
        "CC-DFlash-R2": [
            _row(
                condition="CC-DFlash-R2",
                expected="The fish sector got COVID-19 support including 62.5M and CERB.",
                generated="There was no government support for fishing.",
            )
        ]
    }

    summary, _table, cases = analyze_evidence_policy(task77, task76_cases=[])

    assert summary["decisions"]["qmsum_n100_justified"] is False
    assert summary["decisions"]["mnt512_needed"] is False
    assert summary["by_condition"]["CC-DFlash-R2"]["wrong_negative_count"] == 1
    assert cases[0]["task77_evidence_error_label"] == "WRONG_NEGATIVE"
