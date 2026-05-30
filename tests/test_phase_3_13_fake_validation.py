"""Phase 3.13 — Fake harness end-to-end validation tests.

All tests are pure: no GGUF model, no GPU, no disk access.
Uses run_fake_baseline(), run_fake_strict(), run_validation_case(), and
the predefined ValidationCase fixtures from fake_harness.

Tests cover:
    1.  strict output equals baseline for full accept
    2.  strict output equals baseline for partial accept + fallback
    3.  strict output equals baseline for full reject + fallback
    4.  strict output does NOT include unused suffix
    5.  harness detects unused suffix leak
    6.  harness detects wrong fallback (divergent case)
    7.  harness detects output length mismatch
    8.  harness reports first divergence position correctly
    9.  max_new_tokens truncates output consistently
    10. max_cycles bound is respected
    11. no_progress_error reported when no fallback available
    12. EOS token terminates generation normally
    13. fallback-only cycles produce warnings
    14. repeated fallback-only cycles are warning-worthy (not speedup)
    15. CycleRecord tracks cycle decisions correctly
"""

from __future__ import annotations

import pytest

from htfsd.validation.equivalence import (
    DIVERGENCE_NONE,
    EQUIVALENCE_STATUS_DIVERGENT,
    EQUIVALENCE_STATUS_EQUIVALENT,
    STOP_REASON_EOS,
    STOP_REASON_MAX_CYCLES,
    STOP_REASON_MAX_TOKENS,
    STOP_REASON_NO_PROGRESS_ERROR,
    WARNING_REPEATED_FALLBACK,
    BaselineRunResult,
    compare_outputs,
)
from htfsd.validation.fake_harness import (
    FAKE_EOS_TOKEN_ID,
    CycleRecord,
    case_eos_termination,
    case_full_accept,
    case_full_reject_with_fallback,
    case_max_new_tokens_truncation,
    case_no_progress_error,
    case_partial_accept_with_fallback,
    case_unused_suffix_leak_detection,
    run_fake_baseline,
    run_fake_strict,
    run_validation_case,
)


# ---------------------------------------------------------------------------
# 1. Full accept: strict equals baseline
# ---------------------------------------------------------------------------


def test_full_accept_strict_equals_baseline() -> None:
    """All candidate tokens match greedy: strict output == baseline output."""
    result = run_validation_case(case_full_accept())

    assert result.equivalent
    assert result.strict.token_ids == [1, 2, 3]
    assert result.baseline.token_ids == [1, 2, 3]


def test_full_accept_no_fallback_used() -> None:
    """Full accept: no fallback tokens should be used."""
    result = run_validation_case(case_full_accept())

    assert result.strict.fallback_token_count == 0
    assert result.strict.rejected_target_token_count == 0


def test_full_accept_no_divergence() -> None:
    result = run_validation_case(case_full_accept())

    assert result.divergence.divergence_reason == DIVERGENCE_NONE
    assert result.divergence.divergence_position is None


# ---------------------------------------------------------------------------
# 2. Partial accept + fallback: strict equals baseline
# ---------------------------------------------------------------------------


def test_partial_accept_with_fallback_strict_equals_baseline() -> None:
    """Partial accept then accept: [1,2] + fallback 9 + [8,7] = [1,2,9,8,7]."""
    result = run_validation_case(case_partial_accept_with_fallback())

    assert result.equivalent
    assert result.strict.token_ids == [1, 2, 9, 8, 7]
    assert result.baseline.token_ids == [1, 2, 9, 8, 7]


def test_partial_accept_uses_one_fallback() -> None:
    result = run_validation_case(case_partial_accept_with_fallback())

    assert result.strict.fallback_token_count == 1
    assert result.strict.accepted_target_token_count == 4  # 2 in cycle0 + 2 in cycle1


def test_partial_accept_unused_suffix_not_in_output() -> None:
    """Unused suffix token [4] must NOT appear in the strict output."""
    result = run_validation_case(case_partial_accept_with_fallback())

    # Token 4 is the unused suffix in cycle 0 — must not be in strict output
    assert 4 not in result.strict.token_ids


# ---------------------------------------------------------------------------
# 3. Full reject + fallback: strict equals baseline
# ---------------------------------------------------------------------------


