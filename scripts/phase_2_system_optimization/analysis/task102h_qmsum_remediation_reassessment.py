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

DEFAULT_ORIGINAL_JSONL = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102_qmsum_light_gpu_n30_feasibility_run/runs/"
    "20260622_151200_cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl"
)
DEFAULT_TASK102E_RESOLUTION = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102e_qmsum_hard_risk_and_residual_uncertainty_resolution/"
    "task102e_target_row_resolution.jsonl"
)
DEFAULT_REMEDIATED_JSONL = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102g_qmsum_target_row_remediation_rerun/runs/"
    "20260622_235012_cc_dflash_r2_light_gpu_qmsum_target_rows_n6_mnt384.jsonl"
)
DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102h_qmsum_remediation_reassessment"
)

OUTPUT_RELATIVE_PATHS = (
    Path("task102h_remediation_reassessment_summary.json"),
    Path("task102h_before_after_row_assessment.jsonl"),
    Path("task102h_resolved_rows.jsonl"),
    Path("task102h_remaining_risk_rows.jsonl"),
    Path("task102h_before_after_table.csv"),
    Path("task102h_claim_update.json"),
    Path("task102h_next_task_decision.json"),
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
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_no} is not a JSON object")
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


def _entity_number_terms(text: Any) -> set[str]:
    source = str(text or "")
    terms = set(re.findall(r"\b[A-Z][A-Za-z0-9-]*\b|\b[A-Z]{2,}\b|\b\d+(?:\.\d+)?\b", source))
    return {term.lower() for term in terms if term.lower() not in STOPWORDS}


def _has_generic_phrase(text: Any) -> bool:
    lowered = str(text or "").lower()
    return any(re.search(pattern, lowered) for pattern in GENERIC_PATTERNS)


def _looks_cap_limited(row: dict[str, Any]) -> bool:
    max_new_tokens = _number(row, "max_new_tokens")
    if not max_new_tokens:
        return False
    generated_tokens = _number(row, "generated_token_count", "output_tokens", "new_tokens")
    if generated_tokens is not None and generated_tokens >= max_new_tokens:
        return True
    text = str(row.get("generated_text") or row.get("generated_output") or "").strip()
    return bool(text) and not text.endswith((".", "?", "!", '"', "'", ")", "]"))


def _proxy_metrics(*, output: str, reference: str, question: str, source: str) -> dict[str, Any]:
    output_tokens = _tokens(output)
    reference_tokens = _tokens(reference)
    question_tokens = _tokens(question)
    source_tokens = _tokens(source)
    output_set = set(output_tokens)
    reference_set = set(reference_tokens)
    question_set = set(question_tokens)
    source_set = set(source_tokens)
    reference_overlap = _safe_ratio(len(output_set & reference_set), len(reference_set))
    reference_f1 = _safe_ratio(2 * len(output_set & reference_set), len(output_set) + len(reference_set))
    reference_bigram_overlap = _safe_ratio(len(_bigrams(output_tokens) & _bigrams(reference_tokens)), len(_bigrams(reference_tokens)))
    question_overlap = _safe_ratio(len(output_set & question_set), len(question_set))
    source_grounding = _safe_ratio(len(output_set & source_set), len(output_set))
    reference_entities = _entity_number_terms(reference)
    output_entities = _entity_number_terms(output)
    entity_number_overlap = _safe_ratio(len(reference_entities & output_entities), len(reference_entities))
    return {
        "reference_overlap": _round(reference_overlap),
        "reference_f1": _round(reference_f1),
        "reference_bigram_overlap": _round(reference_bigram_overlap),
        "question_overlap": _round(question_overlap),
        "source_grounding_overlap": _round(source_grounding),
        "entity_number_overlap": _round(entity_number_overlap),
        "output_content_terms": len(output_set),
        "generic_flag": _has_generic_phrase(output),
        "not_discussed_flag": _has_generic_phrase(output),
        "entity_number_count": len(output_entities),
    }


def _source_text(original_row: dict[str, Any], prior_row: dict[str, Any]) -> str:
    return str(
        original_row.get("original_context_preview")
        or original_row.get("source_prompt_preview")
        or prior_row.get("source_prompt_preview")
        or original_row.get("original_prompt_preview")
        or ""
    )


def _delta(after: float | None, before: float | None) -> float | None:
    if after is None or before is None:
        return None
    return _round(after - before)


