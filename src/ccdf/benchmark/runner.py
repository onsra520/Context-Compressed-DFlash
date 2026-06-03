from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from .conditions import CONDITIONS


@dataclass
class BenchmarkRunner:
    config: dict[str, Any] | None = None
    conditions: Sequence[dict[str, Any]] = field(default_factory=lambda: CONDITIONS)

    def list_conditions(self) -> list[str]:
        return [condition["name"] for condition in self.conditions]

    def run(self, *args, **kwargs):
        raise NotImplementedError(
            "BenchmarkRunner is structurally ready; execution will be wired after the upstream split."
        )