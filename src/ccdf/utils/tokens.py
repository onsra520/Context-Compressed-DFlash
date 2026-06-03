from __future__ import annotations

from typing import Any


def count_tokens(text: str, tokenizer: Any | None = None) -> int:
    if tokenizer is not None and hasattr(tokenizer, "encode"):
        encoded = tokenizer.encode(text)
        return len(encoded) if not isinstance(encoded, int) else int(encoded)
    return len(text.split())