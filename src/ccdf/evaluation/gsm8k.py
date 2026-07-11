"""GSM8K numeric evaluator."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

NUMERIC_RE = re.compile(r"[-+]?\$?[\d,]+(?:\.\d+)?")
EVALUATOR_VERSION = "rec-t02b.gsm8k-evaluator.v1"


def _last_number(text: str) -> str | None:
    matches = NUMERIC_RE.findall(text)
    if not matches:
        return None
    return matches[-1].replace("$", "").replace(",", "")


def evaluate(generated_text: str, reference_answer: str, *, cap_hit: bool = False) -> dict[str, Any]:
    prediction = _last_number(generated_text)
    if cap_hit and prediction is None:
        label = "cap_limited_incomplete"
    elif prediction is None:
        label = "invalid"
    else:
        try:
            label = "strict_correct" if Decimal(prediction) == Decimal(reference_answer) else "wrong_numeric"
        except InvalidOperation:
            label = "invalid"
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "label": label,
        "prediction": prediction,
        "reference": reference_answer,
        "tokenizer_source": "target",
    }
