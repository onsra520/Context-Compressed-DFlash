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

from scripts.phase_1_system_build_and_evaluation.analysis.t47_quality_refinement import classify_row, normalize_numeric


TASK60_PATHS = {
    "LLMLingua-AR-R2": Path("results/task60_gsm8k_short_llmlingua_ar_r2_n10_mnt256_suffixfix.jsonl"),
    "CC-DFlash-R2": Path("results/task60_gsm8k_short_cc_dflash_r2_n10_mnt256_suffixfix.jsonl"),
}
TASK61B_PATHS = {
    "LLMLingua-AR-R2": Path("results/task61b_gsm8k_short_llmlingua_ar_r2_n10_mnt256_k067.jsonl"),
    "CC-DFlash-R2": Path("results/task61b_gsm8k_short_cc_dflash_r2_n10_mnt256_k067.jsonl"),
}
DEFAULT_CHANGED_OUTCOMES = Path("results/task61b_keep_rate67_changed_outcomes.jsonl")
DEFAULT_DATASET = Path("data/eval/gsm8k_100.jsonl")
DEFAULT_SUMMARY_OUTPUT = Path("results/task62_changed_outcome_triage_summary.json")
DEFAULT_CASES_OUTPUT = Path("results/task62_changed_outcome_cases.jsonl")

TRIAGED_OUTCOMES = {"FAIL_TO_PASS", "PASS_TO_FAIL", "SAME_FAIL"}
FINAL_ANSWER_MARKER_RE = re.compile(
    r"final\s+(?:numeric\s+)?answer\s*(?:is|=|:|：)\s*[-+]?\$?\d[\d,]*(?:\.\d+)?",
    re.IGNORECASE,
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


def _prompt_key(row: dict[str, Any]) -> str:
    for field_name in ("dataset_id", "fixture_id", "benchmark_prompt_index", "prompt_id"):
        value = row.get(field_name)
        if value is not None:
            return str(value)
    return ""


def _index_rows(paths: dict[str, Path]) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        condition: {_prompt_key(row): row for row in load_jsonl(path)}
        for condition, path in paths.items()
    }


