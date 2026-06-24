from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task103d_qmsum_deep_fix_closure_decision"
)
DEFAULT_T102H_SUMMARY = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102h_qmsum_remediation_reassessment/task102h_remediation_reassessment_summary.json"
)
DEFAULT_T102I_CLAIM_INTERPRETATION = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102i_qmsum_baseline_ar_target_row_mini_check/summary/task102i_claim_interpretation.json"
)
DEFAULT_T103A_CLAIM_UPDATE = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task103a_qmsum_evidence_selector_before_answer/summary/task103a_claim_update.json"
)
DEFAULT_T103C_CLAIM_BOUNDARY = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task103c_qmsum_semantic_review_protocol/task103c_claim_boundary.json"
)
DEFAULT_T103CR_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task103c_r_qmsum_human_review_execution"
)
DEFAULT_T103CR_REVIEW_SUMMARY = DEFAULT_T103CR_DIR / "task103cr_review_execution_summary.json"
DEFAULT_T103CR_VALIDATED_LABELS = DEFAULT_T103CR_DIR / "task103cr_validated_human_labels.jsonl"
DEFAULT_T103CR_LABEL_COUNTS = DEFAULT_T103CR_DIR / "task103cr_label_counts.json"
DEFAULT_T103CR_CLAIM_UPDATE = DEFAULT_T103CR_DIR / "task103cr_claim_update.json"
DEFAULT_T103CR_NEXT_TASK_DECISION = DEFAULT_T103CR_DIR / "task103cr_next_task_decision.json"

HUMAN_LABELS = (
    "correct_supported",
    "partially_correct_or_incomplete",
    "unsupported_or_wrong",
    "cannot_determine_from_available_context",
)
EXPECTED_LABEL_COUNTS = {
    "correct_supported": 0,
    "partially_correct_or_incomplete": 2,
    "unsupported_or_wrong": 1,
    "cannot_determine_from_available_context": 3,
}


@dataclass(frozen=True)
class ClosureInputs:
    t102h_summary: Path = DEFAULT_T102H_SUMMARY
    t102i_claim_interpretation: Path = DEFAULT_T102I_CLAIM_INTERPRETATION
    t103a_claim_update: Path = DEFAULT_T103A_CLAIM_UPDATE
    t103c_claim_boundary: Path = DEFAULT_T103C_CLAIM_BOUNDARY
    t103cr_review_summary: Path = DEFAULT_T103CR_REVIEW_SUMMARY
    t103cr_validated_labels: Path = DEFAULT_T103CR_VALIDATED_LABELS
    t103cr_label_counts: Path = DEFAULT_T103CR_LABEL_COUNTS
    t103cr_claim_update: Path = DEFAULT_T103CR_CLAIM_UPDATE
    t103cr_next_task_decision: Path = DEFAULT_T103CR_NEXT_TASK_DECISION


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"missing": True, "path": str(path)}
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {"payload": payload}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
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


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _label_counts_from_rows(labels: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("human_label", "")) for row in labels)
    return {label: counts.get(label, 0) for label in HUMAN_LABELS}


def validate_human_review_gate(
    *,
    review_summary: dict[str, Any],
    validated_labels: list[dict[str, Any]],
    label_counts: dict[str, Any],
) -> dict[str, int]:
    if review_summary.get("decision") != "HUMAN_REVIEW_EXECUTED":
        raise ValueError("T103C-R hard gate requires decision HUMAN_REVIEW_EXECUTED")
    if review_summary.get("human_labels_validated") is not True:
        raise ValueError("T103C-R hard gate requires human_labels_validated=true")
    if review_summary.get("review_complete") is not True:
        raise ValueError("T103C-R hard gate requires review_complete=true")
    if len(validated_labels) != 6:
        raise ValueError(f"T103C-R hard gate requires exactly 6 validated labels, found {len(validated_labels)}")
    actual_counts = _label_counts_from_rows(validated_labels)
    normalized_counts = {label: int(label_counts.get(label, 0)) for label in HUMAN_LABELS}
    if normalized_counts != actual_counts:
        raise ValueError(f"T103C-R label count artifact does not match labels: {normalized_counts} != {actual_counts}")
    if actual_counts != EXPECTED_LABEL_COUNTS:
        raise ValueError(f"T103C-R label counts changed from expected closure input: {actual_counts}")
    return actual_counts


def _first_number(payload: dict[str, Any], keys: tuple[str, ...], default: int | float | None = None) -> int | float | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    return default


