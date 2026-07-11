"""Schemas for the canonical reconstruction configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResolvedConfig:
    data: dict[str, Any]
    sha256: str

    @property
    def canonical(self) -> bool:
        return bool(self.data["canonical"])
