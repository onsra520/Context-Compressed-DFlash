from __future__ import annotations

import time
import torch
from dataclasses import dataclass


@dataclass
class TimingContext:
    start_time: float = 0.0
    end_time: float = 0.0

    def __enter__(self):
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        self.end_time = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000.0


def measure_vram() -> float | None:
    if not torch.cuda.is_available():
        return None
    torch.cuda.synchronize()
    return torch.cuda.max_memory_allocated() / (1024 ** 3)
