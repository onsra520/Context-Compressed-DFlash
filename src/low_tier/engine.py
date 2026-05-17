"""Low Tier decoding engine for Qwen D-Flash drafts and Gemma verification."""

from __future__ import annotations

from importlib import import_module
import time
from typing import Protocol

from config import clamp_dflash_max_tokens
from dflash.parser import parse_dflash
from metrics.counters import GenerationCounter
from metrics.timers import timer_ms
from tokenization.gemma import RetokenizedDraft

_types = import_module("htfsd_types")
CycleTrace = _types.CycleTrace
GenerateResult = _types.GenerateResult
TokenResult = _types.TokenResult
VerificationResult = _types.VerificationResult


class Drafter(Protocol):  # pylint: disable=too-few-public-methods
    """Protocol for D-Flash draft producers."""

    def draft(self, context_text: str, *, max_tokens: int) -> str:
        """Generate a raw D-Flash draft envelope from decoded context text."""

        raise NotImplementedError


class TokenizerBoundary(Protocol):
    """Tokenizer operations required by the Low Tier engine."""

    @property
    def eos_token_id(self) -> int | None:
        """Return the tokenizer EOS token ID when available."""

        raise NotImplementedError

    def encode_prompt(self, prompt: str) -> list[int]:
        """Encode the initial user prompt into verifier token IDs."""

        raise NotImplementedError

    def retokenize_draft(self, draft_text: str, *, max_tokens: int) -> RetokenizedDraft:
        """Encode D-Flash draft text into verifier candidate token IDs."""

        raise NotImplementedError

    def decode(self, token_ids: list[int]) -> str:
        """Decode verifier token IDs into text."""

        raise NotImplementedError


class Verifier(Protocol):
    """Verifier operations required by the Low Tier engine."""

    def verify_greedy_prefix(
        self,
        context_token_ids: list[int],
        candidate_token_ids: list[int],
    ) -> VerificationResult:
        """Verify candidate token IDs against the verifier greedy path."""

        raise NotImplementedError

    def greedy_next_token(self, context_token_ids: list[int]) -> TokenResult:
        """Return one greedy fallback token for the current context."""

        raise NotImplementedError


