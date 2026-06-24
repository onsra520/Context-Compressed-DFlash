from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from scripts.phase_2_system_optimization.analysis import task103d_qmsum_deep_fix_closure_decision as closure


LABELS = [
    ("qmsum_meeting_qa_test_0036", "partially_correct_or_incomplete"),
    ("qmsum_meeting_qa_test_0070", "cannot_determine_from_available_context"),
    ("qmsum_meeting_qa_test_0055", "unsupported_or_wrong"),
    ("qmsum_meeting_qa_test_0078", "partially_correct_or_incomplete"),
    ("qmsum_meeting_qa_test_0094", "cannot_determine_from_available_context"),
    ("qmsum_meeting_qa_test_0001", "cannot_determine_from_available_context"),
]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _fixture_inputs(tmp_path: Path) -> closure.ClosureInputs:
    root = tmp_path / "inputs"
    t102h_summary = root / "task102h_summary.json"
    t102i_claim = root / "task102i_claim.json"
    t103a_claim = root / "task103a_claim.json"
    t103c_boundary = root / "task103c_boundary.json"
    t103cr_summary = root / "task103cr_summary.json"
    t103cr_counts = root / "task103cr_counts.json"
    t103cr_claim = root / "task103cr_claim.json"
    t103cr_next = root / "task103cr_next.json"
    t103cr_labels = root / "task103cr_labels.jsonl"

    _write_json(
        t102h_summary,
        {
            "decision": "PASS_WITH_CAVEAT",
            "resolved_by_targeted_policy": 0,
            "target_row_count": 6,
            "remaining_hard_risk_rows": 3,
            "remaining_unresolved_rows": 2,
            "qmsum_claim_status": "REMEDIATION_FAILED",
        },
    )
    _write_json(
        t102i_claim,
        {
            "interpretation": "TARGET_MODEL_OR_QMSUM_GROUNDING_LIMITATION_SUPPORTED",
            "compression_path_specific_risk_supported": False,
            "baseline_also_fails_or_uncertain": 4,
            "target_row_count": 6,
        },
    )
    _write_json(
        t103a_claim,
        {
            "decision": "PASS_WITH_CAVEAT",
            "resolved_rows": 0,
            "baseline_evidence_selector": {"improved": 0, "unchanged": 4, "worsened": 2},
            "cc_dflash_evidence_selector": {"improved": 1, "unchanged": 3, "worsened": 2},
        },
    )
    _write_json(
        t103c_boundary,
        {
            "review_protocol_status": "SEMANTIC_REVIEW_PROTOCOL_PREPARED",
            "blocked_claims": ["QMSum semantic correctness is proven."],
        },
    )
    _write_json(
        t103cr_summary,
        {
            "decision": "HUMAN_REVIEW_EXECUTED",
            "human_labels_present": True,
            "human_labels_validated": True,
            "review_complete": True,
            "review_sheet_rows": 6,
            "label_counts": {
                "correct_supported": 0,
                "partially_correct_or_incomplete": 2,
                "unsupported_or_wrong": 1,
                "cannot_determine_from_available_context": 3,
            },
        },
    )
    _write_json(
        t103cr_counts,
        {
            "correct_supported": 0,
            "partially_correct_or_incomplete": 2,
            "unsupported_or_wrong": 1,
            "cannot_determine_from_available_context": 3,
        },
    )
    _write_json(t103cr_claim, {"status": "HUMAN_REVIEW_EXECUTED"})
    _write_json(t103cr_next, {"next_task": "T103D — QMSum Deep Fix Closure Decision"})
    _write_jsonl(
        t103cr_labels,
        [
            {
                "fixture_id": fixture_id,
                "human_label": label,
                "confidence": "high",
                "review_notes": "bounded human review note",
            }
            for fixture_id, label in LABELS
        ],
    )

    return closure.ClosureInputs(
        t102h_summary=t102h_summary,
        t102i_claim_interpretation=t102i_claim,
        t103a_claim_update=t103a_claim,
        t103c_claim_boundary=t103c_boundary,
        t103cr_review_summary=t103cr_summary,
        t103cr_validated_labels=t103cr_labels,
        t103cr_label_counts=t103cr_counts,
        t103cr_claim_update=t103cr_claim,
        t103cr_next_task_decision=t103cr_next,
    )


def test_hard_gate_requires_executed_human_review(tmp_path: Path) -> None:
    inputs = _fixture_inputs(tmp_path)
    _write_json(
        inputs.t103cr_review_summary,
        {
            "decision": "WAITING_FOR_HUMAN_LABELS",
            "human_labels_validated": False,
            "review_complete": False,
            "label_counts": {},
        },
    )

    with pytest.raises(ValueError, match="HUMAN_REVIEW_EXECUTED"):
        closure.run_closure_audit(inputs=inputs, output_dir=tmp_path / "out")


def test_closure_audit_writes_expected_outputs(tmp_path: Path) -> None:
    result = closure.run_closure_audit(inputs=_fixture_inputs(tmp_path), output_dir=tmp_path / "out")

    assert result["closure_summary"]["decision"] == "PASS_WITH_CAVEAT"
    assert result["closure_summary"]["qmsum_deep_fix_status"] == "CLOSED_WITH_PERSISTENT_RESIDUAL_RISK"
    assert result["closure_summary"]["t104_allowed"] == "YES_WITH_MANDATORY_QMSUM_CAVEAT"
    assert result["human_review_summary"]["label_counts"]["correct_supported"] == 0
    assert (tmp_path / "out" / "task103d_closure_summary.json").exists()
    assert (tmp_path / "out" / "task103d_evidence_chain.json").exists()
    assert (tmp_path / "out" / "tables" / "task103d_qmsum_deep_fix_evidence_table.csv").exists()


def test_claim_boundary_blocks_semantic_correctness_and_query_aware_claims(tmp_path: Path) -> None:
    result = closure.run_closure_audit(inputs=_fixture_inputs(tmp_path), output_dir=tmp_path / "out")

    blocked = " ".join(result["claim_boundary"]["blocked_claims"])
    allowed = " ".join(result["claim_boundary"]["allowed_claims"])
    assert "QMSum semantic correctness is proven" in blocked
    assert "Query-aware compression is validated" in blocked
    assert "persistent residual risk" in allowed
    assert result["claim_boundary"]["qmsum_semantic_correctness"] == "NOT_CLAIMED"


def test_next_task_is_t104_with_mandatory_caveat(tmp_path: Path) -> None:
    result = closure.run_closure_audit(inputs=_fixture_inputs(tmp_path), output_dir=tmp_path / "out")

    next_task = result["next_task_decision"]
    assert next_task["next_task"] == "T104 — Reference Alignment for Speed Claim"
    assert next_task["t103b_default_next"] == "NO"
    assert next_task["mandatory_qmsum_caveat"] is True


def test_no_model_loading_in_task103d_script() -> None:
    source = inspect.getsource(closure)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
