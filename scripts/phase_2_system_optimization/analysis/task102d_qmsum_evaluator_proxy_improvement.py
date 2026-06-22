from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_QMSUM_JSONL = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102_qmsum_light_gpu_n30_feasibility_run/runs/"
    "20260622_151200_cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl"
)
DEFAULT_ROW_LABELS = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102b_qmsum_output_semantic_risk_analysis/task102b_qmsum_row_labels.jsonl"
)
DEFAULT_T102C_TRIAGE = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102c_qmsum_proxy_uncertainty_triage/task102c_uncertain_row_triage.jsonl"
)
DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102d_qmsum_evaluator_proxy_improvement"
)

OUTPUT_RELATIVE_PATHS = (
    Path("task102d_proxy_improvement_summary.json"),
    Path("task102d_row_proxy_reassessment.jsonl"),
    Path("task102d_proxy_comparison_table.csv"),
    Path("task102d_claim_update.json"),
    Path("task102d_next_task_decision.json"),
)

STOPWORDS = {
    "about",
    "above",
    "after",
    "also",
    "and",
    "answer",
    "because",
    "been",
    "being",
    "but",
    "can",
    "could",
    "did",
    "does",
    "during",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "into",
    "its",
    "meeting",
    "not",
    "only",
    "question",
    "said",
    "she",
    "should",
    "that",
    "the",
    "their",
    "them",
    "there",
    "they",
    "this",
    "through",
    "use",
    "used",
    "using",
    "was",
    "were",
    "what",
    "when",
    "which",
    "while",
    "who",
    "why",
    "with",
    "would",
}
LOW_SIGNAL_TERMS = {
    "agenda",
    "answer",
    "context",
    "decision",
    "discuss",
    "discussion",
    "general",
    "meeting",
    "point",
    "project",
    "question",
    "summary",
    "team",
    "topic",
}


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


def normalize_token(token: str) -> str:
    token = token.lower()
    aliases = {
        "colours": "color",
        "colour": "color",
        "mics": "microphone",
        "mike": "microphone",
        "mikes": "microphone",
        "microphones": "microphone",
        "recognition": "recognition",
        "summarization": "summary",
        "summarisation": "summary",
    }
    if token in aliases:
        return aliases[token]
    if token.endswith("ies") and len(token) > 5:
        token = token[:-3] + "y"
    elif token.endswith("ing") and len(token) > 6:
        token = token[:-3]
    elif token.endswith("ed") and len(token) > 5:
        token = token[:-2]
    elif token.endswith("s") and len(token) > 4:
        token = token[:-1]
    return token


def content_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in re.findall(r"[A-Za-z0-9]+", text.lower()):
        token = normalize_token(raw)
        if len(token) <= 2 or token in STOPWORDS or token in LOW_SIGNAL_TERMS:
            continue
        tokens.append(token)
    return tokens


def content_recall(candidate: str, reference: str) -> float | None:
    reference_terms = set(content_tokens(reference))
    if not reference_terms:
        return None
    candidate_terms = set(content_tokens(candidate))
    return len(candidate_terms & reference_terms) / len(reference_terms)


def content_precision(candidate: str, reference: str) -> float | None:
    candidate_terms = set(content_tokens(candidate))
    if not candidate_terms:
        return None
    reference_terms = set(content_tokens(reference))
    return len(candidate_terms & reference_terms) / len(candidate_terms)


def content_f1(candidate: str, reference: str) -> float | None:
    precision = content_precision(candidate, reference)
    recall = content_recall(candidate, reference)
    if precision is None or recall is None or precision + recall == 0:
        return None
    return 2 * precision * recall / (precision + recall)


def _text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _metric(row: dict[str, Any], key: str) -> float | None:
    metrics = row.get("metrics")
    if isinstance(metrics, dict):
        value = metrics.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    value = row.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _labels(row: dict[str, Any]) -> dict[str, Any]:
    labels = row.get("labels")
    return labels if isinstance(labels, dict) else {}


def _previews(row: dict[str, Any]) -> dict[str, Any]:
    previews = row.get("previews")
    return previews if isinstance(previews, dict) else {}


def _reference_text(qmsum_row: dict[str, Any], label_row: dict[str, Any]) -> str:
    for key in ("expected_answer", "reference_answer", "target_answer"):
        value = qmsum_row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    value = _previews(label_row).get("expected_answer")
    return value.strip() if isinstance(value, str) else ""