class LowTierEngine:  # pylint: disable=too-few-public-methods
    """Own the Low Tier greedy speculative decoding loop."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        drafter: Drafter,
        verifier: Verifier,
        tokenizer: TokenizerBoundary,
        execution_mode: str,
        default_draft_max_tokens: int,
        hard_draft_max_tokens: int,
    ) -> None:
        self._drafter = drafter
        self._verifier = verifier
        self._tokenizer = tokenizer
        self._execution_mode = execution_mode
        self._default_draft_max_tokens = default_draft_max_tokens
        self._hard_draft_max_tokens = hard_draft_max_tokens

    def generate(  # pylint: disable=too-many-arguments,too-many-locals,too-many-branches,too-many-statements
        self,
        prompt: str,
        *,
        max_new_tokens: int,
        decoding: str = "greedy",
        stop_on_eos: bool = True,
        debug_trace: bool = True,
    ) -> GenerateResult:
        """Generate text with D-Flash drafts and Gemma greedy verification."""

        if decoding != "greedy":
            raise ValueError("LowTierEngine correctness path only supports greedy decoding")

        context_token_ids = self._tokenizer.encode_prompt(prompt)
        initial_context_len = len(context_token_ids)
        trace: list[CycleTrace] = []
        counter = GenerationCounter(
            execution_mode=self._execution_mode,
            decoding_mode=decoding,
        )

        with timer_ms() as total_timer:
            cycle_index = 0
            while len(context_token_ids) - initial_context_len < max_new_tokens:
                cycle_start = time.perf_counter()
                with timer_ms() as draft_timer:
                    raw_dflash = self._drafter.draft(
                        self._tokenizer.decode(context_token_ids),
                        max_tokens=self._default_draft_max_tokens,
                    )

                with timer_ms() as parse_timer:
                    parse_result = parse_dflash(raw_dflash)

                malformed_reason = parse_result.error_reason if not parse_result.parse_ok else None
                candidate_token_ids: list[int] = []
                verification = VerificationResult([], None, None, True)
                fallback_used = False
                accepted_count = 0
                stop_now = False

                if parse_result.parse_ok and parse_result.draft_text is not None:
                    max_tokens = clamp_dflash_max_tokens(
                        requested=parse_result.max_tokens,
                        default=self._default_draft_max_tokens,
                        hard=self._hard_draft_max_tokens,
                    )
                    with timer_ms() as retokenize_timer:
                        retokenized = self._tokenizer.retokenize_draft(
                            parse_result.draft_text,
                            max_tokens=max_tokens,
                        )
                    candidate_token_ids = list(retokenized.token_ids)
                    if retokenized.empty:
                        malformed_reason = "retokenized_empty"
                else:
                    retokenize_timer = _StaticTimer()

                if candidate_token_ids and malformed_reason is None:
                    with timer_ms() as verify_timer:
                        verification = self._verifier.verify_greedy_prefix(
                            context_token_ids,
                            candidate_token_ids,
                        )
                    room = max_new_tokens - (len(context_token_ids) - initial_context_len)
                    accepted = self._accepted_until_limit_or_eos(
                        verification.accepted_token_ids,
                        room=room,
                        stop_on_eos=stop_on_eos,
                    )
                    if accepted:
                        context_token_ids.extend(accepted)
                        accepted_count = len(accepted)
                        if stop_on_eos and accepted[-1] == self._tokenizer.eos_token_id:
                            stop_now = True

                    room = max_new_tokens - (len(context_token_ids) - initial_context_len)
                    if not stop_now and not verification.candidate_exhausted and room > 0:
                        fallback_used = True
                        fallback = self._verifier.greedy_next_token(context_token_ids)
                        context_token_ids.append(fallback.token_id)
                        if stop_on_eos and fallback.is_eos:
                            stop_now = True
                else:
                    verify_timer = _StaticTimer()
                    room = max_new_tokens - (len(context_token_ids) - initial_context_len)
                    if room > 0:
                        fallback_used = True
                        fallback = self._verifier.greedy_next_token(context_token_ids)
                        context_token_ids.append(fallback.token_id)
                        if stop_on_eos and fallback.is_eos:
                            stop_now = True

                cycle_ms = (time.perf_counter() - cycle_start) * 1000.0
                counter.add_cycle(
                    drafted_candidate_tokens=len(candidate_token_ids),
                    accepted_tokens=accepted_count,
                    fallback_tokens=1 if fallback_used else 0,
                    malformed_reason=malformed_reason,
                )
                trace.append(
                    self._cycle_trace(
                        cycle_index,
                        context_token_ids,
                        parse_result.parse_ok,
                        malformed_reason,
                        parse_result.draft_text,
                        candidate_token_ids,
                        verification,
                        accepted_count,
                        fallback_used,
                        draft_timer.elapsed_ms,
                        parse_timer.elapsed_ms,
                        retokenize_timer.elapsed_ms,
                        verify_timer.elapsed_ms,
                        cycle_ms,
                    )
                )
                cycle_index += 1
                if stop_now:
                    break

        generated_token_count = len(context_token_ids) - initial_context_len
        return GenerateResult(
            text=self._tokenizer.decode(context_token_ids),
            token_ids=context_token_ids,
            metrics=counter.to_metrics(
                total_ms=total_timer.elapsed_ms,
                generated_tokens=generated_token_count,
            ),
            trace=trace if debug_trace else [],
        )

    def _accepted_until_limit_or_eos(
        self,
        accepted_token_ids: list[int],
        *,
        room: int,
        stop_on_eos: bool,
    ) -> list[int]:
        accepted = list(accepted_token_ids[:room])
        eos_token_id = self._tokenizer.eos_token_id
        if stop_on_eos and eos_token_id is not None and eos_token_id in accepted:
            eos_index = accepted.index(eos_token_id)
            return accepted[: eos_index + 1]
        return accepted

    def _cycle_trace(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        cycle_index: int,
        context_token_ids: list[int],
        parse_ok: bool,
        malformed_reason: str | None,
        draft_text: str | None,
        candidate_token_ids: list[int],
        verification: VerificationResult,
        accepted_count: int,
        fallback_used: bool,
        qwen_draft_ms: float,
        dflash_parse_ms: float,
        gemma_retokenize_ms: float,
        e2b_verify_ms: float,
        cycle_ms: float,
    ) -> CycleTrace:
        return CycleTrace(
            cycle_index=cycle_index,
            context_tokens=len(context_token_ids),
            dflash_parse_ok=parse_ok,
            malformed_dflash=malformed_reason is not None,
            draft_text_chars=len(draft_text or ""),
            draft_candidate_tokens=len(candidate_token_ids),
            accepted_tokens=accepted_count,
            reject_position=verification.reject_position,
            candidate_exhausted=verification.candidate_exhausted,
            fallback_used=fallback_used,
            qwen_draft_ms=qwen_draft_ms,
            dflash_parse_ms=dflash_parse_ms,
            gemma_retokenize_ms=gemma_retokenize_ms,
            e2b_verify_ms=e2b_verify_ms,
            cycle_ms=cycle_ms,
        )


class _StaticTimer:  # pylint: disable=too-few-public-methods
    elapsed_ms = 0.0
