"""LLMLingua compression wrapper with context-only output."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ccdf.compression.base import CompressorBase
from ccdf.compression.chunking import chunk_context
from ccdf.compression.schemas import CompressionConfig, CompressionResult

LOCAL_LLMLINGUA_MODEL = Path("models/llmlingua-2-bert-base-multilingual-cased-meetingbank")


class LLMLinguaCompressor(CompressorBase):
    def __init__(self, model_path: Path = LOCAL_LLMLINGUA_MODEL, *, device_map: str = "cpu") -> None:
        from llmlingua import PromptCompressor
        from transformers import AutoTokenizer

        self.model_path = model_path
        self.device_map = device_map
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.backend = PromptCompressor(
            model_name=str(model_path),
            device_map=device_map,
            use_llmlingua2=True,
        )
        self.device_audit = self._audit_devices()
        self.cuda_verified = self._verify_cuda() if device_map == "cuda" else False
        if device_map == "cuda" and not self.cuda_verified:
            raise RuntimeError(
                "LLMLingua compressor did not place every parameter and buffer on CUDA: "
                f"{self.device_audit}"
            )
        self.tokenizer_id = f"llmlingua2:{model_path}"

    def _tensor_owners(self) -> list[tuple[str, Any]]:
        """Return distinct backend objects that may own model tensors."""
        owners: list[tuple[str, Any]] = []
        seen: set[int] = set()
        for name in ("model", "compressor", "llm"):
            candidate = getattr(self.backend, name, None)
            if candidate is not None and id(candidate) not in seen:
                owners.append((name, candidate))
                seen.add(id(candidate))
        return owners

    def _audit_devices(self) -> dict[str, Any]:
        """Count *all* compressor tensors, so ``device_map`` cannot silently fall back."""
        tensors = []
        for owner_name, owner in self._tensor_owners():
            parameters = getattr(owner, "parameters", None)
            buffers = getattr(owner, "buffers", None)
            if callable(parameters):
                tensors.extend(("parameter", owner_name, tensor) for tensor in parameters())
            if callable(buffers):
                tensors.extend(("buffer", owner_name, tensor) for tensor in buffers())
        parameter_tensors = [tensor for kind, _, tensor in tensors if kind == "parameter"]
        buffer_tensors = [tensor for kind, _, tensor in tensors if kind == "buffer"]
        devices = sorted({str(tensor.device) for _, _, tensor in tensors})
        cuda_parameters = [tensor for tensor in parameter_tensors if tensor.device.type == "cuda"]
        cuda_buffers = [tensor for tensor in buffer_tensors if tensor.device.type == "cuda"]
        all_cuda = bool(tensors) and all(tensor.device.type == "cuda" for _, _, tensor in tensors)
        return {
            "unique_devices": devices,
            "total_parameters": len(parameter_tensors),
            "cuda_parameters": len(cuda_parameters),
            "total_buffers": len(buffer_tensors),
            "cuda_buffers": len(cuda_buffers),
            "total_parameter_bytes": sum(tensor.numel() * tensor.element_size() for tensor in parameter_tensors),
            "cuda_parameter_bytes": sum(tensor.numel() * tensor.element_size() for tensor in cuda_parameters),
            "total_buffer_bytes": sum(tensor.numel() * tensor.element_size() for tensor in buffer_tensors),
            "cuda_buffer_bytes": sum(tensor.numel() * tensor.element_size() for tensor in cuda_buffers),
            "all_tensors_cuda": all_cuda,
            "execution_mode": "resident" if all_cuda else "staged",
        }

    def _verify_cuda(self) -> bool:
        """Reject CPU/offload fallback across every backend parameter and buffer."""
        import torch

        audit = self.device_audit
        return bool(
            torch.cuda.is_available()
            and audit["all_tensors_cuda"]
            and audit["total_parameters"] == audit["cuda_parameters"]
            and audit["total_buffers"] == audit["cuda_buffers"]
        )

    def _count(self, text: str) -> int:
        # Counting may intentionally inspect a sequence longer than the
        # compressor model window. Compression itself operates on bounded
        # chunks, so suppress the tokenizer's model-length warning here.
        return len(
            self.tokenizer.encode(
                text,
                add_special_tokens=False,
                truncation=False,
                verbose=False,
            )
        )

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
                "compressor_device": self.device_map,
                "compressor_cuda_verified": self.cuda_verified,
                "device_audit": self.device_audit,
                "execution_mode": self.device_audit["execution_mode"],
                "transfer_to_device_ms": 0.0,
                "offload_ms": 0.0,
            },
            bypassed=False,
        )
