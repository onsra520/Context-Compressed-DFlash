"""Environment and model-path preflight."""

from __future__ import annotations

import importlib.util
from importlib.metadata import PackageNotFoundError, version
import platform
from pathlib import Path
import sys
from typing import Any

import torch

from ..config import Rec2Config
from ..errors import ConfigurationError


def _package_version(*names: str) -> str | None:
    for name in names:
        try:
            return version(name)
        except PackageNotFoundError:
            continue
    return None


def validate_environment(config: Rec2Config) -> dict[str, Any]:
    require_cuda = bool(config.get("validation.require_cuda", True))
    if require_cuda and not torch.cuda.is_available():
        raise RuntimeError("CUDA is required by config but is not available")
    if bool(config.get("validation.require_single_gpu", True)) and torch.cuda.device_count() != 1:
        raise RuntimeError(f"expected exactly one visible GPU, found {torch.cuda.device_count()}")
    paths = {
        "baseline": Path(config.require("models.baseline.local_path")),
        "target": Path(config.require("models.dflash.target.local_path")),
        "drafter": Path(config.require("models.dflash.drafter.local_path")),
        "compressor": Path(config.require("models.compressor.local_path")),
    }
    missing = [str(path) for key, path in paths.items() if key != "compressor" and not path.exists()]
    if missing:
        raise ConfigurationError(f"required model paths are missing: {missing}")
    awq_available = importlib.util.find_spec("awq") is not None
    result = {
        "python": platform.python_version(),
        "sys_executable": sys.executable,
        "venv_expected_path": str(config.root / ".venv"),
        "sys_executable_is_project_venv": Path(sys.executable).is_relative_to(config.root / ".venv"),
        "torch": torch.__version__,
        "package_versions": {
            "torch": _package_version("torch"),
            "transformers": _package_version("transformers"),
            "triton": _package_version("triton"),
            "accelerate": _package_version("accelerate"),
            "awq": _package_version("autoawq", "awq"),
            "safetensors": _package_version("safetensors"),
            "huggingface_hub": _package_version("huggingface-hub"),
        },
        "cuda_available": torch.cuda.is_available(),
        "cuda_runtime": torch.version.cuda,
        "visible_gpu_count": torch.cuda.device_count(),
        "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "total_vram_bytes": (
            int(torch.cuda.get_device_properties(0).total_memory) if torch.cuda.is_available() else None
        ),
        "awq_runtime_available": awq_available,
        "paths": {key: {"path": str(path), "exists": path.exists()} for key, path in paths.items()},
    }
    if str(config.require("models.baseline.quantization")).startswith("awq") and not awq_available:
        result["warning"] = "AWQ package not detected; install the awq optional dependencies"
    return result
