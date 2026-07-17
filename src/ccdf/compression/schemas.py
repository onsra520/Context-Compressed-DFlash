"""Stable contracts for context-only compression."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CompressionConfig:
    keep_rate: float = 0.5
    min_context_tokens: int = 1
    chunk_max_words: int = 180

    def __post_init__(self) -> None:
        if not 0 < self.keep_rate <= 1:
            raise ValueError("keep_rate must be in (0, 1]")
        if self.min_context_tokens < 1 or self.chunk_max_words < 1:
            raise ValueError("token and chunk limits must be positive")


@dataclass(frozen=True)
class CompressionResult:
    compressed_context: str
    original_tokens: int
    compressed_tokens: int
    reduction_rate: float
    compression_latency_ms: float
    peak_allocated_vram_bytes: int
    peak_reserved_vram_bytes: int
    reserved_vram_budget_bytes: int
    reserved_vram_budget_pass: bool
    protected_fields_unchanged: bool
    chunk_count: int
    input_word_count: int
    submitted_word_count: int
    device_audit: dict[str, Any] = field(default_factory=dict)
