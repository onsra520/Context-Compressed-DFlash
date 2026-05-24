"""Environment and GGUF model diagnostics."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path
import os
import platform
import re
import sys
from typing import Any

from htfsd.types import HTFSDConfig, MODEL_STATUS_OK, ModelDiscovery

QUANTIZATION_PATTERN = re.compile(r"(Q\d(?:_[A-Z0-9]+)+|Q\d)")


def collect_environment_diagnostics(config: HTFSDConfig) -> dict[str, Any]:
    """Collect agent-readable environment and model-discovery diagnostics."""

    return {
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "virtualenv": os.environ.get("VIRTUAL_ENV"),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "is_wsl": _is_wsl(),
        },
        "backend": {
            "name": config.runtime.backend,
            "llama_cpp_importable": _module_importable("llama_cpp"),
            "llama_cpp_version": _package_version("llama-cpp-python"),
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        },
        "runtime": {
            "n_ctx": config.runtime.n_ctx,
            "n_gpu_layers": config.runtime.n_gpu_layers,
            "seed": config.runtime.seed,
        },
        "models": {
            name: _model_diagnostics(model) for name, model in config.models.items()
        },
    }


def infer_quantization(path: Path | None) -> str | None:
    """Infer common GGUF quantization labels from a filename."""

    if path is None:
        return None
    match = QUANTIZATION_PATTERN.search(path.name)
    return match.group(1) if match else None


def _model_diagnostics(model: ModelDiscovery) -> dict[str, Any]:
    status = model.status
    if model.optional and status != MODEL_STATUS_OK:
        status = "optional_missing" if status in {"missing_model_dir", "missing_model_file"} else status
    return {
        "model_dir": str(model.model_dir),
        "configured_model_file": str(model.model_file) if model.model_file else None,
        "discovered_model_file": str(model.discovered_model_file) if model.discovered_model_file else None,
        "status": status,
        "error_code": model.error_code,
        "candidates": [str(path) for path in model.candidates],
        "quantization": infer_quantization(model.discovered_model_file),
    }


def _is_wsl() -> bool:
    release = platform.release().lower()
    if "microsoft" in release or "wsl" in release:
        return True
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False


def _module_importable(module_name: str) -> bool:
    try:
        __import__(module_name)
    except Exception:
        return False
    return True


def _package_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None