def _question_text(qmsum_row: dict[str, Any], label_row: dict[str, Any]) -> str:
    preview_question = _previews(label_row).get("question")
    if isinstance(preview_question, str) and preview_question.strip():
        return preview_question.strip()
    explicit = _text(qmsum_row, "question", "query")
    if explicit:
        return explicit
    tail = _text(qmsum_row, "final_prompt_tail_preview")
    if "Answer only the question" in tail:
        return tail.split("Answer only the question", 1)[0][-260:].strip(" .")
    return ""


def _source_text(qmsum_row: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in [
            _text(qmsum_row, "compressed_context_preview"),
            _text(qmsum_row, "compressed_prompt_preview"),
            _text(qmsum_row, "original_context_preview"),
            _text(qmsum_row, "original_prompt_preview"),
            _text(qmsum_row, "final_prompt_tail_preview"),
        ]
        if part
    )


def _has_source_context(qmsum_row: dict[str, Any]) -> bool:
    return any(
        _text(qmsum_row, key)
        for key in (
            "compressed_context_preview",
            "compressed_prompt_preview",
            "original_context_preview",
            "original_prompt_preview",
        )
    )


def _index_by_fixture(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("fixture_id") or row.get("dataset_id") or "")
        if key:
            indexed[key] = row
    return indexed


def _generic_ratio(generated: str) -> float:
    tokens = content_tokens(generated)
    if not tokens:
        return 1.0
    generic_count = sum(1 for token in tokens if token in LOW_SIGNAL_TERMS)
    return generic_count / len(tokens)


def _entity_terms(text: str) -> set[str]:
    terms = set()
    for token in re.findall(r"\b[A-Z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)?\b|\b\d+(?:\.\d+)?%?\b", text):
        normalized = normalize_token(token.strip("'"))
        if len(normalized) > 1 and normalized not in STOPWORDS:
            terms.add(normalized)
    return terms


def _entity_overlap(generated: str, reference: str) -> float | None:
    reference_entities = _entity_terms(reference)
    if not reference_entities:
        return None
    return len(_entity_terms(generated) & reference_entities) / len(reference_entities)


