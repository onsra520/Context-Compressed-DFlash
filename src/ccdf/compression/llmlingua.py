"""LLMLingua compression wrapper with context-only output."""

from __future__ import annotations

import time
from pathlib import Path

from transformers import AutoTokenizer

from ccdf.compression.base import CompressorBase
from ccdf.compression.chunking import chunk_context
from ccdf.compression.schemas import CompressionConfig, CompressionResult

LOCAL_LLMLINGUA_MODEL = Path("models/llmlingua-2-bert-base-multilingual-cased-meetingbank")


class LLMLinguaCompressor(CompressorBase):
    def __init__(self, model_path: Path = LOCAL_LLMLINGUA_MODEL, *, device_map: str = "cpu") -> None:
        from llmlingua import PromptCompressor

        self.model_path = model_path
        self.device_map = device_map
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.backend = PromptCompressor(
            model_name=str(model_path),
            device_map=device_map,
            use_llmlingua2=True,
        )
        self.tokenizer_id = f"llmlingua2:{model_path}"

    def _count(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def compress(
        self, *, context: str, question: str, config: CompressionConfig
    ) -> CompressionResult:
        if not config.compression_enabled:
            from ccdf.compression.passthrough import PassthroughCompressor

            return PassthroughCompressor().compress(context=context, question=question, config=config)
        original_tokens = self._count(context)
        if original_tokens < config.min_context_tokens:
            from ccdf.compression.passthrough import PassthroughCompressor

            result = PassthroughCompressor().compress(context=context, question=question, config=config)
            result.backend_metadata["bypass_reason"] = "below_min_context_tokens"
            return result

        chunks = chunk_context(context, max_words=config.chunk_max_words)
        start = time.perf_counter()
        compressed_chunks: list[str] = []
        for chunk in chunks:
            compressed = self.backend.compress_prompt(
                [chunk],
                question=question,
                rate=config.keep_rate,
                concate_question=False,
                add_instruction=False,
                use_context_level_filter=True,
                use_token_level_filter=True,
                strict_preserve_uncompressed=True,
            )
            compressed_chunks.append(compressed["compressed_prompt"])
        compression_total_ms = (time.perf_counter() - start) * 1000
        compressed_context = "\n".join(part for part in compressed_chunks if part)
        compressed_tokens = self._count(compressed_context)
        retained_ratio = compressed_tokens / original_tokens if original_tokens else 1.0
        return CompressionResult(
            compressed_context=compressed_context,
            segment_original_tokens=original_tokens,
            segment_compressed_tokens=compressed_tokens,
            segment_tokenizer_id=self.tokenizer_id,
            compression_factor=original_tokens / compressed_tokens if compressed_tokens else 0.0,
            retained_ratio=retained_ratio,
            reduction_pct=(1.0 - retained_ratio) * 100,
            chunk_count=len(chunks),
            compression_total_ms=compression_total_ms,
            backend_metadata={
                "backend": "llmlingua2",
                "model_path": str(self.model_path),
                "question_conditioning": True,
                "concate_question": False,
            },
            bypassed=False,
        )