def test_full_reject_with_fallback_strict_equals_baseline() -> None:
    """Full reject then accept: fallback 9 + [8,7] = [9,8,7]."""
    result = run_validation_case(case_full_reject_with_fallback())

    assert result.equivalent
    assert result.strict.token_ids == [9, 8, 7]
    assert result.baseline.token_ids == [9, 8, 7]


def test_full_reject_unused_suffix_not_in_output() -> None:
    """Unused suffix [2,3] must NOT appear in strict output."""
    result = run_validation_case(case_full_reject_with_fallback())

    assert 2 not in result.strict.token_ids  # rejected suffix token
    assert 3 not in result.strict.token_ids  # rejected suffix token


# ---------------------------------------------------------------------------
# 4. Strict does not include unused suffix (explicit check)
# ---------------------------------------------------------------------------


def test_strict_does_not_include_unused_suffix() -> None:
    """Direct check: run strict with known unused suffix and verify it's absent."""
    strict_result, cycle_records = run_fake_strict(
        baseline_token_ids=[1, 2, 9, 8, 7],
        candidate_batches=[[1, 2, 3, 4]],   # accept [1,2], reject 3, unused=[4]
        max_new_tokens=32,
    )
    # Strict should have committed [1, 2, 9] (accepted prefix + fallback)
    assert 4 not in strict_result.token_ids
    # Unused suffix count is tracked
    assert strict_result.unused_suffix_token_count == 1


# ---------------------------------------------------------------------------
# 5. Harness detects unused suffix leak
# ---------------------------------------------------------------------------


def test_harness_detects_unused_suffix_leak_via_compare_outputs() -> None:
    """Simulate a bad implementation that includes unused suffix in output."""
    # Correct baseline: [1, 2, 9]
    baseline = BaselineRunResult(
        token_ids=[1, 2, 9],
        text=None,
        stop_reason=STOP_REASON_MAX_TOKENS,
        token_count=3,
    )
    from htfsd.validation.equivalence import StrictRunResult
    # BAD strict: includes unused suffix token 4
    bad_strict = StrictRunResult(
        token_ids=[1, 2, 9, 4],    # BUG: [4] leaked from unused suffix
        text=None,
        stop_reason=STOP_REASON_MAX_TOKENS,
        token_count=4,
        cycle_count=1,
        accepted_target_token_count=2,
        rejected_target_token_count=1,
        unused_suffix_token_count=1,
        fallback_token_count=1,
        no_progress_cycles=0,
        warnings=[],
    )
    result = compare_outputs(baseline, bad_strict)

    assert result.divergent
    assert result.status == EQUIVALENCE_STATUS_DIVERGENT
    # Length mismatch catches it first
    from htfsd.validation.equivalence import DIVERGENCE_LENGTH_MISMATCH
    assert result.divergence.divergence_reason == DIVERGENCE_LENGTH_MISMATCH


# ---------------------------------------------------------------------------
# 6. Harness detects wrong fallback token
# ---------------------------------------------------------------------------


def test_harness_detects_wrong_fallback_token() -> None:
    """Simulate a bad implementation using the wrong fallback token."""
    baseline = BaselineRunResult(
        token_ids=[1, 2, 9],   # correct: fallback should be 9
        text=None,
        stop_reason=STOP_REASON_MAX_TOKENS,
        token_count=3,
    )
    from htfsd.validation.equivalence import StrictRunResult
    bad_strict = StrictRunResult(
        token_ids=[1, 2, 99],  # BUG: used wrong fallback 99 instead of 9
        text=None,
        stop_reason=STOP_REASON_MAX_TOKENS,
        token_count=3,
        cycle_count=1,
        accepted_target_token_count=2,
        rejected_target_token_count=1,
        unused_suffix_token_count=0,
        fallback_token_count=1,
        no_progress_cycles=0,
        warnings=[],
    )
    result = compare_outputs(baseline, bad_strict)

    assert result.divergent
    from htfsd.validation.equivalence import DIVERGENCE_TOKEN_MISMATCH
    assert result.divergence.divergence_reason == DIVERGENCE_TOKEN_MISMATCH
    assert result.divergence.divergence_position == 2
    assert result.divergence.baseline_token == 9
    assert result.divergence.strict_token == 99


# ---------------------------------------------------------------------------
# 7. Harness detects output length mismatch
# ---------------------------------------------------------------------------


