from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task103a_qmsum_evidence_selector as selector
from scripts.phase_2_system_optimization.analysis import task103a_qmsum_evidence_selector_before_answer as analyzer


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


def _target_row(fixture_id: str, **extra: object) -> dict[str, object]:
    row = {
        "id": fixture_id,
        "context": (
            "Speaker A: The group discussed coffee and unrelated planning. "
            "Professor B: Alice approved the launch plan after the budget review. "
            "PhD C: The team also discussed music and travel."
        ),
        "question": "What did Alice approve?",
        "expected_answer": "Alice approved the launch plan after the budget review.",
        "prompt": "Meeting transcript:\nFull prompt.\n\nQuestion: What did Alice approve?",
    }
    row.update(extra)
    return row


def _result_row(condition: str, fixture_id: str, generated_text: str, **extra: object) -> dict[str, object]:
    row = {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "condition": condition,
        "dataset_name": "qmsum_meeting_qa_long",
        "expected_answer": "Alice approved the launch plan after the budget review.",
        "question": "What did Alice approve?",
        "generated_text": generated_text,
        "generated_token_count": 24,
        "output_tokens": 24,
        "max_new_tokens": 384,
        "generation_time_s": 3.0,
        "tok_per_sec": 20.0,
        "vram_reserved_gib": 4.0,
        "qmsum_policy_suffix_override": True,
        "qmsum_answer_policy_type": "qmsum_evidence_selected_v1",
    }
    row.update(extra)
    return row


def test_selector_extracts_question_focused_evidence_without_reference_or_generated_leakage(tmp_path: Path) -> None:
    target = tmp_path / "target.jsonl"
    dataset = tmp_path / "selected.jsonl"
    out = tmp_path / "out"
    row = _target_row(
        "qmsum_meeting_qa_test_0036",
        expected_answer="SECRET reference must not appear in selected evidence.",
    )
    _write_jsonl(target, [row])

    result = selector.build_evidence_selected_dataset(
        input_path=target,
        dataset_output_path=dataset,
        output_dir=out,
        expected_ids=("qmsum_meeting_qa_test_0036",),
        max_chars=220,
        top_k=2,
    )

    selected_rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines()]
    assert result["summary"]["row_count"] == 1
    assert "Alice approved the launch plan" in selected_rows[0]["context"]
    assert len(selected_rows[0]["context"]) <= 220
    assert "SECRET reference" not in selected_rows[0]["context"]
    assert selected_rows[0]["selector_metadata"]["reference_used_for_retrieval"] is False
    assert selected_rows[0]["selector_metadata"]["prior_generated_outputs_used"] is False
    assert (out / "summary/task103a_selector_summary.json").exists()
    assert (out / "summary/task103a_selected_evidence.jsonl").exists()


def test_selector_validation_rejects_generated_output_leakage_fields(tmp_path: Path) -> None:
    target = tmp_path / "target.jsonl"
    _write_jsonl(target, [_target_row("qmsum_meeting_qa_test_0036", generated_text="bad")])

    audit = selector.validate_source_rows(selector.read_jsonl(target), expected_ids=("qmsum_meeting_qa_test_0036",))

    assert audit["valid"] is False
    assert "generated-output fields present" in " ".join(audit["errors"])


def test_selector_trims_single_oversized_matching_window() -> None:
    row = _target_row(
        "qmsum_meeting_qa_test_0036",
        context="Professor B: " + "Alice approved the launch plan after the budget review. " * 40,
    )

    selection = selector.select_evidence(row, top_k=3, max_chars=240)

    assert selection["selected_chars"] <= 240
    assert "Alice approved the launch plan" in selection["selected_context"]


def test_analyzer_classifies_evidence_selected_improvement() -> None:
    category = analyzer.classify_transition(
        previous_metrics={"reference_overlap": 0.10, "reference_bigram_overlap": 0.0, "generic_flag": True},
        evidence_metrics={"reference_overlap": 0.55, "reference_bigram_overlap": 0.25, "generic_flag": False},
    )

    assert category == "resolved"


