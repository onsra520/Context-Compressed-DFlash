"""Dataset-aware prompt construction.

Human-readable rendering and model chat-template encoding are deliberately
separate.  Compression may replace only ``PromptParts.context``.
"""

from __future__ import annotations

from ccdf.prompts.schemas import PromptParts


def render_prompt(parts: PromptParts, dataset: str = "qmsum") -> str:
    prefix = f"{parts.system}\n\n" if parts.system else ""
    if dataset == "gsm8k":
        return f"{prefix}Problem:\n{parts.question}\n\n{parts.instruction}".strip()
    if dataset == "qmsum":
        return (
            f"{prefix}Meeting transcript:\n{parts.context}\n\n"
            f"Question:\n{parts.question}\n\n{parts.instruction}"
        ).strip()
    if parts.context:
        return (
            f"{prefix}Context:\n{parts.context}\n\n"
            f"Question:\n{parts.question}\n\n{parts.instruction}"
        ).strip()
    return f"{prefix}{parts.question}\n\n{parts.instruction}".strip()


def build_messages(parts: PromptParts, dataset: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if parts.system:
        messages.append({"role": "system", "content": parts.system})
    messages.append({"role": "user", "content": render_prompt(PromptParts(
        context=parts.context,
        question=parts.question,
        instruction=parts.instruction,
        system=None,
    ), dataset)})
    return messages


def render_gsm8k_prompt(question: str, *, instruction: str | None = None, system: str | None = None) -> PromptParts:
    return PromptParts(
        context="",
        question=question,
        instruction=instruction
        or 'Solve the problem. End with exactly one line in the form "Final answer: <number>", then stop.',
        system=system,
    )
