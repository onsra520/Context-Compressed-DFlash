from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SegmentedPrompt:
    question: str
    context: str


def segment_gsm8k(full_prompt: str) -> SegmentedPrompt:
    parts = full_prompt.rsplit("\n\n", 1)
    if len(parts) == 2:
        context, question = parts
        return SegmentedPrompt(question=question.strip(), context=context.strip())
    return SegmentedPrompt(question=full_prompt.strip(), context="")


def merge(compressed_context: str, question: str) -> str:
    if not compressed_context:
        return question
    if not question:
        return compressed_context
    return f"{compressed_context}\n\n{question}"