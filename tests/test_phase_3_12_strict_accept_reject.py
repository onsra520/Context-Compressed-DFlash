"""Phase 3.12 — Strict accept/reject algorithm tests.

All tests in this file are pure: no GGUF model, no GPU, no disk access.
Tests use fake/deterministic token IDs to exercise the comparison algorithm.

Covers:
    1. Full accept
    2. Partial accept
    3. Full reject
    4. Empty candidate
    5. Missing greedy tokens (no fallback)
    6. Unused suffix accounting
    7. Fallback-only cycle semantics
    8. Repeated fallback-only cycle detection
    9. Candidate longer than greedy sequence
    10. Correct VerificationDecision field values
    11. Data structure invariants
    12. select_context_update_source labels
    13. Constants and naming guard
"""

from __future__ import annotations

import pytest

from htfsd.low_tier.strict_verifier import (
    CONTEXT_UPDATE_ACCEPTED_PREFIX,
    CONTEXT_UPDATE_FALLBACK_ONLY,
    CONTEXT_UPDATE_FULL_ACCEPT,
    FALLBACK_REASON_EMPTY_CANDIDATE,
    FALLBACK_REASON_FULL_REJECT,
    FALLBACK_REASON_PARTIAL_ACCEPT,
    REJECTION_REASON_EMPTY_CANDIDATE,
    REJECTION_REASON_NO_GREEDY_TOKENS,
    REJECTION_REASON_TOKEN_MISMATCH,
    STOP_REASON_NO_PROGRESS_ERROR,
    VERIFICATION_FULL_ACCEPT,
    VERIFICATION_FULL_REJECT,
    VERIFICATION_PARTIAL_ACCEPT,
    VerificationDecision,
    VerifierCycleTrace,
    compare_candidate_to_greedy,
    select_context_update_source,
)


# ---------------------------------------------------------------------------
# 1. Full accept
# ---------------------------------------------------------------------------


def test_full_accept_all_tokens_match() -> None:
    """All candidate tokens match verifier greedy: full_accept, no fallback."""
    candidate = [1, 2, 3]
    greedy = [1, 2, 3]
    decision = compare_candidate_to_greedy(candidate, greedy)

    assert decision.verification_result == VERIFICATION_FULL_ACCEPT
    assert decision.matched_verifier_token_count == 3
    assert decision.accepted_target_token_count == 3
    assert decision.rejected_target_token_count == 0
    assert decision.unused_suffix_token_count == 0
    assert decision.first_rejection_position is None
    assert decision.fallback_token_id is None
    assert decision.rejection_reason is None
    assert decision.stop_reason is None


def test_full_accept_preserves_accepted_prefix_property() -> None:
    candidate = [10, 20, 30]
    greedy = [10, 20, 30]
    decision = compare_candidate_to_greedy(candidate, greedy)

    assert decision.accepted_prefix == [10, 20, 30]
    assert decision.unused_suffix == []


def test_full_accept_greedy_longer_than_candidate() -> None:
    """Greedy has more tokens than candidate: still full accept on the candidate."""
    candidate = [1, 2]
    greedy = [1, 2, 3, 4]
    decision = compare_candidate_to_greedy(candidate, greedy)

    assert decision.verification_result == VERIFICATION_FULL_ACCEPT
    assert decision.matched_verifier_token_count == 2
    assert decision.accepted_target_token_count == 2
    assert decision.unused_suffix_token_count == 0
    assert decision.fallback_token_id is None


# ---------------------------------------------------------------------------
# 2. Partial accept
# ---------------------------------------------------------------------------


def test_partial_accept_prefix_matches() -> None:
    """First two tokens match, third mismatches: partial_accept with fallback."""
    candidate = [1, 2, 3, 4]
    greedy = [1, 2, 9, 8]
    decision = compare_candidate_to_greedy(candidate, greedy)

    assert decision.verification_result == VERIFICATION_PARTIAL_ACCEPT
    assert decision.matched_verifier_token_count == 2
    assert decision.accepted_target_token_count == 2
    assert decision.rejected_target_token_count == 1
    assert decision.first_rejection_position == 2
    assert decision.unused_suffix_token_count == 1   # [4] is discarded
    assert decision.fallback_token_id == 9
    assert decision.fallback_reason == FALLBACK_REASON_PARTIAL_ACCEPT
    assert decision.rejection_reason == REJECTION_REASON_TOKEN_MISMATCH
    assert decision.stop_reason is None


