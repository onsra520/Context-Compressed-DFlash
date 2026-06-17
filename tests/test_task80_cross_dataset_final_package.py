from __future__ import annotations

from scripts.phase_1_analysis.analyze_task80_cross_dataset_final_package import (
    build_claims_matrix,
    build_cross_dataset_package,
    summarize_gsm8k_condition,
)


def _row(condition: str, *, expected: str = "42", generated: str = "Final answer: 42", compress: bool = False) -> dict:
    row = {
        "condition": condition,
        "dataset_name": "gsm8k_short",
        "expected_answer": expected,
        "generated_text": generated,
        "output_tokens": 10,
        "input_tokens": 100,
        "generation_time_s": 2.0,
        "tok_per_sec": 5.0,
        "tokens_per_second": 5.0,
        "t_prefill_ms": 100.0,
        "max_new_tokens": 384,
        "tau_mean": 0.0,
    }
    if compress:
        row.update(
            {
                "keep_rate": 0.5,
                "t_compress_ms": 500.0,
                "R_actual": 2.0,
                "compression_ratio": 2.0,
                "original_input_tokens": 200,
                "compressed_input_tokens": 100,
                "protected_suffix_preserved": True,
                "question_preserved": True,
            }
        )
    return row


def test_summarize_gsm8k_condition_computes_quality_and_latency():
    rows = [
        _row("CC-DFlash-R2", compress=True),
        _row("CC-DFlash-R2", generated="Final answer: 7", compress=True),
    ]

    summary = summarize_gsm8k_condition("CC-DFlash-R2", rows)

    assert summary["n"] == 2
    assert summary["numeric_matches"] == 1
    assert summary["numeric_accuracy"] == 0.5
    assert summary["avg_e2e_latency_s"] == 2.5
    assert summary["e2e_tok_per_sec"] == 4.0
    assert summary["avg_t_compress_ms"] == 500.0
    assert summary["compression_ratio"] == 2.0
    assert summary["keep_rate"] == 0.5


def test_build_claims_matrix_contains_required_forbidden_and_allowed_claims():
    rows = build_claims_matrix()
    by_claim = {row["claim"]: row for row in rows}

    assert by_claim["Compression always improves e2e latency."]["status"] == "forbidden"
    assert by_claim["QMSum is useful as long-context diagnostic benchmark."]["status"] == "allowed"
    assert by_claim["CC-DFlash improves e2e over LLMLingua-AR-R2 on GSM8K n30."]["status"] == "allowed_with_caveat"


def test_build_cross_dataset_package_splits_gsm8k_quality_from_qmsum_diagnostic():
    rows_by_condition = {
        "Baseline-AR": [_row("Baseline-AR")],
        "DFlash-R1": [_row("DFlash-R1")],
        "LLMLingua-AR-R2": [_row("LLMLingua-AR-R2", compress=True)],
        "CC-DFlash-R2": [_row("CC-DFlash-R2", compress=True)],
    }
    qmsum_decision = {
        "qmsum_final_role": "diagnostic long-context benchmark",
        "qmsum_n100_justified": False,
        "mnt512_needed": False,
        "more_suffix_tuning_justified": False,
    }
    qmsum_retention = {
        "count_by_evidence_retention_label": {
            "EVIDENCE_PRESENT_IN_COMPRESSED_PROMPT_MODEL_FAILED": 10,
        }
    }

    package = build_cross_dataset_package(
        gsm8k_rows_by_condition=rows_by_condition,
        qmsum_decision=qmsum_decision,
        qmsum_retention_summary=qmsum_retention,
        qmsum_full_matrix_summary={},
        qmsum_policy_summaries={},
    )

    assert package["status"] == "PASS_WITH_NOTES"
    assert package["datasets"]["gsm8k_short"]["role"] == "short-context numeric quality"
    assert package["datasets"]["qmsum_meeting_qa_long"]["semantic_correctness_claimed"] is False
    assert package["cross_dataset_conclusion"]["hypothesis_status"] == "partially_supported_conditionally"
