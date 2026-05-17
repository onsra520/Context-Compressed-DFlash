from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TokenizerLike(Protocol):
    eos_token_id: int | None

    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        ...

    def decode(self, token_ids: list[int], skip_special_tokens: bool = True) -> str:
        ...


@dataclass(frozen=True)
class RetokenizedDraft:
    token_ids: list[int]
    empty: bool


def reject_empty_draft(draft_text: str) -> str:
    normalized = draft_text.strip()
    if not normalized:
        raise ValueError("empty draft_text")
    return normalized


class GemmaTokenizer:
    def __init__(self, tokenizer: TokenizerLike):
        self._tokenizer = tokenizer

    @property
    def eos_token_id(self) -> int | None:
        return self._tokenizer.eos_token_id

    def encode_prompt(self, prompt: str) -> list[int]:
        return self._tokenizer.encode(prompt, add_special_tokens=False)

    def retokenize_draft(self, draft_text: str, *, max_tokens: int) -> RetokenizedDraft:
        normalized = reject_empty_draft(draft_text)
        token_ids = self._tokenizer.encode(normalized, add_special_tokens=False)
        capped = token_ids[:max_tokens]
        return RetokenizedDraft(token_ids=capped, empty=len(capped) == 0)

    def decode(self, token_ids: list[int]) -> str:
        return self._tokenizer.decode(token_ids, skip_special_tokens=True)