def test_partial_accept_unused_suffix_is_not_rejected() -> None:
    """Unused suffix tokens are counted separately, not as rejected_target_token_count."""
    candidate = [1, 2, 3, 4, 5]
    greedy = [1, 2, 9, 8, 7]
    decision = compare_candidate_to_greedy(candidate, greedy)

    # Position 2 is the first mismatch
    assert decision.first_rejection_position == 2
    # rejected_target_token_count is exactly 1 (the mismatching position)
    assert decision.rejected_target_token_count == 1
    # Positions 3,4 (tokens [4,5]) are the unused suffix — NOT counted as rejected
    assert decision.unused_suffix_token_count == 2
    # accepted prefix: [1, 2]
    assert decision.accepted_prefix == [1, 2]
    # unused suffix: [4, 5]
    assert decision.unused_suffix == [4, 5]


def test_partial_accept_accounting_adds_up() -> None:
    """accepted + rejected + unused = len(candidate)."""
    candidate = [1, 2, 3, 4]
    greedy = [1, 2, 9, 8]
    decision = compare_candidate_to_greedy(candidate, greedy)

    total = (
        decision.accepted_target_token_count
        + decision.rejected_target_token_count
        + decision.unused_suffix_token_count
    )
    assert total == len(candidate)


# ---------------------------------------------------------------------------
# 3. Full reject
# ---------------------------------------------------------------------------


def test_full_reject_first_token_mismatches() -> None:
    """First candidate token mismatches: full_reject, 0 accepted."""
    candidate = [1, 2, 3]
    greedy = [9, 8, 7]
    decision = compare_candidate_to_greedy(candidate, greedy)

    assert decision.verification_result == VERIFICATION_FULL_REJECT
    assert decision.matched_verifier_token_count == 0
    assert decision.accepted_target_token_count == 0
    assert decision.rejected_target_token_count == 1
    assert decision.first_rejection_position == 0
    # unused suffix: [2, 3] — the positions after position 0
    assert decision.unused_suffix_token_count == 2
    assert decision.fallback_token_id == 9
    assert decision.fallback_reason == FALLBACK_REASON_FULL_REJECT
    assert decision.rejection_reason == REJECTION_REASON_TOKEN_MISMATCH
    assert decision.stop_reason is None


def test_full_reject_accepted_prefix_is_empty() -> None:
    candidate = [1, 2, 3]
    greedy = [9, 8, 7]
    decision = compare_candidate_to_greedy(candidate, greedy)

    assert decision.accepted_prefix == []
    assert decision.unused_suffix == [2, 3]


# ---------------------------------------------------------------------------
# 4. Empty candidate
# ---------------------------------------------------------------------------


def test_empty_candidate_with_greedy_available() -> None:
    """Empty candidate: fallback to greedy[0], no accepted tokens."""
    candidate: list[int] = []
    greedy = [9, 8, 7]
    decision = compare_candidate_to_greedy(candidate, greedy)

    assert decision.verification_result == VERIFICATION_FULL_REJECT
    assert decision.matched_verifier_token_count == 0
    assert decision.accepted_target_token_count == 0
    assert decision.rejected_target_token_count == 0
    assert decision.unused_suffix_token_count == 0
    assert decision.fallback_token_id == 9
    assert decision.rejection_reason == REJECTION_REASON_EMPTY_CANDIDATE
    assert decision.fallback_reason == FALLBACK_REASON_EMPTY_CANDIDATE
    assert decision.stop_reason is None


def test_empty_candidate_no_greedy_triggers_no_progress() -> None:
    """Empty candidate AND no greedy tokens: no_progress_error."""
    candidate: list[int] = []
    greedy: list[int] = []
    decision = compare_candidate_to_greedy(candidate, greedy)

    assert decision.verification_result == VERIFICATION_FULL_REJECT
    assert decision.fallback_token_id is None
    assert decision.stop_reason == STOP_REASON_NO_PROGRESS_ERROR


# ---------------------------------------------------------------------------
# 5. Missing greedy tokens (no fallback available)
# ---------------------------------------------------------------------------


def test_missing_greedy_tokens_triggers_no_progress() -> None:
    """Candidate present but no greedy tokens: no_progress_error."""
    candidate = [1, 2, 3]
    greedy: list[int] = []
    decision = compare_candidate_to_greedy(candidate, greedy)

    assert decision.verification_result == VERIFICATION_FULL_REJECT
    assert decision.fallback_token_id is None
    assert decision.stop_reason == STOP_REASON_NO_PROGRESS_ERROR
    assert decision.rejection_reason == REJECTION_REASON_NO_GREEDY_TOKENS
    assert decision.no_progress is True


# ---------------------------------------------------------------------------
# 6. Unused suffix is not rejected
# ---------------------------------------------------------------------------


