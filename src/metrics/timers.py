"""Small timing helpers used by generation and benchmark code."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


@dataclass
class TimerValue:
    """Mutable elapsed-time value populated by ``timer_ms``."""

    elapsed_ms: float = 0.0


@contextmanager
def timer_ms() -> Iterator[TimerValue]:
    """Measure an operation in milliseconds."""

    value = TimerValue()
    start = time.perf_counter()
    try:
        yield value
    finally:
        value.elapsed_ms = (time.perf_counter() - start) * 1000.0
