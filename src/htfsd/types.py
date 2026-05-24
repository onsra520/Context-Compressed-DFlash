"""Shared dataclasses for HTFS-Decoding."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


MODEL_STATUS_OK = "ok"
MODEL_STATUS_MISSING_DIR = "missing_model_dir"
MODEL_STATUS_MISSING_FILE = "missing_model_file"
MODEL_STATUS_AMBIGUOUS = "ambiguous_model_files"


@dataclass(frozen=True)
class ModelDiscovery:
    """Resolved model-directory and GGUF discovery status."""

    name: str
    model_dir: Path
    model_file: Path | None
    discovered_model_file: Path | None
    status: str
    error_code: str | None = None
    candidates: list[Path] = field(default_factory=list)
    optional: bool = False
    expected_device: str = "auto"
    n_gpu_layers: int = -1

    @property
    def ok(self) -> bool:
        """Return whether the model has one usable GGUF file."""

        return self.status == MODEL_STATUS_OK and self.discovered_model_file is not None


@dataclass(frozen=True)
class RuntimeConfig:
    """Backend settings shared by smoke commands."""

    backend: str
    n_ctx: int
    seed: int


@dataclass(frozen=True)
class GenerationConfig:
    """Small generation settings for smoke commands."""

    max_tokens: int
    temperature: float


@dataclass(frozen=True)
class TextGenerationResult:
    """Text returned by a runtime backend plus optional token count."""

    text: str
    completion_tokens: int | None = None


@dataclass(frozen=True)
class BridgeDraft:
    """Normalized Qwen draft text for the Gemma text bridge."""

    bridge_status: str
    normalized_text: str
    rejection_reason: str | None = None


@dataclass(frozen=True)
class PairSmokeResult:
    """Result for the low-tier Qwen-to-Gemma pair smoke path."""

    prompt: str
    raw_draft_text: str
    normalized_draft_text: str
    gemma_output_text: str
    bridge_status: str
    rejection_reason: str | None
    fallback_count: int
    draft_valid_count: int
    draft_rejected_count: int
    latency_seconds: float
    qwen_decode_tokens_per_second: float | None
    gemma_decode_tokens_per_second: float | None

    @property
    def tokens_per_second(self) -> float | None:
        values = [
            value
            for value in (
                self.qwen_decode_tokens_per_second,
                self.gemma_decode_tokens_per_second,
            )
            if value is not None
        ]
        if not values:
            return None
        return sum(values) / len(values)

    @property
    def metrics(self) -> dict[str, float | int | None]:
        """Return allowed smoke metrics without speculative claims."""

        return {
            "draft_valid_count": self.draft_valid_count,
            "draft_rejected_count": self.draft_rejected_count,
            "fallback_count": self.fallback_count,
            "latency_seconds": self.latency_seconds,
            "tokens_per_second": self.tokens_per_second,
            "qwen_decode_tokens_per_second": self.qwen_decode_tokens_per_second,
            "gemma_decode_tokens_per_second": self.gemma_decode_tokens_per_second,
        }


@dataclass(frozen=True)
class HTFSDConfig:
    """Complete loaded configuration with structured model discovery."""

    repo_root: Path
    config_path: Path
    models: dict[str, ModelDiscovery]
    runtime: RuntimeConfig
    generation: GenerationConfig
