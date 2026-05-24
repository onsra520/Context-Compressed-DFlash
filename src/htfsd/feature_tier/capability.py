"""Capability checks for the future high-tier path."""

from __future__ import annotations

from typing import Any


def feature_tier_readiness(backend: Any) -> dict[str, Any]:
    """Report whether a backend can support feature-tier work."""

    supports_hidden_states = bool(getattr(backend, "supports_hidden_states", False))
    if not supports_hidden_states:
        return {
            "supports_hidden_states": False,
            "readiness": "blocked",
            "reason": "hidden_states_unavailable",
        }
    return {
        "supports_hidden_states": True,
        "readiness": "ready",
        "reason": None,
    }
