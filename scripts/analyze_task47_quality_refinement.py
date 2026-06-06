from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_task29_answers import normalize_text


DEFAULT_AUDIT = Path("results/task45_final_artifact_audit_summary.json")
DEFAULT_PARETO = Path("results/task46_pareto_summary.json")
DEFAULT_OUTPUT = Path("results/task47_quality_refinement_summary.json")
DEFAULT_SAMPLES_OUTPUT = Path("results/task47_quality_failure_samples.jsonl")
DEFAULT_CSV = Path("results/task47_quality_table.csv")
DEFAULT_FIXTURE = Path("data/processed/gsm8k_wikipedia_augmented_full.jsonl")
CONDITION_ORDER = ["Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-LLM-R2"]

NUMBER_RE = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?")
MARKER_PATTERNS = [
    re.compile(r"(?:^|\n)\s*####\s*(?P<number>[-+]?\$?\d[\d,]*(?:\.\d+)?)", re.IGNORECASE),
    re.compile(
        r"(?:final\s+(?:numeric\s+)?answer|answer)\s*(?:is|=|:|：)\s*(?P<number>[-+]?\$?\d[\d,]*(?:\.\d+)?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:therefore|so|thus)[^\n.]{0,80}?(?:answer|result)[^\n.]{0,30}?(?:is|=|:|：)\s*(?P<number>[-+]?\$?\d[\d,]*(?:\.\d+)?)",
        re.IGNORECASE,
    ),
]


@dataclass(frozen=True)
class Extraction:
    answer: str | None
    candidates: list[str]
    source: str
    ambiguous: bool


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: line {line_number} is not valid JSON ({exc})") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}: line {line_number} is not a JSON object")
        rows.append(row)
    return rows