def _improved(after: float | None, before: float | None, *, threshold: float) -> bool:
    return after is not None and before is not None and after - before >= threshold


def assess_row(
    *,
    fixture_id: str,
    original_row: dict[str, Any],
    remediated_row: dict[str, Any],
    prior_row: dict[str, Any],
) -> dict[str, Any]:
    reference = str(remediated_row.get("expected_answer") or original_row.get("expected_answer") or prior_row.get("reference_answer_preview") or "")
    question = str(remediated_row.get("question") or original_row.get("question") or prior_row.get("question") or "")
    source = _source_text(original_row, prior_row)
    original_text = str(original_row.get("generated_text") or prior_row.get("generated_output") or "")
    remediated_text = str(remediated_row.get("generated_text") or "")
    original_metrics = _proxy_metrics(output=original_text, reference=reference, question=question, source=source)
    remediated_metrics = _proxy_metrics(output=remediated_text, reference=reference, question=question, source=source)
    prior_status = str(prior_row.get("final_resolution") or prior_row.get("prior_status") or "other")
    flags: list[str] = []
    if _improved(remediated_metrics["reference_overlap"], original_metrics["reference_overlap"], threshold=0.05):
        flags.append("reference_overlap_improved")
    if _improved(remediated_metrics["source_grounding_overlap"], original_metrics["source_grounding_overlap"], threshold=0.03):
        flags.append("source_grounding_improved")
    if _improved(remediated_metrics["question_overlap"], original_metrics["question_overlap"], threshold=0.10):
        flags.append("question_focus_improved")
    if remediated_metrics["output_content_terms"] > original_metrics["output_content_terms"] + 5:
        flags.append("specificity_improved")
    if original_metrics["generic_flag"] and not remediated_metrics["generic_flag"]:
        flags.append("generic_answer_removed")
    if original_metrics["not_discussed_flag"] and not remediated_metrics["not_discussed_flag"]:
        flags.append("not_discussed_removed")
    if remediated_metrics["entity_number_count"] > original_metrics["entity_number_count"]:
        flags.append("evidence_entities_added")
    if remediated_metrics["reference_overlap"] < 0.25:
        flags.append("still_low_reference_overlap")
    if remediated_metrics["source_grounding_overlap"] < 0.08:
        flags.append("still_low_source_grounding")
    if remediated_metrics["generic_flag"]:
        flags.append("still_generic")
    if remediated_metrics["reference_overlap"] < 0.10 and remediated_metrics["question_overlap"] < 0.20:
        flags.append("still_off_topic")
    if not _looks_cap_limited(remediated_row):
        flags.append("no_cap_issue")
    if remediated_text.strip():
        flags.append("no_malformed_output")

    resolved = (
        remediated_metrics["reference_overlap"] >= 0.45
        and remediated_metrics["reference_bigram_overlap"] >= 0.20
        and not remediated_metrics["generic_flag"]
    )
    material_improvement = (
        "reference_overlap_improved" in flags
        or ("generic_answer_removed" in flags and remediated_metrics["reference_overlap"] >= 0.18)
    )
    generic_worsened = (not original_metrics["generic_flag"]) and remediated_metrics["generic_flag"]
    off_topic_worsened = remediated_metrics["reference_overlap"] + 0.02 < original_metrics["reference_overlap"]

    if resolved:
        remediation_outcome = "resolved_by_targeted_policy"
        final_risk_bucket = "resolved_proxy_supported"
    elif generic_worsened or off_topic_worsened:
        remediation_outcome = "worsened"
        final_risk_bucket = "worsened_output"
    elif prior_status == "confirmed_generic_or_under_specific":
        if remediated_metrics["generic_flag"] or remediated_metrics["reference_overlap"] < 0.25:
            remediation_outcome = "unchanged_quality_failure"
            final_risk_bucket = "residual_generic_or_under_specific"
        else:
            remediation_outcome = "improved_but_still_risky"
            final_risk_bucket = "residual_proxy_limitation"
    elif prior_status == "confirmed_evidence_miss":
        if material_improvement:
            remediation_outcome = "improved_but_still_risky"
        else:
            remediation_outcome = "unchanged_quality_failure"
        final_risk_bucket = "residual_evidence_miss"
    elif prior_status == "still_unresolved_without_semantic_judge":
        if remediated_metrics["reference_overlap"] >= 0.20 and _improved(
            remediated_metrics["reference_overlap"], original_metrics["reference_overlap"], threshold=0.08
        ):
            remediation_outcome = "improved_but_still_risky"
            final_risk_bucket = "residual_proxy_limitation"
        else:
            remediation_outcome = "still_unresolved_without_semantic_judge"
            final_risk_bucket = "residual_unresolved_deterministic_limitation"
            flags.append("deterministic_evidence_insufficient")
    else:
        remediation_outcome = "improved_but_still_risky" if material_improvement else "still_unresolved_without_semantic_judge"
        final_risk_bucket = "residual_proxy_limitation"
        if not material_improvement:
            flags.append("deterministic_evidence_insufficient")

    return {
        "fixture_id": fixture_id,
        "prior_status": prior_status,
        "remediation_outcome": remediation_outcome,
        "final_risk_bucket": final_risk_bucket,
        "secondary_flags": sorted(set(flags)),
        "question": question,
        "reference_answer": reference,
        "original_generated_answer": original_text,
        "remediated_generated_answer": remediated_text,
        "original_reference_overlap": original_metrics["reference_overlap"],
        "remediated_reference_overlap": remediated_metrics["reference_overlap"],
        "delta_reference_overlap": _delta(remediated_metrics["reference_overlap"], original_metrics["reference_overlap"]),
        "original_reference_bigram_overlap": original_metrics["reference_bigram_overlap"],
        "remediated_reference_bigram_overlap": remediated_metrics["reference_bigram_overlap"],
        "delta_reference_bigram_overlap": _delta(
            remediated_metrics["reference_bigram_overlap"], original_metrics["reference_bigram_overlap"]
        ),
        "original_question_overlap": original_metrics["question_overlap"],
        "remediated_question_overlap": remediated_metrics["question_overlap"],
        "delta_question_overlap": _delta(remediated_metrics["question_overlap"], original_metrics["question_overlap"]),
        "original_source_grounding_overlap": original_metrics["source_grounding_overlap"],
        "remediated_source_grounding_overlap": remediated_metrics["source_grounding_overlap"],
        "delta_source_grounding_overlap": _delta(
            remediated_metrics["source_grounding_overlap"], original_metrics["source_grounding_overlap"]
        ),
        "original_entity_number_overlap": original_metrics["entity_number_overlap"],
        "remediated_entity_number_overlap": remediated_metrics["entity_number_overlap"],
        "original_output_tokens": _number(original_row, "generated_token_count", "output_tokens"),
        "remediated_output_tokens": _number(remediated_row, "generated_token_count", "output_tokens"),
        "output_token_delta": _delta(
            _number(remediated_row, "generated_token_count", "output_tokens"),
            _number(original_row, "generated_token_count", "output_tokens"),
        ),
        "original_generic_flag": original_metrics["generic_flag"],
        "remediated_generic_flag": remediated_metrics["generic_flag"],
        "original_not_discussed_flag": original_metrics["not_discussed_flag"],
        "remediated_not_discussed_flag": remediated_metrics["not_discussed_flag"],
        "remediated_cap_tail_flag": _looks_cap_limited(remediated_row),
        "remediated_empty_or_malformed": not bool(remediated_text.strip()),
        "remediated_t_compress_ms": _number(remediated_row, "t_compress_ms"),
        "remediated_generation_time_s": _number(remediated_row, "generation_time_s"),
        "remediated_tokens_per_second": _number(remediated_row, "tokens_per_second", "tok_per_sec"),
    }


