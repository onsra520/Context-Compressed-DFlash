"""Environment and model-path preflight."""

from __future__ import annotations

import importlib.util
from importlib.metadata import PackageNotFoundError, version
import os
import platform
from pathlib import Path
import shutil
import sys
from typing import Any

import torch

from ..config import Config
from ..errors import ConfigurationError


def _package_version(*names: str) -> str | None:
    for name in names:
        try:
            return version(name)
        except PackageNotFoundError:
            continue
    return None


def _module_origin(name: str) -> str | None:
    spec = importlib.util.find_spec(name)
    return str(spec.origin) if spec is not None and spec.origin is not None else None


def validate_environment(config: Config) -> dict[str, Any]:
    require_cuda = bool(config.require("validation.require_cuda"))
    if require_cuda and not torch.cuda.is_available():
        raise RuntimeError("CUDA is required by config but is not available")
    if bool(config.require("validation.require_single_gpu")) and torch.cuda.device_count() != 1:
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
        "which_python": shutil.which("python"),
        "sys_executable": sys.executable,
        "sys_prefix": sys.prefix,
        "virtual_env": os.environ.get("VIRTUAL_ENV"),
        "conda_prefix": os.environ.get("CONDA_PREFIX"),
        "pythonpath": os.environ.get("PYTHONPATH"),
        "sys_path": list(sys.path),
        "venv_expected_path": str(config.root / ".venv"),
        "sys_executable_is_project_venv": Path(sys.executable).is_relative_to(config.root / ".venv"),
        "sys_prefix_is_project_venv": Path(sys.prefix).resolve() == (config.root / ".venv").resolve(),
        "external_site_packages": [
            entry
            for entry in sys.path
            if "site-packages" in entry
            and not Path(entry).resolve().is_relative_to((config.root / ".venv").resolve())
        ],
        "import_paths": {
            name: _module_origin(name)
            for name in ("ccdf", "torch", "transformers", "llmlingua", "awq")
        },
        "torch": torch.__version__,
        "package_versions": {
            "torch": _package_version("torch"),
            "transformers": _package_version("transformers"),
            "triton": _package_version("triton"),
            "accelerate": _package_version("accelerate"),
            "awq": _package_version("autoawq", "awq"),
            "llmlingua": _package_version("llmlingua"),
            "safetensors": _package_version("safetensors"),
            "huggingface_hub": _package_version("huggingface-hub"),
        },
        "cuda_available": torch.cuda.is_available(),
        "cuda_runtime": torch.version.cuda,
        "visible_gpu_count": torch.cuda.device_count(),
        "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "compute_capability": (
            list(torch.cuda.get_device_capability(0)) if torch.cuda.is_available() else None
        ),
        "process_default_sdpa_state": {
            "configured_attention_backend": config.require("runtime.attention_backend"),
            "configured_kernel": config.require("runtime.sdpa_kernel"),
            "flash_enabled": (
                bool(torch.backends.cuda.flash_sdp_enabled()) if torch.cuda.is_available() else None
            ),
            "memory_efficient_enabled": (
                bool(torch.backends.cuda.mem_efficient_sdp_enabled())
                if torch.cuda.is_available() else None
            ),
            "math_enabled": (
                bool(torch.backends.cuda.math_sdp_enabled()) if torch.cuda.is_available() else None
            ),
            "matmul_tf32_enabled": (
                bool(torch.backends.cuda.matmul.allow_tf32)
                if torch.cuda.is_available() else None
            ),
            "cudnn_tf32_enabled": (
                bool(torch.backends.cudnn.allow_tf32) if torch.cuda.is_available() else None
            ),
        },
        "local_only": {
            "config_local_files_only": config.require("runtime.local_files_only"),
            "hf_hub_offline": os.environ.get("HF_HUB_OFFLINE"),
            "transformers_offline": os.environ.get("TRANSFORMERS_OFFLINE"),
        },
        "total_vram_bytes": (
            int(torch.cuda.get_device_properties(0).total_memory) if torch.cuda.is_available() else None
        ),
        "awq_runtime_available": awq_available,
        "compatibility_risks": [
            {
                "component": "AutoAWQ",
                "risk": "installed package emits an upstream deprecation warning",
                "batch_gate": False,
            }
        ] if awq_available else [],
        "paths": {key: {"path": str(path), "exists": path.exists()} for key, path in paths.items()},
    }
    if str(config.require("models.baseline.quantization")).startswith("awq") and not awq_available:
        result["warning"] = "AWQ package not detected; install the awq optional dependencies"
    return result
