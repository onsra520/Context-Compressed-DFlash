from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_system_build_and_evaluation.probes.t29_answers import normalize_text


TASK31_ARTIFACTS = [
    Path("results/task31_dflash_r1_longctx_text_n6.jsonl"),
    Path("results/task31_cc_llm_r2_longctx_text_n6.jsonl"),
    Path("results/task31_cc_llm_r3_longctx_text_n6.jsonl"),
    Path("results/task31_llmlingua_ar_r2_longctx_text_n6.jsonl"),
    Path("results/task31_llmlingua_ar_r3_longctx_text_n6.jsonl"),
]

DEFAULT_OUTPUT = Path("results/task32_answer_quality_summary.json")


class ScorerCategory(Enum):
    EXACT_CONTAINMENT = "EXACT_CONTAINMENT"
    NORMALIZED_CONTAINMENT = "NORMALIZED_CONTAINMENT"
    NO_CONTAINMENT = "NO_CONTAINMENT"
    NOT_EVALUABLE = "NOT_EVALUABLE"


@dataclass(frozen=True)
class RowScore:
    category: ScorerCategory
    exact_match: bool
    normalized_match: bool
    generated_text_present: bool
    extracted_answer: str | None = None
    expected_extracted_answer: str | None = None
    extracted_answer_match: bool = False


_NUMBER_PATTERN = r"-?\d[\d,]*(?:\.\d+)?"
_FINAL_ANSWER_PATTERNS = [
    re.compile(rf"(?:final\s+answer|answer)\s*[:：]\s*({_NUMBER_PATTERN})", re.IGNORECASE),
    re.compile(rf"####\s*({_NUMBER_PATTERN})", re.IGNORECASE),
]
_ANY_NUMBER_RE = re.compile(_NUMBER_PATTERN)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _generated_text(row: dict[str, Any]) -> str | None:
    value = row.get("generated_text")
    if isinstance(value, str) and value.strip():
        return value
    return None


def _normalize_number(value: str) -> str:
    cleaned = value.replace(",", "").strip()
    return cleaned[:-1] if cleaned.endswith(".") else cleaned


def extract_final_numeric_answer(text: str) -> str | None:
    """Extract a final numeric answer from common GSM8K-style outputs."""
    if not isinstance(text, str) or not text.strip():
        return None

    for pattern in _FINAL_ANSWER_PATTERNS:
        matches = list(pattern.finditer(text))
        if matches:
            return _normalize_number(matches[-1].group(1))

    matches = _ANY_NUMBER_RE.findall(text)
    if not matches:
        return None
    return _normalize_number(matches[-1])


def score_row(row: dict[str, Any]) -> RowScore:
    expected_answer = str(row.get("expected_answer", ""))
    generated_text = _generated_text(row)
    if generated_text is None:
        return RowScore(
            category=ScorerCategory.NOT_EVALUABLE,
            exact_match=False,
            normalized_match=False,
            generated_text_present=False,
            expected_extracted_answer=extract_final_numeric_answer(expected_answer),
        )

    exact_match = bool(expected_answer) and expected_answer in generated_text
    normalized_expected = normalize_text(expected_answer)
    normalized_generated = normalize_text(generated_text)
    normalized_match = bool(normalized_expected) and normalized_expected in normalized_generated
    extracted_answer = extract_final_numeric_answer(generated_text)
    expected_extracted_answer = extract_final_numeric_answer(expected_answer)
    extracted_answer_match = (
        extracted_answer is not None
        and expected_extracted_answer is not None
        and extracted_answer == expected_extracted_answer
    )

    if exact_match:
        category = ScorerCategory.EXACT_CONTAINMENT
    elif normalized_match:
        category = ScorerCategory.NORMALIZED_CONTAINMENT
    else:
        category = ScorerCategory.NO_CONTAINMENT

    return RowScore(
        category=category,
        exact_match=exact_match,
        normalized_match=normalized_match,
        generated_text_present=True,
        extracted_answer=extracted_answer,
        expected_extracted_answer=expected_extracted_answer,
        extracted_answer_match=extracted_answer_match,
    )


def _average(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _rate(count: int, denominator: int) -> float:
    return count / denominator if denominator else 0.0


def _numeric_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]