def _mean_delta(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [row.get(key) for row in rows if isinstance(row.get(key), (int, float))]
    return _round(statistics.fmean(values)) if values else None


def summarize_assessments(assessments: list[dict[str, Any]]) -> dict[str, Any]:
    outcomes = [row["remediation_outcome"] for row in assessments]
    buckets = [row["final_risk_bucket"] for row in assessments]
    hard_buckets = {"residual_evidence_miss", "residual_generic_or_under_specific", "worsened_output"}
    summary = {
        "target_rows_total": len(assessments),
        "resolved_by_targeted_policy_count": outcomes.count("resolved_by_targeted_policy"),
        "improved_but_still_risky_count": outcomes.count("improved_but_still_risky"),
        "unchanged_quality_failure_count": outcomes.count("unchanged_quality_failure"),
        "worsened_count": outcomes.count("worsened"),
        "still_unresolved_without_semantic_judge_count": outcomes.count("still_unresolved_without_semantic_judge"),
        "remaining_hard_risk_count": sum(1 for bucket in buckets if bucket in hard_buckets),
        "remaining_unresolved_count": buckets.count("residual_unresolved_deterministic_limitation"),
        "confirmed_failures_before_task102e": 3,
        "unresolved_rows_before_task102e": 3,
        "confirmed_failures_reduced_from_task102e": sum(1 for bucket in buckets if bucket in hard_buckets) < 3,
        "unresolved_rows_reduced_from_task102e": buckets.count("residual_unresolved_deterministic_limitation") < 3,
        "aggregate_deltas": {
            "reference_overlap": _mean_delta(assessments, "delta_reference_overlap"),
            "reference_bigram_overlap": _mean_delta(assessments, "delta_reference_bigram_overlap"),
            "question_overlap": _mean_delta(assessments, "delta_question_overlap"),
            "source_grounding_overlap": _mean_delta(assessments, "delta_source_grounding_overlap"),
            "output_tokens": _mean_delta(assessments, "output_token_delta"),
        },
        "generic_flags_before": sum(1 for row in assessments if row.get("original_generic_flag")),
        "generic_flags_after": sum(1 for row in assessments if row.get("remediated_generic_flag")),
    }
    return summary


def build_claim_update(summary: dict[str, Any]) -> dict[str, Any]:
    hard = int(summary.get("remaining_hard_risk_count", 0))
    unresolved = int(summary.get("remaining_unresolved_count", 0))
    worsened = int(summary.get("worsened_count", 0))
    if hard == 0 and unresolved == 0:
        status = "SCOPED_WITH_REMEDIATED_RISK"
        t103 = "ALLOWED_BY_DEFAULT"
    elif worsened > 0:
        status = "REMEDIATION_FAILED"
        t103 = "BLOCKED_BY_DEFAULT"
    elif hard < 3 or unresolved < 3:
        status = "SCOPED_WITH_PARTIAL_REMEDIATION"
        t103 = "CAVEAT_REQUIRED"
    else:
        status = "SCOPED_WITH_PERSISTENT_RESIDUAL_RISK"
        t103 = "BLOCKED_BY_DEFAULT"
    if hard >= 3 and status == "SCOPED_WITH_PARTIAL_REMEDIATION":
        status = "SCOPED_WITH_PERSISTENT_RESIDUAL_RISK"
        t103 = "BLOCKED_BY_DEFAULT"
    return {
        "qmsum_claim_status": status,
        "t103_status": t103,
        "allowed_wording": [
            "QMSum target-row remediation was reassessed with deterministic before/after proxy checks.",
            "QMSum evidence supports benchmark-scoped feasibility and deterministic risk analysis.",
            "Residual QMSum quality risk is explicitly bounded by row-level reassessment.",
        ],
        "blocked_wording": [
            "QMSum semantic correctness is proven.",
            "QMSum quality risk is eliminated unless hard-risk and unresolved rows are zero.",
            "T103 speed-claim closure can ignore QMSum residual quality risk.",
            "Universal 8GB readiness is proven.",
        ],
        "remaining_limitations": [
            "No LLM judge or human semantic scoring was used.",
            "Deterministic lexical/evidence proxies can undercount semantically acceptable abstractive answers.",
            "Persistent hard-risk rows require caveat acceptance, semantic review, or a stop decision before speed-claim closure.",
        ],
    }


def build_next_task_decision(claim_update: dict[str, Any]) -> dict[str, Any]:
    status = claim_update["qmsum_claim_status"]
    if status == "SCOPED_WITH_REMEDIATED_RISK":
        return {
            "next_task": "T103 — Reference Alignment for Speed Claim",
            "caveat_required": False,
            "reason": "Target-row remediation resolved residual QMSum risk enough to proceed.",
        }
    if status == "SCOPED_WITH_PARTIAL_REMEDIATION":
        return {
            "next_task": "T103 — Reference Alignment for Speed Claim",
            "caveat_required": True,
            "reason": "Proceed only with an explicit residual QMSum caveat unless further remediation is requested.",
        }
    return {
        "next_task": "T102I — QMSum Residual Risk Stop-or-Judge Decision",
        "caveat_required": True,
        "reason": "Targeted remediation did not close enough residual risk; choose between accepting caveat, semantic review, or stopping QMSum quality expansion.",
    }


def write_table(path: Path, assessments: list[dict[str, Any]]) -> None:
    columns = [
        "fixture_id",
        "prior_status",
        "remediation_outcome",
        "final_risk_bucket",
        "original_reference_overlap",
        "remediated_reference_overlap",
        "delta_reference_overlap",
        "original_question_overlap",
        "remediated_question_overlap",
        "delta_question_overlap",
        "original_source_grounding_overlap",
        "remediated_source_grounding_overlap",
        "delta_source_grounding_overlap",
        "original_generic_flag",
        "remediated_generic_flag",
        "original_output_tokens",
        "remediated_output_tokens",
        "output_token_delta",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in assessments:
            writer.writerow({column: row.get(column) for column in columns})


def analyze(
    *,
    original_jsonl: Path = DEFAULT_ORIGINAL_JSONL,
    task102e_resolution: Path = DEFAULT_TASK102E_RESOLUTION,
    remediated_jsonl: Path = DEFAULT_REMEDIATED_JSONL,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    original_by_id = _index(read_jsonl(original_jsonl))
    prior_by_id = _index(read_jsonl(task102e_resolution))
    remediated_by_id = _index(read_jsonl(remediated_jsonl))
    assessments = []
    missing: list[str] = []
    for fixture_id in TARGET_FIXTURE_IDS:
        original_row = original_by_id.get(fixture_id)
        prior_row = prior_by_id.get(fixture_id)
        remediated_row = remediated_by_id.get(fixture_id)
        if original_row is None or prior_row is None or remediated_row is None:
            missing.append(fixture_id)
            continue
        assessments.append(
            assess_row(
                fixture_id=fixture_id,
                original_row=original_row,
                remediated_row=remediated_row,
                prior_row=prior_row,
            )
        )
    if missing:
        raise ValueError(f"Missing target rows in one or more inputs: {missing}")
    summary = summarize_assessments(assessments)
    claim_update = build_claim_update(summary)
    next_task_decision = build_next_task_decision(claim_update)
    summary.update(
        {
            "task": "T102H — QMSum Remediation Reassessment",
            "decision": "PASS_WITH_CAVEAT"
            if claim_update["qmsum_claim_status"]
            in {"SCOPED_WITH_PARTIAL_REMEDIATION", "SCOPED_WITH_PERSISTENT_RESIDUAL_RISK", "REMEDIATION_FAILED"}
            else "PASS"
            if claim_update["qmsum_claim_status"] == "SCOPED_WITH_REMEDIATED_RISK"
            else "PARTIAL",
            "qmsum_claim_status": claim_update["qmsum_claim_status"],
            "input_artifacts": {
                "original_jsonl": str(original_jsonl),
                "task102e_resolution": str(task102e_resolution),
                "remediated_jsonl": str(remediated_jsonl),
            },
            "next_task": next_task_decision["next_task"],
            "method": "deterministic before/after lexical, source-grounding, question-focus, genericness, cap, and malformed-output heuristics only",
        }
    )
    resolved_rows = [row for row in assessments if row["final_risk_bucket"] == "resolved_proxy_supported"]
    remaining_rows = [row for row in assessments if row["final_risk_bucket"] != "resolved_proxy_supported"]
    write_json(output_dir / "task102h_remediation_reassessment_summary.json", summary)
    write_jsonl(output_dir / "task102h_before_after_row_assessment.jsonl", assessments)
    write_jsonl(output_dir / "task102h_resolved_rows.jsonl", resolved_rows)
    write_jsonl(output_dir / "task102h_remaining_risk_rows.jsonl", remaining_rows)
    write_table(output_dir / "task102h_before_after_table.csv", assessments)
    write_json(output_dir / "task102h_claim_update.json", claim_update)
    write_json(output_dir / "task102h_next_task_decision.json", next_task_decision)
    return {
        "summary": summary,
        "row_assessments": assessments,
        "claim_update": claim_update,
        "next_task_decision": next_task_decision,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reassess Task102H QMSum target-row remediation outputs.")
    parser.add_argument("--original-jsonl", type=Path, default=DEFAULT_ORIGINAL_JSONL)
    parser.add_argument("--task102e-resolution", type=Path, default=DEFAULT_TASK102E_RESOLUTION)
    parser.add_argument("--remediated-jsonl", type=Path, default=DEFAULT_REMEDIATED_JSONL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = analyze(
        original_jsonl=args.original_jsonl,
        task102e_resolution=args.task102e_resolution,
        remediated_jsonl=args.remediated_jsonl,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
