from __future__ import annotations

import csv
import inspect
import json
from pathlib import Path

import pytest

from scripts.phase_2_system_optimization.analysis import task103cr_qmsum_human_review_execution as review


TARGET_IDS = [
    "qmsum_meeting_qa_test_0036",
    "qmsum_meeting_qa_test_0070",
    "qmsum_meeting_qa_test_0055",
    "qmsum_meeting_qa_test_0078",
    "qmsum_meeting_qa_test_0094",
    "qmsum_meeting_qa_test_0001",
]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _packet_row(fixture_id: str) -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "question": "What did Alice approve?",
        "reference_answer": "Alice approved the launch plan after the budget review.",
        "selected_source_evidence": "Professor B: Alice approved the launch plan after the budget review.",
        "outputs": {
            "original_cc_dflash": "Alice approved the launch plan.",
            "remediated_cc_dflash": "Alice approved the launch plan after review.",
            "baseline_ar": "Alice approved a plan.",
            "evidence_selected_baseline_ar": "Alice approved the launch plan after the budget review.",
            "evidence_selected_cc_dflash": "Alice approved the launch plan.",
        },
        "deterministic_labels": {
            "task102h_final_risk_bucket": "residual_unresolved_deterministic_limitation",
            "task102i_baseline_category": "baseline_also_fails_or_uncertain",
            "task103a_baseline_evidence_category": "unchanged",
            "task103a_cc_evidence_category": "improved",
        },
    }


def _fixture_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    packet = tmp_path / "packet.jsonl"
    rubric = tmp_path / "rubric.json"
    boundary = tmp_path / "boundary.json"
    _write_jsonl(packet, [_packet_row(fixture_id) for fixture_id in TARGET_IDS])
    _write_json(
        rubric,
        {
            "labels": [{"label": label} for label in review.ALLOWED_HUMAN_LABELS],
            "rubric_name": "test_rubric",
        },
    )
    _write_json(
        boundary,
        {
            "allowed_claims": ["A semantic review protocol was prepared for residual QMSum rows."],
            "blocked_claims": ["QMSum semantic correctness is proven."],
        },
    )
    return packet, rubric, boundary


def _write_label_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=review.REVIEW_SHEET_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _valid_label_rows() -> list[dict[str, str]]:
    labels = [
        "correct_supported",
        "partially_correct_or_incomplete",
        "unsupported_or_wrong",
        "cannot_determine_from_available_context",
        "unsupported_or_wrong",
        "partially_correct_or_incomplete",
    ]
    rows: list[dict[str, str]] = []
    for fixture_id, label in zip(TARGET_IDS, labels):
        row = {column: "" for column in review.REVIEW_SHEET_COLUMNS}
        row.update(
            {
                "fixture_id": fixture_id,
                "human_label": label,
                "confidence": "medium",
                "answers_question": "true",
                "uses_correct_evidence": "false",
                "complete_enough": "",
                "hallucination_or_unsupported": "false",
                "not_discussed_error": "false",
                "review_notes": "bounded test note",
            }
        )
        rows.append(row)
    return rows


def test_no_labels_exports_review_sheet_and_waiting_decision(tmp_path: Path) -> None:
    packet, rubric, boundary = _fixture_inputs(tmp_path)
    out = tmp_path / "out"

    result = review.execute_review_workflow(
        review_packet_path=packet,
        rubric_path=rubric,
        claim_boundary_path=boundary,
        output_dir=out,
    )

    assert result["summary"]["decision"] == "WAITING_FOR_HUMAN_LABELS"
    assert result["claim_update"]["status"] == "WAITING_FOR_HUMAN_LABELS"
    assert result["next_task_decision"]["next_task"] == "WAITING_FOR_HUMAN_LABELS_OR_T103D"
    assert (out / "task103cr_human_review_sheet.csv").exists()
    assert (out / "task103cr_human_review_instructions.md").exists()
    assert not (out / "task103cr_validated_human_labels.jsonl").exists()
    with (out / "task103cr_human_review_sheet.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    assert rows[0]["human_label"] == ""


def test_invalid_human_label_is_rejected(tmp_path: Path) -> None:
    packet, rubric, boundary = _fixture_inputs(tmp_path)
    out = tmp_path / "out"
    label_path = out / "task103cr_human_labels_input.csv"
    rows = _valid_label_rows()
    rows[0]["human_label"] = "looks_good_to_me"
    _write_label_csv(label_path, rows)

    with pytest.raises(ValueError, match="invalid human_label"):
        review.execute_review_workflow(
            review_packet_path=packet,
            rubric_path=rubric,
            claim_boundary_path=boundary,
            output_dir=out,
        )


def test_valid_label_file_is_ingested_and_counts_written(tmp_path: Path) -> None:
    packet, rubric, boundary = _fixture_inputs(tmp_path)
    out = tmp_path / "out"
    label_path = out / "task103cr_human_labels_input.csv"
    _write_label_csv(label_path, _valid_label_rows())

    result = review.execute_review_workflow(
        review_packet_path=packet,
        rubric_path=rubric,
        claim_boundary_path=boundary,
        output_dir=out,
    )

    assert result["summary"]["decision"] == "HUMAN_REVIEW_EXECUTED"
    assert result["claim_update"]["status"] == "HUMAN_REVIEW_EXECUTED"
    assert result["next_task_decision"]["next_task"] == "T103D — QMSum Deep Fix Closure Decision"
    assert result["label_counts"]["correct_supported"] == 1
    assert result["label_counts"]["partially_correct_or_incomplete"] == 2
    assert result["label_counts"]["unsupported_or_wrong"] == 2
    assert result["label_counts"]["cannot_determine_from_available_context"] == 1
    assert (out / "task103cr_validated_human_labels.jsonl").exists()
    assert (out / "task103cr_label_counts.json").exists()


def test_confidence_and_boolean_validation(tmp_path: Path) -> None:
    packet, rubric, boundary = _fixture_inputs(tmp_path)
    out = tmp_path / "out"
    label_path = out / "task103cr_human_labels_input.csv"
    rows = _valid_label_rows()
    rows[0]["confidence"] = "very"
    _write_label_csv(label_path, rows)

    with pytest.raises(ValueError, match="invalid confidence"):
        review.execute_review_workflow(
            review_packet_path=packet,
            rubric_path=rubric,
            claim_boundary_path=boundary,
            output_dir=out,
        )


def test_claim_update_blocks_semantic_correctness_proof() -> None:
    update = review.build_claim_update(labels_present=False, label_counts=None)

    assert "Human review was performed." in update["blocked_wording"]
    assert any("human review sheet" in claim for claim in update["allowed_wording"])

    executed = review.build_claim_update(
        labels_present=True,
        label_counts={"correct_supported": 1, "partially_correct_or_incomplete": 2, "unsupported_or_wrong": 2},
    )
    blocked = " ".join(executed["blocked_wording"])
    assert "Full QMSum semantic correctness is proven" in blocked
    assert "The full QMSum matrix is complete" in blocked


def test_no_model_loading_in_task103cr_script() -> None:
    source = inspect.getsource(review)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
