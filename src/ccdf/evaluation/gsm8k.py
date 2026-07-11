"""GSM8K evaluator consuming the validated output contract."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from ccdf.inference.output_contract import first_final_answer

NUMERIC_RE = re.compile(r"[-+]?\$?[\d,]+(?:\.\d+)?")
EVALUATOR_VERSION = "rec-t06a3.gsm8k-evaluator.v2"


def _reference_number(text: str) -> str | None:
    matches = NUMERIC_RE.findall(text)
    return matches[-1].replace("$", "").replace(",", "") if matches else None


def evaluate(
    generated_text: str,
    reference_answer: str,
    *,
    validated_answer: str | None = None,
    cap_hit: bool = False,
    repetition_detected: bool = False,
) -> dict[str, Any]:
    prediction = validated_answer or first_final_answer(generated_text)
    reference = _reference_number(reference_answer) or reference_answer
    if repetition_detected:
        label = "repetition_invalid"
    elif prediction is None and cap_hit:
        label = "cap_limited"
    elif prediction is None:
        label = "no_final_answer"
    else:
        try:
            label = "strict_correct" if Decimal(prediction) == Decimal(reference) else "wrong_numeric"
        except InvalidOperation:
            label = "invalid"
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "label": label,
        "prediction": prediction,
        "reference": reference,
        "cap_limited": cap_hit,
        "repetition_detected": repetition_detected,
        "tokenizer_source": "target",
    }
