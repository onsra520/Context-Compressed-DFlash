"""Deterministic context chunking."""

from __future__ import annotations


def chunk_context(context: str, *, max_words: int = 180) -> list[str]:
    words = context.split()
    if not words:
        return []
    return [" ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)]
