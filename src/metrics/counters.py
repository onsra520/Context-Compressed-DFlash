"""Request-level metric counters for Low Tier generation."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

_types = import_module("htfsd_types")
GenerationMetrics = _types.GenerationMetrics


@dataclass
class GenerationCounter:  # pylint: disable=too-many-instance-attributes
    """Mutable accumulator converted into immutable generation metrics."""

    execution_mode: str
    decoding_mode: str
    cycles: int = 0
    drafted_candidate_tokens: int = 0
    accepted_tokens: int = 0
    fallback_tokens: int = 0
    malformed_dflash_count: int = 0
    dflash_parse_fail_count: int = 0
    dflash_schema_invalid_count: int = 0
    dflash_empty_draft_count: int = 0
    retokenized_empty_count: int = 0

    def add_cycle(
        self,
        *,
        drafted_candidate_tokens: int,
        accepted_tokens: int,
        fallback_tokens: int,
        malformed_reason: str | None,
    ) -> None:
        """Add one decode cycle worth of acceptance and fallback counts."""

        self.cycles += 1
        self.drafted_candidate_tokens += drafted_candidate_tokens
        self.accepted_tokens += accepted_tokens
        self.fallback_tokens += fallback_tokens
        if malformed_reason is None:
            return
        self.malformed_dflash_count += 1
        if malformed_reason == "parse_fail":
            self.dflash_parse_fail_count += 1
        elif malformed_reason == "schema_invalid":
            self.dflash_schema_invalid_count += 1
        elif malformed_reason == "empty_draft":
            self.dflash_empty_draft_count += 1
        elif malformed_reason == "retokenized_empty":
            self.retokenized_empty_count += 1
        else:
            self.dflash_schema_invalid_count += 1

    def to_metrics(self, *, total_ms: float, generated_tokens: int) -> GenerationMetrics:
        """Build final request metrics from accumulated counters."""

        low_acceptance_rate = (
            self.accepted_tokens / self.drafted_candidate_tokens
            if self.drafted_candidate_tokens
            else 0.0
        )
        fallback_rate = self.fallback_tokens / generated_tokens if generated_tokens else 0.0
        tokens_per_second = generated_tokens / (total_ms / 1000.0) if total_ms > 0 else 0.0
        latency_per_token_ms = total_ms / generated_tokens if generated_tokens else 0.0
        return GenerationMetrics(
            generated_tokens=generated_tokens,
            cycles=self.cycles,
            drafted_candidate_tokens=self.drafted_candidate_tokens,
            accepted_tokens=self.accepted_tokens,
            fallback_tokens=self.fallback_tokens,
            malformed_dflash_count=self.malformed_dflash_count,
            dflash_parse_fail_count=self.dflash_parse_fail_count,
            dflash_schema_invalid_count=self.dflash_schema_invalid_count,
            dflash_empty_draft_count=self.dflash_empty_draft_count,
            retokenized_empty_count=self.retokenized_empty_count,
            low_acceptance_rate=low_acceptance_rate,
            fallback_rate=fallback_rate,
            total_ms=total_ms,
            tokens_per_second=tokens_per_second,
            latency_per_token_ms=latency_per_token_ms,
            execution_mode=self.execution_mode,
            decoding_mode=self.decoding_mode,
        )
