"""Strict final-answer quality checks for the locked arithmetic fixtures."""

from __future__ import annotations

from dataclasses import dataclass
import re


EXPECTED = (
    "12",
    "any number multiplied by zero equals zero",
    "20 balls",
    "$27",
    "total distance 300 km; elapsed time 5.5 hours; average speed about 54.55 km/h",
    "new area 105 square meters; decrease of 3 square meters",
    "216 liters",
    "attendance 52 students; ratio 7:6",
    "$73.44",
    "total distance 48 km; total time 3.5 hours; average speed about 13.71 km/h",
)


@dataclass(frozen=True)
class QualityResult:
    prompt_index: int
    expected_answer: str
    extracted_answer: str
    answer_correctness_pass: bool
    completeness_pass: bool
    final_answer_line_format_pass: bool
    fixture_format_compliance_pass: bool
    quality_pass: bool
    hit_token_cap: bool
    stop_reason: str
    checks: dict[str, bool]

    def to_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


STRICT_FINAL_ANSWER_RE = re.compile(r"^Final answer: (?P<answer>\S.*)$")
LOOSE_FINAL_ANSWER_RE = re.compile(r"^final\s+answer:\s*(?P<answer>\S.*)$", re.IGNORECASE)


def _final_answer_span(text: str) -> tuple[str, bool]:
    """Extract only the last non-empty line and audit the exact final-line contract."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return "", False
    last_line = lines[-1]
    loose_match = LOOSE_FINAL_ANSWER_RE.fullmatch(last_line.strip())
    extracted = loose_match.group("answer").strip() if loose_match else ""
    strict_match = STRICT_FINAL_ANSWER_RE.fullmatch(last_line)
    strict_line_count = sum(STRICT_FINAL_ANSWER_RE.fullmatch(line) is not None for line in lines)
    format_pass = strict_match is not None and strict_line_count == 1 and last_line == last_line.strip()
    return extracted, format_pass


def _number(text: str, value: str) -> bool:
    """Match a complete integer/decimal value, never a numeric substring."""
    return bool(re.search(rf"(?<![\d.]){re.escape(value)}(?!\d|\.\d)", text))


def _phrase(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, re.IGNORECASE))


def _value_with_unit(text: str, value: str, unit_pattern: str) -> bool:
    return bool(
        re.search(
            rf"(?<![\d.]){re.escape(value)}(?![\d.])\s*{unit_pattern}\b",
            text,
            re.IGNORECASE,
        )
    )


def _labelled_value(text: str, label_pattern: str, value: str, unit_pattern: str) -> bool:
    return bool(
        re.search(
            rf"\b(?:{label_pattern})\b\s*(?:is|=|:)?\s*(?:about|approximately|approx\.?|≈)?\s*"
            rf"(?<![\d.]){re.escape(value)}(?![\d.])\s*{unit_pattern}\b",
            text,
            re.IGNORECASE,
        )
    )


def _currency(text: str, value: str) -> bool:
    return bool(re.search(rf"(?<![\w$])\$\s*{re.escape(value)}(?!\d|\.\d)", text))


def _ratio(text: str, left: str, right: str) -> bool:
    return bool(re.search(rf"(?<!\d){re.escape(left)}\s*:\s*{re.escape(right)}(?!\d)", text))


def _answer_checks(prompt_index: int, answer: str) -> dict[str, bool]:
    zero = r"(?:zero|0)"
    checks_by_prompt = (
        {"answer_value_12": _number(answer, "12")},
        {
            "answer_general_zero_rule": (
                _phrase(
                    answer,
                    rf"\b(?:any|every|all)\s+(?:number|value)s?\b.*\bmultipl(?:y|ied|ying)\b.*\bby\s+{zero}\b.*\b(?:equals?|is|gives?|results?\s+in)\s+{zero}\b",
                )
                or _phrase(
                    answer,
                    rf"\bproduct\s+of\s+(?:any|every|all)\s+(?:number|value)s?\s+and\s+{zero}\s+(?:equals?|is)\s+{zero}\b",
                )
            )
        },
        {"answer_value_20": _number(answer, "20")},
        {"answer_value_27": _number(answer, "27")},
        {
            "answer_distance_300": _number(answer, "300"),
            "answer_time_5_5": _number(answer, "5.5"),
            "answer_speed_54_55": _number(answer, "54.55"),
        },
        {
            "answer_area_105": _number(answer, "105"),
            "answer_change_3": _number(answer, "3")
            and _phrase(answer, r"(?:\bdecrease\b|\breduction\b|(?<![\d.])-\s*3(?![\d.]))"),
        },
        {"answer_value_216": _number(answer, "216")},
        {"answer_attendance_52": _number(answer, "52"), "answer_ratio_7_6": _ratio(answer, "7", "6")},
        {"answer_value_73_44": _number(answer, "73.44")},
        {
            "answer_distance_48": _number(answer, "48"),
            "answer_time_3_5": _number(answer, "3.5"),
            "answer_speed_13_71": _number(answer, "13.71"),
        },
    )
    return checks_by_prompt[prompt_index]


def _fixture_checks(prompt_index: int, answer: str) -> dict[str, bool]:
    km = r"(?:km|kilometers?)"
    hours = r"(?:hours?|hrs?)"
    speed = r"(?:km/h|kilometers?\s+per\s+hour)"
    area = r"(?:m(?:\^?2|²)|square\s+meters?)"
    checks_by_prompt = (
        {"fixture_plain_numeric_answer": bool(re.fullmatch(r"12\.?", answer.strip(), re.IGNORECASE))},
        {"fixture_general_rule_stated": _phrase(answer, r"\b(?:any|every|all)\s+(?:number|value)s?\b")},
        {"fixture_balls_unit": _value_with_unit(answer, "20", r"balls?")},
        {"fixture_currency": _currency(answer, "27")},
        {
            "fixture_total_distance_label_and_unit": _labelled_value(answer, r"total\s+distance", "300", km),
            "fixture_elapsed_time_label_and_unit": _labelled_value(answer, r"elapsed\s+time", "5.5", hours),
            "fixture_average_speed_label_and_unit": _labelled_value(answer, r"average\s+speed", "54.55", speed),
        },
        {
            "fixture_new_area_label_and_unit": _labelled_value(answer, r"new\s+area", "105", area),
            "fixture_change_label_and_unit": bool(
                re.search(
                    rf"\b(?:change|decrease|reduction)\b\s*(?:is|=|:|of)?\s*(?:(?<![\d.])-\s*3|3)(?![\d.])\s*{area}\b",
                    answer,
                    re.IGNORECASE,
                )
            ),
        },
        {"fixture_liters_unit": _value_with_unit(answer, "216", r"liters?")},
        {
            "fixture_attendance_label_students_unit": _labelled_value(answer, r"(?:attendance|students?\s+attending)", "52", r"students?"),
            "fixture_ratio_label": bool(re.search(r"\bratio\b\s*(?:is|=|:)?\s*7\s*:\s*6(?!\d)", answer, re.IGNORECASE)),
        },
        {"fixture_currency": _currency(answer, "73.44")},
        {
            "fixture_total_distance_label_and_unit": _labelled_value(answer, r"total\s+distance", "48", km),
            "fixture_total_time_label_and_unit": _labelled_value(answer, r"total\s+time", "3.5", hours),
            "fixture_average_speed_label_and_unit": _labelled_value(answer, r"average\s+speed", "13.71", speed),
        },
    )
    return checks_by_prompt[prompt_index]


def evaluate_complete_answer(*, prompt_index: int, text: str, stop_reason: str, output_tokens: int, max_new_tokens: int) -> QualityResult:
    if not 0 <= prompt_index < len(EXPECTED):
        raise ValueError(f"unsupported prompt index {prompt_index}")
    extracted_answer, final_answer_line_format_pass = _final_answer_span(text)
    cap = output_tokens >= max_new_tokens or stop_reason == "max_new_tokens"
    answer_checks = _answer_checks(prompt_index, extracted_answer)
    fixture_checks = _fixture_checks(prompt_index, extracted_answer)
    answer_correctness_pass = bool(extracted_answer) and all(answer_checks.values())
    completeness_pass = bool(extracted_answer) and not cap
    fixture_format_compliance_pass = bool(extracted_answer) and all(fixture_checks.values())
    checks = {
        **answer_checks,
        **fixture_checks,
        "has_final_answer_span": bool(extracted_answer),
        "termination_before_token_cap": not cap,
        "exact_final_answer_line": final_answer_line_format_pass,
    }
    quality_pass = all(
        (
            answer_correctness_pass,
            completeness_pass,
            final_answer_line_format_pass,
            fixture_format_compliance_pass,
        )
    )
    return QualityResult(
        prompt_index,
        EXPECTED[prompt_index],
        extracted_answer,
        answer_correctness_pass,
        completeness_pass,
        final_answer_line_format_pass,
        fixture_format_compliance_pass,
        quality_pass,
        cap,
        stop_reason,
        checks,
    )
