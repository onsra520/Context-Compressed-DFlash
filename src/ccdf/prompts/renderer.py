"""Canonical prompt renderer."""

from __future__ import annotations

from ccdf.prompts.schemas import PromptParts


def render_prompt(parts: PromptParts) -> str:
    prefix = f"{parts.system}\n\n" if parts.system else ""
    return (
        f"{prefix}"
        "Meeting transcript:\n"
        f"{parts.context}\n\n"
        "Question:\n"
        f"{parts.question}\n\n"
        f"{parts.instruction}"
    )


def render_gsm8k_prompt(question: str) -> PromptParts:
    return PromptParts(
        context="Short-context numeric QA.",
        question=question,
        instruction="End with exactly one line: Final answer: <number>",
    )
