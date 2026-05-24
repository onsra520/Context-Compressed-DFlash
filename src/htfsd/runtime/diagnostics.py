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


def collect_environment_diagnostics(
    config: HTFSDConfig,
    *,
    llama_cpp_supports_gpu_offload: bool | None = None,
    observed_gpu_offload: dict[str, bool | None] | None = None,
) -> dict[str, Any]:
    """Collect agent-readable environment and model-discovery diagnostics."""

    supports_gpu_offload = (
        _llama_cpp_supports_gpu_offload()
        if llama_cpp_supports_gpu_offload is None
        else llama_cpp_supports_gpu_offload
    )
    observed = observed_gpu_offload or {}
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
            "llama_cpp_supports_gpu_offload": supports_gpu_offload,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        },
        "runtime": {
            "n_ctx": config.runtime.n_ctx,
            "seed": config.runtime.seed,
        },
        "models": {
            name: _model_diagnostics(
                model,
                observed_backend=config.runtime.backend,
                observed_gpu_offload=observed.get(name),
                llama_cpp_supports_gpu_offload=supports_gpu_offload,
            )
            for name, model in config.models.items()
        },
    }


def infer_quantization(path: Path | None) -> str | None:
    """Infer common GGUF quantization labels from a filename."""

    if path is None:
        return None
    match = QUANTIZATION_PATTERN.search(path.name)
    return match.group(1) if match else None


def _model_diagnostics(
    model: ModelDiscovery,
    *,
    observed_backend: str,
    observed_gpu_offload: bool | None,
    llama_cpp_supports_gpu_offload: bool,
) -> dict[str, Any]:
    status = model.status
    if model.optional and status != MODEL_STATUS_OK:
        status = "optional_missing" if status in {"missing_model_dir", "missing_model_file"} else status
    device_status = _device_status(
        model=model,
        model_status=status,
        observed_gpu_offload=observed_gpu_offload,
        llama_cpp_supports_gpu_offload=llama_cpp_supports_gpu_offload,
    )
    return {
        "model_name": model.name,
        "model_dir": str(model.model_dir),
        "configured_model_file": str(model.model_file) if model.model_file else None,
        "discovered_model_file": str(model.discovered_model_file) if model.discovered_model_file else None,
        "model_path": str(model.discovered_model_file) if model.discovered_model_file else None,
        "status": status,
        "error_code": model.error_code,
        "candidates": [str(path) for path in model.candidates],
        "quantization": infer_quantization(model.discovered_model_file),
        "expected_device": model.expected_device,
        "configured_n_gpu_layers": model.n_gpu_layers,
        "observed_backend": observed_backend,
        "observed_gpu_offload": observed_gpu_offload,
        "device_status": device_status,
    }


def _device_status(
    *,
    model: ModelDiscovery,
    model_status: str,
    observed_gpu_offload: bool | None,
    llama_cpp_supports_gpu_offload: bool,
) -> str:
    if model_status == "optional_missing":
        return "optional_missing"
    if model_status != MODEL_STATUS_OK:
        return "unknown"
    if model.expected_device == "cpu" and model.n_gpu_layers == 0:
        return "ok"
    if model.expected_device == "cuda":
        if not llama_cpp_supports_gpu_offload:
            return "cuda_backend_unavailable"
        if observed_gpu_offload is False:
            return "device_policy_mismatch"
        if observed_gpu_offload is True:
            return "ok"
        return "unknown"
    if model.expected_device == "auto":
        return "ok" if observed_gpu_offload else "functional_cpu_only"
    return "unknown"


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


def _llama_cpp_supports_gpu_offload() -> bool:
    try:
        import llama_cpp

        return bool(llama_cpp.llama_supports_gpu_offload())
    except Exception:
        return False


def _package_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None
