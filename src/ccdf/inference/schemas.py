"""Inference schemas."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GenerationConfig:
    max_new_tokens: int = 64
    temperature: float = 0.0
    stop_token_ids: tuple[int, ...] = (151645,)
    enable_thinking: bool = False


@dataclass
class GenerationResult:
    generated_text: str
    output_token_ids: list[int]
    prompt_token_count: int
    output_token_count: int
    stop_reason: str
    acceptance_lengths: list[int] = field(default_factory=list)
    verification_calls: int = 0
    draft_tokens_proposed: int = 0

    @property
    def accepted_draft_tokens(self) -> int:
        if not self.acceptance_lengths:
            return 0
        return sum(self.acceptance_lengths) - len(self.acceptance_lengths)

    @property
    def rollback_tokens(self) -> int:
        return self.draft_tokens_proposed - self.accepted_draft_tokens