def normalize_numeric(value: str | int | float | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = NUMBER_RE.search(text)
    if not match:
        return None
    number = match.group(0).replace("$", "").replace(",", "").strip()
    if number.endswith("."):
        number = number[:-1]
    if number.startswith("+"):
        number = number[1:]
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    if number == "-0":
        number = "0"
    return number


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def extract_numeric_answer(text: str | None) -> Extraction:
    if not isinstance(text, str) or not text.strip():
        return Extraction(answer=None, candidates=[], source="missing", ambiguous=False)

    marked_candidates: list[str] = []
    for pattern in MARKER_PATTERNS:
        for match in pattern.finditer(text):
            normalized = normalize_numeric(match.group("number"))
            if normalized is not None:
                marked_candidates.append(normalized)
    marked_candidates = _unique_preserving_order(marked_candidates)
    if marked_candidates:
        return Extraction(
            answer=marked_candidates[-1],
            candidates=marked_candidates,
            source="marked_final_answer",
            ambiguous=len(marked_candidates) > 1,
        )

    tail = text[-500:]
    fallback_candidates = [
        normalized
        for normalized in (normalize_numeric(match.group(0)) for match in NUMBER_RE.finditer(tail))
        if normalized is not None
    ]
    fallback_candidates = _unique_preserving_order(fallback_candidates)
    if fallback_candidates:
        return Extraction(
            answer=fallback_candidates[-1],
            candidates=fallback_candidates,
            source="last_number_fallback",
            ambiguous=False,
        )
    return Extraction(answer=None, candidates=[], source="no_number", ambiguous=False)


def expected_answer_for(row: dict[str, Any], fixture_by_id: dict[str, dict[str, Any]] | None = None) -> str:
    for field_name in ("expected_answer", "ground_truth_answer", "answer"):
        value = row.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
    fixture_id = row.get("fixture_id") or row.get("dataset_id") or row.get("id")
    if fixture_by_id and fixture_id in fixture_by_id:
        fixture_row = fixture_by_id[fixture_id]
        for field_name in ("expected_answer", "ground_truth_answer", "answer"):
            value = fixture_row.get(field_name)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _is_truncated(row: dict[str, Any], generated_text: str | None) -> bool:
    output_tokens = row.get("output_tokens")
    max_new_tokens = row.get("max_new_tokens")
    if isinstance(output_tokens, (int, float)) and isinstance(max_new_tokens, (int, float)):
        if output_tokens >= max_new_tokens:
            return True
    if not isinstance(generated_text, str) or not generated_text.strip():
        return False
    stripped = generated_text.rstrip()
    if stripped.endswith((".", "!", "?", "。", ")", "]")):
        return False
    return len(stripped.split()) > 40


def _excerpt(text: str | None, limit: int = 360) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def classify_row(
    row: dict[str, Any],
    *,
    row_index: int,
    condition: str,
    artifact: str,
    fixture_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    expected_answer = expected_answer_for(row, fixture_by_id)
    generated_text = row.get("generated_text")
    prompt_id = row.get("benchmark_prompt_index", row.get("prompt_id", row_index))

    if not isinstance(generated_text, str) or not generated_text.strip():
        return {
            "artifact": artifact,
            "condition": condition,
            "row_index": row_index,
            "prompt_id": prompt_id,
            "fixture_id": row.get("fixture_id"),
            "expected_answer": expected_answer,
            "expected_numeric": normalize_numeric(expected_answer),
            "extracted_answer": None,
            "extraction_source": "missing",
            "candidate_answers": [],
            "exact_match": False,
            "numeric_match": False,
            "failure_type": "generated_text_missing",
            "truncated_or_stopped_early": False,
            "generated_text_excerpt": "",
        }

    exact_match = bool(expected_answer) and expected_answer in generated_text
    normalized_match = bool(expected_answer) and normalize_text(expected_answer) in normalize_text(generated_text)
    extraction = extract_numeric_answer(generated_text)
    expected_numeric = normalize_numeric(expected_answer)
    numeric_match = (
        extraction.answer is not None
        and expected_numeric is not None
        and extraction.answer == expected_numeric
    )
    truncated = _is_truncated(row, generated_text)

    if extraction.ambiguous:
        failure_type = "parse_ambiguous"
    elif exact_match:
        failure_type = "exact_match"
    elif numeric_match:
        failure_type = "numeric_match"
    elif extraction.answer is not None:
        failure_type = "extracted_but_wrong"
    elif truncated:
        failure_type = "truncated_or_stopped_early"
    else:
        failure_type = "no_final_answer_found"

    return {
        "artifact": artifact,
        "condition": condition,
        "row_index": row_index,
        "prompt_id": prompt_id,
        "fixture_id": row.get("fixture_id"),
        "expected_answer": expected_answer,
        "expected_numeric": expected_numeric,
        "extracted_answer": extraction.answer,
        "extraction_source": extraction.source,
        "candidate_answers": extraction.candidates,
        "exact_match": exact_match,
        "normalized_text_match": normalized_match,
        "numeric_match": numeric_match,
        "failure_type": failure_type,
        "truncated_or_stopped_early": truncated,
        "output_tokens": row.get("output_tokens"),
        "max_new_tokens": row.get("max_new_tokens"),
        "generated_text_excerpt": _excerpt(generated_text),
    }


def _load_fixture(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    rows = load_jsonl(path)
    return {
        str(row.get("id") or row.get("fixture_id") or row.get("dataset_id")): row
        for row in rows
        if row.get("id") or row.get("fixture_id") or row.get("dataset_id")
    }


def _rate(count: int, denominator: int) -> float:
    return count / denominator if denominator else 0.0


def summarize_classifications(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    counts = Counter(row["failure_type"] for row in rows)
    generated_text_rows = sum(row["failure_type"] != "generated_text_missing" for row in rows)
    exact_count = counts["exact_match"]
    numeric_count = sum(1 for row in rows if row.get("numeric_match"))
    ambiguous_count = counts["parse_ambiguous"]
    missing_count = counts["generated_text_missing"]
    no_final_count = counts["no_final_answer_found"]
    extracted_wrong_count = counts["extracted_but_wrong"]
    truncated_count = counts["truncated_or_stopped_early"]
    return {
        "rows": total,
        "generated_text_rows": generated_text_rows,
        "exact_match_count": exact_count,
        "numeric_match_count": numeric_count,
        "extracted_but_wrong_count": extracted_wrong_count,
        "no_final_answer_found_count": no_final_count,
        "ambiguous_count": ambiguous_count,
        "missing_generated_text_count": missing_count,
        "truncated_or_stopped_early_count": truncated_count,
        "exact_match_rate": _rate(exact_count, total),
        "numeric_match_rate": _rate(numeric_count, total),
        "no_answer_rate": _rate(no_final_count + truncated_count + missing_count, total),
        "failure_mode_distribution": dict(sorted(counts.items())),
    }


def select_failure_samples(classified_by_condition: dict[str, list[dict[str, Any]]], limit_per_condition: int = 5) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for condition in CONDITION_ORDER:
        failures = [
            row
            for row in classified_by_condition.get(condition, [])
            if row["failure_type"] not in {"exact_match", "numeric_match"}
        ]
        for row in failures[:limit_per_condition]:
            samples.append(
                {
                    "condition": row["condition"],
                    "artifact": row["artifact"],
                    "row_index": row["row_index"],
                    "prompt_id": row["prompt_id"],
                    "fixture_id": row.get("fixture_id"),
                    "expected_answer": row["expected_answer"],
                    "expected_numeric": row["expected_numeric"],
                    "extracted_answer": row["extracted_answer"],
                    "candidate_answers": row["candidate_answers"],
                    "failure_type": row["failure_type"],
                    "truncated_or_stopped_early": row["truncated_or_stopped_early"],
                    "generated_text_excerpt": row["generated_text_excerpt"],
                }
            )
    return samples


def compare_quality(conditions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pairs = [
        ("DFlash-R1_vs_Baseline-AR", "DFlash-R1", "Baseline-AR"),
        ("LLMLingua-AR-R2_vs_Baseline-AR", "LLMLingua-AR-R2", "Baseline-AR"),
        ("CC-LLM-R2_vs_LLMLingua-AR-R2", "CC-LLM-R2", "LLMLingua-AR-R2"),
        ("CC-LLM-R2_vs_DFlash-R1", "CC-LLM-R2", "DFlash-R1"),
        ("CC-LLM-R2_vs_Baseline-AR", "CC-LLM-R2", "Baseline-AR"),
    ]
    comparisons = {}
    for key, left, right in pairs:
        left_summary = conditions[left]
        right_summary = conditions[right]
        comparisons[key] = {
            "left_condition": left,
            "right_condition": right,
            "exact_match_rate_delta": left_summary["exact_match_rate"] - right_summary["exact_match_rate"],
            "numeric_match_rate_delta": left_summary["numeric_match_rate"] - right_summary["numeric_match_rate"],
            "no_answer_rate_delta": left_summary["no_answer_rate"] - right_summary["no_answer_rate"],
            "extracted_but_wrong_delta": left_summary["extracted_but_wrong_count"] - right_summary["extracted_but_wrong_count"],
            "truncated_delta": left_summary["truncated_or_stopped_early_count"] - right_summary["truncated_or_stopped_early_count"],
        }
    return comparisons


def analyze_task47(
    *,
    audit_path: Path = DEFAULT_AUDIT,
    pareto_path: Path = DEFAULT_PARETO,
    fixture_path: Path | None = DEFAULT_FIXTURE,
) -> dict[str, Any]:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    pareto = json.loads(pareto_path.read_text(encoding="utf-8"))
    if audit.get("status") != "PASS":
        raise ValueError(f"Task 45 audit summary is not PASS: {audit.get('status')}")
    if pareto.get("status") != "PASS":
        raise ValueError(f"Task 46 Pareto summary is not PASS: {pareto.get('status')}")

    fixture_by_id = _load_fixture(fixture_path)
    classified_by_condition: dict[str, list[dict[str, Any]]] = {}
    summaries: dict[str, dict[str, Any]] = {}

    for condition in CONDITION_ORDER:
        artifact_path = Path(audit["artifacts"][condition]["path"])
        rows = load_jsonl(artifact_path)
        classified = [
            classify_row(
                row,
                row_index=row_index,
                condition=condition,
                artifact=str(artifact_path),
                fixture_by_id=fixture_by_id,
            )
            for row_index, row in enumerate(rows, start=1)
        ]
        classified_by_condition[condition] = classified
        summaries[condition] = summarize_classifications(classified)

    samples = select_failure_samples(classified_by_condition)
    recommendation = (
        "Task 48 can produce paper-ready figures only if figures label quality as deterministic numeric extraction "
        "and avoid final semantic correctness claims. A separate semantic/human evaluation remains recommended."
    )

    return {
        "task": "47-quality-refinement",
        "status": "PASS",
        "inputs": {
            "audit_summary": str(audit_path),
            "pareto_summary": str(pareto_path),
            "fixture": str(fixture_path) if fixture_path else None,
            "artifacts": {
                condition: audit["artifacts"][condition]["path"]
                for condition in CONDITION_ORDER
            },
        },
        "method": {
            "judge": "deterministic_only_no_llm_judge",
            "exact_match": "expected_answer appears verbatim in generated_text",
            "numeric_match": "normalized expected numeric answer equals deterministic extracted numeric answer",
            "final_answer_markers": ["####", "final answer:", "answer:", "answer is", "therefore ... answer is"],
            "fallback": "last standalone number in generated_text tail when no final-answer marker exists",
            "truncation_signal": "output_tokens >= max_new_tokens or long generated_text ending without terminal punctuation",
        },
        "conditions": summaries,
        "comparisons": compare_quality(summaries),
        "failure_samples": {
            "path": str(DEFAULT_SAMPLES_OUTPUT),
            "rows": len(samples),
            "limit_per_condition": 5,
        },
        "claim_policy": {
            "allowed": [
                "measured decode throughput",
                "estimated e2e throughput with CPU compression",
                "diagnostic numeric answer extraction",
                "deterministic failure-mode counts",
            ],
            "forbidden": [
                "final semantic correctness",
                "deployment readiness",
                "confirmed 8 GB deployment",
                "proven end-to-end compression benefit",
                "LLM-judge quality claims",
            ],
        },
        "packaging_decision": {
            "task48_recommendation": recommendation,
            "paper_ready_figures_allowed": True,
            "quality_policy_clear": True,
            "quality_caveat": "Use deterministic numeric extraction as a proxy and label it clearly; do not call it final EM or semantic correctness.",
        },
        "samples": samples,
    }


def write_summary(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = dict(summary)
    serializable.pop("samples", None)
    path.write_text(json.dumps(serializable, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_samples(samples: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(sample, ensure_ascii=False, sort_keys=True) + "\n" for sample in samples),
        encoding="utf-8",
    )


def write_csv(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "condition",
        "rows",
        "generated_text_rows",
        "exact_match_count",
        "numeric_match_count",
        "extracted_but_wrong_count",
        "no_final_answer_found_count",
        "truncated_or_stopped_early_count",
        "ambiguous_count",
        "missing_generated_text_count",
        "exact_match_rate",
        "numeric_match_rate",
        "no_answer_rate",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for condition in CONDITION_ORDER:
            row = dict(summary["conditions"][condition])
            row["condition"] = condition
            writer.writerow({field: row.get(field) for field in fields})


def print_summary(summary: dict[str, Any]) -> None:
    print(f"status: {summary['status']}")
    for condition in CONDITION_ORDER:
        item = summary["conditions"][condition]
        print(
            f"{condition}: rows={item['rows']} exact={item['exact_match_count']} "
            f"numeric={item['numeric_match_count']} wrong={item['extracted_but_wrong_count']} "
            f"no_final={item['no_final_answer_found_count']} truncated={item['truncated_or_stopped_early_count']} "
            f"ambiguous={item['ambiguous_count']} missing={item['missing_generated_text_count']} "
            f"numeric_rate={item['numeric_match_rate']:.2f}"
        )
    print(f"samples: {summary['failure_samples']['rows']} -> {summary['failure_samples']['path']}")
    print(f"recommendation: {summary['packaging_decision']['task48_recommendation']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 47 deterministic quality refinement")
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT), help="Task 45 audit summary JSON")
    parser.add_argument("--pareto", default=str(DEFAULT_PARETO), help="Task 46 Pareto summary JSON")
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE), help="Optional source fixture JSONL")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON summary path")
    parser.add_argument("--samples-output", default=str(DEFAULT_SAMPLES_OUTPUT), help="Failure samples JSONL path")
    parser.add_argument("--csv-output", default=str(DEFAULT_CSV), help="Optional CSV table output path")
    args = parser.parse_args()

    fixture = Path(args.fixture) if args.fixture else None
    summary = analyze_task47(audit_path=Path(args.audit), pareto_path=Path(args.pareto), fixture_path=fixture)
    write_summary(summary, Path(args.output))
    write_samples(summary["samples"], Path(args.samples_output))
    if args.csv_output:
        write_csv(summary, Path(args.csv_output))
    print_summary(summary)
    print(f"wrote {args.output}")
    print(f"wrote {args.samples_output}")
    if args.csv_output:
        print(f"wrote {args.csv_output}")


if __name__ == "__main__":
    main()
