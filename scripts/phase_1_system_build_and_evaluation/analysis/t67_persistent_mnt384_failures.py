from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_system_build_and_evaluation.analysis.t47_quality_refinement import classify_row, normalize_numeric


TASK66_PATHS = {
    "LLMLingua-AR-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task66_gsm8k_short_llmlingua_ar_r2_n30_mnt384_rerun.jsonl"),
    "CC-DFlash-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task66_gsm8k_short_cc_dflash_r2_n30_mnt384_rerun.jsonl"),
}
DEFAULT_DATASET = Path("data/eval/gsm8k_100.jsonl")
DEFAULT_CHANGED_OUTCOMES = Path("results/phase_1_system_build_and_evaluation/early_experiments/task66_mnt384_rerun_changed_outcomes.jsonl")
DEFAULT_SUMMARY_OUTPUT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task67_persistent_mnt384_failure_summary.json")
DEFAULT_CASES_OUTPUT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task67_persistent_mnt384_failure_cases.jsonl")

NUMBER_RE = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?")
FINAL_ANSWER_MARKER_RE = re.compile(
    r"final\s+(?:numeric\s+)?answer\s*(?:is|=|:|：)\s*[-+]?\$?\d[\d,]*(?:\.\d+)?",
    re.IGNORECASE,
)
FINAL_ANSWER_INSTRUCTION = "Final answer: <number>"
UNFINISHED_HINTS = (
    "let ",
    "we need",
    "we have",
    "so far",
    "first",
    "then",
    "next",
    "step",
    "therefore",
    "remaining",
    "total",
    "=",
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


def _compact(text: Any, *, limit: int = 520) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def hit_token_cap(row: dict[str, Any]) -> bool:
    output_tokens = row.get("output_tokens")
    max_new_tokens = row.get("max_new_tokens")
    return (
        isinstance(output_tokens, (int, float))
        and not isinstance(output_tokens, bool)
        and isinstance(max_new_tokens, (int, float))
        and not isinstance(max_new_tokens, bool)
        and output_tokens >= max_new_tokens
    )


def has_final_answer_marker(text: Any) -> bool:
    return isinstance(text, str) and bool(FINAL_ANSWER_MARKER_RE.search(text))


def _numbers_in_text(text: Any) -> set[str]:
    if not isinstance(text, str):
        return set()
    values: set[str] = set()
    for match in NUMBER_RE.finditer(text):
        normalized = normalize_numeric(match.group(0))
        if normalized is not None:
            values.add(normalized)
    return values


def _expected_appears_in_text(expected_answer: str, text: Any) -> bool:
    expected_numeric = normalize_numeric(expected_answer)
    if expected_numeric is not None:
        return expected_numeric in _numbers_in_text(text)
    return isinstance(text, str) and bool(expected_answer) and expected_answer in text


def _appears_unfinished(text: Any) -> bool:
    if not isinstance(text, str) or not text.strip():
        return True
    stripped = text.strip()
    if stripped.endswith(("=", "+", "-", "*", "/", ":", ",", "and", "the")):
        return True
    tail = stripped[-260:].lower()
    if "final answer" in tail:
        return False
    return any(hint in tail for hint in UNFINISHED_HINTS)


def _prompt_metadata_suggests_compression_loss(row: dict[str, Any]) -> bool:
    if row.get("question_preserved") is False:
        return True
    if row.get("protected_suffix_preserved") is False:
        return True
    final_tail = row.get("final_prompt_tail_preview")
    if isinstance(final_tail, str) and FINAL_ANSWER_INSTRUCTION not in final_tail:
        return True
    return False


def label_failure_case(
    row: dict[str, Any],
    *,
    numeric_match: bool,
    extracted_answer: str | None,
    expected_answer: str,
) -> tuple[str, str]:
    generated_text = row.get("generated_text")
    hit_cap = hit_token_cap(row)
    marker = has_final_answer_marker(generated_text)

    if not numeric_match and hit_cap and (not marker or _appears_unfinished(generated_text)):
        return (
            "TRUNCATION_REMAINING",
            "row hit the max_new_tokens cap and appears unfinished or did not reach a usable final-answer marker",
        )

    if not numeric_match and marker and extracted_answer is not None:
        return (
            "REASONING_FAIL",
            "row produced a final-answer marker, but the extracted numeric answer differs from expected",
        )

    if not numeric_match and _expected_appears_in_text(expected_answer, generated_text):
        return (
            "ANSWER_FORMAT_OR_EXTRACTION_ISSUE",
            "expected numeric answer appears in generated text, but deterministic extraction did not match",
        )

    if not numeric_match and _prompt_metadata_suggests_compression_loss(row):
        return (
            "COMPRESSION_LOSS_POSSIBLE",
            "prompt metadata suggests protected question/suffix or final prompt tail may not have survived compression",
        )

    if not numeric_match and hit_cap:
        return (
            "TRUNCATION_REMAINING",
            "row hit the max_new_tokens cap and numeric extraction failed",
        )

    return "UNCLEAR", "insufficient evidence for a more specific label"


def _case_row(
    *,
    condition: str,
    artifact: str,
    row: dict[str, Any],
    classified: dict[str, Any],
    dataset_row: dict[str, Any] | None,
) -> dict[str, Any]:
    expected_answer = str(row.get("expected_answer") or classified.get("expected_answer") or "")
    numeric_match = bool(classified.get("numeric_match"))
    label: str | None = None
    rationale: str | None = None
    if not numeric_match:
        label, rationale = label_failure_case(
            row,
            numeric_match=numeric_match,
            extracted_answer=classified.get("extracted_answer"),
            expected_answer=expected_answer,
        )

    return {
        "condition": condition,
        "artifact": artifact,
        "prompt_id": row.get("prompt_id"),
        "benchmark_prompt_index": row.get("benchmark_prompt_index"),
        "dataset_id": row.get("dataset_id") or row.get("fixture_id"),
        "expected_answer": expected_answer,
        "extracted_answer": classified.get("extracted_answer"),
        "numeric_match": numeric_match,
        "exact_match": bool(classified.get("exact_match")),
        "hit_cap": hit_token_cap(row),
        "output_tokens": row.get("output_tokens"),
        "max_new_tokens": row.get("max_new_tokens"),
        "final_answer_marker": has_final_answer_marker(row.get("generated_text")),
        "answer_appears_in_text": _expected_appears_in_text(expected_answer, row.get("generated_text")),
        "failure_label": label,
        "label_rationale": rationale,
        "protected_suffix_preserved": row.get("protected_suffix_preserved"),
        "question_preserved": row.get("question_preserved"),
        "keep_rate": row.get("keep_rate"),
        "actual_compression_ratio": row.get("actual_compression_ratio") or row.get("compression_ratio") or row.get("R_actual"),
        "original_input_tokens": row.get("original_input_tokens"),
        "compressed_input_tokens": row.get("compressed_input_tokens"),
        "dataset_question": _compact(dataset_row.get("question") if dataset_row else "", limit=260),
        "final_prompt_tail_preview": _compact(row.get("final_prompt_tail_preview"), limit=360),
        "compressed_prompt_preview": _compact(row.get("compressed_prompt_preview") or row.get("compressed_context_preview"), limit=420),
        "generated_text_snippet": _compact(row.get("generated_text"), limit=620),
    }


def summarize_condition_rows(
    *,
    condition: str,
    artifact: str,
    rows: list[dict[str, Any]],
    dataset: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    dataset = dataset or {}
    cases: list[dict[str, Any]] = []
    numeric_matches = 0
    exact_matches = 0
    cap_hits = 0
    cap_hit_failures = 0
    non_cap_failures = 0
    marker_count = 0
    protected_suffix_count = 0
    question_preserved_count = 0

    for row_index, row in enumerate(rows, start=1):
        classified = classify_row(row, row_index=row_index, condition=condition, artifact=artifact)
        numeric_match = bool(classified.get("numeric_match"))
        exact_match = bool(classified.get("exact_match"))
        hit_cap = hit_token_cap(row)
        numeric_matches += int(numeric_match)
        exact_matches += int(exact_match)
        cap_hits += int(hit_cap)
        marker_count += int(has_final_answer_marker(row.get("generated_text")))
        protected_suffix_count += int(row.get("protected_suffix_preserved") is True)
        question_preserved_count += int(row.get("question_preserved") is True)
        if hit_cap and not numeric_match:
            cap_hit_failures += 1
        if not hit_cap and not numeric_match:
            non_cap_failures += 1
        if hit_cap or not numeric_match:
            dataset_id = str(row.get("dataset_id") or row.get("fixture_id") or "")
            cases.append(
                _case_row(
                    condition=condition,
                    artifact=artifact,
                    row=row,
                    classified=classified,
                    dataset_row=dataset.get(dataset_id),
                )
            )

    failure_cases = [case for case in cases if case.get("numeric_match") is False]
    total_rows = len(rows)
    label_counts = dict(sorted(Counter(case["failure_label"] for case in failure_cases).items()))
    summary = {
        "condition": condition,
        "artifact": artifact,
        "rows": total_rows,
        "numeric_matches": numeric_matches,
        "numeric_match_rate": round(numeric_matches / total_rows, 6) if total_rows else 0.0,
        "numeric_failures": total_rows - numeric_matches,
        "exact_matches": exact_matches,
        "exact_match_rate": round(exact_matches / total_rows, 6) if total_rows else 0.0,
        "final_answer_marker_count": marker_count,
        "cap_hits": cap_hits,
        "cap_hit_failures": cap_hit_failures,
        "non_cap_failures": non_cap_failures,
        "cap_hit_numeric_matches": cap_hits - cap_hit_failures,
        "protected_suffix_preserved_count": protected_suffix_count,
        "question_preserved_count": question_preserved_count,
        "failure_case_count": len(failure_cases),
        "attention_case_count": len(cases),
        "label_counts": label_counts,
    }
    return summary, cases


def _decision(summary: dict[str, Any]) -> dict[str, Any]:
    labels = Counter(summary["overall"]["label_counts"])
    truncation = labels.get("TRUNCATION_REMAINING", 0)
    reasoning = labels.get("REASONING_FAIL", 0)
    extraction = labels.get("ANSWER_FORMAT_OR_EXTRACTION_ISSUE", 0)
    compression = labels.get("COMPRESSION_LOSS_POSSIBLE", 0)
    unclear = labels.get("UNCLEAR", 0)
    total_failures = sum(labels.values())

    if extraction:
        mnt512 = "NOT_YET"
        n100 = "NOT_YET"
        recommendation = "Fix extraction or prompt formatting before any larger benchmark."
    elif compression:
        mnt512 = "NOT_YET"
        n100 = "NOT_YET"
        recommendation = "Inspect compressed prompt previews before changing token budget or keep_rate."
    elif truncation > reasoning and truncation >= max(1, total_failures // 2):
        mnt512 = "JUSTIFIED_TINY_TARGETED_CALIBRATION"
        n100 = "NOT_YET"
        recommendation = "Run only a tiny mnt512 targeted calibration before n=100."
    elif reasoning >= truncation:
        mnt512 = "NOT_JUSTIFIED"
        n100 = "CONDITIONALLY_JUSTIFIED_AFTER_REPORT_SYNTHESIS"
        recommendation = "Treat remaining failures as mostly model/reasoning limits; use mnt384 for quality setting and mnt256 for speed-oriented setting."
    else:
        mnt512 = "NOT_JUSTIFIED"
        n100 = "NOT_YET"
        recommendation = "Remaining failures are mixed; synthesize failure evidence before expanding."

    return {
        "mnt512_justification": mnt512,
        "n100_justification": n100,
        "speed_oriented_setting": "max_new_tokens=256, keep_rate=0.50, protected final-answer suffix",
        "quality_oriented_setting": "max_new_tokens=384, keep_rate=0.50, protected final-answer suffix",
        "recommendation": recommendation,
        "remaining_failures_look_like": (
            "model/reasoning limit" if reasoning >= truncation and not extraction and not compression else "mixed or token-budget limited"
        ),
    }


def analyze_paths(
    *,
    artifact_paths: dict[str, Path] | None = None,
    dataset_path: Path | None = None,
    changed_outcomes_path: Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    artifact_paths = artifact_paths or TASK66_PATHS
    dataset_path = dataset_path or DEFAULT_DATASET
    changed_outcomes_path = changed_outcomes_path or DEFAULT_CHANGED_OUTCOMES
    dataset = _dataset_index(dataset_path)

    by_condition: dict[str, dict[str, Any]] = {}
    cases: list[dict[str, Any]] = []
    for condition, artifact in artifact_paths.items():
        rows = load_jsonl(artifact)
        condition_summary, condition_cases = summarize_condition_rows(
            condition=condition,
            artifact=str(artifact),
            rows=rows,
            dataset=dataset,
        )
        by_condition[condition] = condition_summary
        cases.extend(condition_cases)

    failure_cases = [case for case in cases if case.get("numeric_match") is False]
    label_counts = dict(sorted(Counter(case["failure_label"] for case in failure_cases).items()))
    total_cap_hit_failures = sum(item["cap_hit_failures"] for item in by_condition.values())
    total_non_cap_failures = sum(item["non_cap_failures"] for item in by_condition.values())
    changed_counts: dict[str, int] = {}
    if changed_outcomes_path.exists():
        changed_counts = dict(sorted(Counter(row.get("outcome_label") for row in load_jsonl(changed_outcomes_path)).items()))

    summary = {
        "task": "Task 67 read-only triage of persistent mnt384 GSM8K compressed failures",
        "status": "PASS",
        "claim_policy": "read-only artifact analysis; no benchmark execution and no final correctness claim",
        "inputs": {
            "artifacts": {condition: str(path) for condition, path in artifact_paths.items()},
            "dataset": str(dataset_path),
            "changed_outcomes": str(changed_outcomes_path),
        },
        "by_condition": by_condition,
        "overall": {
            "total_failure_cases": len(failure_cases),
            "total_attention_cases": len(cases),
            "label_counts": label_counts,
            "total_cap_hit_failures": total_cap_hit_failures,
            "total_non_cap_failures": total_non_cap_failures,
            "task66_changed_outcome_counts": changed_counts,
        },
    }
    summary["decision"] = _decision(summary)
    return summary, cases


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze persistent Task 66 mnt384 compressed GSM8K failures")
    parser.add_argument("--summary-output", default=str(DEFAULT_SUMMARY_OUTPUT))
    parser.add_argument("--cases-output", default=str(DEFAULT_CASES_OUTPUT))
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--changed-outcomes", default=str(DEFAULT_CHANGED_OUTCOMES))
    args = parser.parse_args()

    summary, cases = analyze_paths(
        dataset_path=Path(args.dataset),
        changed_outcomes_path=Path(args.changed_outcomes),
    )
    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(Path(args.cases_output), cases)

    print(f"status={summary['status']}")
    for condition, item in summary["by_condition"].items():
        print(
            f"{condition}: rows={item['rows']} numeric={item['numeric_matches']}/{item['rows']} "
            f"failures={item['numeric_failures']} cap_hits={item['cap_hits']} "
            f"cap_hit_failures={item['cap_hit_failures']} non_cap_failures={item['non_cap_failures']} "
            f"labels={item['label_counts']}"
        )
    print(f"overall_labels={summary['overall']['label_counts']}")
    print(f"mnt512={summary['decision']['mnt512_justification']}")
    print(f"n100={summary['decision']['n100_justification']}")
    print(f"recommendation={summary['decision']['recommendation']}")


if __name__ == "__main__":
    main()
