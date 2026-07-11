"""Passthrough compression control."""

from __future__ import annotations

from ccdf.compression.base import CompressorBase
from ccdf.compression.schemas import CompressionConfig, CompressionResult


class PassthroughCompressor(CompressorBase):
    tokenizer_id = "passthrough-whitespace"

    def compress(
        self, *, context: str, question: str, config: CompressionConfig
    ) -> CompressionResult:
        del question, config
        tokens = len(context.split())
        return CompressionResult(
            compressed_context=context,
            segment_original_tokens=tokens,
            segment_compressed_tokens=tokens,
            segment_tokenizer_id=self.tokenizer_id,
            compression_factor=1.0,
            retained_ratio=1.0,
            reduction_pct=0.0,
            chunk_count=1 if context else 0,
            compression_total_ms=0.0,
            backend_metadata={"backend": "passthrough"},
            bypassed=True,
        )
