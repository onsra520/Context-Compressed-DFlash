"""JSON-friendly trace helpers for smoke runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PairSmokeTrace:
    """One low-tier pair smoke trace."""

    bridge_status: str
    rejection_reason: str | None
    fallback_count: int
    latency_seconds: float
    qwen_decode_tokens_per_second: float | None
    gemma_decode_tokens_per_second: float | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly dictionary."""

        return asdict(self)
