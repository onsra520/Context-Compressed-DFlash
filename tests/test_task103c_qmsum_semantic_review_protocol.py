from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task103c_qmsum_semantic_review_protocol as protocol


TARGET_IDS = {
    "qmsum_meeting_qa_test_0036",
    "qmsum_meeting_qa_test_0070",
    "qmsum_meeting_qa_test_0055",
    "qmsum_meeting_qa_test_0078",
    "qmsum_meeting_qa_test_0094",
    "qmsum_meeting_qa_test_0001",
}


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _row(fixture_id: str) -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "question": "What did Alice approve?",
        "reference_answer": "Alice approved the launch plan after the budget review.",
        "selected_context": "Professor B: Alice approved the launch plan after the budget review.",
        "selected_chars": 71,
        "original_generated_answer": "Alice approved the launch plan.",
        "remediated_generated_answer": "Alice approved the launch plan after review.",
        "baseline_ar_output": "Alice approved a plan.",
        "baseline_evidence_output": "Alice approved the launch plan after the budget review.",
        "cc_evidence_output": "Alice approved the launch plan.",
        "prior_status": "still_unresolved_without_semantic_judge",
        "remediation_outcome": "still_unresolved_without_semantic_judge",
        "category": "baseline_also_fails_or_uncertain",
        "baseline_evidence_category": "unchanged",
        "cc_evidence_category": "improved",
    }


def test_rubric_uses_required_four_level_labels() -> None:
    rubric = protocol.build_review_rubric()

    labels = {label["label"] for label in rubric["labels"]}
    assert labels == {
        "correct_supported",
        "partially_correct_or_incomplete",
        "unsupported_or_wrong",
        "cannot_determine_from_available_context",
    }
    dimensions = {dimension["name"] for dimension in rubric["scoring_dimensions"]}
    assert "answers_the_question" in dimensions
    assert "reference_source_mismatch_risk" in dimensions


def test_option_matrix_does_not_default_to_llm_judge() -> None:
    matrix = protocol.build_option_matrix()

    by_id = {option["option_id"]: option for option in matrix["options"]}
    assert by_id["A"]["default_when"] == "Phase 2 should continue with deterministic-only methodology."
    assert by_id["B"]["recommended_for_stronger_semantic_claim"] is True
    assert by_id["D"]["recommended_for_stronger_semantic_claim"] is True
    assert by_id["C"]["automatic_default"] is False
    assert matrix["default_recommendation"]["do_not_run_llm_judge_without_explicit_approval"] is True


def test_next_task_decision_routes_by_user_intent() -> None:
    assert protocol.build_next_task_decision("stronger_semantic_claim")["next_task"].startswith("T103C-R")
    assert protocol.build_next_task_decision("deterministic_only")["next_task"].startswith("T103D")
    assert protocol.build_next_task_decision("query_aware_compression")["next_task"].startswith("T103B")


def test_review_packet_contains_required_outputs_and_blank_scoring_fields() -> None:
    row = _row("qmsum_meeting_qa_test_0036")
    packet = protocol.build_review_packet_row(row)

    assert packet["fixture_id"] == "qmsum_meeting_qa_test_0036"
    assert packet["question"]
    assert packet["reference_answer"]
    assert packet["selected_source_evidence"]
    assert packet["outputs"]["original_cc_dflash"]
    assert packet["outputs"]["remediated_cc_dflash"]
    assert packet["outputs"]["baseline_ar"]
    assert packet["outputs"]["evidence_selected_baseline_ar"]
    assert packet["outputs"]["evidence_selected_cc_dflash"]
    assert packet["review_fields"]["semantic_label"] is None
    assert packet["review_fields"]["reviewer_notes"] == ""


def test_protocol_generation_writes_all_expected_artifacts(tmp_path: Path) -> None:
    ids = sorted(TARGET_IDS)
    before_after = tmp_path / "before_after.jsonl"
    selected = tmp_path / "selected.jsonl"
    h_rows = tmp_path / "h.jsonl"
    i_rows = tmp_path / "i.jsonl"
    out = tmp_path / "out"
    rows = [_row(fixture_id) for fixture_id in ids]
    _write_jsonl(before_after, rows)
    _write_jsonl(selected, rows)
    _write_jsonl(h_rows, rows)
    _write_jsonl(i_rows, rows)

    result = protocol.generate_protocol_artifacts(
        output_dir=out,
        task103a_before_after_path=before_after,
        task103a_selected_evidence_path=selected,
        task102h_assessment_path=h_rows,
        task102i_assessment_path=i_rows,
    )

    assert result["review_protocol"]["review_unit_count"] == 6
    assert result["claim_boundary"]["semantic_correctness_proven"] is False
    for relative_path in protocol.OUTPUT_FILENAMES:
        assert (out / relative_path).exists()
    packet_rows = [
        json.loads(line)
        for line in (out / "task103c_review_packet.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert {row["fixture_id"] for row in packet_rows} == TARGET_IDS


def test_claim_boundary_blocks_unperformed_review_claims() -> None:
    boundary = protocol.build_claim_boundary()

    blocked = " ".join(boundary["blocked_claims"])
    assert "QMSum semantic correctness is proven" in blocked
    assert "Human/LLM review was performed" in blocked
    assert "Query-aware compression is validated by T103C" in blocked
    assert any("semantic review protocol was prepared" in claim for claim in boundary["allowed_claims"])


def test_no_model_loading_in_protocol_script() -> None:
    source = inspect.getsource(protocol)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
