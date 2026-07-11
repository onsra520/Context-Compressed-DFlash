"""Compression schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CompressionConfig:
    compression_enabled: bool = True
    compression_profile: str = "llmlingua2-meetingbank"
    keep_rate: float = 0.5
    min_context_tokens: int = 32
    chunk_max_words: int = 180
    backend: str = "llmlingua"
    device_map: str = "cpu"


@dataclass
class CompressionResult:
    compressed_context: str
    segment_original_tokens: int
    segment_compressed_tokens: int
    segment_tokenizer_id: str
    compression_factor: float
    retained_ratio: float
    reduction_pct: float
    chunk_count: int
    compression_total_ms: float
    backend_metadata: dict[str, Any] = field(default_factory=dict)
    bypassed: bool = False
