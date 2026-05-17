"""Gemma tokenizer boundary helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TokenizerLike(Protocol):
    """Minimal tokenizer protocol used by the Gemma boundary."""

    @property
    def eos_token_id(self) -> int | None:
        """Return the EOS token ID when the tokenizer exposes one."""

        raise NotImplementedError

    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        """Encode text into token IDs."""

        raise NotImplementedError

    def decode(self, token_ids: list[int], skip_special_tokens: bool = True) -> str:
        """Decode token IDs into text."""

        raise NotImplementedError


@dataclass(frozen=True)
class RetokenizedDraft:
    """D-Flash draft text encoded in Gemma token space."""

    token_ids: list[int]
    empty: bool


def reject_empty_draft(draft_text: str) -> str:
    """Normalize draft text and reject empty content."""

    normalized = draft_text.strip()
    if not normalized:
        raise ValueError("empty draft_text")
    return normalized


class GemmaTokenizer:
    """Adapt a Gemma tokenizer to the Low Tier tokenizer boundary."""

    def __init__(self, tokenizer: TokenizerLike):
        self._tokenizer = tokenizer

    @property
    def eos_token_id(self) -> int | None:
        """Return the underlying tokenizer EOS token ID."""

        return self._tokenizer.eos_token_id

    def encode_prompt(self, prompt: str) -> list[int]:
        """Encode a prompt without adding special tokens."""

        return self._tokenizer.encode(prompt, add_special_tokens=False)

    def retokenize_draft(self, draft_text: str, *, max_tokens: int) -> RetokenizedDraft:
        """Encode and cap D-Flash draft text in Gemma token space."""

        normalized = reject_empty_draft(draft_text)
        token_ids = self._tokenizer.encode(normalized, add_special_tokens=False)
        capped = token_ids[:max_tokens]
        return RetokenizedDraft(token_ids=capped, empty=len(capped) == 0)

    def decode(self, token_ids: list[int]) -> str:
        """Decode token IDs while skipping special tokens."""

        return self._tokenizer.decode(token_ids, skip_special_tokens=True)
