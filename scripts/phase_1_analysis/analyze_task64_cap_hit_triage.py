from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_analysis.analyze_task47_quality_refinement import classify_row, normalize_numeric


TASK63_PATHS = {
    "LLMLingua-AR-R2": Path("results/task63_gsm8k_short_llmlingua_ar_r2_n30_mnt256.jsonl"),
    "CC-DFlash-R2": Path("results/task63_gsm8k_short_cc_dflash_r2_n30_mnt256.jsonl"),
}
DEFAULT_DATASET = Path("data/eval/gsm8k_100.jsonl")
DEFAULT_SUMMARY_OUTPUT = Path("results/task64_cap_hit_triage_summary.json")
DEFAULT_CASES_OUTPUT = Path("results/task64_cap_hit_cases.jsonl")

FINAL_ANSWER_MARKER_RE = re.compile(
    r"final\s+(?:numeric\s+)?answer\s*(?:is|=|:|：)\s*[-+]?\$?\d[\d,]*(?:\.\d+)?",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?")
UNFINISHED_HINTS = (
    "let ",
    "we need",
    "we are given",
    "solve for",
    "therefore",
    "so:",
    "step",
    "equation",
)


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


def _dataset_index(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {str(row.get("id")): row for row in load_jsonl(path) if row.get("id") is not None}


def _compact(text: Any, *, limit: int = 500) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def _hit_cap(row: dict[str, Any]) -> bool:
    output_tokens = row.get("output_tokens")
    max_new_tokens = row.get("max_new_tokens")
    return (
        isinstance(output_tokens, (int, float))
        and not isinstance(output_tokens, bool)
        and isinstance(max_new_tokens, (int, float))
        and not isinstance(max_new_tokens, bool)
        and output_tokens >= max_new_tokens
    )


def _has_final_answer_marker(text: Any) -> bool:
    return isinstance(text, str) and bool(FINAL_ANSWER_MARKER_RE.search(text))


def _expected_appears_in_text(expected_answer: str, text: Any) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    expected_numeric = normalize_numeric(expected_answer)
    if expected_numeric is None:
        return expected_answer.strip() in text
    found = {
        normalize_numeric(match.group(0))
        for match in NUMBER_RE.finditer(text)
    }
    return expected_numeric in found


def _numbers_from_text(text: Any) -> set[str]:
    if not isinstance(text, str):
        return set()
    return {
        normalized
        for normalized in (normalize_numeric(match.group(0)) for match in NUMBER_RE.finditer(text))
        if normalized is not None
    }


def _preview_text(row: dict[str, Any]) -> str:
    parts = [
        row.get("compressed_prompt_preview"),
        row.get("compressed_context_preview"),
        row.get("final_prompt_preview"),
        row.get("final_prompt_tail_preview"),
    ]
    return "\n".join(str(part) for part in parts if isinstance(part, str))


def _compressed_preview_missing_question_numbers(row: dict[str, Any], dataset_row: dict[str, Any] | None) -> bool:
    if not dataset_row:
        return False
    question_numbers = _numbers_from_text(dataset_row.get("question"))
    if not question_numbers:
        return False
    preview_numbers = _numbers_from_text(_preview_text(row))
    missing = question_numbers - preview_numbers
    return bool(missing) and len(missing) >= max(1, len(question_numbers) // 2)


def _appears_unfinished(text: Any) -> bool:
    if not isinstance(text, str) or not text.strip():
        return True
    stripped = text.strip()
    if stripped.endswith(("=", "+", "-", "*", "/", ":", ",")):
        return True
    tail = stripped[-240:].lower()
    return any(hint in tail for hint in UNFINISHED_HINTS)


def _label_case(
    *,
    row: dict[str, Any],
    classified: dict[str, Any],
    dataset_row: dict[str, Any] | None,
) -> tuple[str, str]:
    expected_answer = str(row.get("expected_answer") or classified.get("expected_answer") or "")
    generated_text = row.get("generated_text")
    hit_cap = _hit_cap(row)
    has_marker = _has_final_answer_marker(generated_text)

    if hit_cap and not has_marker and _appears_unfinished(generated_text):
        return "TRUNCATION_DOMINANT", "row hit max_new_tokens, appears unfinished, and did not reach a final-answer marker"

    if not classified.get("numeric_match") and has_marker:
        return "REASONING_FAIL", "row completed with a final-answer marker, but the extracted numeric answer is wrong"

    if not hit_cap and not classified.get("numeric_match") and _expected_appears_in_text(expected_answer, generated_text):
        return "EXTRACTION_ISSUE", "expected numeric answer appears in generated text, but extraction did not match"

    if not classified.get("numeric_match") and _compressed_preview_missing_question_numbers(row, dataset_row):
        return "COMPRESSION_LOSS_POSSIBLE", "compressed preview appears to omit multiple numeric tokens from the original question"

    if hit_cap and not classified.get("numeric_match"):
        return "TRUNCATION_DOMINANT", "row hit max_new_tokens and numeric extraction failed"

    return "UNCLEAR", "insufficient evidence for a more specific label"


def _case_row(
    *,
    condition: str,
    row: dict[str, Any],
    classified: dict[str, Any],
    dataset_row: dict[str, Any] | None,
    artifact: str,
) -> dict[str, Any]:
    label, rationale = _label_case(row=row, classified=classified, dataset_row=dataset_row)
    expected_answer = str(row.get("expected_answer") or classified.get("expected_answer") or "")
    return {
        "condition": condition,
        "artifact": artifact,
        "prompt_id": row.get("prompt_id"),
        "benchmark_prompt_index": row.get("benchmark_prompt_index"),
        "dataset_id": row.get("dataset_id") or row.get("fixture_id"),
        "expected_answer": expected_answer,
        "extracted_answer": classified.get("extracted_answer"),
        "numeric_match": bool(classified.get("numeric_match")),
        "exact_match": bool(classified.get("exact_match")),
        "hit_cap": _hit_cap(row),
        "output_tokens": row.get("output_tokens"),
        "max_new_tokens": row.get("max_new_tokens"),
        "final_answer_marker": _has_final_answer_marker(row.get("generated_text")),
        "failure_label": label,
        "label_rationale": rationale,
        "original_input_tokens": row.get("original_input_tokens"),
        "compressed_input_tokens": row.get("compressed_input_tokens"),
        "actual_compression_ratio": row.get("actual_compression_ratio") or row.get("compression_ratio"),
        "protected_suffix_preserved": row.get("protected_suffix_preserved"),
        "question_preserved": row.get("question_preserved"),
        "final_prompt_tail_preview": _compact(row.get("final_prompt_tail_preview"), limit=300),
        "compressed_prompt_preview": _compact(row.get("compressed_prompt_preview") or row.get("final_prompt_preview")),
        "generated_text_snippet": _compact(row.get("generated_text")),
    }


def _summarize_condition(
    *,
    condition: str,
    artifact: Path,
    dataset: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = load_jsonl(artifact)
    cases: list[dict[str, Any]] = []
    numeric_matches = 0
    exact_matches = 0
    cap_hits = 0
    cap_hit_failures = 0
    non_cap_failures = 0

    for row_index, row in enumerate(rows, start=1):
        classified = classify_row(row, row_index=row_index, condition=condition, artifact=str(artifact))
        numeric_match = bool(classified.get("numeric_match"))
        exact_match = bool(classified.get("exact_match"))
        hit_cap = _hit_cap(row)
        numeric_matches += int(numeric_match)
        exact_matches += int(exact_match)
        cap_hits += int(hit_cap)
        if hit_cap and not numeric_match:
            cap_hit_failures += 1
        if not hit_cap and not numeric_match:
            non_cap_failures += 1
        if hit_cap or not numeric_match:
            dataset_id = str(row.get("dataset_id") or row.get("fixture_id") or "")
            cases.append(
                _case_row(
                    condition=condition,
                    row=row,
                    classified=classified,
                    dataset_row=dataset.get(dataset_id),
                    artifact=str(artifact),
                )
            )

    total_rows = len(rows)
    projected_matches = min(total_rows, numeric_matches + cap_hit_failures)
    summary = {
        "condition": condition,
        "artifact": str(artifact),
        "total_rows": total_rows,
        "numeric_matches": numeric_matches,
        "numeric_match_rate": round(numeric_matches / total_rows, 6) if total_rows else 0.0,
        "numeric_failures": total_rows - numeric_matches,
        "exact_matches": exact_matches,
        "cap_hits": cap_hits,
        "cap_hit_failures": cap_hit_failures,
        "non_cap_failures": non_cap_failures,
        "cap_hit_failure_overlap_rate": round(cap_hit_failures / cap_hits, 6) if cap_hits else 0.0,
        "projected_upper_bound_matches_if_cap_failures_fixed": projected_matches,
        "projected_upper_bound_rate_if_cap_failures_fixed": round(projected_matches / total_rows, 6) if total_rows else 0.0,
        "label_counts": dict(Counter(case["failure_label"] for case in cases)),
        "case_count": len(cases),
    }
    return summary, cases


def analyze_paths(
    *,
    artifact_paths: dict[str, Path] | None = None,
    dataset_path: Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    artifact_paths = artifact_paths or TASK63_PATHS
    dataset_path = dataset_path or DEFAULT_DATASET
    dataset = _dataset_index(dataset_path)

    by_condition: dict[str, dict[str, Any]] = {}
    cases: list[dict[str, Any]] = []
    for condition, artifact in artifact_paths.items():
        condition_summary, condition_cases = _summarize_condition(
            condition=condition,
            artifact=artifact,
            dataset=dataset,
        )
        by_condition[condition] = condition_summary
        cases.extend(condition_cases)

    label_counts = dict(Counter(case["failure_label"] for case in cases))
    cap_hit_failures = sum(item["cap_hit_failures"] for item in by_condition.values())
    non_cap_failures = sum(item["non_cap_failures"] for item in by_condition.values())
    truncation_dominant = label_counts.get("TRUNCATION_DOMINANT", 0)
    reasoning_fail = label_counts.get("REASONING_FAIL", 0)

    if truncation_dominant >= reasoning_fail and cap_hit_failures:
        recommendation = (
            "Run tiny Task 65 with n=10 and max_new_tokens=384 before n=100; "
            "use it only to test whether cap-hit rows finish cleanly."
        )
        recommended_next_task = "Task 65 tiny GSM8K max_new_tokens=384 cap-hit calibration"
    else:
        recommendation = "Stop increasing token budget for now and investigate reasoning/compression failures first."
        recommended_next_task = "Reasoning/compression failure triage before token-budget changes"

    summary = {
        "task": "Task 64 cap-hit triage on Task 63 GSM8K n=30 results",
        "status": "PASS",
        "claim_policy": "read-only artifact analysis; projected upper bounds are theoretical and not benchmark results",
        "inputs": {
            "artifacts": {condition: str(path) for condition, path in artifact_paths.items()},
            "dataset": str(dataset_path),
        },
        "by_condition": by_condition,
        "overall": {
            "total_cases": len(cases),
            "label_counts": label_counts,
            "total_cap_hit_failures": cap_hit_failures,
            "total_non_cap_failures": non_cap_failures,
        },
        "recommendation": recommendation,
        "recommended_next_task": recommended_next_task,
    }
    return summary, cases


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 63 GSM8K failures and cap-hit rows")
    parser.add_argument("--summary-output", default=str(DEFAULT_SUMMARY_OUTPUT))
    parser.add_argument("--cases-output", default=str(DEFAULT_CASES_OUTPUT))
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    args = parser.parse_args()

    summary, cases = analyze_paths(dataset_path=Path(args.dataset))
    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(Path(args.cases_output), cases)

    print(f"status={summary['status']}")
    for condition, item in summary["by_condition"].items():
        print(
            f"{condition}: rows={item['total_rows']} numeric={item['numeric_matches']} "
            f"failures={item['numeric_failures']} cap_hits={item['cap_hits']} "
            f"cap_hit_failures={item['cap_hit_failures']} non_cap_failures={item['non_cap_failures']} "
            f"upper_bound={item['projected_upper_bound_matches_if_cap_failures_fixed']}/{item['total_rows']}"
        )
    print(f"label_counts={summary['overall']['label_counts']}")
    print(f"recommended_next_task={summary['recommended_next_task']}")


if __name__ == "__main__":
    main()
