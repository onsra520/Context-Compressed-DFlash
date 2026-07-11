"""QMSum lexical proxy plus output-health evidence."""

from __future__ import annotations

import re
from typing import Any

EVALUATOR_VERSION = "rec-t06a3.qmsum-proxy.v2"
WORD_RE = re.compile(r"[A-Za-z0-9]+")


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in WORD_RE.findall(text)}


def evaluate(
    generated_text: str,
    reference_answer: str,
    *,
    cap_hit: bool = False,
    repetition_detected: bool = False,
    instruction_echo_detected: bool = False,
    answer_prefix_count: int = 0,
    repeated_ngram_ratio: float = 0.0,
) -> dict[str, Any]:
    pred = _tokens(generated_text)
    ref = _tokens(reference_answer)
    overlap = pred & ref
    recall = len(overlap) / len(ref) if ref else 0.0
    precision = len(overlap) / len(pred) if pred else 0.0
    invalid = not bool(pred) or repetition_detected or instruction_echo_detected
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "reference_recall": recall,
        "reference_precision": precision,
        "output_length_chars": len(generated_text),
        "output_word_count": len(WORD_RE.findall(generated_text)),
        "invalid": invalid,
        "empty": not bool(pred),
        "cap_hit": cap_hit,
        "repetition_detected": repetition_detected,
        "instruction_echo": instruction_echo_detected,
        "answer_prefix_count": answer_prefix_count,
        "repeated_ngram_ratio": repeated_ngram_ratio,
        "semantic_correctness": "NOT_CLAIMED",
        "tokenizer_source": "target",
    }