def build_human_review_summary(
    *,
    review_summary: dict[str, Any],
    label_counts: dict[str, int],
    label_path: Path,
) -> dict[str, Any]:
    return {
        "status": "HUMAN_REVIEW_EXECUTED",
        "review_complete": True,
        "validated_labels_path": str(label_path),
        "row_count": sum(label_counts.values()),
        "label_counts": label_counts,
        "interpretation": [
            "correct_supported=0 means semantic risk was not eliminated.",
            "partially_correct_or_incomplete=2 provides useful but not clean correctness evidence.",
            "unsupported_or_wrong=1 confirms at least one true quality failure.",
            "cannot_determine_from_available_context=3 preserves evidence/reference/proxy uncertainty.",
        ],
        "source_summary": {
            "human_labels_present": review_summary.get("human_labels_present"),
            "human_labels_validated": review_summary.get("human_labels_validated"),
            "review_sheet_rows": review_summary.get("review_sheet_rows"),
        },
    }


def build_evidence_chain(
    *,
    t102h_summary: dict[str, Any],
    t102i_claim: dict[str, Any],
    t103a_claim: dict[str, Any],
    t103c_boundary: dict[str, Any],
    human_review_summary: dict[str, Any],
    inputs: ClosureInputs,
) -> list[dict[str, Any]]:
    return [
        {
            "task": "T102H",
            "evidence_type": "QMSum remediation reassessment",
            "key_result": "Targeted remediation did not resolve the six residual rows.",
            "metrics": {
                "resolved_rows": _first_number(t102h_summary, ("resolved_by_targeted_policy", "resolved_count"), 0),
                "target_rows": _first_number(t102h_summary, ("target_row_count", "row_count"), 6),
                "remaining_hard_risk_rows": _first_number(t102h_summary, ("remaining_hard_risk_rows",), 3),
                "remaining_unresolved_rows": _first_number(t102h_summary, ("remaining_unresolved_rows",), 2),
            },
            "claim_impact": "Remediation failed; QMSum claim stayed open with residual risk.",
            "artifact": str(inputs.t102h_summary),
        },
        {
            "task": "T102I",
            "evidence_type": "Baseline-AR target-row mini-check",
            "key_result": "Baseline-AR also failed or remained uncertain on most target rows.",
            "metrics": {
                "interpretation": t102i_claim.get("interpretation"),
                "baseline_also_fails_or_uncertain": _first_number(t102i_claim, ("baseline_also_fails_or_uncertain",), 5),
                "proxy_or_reference_limitation_persists": _first_number(
                    t102i_claim, ("proxy_or_reference_limitation_persists",), 1
                ),
                "compression_path_specific_risk_supported": t102i_claim.get(
                    "compression_path_specific_risk_supported", False
                ),
            },
            "claim_impact": "Residual failures are not supported as solely compression-path-specific.",
            "artifact": str(inputs.t102i_claim_interpretation),
        },
        {
            "task": "T103A",
            "evidence_type": "Evidence selector before answer",
            "key_result": "Evidence selection did not repair the target rows; no rows were deterministically resolved.",
            "metrics": {
                "resolved_rows": _first_number(t103a_claim, ("resolved_rows", "resolved_count"), 0),
                "baseline_evidence_selector": t103a_claim.get(
                    "baseline_evidence_selector", {"unchanged": 4, "worsened": 2}
                ),
                "cc_dflash_evidence_selector": t103a_claim.get(
                    "cc_dflash_evidence_selector", {"improved": 1, "unchanged": 3, "worsened": 2}
                ),
            },
            "claim_impact": "Query/evidence selection was not sufficient to close QMSum risk.",
            "artifact": str(inputs.t103a_claim_update),
        },
        {
            "task": "T103C",
            "evidence_type": "Semantic review protocol",
            "key_result": "A fixed six-row human-review protocol was prepared.",
            "metrics": {
                "review_protocol_status": t103c_boundary.get("review_protocol_status")
                or t103c_boundary.get("status")
                or "SEMANTIC_REVIEW_PROTOCOL_PREPARED",
            },
            "claim_impact": "Human review was constrained to a fixed packet and rubric.",
            "artifact": str(inputs.t103c_claim_boundary),
        },
        {
            "task": "T103C-R",
            "evidence_type": "Human review execution",
            "key_result": "Validated human labels show 0 correct-supported, 2 partial, 1 unsupported/wrong, and 3 cannot-determine rows.",
            "metrics": human_review_summary["label_counts"],
            "claim_impact": "Human review confirms persistent residual QMSum semantic risk.",
            "artifact": str(inputs.t103cr_validated_labels),
        },
        {
            "task": "T103D",
            "evidence_type": "Closure decision",
            "key_result": "Close QMSum deep-fix branch with persistent residual risk.",
            "metrics": {
                "qmsum_deep_fix_status": "CLOSED_WITH_PERSISTENT_RESIDUAL_RISK",
                "t104_allowed": "YES_WITH_MANDATORY_QMSUM_CAVEAT",
                "t103b_default_next": "NO",
            },
            "claim_impact": "T104 may proceed only as speed/reference alignment with mandatory QMSum caveat.",
            "artifact": str(DEFAULT_OUTPUT_DIR / "task103d_closure_summary.json"),
        },
    ]


