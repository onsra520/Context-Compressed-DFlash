"""Public runtime integration surface.

The engine is loaded lazily so low-level runtime schemas can be imported by
infrastructure code without executing the full runtime dependency graph.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .engine import RuntimeEngine

__all__ = ["RuntimeEngine"]


def __getattr__(name: str) -> Any:
    if name == "RuntimeEngine":
        from .engine import RuntimeEngine

        return RuntimeEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
