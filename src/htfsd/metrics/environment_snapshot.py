"""Environment snapshot helpers for benchmark-readiness manifests."""

from __future__ import annotations

from importlib import metadata
import platform
import subprocess
import sys
from typing import Any


UNKNOWN = "unknown"


def build_environment_snapshot(
    *,
    config_path: str,
    prompt_set_id: str,
    runtime_backend: str,
    package_names: tuple[str, ...] = ("llama-cpp-python",),
) -> dict[str, Any]:
    """Build a best-effort environment snapshot without failing on missing optional details."""

    cuda_info = _nvidia_smi_info()
    return {
        "os": platform.platform() or UNKNOWN,
        "python_version": sys.version.split()[0] if sys.version else UNKNOWN,
        "package_versions": _package_versions(package_names),
        "llama_cpp_python_version": _package_version("llama-cpp-python"),
        "cuda_available": cuda_info.get("cuda_available", UNKNOWN),
        "cuda_toolkit_version_if_available": cuda_info.get("cuda_toolkit_version_if_available", UNKNOWN),
        "gpu_name_if_available": cuda_info.get("gpu_name_if_available", UNKNOWN),
        "driver_version_if_available": cuda_info.get("driver_version_if_available", UNKNOWN),
        "git_commit": _git_commit(),
        "config_path": config_path,
        "prompt_set_id": prompt_set_id,
        "runtime_backend": runtime_backend,
    }


def _package_versions(package_names: tuple[str, ...]) -> dict[str, str]:
    return {name: _package_version(name) for name in package_names}


def _package_version(package_name: str) -> str:
    try:
        return metadata.version(package_name)
    except Exception:
        return UNKNOWN


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return UNKNOWN
    if result.returncode != 0:
        return UNKNOWN
    return result.stdout.strip() or UNKNOWN


def _nvidia_smi_info() -> dict[str, Any]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version",
                "--format=csv,noheader",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return {
            "cuda_available": False,
            "cuda_toolkit_version_if_available": UNKNOWN,
            "gpu_name_if_available": UNKNOWN,
            "driver_version_if_available": UNKNOWN,
        }
    if result.returncode != 0:
        return {
            "cuda_available": False,
            "cuda_toolkit_version_if_available": UNKNOWN,
            "gpu_name_if_available": UNKNOWN,
            "driver_version_if_available": UNKNOWN,
        }
    first_line = (result.stdout or "").splitlines()[0] if result.stdout else ""
    gpu_name, _, driver_version = first_line.partition(",")
    return {
        "cuda_available": True,
        "cuda_toolkit_version_if_available": UNKNOWN,
        "gpu_name_if_available": gpu_name.strip() or UNKNOWN,
        "driver_version_if_available": driver_version.strip() or UNKNOWN,
    }
