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
    "task103a_qmsum_evidence_selector_before_answer"
)
DEFAULT_EVIDENCE_SELECTED_DATASET = Path("data/eval/qmsum_meeting_qa_target_rows_task103a_evidence_selected.jsonl")
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
DEFAULT_BASELINE_FULL_JSONL = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102i_qmsum_baseline_ar_target_row_mini_check/runs/"
    "20260623_003802_baseline_ar_qmsum_target_rows_n6_mnt384.jsonl"
)

OUTPUT_RELATIVE_PATHS = (
    Path("summary/task103a_run_metadata_audit.json"),
    Path("summary/task103a_before_after_assessment.jsonl"),
    Path("summary/task103a_claim_update.json"),
    Path("summary/task103a_next_task_decision.json"),
    Path("tables/task103a_evidence_selector_comparison.csv"),
)

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
    "why",
    "will",
    "with",
    "would",
}

GENERIC_PATTERNS = (
    r"\bnot (?:mentioned|discussed|provided|available|specified|clear)\b",
    r"\bdoes not (?:mention|provide|discuss|contain)\b",
    r"\bno evidence\b",
    r"\bno information\b",
    r"\bcannot determine\b",
    r"\bnot enough information\b",
)


def read_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    rows: list[dict[str, Any]] = []
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


def _tokens(text: Any) -> list[str]:
    raw = re.findall(r"[A-Za-z0-9]+", str(text or "").lower())
    return [token for token in raw if token not in STOPWORDS and len(token) > 1]


def _bigrams(tokens: list[str]) -> set[tuple[str, str]]:
    return set(zip(tokens, tokens[1:]))


def _safe_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _round(value: float | None) -> float | None:
    return None if value is None else round(float(value), 6)


def _has_generic_phrase(text: Any) -> bool:
    lowered = str(text or "").lower()
    return any(re.search(pattern, lowered) for pattern in GENERIC_PATTERNS)


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


def proxy_metrics(*, output: str, reference: str, question: str, evidence: str) -> dict[str, Any]:
    output_tokens = _tokens(output)
    reference_tokens = _tokens(reference)
    question_tokens = _tokens(question)
    evidence_tokens = _tokens(evidence)
    output_set = set(output_tokens)
    reference_set = set(reference_tokens)
    question_set = set(question_tokens)
    evidence_set = set(evidence_tokens)
    reference_bigrams = _bigrams(reference_tokens)
    return {
        "reference_overlap": _round(_safe_ratio(len(output_set & reference_set), len(reference_set))),
        "reference_bigram_overlap": _round(_safe_ratio(len(_bigrams(output_tokens) & reference_bigrams), len(reference_bigrams))),
        "question_overlap": _round(_safe_ratio(len(output_set & question_set), len(question_set))),
        "selected_evidence_overlap": _round(_safe_ratio(len(output_set & evidence_set), len(output_set))),
        "generic_flag": _has_generic_phrase(output),
        "empty_or_malformed": not bool(str(output or "").strip()),
        "output_content_terms": len(output_set),
    }


def _resolved(metrics: dict[str, Any]) -> bool:
    return (
        float(metrics.get("reference_overlap") or 0.0) >= 0.45
        and float(metrics.get("reference_bigram_overlap") or 0.0) >= 0.20
        and not bool(metrics.get("generic_flag"))
    )


def classify_transition(*, previous_metrics: dict[str, Any], evidence_metrics: dict[str, Any]) -> str:
    prev_ref = float(previous_metrics.get("reference_overlap") or 0.0)
    evidence_ref = float(evidence_metrics.get("reference_overlap") or 0.0)
    if evidence_metrics.get("empty_or_malformed"):
        return "worsened"
    if _resolved(evidence_metrics):
        return "resolved"
    if evidence_metrics.get("generic_flag") and not previous_metrics.get("generic_flag"):
        return "worsened"
    if evidence_ref >= prev_ref + 0.08 and evidence_ref >= 0.18:
        return "improved"
    if evidence_ref + 0.05 < prev_ref:
        return "worsened"
    return "unchanged"


