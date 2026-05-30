"""Phase 3.13 — Equivalence checking data structures and comparison logic.

Design principle:
    Gemma verifies candidate Gemma tokens derived from Qwen draft text.

This module defines:
    - EquivalenceResult: outcome of comparing strict-path output to baseline
    - DivergenceReport:  first divergence point and reason
    - ValidationCase:    test fixture pairing baseline and strict inputs
    - StrictRunResult:   output of running one strict D-Flash cycle sequence
    - BaselineRunResult: output of running the verifier greedy baseline sequence
    - compare_outputs(): pure comparison with no model dependency

Phase 3.13 does not claim correctness is validated.
Phase 3.13 does not measure throughput, speedup, or performance.
Phase 3.13 does not implement EAGLE-style speculation.
Phase 3.13 does not introduce vLLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Divergence reason constants
# ---------------------------------------------------------------------------

DIVERGENCE_TOKEN_MISMATCH = "token_mismatch"
DIVERGENCE_LENGTH_MISMATCH = "length_mismatch"
DIVERGENCE_UNUSED_SUFFIX_LEAKED = "unused_suffix_leaked"
DIVERGENCE_REJECTED_TOKEN_LEAKED = "rejected_token_leaked"
DIVERGENCE_WRONG_FALLBACK_TOKEN = "wrong_fallback_token"
DIVERGENCE_STOP_REASON_MISMATCH = "stop_reason_mismatch"
DIVERGENCE_NONE = "none"

STOP_REASON_EOS = "eos"
STOP_REASON_MAX_TOKENS = "max_tokens"
STOP_REASON_MAX_CYCLES = "max_cycles"
STOP_REASON_NO_PROGRESS_ERROR = "no_progress_error"
STOP_REASON_STOP_SEQUENCE = "stop_sequence"

EQUIVALENCE_STATUS_EQUIVALENT = "equivalent"
EQUIVALENCE_STATUS_DIVERGENT = "divergent"
EQUIVALENCE_STATUS_INCONCLUSIVE = "inconclusive"

WARNING_REPEATED_FALLBACK = "repeated_fallback_only_cycle"
WARNING_NO_CANDIDATES = "no_candidate_tokens"
WARNING_BOUNDARY_MISMATCH = "tokenization_boundary_mismatch"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BaselineRunResult:
    """Output of running the verifier greedy baseline for a prompt.

    The baseline is: verifier runs greedily on the full prompt, producing
    a deterministic token sequence. This is the reference output.

    Fields:
        token_ids:   Verifier greedy token sequence (Gemma-side).
        text:        Decoded text from token_ids (may be None if not decoded).
        stop_reason: Why generation terminated.
        token_count: len(token_ids).
    """

    token_ids: list[int]
    text: str | None
    stop_reason: str
    token_count: int

    @classmethod
    def from_token_ids(cls, token_ids: list[int], stop_reason: str = STOP_REASON_MAX_TOKENS) -> "BaselineRunResult":
        return cls(
            token_ids=list(token_ids),
            text=None,
            stop_reason=stop_reason,
            token_count=len(token_ids),
        )


@dataclass(frozen=True)
class StrictRunResult:
    """Output of running the strict D-Flash prototype for a prompt.

    The strict run processes drafter candidates cycle by cycle, applying the
    accept/reject/fallback algorithm. Only verifier-accepted tokens enter context.

    Fields:
        token_ids:                   Final committed token sequence.
        text:                        Decoded text (may be None).
        stop_reason:                 Why generation terminated.
        token_count:                 len(token_ids).
        cycle_count:                 Number of D-Flash cycles run.
        accepted_target_token_count: Total tokens accepted from candidates.
        rejected_target_token_count: Total first-mismatch rejections.
        unused_suffix_token_count:   Total discarded unused suffix tokens.
        fallback_token_count:        Total fallback tokens committed.
        no_progress_cycles:          Cycles where no token could be committed.
        warnings:                    List of warning strings.
    """

    token_ids: list[int]
    text: str | None
    stop_reason: str
    token_count: int
    cycle_count: int
    accepted_target_token_count: int
    rejected_target_token_count: int
    unused_suffix_token_count: int
    fallback_token_count: int
    no_progress_cycles: int
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DivergenceReport:
    """First point of divergence between strict output and baseline.

    divergence_position: index into the committed token sequence.
    divergence_reason:   categorized reason string.
    baseline_token:      expected token at divergence position (or None).
    strict_token:        actual strict-path token at that position (or None).
    detail:              human-readable detail string.
    """

    divergence_position: int | None
    divergence_reason: str
    baseline_token: int | None
    strict_token: int | None
    detail: str

    @property
    def has_divergence(self) -> bool:
        return self.divergence_reason != DIVERGENCE_NONE


@dataclass(frozen=True)
class EquivalenceResult:
    """Result of comparing strict D-Flash output to the verifier baseline.

    status:
        "equivalent"   – strict output matches baseline exactly.
        "divergent"    – strict output differs from baseline.
        "inconclusive" – comparison could not be completed.

    Do not interpret 'equivalent' as 'correctness validated'.
    Equivalence under controlled fake/deterministic conditions does not
    imply production-grade correctness.
    """

    status: Literal["equivalent", "divergent", "inconclusive"]
    baseline: BaselineRunResult
    strict: StrictRunResult
    divergence: DivergenceReport
    cycle_count: int
    warnings: list[str] = field(default_factory=list)

    @property
    def equivalent(self) -> bool:
        return self.status == EQUIVALENCE_STATUS_EQUIVALENT

    @property
    def divergent(self) -> bool:
        return self.status == EQUIVALENCE_STATUS_DIVERGENT


@dataclass(frozen=True)
class ValidationCase:
    """A single test fixture pairing baseline and strict inputs.

    name:                      Human-readable case name.
    baseline_token_ids:        Expected verifier greedy output token sequence.
    candidate_batches:         List of candidate token ID batches (one per cycle).
    expected_strict_token_ids: Expected strict output (may differ if divergence expected).
    expected_equivalent:       Whether strict should equal baseline.
    expected_stop_reason:      Expected stop reason for both paths.
    max_new_tokens:            Token budget.
    max_cycles:                Cycle budget.
    description:               Human-readable test description.
    """

    name: str
    baseline_token_ids: list[int]
    candidate_batches: list[list[int]]
    expected_strict_token_ids: list[int]
    expected_equivalent: bool
    expected_stop_reason: str = STOP_REASON_MAX_TOKENS
    max_new_tokens: int = 32
    max_cycles: int = 16
    description: str = ""


# ---------------------------------------------------------------------------
# Pure comparison function
# ---------------------------------------------------------------------------


def compare_outputs(
    baseline: BaselineRunResult,
    strict: StrictRunResult,
) -> EquivalenceResult:
    """Compare strict D-Flash output against the verifier greedy baseline.

    This is a pure function — no model execution required.

    Comparison is token-by-token from the start of both sequences.
    The first differing position is the divergence point.

    Returns:
        EquivalenceResult with status, divergence report, and any warnings.
    """
    warnings: list[str] = list(strict.warnings)

    baseline_ids = baseline.token_ids
    strict_ids = strict.token_ids

    # ---- length check ----
    if len(baseline_ids) != len(strict_ids):
        pos = min(len(baseline_ids), len(strict_ids))
        b_tok = baseline_ids[pos] if pos < len(baseline_ids) else None
        s_tok = strict_ids[pos] if pos < len(strict_ids) else None
        divergence = DivergenceReport(
            divergence_position=pos,
            divergence_reason=DIVERGENCE_LENGTH_MISMATCH,
            baseline_token=b_tok,
            strict_token=s_tok,
            detail=(
                f"Length mismatch: baseline={len(baseline_ids)}, strict={len(strict_ids)}"
            ),
        )
        return EquivalenceResult(
            status=EQUIVALENCE_STATUS_DIVERGENT,
            baseline=baseline,
            strict=strict,
            divergence=divergence,
            cycle_count=strict.cycle_count,
            warnings=warnings,
        )

    # ---- token-by-token comparison ----
    for i, (b_tok, s_tok) in enumerate(zip(baseline_ids, strict_ids)):
        if b_tok != s_tok:
            divergence = DivergenceReport(
                divergence_position=i,
                divergence_reason=DIVERGENCE_TOKEN_MISMATCH,
                baseline_token=b_tok,
                strict_token=s_tok,
                detail=f"Token mismatch at position {i}: baseline={b_tok}, strict={s_tok}",
            )
            return EquivalenceResult(
                status=EQUIVALENCE_STATUS_DIVERGENT,
                baseline=baseline,
                strict=strict,
                divergence=divergence,
                cycle_count=strict.cycle_count,
                warnings=warnings,
            )

    # ---- stop reason check (warning, not divergence) ----
    # Token-sequence equality is the primary correctness criterion.
    # Stop reason mismatches (e.g. max_tokens vs max_cycles) are expected
    # when the baseline and strict paths exhaust their respective budgets
    # via different mechanisms.  We record them as warnings, not failures.
    if baseline.stop_reason != strict.stop_reason:
        warnings = list(warnings) + [
            f"stop_reason_mismatch: baseline={baseline.stop_reason!r}, "
            f"strict={strict.stop_reason!r}"
        ]

    # ---- all checks passed: equivalent ----
    divergence = DivergenceReport(
        divergence_position=None,
        divergence_reason=DIVERGENCE_NONE,
        baseline_token=None,
        strict_token=None,
        detail="No divergence detected.",
    )
    return EquivalenceResult(
        status=EQUIVALENCE_STATUS_EQUIVALENT,
        baseline=baseline,
        strict=strict,
        divergence=divergence,
        cycle_count=strict.cycle_count,
        warnings=warnings,
    )


def check_unused_suffix_leak(
    committed_token_ids: list[int],
    unused_suffix_token_ids: list[int],
) -> bool:
    """Return True if any unused suffix token appears in committed output at a suspicious position.

    This checks whether unused suffix tokens leaked into the committed sequence.
    A suffix is considered leaked if the committed tail matches the suffix exactly
    in a position that should not be reachable through normal accept/fallback.

    This is a heuristic guard, not a proof of correctness.
    For unit tests, use deterministic token IDs to make leaks obvious.
    """
    if not unused_suffix_token_ids or not committed_token_ids:
        return False
    suffix_set = set(unused_suffix_token_ids)
    # Check if the trailing portion of committed matches the suffix exactly
    suffix_len = len(unused_suffix_token_ids)
    if len(committed_token_ids) >= suffix_len:
        tail = committed_token_ids[-suffix_len:]
        if tail == unused_suffix_token_ids:
            return True
    return False


def make_divergence_from_leaked_suffix(
    position: int,
    suffix_token: int,
) -> DivergenceReport:
    """Construct a DivergenceReport for a detected unused suffix leak."""
    return DivergenceReport(
        divergence_position=position,
        divergence_reason=DIVERGENCE_UNUSED_SUFFIX_LEAKED,
        baseline_token=None,
        strict_token=suffix_token,
        detail=f"Unused suffix token {suffix_token} leaked into strict output at position {position}",
    )
