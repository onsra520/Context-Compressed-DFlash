"""Qwen text drafter for low-tier smoke paths."""

from __future__ import annotations


class QwenTextDrafter:
    """Thin drafter around a text-generation backend."""

    def __init__(self, backend) -> None:
        self._backend = backend

    def draft(self, prompt: str, *, max_tokens: int, temperature: float = 0.0) -> str:
        """Generate a raw Qwen draft string."""

        return self._backend.generate_text(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        ).text
