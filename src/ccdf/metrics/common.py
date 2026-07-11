"""Common metric helpers."""

from __future__ import annotations


def tokens_per_second(tokens: int, milliseconds: float) -> float:
    if milliseconds <= 0:
        return 0.0
    return tokens / (milliseconds / 1000.0)