def test_unused_suffix_not_counted_as_rejected() -> None:
    """Explicitly verify the core accounting invariant: unused != rejected."""
    candidate = [1, 2, 99, 100, 200]
    greedy = [1, 2, 50, 60, 70]
    decision = compare_candidate_to_greedy(candidate, greedy)

    # Position 2 is the first mismatch: candidate[2]=99 vs greedy[2]=50
    assert decision.first_rejection_position == 2
    assert decision.rejected_target_token_count == 1        # exactly 1
    assert decision.unused_suffix_token_count == 2          # [100, 200] discarded
    assert decision.unused_suffix == [100, 200]


# ---------------------------------------------------------------------------
# 7. Fallback-only cycle commits exactly one token
# ---------------------------------------------------------------------------


def test_full_reject_fallback_commits_one_token() -> None:
    """When full_reject with fallback: exactly one greedy token is committed."""
    candidate = [1, 2, 3]
    greedy = [9, 8, 7]
    decision = compare_candidate_to_greedy(candidate, greedy)

    assert decision.verification_result == VERIFICATION_FULL_REJECT
    assert decision.fallback_token_id == 9      # exactly one fallback token
    assert decision.accepted_target_token_count == 0
    assert decision.no_progress is False        # fallback is available


def test_partial_accept_fallback_commits_after_prefix() -> None:
    """Partial accept: prefix is committed, then exactly one fallback token."""
    candidate = [5, 6, 7]
    greedy = [5, 6, 99]
    decision = compare_candidate_to_greedy(candidate, greedy)

    assert decision.verification_result == VERIFICATION_PARTIAL_ACCEPT
    assert decision.accepted_target_token_count == 2    # [5, 6] accepted
    assert decision.fallback_token_id == 99             # one fallback
    assert decision.no_progress is False


# ---------------------------------------------------------------------------
# 8. Repeated fallback-only cycles: warning-worthy, not speedup
# ---------------------------------------------------------------------------


def test_repeated_fallback_does_not_become_speedup() -> None:
    """Multiple full-reject cycles should each produce exactly one fallback token.

    The test verifies the accounting is consistent across multiple calls.
    Fallback count is NOT correctness, performance, or benchmark evidence.
    """
    for _ in range(5):
        decision = compare_candidate_to_greedy([1, 2, 3], [9, 8, 7])
        assert decision.verification_result == VERIFICATION_FULL_REJECT
        assert decision.fallback_token_id == 9
        assert decision.accepted_target_token_count == 0
        assert decision.rejected_target_token_count == 1
        assert decision.unused_suffix_token_count == 2


# ---------------------------------------------------------------------------
# 9. Candidate longer than greedy sequence
# ---------------------------------------------------------------------------


def test_candidate_longer_than_greedy_partial_match() -> None:
    """Candidate has more tokens than greedy: match up to greedy length, then mismatch."""
    candidate = [1, 2, 3, 4, 5]   # 5 tokens
    greedy = [1, 2, 3]             # 3 tokens — greedy runs out
    decision = compare_candidate_to_greedy(candidate, greedy)

    # Tokens 0-2 all match; candidate[3] has no greedy counterpart → mismatch at pos 3
    assert decision.verification_result == VERIFICATION_PARTIAL_ACCEPT
    assert decision.matched_verifier_token_count == 3
    assert decision.first_rejection_position == 3
    assert decision.rejected_target_token_count == 1
    assert decision.unused_suffix_token_count == 1   # candidate[4] discarded
    # No fallback token available because greedy[3] doesn't exist
    assert decision.fallback_token_id is None
    assert decision.stop_reason == STOP_REASON_NO_PROGRESS_ERROR


# ---------------------------------------------------------------------------
# 10. Single token inputs
# ---------------------------------------------------------------------------


def test_single_token_match() -> None:
    decision = compare_candidate_to_greedy([42], [42])
    assert decision.verification_result == VERIFICATION_FULL_ACCEPT
    assert decision.matched_verifier_token_count == 1
    assert decision.fallback_token_id is None


def test_single_token_mismatch() -> None:
    decision = compare_candidate_to_greedy([42], [99])
    assert decision.verification_result == VERIFICATION_FULL_REJECT
    assert decision.matched_verifier_token_count == 0
    assert decision.fallback_token_id == 99
    assert decision.unused_suffix_token_count == 0   # no tokens after position 0


# ---------------------------------------------------------------------------
# 11. Data structure invariants
# ---------------------------------------------------------------------------


def test_verification_decision_accepted_prefix_matches_slice() -> None:
    candidate = [1, 2, 3, 4, 5]
    greedy = [1, 2, 9, 8, 7]
    decision = compare_candidate_to_greedy(candidate, greedy)

    assert decision.accepted_prefix == candidate[: decision.first_rejection_position]