def interpret_results(*, baseline_categories: list[str], cc_categories: list[str], cc_present: bool) -> dict[str, Any]:
    baseline_helpful = sum(1 for category in baseline_categories if category in {"resolved", "improved"})
    cc_helpful = sum(1 for category in cc_categories if category in {"resolved", "improved"}) if cc_present else 0
    if baseline_helpful >= 4 and cc_present and cc_helpful >= 4:
        interpretation = "EVIDENCE_SELECTION_HELPS_AND_QUERY_AWARE_COMPRESSION_PROMISING"
        next_task = "T103B — Query-aware Compression"
        reason = "Evidence-selected Baseline-AR improves most rows and CC-DFlash also improves under selected evidence."
    elif baseline_helpful >= 4:
        interpretation = "EVIDENCE_SELECTION_HELPS_BASELINE_FIRST"
        next_task = "T103B — Query-aware Compression"
        reason = "Evidence-selected Baseline-AR improves most rows; query-aware compression is the next bounded check."
    elif baseline_helpful < 2 and (not cc_present or cc_helpful < 2):
        interpretation = "GENERATION_OR_SEMANTIC_LIMITATION_REMAINS"
        next_task = "T103C — Semantic Judge / Human Review Protocol"
        reason = "Evidence selection did not materially improve deterministic proxy outcomes."
    else:
        interpretation = "MIXED_EVIDENCE_SELECTION_SIGNAL"
        next_task = "T103D — QMSum Deep Fix Closure Decision"
        reason = "Evidence selection produced mixed deterministic outcomes; choose whether T103B or T103C is still useful."
    return {
        "interpretation": interpretation,
        "baseline_helpful_count": baseline_helpful,
        "cc_helpful_count": cc_helpful,
        "next_task_decision": {"next_task": next_task, "reason": reason},
    }


def _latest_run(pattern: str) -> Path | None:
    candidates = sorted((DEFAULT_OUTPUT_DIR / "runs").glob(pattern))
    return candidates[-1] if candidates else None


def _stat(rows: list[dict[str, Any]], key: str, fn) -> float | None:
    values = [_number(row, key) for row in rows]
    numeric = [value for value in values if value is not None]
    return _round(fn(numeric)) if numeric else None


