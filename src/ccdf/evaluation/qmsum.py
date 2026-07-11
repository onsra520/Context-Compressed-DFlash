"""QMSum lexical proxy evaluator."""

from __future__ import annotations

import re
from typing import Any

EVALUATOR_VERSION = "rec-t02b.qmsum-proxy.v1"
WORD_RE = re.compile(r"[A-Za-z0-9]+")


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in WORD_RE.findall(text)}


def evaluate(generated_text: str, reference_answer: str, *, cap_hit: bool = False) -> dict[str, Any]:
    pred = _tokens(generated_text)
    ref = _tokens(reference_answer)
    overlap = pred & ref
    recall = len(overlap) / len(ref) if ref else 0.0
    precision = len(overlap) / len(pred) if pred else 0.0
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "reference_recall": recall,
        "reference_precision": precision,
        "output_length_chars": len(generated_text),
        "invalid": not bool(pred),
        "cap_hit": cap_hit,
        "semantic_correctness": "NOT_CLAIMED",
        "tokenizer_source": "target",
    }
