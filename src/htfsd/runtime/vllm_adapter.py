from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from typing import Any

from htfsd.low_tier.acceptance import greedy_exact_match
from htfsd.types import ModelConfig, TokenResult, VerificationResult

try:
    from vllm import LLM, SamplingParams
except Exception:
    LLM = None
    SamplingParams = None

VLLM_AVAILABLE = LLM is not None and SamplingParams is not None
VERIFICATION_ADAPTER_VERSION = "generated-greedy-v1"


def vllm_version() -> str:
    try:
        return metadata.version("vllm")
    except metadata.PackageNotFoundError:
        return "not-installed"


@dataclass
class VllmModelHandle:
    model_id_or_path: str
    tensor_parallel_size: int = 1
    dtype: str = "auto"
    gpu_memory_utilization: float | None = None
    llm: Any | None = None

    @classmethod
    def from_config(cls, config: ModelConfig) -> "VllmModelHandle":
        return cls(
            model_id_or_path=config.model_id_or_path,
            tensor_parallel_size=config.tensor_parallel_size,
            dtype=config.dtype,
            gpu_memory_utilization=config.gpu_memory_utilization,
        )

    def load(self) -> Any:
        if self.llm is not None:
            return self.llm
        if not VLLM_AVAILABLE:
            raise RuntimeError("vLLM is not available in this environment")
        kwargs: dict[str, Any] = {
            "model": self.model_id_or_path,
            "tensor_parallel_size": self.tensor_parallel_size,
            "dtype": self.dtype,
        }
        if self.gpu_memory_utilization is not None:
            kwargs["gpu_memory_utilization"] = self.gpu_memory_utilization
        self.llm = LLM(**kwargs)
        return self.llm


class VllmGenerationAdapter:
    def __init__(self, handle: VllmModelHandle):
        self._handle = handle

    def generate_text(
        self,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float = 0.0,
        top_p: float = 1.0,
    ) -> str:
        llm = self._handle.load()
        params = SamplingParams(
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        outputs = llm.generate([prompt], params)
        return outputs[0].outputs[0].text


class VllmVerificationAdapter:
    def __init__(self, handle: VllmModelHandle, tokenizer):
        self._handle = handle
        self._tokenizer = tokenizer

    def verify_greedy_prefix(
        self,
        context_token_ids: list[int],
        candidate_token_ids: list[int],
    ) -> VerificationResult:
        greedy_ids = self._greedy_ids_for_positions(
            context_token_ids=context_token_ids,
            positions=len(candidate_token_ids),
        )
        return greedy_exact_match(
            candidate_token_ids=candidate_token_ids,
            greedy_token_ids=greedy_ids,
        )

    def greedy_next_token(self, context_token_ids: list[int]) -> TokenResult:
        greedy_ids = self._greedy_ids_for_positions(context_token_ids=context_token_ids, positions=1)
        token_id = greedy_ids[0]
        text = self._tokenizer.decode([token_id], skip_special_tokens=True)
        return TokenResult(
            token_id=token_id,
            text=text,
            is_eos=token_id == getattr(self._tokenizer, "eos_token_id", None),
        )

    def _greedy_ids_for_positions(self, *, context_token_ids: list[int], positions: int) -> list[int]:
        llm = self._handle.load()
        params = SamplingParams(
            temperature=0.0,
            max_tokens=positions,
            logprobs=1,
        )
        prompt = {"prompt_token_ids": context_token_ids}
        outputs = llm.generate([prompt], params)
        generated = outputs[0].outputs[0].token_ids
        return list(generated[:positions])
