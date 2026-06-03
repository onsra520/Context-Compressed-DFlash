from __future__ import annotations

import re
import time
from typing import Any

from .base import CompressorBase
from .segmentation import merge

DEFAULT_LLM_LINGUA_2_MODEL = "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"

try:
    from llmlingua import PromptCompressor
except ImportError:  # pragma: no cover - exercised through runtime dependency checks
    PromptCompressor = None


def _parse_ratio(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)x\s*$", value)
        if match:
            return float(match.group(1))
    return None


class LLMLinguaCompressor(CompressorBase):
    def __init__(
        self,
        model_name: str = DEFAULT_LLM_LINGUA_2_MODEL,
        device_map: str = "cpu",
        use_llmlingua2: bool = True,
        default_keep_rate: float = 0.5,
        llmlingua2_config: dict[str, Any] | None = None,
    ) -> None:
        self.model_name = model_name
        self.device_map = device_map
        self.use_llmlingua2 = use_llmlingua2
        self.default_keep_rate = default_keep_rate
        self.llmlingua2_config = llmlingua2_config or {}
        self._compressor = None

    @classmethod
    def from_config(cls, config: dict[str, Any] | None = None) -> "LLMLinguaCompressor":
        cfg = (((config or {}).get("compression") or {}).get("llmlingua") or {})
        return cls(
            model_name=cfg.get("model_name", DEFAULT_LLM_LINGUA_2_MODEL),
            device_map=cfg.get("device_map", "cpu"),
            use_llmlingua2=bool(cfg.get("use_llmlingua2", True)),
            default_keep_rate=float(cfg.get("default_keep_rate", 0.5)),
            llmlingua2_config=cfg.get("llmlingua2_config") or {},
        )

    def _get_compressor(self):
        if PromptCompressor is None:
            raise ImportError(
                "llmlingua is not installed in the active environment. "
                "Install it with: PYTHONPATH=src .venv/bin/python -m pip install llmlingua>=0.2.0"
            )
        if self._compressor is None:
            self._compressor = PromptCompressor(
                model_name=self.model_name,
                device_map=self.device_map,
                use_llmlingua2=self.use_llmlingua2,
                llmlingua2_config=self.llmlingua2_config,
            )
        return self._compressor

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
            }
            return merged_text, info

        compressor = self._get_compressor()
        started = time.perf_counter()
        result = compressor.compress_prompt(
            [context_text],
            question=question_text,
            rate=keep_rate,
            concate_question=False,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        compressed_context = str(result.get("compressed_prompt", "")).strip()
        n_original = int(result.get("origin_tokens", 0))
        n_compressed = int(result.get("compressed_tokens", 0))
        ratio = _parse_ratio(result.get("ratio"))
        if ratio is None:
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
        }
        return merged_text, info


LlmlinguaCompressor = LLMLinguaCompressor
