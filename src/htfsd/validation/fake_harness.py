"""Phase 3.13 — Fake/deterministic validation harness for D-Flash correctness checking.

Design principle:
    Gemma verifies candidate Gemma tokens derived from Qwen draft text.

This module provides a fake harness that simulates D-Flash cycles without
requiring any real GGUF model. It uses:
    - Deterministic token ID sequences as inputs
    - The real Phase 3.12 comparison algorithm (compare_candidate_to_greedy)
    - Fake baseline and strict runner functions
    - Equivalence comparison from Phase 3.13 equivalence module

Usage for validation:
    1. Provide baseline_token_ids (verifier greedy reference sequence).
    2. Provide candidate_batches (one batch per D-Flash cycle).
    3. run_fake_strict() applies the strict accept/reject algorithm.
    4. compare_outputs() checks strict result against baseline.

This harness validates the correctness of the algorithm under controlled
conditions. It does not validate real model outputs.
Real GGUF/llama-cpp tests are optional and gated by environment variables.

Phase 3.13 does not claim correctness is production-validated.
Phase 3.13 does not measure throughput, speedup, or benchmark results.
Phase 3.13 does not implement high-tier or vLLM.
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from typing import Iterator

from htfsd.low_tier.strict_verifier import (
    STOP_REASON_NO_PROGRESS_ERROR,
    VERIFICATION_FULL_ACCEPT,
    VerificationDecision,
    compare_candidate_to_greedy,
    select_context_update_source,
)
from htfsd.validation.equivalence import (
    DIVERGENCE_NONE,
    EQUIVALENCE_STATUS_EQUIVALENT,
    STOP_REASON_EOS,
    STOP_REASON_MAX_CYCLES,
    STOP_REASON_MAX_TOKENS,
    WARNING_REPEATED_FALLBACK,
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
# EOS sentinel
# ---------------------------------------------------------------------------

# Fake EOS token for harness use. In real GGUF: llama.token_eos().
# Using 999 to avoid collisions with small integer test token ids (1, 2, 3, ...).
FAKE_EOS_TOKEN_ID = 999


# ---------------------------------------------------------------------------
# Fake baseline runner
# ---------------------------------------------------------------------------


def run_fake_baseline(
    baseline_token_ids: list[int],
    max_new_tokens: int = 32,
    eos_token_id: int = FAKE_EOS_TOKEN_ID,
) -> BaselineRunResult:
    """Simulate a verifier greedy baseline run using a predetermined token sequence.

    The baseline is the reference: what the verifier would produce if run greedily
    on the full prompt without any drafter involvement.

    Args:
        baseline_token_ids: Full predetermined greedy output sequence.
        max_new_tokens:     Token budget. Truncates if needed.
        eos_token_id:       EOS token id (stops generation if encountered).

    Returns:
        BaselineRunResult with token_ids, stop_reason, and token_count.
    """
    output: list[int] = []
    stop_reason = STOP_REASON_MAX_TOKENS

    for tok in baseline_token_ids:
        output.append(tok)
        if tok == eos_token_id:
            stop_reason = STOP_REASON_EOS
            break
        if len(output) >= max_new_tokens:
            stop_reason = STOP_REASON_MAX_TOKENS
            break

    return BaselineRunResult(
        token_ids=output,
        text=None,
        stop_reason=stop_reason,
        token_count=len(output),
    )


# ---------------------------------------------------------------------------
# Fake strict runner
# ---------------------------------------------------------------------------


@dataclass
class CycleRecord:
    """Internal record for a single D-Flash cycle in the fake harness."""

    cycle_index: int
    candidate_token_ids: list[int]
    decision: VerificationDecision
    committed_token_ids: list[int]
    context_update_source: str
    unused_suffix_detected: bool
    warning: str | None


def run_fake_strict(
    baseline_token_ids: list[int],
    candidate_batches: list[list[int]],
    max_new_tokens: int = 32,
    max_cycles: int = 16,
    eos_token_id: int = FAKE_EOS_TOKEN_ID,
) -> tuple[StrictRunResult, list[CycleRecord]]:
    """Run the strict D-Flash accept/reject algorithm over a sequence of candidate batches.

    This is the core simulation loop for the fake harness.

    Algorithm per cycle:
        1. Take the next candidate batch (candidate_verifier_token_ids).
        2. Take the next greedy tokens from baseline_token_ids at current offset.
        3. Call compare_candidate_to_greedy().
        4. Commit accepted prefix + fallback token to output.
        5. Discard unused suffix (never entered into output).
        6. Advance baseline offset by (accepted + 1 for fallback or accepted for full_accept).

    Args:
        baseline_token_ids: Full predetermined verifier greedy sequence.
        candidate_batches:  One list of token IDs per D-Flash cycle.
        max_new_tokens:     Token budget across all cycles.
        max_cycles:         Cycle count limit.
        eos_token_id:       EOS token id.

    Returns:
        (StrictRunResult, list[CycleRecord])
    """
    committed: list[int] = []
    cycle_records: list[CycleRecord] = []
    baseline_offset = 0

    total_accepted = 0
    total_rejected = 0
    total_unused = 0
    total_fallback = 0
    no_progress_cycles = 0
    run_warnings: list[str] = []
    consecutive_fallback_only = 0
    stop_reason = STOP_REASON_MAX_CYCLES

    for cycle_idx in range(min(max_cycles, len(candidate_batches))):
        if len(committed) >= max_new_tokens:
            stop_reason = STOP_REASON_MAX_TOKENS
            break

        candidate_ids = candidate_batches[cycle_idx]

        # Greedy window from the baseline at current offset
        remaining_budget = max_new_tokens - len(committed)
        greedy_window = baseline_token_ids[baseline_offset : baseline_offset + max(len(candidate_ids) + 1, remaining_budget)]

        # Run the strict comparison
        decision = compare_candidate_to_greedy(candidate_ids, greedy_window)

        if decision.no_progress:
            no_progress_cycles += 1
            run_warnings.append(f"cycle {cycle_idx}: no_progress_error")
            cycle_records.append(CycleRecord(
                cycle_index=cycle_idx,
                candidate_token_ids=list(candidate_ids),
                decision=decision,
                committed_token_ids=[],
                context_update_source=select_context_update_source(decision),
                unused_suffix_detected=False,
                warning="no_progress_error",
            ))
            stop_reason = STOP_REASON_NO_PROGRESS_ERROR
            break

        # Build the committed tokens for this cycle
        cycle_committed: list[int] = []

        # Accept prefix
        cycle_committed.extend(decision.accepted_prefix)
        total_accepted += decision.accepted_target_token_count

        # Advance baseline offset by accepted tokens
        baseline_offset += decision.accepted_target_token_count

        # Fallback token (if needed)
        if decision.fallback_token_id is not None:
            cycle_committed.append(decision.fallback_token_id)
            total_fallback += 1
            baseline_offset += 1  # consumed one greedy token as fallback

        total_rejected += decision.rejected_target_token_count
        total_unused += decision.unused_suffix_token_count

        # Check for repeated fallback-only cycles
        if decision.accepted_target_token_count == 0 and decision.fallback_token_id is not None:
            consecutive_fallback_only += 1
            if consecutive_fallback_only >= 3:
                run_warnings.append(
                    f"{WARNING_REPEATED_FALLBACK}: {consecutive_fallback_only} consecutive cycles"
                )
        else:
            consecutive_fallback_only = 0

        # Unused suffix leak detection (guard: unused suffix must NOT enter committed)
        unused_leaked = check_unused_suffix_leak(
            committed + cycle_committed,
            decision.unused_suffix,
        )

        # Trim to max_new_tokens
        space_left = max_new_tokens - len(committed)
        cycle_committed = cycle_committed[:space_left]
        committed.extend(cycle_committed)

        cycle_records.append(CycleRecord(
            cycle_index=cycle_idx,
            candidate_token_ids=list(candidate_ids),
            decision=decision,
            committed_token_ids=list(cycle_committed),
            context_update_source=select_context_update_source(decision),
            unused_suffix_detected=unused_leaked,
            warning=WARNING_REPEATED_FALLBACK if consecutive_fallback_only >= 3 else None,
        ))

        # EOS check
        if committed and committed[-1] == eos_token_id:
            stop_reason = STOP_REASON_EOS
            break

        if len(committed) >= max_new_tokens:
            stop_reason = STOP_REASON_MAX_TOKENS
            break
    else:
        # Exhausted candidate_batches without filling max_new_tokens
        stop_reason = STOP_REASON_MAX_CYCLES

    strict_result = StrictRunResult(
        token_ids=list(committed),
        text=None,
        stop_reason=stop_reason,
        token_count=len(committed),
        cycle_count=len(cycle_records),
        accepted_target_token_count=total_accepted,
        rejected_target_token_count=total_rejected,
        unused_suffix_token_count=total_unused,
        fallback_token_count=total_fallback,
        no_progress_cycles=no_progress_cycles,
        warnings=run_warnings,
    )
    return strict_result, cycle_records


# ---------------------------------------------------------------------------
# ValidationCase runner
# ---------------------------------------------------------------------------


def run_validation_case(case: ValidationCase) -> EquivalenceResult:
    """Run a complete ValidationCase through the fake harness and compare outputs.

    This is the primary entry point for harness-based unit tests.
    No model required.

    Args:
        case: A ValidationCase with baseline, candidate batches, and expectations.

    Returns:
        EquivalenceResult with status, divergence report, and any warnings.
    """
    # Run the fake baseline
    baseline_result = run_fake_baseline(
        baseline_token_ids=case.baseline_token_ids,
        max_new_tokens=case.max_new_tokens,
    )

    # Run the fake strict path
    strict_result, _cycle_records = run_fake_strict(
        baseline_token_ids=case.baseline_token_ids,
        candidate_batches=case.candidate_batches,
        max_new_tokens=case.max_new_tokens,
        max_cycles=case.max_cycles,
    )

    # Compare outputs
    result = compare_outputs(baseline_result, strict_result)
    return result


# ---------------------------------------------------------------------------
# Predefined ValidationCase fixtures
# ---------------------------------------------------------------------------


def case_full_accept() -> ValidationCase:
    """Full accept: all candidate tokens match greedy baseline."""
    return ValidationCase(
        name="full_accept",
        baseline_token_ids=[1, 2, 3],
        candidate_batches=[[1, 2, 3]],
        expected_strict_token_ids=[1, 2, 3],
        expected_equivalent=True,
        expected_stop_reason=STOP_REASON_MAX_CYCLES,
        description="All candidate tokens match baseline: strict should equal baseline.",
    )


def case_partial_accept_with_fallback() -> ValidationCase:
    """Partial accept + fallback: accepted prefix + verifier greedy fallback."""
    return ValidationCase(
        name="partial_accept_with_fallback",
        baseline_token_ids=[1, 2, 9, 8, 7],
        candidate_batches=[
            [1, 2, 3, 4],   # cycle 0: accept [1,2], reject 3, fallback=9, unused=[4]
            [8, 7],          # cycle 1: accept [8,7]
        ],
        expected_strict_token_ids=[1, 2, 9, 8, 7],
        expected_equivalent=True,
        expected_stop_reason=STOP_REASON_MAX_CYCLES,
        description="Partial accept then full accept: strict matches baseline.",
    )


def case_full_reject_with_fallback() -> ValidationCase:
    """Full reject on first token, fallback, then accept."""
    return ValidationCase(
        name="full_reject_with_fallback",
        baseline_token_ids=[9, 8, 7],
        candidate_batches=[
            [1, 2, 3],   # cycle 0: reject all, fallback=9, unused=[2,3]
            [8, 7],       # cycle 1: accept [8,7]
        ],
        expected_strict_token_ids=[9, 8, 7],
        expected_equivalent=True,
        expected_stop_reason=STOP_REASON_MAX_CYCLES,
        description="Full reject then accept: strict matches baseline via fallback.",
    )


def case_max_new_tokens_truncation() -> ValidationCase:
    """max_new_tokens truncates output."""
    return ValidationCase(
        name="max_new_tokens_truncation",
        baseline_token_ids=[1, 2, 3, 4, 5],
        candidate_batches=[[1, 2, 3, 4, 5]],
        expected_strict_token_ids=[1, 2],
        expected_equivalent=True,
        max_new_tokens=2,
        expected_stop_reason=STOP_REASON_MAX_TOKENS,
        description="max_new_tokens=2 truncates both baseline and strict to [1,2].",
    )


def case_unused_suffix_leak_detection() -> ValidationCase:
    """Divergent case: strict incorrectly includes unused suffix token."""
    # This ValidationCase is not run through run_validation_case() normally;
    # it is used directly in tests to verify leak detection.
    return ValidationCase(
        name="unused_suffix_leak_detection",
        baseline_token_ids=[1, 2, 9],
        candidate_batches=[[1, 2, 3, 4]],  # accept [1,2], reject 3, unused=[4]
        expected_strict_token_ids=[1, 2, 9],  # CORRECT: unused [4] must not appear
        expected_equivalent=True,
        description="Unused suffix [4] must NOT appear in strict output.",
    )


def case_eos_termination() -> ValidationCase:
    """EOS token terminates generation normally."""
    return ValidationCase(
        name="eos_termination",
        baseline_token_ids=[1, FAKE_EOS_TOKEN_ID],
        candidate_batches=[[1, FAKE_EOS_TOKEN_ID]],
        expected_strict_token_ids=[1, FAKE_EOS_TOKEN_ID],
        expected_equivalent=True,
        expected_stop_reason=STOP_REASON_EOS,
        description="EOS token in accepted prefix terminates generation.",
    )


def case_no_progress_error() -> ValidationCase:
    """No candidate tokens, no greedy fallback: no_progress_error."""
    return ValidationCase(
        name="no_progress_error",
        baseline_token_ids=[],   # no greedy tokens → no fallback
        candidate_batches=[[]],   # empty candidate
        expected_strict_token_ids=[],
        expected_equivalent=True,
        expected_stop_reason=STOP_REASON_NO_PROGRESS_ERROR,
        description="Empty baseline and candidate: no_progress_error.",
    )
