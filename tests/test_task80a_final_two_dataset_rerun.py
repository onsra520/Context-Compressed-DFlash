from __future__ import annotations

from scripts.analyze_task80a_final_two_dataset_rerun import (
    build_delta_rows,
    build_run_manifest,
    summarize_condition,
)


def _row(
    *,
    dataset: str,
    condition: str,
    expected: str = "42",
    generated: str = "Final answer: 42",
    output_tokens: int = 10,
    generation_time_s: float = 2.0,
    compress: bool = False,
) -> dict:
    row = {
        "dataset_name": dataset,
        "condition": condition,
        "prompt_id": 1,
        "expected_answer": expected,
        "generated_text": generated,
        "input_tokens": 100,
        "output_tokens": output_tokens,
        "generation_time_s": generation_time_s,
        "tok_per_sec": output_tokens / generation_time_s,
        "tokens_per_second": output_tokens / generation_time_s,
        "t_prefill_ms": 100.0,
        "tau_mean": 0.0,
        "max_new_tokens": 384,
        "vram_allocated_gib": 2.5,
        "vram_reserved_gib": 4.0,
    }
    if dataset == "qmsum_meeting_qa_long":
        row["expected_answer"] = "project manager mentioned language support and microphone issues"
        row["generated_text"] = "The project manager discussed language support and microphone issues."
    if compress:
        row.update(
            {
                "t_compress_ms": 500.0,
                "R_actual": 2.0,
                "compression_ratio": 2.0,
                "original_input_tokens": 200,
                "compressed_input_tokens": 100,
                "keep_rate": 0.5,
                "question_preserved": True,
                "protected_suffix_preserved": True,
            }
        )
    return row


def test_summarize_gsm8k_condition_records_numeric_quality_and_e2e_latency():
    rows = [
        _row(dataset="gsm8k_short", condition="CC-DFlash-R2", compress=True),
        _row(dataset="gsm8k_short", condition="CC-DFlash-R2", generated="Final answer: 7", compress=True),
    ]

    summary = summarize_condition("gsm8k_short", "CC-DFlash-R2", rows, expected_rows=2)

    assert summary["status"] == "completed"
    assert summary["row_count"] == 2
    assert summary["numeric_match_count"] == 1
    assert summary["numeric_accuracy"] == 0.5
    assert summary["avg_e2e_latency_s"] == 2.5
    assert summary["e2e_tok_s"] == 4.0
    assert summary["avg_t_compress_ms"] == 500.0
    assert summary["final_answer_suffix_preserved_count"] == 2


def test_summarize_qmsum_partial_condition_marks_failed_and_keeps_diagnostic_metrics():
    rows = [
        _row(dataset="qmsum_meeting_qa_long", condition="DFlash-R1"),
        _row(dataset="qmsum_meeting_qa_long", condition="DFlash-R1"),
    ]

    summary = summarize_condition("qmsum_meeting_qa_long", "DFlash-R1", rows, expected_rows=30)

    assert summary["status"] == "failed_partial"
    assert summary["row_count"] == 2
    assert summary["semantic_correctness_claim"] is False
    assert summary["avg_overlap_proxy"] > 0
    assert summary["major_shift_reasons"] == ["row_count_incomplete"]


def test_delta_rows_classify_incomplete_qmsum_as_major_shift():
    task80 = {
        ("qmsum_meeting_qa_long", "DFlash-R1"): {
            "row_count": 30,
            "avg_e2e_latency_s": 3.0,
            "e2e_tok_s": 20.0,
        }
    }
    task80a = {
        ("qmsum_meeting_qa_long", "DFlash-R1"): {
            "row_count": 2,
            "avg_e2e_latency_s": 9.0,
            "e2e_tok_s": 10.0,
        }
    }

    rows = build_delta_rows(task80, task80a)

    assert any(row["metric"] == "row_count" and row["severity"] == "major_shift" for row in rows)


def test_run_manifest_records_skipped_conditions_and_resume_flag():
    entries = build_run_manifest(
        commit_before_run="abc123",
        run_status={
            ("qmsum_meeting_qa_long", "DFlash-R1"): {
                "status": "failed_partial",
                "row_count": 2,
                "notes": "Stopped at prompt_id=3 after no progress.",
            },
            ("qmsum_meeting_qa_long", "LLMLingua-AR-R2"): {
                "status": "skipped",
                "row_count": 0,
                "notes": "Skipped after DFlash-R1 stall.",
            },
        },
    )

    by_condition = {(item["dataset"], item["condition"]): item for item in entries}
    assert by_condition[("qmsum_meeting_qa_long", "DFlash-R1")]["resume_used"] is True
    assert by_condition[("qmsum_meeting_qa_long", "DFlash-R1")]["status"] == "failed_partial"
    assert by_condition[("qmsum_meeting_qa_long", "LLMLingua-AR-R2")]["status"] == "skipped"
