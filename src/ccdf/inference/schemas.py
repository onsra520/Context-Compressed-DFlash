"""Inference schemas for structural NF4 DFlash validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GenerationConfig:
    max_new_tokens: int = 64
    temperature: float = 0.0
    stop_token_ids: tuple[int, ...] = (151645,)
    enable_thinking: bool = False
    dataset: str = "gsm8k"
    prompt_policy_text: str = ""
    output_contract_settings: dict[str, object] = field(default_factory=dict)
    dflash_mode: str = "normal"
    dflash_block_size: int | None = None


@dataclass
class GenerationResult:
    # Backward-compatible required surface.
    generated_text: str
    output_token_ids: list[int]
    prompt_token_count: int
    output_token_count: int
    stop_reason: str

    # Rec-T06A3 output contract fields.
    raw_generated_text: str = ""
    validated_answer: str | None = None
    generated_token_ids: list[int] = field(default_factory=list)
    eos_hit: bool = False
    output_contract_hit: bool = False
    cap_hit: bool = False
    repetition_detected: bool = False
    instruction_echo_detected: bool = False
    degeneration_reason: str | None = None
    output_health: dict[str, object] = field(default_factory=dict)

    # DFlash execution/accounting. Baseline leaves these at zero/empty.
    target_seed_tokens: int = 0
    raw_acceptance_lengths: list[int] = field(default_factory=list)
    emitted_acceptance_lengths: list[int] = field(default_factory=list)
    acceptance_lengths: list[int] = field(default_factory=list)
    verification_calls: int = 0
    target_prefill_calls: int = 0
    target_block_verification_calls: int = 0
    target_single_token_fallback_calls: int = 0
    target_hidden_refresh_calls: int = 0
    total_target_forward_calls: int = 0
    draft_forward_calls: int = 0
    draft_tokens_proposed: int = 0
    accepted_draft_tokens: int = 0
    correction_tokens: int = 0
    bonus_target_tokens: int = 0
    rollback_tokens: int = 0
    structural_audit: list[dict[str, Any]] = field(default_factory=list)
    cache_audit: list[dict[str, Any]] = field(default_factory=list)

    # Timing. Rec-T06B will refine process-isolated canonical measurement.
    target_model_init_ms: float = 0.0
    drafter_model_init_ms: float = 0.0
    compressor_init_ms: float = 0.0
    model_init_ms: float = 0.0
    compression_total_ms: float = 0.0
    prompt_render_ms: float = 0.0
    target_prefill_ms: float = 0.0
    draft_prefill_ms: float = 0.0
    decode_total_ms: float = 0.0
    generation_request_e2e_ms: float = 0.0
    warm_request_e2e_ms: float = 0.0
    request_e2e_ms: float = 0.0

    def __post_init__(self) -> None:
        if not self.raw_generated_text:
            self.raw_generated_text = self.generated_text
        if not self.generated_token_ids and self.output_token_count:
            self.generated_token_ids = self.output_token_ids[-self.output_token_count :]
        if not self.emitted_acceptance_lengths and self.acceptance_lengths:
            self.emitted_acceptance_lengths = list(self.acceptance_lengths)
        if not self.acceptance_lengths and self.emitted_acceptance_lengths:
            self.acceptance_lengths = list(self.emitted_acceptance_lengths)
        if not self.raw_acceptance_lengths and self.emitted_acceptance_lengths:
            self.raw_acceptance_lengths = list(self.emitted_acceptance_lengths)

    @property
    def effective_tau(self) -> float:
        if not self.target_block_verification_calls:
            return 0.0
        return sum(self.emitted_acceptance_lengths) / self.target_block_verification_calls

    @property
    def draft_acceptance_rate(self) -> float:
        if not self.draft_tokens_proposed:
            return 0.0
        return self.accepted_draft_tokens / self.draft_tokens_proposed

    @property
    def target_forwards_per_emitted_token(self) -> float:
        if not self.output_token_count:
            return 0.0
        return self.total_target_forward_calls / self.output_token_count
