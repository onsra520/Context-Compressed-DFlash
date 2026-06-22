from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from pathlib import Path
from typing import Any

TARGET_FIXTURE_IDS = (
    "qmsum_meeting_qa_test_0036",
    "qmsum_meeting_qa_test_0070",
    "qmsum_meeting_qa_test_0055",
    "qmsum_meeting_qa_test_0078",
    "qmsum_meeting_qa_test_0094",
    "qmsum_meeting_qa_test_0001",
)

DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102i_qmsum_baseline_ar_target_row_mini_check"
)
DEFAULT_TARGET_DATASET = Path("data/eval/qmsum_meeting_qa_target_rows_task102f.jsonl")
DEFAULT_ORIGINAL_CC_JSONL = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102_qmsum_light_gpu_n30_feasibility_run/runs/"
    "20260622_151200_cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl"
)
DEFAULT_REMEDIATED_CC_JSONL = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102g_qmsum_target_row_remediation_rerun/runs/"
    "20260622_235012_cc_dflash_r2_light_gpu_qmsum_target_rows_n6_mnt384.jsonl"
)
DEFAULT_TASK102H_ASSESSMENT = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102h_qmsum_remediation_reassessment/"
    "task102h_before_after_row_assessment.jsonl"
)

OUTPUT_RELATIVE_PATHS = (
    Path("summary/task102i_baseline_ar_mini_check_summary.json"),
    Path("summary/task102i_baseline_vs_cc_row_assessment.jsonl"),
    Path("summary/task102i_baseline_ar_row_labels.jsonl"),
    Path("summary/task102i_claim_interpretation.json"),
    Path("summary/task102i_next_task_decision.json"),
    Path("tables/task102i_baseline_vs_cc_table.csv"),
)

LEAKAGE_FIELDS = {
    "generated_text",
    "generated_output",
    "model_answer",
    "generated_answer",
    "prediction",
    "response",
    "output",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "might",
    "not",
    "of",
    "on",
    "only",
    "or",
    "she",
    "should",
    "so",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "to",
    "use",
    "used",
    "using",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "will",
    "with",
    "would",
    "you",
}

GENERIC_PATTERNS = (
    r"\bnot (?:mentioned|discussed|provided|available|specified|clear)\b",
    r"\bdoes not (?:mention|provide|discuss|contain)\b",
    r"\bno evidence\b",
    r"\bno information\b",
    r"\bcannot determine\b",
    r"\bnot enough information\b",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_number} is not a JSON object")
        rows.append(payload)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _fixture_id(row: dict[str, Any]) -> str:
    return str(row.get("fixture_id") or row.get("dataset_id") or row.get("id") or "")