def _audit_run(rows: list[dict[str, Any]], *, condition: str, require_compression: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    ids = [_fixture_id(row) for row in rows]
    if len(rows) != len(TARGET_FIXTURE_IDS):
        errors.append(f"expected 6 rows for {condition}, found {len(rows)}")
    if set(ids) != set(TARGET_FIXTURE_IDS):
        errors.append(f"{condition} fixture id mismatch: {sorted(set(ids))}")
    for row in rows:
        fixture_id = _fixture_id(row)
        if row.get("condition") != condition:
            errors.append(f"{fixture_id}: condition={row.get('condition')!r}")
        if row.get("qmsum_answer_policy_type") != "qmsum_evidence_selected_v1":
            errors.append(f"{fixture_id}: qmsum_answer_policy_type={row.get('qmsum_answer_policy_type')!r}")
        if row.get("qmsum_policy_suffix_override") is not True:
            errors.append(f"{fixture_id}: qmsum_policy_suffix_override={row.get('qmsum_policy_suffix_override')!r}")
        if require_compression and row.get("compressor_profile") != "light":
            errors.append(f"{fixture_id}: compressor_profile={row.get('compressor_profile')!r}")
        if require_compression and row.get("compressor_device_map") != "cuda":
            errors.append(f"{fixture_id}: compressor_device_map={row.get('compressor_device_map')!r}")
        if not require_compression and str(row.get("compression", "none")) != "none":
            errors.append(f"{fixture_id}: compression={row.get('compression')!r}")
        if not str(row.get("generated_text") or "").strip():
            errors.append(f"{fixture_id}: empty generated_text")
        if row.get("oom") or row.get("cuda_failure"):
            errors.append(f"{fixture_id}: OOM/CUDA failure flag present")
    return {
        "valid": not errors,
        "errors": errors,
        "row_count": len(rows),
        "fixture_ids": ids,
        "generation_time_s_avg": _stat(rows, "generation_time_s", statistics.fmean),
        "tokens_per_second_avg": _stat(rows, "tokens_per_second", statistics.fmean) or _stat(rows, "tok_per_sec", statistics.fmean),
        "vram_reserved_gib_max": _stat(rows, "vram_reserved_gib", max),
        "t_compress_ms_avg": _stat(rows, "t_compress_ms", statistics.fmean),
    }


def assess_row(
    *,
    fixture_id: str,
    dataset_row: dict[str, Any],
    original_cc_row: dict[str, Any],
    remediated_cc_row: dict[str, Any],
    baseline_full_row: dict[str, Any],
    baseline_evidence_row: dict[str, Any],
    cc_evidence_row: dict[str, Any] | None,
) -> dict[str, Any]:
    reference = str(dataset_row.get("expected_answer") or "")
    question = str(dataset_row.get("question") or "")
    evidence = str(dataset_row.get("context") or "")
    original_cc = proxy_metrics(output=str(original_cc_row.get("generated_text") or ""), reference=reference, question=question, evidence=evidence)
    remediated_cc = proxy_metrics(output=str(remediated_cc_row.get("generated_text") or ""), reference=reference, question=question, evidence=evidence)
    baseline_full = proxy_metrics(output=str(baseline_full_row.get("generated_text") or ""), reference=reference, question=question, evidence=evidence)
    baseline_evidence = proxy_metrics(output=str(baseline_evidence_row.get("generated_text") or ""), reference=reference, question=question, evidence=evidence)
    best_previous = max(
        (original_cc, remediated_cc, baseline_full),
        key=lambda metrics: float(metrics.get("reference_overlap") or 0.0),
    )
    baseline_category = classify_transition(previous_metrics=baseline_full, evidence_metrics=baseline_evidence)
    cc_category = None
    cc_metrics = None
    if cc_evidence_row is not None:
        cc_metrics = proxy_metrics(
            output=str(cc_evidence_row.get("generated_text") or ""),
            reference=reference,
            question=question,
            evidence=evidence,
        )
        cc_category = classify_transition(previous_metrics=remediated_cc, evidence_metrics=cc_metrics)
    return {
        "fixture_id": fixture_id,
        "question": question,
        "reference_answer": reference,
        "baseline_evidence_category": baseline_category,
        "cc_evidence_category": cc_category,
        "best_previous_reference_overlap": best_previous["reference_overlap"],
        "baseline_full_reference_overlap": baseline_full["reference_overlap"],
        "baseline_evidence_reference_overlap": baseline_evidence["reference_overlap"],
        "baseline_evidence_reference_bigram_overlap": baseline_evidence["reference_bigram_overlap"],
        "baseline_evidence_question_overlap": baseline_evidence["question_overlap"],
        "baseline_evidence_selected_evidence_overlap": baseline_evidence["selected_evidence_overlap"],
        "baseline_evidence_generic_flag": baseline_evidence["generic_flag"],
        "cc_remediated_reference_overlap": remediated_cc["reference_overlap"],
        "cc_evidence_reference_overlap": cc_metrics["reference_overlap"] if cc_metrics else None,
        "cc_evidence_reference_bigram_overlap": cc_metrics["reference_bigram_overlap"] if cc_metrics else None,
        "cc_evidence_selected_evidence_overlap": cc_metrics["selected_evidence_overlap"] if cc_metrics else None,
        "cc_evidence_generic_flag": cc_metrics["generic_flag"] if cc_metrics else None,
        "baseline_evidence_output": str(baseline_evidence_row.get("generated_text") or ""),
        "cc_evidence_output": str(cc_evidence_row.get("generated_text") or "") if cc_evidence_row else "",
    }


def write_table(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = [
        "fixture_id",
        "baseline_evidence_category",
        "cc_evidence_category",
        "best_previous_reference_overlap",
        "baseline_full_reference_overlap",
        "baseline_evidence_reference_overlap",
        "baseline_evidence_selected_evidence_overlap",
        "cc_remediated_reference_overlap",
        "cc_evidence_reference_overlap",
        "cc_evidence_selected_evidence_overlap",
        "baseline_evidence_generic_flag",
        "cc_evidence_generic_flag",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in columns})


def analyze(
    *,
    evidence_selected_dataset: Path = DEFAULT_EVIDENCE_SELECTED_DATASET,
    original_cc_jsonl: Path = DEFAULT_ORIGINAL_CC_JSONL,
    remediated_cc_jsonl: Path = DEFAULT_REMEDIATED_CC_JSONL,
    baseline_full_jsonl: Path = DEFAULT_BASELINE_FULL_JSONL,
    baseline_evidence_jsonl: Path | None = None,
    cc_evidence_jsonl: Path | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    baseline_evidence_jsonl = baseline_evidence_jsonl or _latest_run("*baseline_ar_qmsum_evidence_selected_n6_mnt384.jsonl")
    cc_evidence_jsonl = cc_evidence_jsonl or _latest_run("*cc_dflash_r2_light_gpu_qmsum_evidence_selected_n6_mnt384.jsonl")
    if baseline_evidence_jsonl is None:
        raise FileNotFoundError("Missing Task103A Baseline-AR evidence-selected run artifact")
    dataset_by_id = _index(read_jsonl(evidence_selected_dataset))
    original_by_id = _index(read_jsonl(original_cc_jsonl))
    remediated_by_id = _index(read_jsonl(remediated_cc_jsonl))
    baseline_full_by_id = _index(read_jsonl(baseline_full_jsonl))
    baseline_evidence_rows = read_jsonl(baseline_evidence_jsonl)
    cc_evidence_rows = read_jsonl(cc_evidence_jsonl)
    baseline_evidence_by_id = _index(baseline_evidence_rows)
    cc_evidence_by_id = _index(cc_evidence_rows)
    missing: list[str] = []
    assessments: list[dict[str, Any]] = []
    for fixture_id in TARGET_FIXTURE_IDS:
        if not all(
            fixture_id in mapping
            for mapping in (dataset_by_id, original_by_id, remediated_by_id, baseline_full_by_id, baseline_evidence_by_id)
        ):
            missing.append(fixture_id)
            continue
        assessments.append(
            assess_row(
                fixture_id=fixture_id,
                dataset_row=dataset_by_id[fixture_id],
                original_cc_row=original_by_id[fixture_id],
                remediated_cc_row=remediated_by_id[fixture_id],
                baseline_full_row=baseline_full_by_id[fixture_id],
                baseline_evidence_row=baseline_evidence_by_id[fixture_id],
                cc_evidence_row=cc_evidence_by_id.get(fixture_id),
            )
        )
    if missing:
        raise ValueError(f"Missing rows in one or more inputs: {missing}")
    baseline_categories = [row["baseline_evidence_category"] for row in assessments]
    cc_present = len(cc_evidence_by_id) == len(TARGET_FIXTURE_IDS)
    cc_categories = [row["cc_evidence_category"] for row in assessments if row["cc_evidence_category"]]
    interpretation = interpret_results(
        baseline_categories=baseline_categories,
        cc_categories=cc_categories,
        cc_present=cc_present,
    )
    baseline_audit = _audit_run(baseline_evidence_rows, condition="Baseline-AR", require_compression=False)
    cc_audit = _audit_run(cc_evidence_rows, condition="CC-DFlash-R2", require_compression=True) if cc_present else {
        "valid": False,
        "errors": ["CC-DFlash evidence-selected run not present"],
        "row_count": len(cc_evidence_rows),
    }
    metadata_audit = {
        "baseline_evidence_run": baseline_audit,
        "cc_evidence_run": cc_audit,
        "cc_evidence_run_present": cc_present,
    }
    claim_update = {
        "qmsum_claim_status": "EVIDENCE_SELECTION_MINI_CHECK_COMPLETE",
        "interpretation": interpretation["interpretation"],
        "allowed_wording": [
            "Task103A tested deterministic question-focused evidence selection on the six residual QMSum rows.",
            "Task103A supports bounded discussion of whether selected evidence helps target-model grounding.",
        ],
        "blocked_wording": [
            "QMSum semantic correctness is proven.",
            "Evidence selection proves the root cause of QMSum residual failures.",
            "The full QMSum matrix is complete.",
        ],
        "remaining_limitations": [
            "Only six target rows were run.",
            "Evidence selection used deterministic lexical heuristics, not semantic retrieval.",
            "No LLM judge or human semantic scoring was used.",
        ],
    }
    summary = {
        "task": "T103A — QMSum Evidence Retrieval / Evidence Selector before Answer",
        "decision": "PASS_WITH_CAVEAT" if baseline_audit["valid"] and (not cc_present or cc_audit["valid"]) else "PARTIAL",
        "row_count": len(assessments),
        "baseline_category_counts": {category: baseline_categories.count(category) for category in sorted(set(baseline_categories))},
        "cc_category_counts": {category: cc_categories.count(category) for category in sorted(set(cc_categories))},
        "interpretation": interpretation["interpretation"],
        "input_artifacts": {
            "evidence_selected_dataset": str(evidence_selected_dataset),
            "original_cc_jsonl": str(original_cc_jsonl),
            "remediated_cc_jsonl": str(remediated_cc_jsonl),
            "baseline_full_jsonl": str(baseline_full_jsonl),
            "baseline_evidence_jsonl": str(baseline_evidence_jsonl),
            "cc_evidence_jsonl": str(cc_evidence_jsonl) if cc_evidence_jsonl else None,
        },
        "scope": "six QMSum target rows only; deterministic proxy analysis only",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "summary/task103a_run_metadata_audit.json", metadata_audit)
    write_jsonl(output_dir / "summary/task103a_before_after_assessment.jsonl", assessments)
    write_json(output_dir / "summary/task103a_claim_update.json", claim_update)
    write_json(output_dir / "summary/task103a_next_task_decision.json", interpretation["next_task_decision"])
    write_table(output_dir / "tables/task103a_evidence_selector_comparison.csv", assessments)
    write_json(output_dir / "summary/task103a_evidence_selector_run_summary.json", summary)
    return {
        "summary": summary,
        "row_assessments": assessments,
        "metadata_audit": metadata_audit,
        "claim_update": claim_update,
        "next_task_decision": interpretation["next_task_decision"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Task103A QMSum evidence-selected mini-check runs.")
    parser.add_argument("--evidence-selected-dataset", type=Path, default=DEFAULT_EVIDENCE_SELECTED_DATASET)
    parser.add_argument("--original-cc-jsonl", type=Path, default=DEFAULT_ORIGINAL_CC_JSONL)
    parser.add_argument("--remediated-cc-jsonl", type=Path, default=DEFAULT_REMEDIATED_CC_JSONL)
    parser.add_argument("--baseline-full-jsonl", type=Path, default=DEFAULT_BASELINE_FULL_JSONL)
    parser.add_argument("--baseline-evidence-jsonl", type=Path, default=None)
    parser.add_argument("--cc-evidence-jsonl", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = analyze(
        evidence_selected_dataset=args.evidence_selected_dataset,
        original_cc_jsonl=args.original_cc_jsonl,
        remediated_cc_jsonl=args.remediated_cc_jsonl,
        baseline_full_jsonl=args.baseline_full_jsonl,
        baseline_evidence_jsonl=args.baseline_evidence_jsonl,
        cc_evidence_jsonl=args.cc_evidence_jsonl,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
