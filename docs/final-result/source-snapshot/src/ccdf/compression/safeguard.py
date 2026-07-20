"""Generic protected-span safeguards for prompt compression."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import re
from typing import Callable, Iterable

from .fact_validation import validate_facts


@dataclass(frozen=True)
class PromptSpan:
    index: int
    start: int
    end: int
    text: str
    protected: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons)
        return payload


@dataclass(frozen=True)
class SafeguardValidation:
    passed: bool
    checks: dict[str, bool]
    failure_reasons: tuple[str, ...]
    diagnostic_failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "checks": dict(self.checks),
            "failure_reasons": list(self.failure_reasons),
            "diagnostic_failures": list(self.diagnostic_failures),
        }


@dataclass(frozen=True)
class SafeguardedPrompt:
    original_prompt: str
    reconstructed_prompt: str
    spans: tuple[PromptSpan, ...]
    compressed_spans: tuple[dict[str, object], ...]
    validation: SafeguardValidation

    @property
    def protected_spans(self) -> list[dict[str, object]]:
        return [span.to_dict() for span in self.spans if span.protected]

    @property
    def compressible_spans(self) -> list[dict[str, object]]:
        return [span.to_dict() for span in self.spans if not span.protected]


_NUMBER = re.compile(
    r"(?<![\w.])(?:[$€£¥]\s*)?[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    r"(?:\s*/\s*[+-]?\d+(?:\.\d+)?)?(?:\s*%)?(?!\w)",
    re.IGNORECASE,
)
_WRITTEN_FRACTION = re.compile(
    r"\b(?:one\s+half|a\s+half|half|one\s+quarter|a\s+quarter|quarter|"
    r"one\s+third|a\s+third|third|two[-\s]+thirds|three[-\s]+quarters)\b",
    re.IGNORECASE,
)
_OPERATOR = re.compile(
    r"(?:\+|−|-|×|÷|=)|\b(?:plus|minus|times|multiplied\s+by|divided\s+by|"
    r"equals?|product|sum|difference|quotient|addition|subtract(?:ed|ion)?|"
    r"multiply|divide|percent(?:age)?)\b",
    re.IGNORECASE,
)
_UNIT = re.compile(
    r"\b(?:dollars?|cents?|usd|eur|gbp|balls?|boxes?|items?|notebooks?|pens?|"
    r"students?|boys?|girls?|liters?|litres?|kilometers?|kilometres?|km|meters?|"
    r"metres?|m|miles?|hours?|minutes?|seconds?|km/h|mph|square\s+meters?|"
    r"percent|percentage|currency)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(r"\b(?:no|not|never|without|neither|nor|none|zero)\b", re.IGNORECASE)
_RELATION = re.compile(
    r"\b(?:increase[sd]?|decrease[sd]?|add(?:ed|s|ing)?|remove[sd]?|remain(?:s|ed)?|"
    r"use[sd]?|buy|buys|bought|sell|sells|sold|discount(?:ed)?|tax|costs?|price|"
    r"original|new|final|total|attend|absent|travel(?:s|ed)?|rides?|stops?|"
    r"before|after|then|from|to|each|per|of|remaining|left|ratio|average|round)\b",
    re.IGNORECASE,
)
_TIME = re.compile(
    r"\b(?:time|elapsed|duration|stop(?:s|ped)?|before|after|then|hours?|minutes?|seconds?)\b",
    re.IGNORECASE,
)
_LOGIC = re.compile(
    r"\b(?:if|unless|only|all|any|each|every|both|either|neither|and|or|while)\b",
    re.IGNORECASE,
)
_INSTRUCTION = re.compile(
    r"\b(?:show|state|write|explain|reason|calculate|compute|label|include|repeat|round)\b",
    re.IGNORECASE,
)
_REQUEST = re.compile(
    r"(?:^|[.!?]\s*)(?:what|how|why|compute|calculate|find|determine|explain|return|report)\b",
    re.IGNORECASE,
)
_OUTPUT_CUE = re.compile(
    r"\b(?:end\s+with|final\s+(?:non-empty\s+)?line|return\s+exactly|"
    r"output\s+format|required\s+format|must\s+label|in\s+the\s+form|"
    r"include\s+currency|repeat\s+the\s+(?:requested\s+)?unit)\b",
    re.IGNORECASE,
)
_LITERAL = re.compile(r"`[^`]+`|\"[^\"\n]+\"|(?<!\w)'[^'\n]+'(?!\w)")
_STYLE_PREFIX = re.compile(
    r"^(?P<style>\s*(?:briefly|carefully|concisely|succinctly)\b\s*)",
    re.IGNORECASE,
)

_CATEGORY_PATTERNS: dict[str, re.Pattern[str]] = {
    "number": _NUMBER,
    "written_fraction": _WRITTEN_FRACTION,
    "operator": _OPERATOR,
    "unit": _UNIT,
    "negation": _NEGATION,
    "relation": _RELATION,
    "time": _TIME,
    "logic": _LOGIC,
    "instruction": _INSTRUCTION,
    "literal": _LITERAL,
}


def _sentence_ranges(prompt: str) -> Iterable[tuple[int, int, str]]:
    start = 0
    quote: str | None = None
    for index, character in enumerate(prompt):
        if character == "`":
            quote = None if quote == "`" else "`"
        elif character in {'"', "'"} and quote != "`":
            quote = None if quote == character else (character if quote is None else quote)
        decimal_dot = (
            character == "."
            and index > 0
            and index + 1 < len(prompt)
            and prompt[index - 1].isdigit()
            and prompt[index + 1].isdigit()
        )
        if quote is None and character in ".!?" and not decimal_dot:
            end = index + 1
            while end < len(prompt) and prompt[end].isspace():
                end += 1
            yield start, end, prompt[start:end]
            start = end
    if start < len(prompt):
        yield start, len(prompt), prompt[start:]


def _add_interval(
    intervals: list[tuple[int, int, str]], start: int, end: int, reason: str
) -> None:
    if start < end:
        intervals.append((start, end, reason))


def _protected_intervals(prompt: str) -> list[tuple[int, int, str]]:
    intervals: list[tuple[int, int, str]] = []
    for match in _LITERAL.finditer(prompt):
        _add_interval(intervals, match.start(), match.end(), "required_literal")
    for start, end, sentence in _sentence_ranges(prompt):
        request = _REQUEST.search(sentence)
        if "?" in sentence or request:
            _add_interval(intervals, start, end, "main_request")
        cue = _OUTPUT_CUE.search(sentence)
        if cue:
            _add_interval(intervals, start + cue.start(), end, "output_constraint")
        # Preserve the complete semantic clause around critical vocabulary.  A
        # generic stylistic adverb at the beginning remains independently
        # compressible so the safeguard cannot degrade into whole-prompt
        # protection on dense mathematical prompts.
        clause_start = 0
        for delimiter in re.finditer(r"[,;]|\b(?:then|otherwise)\b", sentence, re.IGNORECASE):
            clause_end = delimiter.end()
            clause = sentence[clause_start:clause_end]
            critical = any(
                pattern.search(clause)
                for name, pattern in _CATEGORY_PATTERNS.items()
                if name != "literal"
            )
            if critical:
                style = _STYLE_PREFIX.match(clause)
                protected_start = clause_start + (style.end() if style else 0)
                _add_interval(
                    intervals,
                    start + protected_start,
                    start + clause_end,
                    "semantic_clause",
                )
            clause_start = clause_end
        clause = sentence[clause_start:]
        critical = any(
            pattern.search(clause)
            for name, pattern in _CATEGORY_PATTERNS.items()
            if name != "literal"
        )
        if critical:
            style = _STYLE_PREFIX.match(clause)
            protected_start = clause_start + (style.end() if style else 0)
            _add_interval(
                intervals,
                start + protected_start,
                end,
                "semantic_clause",
            )
    for reason, pattern in _CATEGORY_PATTERNS.items():
        if reason == "literal":
            continue
        for match in pattern.finditer(prompt):
            _add_interval(intervals, match.start(), match.end(), reason)
    return intervals


def _merge_intervals(
    intervals: list[tuple[int, int, str]], prompt_length: int
) -> list[tuple[int, int, tuple[str, ...]]]:
    events = sorted(intervals, key=lambda value: (value[0], value[1]))
    merged: list[tuple[int, int, set[str]]] = []
    for start, end, reason in events:
        start = max(0, min(start, prompt_length))
        end = max(start, min(end, prompt_length))
        if not merged or start > merged[-1][1]:
            merged.append((start, end, {reason}))
            continue
        previous_start, previous_end, reasons = merged[-1]
        reasons.add(reason)
        merged[-1] = (previous_start, max(previous_end, end), reasons)
    return [(start, end, tuple(sorted(reasons))) for start, end, reasons in merged]


def segment_prompt(prompt: str) -> tuple[PromptSpan, ...]:
    if not prompt.strip():
        raise ValueError("prompt must be non-empty")
    intervals = _merge_intervals(_protected_intervals(prompt), len(prompt))
    raw: list[tuple[int, int, bool, tuple[str, ...]]] = []
    cursor = 0
    for start, end, reasons in intervals:
        if cursor < start:
            raw.append((cursor, start, False, ()))
        raw.append((start, end, True, reasons))
        cursor = end
    if cursor < len(prompt):
        raw.append((cursor, len(prompt), False, ()))
    spans: list[PromptSpan] = []
    for start, end, protected, reasons in raw:
        text = prompt[start:end]
        if not protected and not re.search(r"[A-Za-z0-9]", text):
            protected = True
            reasons = ("separator",)
        spans.append(
            PromptSpan(
                index=len(spans),
                start=start,
                end=end,
                text=text,
                protected=protected,
                reasons=reasons,
            )
        )
    return tuple(spans)


def _inventory(text: str, pattern: re.Pattern[str]) -> Counter[str]:
    return Counter(re.sub(r"\s+", " ", match.group(0).strip().lower()) for match in pattern.finditer(text))


def validate_safeguard(
    original: str,
    reconstructed: str,
    spans: tuple[PromptSpan, ...],
    compressed_spans: tuple[dict[str, object], ...],
) -> SafeguardValidation:
    coverage = (
        "".join(span.text for span in spans) == original
        and bool(spans)
        and spans[0].start == 0
        and spans[-1].end == len(original)
        and all(
            span.index == index
            and span.start < span.end
            and span.text == original[span.start : span.end]
            and (index == 0 or spans[index - 1].end == span.start)
            for index, span in enumerate(spans)
        )
    )
    protected_order = True
    cursor = 0
    for span in spans:
        if not span.protected:
            continue
        found = reconstructed.find(span.text, cursor)
        if found < 0:
            protected_order = False
            break
        cursor = found + len(span.text)
    checks = {
        "segmentation_coverage": coverage,
        "protected_spans_exact_and_ordered": protected_order,
        "non_empty_reconstruction": bool(reconstructed.strip()),
        "compressor_invoked": bool(compressed_spans),
        "effective_compression": any(
            str(row["original_text"]) != str(row["compressed_text"])
            for row in compressed_spans
        ),
    }
    facts = validate_facts(original, reconstructed)
    for category, passed in facts.checks.items():
        checks[f"fact_{category}"] = passed
    # Retain the established public check names while sourcing the decision
    # from the independent normalized validator.
    aliases = {
        "number": ("numbers", "currencies", "percentages", "numeric_fractions"),
        "written_fraction": ("written_fractions",),
        "unit": ("units",),
        "relation": ("relations",),
        "negation": ("negations",),
    }
    for category, fact_categories in aliases.items():
        checks[f"preserve_{category}"] = all(facts.checks[name] for name in fact_categories)
    for category, pattern in _CATEGORY_PATTERNS.items():
        checks.setdefault(
            f"preserve_{category}",
            _inventory(original, pattern) == _inventory(reconstructed, pattern),
        )
    checks["preserve_output_constraint"] = bool(_OUTPUT_CUE.search(original)) == bool(
        _OUTPUT_CUE.search(reconstructed)
    )
    checks["preserve_main_request"] = bool(_REQUEST.search(original) or "?" in original) == bool(
        _REQUEST.search(reconstructed) or "?" in reconstructed
    )
    diagnostic_names = {"compressor_invoked", "effective_compression"}
    failures = tuple(
        name for name, passed in checks.items() if not passed and name not in diagnostic_names
    )
    diagnostics = tuple(
        name for name, passed in checks.items() if not passed and name in diagnostic_names
    )
    return SafeguardValidation(not failures, checks, failures, diagnostics)


def _preserve_boundary_whitespace(original: str, replacement: str) -> str:
    # A protected word may end exactly where a compressible span starts. Keep
    # punctuation as well as whitespace so compression cannot join it to the
    # next word and silently change regex/token boundaries (for example
    # ``then, possibly`` becoming ``thenpossibly``).
    leading = re.match(r"[^\w]*", original).group(0)
    trailing = re.search(r"[^\w]*$", original).group(0)
    core = re.sub(r"[^\w]+$", "", re.sub(r"^[^\w]+", "", replacement))
    if not core:
        return leading or trailing
    return f"{leading}{core}{trailing}"


def safeguard_prompt(prompt: str, compressor: Callable[[str], str]) -> SafeguardedPrompt:
    spans = segment_prompt(prompt)
    reconstructed: list[str] = []
    compressed_rows: list[dict[str, object]] = []
    for span in spans:
        if span.protected:
            reconstructed.append(span.text)
            continue
        compressed = _preserve_boundary_whitespace(span.text, compressor(span.text))
        reconstructed.append(compressed)
        compressed_rows.append(
            {
                "span_index": span.index,
                "start": span.start,
                "end": span.end,
                "original_text": span.text,
                "compressed_text": compressed,
            }
        )
    rebuilt = "".join(reconstructed)
    rows = tuple(compressed_rows)
    validation = validate_safeguard(prompt, rebuilt, spans, rows)
    return SafeguardedPrompt(prompt, rebuilt, spans, rows, validation)


def safeguard_prompt_batch(
    prompt: str,
    compressor: Callable[[list[str]], list[str]],
) -> SafeguardedPrompt:
    """Compress all eligible spans in one model batch while preserving their boundaries."""
    spans = segment_prompt(prompt)
    eligible = [span for span in spans if not span.protected]
    replacements = compressor([span.text for span in eligible]) if eligible else []
    if len(replacements) != len(eligible):
        raise ValueError(
            f"batch compressor returned {len(replacements)} spans for {len(eligible)} inputs"
        )
    replacement_by_index = dict(
        zip((span.index for span in eligible), replacements, strict=True)
    )
    reconstructed: list[str] = []
    compressed_rows: list[dict[str, object]] = []
    for span in spans:
        if span.protected:
            reconstructed.append(span.text)
            continue
        compressed = _preserve_boundary_whitespace(
            span.text, str(replacement_by_index[span.index])
        )
        reconstructed.append(compressed)
        compressed_rows.append(
            {
                "span_index": span.index,
                "start": span.start,
                "end": span.end,
                "original_text": span.text,
                "compressed_text": compressed,
            }
        )
    rebuilt = "".join(reconstructed)
    rows = tuple(compressed_rows)
    validation = validate_safeguard(prompt, rebuilt, spans, rows)
    return SafeguardedPrompt(prompt, rebuilt, spans, rows, validation)