def test_harness_detects_output_length_mismatch() -> None:
    baseline = BaselineRunResult(
        token_ids=[1, 2, 3],
        text=None,
        stop_reason=STOP_REASON_MAX_TOKENS,
        token_count=3,
    )
    from htfsd.validation.equivalence import StrictRunResult, DIVERGENCE_LENGTH_MISMATCH
    short_strict = StrictRunResult(
        token_ids=[1, 2],   # missing token 3
        text=None,
        stop_reason=STOP_REASON_MAX_TOKENS,
        token_count=2,
        cycle_count=1,
        accepted_target_token_count=2,
        rejected_target_token_count=0,
        unused_suffix_token_count=0,
        fallback_token_count=0,
        no_progress_cycles=0,
        warnings=[],
    )
    result = compare_outputs(baseline, short_strict)

    assert result.divergent
    assert result.divergence.divergence_reason == DIVERGENCE_LENGTH_MISMATCH


# ---------------------------------------------------------------------------
# 8. Harness reports first divergence position correctly
# ---------------------------------------------------------------------------


def test_harness_reports_first_divergence_position() -> None:
    baseline = BaselineRunResult(
        token_ids=[1, 2, 3, 4],
        text=None,
        stop_reason=STOP_REASON_MAX_TOKENS,
        token_count=4,
    )
    from htfsd.validation.equivalence import StrictRunResult, DIVERGENCE_TOKEN_MISMATCH
    bad_strict = StrictRunResult(
        token_ids=[1, 2, 99, 4],  # diverges at position 2
        text=None,
        stop_reason=STOP_REASON_MAX_TOKENS,
        token_count=4,
        cycle_count=1,
        accepted_target_token_count=2,
        rejected_target_token_count=1,
        unused_suffix_token_count=0,
        fallback_token_count=1,
        no_progress_cycles=0,
        warnings=[],
    )
    result = compare_outputs(baseline, bad_strict)

    assert result.divergent
    assert result.divergence.divergence_position == 2


# ---------------------------------------------------------------------------
# 9. max_new_tokens truncation
# ---------------------------------------------------------------------------


def test_max_new_tokens_truncates_both_outputs() -> None:
    """max_new_tokens=2 truncates both baseline and strict to [1,2]."""
    result = run_validation_case(case_max_new_tokens_truncation())

    assert result.equivalent
    assert result.baseline.token_ids == [1, 2]
    assert result.strict.token_ids == [1, 2]


def test_max_new_tokens_direct_strict() -> None:
    """Direct test: run_fake_strict with max_new_tokens=3 commits at most 3 tokens."""
    strict_result, _ = run_fake_strict(
        baseline_token_ids=[1, 2, 3, 4, 5, 6],
        candidate_batches=[[1, 2, 3, 4, 5, 6]],
        max_new_tokens=3,
    )
    assert len(strict_result.token_ids) <= 3


# ---------------------------------------------------------------------------
# 10. max_cycles bound is respected
# ---------------------------------------------------------------------------


def test_max_cycles_bound() -> None:
    """max_cycles=2 stops after 2 cycles even if more candidates available."""
    strict_result, cycle_records = run_fake_strict(
        baseline_token_ids=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        candidate_batches=[[1], [2], [3], [4], [5]],  # 5 batches
        max_new_tokens=32,
        max_cycles=2,
    )
    assert strict_result.cycle_count <= 2
    assert len(cycle_records) <= 2


# ---------------------------------------------------------------------------
# 11. no_progress_error
# ---------------------------------------------------------------------------


def test_no_progress_error_empty_baseline_and_candidate() -> None:
    result = run_validation_case(case_no_progress_error())

    # Both baseline and strict are empty
    assert result.baseline.token_ids == []
    assert result.strict.token_ids == []
    assert result.strict.stop_reason == STOP_REASON_NO_PROGRESS_ERROR


def test_no_progress_error_direct_strict() -> None:
    """Empty candidate and no baseline: no_progress_error stop."""
    strict_result, cycle_records = run_fake_strict(
        baseline_token_ids=[],
        candidate_batches=[[]],
        max_new_tokens=32,
    )
    assert strict_result.stop_reason == STOP_REASON_NO_PROGRESS_ERROR
    assert strict_result.no_progress_cycles == 1


# ---------------------------------------------------------------------------
# 12. EOS terminates normally
# ---------------------------------------------------------------------------


