"""Independent normalized fact validation for compressed prompts.

This module intentionally does not import or reuse the protector patterns from
``safeguard``.  The two implementations are separate failure domains.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class FactValidation:
    passed: bool
    checks: dict[str, bool]
    missing: dict[str, list[str]]
    added: dict[str, list[str]]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "checks": dict(self.checks),
            "missing": dict(self.missing),
            "added": dict(self.added),
        }


# Decimal punctuation is part of a number only when a digit follows the dot.
_CURRENCY = re.compile(r"(?:[$£€¥]\s*)[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", re.I)
_PERCENTAGE = re.compile(r"(?<![\w.])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*%", re.I)
_NUMERIC_FRACTION = re.compile(r"(?<![\w.])[+-]?\d+(?:\.\d+)?\s*/\s*[+-]?\d+(?:\.\d+)?(?!\w)")
_WRITTEN_FRACTION = re.compile(
    r"\b(?:one\s+half|a\s+half|half|one\s+quarter|a\s+quarter|quarter|"
    r"one\s+third|a\s+third|third|two[-\s]+thirds|three[-\s]+quarters)\b",
    re.I,
)
_NUMBER = re.compile(r"(?<![\w.])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?!\w|\s*[%/])")
_UNIT = re.compile(
    r"\b(?:dollars?|cents?|usd|eur|gbp|euros?|pounds?|pieces?|balls?|boxes?|items?|"
    r"notebooks?|pens?|students?|boys?|girls?|liters?|litres?|kilometers?|kilometres?|"
    r"km|meters?|metres?|m|miles?|hours?|minutes?|seconds?|km/h|mph|square\s+meters?)\b",
    re.I,
)
_RELATION = re.compile(
    r"\b(?:increase(?:d|s)?|decrease(?:d|s)?|add(?:ed|s|ing)?|remove(?:d|s)?|"
    r"remaining|remain(?:s|ed)?|left|each|per|of|used?|uses|stopp(?:ed|ing)|stops?|"
    r"before|after|then|from|to|total|ratio|average|discount(?:ed)?|tax)\b",
    re.I,
)
_NEGATION = re.compile(r"\b(?:no|not|never|without|neither|nor|none|zero|don't|doesn't|didn't)\b", re.I)
_DURATION = re.compile(
    r"\b(?:[+-]?(?:\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(?:hours?|minutes?|seconds?)|duration|elapsed\s+time|stopp(?:ed|ing)\s+for)\b",
    re.I,
)
_OUTPUT = re.compile(
    r"`[^`]*(?:final\s+answer|<[^>]+>)[^`]*`|\b(?:final\s+answer|end\s+with|"
    r"return\s+exactly|output\s+format|final\s+(?:non-empty\s+)?line|must\s+label)\b",
    re.I,
)

_EXTRACTORS = {
    "currencies": _CURRENCY,
    "percentages": _PERCENTAGE,
    "numeric_fractions": _NUMERIC_FRACTION,
    "written_fractions": _WRITTEN_FRACTION,
    "numbers": _NUMBER,
    "units": _UNIT,
    "relations": _RELATION,
    "negations": _NEGATION,
    "durations": _DURATION,
    "output_constraints": _OUTPUT,
}


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower()).replace(" - ", "-")


def extract_fact_inventory(text: str) -> dict[str, Counter[str]]:
    return {
        category: Counter(_normalize(match.group(0)) for match in pattern.finditer(text))
        for category, pattern in _EXTRACTORS.items()
    }


def validate_facts(original: str, candidate: str) -> FactValidation:
    before = extract_fact_inventory(original)
    after = extract_fact_inventory(candidate)
    checks = {category: before[category] == after[category] for category in _EXTRACTORS}
    missing = {
        category: list((before[category] - after[category]).elements())
        for category in _EXTRACTORS
        if before[category] - after[category]
    }
    added = {
        category: list((after[category] - before[category]).elements())
        for category in _EXTRACTORS
        if after[category] - before[category]
    }
    return FactValidation(all(checks.values()), checks, missing, added)