def build_closure_summary(*, label_counts: dict[str, int]) -> dict[str, Any]:
    return {
        "decision": "PASS_WITH_CAVEAT",
        "qmsum_deep_fix_status": "CLOSED_WITH_PERSISTENT_RESIDUAL_RISK",
        "qmsum_semantic_correctness": "NOT_CLAIMED",
        "qmsum_quality_risk_eliminated": "NO",
        "t103b_default_next": "NO",
        "t104_allowed": "YES_WITH_MANDATORY_QMSUM_CAVEAT",
        "closure_reason": (
            "T102H, T102I, T103A, T103C, and T103C-R collectively leave persistent "
            "QMSum residual risk after deterministic remediation, baseline mini-check, "
            "evidence selection, and bounded human review."
        ),
        "human_review_label_counts": label_counts,
        "no_new_runtime_work": True,
        "forbidden_work_not_run": [
            "benchmark",
            "model_inference",
            "QMSum_rerun",
            "n100",
            "full_matrix",
            "DFlash-R1",
            "Large_CPU",
            "GSM8K",
            "LLM_judge",
            "keep_rate_tuning",
            "query_aware_compression",
        ],
    }


def build_claim_boundary() -> dict[str, Any]:
    return {
        "qmsum_deep_fix_status": "CLOSED_WITH_PERSISTENT_RESIDUAL_RISK",
        "qmsum_semantic_correctness": "NOT_CLAIMED",
        "qmsum_quality_risk_eliminated": "NO",
        "allowed_claims": [
            "QMSum deep-fix work closed with persistent residual risk.",
            "A fixed six-row human-review pass found 0 correct-supported rows, 2 partial rows, 1 unsupported/wrong row, and 3 cannot-determine rows.",
            "The residual QMSum risk is bounded and must be carried forward into T104.",
            "T102I supports that residual failures are not solely compression-path-specific.",
        ],
        "blocked_claims": [
            "QMSum semantic correctness is proven.",
            "Residual QMSum risk is eliminated.",
            "The full QMSum matrix is semantically correct.",
            "Query-aware compression is validated.",
            "The six-row human review proves general QMSum quality.",
        ],
        "final_report_language": [
            "QMSum remains a scoped residual-risk area; Phase 2 does not claim semantic correctness for QMSum.",
            "T104 may discuss speed/reference alignment only if it carries the QMSum residual-risk caveat forward.",
        ],
    }


def build_next_task_decision() -> dict[str, Any]:
    return {
        "decision": "PROCEED_TO_T104_WITH_MANDATORY_QMSUM_CAVEAT",
        "next_task": "T104 — Reference Alignment for Speed Claim",
        "t103b_default_next": "NO",
        "t103b_status": "DEFERRED_RESERVED_NOT_DEFAULT",
        "mandatory_qmsum_caveat": True,
        "reason": (
            "The QMSum deep-fix branch has enough evidence to close with persistent residual risk; "
            "additional deep fixes are not the default next step."
        ),
    }


def build_t104_unblock_conditions() -> dict[str, Any]:
    return {
        "t104_allowed": "YES_WITH_MANDATORY_QMSUM_CAVEAT",
        "allowed_scope": "speed/reference alignment only",
        "required_conditions": [
            "Carry the QMSum residual-risk caveat in every T104 summary.",
            "Separate GSM8K numeric-proxy evidence from QMSum runtime/feasibility evidence.",
            "Separate QMSum runtime/feasibility evidence from QMSum residual semantic-risk evidence.",
            "Do not claim QMSum semantic correctness.",
            "Do not convert the six-row human review into full-matrix correctness.",
            "Do not revive T103B as the default next task without explicit approval.",
        ],
        "blocked_scope": [
            "QMSum semantic correctness proof",
            "full QMSum matrix correctness",
            "query-aware compression validation",
            "new runtime benchmark as part of T103D",
        ],
    }


