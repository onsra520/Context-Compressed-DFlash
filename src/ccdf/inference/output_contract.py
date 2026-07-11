"""Shared output health, answer extraction and stopping contracts."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable

FINAL_ANSWER_RE = re.compile(
    # A final answer can start a line or follow a completed sentence.  The
    # latter accepts the concise v3 GSM8K outputs while refusing incidental
    # prose such as "we still need to determine the final answer: ...".
    r"(?im)(?:^\s*|(?<=[.!?])[ \t]+)Final answer:\s*"
    r"(?P<number>[-+]?\$?[\d,]+(?:\.\d+)?)"
    r"(?P<suffix>\s*(?:[A-Za-z%]+(?:\s+[A-Za-z%]+)*)?\s*[.!]?)\s*(?=\n|$)"
)
WORD_RE = re.compile(r"[A-Za-z0-9]+")
ANSWER_PREFIX_RE = re.compile(r"(?im)^\s*Answer\s*:")


@dataclass(frozen=True)
class OutputHealth:
    repetition_detected: bool
    repeated_ngram_ratio: float
    instruction_echo_detected: bool
    answer_prefix_count: int
    final_answer_count: int
    output_words: int
    empty: bool


@dataclass(frozen=True)
class StopDecision:
    should_stop: bool
    stop_reason: str | None
    eos_hit: bool
    output_contract_hit: bool
    cap_hit: bool
    validated_answer: str | None
    raw_generated_text: str
    health: OutputHealth

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["health"] = asdict(self.health)
        return data


def normalize_number(value: str) -> str:
    return value.replace("$", "").replace(",", "").strip()


def first_final_answer(text: str) -> str | None:
    match = FINAL_ANSWER_RE.search(text)
    return normalize_number(match.group("number")) if match else None


def _repeated_ngram_ratio(words: list[str], size: int) -> float:
    if size < 1 or len(words) < size * 2:
        return 0.0
    ngrams = [tuple(words[index : index + size]) for index in range(len(words) - size + 1)]
    return 1.0 - (len(set(ngrams)) / len(ngrams))


def analyze_output_health(
    text: str,
    *,
    policy_text: str,
    repetition_min_tokens: int,
    repeated_ngram_size: int,
    repeated_ngram_ratio: float,
    instruction_echo_limit: int,
) -> OutputHealth:
    words = [word.lower() for word in WORD_RE.findall(text)]
    ratio = _repeated_ngram_ratio(words, repeated_ngram_size)
    policy_echoes = text.lower().count(policy_text.lower()) if policy_text else 0
    known_echoes = sum(
        text.lower().count(phrase)
        for phrase in (
            "do not use markdown",
            "answer using only the meeting transcript",
            "end with exactly one line",
        )
    )
    instruction_echo = policy_echoes > instruction_echo_limit or known_echoes > instruction_echo_limit
    return OutputHealth(
        repetition_detected=len(words) >= repetition_min_tokens and ratio >= repeated_ngram_ratio,
        repeated_ngram_ratio=ratio,
        instruction_echo_detected=instruction_echo,
        answer_prefix_count=len(ANSWER_PREFIX_RE.findall(text)),
        final_answer_count=len(FINAL_ANSWER_RE.findall(text)),
        output_words=len(words),
        empty=not bool(words),
    )


class OutputContractState:
    """Observe committed output tokens and decide whether generation must stop.

    The state is condition-independent: Baseline and DFlash use the same
    instance semantics. DFlash calls it after each committed token so a stop
    inside a verified block is clipped correctly.
    """

    def __init__(
        self,
        *,
        tokenizer,
        dataset: str,
        stop_token_ids: Iterable[int],
        max_new_tokens: int,
        policy_text: str,
        settings: dict[str, object],
    ) -> None:
        self.tokenizer = tokenizer
        self.dataset = dataset
        self.stop_token_ids = {int(token) for token in stop_token_ids}
        self.max_new_tokens = int(max_new_tokens)
        self.policy_text = policy_text
        self.settings = settings
        self._candidate: str | None = None
        self._candidate_observations = 0

    def _decode(self, token_ids: list[int]) -> str:
        return self.tokenizer.decode(token_ids, skip_special_tokens=True)

    def observe(self, token_ids: list[int]) -> StopDecision:
        text = self._decode(token_ids)
        health = analyze_output_health(
            text,
            policy_text=self.policy_text,
            repetition_min_tokens=int(self.settings.get("repetition_min_tokens", 48)),
            repeated_ngram_size=int(self.settings.get("repeated_ngram_size", 4)),
            repeated_ngram_ratio=float(self.settings.get("repeated_ngram_ratio", 0.45)),
            instruction_echo_limit=int(self.settings.get("instruction_echo_limit", 1)),
        )
        eos_hit = bool(token_ids and token_ids[-1] in self.stop_token_ids)
        answer = first_final_answer(text) if self.dataset == "gsm8k" else None
        output_contract_hit = False

        if answer is not None:
            if answer == self._candidate:
                self._candidate_observations += 1
            else:
                self._candidate = answer
                self._candidate_observations = 1
            # Avoid stopping on a partial multi-token number. A line terminator,
            # punctuation, EOS, or one stable follow-up token completes it.
            match = FINAL_ANSWER_RE.search(text)
            suffix = match.group("suffix") if match else ""
            terminated = eos_hit or text.endswith("\n") or bool(suffix.strip())
            output_contract_hit = terminated or self._candidate_observations >= 2
        else:
            self._candidate = None
            self._candidate_observations = 0

        reason: str | None = None
        if eos_hit:
            reason = "eos"
        elif self.dataset == "gsm8k" and output_contract_hit:
            reason = "output_contract"
        elif health.repetition_detected:
            reason = "repetition"
        elif health.instruction_echo_detected:
            reason = "instruction_echo"
        elif len(token_ids) >= self.max_new_tokens:
            reason = "max_new_tokens"

        return StopDecision(
            should_stop=reason is not None,
            stop_reason=reason,
            eos_hit=eos_hit,
            output_contract_hit=output_contract_hit,
            cap_hit=reason == "max_new_tokens",
            validated_answer=answer,
            raw_generated_text=text,
            health=health,
        )
