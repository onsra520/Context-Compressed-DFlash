"""LLMLingua-2 compressor constrained to context-only transformation."""

from __future__ import annotations

import gc
import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from transformers import AutoConfig, AutoTokenizer

from ..runtime.device import GIB, synchronize
from ..errors import MemoryBudgetError
from .schemas import CompressionConfig, CompressionResult


@dataclass(frozen=True)
class ContextOnlyProtocol:
    """Prompt fields whose question/instruction are immutable across compression."""

    context: str
    question: str
    output_instruction: str
    context_header: str = "Context:"
    question_header: str = "Question:"

    def render(self, compressed_context: str) -> str:
        sections = []
        if compressed_context:
            sections.append(f"{self.context_header}\n{compressed_context}")
        sections.append(f"{self.question_header}\n{self.question}")
        sections.append(self.output_instruction)
        return "\n\n".join(sections)


class LLMLinguaCompressor:
    """A resident CUDA LLMLingua-2 backend with no CPU/disk offload path."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        device: str,
        local_files_only: bool,
        reserved_vram_budget_gib: float,
    ) -> None:
        self.model_path = Path(model_path).resolve()
        if not self.model_path.is_dir():
            raise FileNotFoundError(self.model_path)
        if not torch.cuda.is_available() or torch.cuda.device_count() < 1:
            raise RuntimeError("CUDA compressor requested but no CUDA device is available")
        if not device.startswith("cuda"):
            raise ValueError(f"compressor device must be configured as CUDA: {device}")
        if reserved_vram_budget_gib <= 0:
            raise ValueError("reserved_vram_budget_gib must be positive")
        self.reserved_vram_budget_bytes = int(reserved_vram_budget_gib * GIB)
        from llmlingua import PromptCompressor

        model_config = AutoConfig.from_pretrained(
            self.model_path, local_files_only=local_files_only
        )
        architectures = list(getattr(model_config, "architectures", None) or [])
        if model_config.model_type != "xlm-roberta" or not any(
            name.endswith("ForTokenClassification") for name in architectures
        ):
            raise RuntimeError(
                "LLMLingua-2 requires an XLM-RoBERTa token-classification checkpoint: "
                f"model_type={model_config.model_type}, architectures={architectures}"
            )
        self.model_contract = {
            "model_type": model_config.model_type,
            "architectures": architectures,
            "compression_algorithm": "llmlingua2_token_classification",
            "heuristic_or_truncation_fallback": False,
            "configured_device": device,
            "local_files_only": local_files_only,
        }
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path, local_files_only=local_files_only
        )
        synchronize()
        torch.cuda.reset_peak_memory_stats()
        synchronize()
        started = time.perf_counter()
        self.backend = PromptCompressor(
            model_name=str(self.model_path), device_map=device, use_llmlingua2=True
        )
        self.backend_compress_prompt_calls = 0
        synchronize()
        self.initialization_ms = (time.perf_counter() - started) * 1000.0
        self.device_audit = self._audit_cuda()
        self.model_contract["backend_class"] = type(self.backend).__name__
        if not self.device_audit["all_tensors_cuda"]:
            raise RuntimeError(f"compressor must be fully CUDA resident: {self.device_audit}")
        self._enforce_reserved_budget(label="compressor model load")

    def _enforce_reserved_budget(self, *, label: str) -> None:
        peak_reserved = int(torch.cuda.max_memory_reserved())
        if peak_reserved > self.reserved_vram_budget_bytes:
            raise MemoryBudgetError(
                f"{label} peak reserved memory exceeded compressor budget: "
                f"{peak_reserved / GIB:.3f} GiB > {self.reserved_vram_budget_bytes / GIB:.3f} GiB"
            )

    def _owners(self) -> list[tuple[str, Any]]:
        seen: set[int] = set()
        owners: list[tuple[str, Any]] = []
        for name in ("model", "compressor", "llm"):
            value = getattr(self.backend, name, None)
            if value is not None and id(value) not in seen:
                owners.append((name, value))
                seen.add(id(value))
        return owners

    def _audit_cuda(self) -> dict[str, Any]:
        tensors: list[tuple[str, torch.Tensor]] = []
        for _, owner in self._owners():
            if callable(getattr(owner, "parameters", None)):
                tensors.extend(("parameter", value) for value in owner.parameters())
            if callable(getattr(owner, "buffers", None)):
                tensors.extend(("buffer", value) for value in owner.buffers())
            device_map = getattr(owner, "hf_device_map", None)
            if isinstance(device_map, dict) and any(str(v) in {"cpu", "disk"} for v in device_map.values()):
                return {"all_tensors_cuda": False, "reason": "hf_device_map contains CPU/disk offload"}
        parameter_numel = sum(t.numel() for kind, t in tensors if kind == "parameter")
        parameter_bytes = sum(t.numel() * t.element_size() for kind, t in tensors if kind == "parameter")
        buffer_bytes = sum(t.numel() * t.element_size() for kind, t in tensors if kind == "buffer")
        return {
            "all_tensors_cuda": bool(tensors) and all(t.device.type == "cuda" for _, t in tensors),
            "devices": sorted({str(t.device) for _, t in tensors}),
            "parameter_tensor_count": sum(kind == "parameter" for kind, _ in tensors),
            "buffer_tensor_count": sum(kind == "buffer" for kind, _ in tensors),
            "total_parameters_numel": parameter_numel,
            "parameter_bytes": parameter_bytes,
            "buffer_bytes": buffer_bytes,
            "execution_mode": "resident",
            "cpu_offload": False,
        }

    def _count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False, truncation=False, verbose=False))

    def _token_chunks(
        self, context: str, config: CompressionConfig
    ) -> list[tuple[int, int, list[int], str]]:
        token_ids = self.tokenizer.encode(
            context, add_special_tokens=False, truncation=False, verbose=False
        )
        if not token_ids:
            return []
        backend_limit = int(
            getattr(self.backend, "max_seq_len", None)
            or getattr(self.tokenizer, "model_max_length", config.chunk_size_tokens + 2)
        ) - 2
        if config.chunk_size_tokens > backend_limit:
            raise ValueError(
                "configured compression chunk size exceeds backend payload limit: "
                f"{config.chunk_size_tokens} > {backend_limit}"
            )
        chunks: list[tuple[int, int, list[int], str]] = []
        step = config.chunk_size_tokens - config.chunk_overlap_tokens
        start = 0
        while start < len(token_ids):
            end = min(start + config.chunk_size_tokens, len(token_ids))
            source_ids = [int(value) for value in token_ids[start:end]]
            text = self.tokenizer.decode(
                source_ids, skip_special_tokens=False, clean_up_tokenization_spaces=False
            )
            submitted_ids = self.tokenizer.encode(
                text, add_special_tokens=False, truncation=False, verbose=False
            )
            if len(submitted_ids) > backend_limit:
                raise RuntimeError(
                    "decoded compression chunk exceeds backend payload limit; refusing hidden truncation"
                )
            chunks.append((start, end, source_ids, text))
            if end == len(token_ids):
                break
            start += step
        return chunks

    def compress(self, protocol: ContextOnlyProtocol, config: CompressionConfig) -> CompressionResult:
        original_tokens = self._count_tokens(protocol.context)
        input_word_count = len(protocol.context.split())
        if original_tokens < config.min_context_tokens:
            no_op_reason = "empty_context" if original_tokens == 0 else "below_min_context_tokens"
            return CompressionResult(
                protocol.context, original_tokens, original_tokens, 0.0, 0.0,
                int(torch.cuda.max_memory_allocated()), int(torch.cuda.max_memory_reserved()),
                self.reserved_vram_budget_bytes,
                int(torch.cuda.max_memory_reserved()) <= self.reserved_vram_budget_bytes,
                True, 0, input_word_count, 0,
                chunk_token_ranges=[], compressed_tokens_by_chunk=[],
                covered_unique_tokens=original_tokens,
                coverage_rate=1.0,
                dropped_tokens=0,
                hidden_truncated_tokens=0,
                chunk_tokenizer=str(getattr(self.tokenizer, "name_or_path", self.model_path)),
                merge_policy=config.merge_policy,
                no_op_reason=no_op_reason,
                device_audit=self.device_audit,
            )
        torch.cuda.reset_peak_memory_stats()
        synchronize()
        started = time.perf_counter()
        compressed_parts: list[str] = []
        chunk_map: list[dict[str, Any]] = []
        chunks = self._token_chunks(protocol.context, config)
        for chunk_index, (start, end, source_ids, chunk) in enumerate(chunks):
            submitted_tokens = self._count_tokens(chunk)
            self.backend_compress_prompt_calls += 1
            result = self.backend.compress_prompt(
                [chunk], question=protocol.question, rate=config.keep_rate,
                concate_question=False, add_instruction=False,
                use_context_level_filter=False, use_token_level_filter=True,
                strict_preserve_uncompressed=True,
            )
            compressed = str(result["compressed_prompt"])
            compressed_parts.append(compressed)
            chunk_map.append({
                "chunk_index": chunk_index,
                "source_start_token": start,
                "source_end_token_exclusive": end,
                "source_token_count": end - start,
                "submitted_token_count": submitted_tokens,
                "compressed_token_count": self._count_tokens(compressed),
                "source_token_ids_sha256": hashlib.sha256(
                    ",".join(str(value) for value in source_ids).encode("ascii")
                ).hexdigest(),
                "compressed_text_sha256": hashlib.sha256(compressed.encode("utf-8")).hexdigest(),
                "backend_payload_limit_tokens": int(
                    getattr(self.backend, "max_seq_len", config.chunk_size_tokens + 2)
                ) - 2,
                "hidden_truncated_tokens": 0,
            })
        synchronize()
        latency_ms = (time.perf_counter() - started) * 1000.0
        compressed_context = "\n".join(part for part in compressed_parts if part)
        compressed_tokens = self._count_tokens(compressed_context)
        self._enforce_reserved_budget(label="compressor request")
        rendered = protocol.render(compressed_context)
        protected = rendered.encode("utf-8").endswith(protocol.output_instruction.encode("utf-8")) and (
            f"Question:\n{protocol.question}\n\n".encode("utf-8") in rendered.encode("utf-8")
        )
        return CompressionResult(
            compressed_context=compressed_context,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            reduction_rate=1 - (compressed_tokens / original_tokens) if original_tokens else 0.0,
            compression_latency_ms=latency_ms,
            peak_allocated_vram_bytes=int(torch.cuda.max_memory_allocated()),
            peak_reserved_vram_bytes=int(torch.cuda.max_memory_reserved()),
            reserved_vram_budget_bytes=self.reserved_vram_budget_bytes,
            reserved_vram_budget_pass=int(torch.cuda.max_memory_reserved()) <= self.reserved_vram_budget_bytes,
            protected_fields_unchanged=protected,
            chunk_count=len(compressed_parts),
            input_word_count=input_word_count,
            submitted_word_count=sum(len(entry[3].split()) for entry in chunks),
            chunk_token_ranges=chunk_map,
            compressed_tokens_by_chunk=[
                int(item["compressed_token_count"]) for item in chunk_map
            ],
            covered_unique_tokens=original_tokens,
            coverage_rate=1.0,
            dropped_tokens=0,
            hidden_truncated_tokens=0,
            chunk_tokenizer=str(getattr(self.tokenizer, "name_or_path", self.model_path)),
            merge_policy=config.merge_policy,
            no_op_reason=None,
            device_audit=self.device_audit,
        )

    def close(self) -> None:
        """Release the CUDA-resident LLMLingua backend between protocol stages.

        The compressor is intentionally loaded separately from generation models so
        validation and benchmark callers can keep the single-GPU lifecycle explicit.
        """
        self.backend = None
        self.tokenizer = None
        gc.collect()
        if torch.cuda.is_available():
            synchronize()
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
