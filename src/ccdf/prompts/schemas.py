"""Structured prompt schemas shared by CLI, benchmark and compression."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PromptParts:
    context: str
    question: str
    instruction: str
    system: str | None = None


@dataclass(frozen=True)
class EncodedPrompt:
    dataset: str
    parts: PromptParts
    messages: tuple[dict[str, str], ...]
    rendered_text: str
    input_ids: Any
    input_ids_list: tuple[int, ...]
    structured_hash: str
    rendered_hash: str
    input_ids_hash: str
    chat_template_used: bool
    enable_thinking_applied: bool
