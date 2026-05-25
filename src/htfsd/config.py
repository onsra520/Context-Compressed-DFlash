"""Configuration loading and GGUF model discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from htfsd.types import (
    GenerationConfig,
    HTFSDConfig,
    MODEL_STATUS_AMBIGUOUS,
    MODEL_STATUS_MISSING_DIR,
    MODEL_STATUS_MISSING_FILE,
    MODEL_STATUS_OK,
    MODEL_ROLE_ALIASES,
    ModelDiscovery,
    ModelRegistry,
    RuntimeConfig,
)

DEFAULT_CONFIG_PATH = Path("configs/local.example.yaml")
REQUIRED_MODEL_KEYS = ("drafter", "verifier", "target")
ALLOWED_EXPECTED_DEVICES = {"cpu", "cuda", "auto"}
DEFAULT_MODEL_POLICY = {
    "drafter": {"expected_device": "cpu", "n_gpu_layers": 0, "optional": False},
    "verifier": {"expected_device": "cuda", "n_gpu_layers": -1, "optional": False},
    "target": {"expected_device": "cuda", "n_gpu_layers": -1, "optional": True},
}


def find_repo_root(start: Path | None = None) -> Path:
    """Find the project root from the current file layout."""

    current = (start or Path.cwd()).resolve()
    candidates = [current, *current.parents]
    for candidate in candidates:
        if (candidate / "pyproject.toml").exists() and (candidate / "configs").is_dir():
            return candidate
        if (candidate / ".git").is_dir() and (candidate / "README.md").exists():
            return candidate
    return current


def resolve_config_path(config_path: str | Path | None, *, repo_root: Path | None = None) -> Path:
    """Resolve the explicit config path or the default config path."""

    root = (repo_root or find_repo_root()).resolve()
    raw_path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    return raw_path if raw_path.is_absolute() else root / raw_path


def load_config(
    config_path: str | Path | None = None,
    *,
    repo_root: Path | None = None,
) -> HTFSDConfig:
    """Load config and discover GGUF files without raising for missing models."""

    root = (repo_root or find_repo_root()).resolve()
    resolved_config = resolve_config_path(config_path, repo_root=root)
    if not resolved_config.exists():
        raise FileNotFoundError(
            f"config file not found: {resolved_config}. "
            "Create configs/local.example.yaml from the expected template."
        )

    raw = yaml.safe_load(resolved_config.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"config file must contain a mapping: {resolved_config}")

    models = _load_models(raw.get("models"), repo_root=root)
    runtime = raw.get("runtime", {})
    generation = raw.get("generation", {})

    return HTFSDConfig(
        repo_root=root,
        config_path=resolved_config,
        models=models,
        runtime=RuntimeConfig(
            backend=str(runtime.get("backend", "llama_cpp")),
            n_ctx=int(runtime.get("n_ctx", 2048)),
            seed=int(runtime.get("seed", 42)),
        ),
        generation=GenerationConfig(
            max_tokens=int(generation.get("max_tokens", 64)),
            temperature=float(generation.get("temperature", 0.0)),
        ),
    )


def _load_models(raw_models: Any, *, repo_root: Path) -> ModelRegistry:
    if not isinstance(raw_models, dict):
        raise ValueError("config must contain a models mapping")

    discoveries: dict[str, ModelDiscovery] = {}
    for name in REQUIRED_MODEL_KEYS:
        raw_model = _raw_model_for_role(raw_models, name)
        if not isinstance(raw_model, dict):
            raise ValueError(f"models.{name} must be a mapping")
        default_policy = DEFAULT_MODEL_POLICY[name]
        expected_device = str(raw_model.get("expected_device", default_policy["expected_device"]))
        if expected_device not in ALLOWED_EXPECTED_DEVICES:
            raise ValueError(
                f"models.{name}.expected_device must be one of "
                f"{sorted(ALLOWED_EXPECTED_DEVICES)}"
            )
        discoveries[name] = discover_model_file(
            name=name,
            model_dir=raw_model.get("model_dir"),
            model_file=raw_model.get("model_file"),
            repo_root=repo_root,
            optional=bool(raw_model.get("optional", default_policy["optional"])),
            expected_device=expected_device,
            n_gpu_layers=int(raw_model.get("n_gpu_layers", default_policy["n_gpu_layers"])),
        )
    return ModelRegistry(discoveries)


def _raw_model_for_role(raw_models: dict[str, Any], role: str) -> Any:
    if role in raw_models:
        return raw_models[role]
    for alias, canonical in MODEL_ROLE_ALIASES.items():
        if canonical == role and alias in raw_models:
            return raw_models[alias]
    return None


def discover_model_file(
    *,
    name: str,
    model_dir: str | Path | None,
    model_file: str | Path | None,
    repo_root: Path,
    optional: bool = False,
    expected_device: str = "auto",
    n_gpu_layers: int = -1,
) -> ModelDiscovery:
    """Resolve a model GGUF file from an optional override or directory scan."""

    if model_dir is None:
        raise ValueError(f"models.{name}.model_dir is required")

    resolved_dir = _resolve_path(model_dir, repo_root=repo_root)
    if model_file:
        resolved_file = _resolve_path(model_file, repo_root=repo_root)
        if resolved_file.suffix.lower() != ".gguf":
            return ModelDiscovery(
                name=name,
                model_dir=resolved_dir,
                model_file=resolved_file,
                discovered_model_file=None,
                status=MODEL_STATUS_MISSING_FILE,
                error_code="model_file_not_gguf",
                optional=optional,
                expected_device=expected_device,
                n_gpu_layers=n_gpu_layers,
            )
        if not resolved_file.exists():
            return ModelDiscovery(
                name=name,
                model_dir=resolved_dir,
                model_file=resolved_file,
                discovered_model_file=None,
                status=MODEL_STATUS_MISSING_FILE,
                error_code="missing_model_file",
                optional=optional,
                expected_device=expected_device,
                n_gpu_layers=n_gpu_layers,
            )
        return ModelDiscovery(
            name=name,
            model_dir=resolved_dir,
            model_file=resolved_file,
            discovered_model_file=resolved_file,
            status=MODEL_STATUS_OK,
            candidates=[resolved_file],
            optional=optional,
            expected_device=expected_device,
            n_gpu_layers=n_gpu_layers,
        )

    if not resolved_dir.is_dir():
        return ModelDiscovery(
            name=name,
            model_dir=resolved_dir,
            model_file=None,
            discovered_model_file=None,
            status=MODEL_STATUS_MISSING_DIR,
            error_code="missing_model_dir",
            optional=optional,
            expected_device=expected_device,
            n_gpu_layers=n_gpu_layers,
        )

    candidates = sorted(path for path in resolved_dir.iterdir() if path.is_file() and path.suffix.lower() == ".gguf")
    if len(candidates) == 1:
        return ModelDiscovery(
            name=name,
            model_dir=resolved_dir,
            model_file=None,
            discovered_model_file=candidates[0],
            status=MODEL_STATUS_OK,
            candidates=candidates,
            optional=optional,
            expected_device=expected_device,
            n_gpu_layers=n_gpu_layers,
        )
    if not candidates:
        return ModelDiscovery(
            name=name,
            model_dir=resolved_dir,
            model_file=None,
            discovered_model_file=None,
            status=MODEL_STATUS_MISSING_FILE,
            error_code="missing_model",
            optional=optional,
            expected_device=expected_device,
            n_gpu_layers=n_gpu_layers,
        )
    return ModelDiscovery(
        name=name,
        model_dir=resolved_dir,
        model_file=None,
        discovered_model_file=None,
        status=MODEL_STATUS_AMBIGUOUS,
        error_code="ambiguous_model",
        candidates=candidates,
        optional=optional,
        expected_device=expected_device,
        n_gpu_layers=n_gpu_layers,
    )


def _resolve_path(path: str | Path, *, repo_root: Path) -> Path:
    raw_path = Path(path)
    return raw_path if raw_path.is_absolute() else repo_root / raw_path
