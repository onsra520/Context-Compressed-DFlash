"""Process and request-level reproducibility controls."""

from __future__ import annotations

import os
import random
from typing import Any

import torch


def configure_determinism(
    *,
    seed: int,
    deterministic: bool,
    allow_tf32: bool,
    matmul_precision: str,
    sdpa_kernel: str = "math",
) -> dict[str, Any]:
    """Apply all supported Python, Torch, and CUDA reproducibility controls."""
    if sdpa_kernel not in {"math", "auto"}:
        raise ValueError(f"unsupported SDPA kernel policy: {sdpa_kernel}")
    seed = int(seed)
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)

    torch.use_deterministic_algorithms(bool(deterministic))
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = bool(deterministic)
        torch.backends.cudnn.benchmark = not bool(deterministic)

    effective_tf32 = bool(allow_tf32) and not bool(deterministic)
    if hasattr(torch.backends, "cuda") and hasattr(torch.backends.cuda, "matmul"):
        torch.backends.cuda.matmul.allow_tf32 = effective_tf32
        if sdpa_kernel == "math":
            torch.backends.cuda.enable_flash_sdp(False)
            torch.backends.cuda.enable_mem_efficient_sdp(False)
            torch.backends.cuda.enable_math_sdp(True)
        else:
            # Restore the dispatcher choices explicitly because a previous math-only
            # request may have changed these process-global Torch settings.
            torch.backends.cuda.enable_flash_sdp(True)
            torch.backends.cuda.enable_mem_efficient_sdp(True)
            torch.backends.cuda.enable_math_sdp(True)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.allow_tf32 = effective_tf32
    torch.set_float32_matmul_precision(str(matmul_precision))

    flash_enabled = (
        bool(torch.backends.cuda.flash_sdp_enabled()) if torch.cuda.is_available() else None
    )
    memory_efficient_enabled = (
        bool(torch.backends.cuda.mem_efficient_sdp_enabled())
        if torch.cuda.is_available()
        else None
    )
    math_enabled = (
        bool(torch.backends.cuda.math_sdp_enabled()) if torch.cuda.is_available() else None
    )
    effective_allowed_backends = [
        name
        for name, enabled in (
            ("flash", flash_enabled),
            ("memory_efficient", memory_efficient_enabled),
            ("math", math_enabled),
        )
        if enabled is True
    ]
    return {
        "seed": seed,
        "python_random_seeded": True,
        "python_hash_seed_environment": os.environ["PYTHONHASHSEED"],
        "torch_initial_seed": int(torch.initial_seed()),
        "cuda_seeded": bool(torch.cuda.is_available()),
        "deterministic_algorithms": bool(torch.are_deterministic_algorithms_enabled()),
        "cudnn_deterministic": bool(torch.backends.cudnn.deterministic),
        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
        "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"],
        "allow_tf32_requested": bool(allow_tf32),
        "allow_tf32_effective": effective_tf32,
        "matmul_precision": str(matmul_precision),
        "configured_attention_backend": "sdpa",
        "configured_sdpa_kernel_policy": sdpa_kernel,
        "sdpa_kernel_policy": sdpa_kernel,
        "dispatcher_state_scope": "kernel availability, not observed kernel execution",
        "actual_kernel_observed": False,
        "actual_backend": None,
        "effective_allowed_backends": effective_allowed_backends,
        "pytorch_allocator_environment": os.environ.get("PYTORCH_ALLOC_CONF"),
        "flash_sdp_enabled": flash_enabled,
        "mem_efficient_sdp_enabled": memory_efficient_enabled,
        "math_sdp_enabled": math_enabled,
    }