def _index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_fixture_id(row): row for row in rows if _fixture_id(row)}


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def _number(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _round(value: float | None) -> float | None:
    return None if value is None else round(float(value), 6)


def _tokens(text: Any) -> list[str]:
    raw = re.findall(r"[A-Za-z0-9]+", str(text or "").lower())
    return [token for token in raw if token not in STOPWORDS and len(token) > 1]


def _bigrams(tokens: list[str]) -> set[tuple[str, str]]:
    return set(zip(tokens, tokens[1:]))


def _safe_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _has_generic_phrase(text: Any) -> bool:
    lowered = str(text or "").lower()
    return any(re.search(pattern, lowered) for pattern in GENERIC_PATTERNS)


def _entity_number_terms(text: Any) -> set[str]:
    source = str(text or "")
    terms = set(re.findall(r"\b[A-Z][A-Za-z0-9-]*\b|\b[A-Z]{2,}\b|\b\d+(?:\.\d+)?\b", source))
    return {term.lower() for term in terms if term.lower() not in STOPWORDS}


def proxy_metrics(*, output: str, reference: str, question: str, source: str) -> dict[str, Any]:
    output_tokens = _tokens(output)
    reference_tokens = _tokens(reference)
    question_tokens = _tokens(question)
    source_tokens = _tokens(source)
    output_set = set(output_tokens)
    reference_set = set(reference_tokens)
    question_set = set(question_tokens)
    source_set = set(source_tokens)
    reference_bigrams = _bigrams(reference_tokens)
    reference_entities = _entity_number_terms(reference)
    output_entities = _entity_number_terms(output)
    reference_overlap = _safe_ratio(len(output_set & reference_set), len(reference_set))
    return {
        "reference_overlap": _round(reference_overlap),
        "reference_bigram_overlap": _round(_safe_ratio(len(_bigrams(output_tokens) & reference_bigrams), len(reference_bigrams))),
        "reference_f1": _round(_safe_ratio(2 * len(output_set & reference_set), len(output_set) + len(reference_set))),
        "question_focus_overlap": _round(_safe_ratio(len(output_set & question_set), len(question_set))),
        "source_grounding_overlap": _round(_safe_ratio(len(output_set & source_set), len(output_set))),
        "entity_number_overlap": _round(_safe_ratio(len(reference_entities & output_entities), len(reference_entities))),
        "output_content_terms": len(output_set),
        "generic_flag": _has_generic_phrase(output),
        "empty_or_malformed": not bool(str(output or "").strip()),
    }


def _resolved(metrics: dict[str, Any]) -> bool:
    return (
        float(metrics.get("reference_overlap") or 0.0) >= 0.45
        and float(metrics.get("reference_bigram_overlap") or 0.0) >= 0.20
        and not bool(metrics.get("generic_flag"))
    )


def classify_row(
    *,
    baseline_metrics: dict[str, Any],
    original_metrics: dict[str, Any],
    remediated_metrics: dict[str, Any],
) -> str:
    baseline_resolved = _resolved(baseline_metrics)
    cc_resolved = _resolved(original_metrics) or _resolved(remediated_metrics)
    best_cc_reference = max(float(original_metrics.get("reference_overlap") or 0.0), float(remediated_metrics.get("reference_overlap") or 0.0))
    baseline_reference = float(baseline_metrics.get("reference_overlap") or 0.0)
    baseline_grounding = float(baseline_metrics.get("source_grounding_overlap") or 0.0)
    if baseline_resolved and not cc_resolved and best_cc_reference < 0.25:
        return "compression_path_specific_risk"
    if baseline_resolved:
        return "baseline_resolves_proxy_supported"
    if baseline_reference >= best_cc_reference + 0.10 and baseline_reference >= 0.20 and not baseline_metrics.get("generic_flag"):
        return "baseline_clearly_better_but_not_resolved"
    if baseline_reference < 0.18 or baseline_metrics.get("generic_flag") or baseline_metrics.get("empty_or_malformed"):
        return "baseline_also_fails_or_uncertain"
    if baseline_grounding < 0.08:
        return "proxy_or_reference_limitation_persists"
    return "proxy_or_reference_limitation_persists"


def _next_task_decision(interpretation: str) -> dict[str, Any]:
    if interpretation == "TARGET_MODEL_OR_QMSUM_GROUNDING_LIMITATION_SUPPORTED":
        return {
            "next_task": "T102J — QMSum Residual Risk Stop-or-Judge Decision",
            "recommended_path": "accept residual caveat and unblock T103 if the user agrees",
            "reason": "Baseline-AR also fails or remains uncertain on most target rows, consistent with target-model/QMSum grounding or proxy limitations rather than only compression.",
        }
    if interpretation == "COMPRESSION_PATH_SPECIFIC_QMSUM_RISK_SUPPORTED":
        return {
            "next_task": "T102J — QMSum Residual Risk Stop-or-Judge Decision",
            "recommended_path": "keep a stronger QMSum compression-quality caveat before T103",
            "reason": "Baseline-AR resolves or strongly improves most rows that CC-DFlash failed.",
        }
    return {
        "next_task": "T102J — QMSum Residual Risk Stop-or-Judge Decision",
        "recommended_path": "accept residual caveat only if the user agrees; otherwise semantic review would be required",
        "reason": "Baseline-AR signal is mixed across the six target rows.",
    }


def interpret_categories(categories: list[str]) -> dict[str, Any]:
    target_model_like = sum(
        1 for category in categories if category in {"baseline_also_fails_or_uncertain", "proxy_or_reference_limitation_persists"}
    )
    compression_like = sum(
        1 for category in categories if category in {"compression_path_specific_risk", "baseline_resolves_proxy_supported"}
    )
    if target_model_like >= 4:
        interpretation = "TARGET_MODEL_OR_QMSUM_GROUNDING_LIMITATION_SUPPORTED"
        meaning = (
            "Residual QMSum failures are consistent with local target-model evidence locating / grounding limitations "
            "and/or QMSum source-reference/proxy limitations, not only CC-DFlash compression."
        )
    elif compression_like >= 4:
        interpretation = "COMPRESSION_PATH_SPECIFIC_QMSUM_RISK_SUPPORTED"
        meaning = "Residual QMSum risk is stronger evidence against compressed CC-DFlash context quality."
    else:
        interpretation = "MIXED_BASELINE_SIGNAL"
        meaning = "Some risk appears target-model/proxy related, while some may be compression-path specific."
    return {
        "interpretation": interpretation,
        "meaning": meaning,
        "category_counts": {category: categories.count(category) for category in sorted(set(categories))},
        "next_task_decision": _next_task_decision(interpretation),
    }


def validate_target_dataset(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    errors: list[str] = []
    ids = [_fixture_id(row) for row in rows]
    if len(rows) != len(TARGET_FIXTURE_IDS):
        errors.append(f"expected 6 rows, found {len(rows)}")
    if set(ids) != set(TARGET_FIXTURE_IDS):
        errors.append(f"fixture id mismatch: {sorted(set(ids))}")
    if len(ids) != len(set(ids)):
        errors.append("duplicate fixture_id found")
    for row in rows:
        missing = [field for field in ("context", "question", "expected_answer") if not str(row.get(field) or "").strip()]
        if missing:
            errors.append(f"{_fixture_id(row)} missing required fields: {missing}")
        leaked = sorted(LEAKAGE_FIELDS & set(row))
        if leaked:
            errors.append(f"{_fixture_id(row)} generated-output fields present: {leaked}")
    return {"valid": not errors, "errors": errors, "row_count": len(rows), "fixture_ids": ids}


def audit_baseline_run(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    ids = [_fixture_id(row) for row in rows]
    if len(rows) != len(TARGET_FIXTURE_IDS):
        errors.append(f"expected 6 result rows, found {len(rows)}")
    if set(ids) != set(TARGET_FIXTURE_IDS):
        errors.append(f"fixture id mismatch: {sorted(set(ids))}")
    for row in rows:
        prefix = _fixture_id(row)
        if row.get("condition") != "Baseline-AR":
            errors.append(f"{prefix}: condition={row.get('condition')!r}")
        if str(row.get("compression", "none")) not in {"none", ""}:
            errors.append(f"{prefix}: compression unexpectedly active: {row.get('compression')!r}")
        if row.get("draft_used") not in {False, None}:
            errors.append(f"{prefix}: draft_used={row.get('draft_used')!r}")
        if _boolish(row.get("qmsum_policy_suffix_override")) is not True:
            errors.append(f"{prefix}: qmsum_policy_suffix_override={row.get('qmsum_policy_suffix_override')!r}")
        if row.get("qmsum_answer_policy_type") != "qmsum_targeted_evidence_repair_v1":
            errors.append(f"{prefix}: qmsum_answer_policy_type={row.get('qmsum_answer_policy_type')!r}")
        if not str(row.get("generated_text") or "").strip():
            errors.append(f"{prefix}: empty generated_text")
        if row.get("oom") or row.get("cuda_failure"):
            errors.append(f"{prefix}: OOM/CUDA failure flag present")
    return {
        "valid": not errors,
        "errors": errors,
        "row_count": len(rows),
        "fixture_ids": ids,
        "condition_values": sorted({str(row.get("condition")) for row in rows}),
        "policy_override_values": sorted({str(_boolish(row.get("qmsum_policy_suffix_override"))) for row in rows}),
        "compression_values": sorted({str(row.get("compression", "none")) for row in rows}),
        "max_vram_reserved_gib": _stat(rows, "vram_reserved_gib", max),
    }


def _stat(rows: list[dict[str, Any]], key: str, fn) -> float | None:
    values = [_number(row, key) for row in rows]
    numeric = [value for value in values if value is not None]
    return _round(fn(numeric)) if numeric else None


def _runtime_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "generation_time_s_avg": _stat(rows, "generation_time_s", statistics.fmean),
        "generation_time_s_min": _stat(rows, "generation_time_s", min),
        "generation_time_s_max": _stat(rows, "generation_time_s", max),
        "tokens_per_second_avg": _stat(rows, "tokens_per_second", statistics.fmean) or _stat(rows, "tok_per_sec", statistics.fmean),
        "tokens_per_second_min": _stat(rows, "tokens_per_second", min) or _stat(rows, "tok_per_sec", min),
        "tokens_per_second_max": _stat(rows, "tokens_per_second", max) or _stat(rows, "tok_per_sec", max),
        "output_tokens_avg": _stat(rows, "generated_token_count", statistics.fmean) or _stat(rows, "output_tokens", statistics.fmean),
        "vram_reserved_gib_max": _stat(rows, "vram_reserved_gib", max),
        "vram_allocated_gib_max": _stat(rows, "vram_allocated_gib", max),
    }


def _source_text(dataset_row: dict[str, Any], original_row: dict[str, Any]) -> str:
    return str(dataset_row.get("context") or original_row.get("original_context_preview") or original_row.get("source_prompt_preview") or "")


def assess_row(
    *,
    fixture_id: str,
    dataset_row: dict[str, Any],
    baseline_row: dict[str, Any],
    original_row: dict[str, Any],
    remediated_row: dict[str, Any],
    task102h_row: dict[str, Any],
) -> dict[str, Any]:
    reference = str(dataset_row.get("expected_answer") or baseline_row.get("expected_answer") or "")
    question = str(dataset_row.get("question") or baseline_row.get("question") or "")
    source = _source_text(dataset_row, original_row)
    baseline_text = str(baseline_row.get("generated_text") or "")
    original_text = str(original_row.get("generated_text") or "")
    remediated_text = str(remediated_row.get("generated_text") or "")
    baseline_metrics = proxy_metrics(output=baseline_text, reference=reference, question=question, source=source)
    original_metrics = proxy_metrics(output=original_text, reference=reference, question=question, source=source)
    remediated_metrics = proxy_metrics(output=remediated_text, reference=reference, question=question, source=source)
    category = classify_row(
        baseline_metrics=baseline_metrics,
        original_metrics=original_metrics,
        remediated_metrics=remediated_metrics,
    )
    return {
        "fixture_id": fixture_id,
        "category": category,
        "task102h_remediation_outcome": task102h_row.get("remediation_outcome"),
        "question": question,
        "reference_answer": reference,
        "original_cc_output": original_text,
        "remediated_cc_output": remediated_text,
        "baseline_ar_output": baseline_text,
        "baseline_reference_overlap": baseline_metrics["reference_overlap"],
        "baseline_reference_bigram_overlap": baseline_metrics["reference_bigram_overlap"],
        "baseline_question_focus_overlap": baseline_metrics["question_focus_overlap"],
        "baseline_source_grounding_overlap": baseline_metrics["source_grounding_overlap"],
        "baseline_entity_number_overlap": baseline_metrics["entity_number_overlap"],
        "baseline_generic_flag": baseline_metrics["generic_flag"],
        "baseline_empty_or_malformed": baseline_metrics["empty_or_malformed"],
        "original_reference_overlap": original_metrics["reference_overlap"],
        "remediated_reference_overlap": remediated_metrics["reference_overlap"],
        "best_cc_reference_overlap": max(original_metrics["reference_overlap"], remediated_metrics["reference_overlap"]),
        "baseline_minus_best_cc_reference_overlap": _round(
            baseline_metrics["reference_overlap"] - max(original_metrics["reference_overlap"], remediated_metrics["reference_overlap"])
        ),
        "baseline_generation_time_s": _number(baseline_row, "generation_time_s"),
        "baseline_tokens_per_second": _number(baseline_row, "tokens_per_second", "tok_per_sec"),
        "baseline_output_tokens": _number(baseline_row, "generated_token_count", "output_tokens"),
        "baseline_vram_reserved_gib": _number(baseline_row, "vram_reserved_gib"),
    }


def write_table(path: Path, assessments: list[dict[str, Any]]) -> None:
    columns = [
        "fixture_id",
        "category",
        "task102h_remediation_outcome",
        "baseline_reference_overlap",
        "baseline_reference_bigram_overlap",
        "baseline_question_focus_overlap",
        "baseline_source_grounding_overlap",
        "baseline_generic_flag",
        "original_reference_overlap",
        "remediated_reference_overlap",
        "best_cc_reference_overlap",
        "baseline_minus_best_cc_reference_overlap",
        "baseline_generation_time_s",
        "baseline_tokens_per_second",
        "baseline_output_tokens",
        "baseline_vram_reserved_gib",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in assessments:
            writer.writerow({column: row.get(column) for column in columns})


def _latest_baseline_artifact() -> Path:
    candidates = sorted((DEFAULT_OUTPUT_DIR / "runs").glob("*baseline_ar_qmsum_target_rows_n6_mnt384.jsonl"))
    if not candidates:
        raise FileNotFoundError(f"No Baseline-AR T102I run artifact found under {DEFAULT_OUTPUT_DIR / 'runs'}")
    return candidates[-1]


def analyze(
    *,
    baseline_jsonl: Path | None = None,
    original_cc_jsonl: Path = DEFAULT_ORIGINAL_CC_JSONL,
    remediated_cc_jsonl: Path = DEFAULT_REMEDIATED_CC_JSONL,
    task102h_assessment: Path = DEFAULT_TASK102H_ASSESSMENT,
    target_dataset: Path = DEFAULT_TARGET_DATASET,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    baseline_jsonl = baseline_jsonl or _latest_baseline_artifact()
    target_audit = validate_target_dataset(target_dataset)
    if not target_audit["valid"]:
        raise ValueError(f"Target dataset validation failed: {target_audit['errors']}")
    dataset_by_id = _index(read_jsonl(target_dataset))
    baseline_rows = read_jsonl(baseline_jsonl)
    baseline_audit = audit_baseline_run(baseline_rows)
    original_by_id = _index(read_jsonl(original_cc_jsonl))
    remediated_by_id = _index(read_jsonl(remediated_cc_jsonl))
    task102h_by_id = _index(read_jsonl(task102h_assessment))
    baseline_by_id = _index(baseline_rows)
    assessments: list[dict[str, Any]] = []
    missing: list[str] = []
    for fixture_id in TARGET_FIXTURE_IDS:
        if not all(
            fixture_id in mapping
            for mapping in (dataset_by_id, baseline_by_id, original_by_id, remediated_by_id, task102h_by_id)
        ):
            missing.append(fixture_id)
            continue
        assessments.append(
            assess_row(
                fixture_id=fixture_id,
                dataset_row=dataset_by_id[fixture_id],
                baseline_row=baseline_by_id[fixture_id],
                original_row=original_by_id[fixture_id],
                remediated_row=remediated_by_id[fixture_id],
                task102h_row=task102h_by_id[fixture_id],
            )
        )
    if missing:
        raise ValueError(f"Missing target rows in one or more inputs: {missing}")
    categories = [row["category"] for row in assessments]
    interpretation = interpret_categories(categories)
    next_task_decision = interpretation["next_task_decision"]
    decision = "PASS_WITH_CAVEAT" if baseline_audit["valid"] else "PARTIAL"
    summary = {
        "task": "T102I — QMSum Baseline-AR Target-row Mini-check",
        "decision": decision,
        "row_count": len(assessments),
        "input_artifacts": {
            "baseline_jsonl": str(baseline_jsonl),
            "original_cc_jsonl": str(original_cc_jsonl),
            "remediated_cc_jsonl": str(remediated_cc_jsonl),
            "task102h_assessment": str(task102h_assessment),
            "target_dataset": str(target_dataset),
        },
        "target_dataset_audit": target_audit,
        "baseline_run_audit": baseline_audit,
        "runtime_summary": _runtime_summary(baseline_rows),
        "category_counts": interpretation["category_counts"],
        "interpretation": interpretation["interpretation"],
        "method": "deterministic lexical, source-grounding, question-focus, genericness, cap/tail, and metadata checks only",
        "scope": "six Baseline-AR QMSum target rows only; no full matrix and no semantic judge",
    }
    row_labels = [
        {
            "fixture_id": row["fixture_id"],
            "category": row["category"],
            "baseline_reference_overlap": row["baseline_reference_overlap"],
            "baseline_source_grounding_overlap": row["baseline_source_grounding_overlap"],
            "baseline_generic_flag": row["baseline_generic_flag"],
            "baseline_empty_or_malformed": row["baseline_empty_or_malformed"],
        }
        for row in assessments
    ]
    claim_interpretation = {
        "interpretation": interpretation["interpretation"],
        "meaning": interpretation["meaning"],
        "claim_impact": (
            "Use this as scoped evidence about whether residual QMSum risk is consistent with target-model/QMSum grounding limits "
            "or compression-path-specific risk. Do not claim QMSum semantic correctness."
        ),
        "allowed_wording": [
            "Baseline-AR was checked on the same six QMSum residual-risk target rows with the same targeted policy.",
            "The result is deterministic proxy evidence only and is suitable for claim-boundary triage.",
        ],
        "blocked_wording": [
            "QMSum semantic correctness is proven.",
            "Baseline-AR mini-check completes the full matrix.",
            "Residual QMSum risk is conclusively caused by one factor.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[0], summary)
    write_jsonl(output_dir / OUTPUT_RELATIVE_PATHS[1], assessments)
    write_jsonl(output_dir / OUTPUT_RELATIVE_PATHS[2], row_labels)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[3], claim_interpretation)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[4], next_task_decision)
    write_table(output_dir / OUTPUT_RELATIVE_PATHS[5], assessments)
    return {
        "summary": summary,
        "row_assessments": assessments,
        "claim_interpretation": claim_interpretation,
        "next_task_decision": next_task_decision,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Task102I Baseline-AR QMSum target-row mini-check.")
    parser.add_argument("--baseline-jsonl", type=Path, default=None)
    parser.add_argument("--original-cc-jsonl", type=Path, default=DEFAULT_ORIGINAL_CC_JSONL)
    parser.add_argument("--remediated-cc-jsonl", type=Path, default=DEFAULT_REMEDIATED_CC_JSONL)
    parser.add_argument("--task102h-assessment", type=Path, default=DEFAULT_TASK102H_ASSESSMENT)
    parser.add_argument("--target-dataset", type=Path, default=DEFAULT_TARGET_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = analyze(
        baseline_jsonl=args.baseline_jsonl,
        original_cc_jsonl=args.original_cc_jsonl,
        remediated_cc_jsonl=args.remediated_cc_jsonl,
        task102h_assessment=args.task102h_assessment,
        target_dataset=args.target_dataset,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
