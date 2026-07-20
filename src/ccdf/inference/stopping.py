"""Low-overhead token and block-boundary stopping state."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

FINAL_ANSWER_RE = re.compile(r"(?im)^\s*Final answer:\s*[-+]?\$?[\d,]+(?:\.\d+)?(?:\s*[A-Za-z%]+)?\s*[.!]?\s*$")
WORD_RE = re.compile(r"[A-Za-z0-9]+")


@dataclass(frozen=True)
class StopState:
    should_stop: bool
    reason: str | None
    text: str
    eos_hit: bool
    cap_hit: bool


class BlockStopController:
    def __init__(
        self,
        *,
        tokenizer,
        stop_token_ids: Iterable[int],
        max_new_tokens: int,
        dataset: str = "general",
    ) -> None:
        self.tokenizer = tokenizer
        self.stop_token_ids = {int(token) for token in stop_token_ids}
        self.max_new_tokens = int(max_new_tokens)
        self.dataset = dataset

    def token_reason(self, token_id: int, count: int) -> str | None:
        if int(token_id) in self.stop_token_ids:
            return "eos"
        if count >= self.max_new_tokens:
            return "max_new_tokens"
        return None

    def block_boundary(self, token_ids: list[int]) -> StopState:
        text = self.tokenizer.decode(token_ids, skip_special_tokens=True)
        eos = bool(token_ids and token_ids[-1] in self.stop_token_ids)
        cap = len(token_ids) >= self.max_new_tokens
        reason: str | None = "eos" if eos else "max_new_tokens" if cap else None
        if reason is None and self.dataset == "gsm8k" and FINAL_ANSWER_RE.search(text):
            reason = "output_contract"
        return StopState(reason is not None, reason, text, eos, cap)

    def finalize(self, token_ids: list[int], reason: str | None = None) -> tuple[StopState, dict[str, object]]:
        text = self.tokenizer.decode(token_ids, skip_special_tokens=True)
        words = [value.lower() for value in WORD_RE.findall(text)]
        size = 4
        ngrams = [tuple(words[index : index + size]) for index in range(max(len(words) - size + 1, 0))]
        repeated_ratio = 1.0 - len(set(ngrams)) / len(ngrams) if ngrams else 0.0
        repetition = len(words) >= 48 and repeated_ratio >= 0.45
        eos = bool(token_ids and token_ids[-1] in self.stop_token_ids)
        cap = len(token_ids) >= self.max_new_tokens
        final_reason = reason or ("eos" if eos else "max_new_tokens" if cap else "completed")
        return (
            StopState(final_reason != "completed", final_reason, text, eos, cap),
            {
                "repetition_detected": repetition,
                "repeated_ngram_ratio": repeated_ratio,
                "output_words": len(words),
                "empty": not bool(words),
            },
        )
