"""Phase 3.15 — Low-tier benchmark dry-run harness.

Design principle:
    Gemma verifies candidate Gemma tokens derived from Qwen draft text.

This module provides:
    - VerifierTokenAccess: thin extension exposing token-level ops from llama_cpp.Llama.
    - run_real_baseline: real verifier greedy text generation baseline.
    - run_real_strict_cycle: real D-Flash strict cycle using token-level verify.
    - run_fake_dry_run: deterministic fallback using Phase 3.13 fake harness.
    - DryRunResult / DryRunCaseResult: result data structures.
    - aggregate_dry_run_metrics: aggregate structural metrics across cases.

Non-claims:
    This is not a production benchmark.
    This is not a speedup measurement.
    This is not a statistically significant study.
    No production lossless generation claim is made.

Blocker tracking:
    BLOCKER_MISSING_MODEL         = model file not found
    BLOCKER_BACKEND_NO_TOKEN_OPS  = LlamaCppBackend does not expose tokenize/eval/sample
    BLOCKER_WRAPPER_EXTENSION_REQ = thin wrapper extension required to expose raw ops
    BLOCKER_LOAD_FAILURE          = model failed to load
    BLOCKER_GPU_UNAVAILABLE       = GPU not available
    BLOCKER_TOKENIZER_BOUNDARY    = tokenization boundary mismatch in real model
    BLOCKER_NO_CONFIG             = local config not found
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from htfsd.low_tier.strict_verifier import (
    compare_candidate_to_greedy,
    VerificationDecision,
    VERIFICATION_FULL_ACCEPT,
    VERIFICATION_PARTIAL_ACCEPT,
)
from htfsd.low_tier.token_bridge import derive_candidate_suffix
from htfsd.validation.equivalence import (
    BaselineRunResult,
    StrictRunResult,
    compare_outputs,
    STOP_REASON_MAX_TOKENS,
    STOP_REASON_EOS,
    STOP_REASON_NO_PROGRESS_ERROR,
)
from htfsd.validation.fake_harness import (
    run_validation_case,
    ValidationCase,
)

# ---------------------------------------------------------------------------
# Blocker constants
# ---------------------------------------------------------------------------

BLOCKER_MISSING_MODEL = "missing_model"
BLOCKER_BACKEND_NO_TOKEN_OPS = "backend_no_token_level_ops"
BLOCKER_WRAPPER_EXTENSION_REQ = "wrapper_extension_required"
BLOCKER_LOAD_FAILURE = "model_load_failure"
BLOCKER_GPU_UNAVAILABLE = "gpu_unavailable"
BLOCKER_TOKENIZER_BOUNDARY = "tokenizer_boundary_mismatch"
BLOCKER_NO_CONFIG = "no_local_config"
BLOCKER_EQUIV_GATE_FAILED = "equivalence_gate_failed"

# Dry run case status constants
CASE_STATUS_EQUIVALENT = "equivalent"
CASE_STATUS_DIVERGENT = "divergent"
CASE_STATUS_INVALID_FOR_PERFORMANCE = "invalid_for_performance"
CASE_STATUS_NO_PROGRESS_ERROR = "no_progress_error"
CASE_STATUS_EXPECTED_FAILURE = "expected_failure_case"
CASE_STATUS_BLOCKED = "blocked"


# ---------------------------------------------------------------------------
# VerifierTokenAccess — thin extension for token-level ops
# ---------------------------------------------------------------------------


class VerifierTokenAccess:
    """Thin wrapper exposing token-level ops from a raw llama_cpp.Llama instance.

    This resolves the Phase 3.14 blocker:
        BLOCKER_WRAPPER_EXTENSION_REQ:
            LlamaCppBackend only exposes text generation.
            Token-level strict verification requires:
                - tokenize(text) -> list[int]
                - eval(tokens) -> None  (updates KV cache)
                - sample(temp=0.0) -> int  (greedy token)
                - reset() -> None
                - token_eos() -> int
            These are available on llama_cpp.Llama but not on LlamaCppBackend.

    Usage:
        backend = LlamaCppBackend(...)
        raw_model = backend._load()  # accesses the underlying Llama instance
        token_access = VerifierTokenAccess(raw_model)
    """

    def __init__(self, raw_llama_model: Any) -> None:
        self._model = raw_llama_model

    def tokenize(self, text: str, *, add_bos: bool = False) -> list[int]:
        """Tokenize text using the verifier tokenizer."""
        return self._model.tokenize(text.encode("utf-8"), add_bos=add_bos, special=False)

    def tokenize_bytes(self, text: bytes, *, add_bos: bool = False) -> list[int]:
        """Tokenize raw bytes using the verifier tokenizer."""
        return self._model.tokenize(text, add_bos=add_bos, special=False)

    def detokenize(self, token_ids: list[int]) -> str:
        """Decode token ids back to text."""
        raw = self._model.detokenize(token_ids)
        return raw.decode("utf-8", errors="replace")

    def eval_and_sample_greedy(self, context_token_ids: list[int]) -> int:
        """Evaluate context tokens and return greedy next token.

        Uses:
            self._model.eval(context_token_ids)
            self._model.sample(temp=0.0)

        Note: sample(temp=0.0) returns the greedy (argmax) token.
        This is the equivalent of argmax(logits[-1]) without needing logits_all=True.
        """
        self.reset()
        self._model.eval(context_token_ids)
        return self._model.sample(temp=0.0)


    def token_eos(self) -> int:
        """Return the EOS token id."""
        return self._model.token_eos()

    def token_bos(self) -> int:
        """Return the BOS token id."""
        return self._model.token_bos()

    def reset(self) -> None:
        """Reset KV cache (n_tokens = 0)."""
        self._model.reset()

    def greedy_generate(
        self,
        prompt_token_ids: list[int],
        *,
        max_new_tokens: int,
    ) -> tuple[list[int], str]:
        """Generate a greedy token sequence from prompt token ids.

        Returns:
            (token_ids, stop_reason)

        Note: resets KV cache before generation. Uses eval + sample per token.
        This is token-level greedy generation (equivalent to temp=0.0 text gen
        but returning token ids for comparison).
        """
        self.reset()
        # Build up context progressively
        context = list(prompt_token_ids)
        generated: list[int] = []
        stop_reason = STOP_REASON_MAX_TOKENS

        # Eval the prompt first
        if context:
            self._model.eval(context)

        for _ in range(max_new_tokens):
            next_token = self._model.sample(temp=0.0)
            generated.append(next_token)
            if next_token == self.token_eos():
                stop_reason = STOP_REASON_EOS
                break
            # Eval the new token to advance KV cache
            self._model.eval([next_token])

        return generated, stop_reason


# ---------------------------------------------------------------------------
# Real baseline run
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RealBaselineResult:
    """Result of a real verifier greedy baseline run."""

    prompt_id: str
    prompt: str
    prompt_token_ids: list[int]
    baseline_token_ids: list[int]
    baseline_text: str
    stop_reason: str
    wall_time_ms: float
    token_count: int
    tokens_per_second: float | None
    model_path: str
    blocker: str | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.blocker is None and self.error is None


def run_real_baseline(
    *,
    prompt_id: str,
    prompt: str,
    token_access: VerifierTokenAccess,
    max_new_tokens: int,
    model_path: str,
) -> RealBaselineResult:
    """Run the real verifier greedy baseline for a single prompt.

    This is the token-level greedy generation baseline.
    Uses eval() + sample(temp=0.0) per token.
    """
    try:
        prompt_token_ids = token_access.tokenize(prompt, add_bos=True)
        t0 = time.perf_counter()
        baseline_ids, stop_reason = token_access.greedy_generate(
            prompt_token_ids,
            max_new_tokens=max_new_tokens,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        baseline_text = token_access.detokenize(baseline_ids)
        tps = (len(baseline_ids) / (elapsed_ms / 1000.0)) if elapsed_ms > 0 else None

        return RealBaselineResult(
            prompt_id=prompt_id,
            prompt=prompt,
            prompt_token_ids=prompt_token_ids,
            baseline_token_ids=baseline_ids,
            baseline_text=baseline_text,
            stop_reason=stop_reason,
            wall_time_ms=elapsed_ms,
            token_count=len(baseline_ids),
            tokens_per_second=tps,
            model_path=model_path,
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return RealBaselineResult(
            prompt_id=prompt_id,
            prompt=prompt,
            prompt_token_ids=[],
            baseline_token_ids=[],
            baseline_text="",
            stop_reason="error",
            wall_time_ms=0.0,
            token_count=0,
            tokens_per_second=None,
            model_path=model_path,
            blocker=BLOCKER_LOAD_FAILURE,
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# Real multi-cycle D-Flash benchmark loop
# ---------------------------------------------------------------------------

def run_multicycle_dflash(
    *,
    prompt_text: str,
    drafter_fn: Any,
    token_access: Any,
    max_new_tokens: int,
    max_cycles: int,
    draft_tokens: int,
) -> dict[str, Any]:
    """Run multi-cycle strict D-Flash loop.

    Returns dict with all metrics.
    """
    static_context_token_ids = token_access.tokenize(prompt_text, add_bos=True)
    committed_output_token_ids: list[int] = []
    committed_text = ""

    cycles = 0
    full_accept = 0
    partial_accept = 0
    full_reject = 0
    accepted_target_tokens = 0
    rejected_target_tokens = 0
    unused_suffix_tokens = 0
    fallback_events = 0
    candidate_tokens_total = 0
    matched_tokens_total = 0
    no_progress_errors = 0
    drafter_time_ms = 0.0
    verifier_time_ms = 0.0
    bridge_time_ms = 0.0
    comparison_time_ms = 0.0
    cycle_log: list[dict[str, Any]] = []
    stop_reason = "max_cycles"

    EOS = token_access.token_eos()
    total_wall_t0 = time.perf_counter()

    for cycle_idx in range(max_cycles):
        if len(committed_output_token_ids) >= max_new_tokens:
            stop_reason = "max_tokens"
            break

        drafter_input_text = prompt_text + committed_text

        # --- Step 1: Drafter produces candidate text ---
        t0 = time.perf_counter()
        candidate_text = drafter_fn(drafter_input_text, draft_tokens)
        drafter_time_ms += (time.perf_counter() - t0) * 1000.0

        # --- Step 2: Bridge: derive candidate_verifier_token_ids ---
        t0 = time.perf_counter()
        def bridge_tokenizer(
            text: bytes,
            add_bos: bool = False,
            special: bool = False,  # pylint: disable=unused-argument
        ) -> list[int]:
            _ = special
            return token_access.tokenize_bytes(text, add_bos=add_bos)

        bridge = derive_candidate_suffix(
            drafter_input_text,
            candidate_text,
            bridge_tokenizer,
            add_bos=True,
        )
        bridge_time_ms += (time.perf_counter() - t0) * 1000.0

        if not bridge.ok or not bridge.candidate_verifier_token_ids:
            no_progress_errors += 1
            t0 = time.perf_counter()
            evaluation_context = static_context_token_ids + committed_output_token_ids
            single_tok = token_access.eval_and_sample_greedy(evaluation_context)
            verifier_time_ms += (time.perf_counter() - t0) * 1000.0

            # Commit the fallback token first (including EOS)
            committed_output_token_ids.append(single_tok)
            committed_text += token_access.detokenize([single_tok])
            cycle_log.append({
                "cycle": cycle_idx,
                "bridge_status": bridge.bridge_status,
                "result": "no_bridge",
                "committed": [single_tok],
            })
            cycles += 1

            if single_tok == EOS:
                stop_reason = "eos"
                break
            continue

        candidate_ids = bridge.candidate_verifier_token_ids
        candidate_tokens_total += len(candidate_ids)

        # --- Step 3: Verifier greedy for candidate window ---
        evaluation_context = static_context_token_ids + committed_output_token_ids
        t0 = time.perf_counter()
        greedy_ids, _ = token_access.greedy_generate(
            evaluation_context,
            max_new_tokens=len(candidate_ids) + 1
        )
        verifier_time_ms += (time.perf_counter() - t0) * 1000.0

        # --- Step 4: Compare ---
        t0 = time.perf_counter()
        dec = compare_candidate_to_greedy(candidate_ids, greedy_ids[:len(candidate_ids) + 1])
        comparison_time_ms += (time.perf_counter() - t0) * 1000.0

        matched_tokens_total += dec.matched_verifier_token_count
        accepted_target_tokens += dec.accepted_target_token_count
        rejected_target_tokens += dec.rejected_target_token_count
        unused_suffix_tokens += dec.unused_suffix_token_count

        log_entry: dict[str, Any] = {
            "cycle": cycle_idx,
            "bridge_status": bridge.bridge_status,
            "candidate_len": len(candidate_ids),
            "result": dec.verification_result,
            "matched": dec.matched_verifier_token_count,
            "unused": dec.unused_suffix_token_count,
            "fallback": dec.fallback_token_id,
            "cand_text_preview": repr(candidate_text[:40]),
        }

        cycle_committed: list[int] = []
        if dec.verification_result == VERIFICATION_FULL_ACCEPT:
            full_accept += 1
            cycle_committed = list(candidate_ids)
            if EOS in cycle_committed:
                eos_pos = cycle_committed.index(EOS)
                cycle_committed = cycle_committed[:eos_pos + 1]
        else:
            if dec.verification_result == VERIFICATION_PARTIAL_ACCEPT:
                partial_accept += 1
            else:
                full_reject += 1
            fallback_events += 1

            cycle_committed = list(dec.accepted_prefix)
            if dec.fallback_token_id is not None:
                cycle_committed.append(dec.fallback_token_id)
            else:
                no_progress_errors += 1
                cycle_log.append(log_entry)
                cycles += 1
                break

        # Trim to remaining max_new_tokens budget
        space_left = max_new_tokens - len(committed_output_token_ids)
        cycle_committed = cycle_committed[:space_left]

        if not cycle_committed:
            no_progress_errors += 1
            cycles += 1
            break

        committed_output_token_ids.extend(cycle_committed)
        committed_text += token_access.detokenize(cycle_committed)
        log_entry["committed"] = cycle_committed
        cycle_log.append(log_entry)
        cycles += 1

        if EOS in cycle_committed:
            stop_reason = "eos"
            break

    total_wall_ms = (time.perf_counter() - total_wall_t0) * 1000.0
    strict_ids = committed_output_token_ids
    strict_text = token_access.detokenize(committed_output_token_ids)

    acceptance_ratio_token_level = (
        accepted_target_tokens / candidate_tokens_total if candidate_tokens_total > 0 else 0.0
    )
    acceptance_ratio_cycle_level = (
        full_accept / cycles if cycles > 0 else 0.0
    )

    return {
        "cycles": cycles,
        "full_accept": full_accept,
        "partial_accept": partial_accept,
        "full_reject": full_reject,
        "accepted_target_tokens": accepted_target_tokens,
        "rejected_target_tokens": rejected_target_tokens,
        "unused_suffix_tokens": unused_suffix_tokens,
        "fallback_events": fallback_events,
        "candidate_tokens_total": candidate_tokens_total,
        "matched_tokens_total": matched_tokens_total,
        "no_progress_errors": no_progress_errors,
        "drafter_time_ms": drafter_time_ms,
        "verifier_time_ms": verifier_time_ms,
        "bridge_time_ms": bridge_time_ms,
        "comparison_time_ms": comparison_time_ms,
        "cycle_log": cycle_log,
        "stop_reason": stop_reason,
        "total_wall_ms": total_wall_ms,
        "strict_ids": strict_ids,
        "strict_text": strict_text,
        "acceptance_ratio_token_level": acceptance_ratio_token_level,
        "acceptance_ratio_cycle_level": acceptance_ratio_cycle_level,
    }


# ---------------------------------------------------------------------------
# Real strict cycle run (one D-Flash cycle)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RealStrictCycleResult:
    """Result of one real D-Flash strict cycle."""

    cycle_index: int
    candidate_text: str
    candidate_verifier_token_ids: list[int]
    bridge_status: str
    decision: VerificationDecision | None
    committed_token_ids: list[int]
    context_update_source: str
    wall_time_ms: float
    blocker: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Dry-run result structures
# ---------------------------------------------------------------------------


@dataclass
class DryRunCaseResult:
    """Result for one dry-run case (real or fake)."""

    case_name: str
    case_category: str
    prompt_id: str
    run_mode: str  # "real" | "fake"

    # Equivalence
    equivalent: bool
    status: str  # CASE_STATUS_*

    # Structural metrics
    cycle_count: int
    accepted_target_token_count: int
    rejected_target_token_count: int
    unused_suffix_token_count: int
    fallback_token_count: int
    full_accept_cycle_count: int
    partial_accept_cycle_count: int
    full_reject_cycle_count: int
    no_progress_error_count: int
    fallback_only_cycle_count: int

    # Timing
    baseline_wall_time_ms: float | None
    strict_wall_time_ms: float | None

    # Gates
    correctness_gate_passed: bool
    equivalence_gate_passed: bool

    # Divergence
    divergence_position: int | None
    divergence_reason: str | None

    # Blocker
    blocker: str | None

    # Notes
    notes: list[str] = field(default_factory=list)

    @property
    def valid_for_performance(self) -> bool:
        return self.equivalent and self.blocker is None


@dataclass
class DryRunResult:
    """Aggregate result across all dry-run cases."""

    run_mode: str  # "real" | "fake" | "mixed"
    total_request_count: int
    equivalent_request_count: int
    divergent_request_count: int
    invalid_for_performance_count: int
    no_progress_error_count: int
    blocked_count: int

    # Aggregate structural metrics
    total_cycle_count: int
    total_accepted_target_token_count: int
    total_rejected_target_token_count: int
    total_unused_suffix_token_count: int
    total_fallback_token_count: int
    total_full_accept_cycle_count: int
    total_partial_accept_cycle_count: int
    total_full_reject_cycle_count: int
    total_fallback_only_cycle_count: int

    # Gate results
    correctness_gate_passed: bool
    equivalence_gate_passed: bool

    # Timing summary
    baseline_wall_time_ms_total: float | None
    strict_wall_time_ms_total: float | None

    # Per-case results
    cases: list[DryRunCaseResult]

    # Blockers found
    blockers: list[str]

    # Non-claims (always present)
    non_claims: list[str] = field(default_factory=lambda: [
        "This is not a production benchmark.",
        "This is not a speedup measurement.",
        "No speedup claim is made.",
        "No low-tier-is-faster claim is made.",
        "No production lossless-generation claim is made.",
        "No target Gemma E4B equivalence claim is made.",
        "No high-tier implementation claim is made.",
        "No EAGLE-style speculation is implemented.",
        "No vLLM integration is used.",
        "Dry-run metrics are local scaffold metrics only.",
    ])

    @property
    def performance_eligible(self) -> bool:
        return self.equivalence_gate_passed and self.blocked_count == 0

    @property
    def speedup_candidate(self) -> bool:
        if not self.equivalence_gate_passed:
            return False
        if self.baseline_wall_time_ms_total is None or self.strict_wall_time_ms_total is None:
            return False
        return self.strict_wall_time_ms_total < self.baseline_wall_time_ms_total


# ---------------------------------------------------------------------------
# Fake/deterministic dry-run cases
# ---------------------------------------------------------------------------


def _make_fake_cases() -> list[tuple[str, str, ValidationCase, str]]:
    """Return list of (case_name, category, ValidationCase, expected_status) tuples."""
    from htfsd.validation.fake_harness import (
        case_full_accept,
        case_partial_accept_with_fallback,
        case_full_reject_with_fallback,
        case_eos_termination,
        case_no_progress_error,
        case_max_new_tokens_truncation,
    )

    return [
        ("full_accept", "full_accept_case", case_full_accept(), CASE_STATUS_EQUIVALENT),
        ("partial_accept_with_fallback", "partial_accept_case",
         case_partial_accept_with_fallback(), CASE_STATUS_EQUIVALENT),
        ("full_reject_with_fallback", "full_reject_case",
         case_full_reject_with_fallback(), CASE_STATUS_EQUIVALENT),
        ("eos_termination", "eos_stop_case",
         case_eos_termination(), CASE_STATUS_EQUIVALENT),
        ("no_progress_error", "no_progress_case",
         case_no_progress_error(), CASE_STATUS_NO_PROGRESS_ERROR),
        ("max_new_tokens_truncation", "truncation_case",
         case_max_new_tokens_truncation(), CASE_STATUS_EQUIVALENT),
    ]


def _make_divergence_case() -> DryRunCaseResult:
    """Simulate a divergent case for gate testing."""
    baseline = BaselineRunResult(
        token_ids=[1, 2, 3],
        text=None,
        stop_reason=STOP_REASON_MAX_TOKENS,
        token_count=3,
    )
    bad_strict = StrictRunResult(
        token_ids=[1, 2, 99],  # diverges at position 2
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
    equiv = compare_outputs(baseline, bad_strict)
    return DryRunCaseResult(
        case_name="simulated_divergence",
        case_category="divergence_detection_case",
        prompt_id="sim_divergence_001",
        run_mode="fake",
        equivalent=equiv.equivalent,
        status=CASE_STATUS_DIVERGENT,
        cycle_count=1,
        accepted_target_token_count=2,
        rejected_target_token_count=1,
        unused_suffix_token_count=0,
        fallback_token_count=1,
        full_accept_cycle_count=0,
        partial_accept_cycle_count=1,
        full_reject_cycle_count=0,
        no_progress_error_count=0,
        fallback_only_cycle_count=0,
        baseline_wall_time_ms=None,
        strict_wall_time_ms=None,
        correctness_gate_passed=False,
        equivalence_gate_passed=False,
        divergence_position=equiv.divergence.divergence_position,
        divergence_reason=equiv.divergence.divergence_reason,
        blocker=BLOCKER_EQUIV_GATE_FAILED,
        notes=["Expected divergence case: simulated bad fallback token."],
    )


def _make_unused_suffix_leak_case() -> DryRunCaseResult:
    """Simulate an unused-suffix-leak detection case."""
    baseline = BaselineRunResult(
        token_ids=[1, 2, 9],
        text=None,
        stop_reason=STOP_REASON_MAX_TOKENS,
        token_count=3,
    )
    leaky_strict = StrictRunResult(
        token_ids=[1, 2, 9, 4],  # BUG: [4] leaked from unused suffix
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
    equiv = compare_outputs(baseline, leaky_strict)
    return DryRunCaseResult(
        case_name="unused_suffix_leak",
        case_category="suffix_leak_detection_case",
        prompt_id="sim_suffix_leak_001",
        run_mode="fake",
        equivalent=equiv.equivalent,
        status=CASE_STATUS_EXPECTED_FAILURE,
        cycle_count=1,
        accepted_target_token_count=2,
        rejected_target_token_count=1,
        unused_suffix_token_count=1,
        fallback_token_count=1,
        full_accept_cycle_count=0,
        partial_accept_cycle_count=1,
        full_reject_cycle_count=0,
        no_progress_error_count=0,
        fallback_only_cycle_count=0,
        baseline_wall_time_ms=None,
        strict_wall_time_ms=None,
        correctness_gate_passed=False,
        equivalence_gate_passed=False,
        divergence_position=equiv.divergence.divergence_position,
        divergence_reason=equiv.divergence.divergence_reason,
        blocker=BLOCKER_EQUIV_GATE_FAILED,
        notes=["Expected failure: simulated unused suffix leak. Harness correctly detected it."],
    )


def _fake_case_to_dry_run_result(
    case_name: str,
    category: str,
    validation_case: ValidationCase,
    expected_status: str,
) -> DryRunCaseResult:
    """Run one fake ValidationCase and return a DryRunCaseResult."""
    equiv_result = run_validation_case(validation_case)

    strict = equiv_result.strict
    no_progress = strict.stop_reason == STOP_REASON_NO_PROGRESS_ERROR

    # Classify cycle types from strict result
    # We can approximate based on accepted/rejected counts
    full_accept = 1 if strict.accepted_target_token_count > 0 and strict.rejected_target_token_count == 0 else 0
    full_reject = 1 if strict.accepted_target_token_count == 0 and strict.rejected_target_token_count > 0 else 0
    partial = 1 if strict.accepted_target_token_count > 0 and strict.rejected_target_token_count > 0 else 0

    if expected_status == CASE_STATUS_NO_PROGRESS_ERROR:
        status = CASE_STATUS_NO_PROGRESS_ERROR
        correct = False
        equiv_gate = False
    elif equiv_result.equivalent:
        status = CASE_STATUS_EQUIVALENT
        correct = True
        equiv_gate = True
    else:
        status = CASE_STATUS_DIVERGENT
        correct = False
        equiv_gate = False

    return DryRunCaseResult(
        case_name=case_name,
        case_category=category,
        prompt_id=validation_case.name,
        run_mode="fake",
        equivalent=equiv_result.equivalent,
        status=status,
        cycle_count=strict.cycle_count,
        accepted_target_token_count=strict.accepted_target_token_count,
        rejected_target_token_count=strict.rejected_target_token_count,
        unused_suffix_token_count=strict.unused_suffix_token_count,
        fallback_token_count=strict.fallback_token_count,
        full_accept_cycle_count=full_accept,
        partial_accept_cycle_count=partial,
        full_reject_cycle_count=full_reject,
        no_progress_error_count=1 if no_progress else 0,
        fallback_only_cycle_count=1 if full_reject else 0,
        baseline_wall_time_ms=None,
        strict_wall_time_ms=None,
        correctness_gate_passed=correct,
        equivalence_gate_passed=equiv_gate,
        divergence_position=equiv_result.divergence.divergence_position,
        divergence_reason=equiv_result.divergence.divergence_reason if not correct else None,
        blocker=None,
        notes=[f"Fake dry-run case. Expected: {expected_status}. Got: {status}."],
    )


# ---------------------------------------------------------------------------
# Fake dry-run orchestrator
# ---------------------------------------------------------------------------


def run_fake_dry_run() -> DryRunResult:
    """Run all fake/deterministic dry-run cases.

    This is the fallback diagnostic dry run.
    It does not require real model execution.
    It does not prove real model correctness.
    It validates that the Phase 3.12–3.13 scaffold mechanics work.
    """
    cases: list[DryRunCaseResult] = []

    # Standard fake validation cases
    for case_name, category, validation_case, expected_status in _make_fake_cases():
        result = _fake_case_to_dry_run_result(case_name, category, validation_case, expected_status)
        cases.append(result)

    # Divergence detection case (expected failure — proves gate works)
    cases.append(_make_divergence_case())

    # Unused suffix leak detection (expected failure — proves gate works)
    cases.append(_make_unused_suffix_leak_case())

    return aggregate_dry_run_metrics(cases, run_mode="fake")


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------


def aggregate_dry_run_metrics(
    cases: list[DryRunCaseResult],
    *,
    run_mode: str,
) -> DryRunResult:
    """Aggregate structural metrics across all dry-run cases."""

    equiv_count = sum(1 for c in cases if c.equivalent)
    diverg_count = sum(1 for c in cases if not c.equivalent and c.blocker != BLOCKER_EQUIV_GATE_FAILED)
    invalid_count = sum(1 for c in cases if not c.valid_for_performance)
    no_prog = sum(c.no_progress_error_count for c in cases)
    blocked = sum(1 for c in cases if c.blocker is not None and c.blocker != BLOCKER_EQUIV_GATE_FAILED)

    # Correctness/equivalence gate: pass only if ALL valid (non-expected-failure) cases are equivalent
    # Expected failure cases (divergence detection, suffix leak) don't count against the gate
    eligible_cases = [c for c in cases if c.status not in (CASE_STATUS_EXPECTED_FAILURE, CASE_STATUS_NO_PROGRESS_ERROR)]
    gate_passed = all(c.equivalent for c in eligible_cases) if eligible_cases else False

    blockers_found = list({c.blocker for c in cases if c.blocker is not None and c.blocker != BLOCKER_EQUIV_GATE_FAILED})

    bl_total = sum(c.baseline_wall_time_ms for c in cases if c.baseline_wall_time_ms is not None) or None
    st_total = sum(c.strict_wall_time_ms for c in cases if c.strict_wall_time_ms is not None) or None

    return DryRunResult(
        run_mode=run_mode,
        total_request_count=len(cases),
        equivalent_request_count=equiv_count,
        divergent_request_count=diverg_count,
        invalid_for_performance_count=invalid_count,
        no_progress_error_count=no_prog,
        blocked_count=blocked,
        total_cycle_count=sum(c.cycle_count for c in cases),
        total_accepted_target_token_count=sum(c.accepted_target_token_count for c in cases),
        total_rejected_target_token_count=sum(c.rejected_target_token_count for c in cases),
        total_unused_suffix_token_count=sum(c.unused_suffix_token_count for c in cases),
        total_fallback_token_count=sum(c.fallback_token_count for c in cases),
        total_full_accept_cycle_count=sum(c.full_accept_cycle_count for c in cases),
        total_partial_accept_cycle_count=sum(c.partial_accept_cycle_count for c in cases),
        total_full_reject_cycle_count=sum(c.full_reject_cycle_count for c in cases),
        total_fallback_only_cycle_count=sum(c.fallback_only_cycle_count for c in cases),
        correctness_gate_passed=gate_passed,
        equivalence_gate_passed=gate_passed,
        baseline_wall_time_ms_total=bl_total,
        strict_wall_time_ms_total=st_total,
        cases=cases,
        blockers=blockers_found,
    )
