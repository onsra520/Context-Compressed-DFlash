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

    @property
    def ok(self) -> bool:
        """Return whether the model has one usable GGUF file."""

        return self.status == MODEL_STATUS_OK and self.discovered_model_file is not None


@dataclass(frozen=True)
class RuntimeConfig:
    """Backend settings shared by smoke commands."""

    backend: str
    n_ctx: int
    n_gpu_layers: int
    seed: int


@dataclass(frozen=True)
class GenerationConfig:
    """Small generation settings for smoke commands."""

    max_tokens: int
    temperature: float


@dataclass(frozen=True)
class HTFSDConfig:
    """Complete loaded configuration with structured model discovery."""

    repo_root: Path
    config_path: Path
    models: dict[str, ModelDiscovery]
    runtime: RuntimeConfig
    generation: GenerationConfig