def test_analyzer_interprets_baseline_and_cc_improvement_as_query_aware_path() -> None:
    interpretation = analyzer.interpret_results(
        baseline_categories=["resolved", "improved", "resolved", "unchanged", "improved", "resolved"],
        cc_categories=["resolved", "improved", "improved", "unchanged", "improved", "resolved"],
        cc_present=True,
    )

    assert interpretation["interpretation"] == "EVIDENCE_SELECTION_HELPS_AND_QUERY_AWARE_COMPRESSION_PROMISING"
    assert interpretation["next_task_decision"]["next_task"] == "T103B — Query-aware Compression"


def test_analyzer_routes_to_semantic_protocol_when_neither_path_improves() -> None:
    interpretation = analyzer.interpret_results(
        baseline_categories=["unchanged", "unchanged", "worsened", "unchanged", "unchanged", "unchanged"],
        cc_categories=["unchanged", "worsened", "unchanged", "unchanged", "unchanged", "unchanged"],
        cc_present=True,
    )

    assert interpretation["interpretation"] == "GENERATION_OR_SEMANTIC_LIMITATION_REMAINS"
    assert interpretation["next_task_decision"]["next_task"] == "T103C — Semantic Judge / Human Review Protocol"


def test_analyzer_pairs_runs_and_writes_required_artifacts(tmp_path: Path) -> None:
    ids = sorted(TARGET_IDS)
    selected_dataset = tmp_path / "selected.jsonl"
    original = tmp_path / "original.jsonl"
    remediated = tmp_path / "remediated.jsonl"
    baseline_full = tmp_path / "baseline_full.jsonl"
    baseline_selected = tmp_path / "baseline_selected.jsonl"
    cc_selected = tmp_path / "cc_selected.jsonl"
    out = tmp_path / "out"
    _write_jsonl(selected_dataset, [_target_row(fixture_id) for fixture_id in ids])
    _write_jsonl(original, [_result_row("CC-DFlash-R2", fixture_id, "The answer is not discussed.") for fixture_id in ids])
    _write_jsonl(remediated, [_result_row("CC-DFlash-R2", fixture_id, "The answer is not discussed.") for fixture_id in ids])
    _write_jsonl(baseline_full, [_result_row("Baseline-AR", fixture_id, "The answer is not discussed.") for fixture_id in ids])
    _write_jsonl(
        baseline_selected,
        [_result_row("Baseline-AR", fixture_id, "Alice approved the launch plan after the budget review.") for fixture_id in ids],
    )
    _write_jsonl(
        cc_selected,
        [
            _result_row(
                "CC-DFlash-R2",
                fixture_id,
                "Alice approved the launch plan after the budget review.",
                compression="llmlingua",
                compressor_profile="light",
                compressor_device_map="cuda",
                requested_compressor_device_map="cuda",
            )
            for fixture_id in ids
        ],
    )

    result = analyzer.analyze(
        evidence_selected_dataset=selected_dataset,
        original_cc_jsonl=original,
        remediated_cc_jsonl=remediated,
        baseline_full_jsonl=baseline_full,
        baseline_evidence_jsonl=baseline_selected,
        cc_evidence_jsonl=cc_selected,
        output_dir=out,
    )

    assert result["summary"]["row_count"] == 6
    assert result["claim_update"]["qmsum_claim_status"] == "EVIDENCE_SELECTION_MINI_CHECK_COMPLETE"
    for relative in analyzer.OUTPUT_RELATIVE_PATHS:
        assert (out / relative).exists()


def test_no_model_loading_in_task103a_analysis_scripts() -> None:
    combined = inspect.getsource(selector) + inspect.getsource(analyzer)

    assert "transformers" not in combined
    assert "import torch" not in combined
    assert "from torch" not in combined
    assert "AutoModel" not in combined
