from __future__ import annotations


def get_vram_allocated(device: str | None = None) -> float:
    try:
        import torch

        if not torch.cuda.is_available():
            return 0.0
        if device is not None:
            return float(torch.cuda.memory_allocated(device)) / 1e9
        return float(torch.cuda.memory_allocated()) / 1e9
    except Exception:
        return 0.0