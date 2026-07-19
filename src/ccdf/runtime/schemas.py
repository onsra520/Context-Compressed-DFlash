"""Stable runtime result schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class GenerationSettings:
    max_new_tokens: int
    temperature: float
    stop_token_ids: tuple[int, ...]
    dataset: str = "general"
    block_size: int = 16
    output_contract_mode: str = "finalize_only"


@dataclass
class TimingBreakdown:
    prompt_prepare_ms: float = 0.0
    target_prefill_ms: float = 0.0
    draft_prefill_ms: float | None = None
    decode_total_ms: float = 0.0
    steady_state_decode_ms: float | None = None
    generation_total_ms: float = 0.0
    warm_request_ms: float = 0.0
    profiling_invasive: bool = False


@dataclass
class MemoryStats:
    allocated_before_bytes: int | None = None
    reserved_before_bytes: int | None = None
    peak_allocated_bytes: int = 0
    peak_reserved_bytes: int = 0
    allocated_after_bytes: int | None = None
    reserved_after_bytes: int | None = None
    free_bytes_after_request: int | None = None
    total_device_bytes: int | None = None
    limit_bytes: int | None = None
    gate_pass: bool | None = None


@dataclass
class DFlashStats:
    target_prefill_calls: int = 0
    target_verification_calls: int = 0
    target_single_token_calls: int = 0
    draft_forward_calls: int = 0
    acceptance_lengths: list[int] = field(default_factory=list)
    accepted_draft_tokens: int = 0
    draft_tokens_proposed: int = 0
    rollback_tokens: int = 0
    correction_tokens: int = 0
    bonus_tokens: int = 0
    block_sizes: list[int] = field(default_factory=list)
    block_profiles: list[dict[str, float | int]] = field(default_factory=list)
    structural_audit: list[dict[str, Any]] = field(default_factory=list)

    @property
    def effective_tau(self) -> float:
        if not self.target_verification_calls:
            return 0.0
        return sum(self.acceptance_lengths) / self.target_verification_calls

    @property
    def acceptance_rate(self) -> float:
        if not self.draft_tokens_proposed:
            return 0.0
        return self.accepted_draft_tokens / self.draft_tokens_proposed


@dataclass
class GenerationOutput:
    condition: str
    text: str
    prompt_tokens: int
    output_tokens: int
    generated_token_ids: list[int]
    stop_reason: str
    timing: TimingBreakdown
    memory: MemoryStats
    dflash: DFlashStats | None = None
    model: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)

    @property
    def decode_tokens(self) -> int:
        """Tokens emitted after the first token produced by target prefill."""
        return max(self.output_tokens - 1, 0)

    @property
    def decode_tok_s(self) -> float:
        if self.timing.decode_total_ms <= 0:
            return 0.0
        return self.decode_tokens / (self.timing.decode_total_ms / 1000.0)

    @property
    def generation_tok_s(self) -> float:
        if self.timing.generation_total_ms <= 0:
            return 0.0
        return self.output_tokens / (self.timing.generation_total_ms / 1000.0)

    @property
    def warm_request_tok_s(self) -> float:
        if self.timing.warm_request_ms <= 0:
            return 0.0
        return self.output_tokens / (self.timing.warm_request_ms / 1000.0)

    @property
    def steady_state_decode_tok_s(self) -> float | None:
        elapsed = self.timing.steady_state_decode_ms
        if elapsed is None or elapsed <= 0:
            return None
        return self.decode_tokens / (elapsed / 1000.0) if self.decode_tokens else None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["metrics"] = {
            "decode_tokens": self.decode_tokens,
            "decode_tok_s": self.decode_tok_s,
            "generation_tok_s": self.generation_tok_s,
            "warm_request_tok_s": self.warm_request_tok_s,
            "steady_state_decode_tok_s": self.steady_state_decode_tok_s,
        }
        if self.dflash is not None:
            payload["dflash"]["effective_tau"] = self.dflash.effective_tau
            payload["dflash"]["draft_acceptance_rate"] = self.dflash.acceptance_rate
            total_target = (
                self.dflash.target_prefill_calls
                + self.dflash.target_verification_calls
                + self.dflash.target_single_token_calls
            )
            payload["dflash"]["target_forwards_per_output_token"] = (
                total_target / self.output_tokens if self.output_tokens else 0.0
            )
        return payload
