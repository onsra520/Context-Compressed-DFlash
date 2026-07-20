"""Dependency-free GSM8K and QMSum evaluators for Stage 3 evidence."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

_FINAL_NUMERIC = re.compile(
    r"Final answer:\s*([-+]?\$?[\d,]+(?:\.\d+)?)\.?\s*$",
    re.IGNORECASE,
)
_WORD = re.compile(r"[A-Za-z0-9]+")


def normalize_numeric(value: str) -> str | None:
    candidate = value.replace("$", "").replace(",", "").strip()
    try:
        number = Decimal(candidate)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    normalized = format(number.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return "0" if normalized in {"-0", "+0", ""} else normalized


def _parse_final_numeric(text: str) -> tuple[str | None, str]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return None, "empty_output"
    match = _FINAL_NUMERIC.search(text)
    if not match:
        return None, "missing_final_answer_line"
    parsed = normalize_numeric(match.group(1))
    return (parsed, "parsed") if parsed is not None else (None, "invalid_numeric")


def _tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in _WORD.finditer(text)]


def _lcs_length(left: list[str], right: list[str]) -> int:
    if len(right) > len(left):
        left, right = right, left
    previous = [0] * (len(right) + 1)
    for left_token in left:
        current = [0]
        for index, right_token in enumerate(right, start=1):
            current.append(
                previous[index - 1] + 1
                if left_token == right_token
                else max(previous[index], current[-1])
            )
        previous = current
    return previous[-1]


def _rouge_l(text: str, reference: str) -> dict[str, Any]:
    prediction_tokens = _tokens(text)
    reference_tokens = _tokens(reference)
    lcs = _lcs_length(prediction_tokens, reference_tokens)
    precision = lcs / len(prediction_tokens) if prediction_tokens else 0.0
    recall = lcs / len(reference_tokens) if reference_tokens else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "metric": "rouge_l_f1",
        "rouge_l_f1": f1,
        "rouge_l_precision": precision,
        "rouge_l_recall": recall,
        "lcs_tokens": lcs,
        "prediction_tokens": len(prediction_tokens),
        "reference_tokens": len(reference_tokens),
        "empty_output": not bool(prediction_tokens),
        "semantic_correctness": "NOT_CLAIMED",
    }


def evaluate_dataset_output(sample: dict[str, Any], text: str) -> dict[str, Any]:
    dataset = str(sample["dataset"])
    if dataset == "gsm8k":
        parsed, parser_status = _parse_final_numeric(text)
        reference = normalize_numeric(str(sample["reference"]))
        if reference is None:
            raise ValueError(f"invalid GSM8K reference for {sample['sample_id']}")
        exact_match = parsed is not None and parsed == reference
        return {
            "evaluator": "ccdf.gsm8k.numeric-exact.v1",
            "parsed_answer": parsed,
            "parser_status": parser_status,
            "quality_score": float(exact_match),
            "details": {
                "exact_numeric_match": exact_match,
                "reference_numeric": reference,
                "substring_matching": False,
            },
        }
    if dataset == "qmsum":
        details = _rouge_l(text, str(sample["reference"]))
        return {
            "evaluator": "ccdf.qmsum.rouge-l-proxy.v1",
            "parsed_answer": None,
            "parser_status": "not_applicable",
            "quality_score": float(details["rouge_l_f1"]),
            "details": details,
        }
    raise ValueError(f"unsupported dataset evaluator: {dataset}")
