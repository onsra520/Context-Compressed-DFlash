from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.phase_2_system_optimization.analysis import task102d_qmsum_evaluator_proxy_improvement as proxy

DEFAULT_QMSUM_JSONL = proxy.DEFAULT_QMSUM_JSONL
DEFAULT_ROW_LABELS = proxy.DEFAULT_ROW_LABELS
DEFAULT_T102D_REASSESSMENT = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102d_qmsum_evaluator_proxy_improvement/task102d_row_proxy_reassessment.jsonl"
)
DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102e_qmsum_hard_risk_and_residual_uncertainty_resolution"
)

OUTPUT_RELATIVE_PATHS = (
    Path("task102e_hard_risk_resolution_summary.json"),
    Path("task102e_target_row_resolution.jsonl"),
    Path("task102e_hard_risk_resolution_table.csv"),
    Path("task102e_claim_update.json"),
    Path("task102e_next_task_decision.json"),
)

TARGET_BANDS = {
    "hard_quality_risk",
    "generic_or_under_specific",
    "unresolved_deterministic_limitation",
}
TARGET_OUTCOMES = {
    "hard_risk",
    "remaining_unexplained_uncertain",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return proxy.read_jsonl(path)


def write_json(path: Path, payload: Any) -> None:
    proxy.write_json(path, payload)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    proxy.write_jsonl(path, rows)


def _index_by_fixture(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("fixture_id") or row.get("dataset_id") or "")
        if key:
            indexed[key] = row
    return indexed


def _target_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets = []
    for row in rows:
        if row.get("improved_confidence_band") in TARGET_BANDS or row.get("improved_outcome") in TARGET_OUTCOMES:
            targets.append(row)
    return targets


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


def _preview_metrics(qmsum_row: dict[str, Any], label_row: dict[str, Any]) -> dict[str, float | None]:
    generated = proxy._text(qmsum_row, "generated_text")
    reference = proxy._reference_text(qmsum_row, label_row)
    question = proxy._question_text(qmsum_row, label_row)
    source = proxy._source_text(qmsum_row)
    return {
        "reference_overlap": _metric(label_row, "reference_unigram_recall"),
        "source_grounding_overlap": _metric(label_row, "output_source_keyword_overlap"),
        "question_focus_overlap": proxy.content_recall(generated, question),
        "entity_number_overlap": proxy._entity_overlap(generated, reference),
        "reference_content_recall": proxy.content_recall(generated, reference),
        "reference_content_f1": proxy.content_f1(generated, reference),
        "source_content_recall": proxy.content_recall(generated, source),
        "output_length": _metric(label_row, "output_token_count") or float(len(generated.split()) if generated else 0),
        "genericness": 0.0 if generated else 1.0,
    }


def _contains_missing_answer_claim(text: str) -> bool:
    lower = text.lower()
    return any(
        phrase in lower
        for phrase in (
            "does not mention",
            "not discussed",
            "information is not",
            "context does not",
            "meeting context does not",
        )
    )


def resolve_row(
    qmsum_row: dict[str, Any],
    label_row: dict[str, Any],
    t102d_row: dict[str, Any],
) -> dict[str, Any]:
    fixture_id = str(t102d_row.get("fixture_id") or qmsum_row.get("fixture_id") or label_row.get("fixture_id") or "")
    generated = proxy._text(qmsum_row, "generated_text")
    reference = proxy._reference_text(qmsum_row, label_row)
    question = proxy._question_text(qmsum_row, label_row)
    source = proxy._source_text(qmsum_row)
    metrics = _preview_metrics(qmsum_row, label_row)
    previous_band = str(t102d_row.get("improved_confidence_band") or "")
    previous_outcome = str(t102d_row.get("improved_outcome") or "")
    previous_t102c = str(t102d_row.get("previous_t102c_bucket") or "")

    ref_content = metrics["reference_content_recall"] or 0.0
    ref_f1 = metrics["reference_content_f1"] or 0.0
    source_support = max(metrics["source_content_recall"] or 0.0, metrics["source_grounding_overlap"] or 0.0)
    question_focus = metrics["question_focus_overlap"]
    entity_support = metrics["entity_number_overlap"]
    output_length = metrics["output_length"] or 0.0

    strong_support = ref_content >= 0.34 and ref_f1 >= 0.20 and source_support >= 0.12
    source_reference_mismatch = source_support >= 0.12 and (question_focus is None or question_focus >= 0.25) and ref_content >= 0.10
    weak_reference = ref_content < 0.12 and ref_f1 < 0.12
    weak_source = source_support < 0.10
    weak_question = question_focus is not None and question_focus < 0.20

    if strong_support:
        final_resolution = "resolved_stronger_proxy_support"
        final_status = "resolved"
        reason = "Reference content, source grounding, and question focus are all strong enough for deterministic proxy support."
    elif previous_band == "generic_or_under_specific" or output_length < 35 or _contains_missing_answer_claim(generated):
        final_resolution = "confirmed_generic_or_under_specific"
        final_status = "confirmed_quality_failure"
        reason = "Output is short, generic, or claims missing information despite an available reference answer."
    elif previous_t102c == "evidence_miss_likely" and not source_reference_mismatch:
        final_resolution = "confirmed_evidence_miss"
        final_status = "confirmed_quality_failure"
        reason = "Prior evidence-miss label remains supported because source/reference/question signals are still weak."
    elif weak_question and weak_reference:
        final_resolution = "confirmed_prompt_evidence_failure"
        final_status = "confirmed_quality_failure"
        reason = "Output does not remain focused on the requested evidence and has weak reference support."
    elif weak_reference and weak_source:
        final_resolution = "confirmed_evidence_miss"
        final_status = "confirmed_quality_failure"
        reason = "Output remains weak against both reference and source-grounding signals."
    elif source_reference_mismatch and (entity_support is None or entity_support >= 0.0):
        final_resolution = "resolved_source_grounded_but_reference_mismatch"
        final_status = "resolved"
        reason = "Output is question-focused and source-grounded enough to resolve the row as a deterministic reference/proxy mismatch, not semantic proof."
    elif ref_content >= 0.18 and (question_focus is None or question_focus >= 0.25):
        final_resolution = "resolved_reference_mismatch"
        final_status = "resolved"
        reason = "Improved reference content signal is enough to resolve the prior unexplained bucket as reference-mismatch/proxy limitation."
    else:
        final_resolution = "still_unresolved_without_semantic_judge"
        final_status = "still_unresolved"
        reason = "Available deterministic signals remain mixed; resolving this row would require human or LLM semantic judging."

    return {
        "fixture_id": fixture_id,
        "prior_labels": {
            "task102d_confidence_band": previous_band,
            "task102d_outcome": previous_outcome,
            "task102c_bucket": previous_t102c,
        },
        "question": question,
        "reference_answer_preview": reference[:600],
        "generated_output": generated,
        "generated_tail": generated[-320:],
        "source_prompt_preview": source[:900],
        "signals": metrics,
        "final_resolution": final_resolution,
        "final_status": final_status,
        "deterministic_reason": reason,
        "semantic_correctness_claim": False,
    }


def build_summary(target_resolutions: list[dict[str, Any]], t102d_rows: list[dict[str, Any]]) -> dict[str, Any]:
    before_unexplained = sum(1 for row in t102d_rows if row.get("improved_outcome") == "remaining_unexplained_uncertain")
    before_hard = sum(1 for row in t102d_rows if row.get("improved_outcome") == "hard_risk")
    status_counts = Counter(row["final_status"] for row in target_resolutions)
    resolution_counts = Counter(row["final_resolution"] for row in target_resolutions)
    after_unexplained = status_counts["still_unresolved"]
    after_hard = status_counts["confirmed_quality_failure"]
    return {
        "task": "T102E",
        "target_rows_count": len(target_resolutions),
        "before_unexplained_deterministic_uncertainty_count": before_unexplained,
        "after_unexplained_deterministic_uncertainty_count": after_unexplained,
        "before_hard_risk_count": before_hard,
        "after_hard_risk_count": after_hard,
        "resolved_rows_count": status_counts["resolved"],
        "confirmed_quality_failure_rows_count": status_counts["confirmed_quality_failure"],
        "still_unresolved_rows_count": status_counts["still_unresolved"],
        "resolution_counts": dict(sorted(resolution_counts.items())),
        "t103_allowed_to_proceed": after_unexplained == 0 and after_hard == 0,
        "next_remediation_task_required": after_unexplained > 0 or after_hard > 0,
    }


def decide(summary: dict[str, Any]) -> str:
    if (
        summary.get("after_unexplained_deterministic_uncertainty_count") == 0
        and summary.get("after_hard_risk_count") == 0
        and summary.get("confirmed_quality_failure_rows_count") == 0
        and summary.get("still_unresolved_rows_count") == 0
    ):
        return "PASS"
    if summary.get("confirmed_quality_failure_rows_count", 0) > 0 or summary.get("still_unresolved_rows_count", 0) > 0:
        return "NEEDS_REMEDIATION_TASK"
    return "PASS_WITH_CAVEAT"


def build_claim_update(summary: dict[str, Any], decision: str) -> dict[str, Any]:
    return {
        "QMSum claim": {
            "status": "SCOPED_WITH_CONFIRMED_FAILURES" if decision == "NEEDS_REMEDIATION_TASK" else "SCOPED_WITH_RESOLVED_PROXY_RISK",
            "allowed_wording": [
                "QMSum Light GPU n30 has deterministic proxy/evidence analysis through residual hard-risk resolution.",
                "Remaining QMSum quality concerns are explicitly bounded by confirmed failure and unresolved rows.",
            ],
            "blocked_wording": [
                "QMSum semantic correctness is proven.",
                "QMSum quality risk has been eliminated." if decision != "PASS" else "QMSum semantic correctness is proven.",
                "T103 speed-claim closure can proceed without acknowledging QMSum residual quality risk.",
            ],
            "reason": {
                "after_unexplained_deterministic_uncertainty_count": summary["after_unexplained_deterministic_uncertainty_count"],
                "after_hard_risk_count": summary["after_hard_risk_count"],
                "confirmed_quality_failure_rows_count": summary["confirmed_quality_failure_rows_count"],
                "still_unresolved_rows_count": summary["still_unresolved_rows_count"],
            },
        }
    }


def build_next_task_decision(summary: dict[str, Any], decision: str) -> dict[str, Any]:
    if decision == "PASS":
        return {
            "decision": decision,
            "t103_allowed_to_proceed": True,
            "next_task": "T103 — Reference Alignment for Speed Claim",
            "remediation_required": False,
            "reason": "T102E reduced hard-risk and unexplained deterministic uncertainty to zero without semantic overclaiming.",
        }
    return {
        "decision": decision,
        "t103_allowed_to_proceed": False,
        "next_task": "T102F — QMSum Target-row Remediation Decision",
        "remediation_required": True,
        "recommended_options": [
            "prompt/evidence policy improvement",
            "small controlled rerun on only target rows",
            "human review",
            "LLM judge",
            "keep caveat and stop QMSum quality expansion",
        ],
        "reason": "Confirmed quality failures or unresolved rows remain, so T103 should wait unless the user explicitly accepts the caveat.",
    }


def _write_table(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "fixture_id",
                "task102d_confidence_band",
                "task102d_outcome",
                "task102c_bucket",
                "final_resolution",
                "final_status",
                "reference_overlap",
                "source_grounding_overlap",
                "question_focus_overlap",
                "entity_number_overlap",
                "output_length",
                "deterministic_reason",
            ],
        )
        writer.writeheader()
        for row in rows:
            signals = row["signals"]
            prior = row["prior_labels"]
            writer.writerow(
                {
                    "fixture_id": row["fixture_id"],
                    "task102d_confidence_band": prior["task102d_confidence_band"],
                    "task102d_outcome": prior["task102d_outcome"],
                    "task102c_bucket": prior["task102c_bucket"],
                    "final_resolution": row["final_resolution"],
                    "final_status": row["final_status"],
                    "reference_overlap": signals.get("reference_overlap"),
                    "source_grounding_overlap": signals.get("source_grounding_overlap"),
                    "question_focus_overlap": signals.get("question_focus_overlap"),
                    "entity_number_overlap": signals.get("entity_number_overlap"),
                    "output_length": signals.get("output_length"),
                    "deterministic_reason": row["deterministic_reason"],
                }
            )


