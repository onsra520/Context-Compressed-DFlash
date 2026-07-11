from __future__ import annotations

from ccdf.compression.passthrough import PassthroughCompressor
from ccdf.compression.schemas import CompressionConfig, CompressionResult
from ccdf.compression.validation import (
    prompt_invariants,
    token_scope_audit,
    validate_prompt_invariants,
)
from ccdf.prompts.renderer import render_prompt
from ccdf.prompts.schemas import PromptParts


def parts() -> PromptParts:
    return PromptParts(
        context="Alice approved the launch date. Bob asked about budget.",
        question="What was approved?",
        instruction="Answer using only the meeting transcript. A concise answer is enough.",
    )


def test_structured_parts_round_trip_and_passthrough_equivalence() -> None:
    original = parts()
    result = PassthroughCompressor().compress(
        context=original.context, question=original.question, config=CompressionConfig()
    )
    assert result.compressed_context == original.context
    validate_prompt_invariants(original, result.compressed_context)
    assert render_prompt(original) == prompt_invariants(original, result.compressed_context)[
        "final_prompt"
    ]


def test_only_context_changes_and_markers_preserved() -> None:
    original = parts()
    compressed = "Alice approved launch date."
    audit = prompt_invariants(original, compressed)
    assert audit["only_context_changed"] is True
    assert audit["question_occurrence"] == 1
    assert audit["instruction_occurrence"] == 1
    assert audit["meeting_marker_preserved"] is True
    assert audit["question_marker_preserved"] is True


def test_question_repetition_rejected() -> None:
    original = parts()
    bad_context = f"{original.context} {original.question}"
    try:
        validate_prompt_invariants(original, bad_context)
    except ValueError as exc:
        assert "question occurrence" in str(exc)
    else:
        raise AssertionError("expected repeated question to fail")


def test_token_scope_audit_keeps_segment_and_full_prompt_separate() -> None:
    original = parts()
    result = CompressionResult(
        compressed_context="Alice approved launch date.",
        segment_original_tokens=10,
        segment_compressed_tokens=4,
        segment_tokenizer_id="llmlingua2:local",
        compression_factor=2.5,
        retained_ratio=0.4,
        reduction_pct=60.0,
        chunk_count=1,
        compression_total_ms=1.0,
    )
    audit = token_scope_audit(original, result)
    assert audit["tokenizer_scopes_separate"] is True
    assert audit["final_target_prompt_tokens"] < audit["precompression_target_prompt_tokens"]


def test_bypass_is_explicit_for_short_context() -> None:
    original = parts()
    result = PassthroughCompressor().compress(
        context=original.context, question=original.question, config=CompressionConfig()
    )
    assert result.bypassed is True
    assert result.backend_metadata["backend"] == "passthrough"
