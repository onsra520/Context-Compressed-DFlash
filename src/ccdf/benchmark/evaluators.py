"""Deterministic dataset evaluators used by the tracked smoke workflow."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from fractions import Fraction
import re
from typing import Any, Mapping


_INTEGER = r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)"
_DECIMAL = rf"[-+]?(?:{_INTEGER})(?:\.\d+)?"
_NUMERIC = re.compile(rf"^(?P<numerator>{_DECIMAL})(?:/(?P<denominator>{_DECIMAL}))?$")


def _numeric_value(text: str) -> Fraction | None:
    candidate = text.strip().replace("$", "")
    match = _NUMERIC.fullmatch(candidate)
    if match is None:
        return None
    try:
        numerator = Fraction(Decimal(match.group("numerator").replace(",", "")))
        denominator_text = match.group("denominator")
        if denominator_text is None:
            return numerator
        denominator = Fraction(Decimal(denominator_text.replace(",", "")))
        if denominator == 0:
            return None
        return numerator / denominator
    except (InvalidOperation, ValueError, ZeroDivisionError):
        return None


def evaluate_gsm8k(
    generated_text: str,
    reference_answer: str,
    settings: Mapping[str, Any],
    *,
    cap_hit: bool = False,
) -> dict[str, Any]:
    """Evaluate the final ``Final answer:`` line by normalized numeric value."""
    prefix = str(settings["final_answer_prefix"])
    line_pattern = re.compile(rf"^\s*{re.escape(prefix)}\s*(.*?)\s*$", re.MULTILINE)
    matches = list(line_pattern.finditer(generated_text))
    prediction_text = matches[-1].group(1) if matches else None
    prediction_value = _numeric_value(prediction_text) if prediction_text is not None else None
    reference_value = _numeric_value(reference_answer)
    if cap_hit:
        label = "cap_hit"
    elif prediction_text is None:
        label = "missing_answer"
    elif prediction_value is None or reference_value is None:
        label = "invalid_format"
    elif prediction_value == reference_value:
        label = "correct"
    else:
        label = "wrong_numeric"
    return {
        "evaluator_version": str(settings["version"]),
        "label": label,
        "valid": label in {"correct", "wrong_numeric"},
        "correct": label == "correct",
        "prediction_text": prediction_text,
        "prediction_normalized": str(prediction_value) if prediction_value is not None else None,
        "reference_text": reference_answer,
        "reference_normalized": str(reference_value) if reference_value is not None else None,
        "exact_text_match_diagnostic": (
            prediction_text.strip() == reference_answer.strip()
            if prediction_text is not None
            else False
        ),
        "final_answer_line_count": len(matches),
        "cap_hit": cap_hit,
        "quality_metric": "normalized_numeric_equality",
    }


def _overlap_tokens(text: str, word_pattern: str) -> set[str]:
    return {token.lower() for token in re.findall(word_pattern, text)}


def evaluate_qmsum(
    generated_text: str,
    reference_answer: str,
    settings: Mapping[str, Any],
    *,
    cap_hit: bool = False,
    evidence_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Port of the prior set-token overlap evaluator; it is not semantic scoring."""
    word_pattern = str(settings["word_pattern"])
    prediction_tokens = _overlap_tokens(generated_text, word_pattern)
    reference_tokens = _overlap_tokens(reference_answer, word_pattern)
    overlap = prediction_tokens & reference_tokens
    recall = len(overlap) / len(reference_tokens) if reference_tokens else 0.0
    precision = len(overlap) / len(prediction_tokens) if prediction_tokens else 0.0
    return {
        "evaluator_version": str(settings["version"]),
        "valid": bool(prediction_tokens),
        "invalid": not bool(prediction_tokens),
        "reference_recall": recall,
        "reference_precision": precision,
        "overlap_token_count": len(overlap),
        "prediction_unique_token_count": len(prediction_tokens),
        "reference_unique_token_count": len(reference_tokens),
        "output_length_chars": len(generated_text),
        "output_word_count": len(re.findall(word_pattern, generated_text)),
        "empty": not bool(prediction_tokens),
        "cap_hit": cap_hit,
        "semantic_correctness": "NOT_CLAIMED",
        "coverage_proxy_only": True,
        "evidence_diagnostics": dict(evidence_diagnostics or {}),
    }


def validate_evaluator_fixtures(settings: Mapping[str, Any]) -> dict[str, Any]:
    """Lock evaluator behavior to config-owned fixtures before any benchmark work."""
    records: list[dict[str, Any]] = []
    for fixture in settings["gsm8k"]["fixture_cases"]:
        result = evaluate_gsm8k(
            str(fixture["generated"]), str(fixture["reference"]), settings["gsm8k"]
        )
        records.append({
            "evaluator": "gsm8k",
            "expected": fixture["label"],
            "actual": result["label"],
            "pass": result["label"] == fixture["label"],
        })
    for fixture in settings["qmsum"]["fixture_cases"]:
        result = evaluate_qmsum(
            str(fixture["generated"]), str(fixture["reference"]), settings["qmsum"]
        )
        expected_recall = float(fixture["recall"])
        expected_precision = float(fixture["precision"])
        records.append({
            "evaluator": "qmsum",
            "expected_recall": expected_recall,
            "actual_recall": result["reference_recall"],
            "expected_precision": expected_precision,
            "actual_precision": result["reference_precision"],
            "pass": (
                result["reference_recall"] == expected_recall
                and result["reference_precision"] == expected_precision
            ),
        })
    return {"pass": all(record["pass"] for record in records), "records": records}


def qmsum_evidence_diagnostics(
    context: str, reference_answer: str, word_pattern: str
) -> dict[str, Any]:
    context_tokens = _overlap_tokens(context, word_pattern)
    reference_tokens = _overlap_tokens(reference_answer, word_pattern)
    available = reference_tokens & context_tokens
    return {
        "diagnostic_policy": "lexical_reference_token_presence_in_full_context",
        "reference_unique_tokens": len(reference_tokens),
        "reference_tokens_present": len(available),
        "reference_token_availability_rate": (
            len(available) / len(reference_tokens) if reference_tokens else 0.0
        ),
        "reference_evidence_semantically_verified": False,
    }
