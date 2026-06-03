from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Iterator


def cuda_time() -> float:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.synchronize()
    except Exception:
        pass
    return perf_counter()


@contextmanager
def measure_cuda_time() -> Iterator[float]:
    start = cuda_time()
    yield start