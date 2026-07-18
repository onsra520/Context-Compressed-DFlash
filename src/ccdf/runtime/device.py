"""CUDA placement, timing, and memory gates."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import torch

from ..errors import MemoryBudgetError, ModelContractError
from ..schemas import MemoryStats

GIB = 1024**3


def configure_cuda_allocator_environment(value: str | None) -> dict[str, Any]:
    """Apply a config-owned allocator policy before the first CUDA allocation."""
    if value is None:
        return {
            "configured": None,
            "environment": os.environ.get("PYTORCH_ALLOC_CONF"),
            "applied": False,
        }
    value = str(value)
    current = os.environ.get("PYTORCH_ALLOC_CONF")
    if torch.cuda.is_initialized() and current != value:
        raise RuntimeError("CUDA allocator policy cannot change after CUDA initialization")
    os.environ["PYTORCH_ALLOC_CONF"] = value
    return {"configured": value, "environment": value, "applied": True}


def synchronize(device: Any | None = None) -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize(device=device)


def reset_peak_memory() -> None:
    if torch.cuda.is_available():
        synchronize()
        torch.cuda.reset_peak_memory_stats()
        synchronize()


def current_memory_state() -> dict[str, int | None]:
    """Return the non-peak CUDA allocator state at a request boundary."""
    if not torch.cuda.is_available():
        return {"allocated_bytes": None, "reserved_bytes": None}
    synchronize()
    return {
        "allocated_bytes": int(torch.cuda.memory_allocated()),
        "reserved_bytes": int(torch.cuda.memory_reserved()),
    }


def collect_memory(limit_gib: float | None = None) -> MemoryStats:
    if not torch.cuda.is_available():
        return MemoryStats(limit_bytes=int(limit_gib * GIB) if limit_gib else None)
    synchronize()
    free, total = torch.cuda.mem_get_info()
    peak_allocated = int(torch.cuda.max_memory_allocated())
    peak_reserved = int(torch.cuda.max_memory_reserved())
    limit = int(limit_gib * GIB) if limit_gib is not None else None
    return MemoryStats(
        peak_allocated_bytes=peak_allocated,
        peak_reserved_bytes=peak_reserved,
        allocated_after_bytes=int(torch.cuda.memory_allocated()),
        reserved_after_bytes=int(torch.cuda.memory_reserved()),
        free_bytes_after_request=int(free),
        total_device_bytes=int(total),
        limit_bytes=limit,
        gate_pass=(peak_reserved <= limit) if limit is not None else None,
    )


def enforce_memory_gate(stats: MemoryStats, *, label: str) -> None:
    if stats.limit_bytes is not None and not bool(stats.gate_pass):
        raise MemoryBudgetError(
            f"{label} peak reserved memory exceeded gate: "
            f"{stats.peak_reserved_bytes / GIB:.3f} GiB > {stats.limit_bytes / GIB:.3f} GiB"
        )


def assert_cuda_only(model: Any, *, label: str) -> dict[str, Any]:
    tensors = [
        *(('parameter', value) for value in model.parameters()),
        *(('buffer', value) for value in model.buffers()),
    ]
    devices = {str(tensor.device) for _, tensor in tensors}
    if not tensors:
        raise ModelContractError(f"{label} has no parameters")
    if any(not device.startswith("cuda") for device in devices):
        raise ModelContractError(
            f"{label} parameters/buffers are not fully CUDA resident: {sorted(devices)}"
        )
    device_map = getattr(model, "hf_device_map", None)
    if isinstance(device_map, dict):
        forbidden = {str(value) for value in device_map.values() if str(value) in {"cpu", "disk"}}
        if forbidden:
            raise ModelContractError(f"{label} uses CPU/disk offload: {sorted(forbidden)}")
    return {
        "label": label,
        "all_tensors_cuda": True,
        "devices": sorted(devices),
        "parameter_tensor_count": sum(kind == "parameter" for kind, _ in tensors),
        "buffer_tensor_count": sum(kind == "buffer" for kind, _ in tensors),
        "parameter_bytes": sum(
            tensor.numel() * tensor.element_size()
            for kind, tensor in tensors
            if kind == "parameter"
        ),
        "buffer_bytes": sum(
            tensor.numel() * tensor.element_size()
            for kind, tensor in tensors
            if kind == "buffer"
        ),
        "hf_device_map": device_map,
        "cpu_or_disk_offload": False,
        "execution_mode": "resident",
    }


def attention_runtime_state(model: Any) -> dict[str, Any]:
    config = getattr(model, "config", None)
    state = {
        "attn_implementation": getattr(config, "_attn_implementation", None),
        "flash_sdp_enabled": bool(torch.backends.cuda.flash_sdp_enabled()) if torch.cuda.is_available() else False,
        "mem_efficient_sdp_enabled": bool(torch.backends.cuda.mem_efficient_sdp_enabled()) if torch.cuda.is_available() else False,
        "math_sdp_enabled": bool(torch.backends.cuda.math_sdp_enabled()) if torch.cuda.is_available() else False,
    }
    return state


@dataclass
class EventSpan:
    """Non-invasive CUDA event span; elapsed time is read after final synchronization."""

    enabled: bool

    def __post_init__(self) -> None:
        self._cpu_start: float | None = None
        self._cpu_end: float | None = None
        self._start = torch.cuda.Event(enable_timing=True) if self.enabled and torch.cuda.is_available() else None
        self._end = torch.cuda.Event(enable_timing=True) if self.enabled and torch.cuda.is_available() else None

    def start(self) -> None:
        import time

        if not self.enabled:
            return
        if self._start is not None:
            self._start.record()
        else:
            self._cpu_start = time.perf_counter()

    def stop(self) -> None:
        import time

        if not self.enabled:
            return
        if self._end is not None:
            self._end.record()
        else:
            self._cpu_end = time.perf_counter()

    def elapsed_ms(self) -> float | None:
        if self._start is not None and self._end is not None:
            synchronize()
            return float(self._start.elapsed_time(self._end))
        if self._cpu_start is not None and self._cpu_end is not None:
            return (self._cpu_end - self._cpu_start) * 1000.0
        return None