def _dataset_index(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    return {str(row.get("id")): row for row in load_jsonl(path) if row.get("id") is not None}


def _compact(text: Any, *, limit: int = 420) -> str:
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


def _has_final_answer_marker(row: dict[str, Any]) -> bool:
    text = row.get("generated_text")
    return isinstance(text, str) and bool(FINAL_ANSWER_MARKER_RE.search(text))


def _preview_text(row: dict[str, Any]) -> str:
    parts = [
        row.get("compressed_prompt_preview"),
        row.get("final_prompt_preview"),
        row.get("final_prompt_tail_preview"),
        row.get("compressed_context_preview"),
    ]
    return "\n".join(str(part) for part in parts if isinstance(part, str))


def _normalized_expected_in_preview(expected: str, preview: str) -> bool:
    normalized = normalize_numeric(expected)
    if normalized is None:
        return bool(expected and expected in preview)
    preview_numbers = {normalize_numeric(match.group(0)) for match in re.finditer(r"[-+]?\$?\d[\d,]*(?:\.\d+)?", preview)}
    return normalized in preview_numbers


def _extract_answer(row: dict[str, Any], *, condition: str, artifact: str) -> dict[str, Any]:
    return classify_row(row, row_index=int(row.get("prompt_id") or 0), condition=condition, artifact=artifact)


def _infer_label(
    *,
    outcome_label: str,
    expected_answer: str,
    before_row: dict[str, Any],
    after_row: dict[str, Any],
    before_classified: dict[str, Any],
    after_classified: dict[str, Any],
) -> tuple[str, str, dict[str, bool]]:
    before_preview = _preview_text(before_row)
    after_preview = _preview_text(after_row)
    before_hit_cap = _hit_cap(before_row)
    after_hit_cap = _hit_cap(after_row)
    before_marker = _has_final_answer_marker(before_row)
    after_marker = _has_final_answer_marker(after_row)
    before_expected_in_preview = _normalized_expected_in_preview(expected_answer, before_preview)
    after_expected_in_preview = _normalized_expected_in_preview(expected_answer, after_preview)

    evidence = {
        "k50_expected_answer_in_preview": before_expected_in_preview,
        "k67_expected_answer_in_preview": after_expected_in_preview,
        "k50_hit_cap": before_hit_cap,
        "k67_hit_cap": after_hit_cap,
        "k50_final_answer_marker": before_marker,
        "k67_final_answer_marker": after_marker,
    }

    if after_hit_cap and not after_classified.get("numeric_match"):
        return "TRUNCATION_REMAINING", "k67 output hit max_new_tokens without a numeric match", evidence

    if outcome_label == "FAIL_TO_PASS":
        if after_expected_in_preview and not before_expected_in_preview:
            return (
                "K67_HELPED_COMPRESSION_LOSS",
                "k67 preview contains the expected numeric answer while k50 preview does not",
                evidence,
            )
        return (
            "UNCLEAR",
            "k67 changed failure to pass, but previews do not directly prove restored critical information",
            evidence,
        )

    if outcome_label == "PASS_TO_FAIL":
        if after_marker and not after_classified.get("numeric_match"):
            return (
                "K67_HURT_BY_EXTRA_CONTEXT_OR_GENERATION_VARIANCE",
                "k67 generated a final-answer marker with the wrong numeric answer after k50 passed",
                evidence,
            )
        if not after_marker:
            return (
                "EXTRACTION_OR_FORMAT_FAIL",
                "k67 did not emit a clear final-answer marker after k50 passed",
                evidence,
            )
        return (
            "UNCLEAR",
            "k67 regressed from pass to fail without enough preview evidence for a specific cause",
            evidence,
        )

    if outcome_label == "SAME_FAIL":
        if before_hit_cap or after_hit_cap:
            return "TRUNCATION_REMAINING", "one or both stages hit the output token cap", evidence
        if before_marker or after_marker:
            return "MODEL_ARITHMETIC_FAIL", "a final-answer marker was present but numeric extraction still failed", evidence
        return "EXTRACTION_OR_FORMAT_FAIL", "neither stage produced an extractable final-answer marker", evidence

    return "UNCLEAR", "outcome label was not in the triage set", evidence


def _case_from_row(
    *,
    changed_row: dict[str, Any],
    before_row: dict[str, Any],
    after_row: dict[str, Any],
    task60_artifact: str,
    task61b_artifact: str,
    dataset_row: dict[str, Any] | None,
) -> dict[str, Any]:
    condition = str(changed_row["condition"])
    outcome_label = str(changed_row["outcome_label"])
    expected_answer = str(after_row.get("expected_answer") or before_row.get("expected_answer") or changed_row.get("expected_answer") or "")
    before_classified = _extract_answer(before_row, condition=condition, artifact=task60_artifact)
    after_classified = _extract_answer(after_row, condition=condition, artifact=task61b_artifact)
    triage_label, rationale, evidence = _infer_label(
        outcome_label=outcome_label,
        expected_answer=expected_answer,
        before_row=before_row,
        after_row=after_row,
        before_classified=before_classified,
        after_classified=after_classified,
    )
    return {
        "condition": condition,
        "dataset_id": changed_row.get("dataset_id") or after_row.get("dataset_id") or before_row.get("dataset_id"),
        "prompt_key": changed_row.get("prompt_key") or _prompt_key(after_row),
        "outcome_label": outcome_label,
        "triage_label": triage_label,
        "triage_rationale": rationale,
        "expected_answer": expected_answer,
        "question": dataset_row.get("question") if dataset_row else after_row.get("question"),
        "k50_extracted_answer": before_classified.get("extracted_answer"),
        "k67_extracted_answer": after_classified.get("extracted_answer"),
        "k50_numeric_match": bool(before_classified.get("numeric_match")),
        "k67_numeric_match": bool(after_classified.get("numeric_match")),
        "k50_final_answer_marker": evidence["k50_final_answer_marker"],
        "k67_final_answer_marker": evidence["k67_final_answer_marker"],
        "k50_hit_cap": evidence["k50_hit_cap"],
        "k67_hit_cap": evidence["k67_hit_cap"],
        "k50_output_tokens": before_row.get("output_tokens"),
        "k67_output_tokens": after_row.get("output_tokens"),
        "k50_original_input_tokens": before_row.get("original_input_tokens"),
        "k67_original_input_tokens": after_row.get("original_input_tokens"),
        "k50_compressed_input_tokens": before_row.get("compressed_input_tokens"),
        "k67_compressed_input_tokens": after_row.get("compressed_input_tokens"),
        "k50_actual_compression_ratio": before_row.get("actual_compression_ratio") or before_row.get("compression_ratio"),
        "k67_actual_compression_ratio": after_row.get("actual_compression_ratio") or after_row.get("compression_ratio"),
        "k50_protected_suffix_preserved": before_row.get("protected_suffix_preserved"),
        "k67_protected_suffix_preserved": after_row.get("protected_suffix_preserved"),
        "k50_final_prompt_tail_preview": _compact(before_row.get("final_prompt_tail_preview")),
        "k67_final_prompt_tail_preview": _compact(after_row.get("final_prompt_tail_preview")),
        "k50_compressed_prompt_preview": _compact(before_row.get("compressed_prompt_preview") or before_row.get("final_prompt_preview")),
        "k67_compressed_prompt_preview": _compact(after_row.get("compressed_prompt_preview") or after_row.get("final_prompt_preview")),
        "k50_generated_text_snippet": _compact(before_row.get("generated_text")),
        "k67_generated_text_snippet": _compact(after_row.get("generated_text")),
        "k67_restored_expected_answer_in_preview": evidence["k67_expected_answer_in_preview"] and not evidence["k50_expected_answer_in_preview"],
    }


def analyze_paths(
    *,
    task60_paths: dict[str, Path] | None = None,
    task61b_paths: dict[str, Path] | None = None,
    changed_outcomes_path: Path | None = None,
    dataset_path: Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    task60_paths = task60_paths or TASK60_PATHS
    task61b_paths = task61b_paths or TASK61B_PATHS
    changed_outcomes_path = changed_outcomes_path or DEFAULT_CHANGED_OUTCOMES
    dataset_path = dataset_path or DEFAULT_DATASET

    before = _index_rows(task60_paths)
    after = _index_rows(task61b_paths)
    dataset = _dataset_index(dataset_path)
    changed_rows = [
        row for row in load_jsonl(changed_outcomes_path)
        if row.get("outcome_label") in TRIAGED_OUTCOMES
    ]

    cases: list[dict[str, Any]] = []
    for changed_row in changed_rows:
        condition = str(changed_row.get("condition"))
        key = str(changed_row.get("prompt_key") or changed_row.get("dataset_id") or "")
        if condition not in before or condition not in after:
            raise ValueError(f"unknown condition in changed outcomes: {condition}")
        if key not in before[condition] or key not in after[condition]:
            raise ValueError(f"missing before/after row for {condition} {key}")
        dataset_id = str(changed_row.get("dataset_id") or key)
        cases.append(
            _case_from_row(
                changed_row=changed_row,
                before_row=before[condition][key],
                after_row=after[condition][key],
                task60_artifact=str(task60_paths[condition]),
                task61b_artifact=str(task61b_paths[condition]),
                dataset_row=dataset.get(dataset_id),
            )
        )

    label_counts = dict(Counter(case["triage_label"] for case in cases))
    outcome_counts = dict(Counter(case["outcome_label"] for case in cases))
    by_condition: dict[str, dict[str, Any]] = {}
    for condition in sorted({case["condition"] for case in cases}):
        condition_cases = [case for case in cases if case["condition"] == condition]
        by_condition[condition] = {
            "cases": len(condition_cases),
            "outcome_counts": dict(Counter(case["outcome_label"] for case in condition_cases)),
            "label_counts": dict(Counter(case["triage_label"] for case in condition_cases)),
            "fail_to_pass_cases": sum(1 for case in condition_cases if case["outcome_label"] == "FAIL_TO_PASS"),
            "pass_to_fail_cases": sum(1 for case in condition_cases if case["outcome_label"] == "PASS_TO_FAIL"),
            "same_fail_cases": sum(1 for case in condition_cases if case["outcome_label"] == "SAME_FAIL"),
            "avg_k50_compressed_input_tokens": _mean([case.get("k50_compressed_input_tokens") for case in condition_cases]),
            "avg_k67_compressed_input_tokens": _mean([case.get("k67_compressed_input_tokens") for case in condition_cases]),
        }

    direct_help = any(case["triage_label"] == "K67_HELPED_COMPRESSION_LOSS" for case in cases)
    instability = any(case["triage_label"] == "K67_HURT_BY_EXTRA_CONTEXT_OR_GENERATION_VARIANCE" for case in cases)
    remaining_truncation = any(case["triage_label"] == "TRUNCATION_REMAINING" for case in cases)
    pass_to_fail_count = outcome_counts.get("PASS_TO_FAIL", 0)
    fail_to_pass_count = outcome_counts.get("FAIL_TO_PASS", 0)

    if direct_help and not instability and pass_to_fail_count == 0:
        recommendation = "Consider a tiny keep_rate_percent=80 run before larger n."
        test_keep_rate_80 = True
        next_n30 = "Defer n=30 until the 80% tiny run is inspected."
    elif pass_to_fail_count or instability:
        recommendation = (
            "Do not test keep_rate_percent=80 yet. Triage the pass-to-fail and same-fail rows first; "
            "if scaling is needed, run n=30 with default keep_rate=50 and optionally keep_rate=67 for confidence intervals."
        )
        test_keep_rate_80 = False
        next_n30 = "Run n=30 only after triage, preferably keep_rate=50 baseline plus optional 67% comparison."
    elif remaining_truncation:
        recommendation = "Do prompt/output triage before more keep-rate changes."
        test_keep_rate_80 = False
        next_n30 = "Defer n=30 until truncation cases are understood."
    else:
        recommendation = "Evidence is unclear; do not test 80 yet."
        test_keep_rate_80 = False
        next_n30 = "If more confidence is needed, n=30 with keep_rate=50 and 67 is more useful than 80."

    summary = {
        "task": "Task 62 compressed GSM8K changed-outcome triage after keep_rate=67",
        "status": "PASS",
        "claim_policy": "read-only triage; no final correctness or compression-loss claim",
        "task61b_commit": _task61b_commit(),
        "inputs": {
            "task60_artifacts": {condition: str(path) for condition, path in task60_paths.items()},
            "task61b_artifacts": {condition: str(path) for condition, path in task61b_paths.items()},
            "changed_outcomes": str(changed_outcomes_path),
            "dataset": str(dataset_path),
        },
        "total_cases": len(cases),
        "outcome_counts": outcome_counts,
        "label_counts": label_counts,
        "by_condition": by_condition,
        "direct_evidence_k67_helped_compression_loss": direct_help,
        "direct_evidence_k67_hurt_or_instability": instability,
        "remaining_truncation": remaining_truncation,
        "test_keep_rate_80_next": test_keep_rate_80,
        "n30_recommendation": next_n30,
        "recommendation": recommendation,
    }
    return summary, cases


def _mean(values: list[Any]) -> float:
    numeric = [float(value) for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
    return statistics.fmean(numeric) if numeric else 0.0


def _task61b_commit() -> str:
    import subprocess

    try:
        return subprocess.check_output(
            ["git", "log", "--format=%h %s", "-1", "--grep", "test: calibrate compressed gsm8k at keep rate 67"],
            text=True,
        ).strip()
    except Exception:
        return ""


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Triage Task 60 vs Task 61B compressed GSM8K changed outcomes")
    parser.add_argument("--summary-output", default=str(DEFAULT_SUMMARY_OUTPUT))
    parser.add_argument("--cases-output", default=str(DEFAULT_CASES_OUTPUT))
    parser.add_argument("--changed-outcomes", default=str(DEFAULT_CHANGED_OUTCOMES))
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    args = parser.parse_args()

    summary, cases = analyze_paths(
        changed_outcomes_path=Path(args.changed_outcomes),
        dataset_path=Path(args.dataset),
    )
    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(Path(args.cases_output), cases)

    print(f"status={summary['status']}")
    print(f"task61b_commit={summary['task61b_commit']}")
    print(f"total_cases={summary['total_cases']}")
    print(f"outcome_counts={summary['outcome_counts']}")
    print(f"label_counts={summary['label_counts']}")
    print(f"test_keep_rate_80_next={summary['test_keep_rate_80_next']}")
    print(f"recommendation={summary['recommendation']}")


if __name__ == "__main__":
    main()
