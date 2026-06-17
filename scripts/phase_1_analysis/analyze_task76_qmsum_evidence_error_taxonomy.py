from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_analysis.analyze_task70_qmsum_diagnostic_audit import load_jsonl
from scripts.phase_1_analysis.analyze_task74_qmsum_proxy_case_triage import lexical_diagnostics

DEFAULT_CASE_INPUT = Path("results/task75_qmsum_balanced_policy_cases.jsonl")
DEFAULT_SUMMARY_OUTPUT = Path("results/task76_qmsum_evidence_error_summary.json")
DEFAULT_TABLE_OUTPUT = Path("results/task76_qmsum_evidence_error_table.csv")
DEFAULT_CASES_OUTPUT = Path("results/task76_qmsum_evidence_error_cases.jsonl")

STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "answer",
    "because",
    "been",
    "being",
    "between",
    "could",
    "decision",
    "details",
    "discussion",
    "does",
    "during",
    "from",
    "have",
    "meeting",
    "not",
    "that",
    "their",
    "there",
    "they",
    "this",
    "were",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
}
NOISY_ENTITY_WORDS = {
    "Also",
    "Although",
    "And",
    "As",
    "By",
    "Additionally",
    "Firstly",
    "He",
    "In",
    "Let",
    "Many",
    "Over",
    "Plus",
    "She",
    "So",
    "That",
    "The",
    "They",
    "Therefore",
    "This",
    "Using",
}
ENTITY_RE = re.compile(
    r"\b(?:COVID-19|[A-Z][A-Z0-9]{1,}(?:-[A-Z0-9]+)*|\d+(?:[.,]\d+)*(?:M|GB|MB|ms|%)?|[A-Z][a-z]+)\b"
)
WORD_RE = re.compile(r"[a-z0-9]+")
WRONG_NEGATIVE_RE = re.compile(
    r"\b(not (?:mentioned|discussed|provided|specified|directly addressed|clear)|"
    r"no (?:specific |direct )?(?:mention|evidence|information|support|intervention)|"
    r"no (?:direct |government |specific |clear )?[a-z\s]{0,40}?(?:support|intervention)|"
    r"does not (?:mention|provide|specify|state|address)|"
    r"cannot be determined|not available)\b",
    re.IGNORECASE,
)
NUMBER_PHRASE_RE = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)\s+"
    r"(?:million|billion|thousand|hundred)\b",
    re.IGNORECASE,
)


def _tokens(text: Any) -> list[str]:
    if not isinstance(text, str):
        return []
    return WORD_RE.findall(text.lower())


def _keywords(text: Any) -> set[str]:
    return {token for token in _tokens(text) if len(token) > 2 and token not in STOPWORDS}


def _entities_and_numbers(text: Any) -> list[str]:
    if not isinstance(text, str):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for match in NUMBER_PHRASE_RE.finditer(text):
        value = match.group(0).strip()
        key = value.lower()
        if key not in seen:
            seen.add(key)
            result.append(value)
    for match in ENTITY_RE.finditer(text):
        value = match.group(0).strip()
        if not value or value in NOISY_ENTITY_WORDS or value.lower() in STOPWORDS:
            continue
        key = value.lower()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _missing_entities_or_numbers(expected: str, generated: str) -> list[str]:
    generated_lower = generated.lower()
    missing: list[str] = []
    for item in _entities_and_numbers(expected):
        item_lower = item.lower()
        if item_lower not in generated_lower:
            missing.append(item)
    return missing


def _compact(text: Any, limit: int = 420) -> str:
    if not isinstance(text, str):
        return ""
    clean = " ".join(text.split())
    return clean[:limit] + ("..." if len(clean) > limit else "")


def _numeric(row: dict[str, Any], field: str) -> float:
    value = row.get(field)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _case_diagnostics(row: dict[str, Any]) -> dict[str, float]:
    diagnostics = row.get("balanced_diagnostics")
    if isinstance(diagnostics, dict):
        return {
            "balanced_overlap": float(diagnostics.get("unigram_overlap", 0.0) or 0.0),
            "keyword_overlap": float(diagnostics.get("keyword_overlap", 0.0) or 0.0),
            "numeric_entity_overlap": float(diagnostics.get("numeric_entity_overlap", 0.0) or 0.0),
            "reference_answer_coverage": float(diagnostics.get("reference_answer_coverage", 0.0) or 0.0),
        }
    generated = str(row.get("balanced_generated_snippet") or row.get("generated_text") or "")
    expected = str(row.get("expected_answer") or "")
    computed = lexical_diagnostics(expected, generated)
    return {
        "balanced_overlap": computed["unigram_overlap"],
        "keyword_overlap": computed["keyword_overlap"],
        "numeric_entity_overlap": computed["numeric_entity_overlap"],
        "reference_answer_coverage": computed["reference_answer_coverage"],
    }


