"""Phase 3.12 — Strict acceptance/rejection prototype for D-Flash low-tier path.

Design principle:
    Gemma verifies candidate Gemma tokens derived from Qwen draft text.

This module contains:
    - Immutable data structures for verification decisions.
    - Pure comparison function (no model dependency).
    - Fallback token selection.
    - Unused suffix accounting.

No GGUF model execution is required in this module.
The pure functions here are the safest, independently testable core of Phase 3.12.

Naming follows canonical role conventions:
    drafter_*   = Qwen3-0.6B side
    verifier_*  = Gemma E2B side
    target_*    = reserved for Phase 4.0+ (Gemma E4B)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERIFICATION_FULL_ACCEPT = "full_accept"
VERIFICATION_PARTIAL_ACCEPT = "partial_accept"
VERIFICATION_FULL_REJECT = "full_reject"

REJECTION_REASON_TOKEN_MISMATCH = "token_mismatch"
REJECTION_REASON_EMPTY_CANDIDATE = "empty_candidate"
REJECTION_REASON_NO_GREEDY_TOKENS = "no_greedy_tokens"

FALLBACK_REASON_PARTIAL_ACCEPT = "partial_accept_fallback"
FALLBACK_REASON_FULL_REJECT = "full_reject_fallback"
FALLBACK_REASON_EMPTY_CANDIDATE = "empty_candidate_fallback"

STOP_REASON_EOS = "eos"
STOP_REASON_STOP_SEQUENCE = "stop_sequence"
STOP_REASON_MAX_TOKENS = "max_tokens"
STOP_REASON_NO_PROGRESS_ERROR = "no_progress_error"

CONTEXT_UPDATE_FULL_ACCEPT = "full_accept"
CONTEXT_UPDATE_ACCEPTED_PREFIX = "accepted_prefix"
CONTEXT_UPDATE_FALLBACK_ONLY = "fallback_only"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerificationDecision:
    """Result of comparing candidate verifier tokens against verifier greedy tokens.

    This is the output of compare_candidate_to_greedy().

    Naming:
        candidate_verifier_token_ids:  Gemma-tokenized candidate derived from drafter text.
        verifier_greedy_token_ids:     Gemma greedy decisions from the verifier model.
        matched_verifier_token_count:  Tokens accepted from the candidate prefix.
        first_rejection_position:      Index of first mismatch (None = full accept).
        accepted_target_token_count:   Alias for matched_verifier_token_count (verifier-side).
        rejected_target_token_count:   1 if any mismatch, else 0.
        unused_suffix_token_count:     Candidate tokens discarded after first mismatch.
        fallback_token_id:             Verifier greedy token at first_rejection_position.

    Accounting invariant:
        rejected_target_token_count counts exactly the mismatching token position, not the
        unused suffix.  unused_suffix_token_count tracks the discarded remainder separately.
    """

    candidate_verifier_token_ids: list[int]
    verifier_greedy_token_ids: list[int]
    verification_result: Literal["full_accept", "partial_accept", "full_reject"]
    matched_verifier_token_count: int
    first_rejection_position: int | None
    accepted_target_token_count: int
    rejected_target_token_count: int
    unused_suffix_token_count: int
    fallback_token_id: int | None
    rejection_reason: str | None
    fallback_reason: str | None
    stop_reason: str | None

    @property
    def accepted_prefix(self) -> list[int]:
        """Token ids accepted from the candidate."""
        if self.first_rejection_position is None:
            return list(self.candidate_verifier_token_ids)
        return list(self.candidate_verifier_token_ids[: self.first_rejection_position])

    @property
    def unused_suffix(self) -> list[int]:
        """Candidate tokens discarded after first mismatch (never reused)."""
        if self.first_rejection_position is None:
            return []
        return list(self.candidate_verifier_token_ids[self.first_rejection_position + 1 :])

    @property
    def no_progress(self) -> bool:
        """True when no token can be committed this cycle."""
        return self.stop_reason == STOP_REASON_NO_PROGRESS_ERROR


@dataclass(frozen=True)
class VerifierCycleTrace:
    """Prototype-level trace for a single D-Flash verification cycle.

    All fields are design-level / prototype-level.
    Do not emit acceptance_rate, speedup, lossless, or correctness_validated.
    """

    cycle_index: int
    candidate_text: str
    candidate_normalized_text: str
    candidate_verifier_token_ids: list[int]
    candidate_verifier_token_count: int
    verifier_greedy_token_ids: list[int]
    verifier_greedy_token_count: int
    matched_verifier_token_count: int
    first_rejection_position: int | None
    verification_result: str
    rejection_reason: str | None
    fallback_reason: str | None
    accepted_target_token_count: int
    rejected_target_token_count: int
    unused_suffix_token_count: int
    fallback_token_id: int | None
    context_update_source: str
    comparison_profile: str = "strict_token_level_v1"
    backend_capability_status: dict[str, str] = field(default_factory=dict)
    deterministic_settings: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pure comparison algorithm
# ---------------------------------------------------------------------------


def compare_candidate_to_greedy(
    candidate_verifier_token_ids: list[int],
    verifier_greedy_token_ids: list[int],
) -> VerificationDecision:
    """Compare candidate verifier tokens against verifier greedy tokens.

    This pure function implements the D-Flash strict accept/reject algorithm.
    It requires no model execution.

    D-Flash accounting rules:
        - Accepted prefix: longest matching token sequence from the left.
        - First mismatch: that candidate position is rejected.
        - Unused suffix: candidate tokens after the rejected position — discarded.
        - Fallback: verifier_greedy_token_ids[first_rejection_position].
        - rejected_target_token_count = 1 per rejection event (not len(unused_suffix)).
        - unused_suffix_token_count is tracked separately.

    Args:
        candidate_verifier_token_ids:
            Gemma-side token ids derived from drafter candidate text.
            Must be tokenized with the verifier (Gemma) tokenizer.
        verifier_greedy_token_ids:
            Gemma greedy token decisions from the verifier model.

    Returns:
        VerificationDecision with full accounting.
    """
    # ---- empty candidate ----
    if not candidate_verifier_token_ids:
        fallback_token_id = verifier_greedy_token_ids[0] if verifier_greedy_token_ids else None
        stop_reason = None if fallback_token_id is not None else STOP_REASON_NO_PROGRESS_ERROR
        fallback_reason = FALLBACK_REASON_EMPTY_CANDIDATE if fallback_token_id is not None else None
        return VerificationDecision(
            candidate_verifier_token_ids=[],
            verifier_greedy_token_ids=list(verifier_greedy_token_ids),
            verification_result=VERIFICATION_FULL_REJECT,
            matched_verifier_token_count=0,
            first_rejection_position=None,
            accepted_target_token_count=0,
            rejected_target_token_count=0,
            unused_suffix_token_count=0,
            fallback_token_id=fallback_token_id,
            rejection_reason=REJECTION_REASON_EMPTY_CANDIDATE,
            fallback_reason=fallback_reason,
            stop_reason=stop_reason,
        )

    # ---- no greedy tokens available ----
    if not verifier_greedy_token_ids:
        return VerificationDecision(
            candidate_verifier_token_ids=list(candidate_verifier_token_ids),
            verifier_greedy_token_ids=[],
            verification_result=VERIFICATION_FULL_REJECT,
            matched_verifier_token_count=0,
            first_rejection_position=0,
            accepted_target_token_count=0,
            rejected_target_token_count=0,
            unused_suffix_token_count=len(candidate_verifier_token_ids) - 1,
            fallback_token_id=None,
            rejection_reason=REJECTION_REASON_NO_GREEDY_TOKENS,
            fallback_reason=None,
            stop_reason=STOP_REASON_NO_PROGRESS_ERROR,
        )

    # ---- token-by-token comparison ----
    matched = 0
    n_compare = min(len(candidate_verifier_token_ids), len(verifier_greedy_token_ids))
    first_mismatch_pos: int | None = None

    for i in range(n_compare):
        if candidate_verifier_token_ids[i] == verifier_greedy_token_ids[i]:
            matched += 1
        else:
            first_mismatch_pos = i
            break

    # If we exhausted the compare window without mismatch, check if candidate is longer
    if first_mismatch_pos is None and matched == n_compare:
        if len(candidate_verifier_token_ids) > len(verifier_greedy_token_ids):
            # Candidate is longer than greedy window — treat excess as mismatch
            first_mismatch_pos = n_compare

    # ---- full accept ----
    if first_mismatch_pos is None:
        return VerificationDecision(
            candidate_verifier_token_ids=list(candidate_verifier_token_ids),
            verifier_greedy_token_ids=list(verifier_greedy_token_ids),
            verification_result=VERIFICATION_FULL_ACCEPT,
            matched_verifier_token_count=matched,
            first_rejection_position=None,
            accepted_target_token_count=matched,
            rejected_target_token_count=0,
            unused_suffix_token_count=0,
            fallback_token_id=None,
            rejection_reason=None,
            fallback_reason=None,
            stop_reason=None,
        )

    # ---- partial accept or full reject ----
    pos = first_mismatch_pos

    # Unused suffix: candidate tokens after the rejected position
    unused_suffix_start = pos + 1
    unused_suffix_count = max(0, len(candidate_verifier_token_ids) - unused_suffix_start)

    # Fallback token: verifier greedy decision at the rejection position
    fallback_token_id: int | None = (
        verifier_greedy_token_ids[pos] if pos < len(verifier_greedy_token_ids) else None
    )

    # If fallback is not available (verifier_greedy_token_ids is shorter), no progress
    stop_reason = None if fallback_token_id is not None else STOP_REASON_NO_PROGRESS_ERROR

    if matched > 0:
        result = VERIFICATION_PARTIAL_ACCEPT
        fallback_reason = FALLBACK_REASON_PARTIAL_ACCEPT
    else:
        result = VERIFICATION_FULL_REJECT
        fallback_reason = FALLBACK_REASON_FULL_REJECT

    if fallback_token_id is None:
        fallback_reason = None

    return VerificationDecision(
        candidate_verifier_token_ids=list(candidate_verifier_token_ids),
        verifier_greedy_token_ids=list(verifier_greedy_token_ids),
        verification_result=result,
        matched_verifier_token_count=matched,
        first_rejection_position=pos,
        accepted_target_token_count=matched,
        rejected_target_token_count=1,
        unused_suffix_token_count=unused_suffix_count,
        fallback_token_id=fallback_token_id,
        rejection_reason=REJECTION_REASON_TOKEN_MISMATCH,
        fallback_reason=fallback_reason,
        stop_reason=stop_reason,
    )


# ---------------------------------------------------------------------------
# Context update
# ---------------------------------------------------------------------------


def select_context_update_source(decision: VerificationDecision) -> str:
    """Return the context update source label for a given VerificationDecision."""
    if decision.verification_result == VERIFICATION_FULL_ACCEPT:
        return CONTEXT_UPDATE_FULL_ACCEPT
    if decision.matched_verifier_token_count > 0:
        return CONTEXT_UPDATE_ACCEPTED_PREFIX
    return CONTEXT_UPDATE_FALLBACK_ONLY
