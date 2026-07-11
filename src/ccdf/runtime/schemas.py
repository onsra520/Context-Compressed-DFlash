"""Structured requests and results for the unified real runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ccdf.prompts.schemas import PromptParts


@dataclass(frozen=True)
class RuntimeRequest:
    resolved: Any
    prompt: str | None = None
    prompt_parts: PromptParts | None = None
    reference_answer: str | None = None
    measurement_mode: str = "benchmark"

    def __post_init__(self) -> None:
        if (self.prompt is None) == (self.prompt_parts is None):
            raise ValueError("provide exactly one of prompt or prompt_parts")
