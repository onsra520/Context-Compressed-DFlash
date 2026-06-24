from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_REVIEW_PACKET = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task103c_qmsum_semantic_review_protocol/task103c_review_packet.jsonl"
)
DEFAULT_RUBRIC = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task103c_qmsum_semantic_review_protocol/task103c_review_rubric.json"
)
DEFAULT_CLAIM_BOUNDARY = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task103c_qmsum_semantic_review_protocol/task103c_claim_boundary.json"
)
DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task103c_r_qmsum_human_review_execution"
)

ALLOWED_HUMAN_LABELS = (
    "correct_supported",
    "partially_correct_or_incomplete",
    "unsupported_or_wrong",
    "cannot_determine_from_available_context",
)
ALLOWED_CONFIDENCE = ("", "low", "medium", "high")
BOOLEAN_COLUMNS = (
    "answers_question",
    "uses_correct_evidence",
    "complete_enough",
    "hallucination_or_unsupported",
    "not_discussed_error",
)
ALLOWED_BOOL_VALUES = ("", "true", "false")

REVIEW_SHEET_COLUMNS = (
    "fixture_id",
    "question",
    "reference_answer",
    "selected_evidence",
    "original_cc_dflash_output",
    "remediated_cc_dflash_output",
    "baseline_ar_output",
    "evidence_selected_baseline_output",
    "evidence_selected_cc_dflash_output",
    "deterministic_status",
    "human_label",
    "confidence",
    "answers_question",
    "uses_correct_evidence",
    "complete_enough",
    "hallucination_or_unsupported",
    "not_discussed_error",
    "review_notes",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _outputs(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("outputs")
    return value if isinstance(value, dict) else {}


def _deterministic_status(row: dict[str, Any]) -> str:
    labels = row.get("deterministic_labels")
    if not isinstance(labels, dict):
        return ""
    parts = []
    for key in (
        "task102h_final_risk_bucket",
        "task102h_remediation_outcome",
        "task102i_baseline_category",
        "task103a_baseline_evidence_category",
        "task103a_cc_evidence_category",
    ):
        value = labels.get(key)
        if value not in (None, ""):
            parts.append(f"{key}={value}")
    return "; ".join(parts)


def _sheet_row(packet_row: dict[str, Any]) -> dict[str, str]:
    outputs = _outputs(packet_row)
    return {
        "fixture_id": str(packet_row.get("fixture_id", "")),
        "question": str(packet_row.get("question", "")),
        "reference_answer": str(packet_row.get("reference_answer", "")),
        "selected_evidence": str(packet_row.get("selected_source_evidence", "")),
        "original_cc_dflash_output": str(outputs.get("original_cc_dflash", "")),
        "remediated_cc_dflash_output": str(outputs.get("remediated_cc_dflash", "")),
        "baseline_ar_output": str(outputs.get("baseline_ar", "")),
        "evidence_selected_baseline_output": str(outputs.get("evidence_selected_baseline_ar", "")),
        "evidence_selected_cc_dflash_output": str(outputs.get("evidence_selected_cc_dflash", "")),
        "deterministic_status": _deterministic_status(packet_row),
        "human_label": "",
        "confidence": "",
        "answers_question": "",
        "uses_correct_evidence": "",
        "complete_enough": "",
        "hallucination_or_unsupported": "",
        "not_discussed_error": "",
        "review_notes": "",
    }


def write_review_sheet(path: Path, packet_rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_SHEET_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(_sheet_row(row) for row in packet_rows)


def write_reviewer_instructions(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    allowed = ", ".join(f"`{label}`" for label in ALLOWED_HUMAN_LABELS)
    path.write_text(
        "\n".join(
            [
                "# Task103C-R Human Review Instructions",
                "",
                "Fill `task103cr_human_labels_input.csv` using the same columns as the review sheet.",
                "",
                "Allowed `human_label` values:",
                "",
                f"- {allowed}",
                "",
                "Allowed `confidence` values: empty, `low`, `medium`, `high`.",
                "",
                "Boolean columns may be empty, `true`, or `false`.",
                "",
                "Use only the packet content. Do not use external knowledge. If the available context is insufficient, use `cannot_determine_from_available_context`.",
                "",
                "This task does not run an LLM judge and does not infer labels automatically.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in REVIEW_SHEET_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"missing required columns: {missing}")
        return [dict(row) for row in reader]


def _normalize_bool(value: str, *, column: str, fixture_id: str) -> bool | None:
    normalized = (value or "").strip().lower()
    if normalized not in ALLOWED_BOOL_VALUES:
        raise ValueError(f"invalid boolean value for {column} in {fixture_id}: {value!r}")
    if normalized == "":
        return None
    return normalized == "true"


def validate_human_labels(label_path: Path, packet_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = _read_csv(label_path)
    packet_ids = [str(row.get("fixture_id", "")) for row in packet_rows]
    expected = set(packet_ids)
    if len(rows) != len(packet_ids):
        raise ValueError(f"expected {len(packet_ids)} human label rows, found {len(rows)}")
    seen: set[str] = set()
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        fixture_id = (row.get("fixture_id") or "").strip()
        if fixture_id in seen:
            raise ValueError(f"duplicate fixture_id: {fixture_id}")
        if fixture_id not in expected:
            raise ValueError(f"fixture_id not found in review packet: {fixture_id}")
        seen.add(fixture_id)
        human_label = (row.get("human_label") or "").strip()
        if human_label not in ALLOWED_HUMAN_LABELS:
            raise ValueError(f"invalid human_label for {fixture_id}: {human_label!r}")
        confidence = (row.get("confidence") or "").strip().lower()
        if confidence not in ALLOWED_CONFIDENCE:
            raise ValueError(f"invalid confidence for {fixture_id}: {confidence!r}")
        normalized: dict[str, Any] = {
            "fixture_id": fixture_id,
            "human_label": human_label,
            "confidence": confidence or None,
            "review_notes": row.get("review_notes") or "",
        }
        for column in BOOLEAN_COLUMNS:
            normalized[column] = _normalize_bool(row.get(column, ""), column=column, fixture_id=fixture_id)
        normalized_rows.append(normalized)
    if seen != expected:
        raise ValueError(f"missing fixture IDs: {sorted(expected - seen)}")
    order = {fixture_id: index for index, fixture_id in enumerate(packet_ids)}
    return sorted(normalized_rows, key=lambda item: order[item["fixture_id"]])


def label_counts(labels: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row["human_label"]) for row in labels)
    return {label: counts.get(label, 0) for label in ALLOWED_HUMAN_LABELS}


def build_claim_update(*, labels_present: bool, label_counts: dict[str, int] | None) -> dict[str, Any]:
    if not labels_present:
        return {
            "status": "WAITING_FOR_HUMAN_LABELS",
            "allowed_wording": [
                "A human review sheet was prepared from the T103C protocol.",
                "The fixed six-row QMSum review workflow is ready for human labels.",
            ],
            "blocked_wording": [
                "Human review was performed.",
                "QMSum semantic correctness is proven.",
                "The full QMSum matrix is complete.",
            ],
            "label_counts": None,
        }
    return {
        "status": "HUMAN_REVIEW_EXECUTED",
        "allowed_wording": [
            "Six residual QMSum rows were reviewed under a fixed human-review rubric.",
            "Human labels are bounded to the six-row T103C review packet.",
        ],
        "blocked_wording": [
            "Full QMSum semantic correctness is proven.",
            "The full QMSum matrix is complete.",
            "The six-row review proves universal QMSum quality.",
        ],
        "label_counts": label_counts or {},
    }


def build_next_task_decision(*, labels_present: bool) -> dict[str, Any]:
    if not labels_present:
        return {
            "next_task": "WAITING_FOR_HUMAN_LABELS_OR_T103D",
            "recommendation": "User fills review sheet, reruns this script, or chooses T103D deterministic-only closure.",
            "requires_user_action": True,
        }
    return {
        "next_task": "T103D — QMSum Deep Fix Closure Decision",
        "recommendation": "Use validated human-label summary to close or bound the QMSum deep-fix branch.",
        "requires_user_action": False,
    }


def build_summary(
    *,
    packet_rows: list[dict[str, Any]],
    labels_present: bool,
    labels_validated: bool,
    label_counts_payload: dict[str, int] | None,
    label_input_path: Path,
) -> dict[str, Any]:
    return {
        "task": "T103C-R — QMSum Human Review Execution",
        "decision": "HUMAN_REVIEW_EXECUTED" if labels_present and labels_validated else "WAITING_FOR_HUMAN_LABELS",
        "review_sheet_rows": len(packet_rows),
        "human_label_input_path": str(label_input_path),
        "human_labels_present": labels_present,
        "human_labels_validated": labels_validated,
        "label_counts": label_counts_payload,
        "review_complete": labels_present and labels_validated,
        "llm_judge_used": False,
        "human_labels_invented": False,
    }


def execute_review_workflow(
    *,
    review_packet_path: Path = DEFAULT_REVIEW_PACKET,
    rubric_path: Path = DEFAULT_RUBRIC,
    claim_boundary_path: Path = DEFAULT_CLAIM_BOUNDARY,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    human_labels_input_path: Path | None = None,
) -> dict[str, Any]:
    packet_rows = read_jsonl(review_packet_path)
    rubric = read_json(rubric_path)
    claim_boundary = read_json(claim_boundary_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    label_input = human_labels_input_path or output_dir / "task103cr_human_labels_input.csv"

    review_sheet_path = output_dir / "task103cr_human_review_sheet.csv"
    instructions_path = output_dir / "task103cr_human_review_instructions.md"
    write_review_sheet(review_sheet_path, packet_rows)
    write_reviewer_instructions(instructions_path)

    validated_labels: list[dict[str, Any]] | None = None
    counts: dict[str, int] | None = None
    labels_present = label_input.exists()
    if labels_present:
        validated_labels = validate_human_labels(label_input, packet_rows)
        counts = label_counts(validated_labels)
        write_jsonl(output_dir / "task103cr_validated_human_labels.jsonl", validated_labels)
        write_json(output_dir / "task103cr_label_counts.json", counts)

    claim_update = build_claim_update(labels_present=labels_present, label_counts=counts)
    next_task_decision = build_next_task_decision(labels_present=labels_present)
    summary = build_summary(
        packet_rows=packet_rows,
        labels_present=labels_present,
        labels_validated=validated_labels is not None,
        label_counts_payload=counts,
        label_input_path=label_input,
    )
    summary["input_artifacts"] = {
        "review_packet": str(review_packet_path),
        "rubric": str(rubric_path),
        "claim_boundary": str(claim_boundary_path),
    }
    summary["rubric_label_count"] = len(rubric.get("labels", [])) if isinstance(rubric, dict) else None
    summary["prior_claim_status"] = claim_boundary.get("qmsum_claim_status") if isinstance(claim_boundary, dict) else None

    write_json(output_dir / "task103cr_review_execution_summary.json", summary)
    write_json(output_dir / "task103cr_claim_update.json", claim_update)
    write_json(output_dir / "task103cr_next_task_decision.json", next_task_decision)

    return {
        "summary": summary,
        "claim_update": claim_update,
        "next_task_decision": next_task_decision,
        "label_counts": counts,
        "validated_labels": validated_labels,
        "review_sheet_path": str(review_sheet_path),
        "instructions_path": str(instructions_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare or ingest Task103C-R QMSum human review labels.")
    parser.add_argument("--review-packet", type=Path, default=DEFAULT_REVIEW_PACKET)
    parser.add_argument("--rubric", type=Path, default=DEFAULT_RUBRIC)
    parser.add_argument("--claim-boundary", type=Path, default=DEFAULT_CLAIM_BOUNDARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--human-labels-input", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = execute_review_workflow(
        review_packet_path=args.review_packet,
        rubric_path=args.rubric,
        claim_boundary_path=args.claim_boundary,
        output_dir=args.output_dir,
        human_labels_input_path=args.human_labels_input,
    )
    print(json.dumps({key: value for key, value in result.items() if key != "validated_labels"}, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
