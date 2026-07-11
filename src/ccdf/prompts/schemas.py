"""Prompt part schemas."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptParts:
    context: str
    question: str
    instruction: str
    system: str | None = None