def test_verification_decision_unused_suffix_matches_slice() -> None:
    candidate = [1, 2, 3, 4, 5]
    greedy = [1, 2, 9, 8, 7]
    decision = compare_candidate_to_greedy(candidate, greedy)

    pos = decision.first_rejection_position
    assert pos is not None
    assert decision.unused_suffix == candidate[pos + 1 :]


def test_no_progress_property() -> None:
    decision = compare_candidate_to_greedy([1], [])
    assert decision.no_progress is True

    decision2 = compare_candidate_to_greedy([1], [1])
    assert decision2.no_progress is False


# ---------------------------------------------------------------------------
# 12. select_context_update_source labels
# ---------------------------------------------------------------------------


def test_context_update_source_full_accept() -> None:
    decision = compare_candidate_to_greedy([1, 2], [1, 2])
    assert select_context_update_source(decision) == CONTEXT_UPDATE_FULL_ACCEPT


def test_context_update_source_accepted_prefix() -> None:
    decision = compare_candidate_to_greedy([1, 2, 3], [1, 2, 9])
    assert select_context_update_source(decision) == CONTEXT_UPDATE_ACCEPTED_PREFIX


def test_context_update_source_fallback_only() -> None:
    decision = compare_candidate_to_greedy([1, 2, 3], [9, 8, 7])
    assert select_context_update_source(decision) == CONTEXT_UPDATE_FALLBACK_ONLY


def test_context_update_source_empty_candidate() -> None:
    decision = compare_candidate_to_greedy([], [9, 8, 7])
    assert select_context_update_source(decision) == CONTEXT_UPDATE_FALLBACK_ONLY


# ---------------------------------------------------------------------------
# 13. Constants and naming guard
# ---------------------------------------------------------------------------


def test_constants_are_strings() -> None:
    """Verify all constants are well-defined strings."""
    assert isinstance(VERIFICATION_FULL_ACCEPT, str)
    assert isinstance(VERIFICATION_PARTIAL_ACCEPT, str)
    assert isinstance(VERIFICATION_FULL_REJECT, str)
    assert isinstance(REJECTION_REASON_TOKEN_MISMATCH, str)
    assert isinstance(REJECTION_REASON_EMPTY_CANDIDATE, str)
    assert isinstance(REJECTION_REASON_NO_GREEDY_TOKENS, str)
    assert isinstance(FALLBACK_REASON_PARTIAL_ACCEPT, str)
    assert isinstance(FALLBACK_REASON_FULL_REJECT, str)
    assert isinstance(FALLBACK_REASON_EMPTY_CANDIDATE, str)
    assert isinstance(STOP_REASON_NO_PROGRESS_ERROR, str)


def test_verification_decision_is_frozen() -> None:
    """VerificationDecision must be immutable."""
    decision = compare_candidate_to_greedy([1, 2], [1, 2])
    with pytest.raises((AttributeError, TypeError)):
        decision.matched_verifier_token_count = 999  # type: ignore[misc]


def test_verifier_cycle_trace_instantiation() -> None:
    """VerifierCycleTrace must be constructable with required fields."""
    trace = VerifierCycleTrace(
        cycle_index=0,
        candidate_text="hello world",
        candidate_normalized_text="hello world",
        candidate_verifier_token_ids=[1, 2],
        candidate_verifier_token_count=2,
        verifier_greedy_token_ids=[1, 2],
        verifier_greedy_token_count=2,
        matched_verifier_token_count=2,
        first_rejection_position=None,
        verification_result=VERIFICATION_FULL_ACCEPT,
        rejection_reason=None,
        fallback_reason=None,
        accepted_target_token_count=2,
        rejected_target_token_count=0,
        unused_suffix_token_count=0,
        fallback_token_id=None,
        context_update_source=CONTEXT_UPDATE_FULL_ACCEPT,
    )
    assert trace.cycle_index == 0
    assert trace.verification_result == VERIFICATION_FULL_ACCEPT
    assert trace.comparison_profile == "strict_token_level_v1"


# ---------------------------------------------------------------------------
# 14. Forbidden field names guard
# ---------------------------------------------------------------------------


def test_verification_decision_has_no_forbidden_field_names() -> None:
    """No qwen_*, gemma_*, acceptance_rate, or accepted_blocks fields."""
    decision = compare_candidate_to_greedy([1, 2], [1, 2])
    attrs = dir(decision)

    forbidden = [
        "qwen_token_ids",
        "gemma_token_ids",
        "accepted_qwen_tokens",
        "accepted_blocks",
        "acceptance_rate",
        "speedup",
        "lossless",
        "target_equivalent",
        "correctness_validated",
    ]
    for name in forbidden:
        assert name not in attrs, f"Forbidden field found: {name!r}"