def summarize_rows(condition: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [score_row(row) for row in rows]
    exact_count = sum(score.exact_match for score in scores)
    normalized_count = sum(score.normalized_match for score in scores)
    normalized_only_count = sum(score.category is ScorerCategory.NORMALIZED_CONTAINMENT for score in scores)
    no_containment_count = sum(score.category is ScorerCategory.NO_CONTAINMENT for score in scores)
    not_evaluable_count = sum(score.category is ScorerCategory.NOT_EVALUABLE for score in scores)
    generated_text_present = sum(score.generated_text_present for score in scores)
    extracted_answer_match_count = sum(score.extracted_answer_match for score in scores)
    e2e_times = [
        float(row["generation_time_s"]) + (float(row.get("t_compress_ms", 0.0)) / 1000.0)
        for row in rows
    ]

    return {
        "condition": condition,
        "rows": len(rows),
        "generated_text_present": generated_text_present,
        "exact_containment_count": exact_count,
        "normalized_containment_count": normalized_count,
        "normalized_only_count": normalized_only_count,
        "no_containment_count": no_containment_count,
        "not_evaluable_count": not_evaluable_count,
        "extracted_answer_match_count": extracted_answer_match_count,
        "exact_rate": _rate(exact_count, len(rows)),
        "normalized_rate": _rate(normalized_count, len(rows)),
        "extracted_answer_match_rate": _rate(extracted_answer_match_count, len(rows)),
        "avg_generated_token_count": _average(_numeric_values(rows, "generated_token_count")),
        "avg_output_tokens": _average(_numeric_values(rows, "output_tokens")),
        "avg_e2e_time_s": _average(e2e_times),
        "avg_tok_per_sec": _average(_numeric_values(rows, "tok_per_sec")),
        "avg_tau_mean": _average(_numeric_values(rows, "tau_mean")),
        "avg_r_actual": _average(_numeric_values(rows, "R_actual")),
    }


def analyze_artifact(path: Path) -> dict[str, Any]:
    rows = load_jsonl(path)
    conditions = {str(row.get("condition")) for row in rows}
    condition = next(iter(conditions)) if len(conditions) == 1 else "mixed"
    scored_rows = []
    for index, row in enumerate(rows, start=1):
        score = score_row(row)
        scored_rows.append(
            {
                "artifact": str(path),
                "row_index": index,
                "condition": row.get("condition"),
                "prompt_id": row.get("prompt_id"),
                "fixture_id": row.get("fixture_id"),
                "expected_answer": row.get("expected_answer"),
                "generated_text": row.get("generated_text"),
                "score_category": score.category.value,
                "exact_match": score.exact_match,
                "normalized_match": score.normalized_match,
                "extracted_answer": score.extracted_answer,
                "expected_extracted_answer": score.expected_extracted_answer,
                "extracted_answer_match": score.extracted_answer_match,
                "generated_text_present": score.generated_text_present,
            }
        )

    return {
        "artifact": str(path),
        "summary": summarize_rows(condition, rows),
        "rows": scored_rows,
    }


def analyze_task31(paths: list[Path] | None = None) -> dict[str, Any]:
    artifact_paths = paths or TASK31_ARTIFACTS
    artifacts = [analyze_artifact(path) for path in artifact_paths]
    return {
        "scorer_policy": {
            "EXACT_CONTAINMENT": "expected_answer appears exactly in generated_text",
            "NORMALIZED_CONTAINMENT": "normalized expected_answer appears in normalized generated_text, but exact containment did not match",
            "NO_CONTAINMENT": "generated_text exists but expected_answer does not appear after normalization",
            "NOT_EVALUABLE": "generated_text is missing or blank",
            "extracted_answer_match": "diagnostic numeric final-answer extraction match; containment remains a separate diagnostic",
        },
        "artifacts": artifacts,
    }


def write_analysis(analysis: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def print_analysis(analysis: dict[str, Any]) -> None:
    for artifact in analysis["artifacts"]:
        summary = artifact["summary"]
        print(
            f"{summary['condition']}: rows={summary['rows']} "
            f"generated_text_present={summary['generated_text_present']} "
            f"exact={summary['exact_containment_count']} "
            f"normalized={summary['normalized_containment_count']} "
            f"normalized_only={summary['normalized_only_count']} "
            f"no_containment={summary['no_containment_count']} "
            f"not_evaluable={summary['not_evaluable_count']} "
            f"extracted={summary['extracted_answer_match_count']} "
            f"exact_rate={summary['exact_rate']:.2f} "
            f"normalized_rate={summary['normalized_rate']:.2f} "
            f"extracted_rate={summary['extracted_answer_match_rate']:.2f} "
            f"avg_generated_token_count={_fmt(summary['avg_generated_token_count'])} "
            f"avg_output_tokens={_fmt(summary['avg_output_tokens'])} "
            f"avg_e2e_time_s={_fmt(summary['avg_e2e_time_s'])} "
            f"avg_tok_per_sec={_fmt(summary['avg_tok_per_sec'])} "
            f"avg_tau_mean={_fmt(summary['avg_tau_mean'])} "
            f"avg_R_actual={_fmt(summary['avg_r_actual'])}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 31 deterministic answer-containment quality")
    parser.add_argument("artifacts", nargs="*", help="Task 31 JSONL artifacts to analyze")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="JSON summary output path")
    args = parser.parse_args()

    paths = [Path(path) for path in args.artifacts] if args.artifacts else TASK31_ARTIFACTS
    analysis = analyze_task31(paths)
    write_analysis(analysis, Path(args.output))
    print_analysis(analysis)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