def reassess_row(
    qmsum_row: dict[str, Any],
    label_row: dict[str, Any],
    t102c_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fixture_id = str(label_row.get("fixture_id") or qmsum_row.get("fixture_id") or qmsum_row.get("dataset_id") or "")
    labels = _labels(label_row)
    generated = _text(qmsum_row, "generated_text") or str(_previews(label_row).get("generated_text") or "")
    reference = _reference_text(qmsum_row, label_row)
    question = _question_text(qmsum_row, label_row)
    source = _source_text(qmsum_row)
    has_source_context = _has_source_context(qmsum_row)
    output_tokens = _metric(label_row, "output_token_count")
    if output_tokens is None:
        output_tokens = float(len(generated.split())) if generated else 0.0

    ref_unigram_recall = _metric(label_row, "reference_unigram_recall")
    old_source_overlap = _metric(label_row, "output_source_keyword_overlap")
    old_bucket = (t102c_row or {}).get("primary_bucket")
    reference_content_recall = content_recall(generated, reference)
    reference_content_precision = content_precision(generated, reference)
    reference_content_f1 = content_f1(generated, reference)
    source_content_recall = content_recall(generated, source)
    question_content_recall = content_recall(generated, question)
    entity_reference_recall = _entity_overlap(generated, reference)
    generic_ratio = _generic_ratio(generated)

    strong_reference = (reference_content_recall or 0.0) >= 0.30 or (
        (reference_content_f1 or 0.0) >= 0.20 and (entity_reference_recall is None or entity_reference_recall >= 0.25)
    )
    source_grounded = max(source_content_recall or 0.0, old_source_overlap or 0.0) >= 0.12
    question_focused = question_content_recall is None or question_content_recall >= 0.25
    low_reference = labels.get("low_reference_overlap") or (ref_unigram_recall is not None and ref_unigram_recall < 0.24)
    likely_off_target = (
        (reference_content_recall or 0.0) < 0.08
        and max(source_content_recall or 0.0, old_source_overlap or 0.0) < 0.08
    ) or (not question_focused and (reference_content_recall or 0.0) < 0.12)
    too_generic = output_tokens < 35 or generic_ratio >= 0.38

    if not generated or not reference:
        band = "unresolved_deterministic_limitation"
        outcome = "remaining_unexplained_uncertain"
        rationale = "Generated text or reference text is missing, so deterministic reassessment cannot improve the proxy."
    elif old_bucket == "evidence_miss_likely" and not (strong_reference or (source_grounded and question_focused)):
        band = "hard_quality_risk"
        outcome = "hard_risk"
        rationale = "The prior evidence-miss label remains hard risk because improved proxy support is still insufficient."
    elif not has_source_context and (old_source_overlap or 0.0) == 0.0:
        band = "unresolved_deterministic_limitation"
        outcome = "remaining_unexplained_uncertain"
        rationale = "Source context preview/support is unavailable, so deterministic reassessment cannot separate source grounding from proxy failure."
    elif strong_reference and source_grounded and question_focused:
        band = "strong_proxy_support"
        outcome = "reduced_uncertainty"
        rationale = "Normalized content terms align with the reference while source/question support remains adequate."
    elif likely_off_target:
        band = "hard_quality_risk"
        outcome = "hard_risk"
        rationale = "Improved content proxy still finds very low reference and source/question support."
    elif too_generic:
        band = "generic_or_under_specific"
        outcome = "hard_risk"
        rationale = "Output is too short or under-specific for deterministic QMSum quality comfort."
    elif low_reference and source_grounded and question_focused:
        band = "source_grounded_reference_mismatch"
        outcome = "explained_proxy_limitation"
        rationale = "Output is question-focused and source-grounded but remains lexically distant from the reference."
    elif (reference_content_recall or 0.0) >= 0.18 and question_focused:
        band = "moderate_proxy_support"
        outcome = "reduced_uncertainty"
        rationale = "Normalized content overlap improves enough to explain part of the old low-overlap warning."
    else:
        band = "unresolved_deterministic_limitation"
        outcome = "remaining_unexplained_uncertain"
        rationale = "Signals remain mixed after normalization, source split, and content-term reassessment."

    return {
        "fixture_id": fixture_id,
        "previous_t102b_proxy_uncertain": bool(labels.get("proxy_uncertain")),
        "previous_t102c_bucket": old_bucket,
        "improved_confidence_band": band,
        "improved_outcome": outcome,
        "rationale_short": rationale,
        "question_preview": question[:260],
        "reference_preview": reference[:360],
        "generated_preview": generated[:500],
        "generated_tail": generated[-260:],
        "metrics": {
            "reference_unigram_recall_old": ref_unigram_recall,
            "source_keyword_overlap_old": old_source_overlap,
            "reference_content_recall": reference_content_recall,
            "reference_content_precision": reference_content_precision,
            "reference_content_f1": reference_content_f1,
            "source_content_recall": source_content_recall,
            "question_content_recall": question_content_recall,
            "entity_reference_recall": entity_reference_recall,
            "generic_ratio": generic_ratio,
            "output_token_count": output_tokens,
        },
        "runtime": {
            "t_compress_ms": _metric(label_row, "t_compress_ms"),
            "e2e_time_s": _metric(label_row, "e2e_time_s"),
            "tokens_per_second": _metric(label_row, "tokens_per_second"),
            "tau_mean": _metric(label_row, "tau_mean"),
        },
    }


def build_summary(total_rows: int, label_rows: list[dict[str, Any]], reassessed_rows: list[dict[str, Any]]) -> dict[str, Any]:
    before_uncertain = sum(1 for row in label_rows if _labels(row).get("proxy_uncertain"))
    before_low_overlap = sum(1 for row in label_rows if _labels(row).get("low_reference_overlap"))
    before_hard = sum(1 for row in label_rows if _labels(row).get("possible_evidence_miss") or _labels(row).get("too_short_or_generic"))
    band_counts = Counter(row["improved_confidence_band"] for row in reassessed_rows)
    outcome_counts = Counter(row["improved_outcome"] for row in reassessed_rows)
    remaining_unexplained = outcome_counts["remaining_unexplained_uncertain"]
    hard_risk = outcome_counts["hard_risk"]
    explained = outcome_counts["explained_proxy_limitation"]
    reduced = outcome_counts["reduced_uncertainty"]
    materially_reduced = remaining_unexplained <= max(6, int(before_uncertain * 0.50))
    return {
        "task": "T102D",
        "total_rows": total_rows,
        "before": {
            "proxy_uncertain_rows": before_uncertain,
            "low_reference_overlap_rows": before_low_overlap,
            "possible_hard_risk_rows": before_hard,
        },
        "after": {
            "rows_reassessed": len(reassessed_rows),
            "remaining_unexplained_uncertain_rows": remaining_unexplained,
            "explained_proxy_limitation_rows": explained,
            "reduced_uncertainty_rows": reduced,
            "hard_risk_rows": hard_risk,
            "unresolved_rows": band_counts["unresolved_deterministic_limitation"],
            "confidence_band_counts": dict(sorted(band_counts.items())),
            "outcome_counts": dict(sorted(outcome_counts.items())),
            "materially_reduced": materially_reduced,
        },
        "comparison": {
            "uncertain_rows_before": before_uncertain,
            "remaining_unexplained_uncertain_after": remaining_unexplained,
            "absolute_uncertainty_reduction": before_uncertain - remaining_unexplained,
            "uncertainty_reduction_rate": round((before_uncertain - remaining_unexplained) / before_uncertain, 6)
            if before_uncertain
            else 0.0,
            "hard_risk_delta_vs_t102b_possible_evidence_miss": hard_risk - before_hard,
        },
    }


def build_claim_update(summary: dict[str, Any]) -> dict[str, Any]:
    after = summary.get("after", {})
    if after.get("materially_reduced") and after.get("remaining_unexplained_uncertain_rows", 0) <= 6:
        status = "SCOPED_WITH_IMPROVED_PROXY_CAVEAT"
    else:
        status = "SCOPED_WITH_UNRESOLVED_PROXY_RISK"
    return {
        "QMSum claim": {
            "status": status,
            "allowed_wording": [
                "QMSum Light GPU n30 now has an improved deterministic proxy reassessment that separates reference overlap, source grounding, output genericness, and remaining unresolved proxy limits.",
                "The reassessment can support benchmark-scoped QMSum proxy-risk reporting, not semantic correctness proof.",
            ],
            "blocked_wording": [
                "QMSum semantic correctness is proven.",
                "The improved proxy is equivalent to human semantic scoring.",
                "QMSum quality is fully solved.",
                "A QMSum n100 or full matrix result was run.",
            ],
            "limitations": [
                "No LLM judge or human semantic scoring was used.",
                "Rows marked source-grounded/reference-mismatch are not automatically correct.",
                "Hard-risk rows remain visible and are not relabeled as acceptable.",
            ],
        },
        "reason": {
            "before_proxy_uncertain_rows": summary.get("before", {}).get("proxy_uncertain_rows"),
            "remaining_unexplained_uncertain_rows": after.get("remaining_unexplained_uncertain_rows"),
            "hard_risk_rows": after.get("hard_risk_rows"),
            "materially_reduced": after.get("materially_reduced"),
        },
    }


def build_next_task_decision(summary: dict[str, Any]) -> dict[str, Any]:
    before_uncertain = summary.get("before", {}).get("proxy_uncertain_rows", 0)
    after = summary.get("after", {})
    remaining = after.get("remaining_unexplained_uncertain_rows", 0)
    hard_risk = after.get("hard_risk_rows", 0)
    unresolved = after.get("unresolved_rows", 0)
    materially_reduced = after.get("materially_reduced", False)
    hard_delta = summary.get("comparison", {}).get("hard_risk_delta_vs_t102b_possible_evidence_miss", 0)
    escalate = (
        remaining >= max(12, int(before_uncertain * 0.75))
        or unresolved >= 8
        or hard_risk >= 8
        or hard_delta >= 5
        or not materially_reduced
    )
    if escalate:
        return {
            "decision": "ESCALATE_TO_T102E",
            "next_task": "T102E — QMSum Manual Reference Alignment / Proxy Escalation",
            "reason": "Improved deterministic proxy did not reduce or bound uncertainty enough from existing artifacts.",
            "automatic_benchmark": False,
        }
    return {
        "decision": "PASS_WITH_CAVEAT",
        "next_task": "T103 — Reference Alignment for Speed Claim",
        "reason": "Improved deterministic proxy materially reduced unexplained uncertainty while preserving caveats and hard-risk rows.",
        "automatic_benchmark": False,
    }


def _write_comparison_table(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "fixture_id",
                "previous_t102c_bucket",
                "improved_confidence_band",
                "improved_outcome",
                "reference_unigram_recall_old",
                "reference_content_recall",
                "reference_content_f1",
                "source_keyword_overlap_old",
                "source_content_recall",
                "question_content_recall",
                "entity_reference_recall",
                "output_token_count",
                "rationale_short",
            ],
        )
        writer.writeheader()
        for row in rows:
            metrics = row["metrics"]
            writer.writerow(
                {
                    "fixture_id": row["fixture_id"],
                    "previous_t102c_bucket": row["previous_t102c_bucket"],
                    "improved_confidence_band": row["improved_confidence_band"],
                    "improved_outcome": row["improved_outcome"],
                    "reference_unigram_recall_old": metrics.get("reference_unigram_recall_old"),
                    "reference_content_recall": metrics.get("reference_content_recall"),
                    "reference_content_f1": metrics.get("reference_content_f1"),
                    "source_keyword_overlap_old": metrics.get("source_keyword_overlap_old"),
                    "source_content_recall": metrics.get("source_content_recall"),
                    "question_content_recall": metrics.get("question_content_recall"),
                    "entity_reference_recall": metrics.get("entity_reference_recall"),
                    "output_token_count": metrics.get("output_token_count"),
                    "rationale_short": row["rationale_short"],
                }
            )


