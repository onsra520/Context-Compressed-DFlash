"""Stable contracts for context-only compression."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CompressionConfig:
    keep_rate: float = 0.5
    min_context_tokens: int = 1
    chunk_size_tokens: int = 480
    chunk_overlap_tokens: int = 32
    tokenizer: str = "compressor"
    merge_policy: str = "newline_preserve_order"

    def __post_init__(self) -> None:
        if not 0 < self.keep_rate <= 1:
            raise ValueError("keep_rate must be in (0, 1]")
        if self.min_context_tokens < 1 or self.chunk_size_tokens < 1:
            raise ValueError("token and chunk limits must be positive")
        if self.chunk_overlap_tokens < 0 or self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ValueError("chunk_overlap_tokens must be in [0, chunk_size_tokens)")
        if self.tokenizer != "compressor":
            raise ValueError(f"unsupported compression tokenizer policy: {self.tokenizer}")
        if self.merge_policy != "newline_preserve_order":
            raise ValueError(f"unsupported compression merge policy: {self.merge_policy}")


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
    chunk_token_ranges: list[dict[str, Any]] = field(default_factory=list)
    compressed_tokens_by_chunk: list[int] = field(default_factory=list)
    covered_unique_tokens: int = 0
    coverage_rate: float = 1.0
    dropped_tokens: int = 0
    hidden_truncated_tokens: int = 0
    chunk_tokenizer: str = ""
    merge_policy: str = ""
    no_op_reason: str | None = None
    device_audit: dict[str, Any] = field(default_factory=dict)