def test_eos_terminates_generation() -> None:
    result = run_validation_case(case_eos_termination())

    assert result.equivalent
    assert result.strict.stop_reason == STOP_REASON_EOS
    assert FAKE_EOS_TOKEN_ID in result.strict.token_ids


def test_eos_in_candidate_accepted_and_stops() -> None:
    """EOS token in fully accepted candidate terminates the loop."""
    strict_result, cycle_records = run_fake_strict(
        baseline_token_ids=[1, FAKE_EOS_TOKEN_ID, 3, 4],
        candidate_batches=[[1, FAKE_EOS_TOKEN_ID]],  # full accept up to EOS
        max_new_tokens=32,
    )
    assert strict_result.stop_reason == STOP_REASON_EOS
    assert FAKE_EOS_TOKEN_ID in strict_result.token_ids
    # Tokens after EOS must not appear
    assert 3 not in strict_result.token_ids
    assert 4 not in strict_result.token_ids


# ---------------------------------------------------------------------------
# 13 + 14. Fallback-only cycles produce warnings
# ---------------------------------------------------------------------------


def test_repeated_fallback_only_cycles_produce_warnings() -> None:
    """3+ consecutive fallback-only cycles should generate a warning."""
    # All candidates mismatch → all cycles are fallback-only
    strict_result, cycle_records = run_fake_strict(
        baseline_token_ids=[9, 8, 7, 6, 5],
        candidate_batches=[
            [1],   # full reject → fallback 9
            [1],   # full reject → fallback 8
            [1],   # full reject → fallback 7 (3rd consecutive: warning triggered)
        ],
        max_new_tokens=32,
    )
    # At least one warning about repeated fallback
    has_repeated_fallback_warning = any(
        WARNING_REPEATED_FALLBACK in w for w in strict_result.warnings
    )
    assert has_repeated_fallback_warning


def test_repeated_fallback_does_not_claim_speedup() -> None:
    """Repeated fallback cycles must not create speedup fields."""
    strict_result, _ = run_fake_strict(
        baseline_token_ids=[9, 8, 7, 6, 5],
        candidate_batches=[[1], [1], [1], [1], [1]],
        max_new_tokens=32,
    )
    attrs = dir(strict_result)
    forbidden = ["speedup", "acceptance_rate", "tokens_per_second", "performance_gain"]
    for name in forbidden:
        assert name not in attrs, f"Forbidden field: {name!r}"


# ---------------------------------------------------------------------------
# 15. CycleRecord tracking
# ---------------------------------------------------------------------------


def test_cycle_record_tracks_decision() -> None:
    """CycleRecord must capture the VerificationDecision for each cycle."""
    _, cycle_records = run_fake_strict(
        baseline_token_ids=[1, 2, 9],
        candidate_batches=[[1, 2, 3]],   # partial accept: accept [1,2], reject 3, fallback 9
        max_new_tokens=32,
    )
    assert len(cycle_records) == 1
    record = cycle_records[0]
    assert record.cycle_index == 0
    assert record.candidate_token_ids == [1, 2, 3]
    assert record.decision.matched_verifier_token_count == 2
    assert record.decision.fallback_token_id == 9
    assert record.committed_token_ids == [1, 2, 9]


def test_cycle_record_context_update_source() -> None:
    """CycleRecord.context_update_source must be set correctly."""
    _, cycle_records = run_fake_strict(
        baseline_token_ids=[1, 2, 3],
        candidate_batches=[[1, 2, 3]],   # full accept
        max_new_tokens=32,
    )
    record = cycle_records[0]
    assert record.context_update_source == "full_accept"


# ---------------------------------------------------------------------------
# 16. run_fake_baseline correctness
# ---------------------------------------------------------------------------


def test_run_fake_baseline_respects_max_new_tokens() -> None:
    baseline = run_fake_baseline([1, 2, 3, 4, 5], max_new_tokens=3)
    assert baseline.token_ids == [1, 2, 3]
    assert baseline.token_count == 3


def test_run_fake_baseline_stops_on_eos() -> None:
    baseline = run_fake_baseline([1, FAKE_EOS_TOKEN_ID, 3])
    assert baseline.token_ids == [1, FAKE_EOS_TOKEN_ID]
    assert baseline.stop_reason == STOP_REASON_EOS


def test_run_fake_baseline_empty_sequence() -> None:
    baseline = run_fake_baseline([])
    assert baseline.token_ids == []
    assert baseline.token_count == 0