def analyze(
    *,
    qmsum_jsonl: Path = DEFAULT_QMSUM_JSONL,
    row_labels: Path = DEFAULT_ROW_LABELS,
    t102c_triage: Path = DEFAULT_T102C_TRIAGE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    qmsum_rows = read_jsonl(qmsum_jsonl)
    label_rows = read_jsonl(row_labels)
    t102c_rows = read_jsonl(t102c_triage)
    qmsum_by_id = _index_by_fixture(qmsum_rows)
    t102c_by_id = _index_by_fixture(t102c_rows)
    uncertain_labels = [row for row in label_rows if _labels(row).get("proxy_uncertain") or _labels(row).get("low_reference_overlap")]
    reassessed = [
        reassess_row(
            qmsum_by_id.get(str(row.get("fixture_id") or row.get("dataset_id") or ""), {}),
            row,
            t102c_by_id.get(str(row.get("fixture_id") or row.get("dataset_id") or "")),
        )
        for row in uncertain_labels
    ]
    summary = build_summary(len(qmsum_rows), label_rows, reassessed)
    claim_update = build_claim_update(summary)
    next_task = build_next_task_decision(summary)
    result = {
        "decision": next_task["decision"],
        "summary": summary,
        "claim_update": claim_update,
        "next_task_decision": next_task,
        "inputs": {
            "qmsum_jsonl": str(qmsum_jsonl),
            "row_labels": str(row_labels),
            "t102c_triage": str(t102c_triage),
        },
        "method": {
            "model_loading": False,
            "llm_judge": False,
            "benchmark_run": False,
            "signals": [
                "normalized content-term reference overlap",
                "source-grounding overlap",
                "question-focus overlap",
                "entity/number reference overlap",
                "output length and genericness",
            ],
        },
    }
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[0], result)
    write_jsonl(output_dir / OUTPUT_RELATIVE_PATHS[1], reassessed)
    _write_comparison_table(output_dir / OUTPUT_RELATIVE_PATHS[2], reassessed)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[3], claim_update)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[4], next_task)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Improve deterministic QMSum proxy reassessment from existing artifacts.")
    parser.add_argument("--qmsum-jsonl", type=Path, default=DEFAULT_QMSUM_JSONL)
    parser.add_argument("--row-labels", type=Path, default=DEFAULT_ROW_LABELS)
    parser.add_argument("--t102c-triage", type=Path, default=DEFAULT_T102C_TRIAGE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = analyze(
        qmsum_jsonl=args.qmsum_jsonl,
        row_labels=args.row_labels,
        t102c_triage=args.t102c_triage,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "decision": result["decision"],
                "output_dir": str(args.output_dir),
                "remaining_unexplained_uncertain_rows": result["summary"]["after"][
                    "remaining_unexplained_uncertain_rows"
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
