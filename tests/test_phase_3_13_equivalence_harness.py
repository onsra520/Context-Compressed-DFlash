"""Phase 3.13 — Equivalence harness data structure tests.

All tests are pure: no GGUF model, no GPU, no disk access.

Tests cover:
    - EquivalenceResult structure and properties
    - DivergenceReport structure and has_divergence
    - BaselineRunResult and StrictRunResult construction
    - compare_outputs() for equal and divergent sequences
    - compare_outputs() for length mismatch
    - compare_outputs() for stop_reason mismatch
    - check_unused_suffix_leak()
    - make_divergence_from_leaked_suffix()
    - ValidationCase construction
    - Forbidden field names (no speedup, acceptance_rate, etc.)
"""

from __future__ import annotations

import pytest

from htfsd.validation.equivalence import (
    DIVERGENCE_LENGTH_MISMATCH,
    DIVERGENCE_NONE,
    DIVERGENCE_STOP_REASON_MISMATCH,
    DIVERGENCE_TOKEN_MISMATCH,
    DIVERGENCE_UNUSED_SUFFIX_LEAKED,
    EQUIVALENCE_STATUS_DIVERGENT,
    EQUIVALENCE_STATUS_EQUIVALENT,
    STOP_REASON_EOS,
    STOP_REASON_MAX_CYCLES,
    STOP_REASON_MAX_TOKENS,
    BaselineRunResult,
    DivergenceReport,
    EquivalenceResult,
    StrictRunResult,
    ValidationCase,
    check_unused_suffix_leak,
    compare_outputs,
    make_divergence_from_leaked_suffix,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_baseline(token_ids: list[int], stop_reason: str = STOP_REASON_MAX_TOKENS) -> BaselineRunResult:
    return BaselineRunResult(
        token_ids=token_ids,
        text=None,
        stop_reason=stop_reason,
        token_count=len(token_ids),
    )


def _make_strict(
    token_ids: list[int],
    stop_reason: str = STOP_REASON_MAX_TOKENS,
    cycle_count: int = 1,
    accepted: int = 0,
    rejected: int = 0,
    unused: int = 0,
    fallback: int = 0,
    no_progress: int = 0,
    warnings: list[str] | None = None,
) -> StrictRunResult:
    return StrictRunResult(
        token_ids=token_ids,
        text=None,
        stop_reason=stop_reason,
        token_count=len(token_ids),
        cycle_count=cycle_count,
        accepted_target_token_count=accepted,
        rejected_target_token_count=rejected,
        unused_suffix_token_count=unused,
        fallback_token_count=fallback,
        no_progress_cycles=no_progress,
        warnings=warnings or [],
    )


# ---------------------------------------------------------------------------
# 1. Equivalent outputs
# ---------------------------------------------------------------------------


def test_compare_outputs_equivalent_sequences() -> None:
    baseline = _make_baseline([1, 2, 3])
    strict = _make_strict([1, 2, 3])
    result = compare_outputs(baseline, strict)

    assert result.equivalent
    assert result.status == EQUIVALENCE_STATUS_EQUIVALENT
    assert result.divergence.divergence_reason == DIVERGENCE_NONE
    assert result.divergence.divergence_position is None
    assert not result.divergence.has_divergence


def test_compare_outputs_empty_sequences_equivalent() -> None:
    baseline = _make_baseline([], STOP_REASON_MAX_CYCLES)
    strict = _make_strict([], STOP_REASON_MAX_CYCLES)
    result = compare_outputs(baseline, strict)

    assert result.equivalent


def test_compare_outputs_single_token_match() -> None:
    baseline = _make_baseline([42])
    strict = _make_strict([42])
    result = compare_outputs(baseline, strict)

    assert result.equivalent


# ---------------------------------------------------------------------------
# 2. Divergent outputs — token mismatch
# ---------------------------------------------------------------------------


def test_compare_outputs_first_token_mismatch() -> None:
    baseline = _make_baseline([1, 2, 3])
    strict = _make_strict([9, 2, 3])
    result = compare_outputs(baseline, strict)

    assert result.divergent
    assert result.divergence.divergence_position == 0
    assert result.divergence.divergence_reason == DIVERGENCE_TOKEN_MISMATCH
    assert result.divergence.baseline_token == 1
    assert result.divergence.strict_token == 9


def test_compare_outputs_middle_token_mismatch() -> None:
    baseline = _make_baseline([1, 2, 3])
    strict = _make_strict([1, 9, 3])
    result = compare_outputs(baseline, strict)

    assert result.divergent
    assert result.divergence.divergence_position == 1
    assert result.divergence.baseline_token == 2
    assert result.divergence.strict_token == 9


def test_compare_outputs_last_token_mismatch() -> None:
    baseline = _make_baseline([1, 2, 3])
    strict = _make_strict([1, 2, 9])
    result = compare_outputs(baseline, strict)

    assert result.divergent
    assert result.divergence.divergence_position == 2


# ---------------------------------------------------------------------------
# 3. Divergent outputs — length mismatch
# ---------------------------------------------------------------------------


def test_compare_outputs_strict_longer_than_baseline() -> None:
    baseline = _make_baseline([1, 2, 3])
    strict = _make_strict([1, 2, 3, 4])  # extra token
    result = compare_outputs(baseline, strict)

    assert result.divergent
    assert result.divergence.divergence_reason == DIVERGENCE_LENGTH_MISMATCH
    assert result.divergence.divergence_position == 3  # first out-of-range position


def test_compare_outputs_strict_shorter_than_baseline() -> None:
    baseline = _make_baseline([1, 2, 3])
    strict = _make_strict([1, 2])  # missing token
    result = compare_outputs(baseline, strict)

    assert result.divergent
    assert result.divergence.divergence_reason == DIVERGENCE_LENGTH_MISMATCH


# ---------------------------------------------------------------------------
# 4. Stop reason mismatch
# ---------------------------------------------------------------------------


def test_compare_outputs_stop_reason_mismatch_is_warning_not_divergence() -> None:
    """Stop reason mismatch is recorded as a warning, not a token divergence."""
    baseline = _make_baseline([1, 2, 3], stop_reason=STOP_REASON_EOS)
    strict = _make_strict([1, 2, 3], stop_reason=STOP_REASON_MAX_TOKENS)
    result = compare_outputs(baseline, strict)

    # Tokens match → still equivalent
    assert result.equivalent
    # But a warning is recorded
    assert any("stop_reason_mismatch" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# 5. EquivalenceResult properties
# ---------------------------------------------------------------------------


def test_equivalence_result_equivalent_property() -> None:
    baseline = _make_baseline([1, 2])
    strict = _make_strict([1, 2])
    result = compare_outputs(baseline, strict)

    assert result.equivalent is True
    assert result.divergent is False


def test_equivalence_result_divergent_property() -> None:
    baseline = _make_baseline([1, 2])
    strict = _make_strict([9, 2])
    result = compare_outputs(baseline, strict)

    assert result.divergent is True
    assert result.equivalent is False


def test_equivalence_result_is_frozen() -> None:
    baseline = _make_baseline([1, 2])
    strict = _make_strict([1, 2])
    result = compare_outputs(baseline, strict)

    with pytest.raises((AttributeError, TypeError)):
        result.status = "divergent"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 6. DivergenceReport
# ---------------------------------------------------------------------------


def test_divergence_report_has_divergence_none() -> None:
    report = DivergenceReport(
        divergence_position=None,
        divergence_reason=DIVERGENCE_NONE,
        baseline_token=None,
        strict_token=None,
        detail="No divergence.",
    )
    assert not report.has_divergence


def test_divergence_report_has_divergence_token_mismatch() -> None:
    report = DivergenceReport(
        divergence_position=2,
        divergence_reason=DIVERGENCE_TOKEN_MISMATCH,
        baseline_token=5,
        strict_token=9,
        detail="mismatch",
    )
    assert report.has_divergence


def test_make_divergence_from_leaked_suffix() -> None:
    report = make_divergence_from_leaked_suffix(position=3, suffix_token=99)
    assert report.divergence_reason == DIVERGENCE_UNUSED_SUFFIX_LEAKED
    assert report.divergence_position == 3
    assert report.strict_token == 99
    assert report.has_divergence


# ---------------------------------------------------------------------------
# 7. check_unused_suffix_leak
# ---------------------------------------------------------------------------


def test_check_unused_suffix_leak_no_leak() -> None:
    committed = [1, 2, 9]
    unused_suffix = [4]
    assert not check_unused_suffix_leak(committed, unused_suffix)


def test_check_unused_suffix_leak_detects_tail_match() -> None:
    """If the tail of committed exactly matches the unused suffix, it's a leak."""
    committed = [1, 2, 9, 4]  # [4] is the unused suffix — leaked
    unused_suffix = [4]
    assert check_unused_suffix_leak(committed, unused_suffix)


def test_check_unused_suffix_leak_multi_token() -> None:
    committed = [1, 2, 9, 100, 200]  # [100, 200] leaked
    unused_suffix = [100, 200]
    assert check_unused_suffix_leak(committed, unused_suffix)


def test_check_unused_suffix_leak_empty_suffix() -> None:
    assert not check_unused_suffix_leak([1, 2, 3], [])


def test_check_unused_suffix_leak_empty_committed() -> None:
    assert not check_unused_suffix_leak([], [4])


# ---------------------------------------------------------------------------
# 8. BaselineRunResult
# ---------------------------------------------------------------------------


def test_baseline_from_token_ids() -> None:
    baseline = BaselineRunResult.from_token_ids([1, 2, 3])
    assert baseline.token_ids == [1, 2, 3]
    assert baseline.token_count == 3
    assert baseline.text is None


def test_baseline_is_frozen() -> None:
    baseline = _make_baseline([1, 2])
    with pytest.raises((AttributeError, TypeError)):
        baseline.token_count = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 9. StrictRunResult
# ---------------------------------------------------------------------------


def test_strict_run_result_construction() -> None:
    strict = _make_strict([1, 2, 9], accepted=2, rejected=1, unused=2, fallback=1, cycle_count=2)
    assert strict.token_ids == [1, 2, 9]
    assert strict.accepted_target_token_count == 2
    assert strict.rejected_target_token_count == 1
    assert strict.unused_suffix_token_count == 2
    assert strict.fallback_token_count == 1


def test_strict_run_result_is_frozen() -> None:
    strict = _make_strict([1, 2])
    with pytest.raises((AttributeError, TypeError)):
        strict.token_count = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 10. ValidationCase
# ---------------------------------------------------------------------------


def test_validation_case_construction() -> None:
    case = ValidationCase(
        name="test_case",
        baseline_token_ids=[1, 2, 3],
        candidate_batches=[[1, 2, 3]],
        expected_strict_token_ids=[1, 2, 3],
        expected_equivalent=True,
    )
    assert case.name == "test_case"
    assert case.expected_equivalent is True
    assert case.max_new_tokens == 32  # default
    assert case.max_cycles == 16      # default


# ---------------------------------------------------------------------------
# 11. Forbidden field names
# ---------------------------------------------------------------------------


def test_equivalence_result_no_forbidden_fields() -> None:
    baseline = _make_baseline([1, 2])
    strict = _make_strict([1, 2])
    result = compare_outputs(baseline, strict)
    attrs = dir(result)

    forbidden = [
        "speedup",
        "acceptance_rate",
        "tokens_per_second",
        "performance_gain",
        "lossless",
        "target_equivalent",
        "benchmark_score",
    ]
    for name in forbidden:
        assert name not in attrs, f"Forbidden field found: {name!r}"


def test_strict_run_result_no_forbidden_fields() -> None:
    strict = _make_strict([1])
    attrs = dir(strict)

    forbidden = ["speedup", "acceptance_rate", "tokens_per_second", "performance_gain"]
    for name in forbidden:
        assert name not in attrs, f"Forbidden field found: {name!r}"
