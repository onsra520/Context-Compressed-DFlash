from __future__ import annotations

import inspect
import time
from typing import Any

from .base import CompressorBase
from .segmentation import merge

DEFAULT_LLM_LINGUA_2_MODEL = "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"
DEFAULT_CONTEXT_TOKEN_BUDGET = 384
DEFAULT_ENCODER_MAX_LENGTH = 512
DEFAULT_CHUNK_SAFETY_MARGIN = 32

try:
    from llmlingua import PromptCompressor
except ImportError:  # pragma: no cover - exercised through runtime dependency checks
    PromptCompressor = None


class LLMLinguaCompressor(CompressorBase):
    def __init__(
        self,
        model_name: str = DEFAULT_LLM_LINGUA_2_MODEL,
        device_map: str = "cpu",
        requested_device_map: str | None = None,
        compressor_path: str | None = None,
        resolved_compressor_path: str | None = None,
        model_source: str | None = None,
        source_kind: str = "model_name",
        local_files_only: bool = False,
        compressor_profile: str = "large",
        use_llmlingua2: bool = True,
        default_keep_rate: float = 0.5,
        llmlingua2_config: dict[str, Any] | None = None,
        max_context_tokens_per_chunk: int = DEFAULT_CONTEXT_TOKEN_BUDGET,
        chunk_safety_margin: int = DEFAULT_CHUNK_SAFETY_MARGIN,
        max_context_words_per_chunk: int | None = None,
    ) -> None:
        self.model_name = model_name
        self.device_map = device_map
        self.requested_device_map = requested_device_map
        self.compressor_path = compressor_path
        self.resolved_compressor_path = resolved_compressor_path
        self.model_source = model_source or model_name
        self.source_kind = source_kind
        self.local_files_only = local_files_only
        self.compressor_profile = compressor_profile
        self.use_llmlingua2 = use_llmlingua2
        self.default_keep_rate = default_keep_rate
        self.llmlingua2_config = llmlingua2_config or {}
        self.max_context_tokens_per_chunk = max(1, int(max_context_tokens_per_chunk))
        self.chunk_safety_margin = max(0, int(chunk_safety_margin))
        self.max_context_words_per_chunk = max_context_words_per_chunk
        self._compressor = None
        self._tokenizer = None
        self._tokenizer_is_fallback = False

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any] | None = None,
        profile: str = "large",
        device_map_override: str | None = None,
    ) -> "LLMLinguaCompressor":
        from ccdf.config.loader import resolve_compressor_model_source, resolve_llmlingua_config

        cfg = resolve_llmlingua_config(config, profile=profile)
        source = resolve_compressor_model_source(cfg)
        resolved_device_map = str(device_map_override or cfg.get("device_map", "cpu"))
        return cls(
            model_name=cfg.get("model_name", DEFAULT_LLM_LINGUA_2_MODEL),
            device_map=resolved_device_map,
            requested_device_map=device_map_override,
            compressor_path=source.get("compressor_path"),
            resolved_compressor_path=source.get("resolved_compressor_path"),
            model_source=source.get("source"),
            source_kind=str(source.get("source_kind", "model_name")),
            local_files_only=bool(source.get("local_files_only", False)),
            compressor_profile=str(profile),
            use_llmlingua2=bool(cfg.get("use_llmlingua2", True)),
            default_keep_rate=float(cfg.get("default_keep_rate", 0.5)),
            llmlingua2_config=cfg.get("llmlingua2_config") or {},
            max_context_tokens_per_chunk=int(
                cfg.get(
                    "max_context_tokens_per_chunk",
                    cfg.get("compressor_chunk_token_budget", DEFAULT_CONTEXT_TOKEN_BUDGET),
                )
            ),
            chunk_safety_margin=int(cfg.get("chunk_safety_margin", DEFAULT_CHUNK_SAFETY_MARGIN)),
            max_context_words_per_chunk=cfg.get("max_context_words_per_chunk"),
        )

    def _source_metadata(self) -> dict[str, Any]:
        return {
            "compressor_model_name": self.model_name,
            "compressor_path": self.compressor_path,
            "resolved_compressor_path": self.resolved_compressor_path,
            "compressor_model_source": self.model_source,
            "compressor_source_kind": self.source_kind,
            "local_files_only": self.local_files_only,
            "compressor_profile": self.compressor_profile,
            "compressor_device_map": self.device_map,
            "requested_compressor_device_map": self.requested_device_map,
        }

    @staticmethod
    def _supports_constructor_kwarg(constructor, name: str) -> bool:
        try:
            parameters = inspect.signature(constructor).parameters.values()
        except (TypeError, ValueError):
            return False
        return any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD or parameter.name == name
            for parameter in parameters
        )

    def _get_compressor(self):
        if PromptCompressor is None:
            raise ImportError(
                "llmlingua is not installed in the active environment. "
                "Install it with: PYTHONPATH=src .venv/bin/python -m pip install llmlingua>=0.2.0"
            )
        if self._compressor is None:
            kwargs = {
                "model_name": self.model_source,
                "device_map": self.device_map,
                "use_llmlingua2": self.use_llmlingua2,
                "llmlingua2_config": self.llmlingua2_config,
            }
            constructor = getattr(PromptCompressor, "__init__", PromptCompressor)
            if self._supports_constructor_kwarg(constructor, "local_files_only"):
                kwargs["local_files_only"] = self.local_files_only
            self._compressor = PromptCompressor(**kwargs)
        return self._compressor

    def _get_tokenizer(self, compressor):
        if self._tokenizer is not None:
            return self._tokenizer

        for attr_name in (
            "tokenizer",
            "context_tokenizer",
            "model_tokenizer",
            "llmlingua_tokenizer",
            "bert_tokenizer",
        ):
            tokenizer = getattr(compressor, attr_name, None)
            if tokenizer is not None:
                self._tokenizer = tokenizer
                self._tokenizer_is_fallback = False
                return tokenizer

        try:
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_source,
                local_files_only=self.local_files_only,
            )
            self._tokenizer_is_fallback = False
            return self._tokenizer
        except Exception:  # pragma: no cover - fallback is only for hostile runtime environments
            self._tokenizer = _FallbackTokenizer()
            self._tokenizer_is_fallback = True
            return self._tokenizer

    @staticmethod
    def _reasonable_length(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            length = int(value)
            if 0 < length < 1_000_000:
                return length
        return None

    def _encoder_max_length(self, tokenizer, compressor) -> int:
        for value in (
            getattr(tokenizer, "model_max_length", None),
            getattr(tokenizer, "max_len_single_sentence", None),
            getattr(getattr(tokenizer, "init_kwargs", {}), "get", lambda _key, _default=None: None)(
                "model_max_length",
                None,
            ),
        ):
            length = self._reasonable_length(value)
            if length is not None:
                return length

        for owner in (compressor, getattr(compressor, "model", None), getattr(compressor, "base_model", None)):
            config = getattr(owner, "config", None)
            length = self._reasonable_length(getattr(config, "max_position_embeddings", None))
            if length is not None:
                return length

        return DEFAULT_ENCODER_MAX_LENGTH

    @staticmethod
    def _token_ids(tokenizer, text: str) -> list[Any]:
        if hasattr(tokenizer, "encode"):
            try:
                token_ids = tokenizer.encode(text, add_special_tokens=False, verbose=False)
            except TypeError:
                try:
                    token_ids = tokenizer.encode(text, add_special_tokens=False)
                except TypeError:
                    token_ids = tokenizer.encode(text)
            if hasattr(token_ids, "tolist"):
                token_ids = token_ids.tolist()
            return list(token_ids)

        try:
            encoded = tokenizer(text, add_special_tokens=False, verbose=False)
        except TypeError:
            encoded = tokenizer(text, add_special_tokens=False)
        input_ids = encoded["input_ids"] if isinstance(encoded, dict) else encoded.input_ids
        if hasattr(input_ids, "tolist"):
            input_ids = input_ids.tolist()
        return list(input_ids)

    def _token_count(self, tokenizer, text: str) -> int:
        return len(self._token_ids(tokenizer, text))

    @staticmethod
    def _decode_tokens(tokenizer, token_ids: list[Any]) -> str | None:
        if not hasattr(tokenizer, "decode"):
            return None
        try:
            return str(
                tokenizer.decode(
                    token_ids,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=False,
                )
            ).strip()
        except TypeError:
            return str(tokenizer.decode(token_ids, skip_special_tokens=True)).strip()
        except Exception:
            return None

    def _split_text_recursively(self, text: str, tokenizer, token_budget: int) -> list[tuple[str, int]]:
        text = text.strip()
        if not text:
            return []

        token_count = self._token_count(tokenizer, text)
        if token_count <= token_budget:
            return [(text, token_count)]

        words = text.split()
        if len(words) > 1:
            midpoint = len(words) // 2
            left = " ".join(words[:midpoint])
            right = " ".join(words[midpoint:])
        elif len(text) > 1:
            midpoint = len(text) // 2
            left = text[:midpoint]
            right = text[midpoint:]
        else:
            raise RuntimeError(
                "Unable to split LLMLingua context into an encoder-safe chunk: "
                f"token_count={token_count}, budget={token_budget}"
            )

        return self._split_text_recursively(left, tokenizer, token_budget) + self._split_text_recursively(
            right,
            tokenizer,
            token_budget,
        )

    def _context_chunks(self, context_text: str, tokenizer, token_budget: int) -> list[tuple[str, int]]:
        token_ids = self._token_ids(tokenizer, context_text)
        if len(token_ids) <= token_budget:
            return [(context_text, len(token_ids))]

        if not self._tokenizer_is_fallback and hasattr(tokenizer, "decode"):
            chunks: list[tuple[str, int]] = []
            for index in range(0, len(token_ids), token_budget):
                decoded = self._decode_tokens(tokenizer, token_ids[index : index + token_budget])
                if decoded:
                    chunks.extend(self._split_text_recursively(decoded, tokenizer, token_budget))
            if chunks:
                return chunks

        return self._split_text_recursively(context_text, tokenizer, token_budget)

    def _chunk_plan(self, context_text: str, question_text: str, compressor) -> dict[str, Any]:
        tokenizer = self._get_tokenizer(compressor)
        encoder_max_length = self._encoder_max_length(tokenizer, compressor)
        question_tokens = self._token_count(tokenizer, question_text) if question_text else 0
        available_after_question = max(1, encoder_max_length - question_tokens - self.chunk_safety_margin)
        token_budget = min(self.max_context_tokens_per_chunk, encoder_max_length, available_after_question)
        chunks = self._context_chunks(context_text, tokenizer, token_budget)
        max_observed_tokens = max((token_count for _, token_count in chunks), default=0)
        if max_observed_tokens > token_budget:
            raise RuntimeError(
                "LLMLingua tokenizer chunk invariant failed before backend call: "
                f"max_observed_tokens={max_observed_tokens}, budget={token_budget}"
            )
        return {
            "tokenizer": tokenizer,
            "chunks": chunks,
            "token_budget": token_budget,
            "encoder_max_length": encoder_max_length,
            "question_tokens": question_tokens,
            "max_observed_tokens": max_observed_tokens,
            "safety_margin": encoder_max_length - token_budget,
            "chunking_mode": "fallback_estimate" if self._tokenizer_is_fallback else "tokenizer",
        }

    @staticmethod
    def _without_question_suffix(text: str, question: str) -> str:
        if question and text.endswith(question):
            return text[: -len(question)].strip()
        return text

    def compress(self, context: Any, question: Any, keep_rate: float | None):
        if keep_rate is None:
            keep_rate = self.default_keep_rate
        if not 0.0 < keep_rate <= 1.0:
            raise ValueError("keep_rate must be in the interval (0, 1].")

        context_text = str(context or "").strip()
        question_text = str(question or "").strip()

        if not context_text:
            merged_text = merge("", question_text)
            info = {
                "t_compress_ms": 0.0,
                "R_actual": 1.0,
                "N_original": 0,
                "N_compressed": 0,
                "keep_rate": keep_rate,
                "strategy": "llmlingua-2",
                "compressor_chunked": False,
                "compressor_chunk_count": 0,
                "compressor_chunking_mode": "tokenizer",
                "compressor_chunk_token_budget": self.max_context_tokens_per_chunk,
                "compressor_chunk_max_observed_tokens": 0,
                "compressor_chunk_encoder_max_length": DEFAULT_ENCODER_MAX_LENGTH,
                "compressor_chunk_safety_margin": DEFAULT_ENCODER_MAX_LENGTH - self.max_context_tokens_per_chunk,
                "compressor_chunk_backend_calls": 0,
            }
            info.update(self._source_metadata())
            return merged_text, info

        compressor = self._get_compressor()
        chunk_plan = self._chunk_plan(context_text, question_text, compressor)
        chunks = chunk_plan["chunks"]
        started = time.perf_counter()
        compressed_chunks = []
        n_original = 0
        n_compressed = 0
        backend_calls = 0
        for chunk, token_count in chunks:
            if token_count > chunk_plan["token_budget"]:
                raise RuntimeError(
                    "LLMLingua tokenizer chunk invariant failed before backend call: "
                    f"token_count={token_count}, budget={chunk_plan['token_budget']}"
                )
            result = compressor.compress_prompt(
                [chunk],
                question=question_text,
                rate=keep_rate,
                concate_question=False,
            )
            backend_calls += 1
            compressed_chunk = self._without_question_suffix(
                str(result.get("compressed_prompt", "")).strip(),
                question_text,
            )
            if compressed_chunk:
                compressed_chunks.append(compressed_chunk)
            n_original += int(result.get("origin_tokens") or token_count)
            n_compressed += int(
                result.get("compressed_tokens")
                or self._token_count(chunk_plan["tokenizer"], compressed_chunk)
            )
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        compressed_context = "\n\n".join(compressed_chunks).strip()
        ratio = float(n_original) / float(n_compressed) if n_compressed > 0 else 1.0

        if question_text and compressed_context.endswith(question_text):
            merged_text = compressed_context
        else:
            merged_text = merge(compressed_context, question_text)

        info = {
            "t_compress_ms": elapsed_ms,
            "R_actual": ratio,
            "N_original": n_original,
            "N_compressed": n_compressed,
            "keep_rate": keep_rate,
            "strategy": "llmlingua-2",
            "compressor_chunked": len(chunks) > 1,
            "compressor_chunk_count": len(chunks),
            "compressor_chunking_mode": chunk_plan["chunking_mode"],
            "compressor_chunk_token_budget": chunk_plan["token_budget"],
            "compressor_chunk_max_observed_tokens": chunk_plan["max_observed_tokens"],
            "compressor_chunk_encoder_max_length": chunk_plan["encoder_max_length"],
            "compressor_chunk_safety_margin": chunk_plan["safety_margin"],
            "compressor_chunk_backend_calls": backend_calls,
        }
        info.update(self._source_metadata())
        return merged_text, info


class _FallbackTokenizer:
    model_max_length = DEFAULT_ENCODER_MAX_LENGTH

    def encode(self, text, add_special_tokens=False):
        return str(text).split()


LlmlinguaCompressor = LLMLinguaCompressor