def classify_case(row: dict[str, Any]) -> dict[str, Any]:
    expected = str(row.get("expected_answer") or "")
    generated = str(row.get("balanced_generated_snippet") or row.get("generated_text") or "")
    original_label = str(row.get("label") or row.get("original_task75_label") or "")
    diagnostics = _case_diagnostics(row)
    expected_keywords = _keywords(expected)
    generated_keywords = _keywords(generated)
    raw_keyword_overlap = len(expected_keywords & generated_keywords) / len(expected_keywords) if expected_keywords else 0.0
    missing = _missing_entities_or_numbers(expected, generated)
    wrong_negative = bool(WRONG_NEGATIVE_RE.search(generated) and expected_keywords)
    evidence_misfocused = False

    keyword_overlap = diagnostics["keyword_overlap"]
    overlap = diagnostics["balanced_overlap"]
    entity_overlap = diagnostics["numeric_entity_overlap"]
    reference_coverage = diagnostics["reference_answer_coverage"]
    generated_token_count = len(_tokens(generated))
    expected_token_count = len(_tokens(expected))
    length_ratio = generated_token_count / expected_token_count if expected_token_count else 0.0

    if wrong_negative:
        label = "WRONG_NEGATIVE"
        rationale = "Generated answer says the information is missing or not discussed despite concrete expected evidence."
    elif raw_keyword_overlap < 0.22 or (keyword_overlap < 0.20 and overlap < 0.22):
        label = "EVIDENCE_MISSING_OR_MISFOCUSED"
        evidence_misfocused = True
        rationale = "Generated answer focuses on a different or generic meeting topic rather than the expected evidence."
    elif missing and (entity_overlap < 0.75 or len(missing) >= 2):
        label = "MISSING_ENTITY_OR_NUMBER"
        rationale = "Generated answer is on topic but omits expected names, numbers, or concrete entities."
    elif keyword_overlap >= 0.50 and reference_coverage >= 0.45 and not missing:
        label = "ACCEPTABLE_EVIDENCE_FOCUSED_ANSWER"
        rationale = "Generated answer covers the expected evidence with key details present."
    elif keyword_overlap < 0.35 and reference_coverage < 0.35:
        label = "ANSWER_TOO_GENERAL"
        rationale = "Generated answer is broadly on topic but lacks concrete support from the expected answer."
    elif length_ratio < 0.55 or original_label == "STILL_TOO_SHORT":
        label = "STILL_TOO_SHORT"
        rationale = "Generated answer is on the right evidence path but remains too brief for expected details."
    elif original_label == "PROXY_WEAKNESS" or (keyword_overlap >= 0.45 and overlap < 0.28 and reference_coverage >= 0.30):
        label = "PROXY_WEAKNESS"
        rationale = "Generated answer appears semantically plausible while lexical overlap remains limited."
    elif "compression" in original_label.lower() and keyword_overlap < 0.30:
        label = "POSSIBLE_COMPRESSION_EVIDENCE_LOSS"
        rationale = "Available snippets suggest answer-relevant evidence may have been lost, but this remains conservative."
    else:
        label = "UNCLEAR"
        rationale = "Available snippets and lexical diagnostics are insufficient for a stronger label."

    return {
        "condition": row.get("condition"),
        "prompt_id": row.get("prompt_id"),
        "fixture_id": row.get("fixture_id"),
        "expected_answer": _compact(expected, 520),
        "balanced_generated_snippet": _compact(generated, 520),
        "original_task75_label": original_label,
        "evidence_error_label": label,
        "short_rationale": rationale,
        "missing_entities_or_numbers": missing,
        "wrong_negative": wrong_negative,
        "evidence_misfocused": evidence_misfocused,
        "balanced_overlap": round(overlap, 6),
        "keyword_overlap": round(keyword_overlap, 6),
        "numeric_entity_overlap": round(entity_overlap, 6),
        "reference_answer_coverage": round(reference_coverage, 6),
        "balanced_output_tokens": row.get("balanced_output_tokens", row.get("output_tokens")),
        "balanced_e2e_latency_s": row.get("balanced_e2e_latency_s"),
        "balanced_hit_cap": bool(row.get("balanced_hit_cap", False)),
        "qmsum_answer_policy_preserved": row.get("qmsum_answer_policy_preserved"),
    }


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _condition_summary(condition: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    labels = Counter(case["evidence_error_label"] for case in cases)
    old_labels = Counter(case["original_task75_label"] for case in cases)
    return {
        "condition": condition,
        "rows": len(cases),
        "original_task75_label_counts": dict(sorted(old_labels.items())),
        "evidence_error_label_counts": dict(sorted(labels.items())),
        "cap_hits": sum(1 for case in cases if case["balanced_hit_cap"]),
        "policy_preservation_rate": round(
            sum(1 for case in cases if case.get("qmsum_answer_policy_preserved") is True) / len(cases),
            6,
        )
        if cases
        else 0.0,
        "avg_balanced_overlap": round(_mean([case["balanced_overlap"] for case in cases]), 6),
        "avg_balanced_output_tokens": round(_mean([_numeric(case, "balanced_output_tokens") for case in cases]), 6),
        "avg_balanced_e2e_latency_s": round(_mean([_numeric(case, "balanced_e2e_latency_s") for case in cases]), 6),
        "avg_keyword_overlap": round(_mean([case["keyword_overlap"] for case in cases]), 6),
        "avg_numeric_entity_overlap": round(_mean([case["numeric_entity_overlap"] for case in cases]), 6),
        "avg_reference_answer_coverage": round(_mean([case["reference_answer_coverage"] for case in cases]), 6),
        "wrong_negative_count": labels["WRONG_NEGATIVE"],
        "missing_entity_or_number_count": labels["MISSING_ENTITY_OR_NUMBER"],
        "evidence_misfocused_count": labels["EVIDENCE_MISSING_OR_MISFOCUSED"],
        "acceptable_count": labels["ACCEPTABLE_EVIDENCE_FOCUSED_ANSWER"],
    }


def _prompt_label_map(cases: list[dict[str, Any]]) -> dict[int, dict[str, str]]:
    result: dict[int, dict[str, str]] = defaultdict(dict)
    for case in cases:
        prompt_id = case.get("prompt_id")
        condition = case.get("condition")
        if isinstance(prompt_id, int) and condition:
            result[prompt_id][str(condition)] = str(case["evidence_error_label"])
    return result


def _prompt_ids_for_labels(cases: list[dict[str, Any]], labels: set[str]) -> list[int]:
    values = {
        case["prompt_id"]
        for case in cases
        if case.get("evidence_error_label") in labels and isinstance(case.get("prompt_id"), int)
    }
    return sorted(values)


def analyze_evidence_errors(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    cases = [classify_case(row) for row in rows]
    by_condition_cases: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_condition_cases[str(case.get("condition"))].append(case)

    table = [_condition_summary(condition, items) for condition, items in sorted(by_condition_cases.items())]
    label_counts = Counter(case["evidence_error_label"] for case in cases)
    old_label_counts = Counter(case["original_task75_label"] for case in cases)

    prompt_labels = _prompt_label_map(cases)
    shared_same: dict[str, list[int]] = defaultdict(list)
    one_condition_only: list[int] = []
    for prompt_id, labels_by_condition in sorted(prompt_labels.items()):
        if len(labels_by_condition) < 2:
            one_condition_only.append(prompt_id)
            continue
        labels = set(labels_by_condition.values())
        if len(labels) == 1:
            shared_same[next(iter(labels))].append(prompt_id)

    summary = {
        "task": "76-qmsum-evidence-error-taxonomy",
        "status": "PASS_WITH_NOTES",
        "total_rows": len(cases),
        "old_task75_label_counts": dict(sorted(old_label_counts.items())),
        "total_label_counts": dict(sorted(label_counts.items())),
        "by_condition": {row["condition"]: row for row in table},
        "shared_prompt_ids_same_label": dict(sorted(shared_same.items())),
        "one_condition_only_prompt_ids": one_condition_only,
        "worst_prompt_ids_by_evidence_error": _prompt_ids_for_labels(
            cases, {"EVIDENCE_MISSING_OR_MISFOCUSED", "WRONG_NEGATIVE", "MISSING_ENTITY_OR_NUMBER"}
        ),
        "acceptable_prompt_ids": _prompt_ids_for_labels(cases, {"ACCEPTABLE_EVIDENCE_FOCUSED_ANSWER"}),
        "proxy_weakness_prompt_ids": _prompt_ids_for_labels(cases, {"PROXY_WEAKNESS"}),
        "decisions": {
            "run_mnt512_next": False,
            "qmsum_n100_justified": False,
            "freeze_balanced_policy": False,
            "recommend_next_task": "Task 77 evidence-focused QMSum protected-suffix calibration",
            "reason": (
                "Task 75 cap hits are zero, but evidence-error taxonomy still shows evidence targeting and "
                "answer completeness issues under lexical proxy diagnostics."
            ),
        },
        "claim_policy": "read-only lexical/sample-level taxonomy; no final semantic correctness or speedup claim",
    }
    return summary, table, cases


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 76 QMSum evidence-error taxonomy")
    parser.add_argument("--input", type=Path, default=DEFAULT_CASE_INPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--table-output", type=Path, default=DEFAULT_TABLE_OUTPUT)
    parser.add_argument("--cases-output", type=Path, default=DEFAULT_CASES_OUTPUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    summary, table, cases = analyze_evidence_errors(rows)
    _write_json(args.summary_output, summary)
    _write_csv(args.table_output, table)
    _write_jsonl(args.cases_output, cases)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "total_rows": summary["total_rows"],
                "label_counts": summary["total_label_counts"],
                "qmsum_n100_justified": summary["decisions"]["qmsum_n100_justified"],
                "run_mnt512_next": summary["decisions"]["run_mnt512_next"],
                "summary_output": str(args.summary_output),
                "table_output": str(args.table_output),
                "cases_output": str(args.cases_output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
