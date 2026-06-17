from __future__ import annotations

from scripts.phase_1_system_build_and_evaluation.analysis.t78_qmsum_evidence_retention import (
    analyze_retention,
    classify_retention,
    extract_important_terms,
)


def test_extract_important_terms_filters_discourse_and_keeps_real_terms():
    terms = extract_important_terms(
        "Plus the Welsh Government discussed COVID-19 support, $62.5M, CERB, EI, "
        "Aurora, Carmen, SPINE, IBM, 550, and 800 MHz. Therefore the disk rack mattered."
    )

    assert "Plus" not in terms
    assert "Therefore" not in terms
    for item in ["Welsh Government", "COVID-19", "62.5", "CERB", "EI", "Aurora", "Carmen", "SPINE", "IBM", "550", "800", "disk rack"]:
        assert item in terms


def test_classify_retention_detects_model_failure_when_evidence_retained():
    result = classify_retention(
        expected_answer="PhD C described 100ms latency, 40ms input delta, 10ms LDA delay.",
        original_context="PhD C described 100ms latency, 40ms input delta, and 10ms LDA delay.",
        compressed_context="PhD C described 100ms latency, 40ms input delta, and 10ms LDA delay.",
        question_preserved=True,
        protected_suffix_preserved=True,
    )

    assert result["evidence_retention_label"] == "EVIDENCE_PRESENT_IN_COMPRESSED_PROMPT_MODEL_FAILED"
    assert result["confidence"] == "high"
    assert not result["lost_terms_after_compression"]


def test_classify_retention_detects_compression_loss():
    result = classify_retention(
        expected_answer="The disk rack added four 36GB disks for Aurora, Carmen, and SPINE directories.",
        original_context="The disk rack added four 36GB disks for Aurora, Carmen, and SPINE directories.",
        compressed_context="The team discussed meeting recordings and data collection.",
        question_preserved=True,
        protected_suffix_preserved=True,
    )

    assert result["evidence_retention_label"] == "EVIDENCE_MISSING_FROM_COMPRESSED_PROMPT"
    assert "Aurora" in result["lost_terms_after_compression"]
    assert result["original_context_hit_rate"] > result["compressed_context_hit_rate"]


def test_analyze_retention_reports_counts_and_priority_cases():
    task77_cases = [
        {
            "condition": "LLMLingua-AR-R2",
            "prompt_id": 14,
            "fixture_id": "qmsum_14",
            "expected_answer": "PhD C described 100ms latency, 40ms input delta, 10ms LDA delay.",
            "task77_evidence_error_label": "WRONG_NEGATIVE",
            "task77_generated_snippet": "The meeting does not mention latency.",
        },
        {
            "condition": "CC-DFlash-R2",
            "prompt_id": 14,
            "fixture_id": "qmsum_14",
            "expected_answer": "PhD C described 100ms latency, 40ms input delta, 10ms LDA delay.",
            "task77_evidence_error_label": "WRONG_NEGATIVE",
            "task77_generated_snippet": "The meeting does not mention latency.",
        },
    ]
    reconstructed = {
        14: {
            "original_context": "PhD C described 100ms latency, 40ms input delta, and 10ms LDA delay.",
            "compressed_context": "PhD C described 100ms latency, 40ms input delta, and 10ms LDA delay.",
            "question_preserved": True,
            "protected_suffix_preserved": True,
        }
    }

    summary, table, cases = analyze_retention(task77_cases, reconstructed_by_prompt=reconstructed)

    assert summary["total_audited_cases"] == 1
    assert summary["count_by_evidence_retention_label"]["EVIDENCE_PRESENT_IN_COMPRESSED_PROMPT_MODEL_FAILED"] == 1
    assert summary["specific_prompt_checks"]["14"][0]["evidence_retention_label"] == "EVIDENCE_PRESENT_IN_COMPRESSED_PROMPT_MODEL_FAILED"
    assert table[0]["evidence_retention_label"] == "EVIDENCE_PRESENT_IN_COMPRESSED_PROMPT_MODEL_FAILED"
    assert cases[0]["condition"] == "shared_compressed_prompt"
