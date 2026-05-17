from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelConfig:
    model_id_or_path: str
    tensor_parallel_size: int = 1
    dtype: str = "auto"
    gpu_memory_utilization: float | None = None


@dataclass(frozen=True)
class RuntimeConfig:
    backend: str
    execution_mode: str
    max_context_tokens: int
    seed: int


@dataclass(frozen=True)
class GenerationConfig:
    max_new_tokens: int
    stop_on_eos: bool


@dataclass(frozen=True)
class DFlashConfig:
    parser: str
    required_fields: list[str]
    default_max_tokens: int
    hard_max_tokens: int
    experimental_repair: bool


@dataclass(frozen=True)
class LowTierConfig:
    acceptance_policy: str
    fallback_policy: str
    fallback_tokens_per_cycle: int


@dataclass(frozen=True)
class SamplingConfig:
    enabled: bool
    experimental: bool
    temperature: float
    top_p: float


@dataclass(frozen=True)
class DecodingConfig:
    default: str
    sampling: SamplingConfig


@dataclass(frozen=True)
class BenchmarkDatasetConfig:
    enabled: bool
    name: str | None
    split: str | None


@dataclass(frozen=True)
class BenchmarkConfig:
    fixture_path: str
    dataset: BenchmarkDatasetConfig


@dataclass(frozen=True)
class AppConfig:
    qwen_drafter: ModelConfig
    gemma_e2b: ModelConfig
    gemma_e4b_baseline: ModelConfig
    runtime: RuntimeConfig
    generation: GenerationConfig
    dflash: DFlashConfig
    low_tier: LowTierConfig
    decoding: DecodingConfig
    benchmark: BenchmarkConfig


@dataclass(frozen=True)
class DraftResult:
    raw_text: str
    draft_text: str | None
    confidence: float | None
    max_tokens: int | None
    parse_ok: bool
    error_reason: str | None = None


@dataclass(frozen=True)
class DFlashParseResult:
    draft_text: str | None
    confidence: float | None
    max_tokens: int | None
    parse_ok: bool
    error_reason: str | None = None


@dataclass(frozen=True)
class TokenResult:
    token_id: int
    text: str
    is_eos: bool = False


@dataclass(frozen=True)
class VerificationResult:
    accepted_token_ids: list[int]
    rejected_token_id: int | None
    reject_position: int | None
    candidate_exhausted: bool


@dataclass(frozen=True)
class CycleTrace:
    cycle_index: int
    context_tokens: int
    dflash_parse_ok: bool
    malformed_dflash: bool
    draft_text_chars: int
    draft_candidate_tokens: int
    accepted_tokens: int
    reject_position: int | None
    candidate_exhausted: bool
    fallback_used: bool
    qwen_draft_ms: float
    dflash_parse_ms: float
    gemma_retokenize_ms: float
    e2b_verify_ms: float
    cycle_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GenerationMetrics:
    generated_tokens: int
    cycles: int
    drafted_candidate_tokens: int
    accepted_tokens: int
    fallback_tokens: int
    malformed_dflash_count: int
    dflash_parse_fail_count: int
    dflash_schema_invalid_count: int
    dflash_empty_draft_count: int
    retokenized_empty_count: int
    low_acceptance_rate: float
    fallback_rate: float
    total_ms: float
    tokens_per_second: float
    latency_per_token_ms: float
    execution_mode: str
    decoding_mode: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GenerateResult:
    text: str
    token_ids: list[int]
    metrics: GenerationMetrics
    trace: list[CycleTrace] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "token_ids": self.token_ids,
            "metrics": self.metrics.to_dict(),
            "trace": [item.to_dict() for item in self.trace],
        }
