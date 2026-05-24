"""Shared prompt sets for controlled trace runs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TracePrompt:
    """One controlled trace prompt."""

    prompt_id: str
    text: str


@dataclass(frozen=True)
class TracePromptSet:
    """Named prompt set for low-tier and baseline traces."""

    prompt_set_id: str
    prompts: tuple[TracePrompt, ...]


DEFAULT_TRACE_PROMPT_SET = TracePromptSet(
    prompt_set_id="phase-1-controlled-trace-v1",
    prompts=(
        TracePrompt("prompt-001", "Explain speculative decoding in one short sentence."),
        TracePrompt("prompt-002", "Write a five word greeting."),
        TracePrompt("prompt-003", "List two benefits of GPU inference."),
    ),
)


def default_trace_prompts() -> tuple[TracePrompt, ...]:
    """Return the default controlled trace prompts."""

    return DEFAULT_TRACE_PROMPT_SET.prompts


def default_trace_prompt_texts() -> tuple[str, ...]:
    """Return only prompt text for compatibility with older callers."""

    return tuple(prompt.text for prompt in DEFAULT_TRACE_PROMPT_SET.prompts)
