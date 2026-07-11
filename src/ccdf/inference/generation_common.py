"""Small generation helpers shared by production paths."""

from __future__ import annotations


def synchronize_if_cuda(device) -> None:
    if getattr(device, "type", None) == "cuda":
        import torch

        torch.cuda.synchronize(device)