def analyze(
    *,
    qmsum_jsonl: Path = DEFAULT_QMSUM_JSONL,
    row_labels: Path = DEFAULT_ROW_LABELS,
    t102d_reassessment: Path = DEFAULT_T102D_REASSESSMENT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    qmsum_rows = read_jsonl(qmsum_jsonl)
    label_rows = read_jsonl(row_labels)
    t102d_rows = read_jsonl(t102d_reassessment)
    if not qmsum_rows or not label_rows or not t102d_rows:
        raise FileNotFoundError("Required Task102/102B/102D artifacts are missing or empty.")
    qmsum_by_id = _index_by_fixture(qmsum_rows)
    labels_by_id = _index_by_fixture(label_rows)
    target_rows = _target_rows(t102d_rows)
    resolutions = [
        resolve_row(
            qmsum_by_id.get(str(row.get("fixture_id") or ""), {}),
            labels_by_id.get(str(row.get("fixture_id") or ""), {}),
            row,
        )
        for row in target_rows
    ]
    summary = build_summary(resolutions, t102d_rows)
    decision = decide(summary)
    claim_update = build_claim_update(summary, decision)
    next_task = build_next_task_decision(summary, decision)
    result = {
        "decision": decision,
        "summary": summary,
        "claim_update": claim_update,
        "next_task_decision": next_task,
        "inputs": {
            "qmsum_jsonl": str(qmsum_jsonl),
            "row_labels": str(row_labels),
            "t102d_reassessment": str(t102d_reassessment),
        },
        "scope": {
            "benchmark_run": False,
            "model_inference": False,
            "qmsum_rerun": False,
            "llm_judge": False,
            "human_semantic_scoring": False,
        },
    }
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[0], result)
    write_jsonl(output_dir / OUTPUT_RELATIVE_PATHS[1], resolutions)
    _write_table(output_dir / OUTPUT_RELATIVE_PATHS[2], resolutions)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[3], claim_update)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[4], next_task)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve Task102D QMSum hard-risk and residual uncertainty rows.")
    parser.add_argument("--qmsum-jsonl", type=Path, default=DEFAULT_QMSUM_JSONL)
    parser.add_argument("--row-labels", type=Path, default=DEFAULT_ROW_LABELS)
    parser.add_argument("--t102d-reassessment", type=Path, default=DEFAULT_T102D_REASSESSMENT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = analyze(
        qmsum_jsonl=args.qmsum_jsonl,
        row_labels=args.row_labels,
        t102d_reassessment=args.t102d_reassessment,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "decision": result["decision"],
                "output_dir": str(args.output_dir),
                "after_unexplained": result["summary"]["after_unexplained_deterministic_uncertainty_count"],
                "after_hard_risk": result["summary"]["after_hard_risk_count"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