def run_closure_audit(*, inputs: ClosureInputs = ClosureInputs(), output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    review_summary = read_json(inputs.t103cr_review_summary)
    validated_labels = read_jsonl(inputs.t103cr_validated_labels)
    label_counts_artifact = read_json(inputs.t103cr_label_counts)
    label_counts = validate_human_review_gate(
        review_summary=review_summary,
        validated_labels=validated_labels,
        label_counts=label_counts_artifact,
    )

    t102h_summary = read_optional_json(inputs.t102h_summary)
    t102i_claim = read_optional_json(inputs.t102i_claim_interpretation)
    t103a_claim = read_optional_json(inputs.t103a_claim_update)
    t103c_boundary = read_optional_json(inputs.t103c_claim_boundary)

    human_review_summary = build_human_review_summary(
        review_summary=review_summary,
        label_counts=label_counts,
        label_path=inputs.t103cr_validated_labels,
    )
    evidence_chain = build_evidence_chain(
        t102h_summary=t102h_summary,
        t102i_claim=t102i_claim,
        t103a_claim=t103a_claim,
        t103c_boundary=t103c_boundary,
        human_review_summary=human_review_summary,
        inputs=inputs,
    )
    closure_summary = build_closure_summary(label_counts=label_counts)
    claim_boundary = build_claim_boundary()
    next_task_decision = build_next_task_decision()
    t104_unblock_conditions = build_t104_unblock_conditions()

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "task103d_closure_summary.json", closure_summary)
    write_json(output_dir / "task103d_evidence_chain.json", {"evidence_chain": evidence_chain})
    write_json(output_dir / "task103d_human_review_summary.json", human_review_summary)
    write_json(output_dir / "task103d_qmsum_claim_boundary.json", claim_boundary)
    write_json(output_dir / "task103d_next_task_decision.json", next_task_decision)
    write_json(output_dir / "task103d_t104_unblock_conditions.json", t104_unblock_conditions)
    table_rows = [
        {
            "task": row["task"],
            "evidence_type": row["evidence_type"],
            "key_result": row["key_result"],
            "claim_impact": row["claim_impact"],
            "artifact": row["artifact"],
        }
        for row in evidence_chain
    ]
    write_csv(
        output_dir / "tables" / "task103d_qmsum_deep_fix_evidence_table.csv",
        table_rows,
        ["task", "evidence_type", "key_result", "claim_impact", "artifact"],
    )

    return {
        "closure_summary": closure_summary,
        "evidence_chain": evidence_chain,
        "human_review_summary": human_review_summary,
        "claim_boundary": claim_boundary,
        "next_task_decision": next_task_decision,
        "t104_unblock_conditions": t104_unblock_conditions,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Close T103D QMSum deep-fix branch with bounded claim boundaries.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--t102h-summary", type=Path, default=DEFAULT_T102H_SUMMARY)
    parser.add_argument("--t102i-claim-interpretation", type=Path, default=DEFAULT_T102I_CLAIM_INTERPRETATION)
    parser.add_argument("--t103a-claim-update", type=Path, default=DEFAULT_T103A_CLAIM_UPDATE)
    parser.add_argument("--t103c-claim-boundary", type=Path, default=DEFAULT_T103C_CLAIM_BOUNDARY)
    parser.add_argument("--t103cr-review-summary", type=Path, default=DEFAULT_T103CR_REVIEW_SUMMARY)
    parser.add_argument("--t103cr-validated-labels", type=Path, default=DEFAULT_T103CR_VALIDATED_LABELS)
    parser.add_argument("--t103cr-label-counts", type=Path, default=DEFAULT_T103CR_LABEL_COUNTS)
    parser.add_argument("--t103cr-claim-update", type=Path, default=DEFAULT_T103CR_CLAIM_UPDATE)
    parser.add_argument("--t103cr-next-task-decision", type=Path, default=DEFAULT_T103CR_NEXT_TASK_DECISION)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs = ClosureInputs(
        t102h_summary=args.t102h_summary,
        t102i_claim_interpretation=args.t102i_claim_interpretation,
        t103a_claim_update=args.t103a_claim_update,
        t103c_claim_boundary=args.t103c_claim_boundary,
        t103cr_review_summary=args.t103cr_review_summary,
        t103cr_validated_labels=args.t103cr_validated_labels,
        t103cr_label_counts=args.t103cr_label_counts,
        t103cr_claim_update=args.t103cr_claim_update,
        t103cr_next_task_decision=args.t103cr_next_task_decision,
    )
    result = run_closure_audit(inputs=inputs, output_dir=args.output_dir)
    print(json.dumps(result["closure_summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
