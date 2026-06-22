from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task102f_qmsum_target_row_remediation_decision as t102f


EXPECTED_IDS = {
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


def _dataset_row(fixture_id: str) -> dict[str, object]:
    return {
        "id": fixture_id,
        "dataset_name": "qmsum_meeting_qa_long",
        "context": f"Speaker A: Evidence for {fixture_id}.",
        "question": f"What happened in {fixture_id}?",
        "expected_answer": f"Reference answer for {fixture_id}.",
        "prompt": f"Meeting transcript:\nSpeaker A: Evidence for {fixture_id}.\n\nQuestion: What happened?",
        "domain": "meeting_qa_long_context",
        "evidence": "QMSum reference answer.",
        "approximate_context_words": 5,
        "quality_policy": "normalized_text_containment_proxy",
    }


def _resolution_row(fixture_id: str, final_resolution: str) -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "prior_labels": {
            "task102d_confidence_band": "hard_quality_risk",
            "task102d_outcome": "hard_risk",
            "task102c_bucket": "evidence_miss_likely",
        },
        "question": f"What happened in {fixture_id}?",
        "reference_answer_preview": f"Reference answer for {fixture_id}.",
        "generated_output": f"Generated answer for {fixture_id}.",
        "source_prompt_preview": f"Source for {fixture_id}.",
        "signals": {"reference_overlap": 0.1},
        "final_resolution": final_resolution,
        "final_status": "confirmed_quality_failure"
        if final_resolution.startswith("confirmed")
        else "still_unresolved",
        "deterministic_reason": "test reason",
    }


def test_analyzer_freezes_expected_targets_and_writes_outputs(tmp_path: Path) -> None:
    dataset = tmp_path / "qmsum.jsonl"
    resolutions = tmp_path / "resolutions.jsonl"
    output_dir = tmp_path / "out"
    target_dataset = tmp_path / "target.jsonl"
    rows = [_dataset_row(fixture_id) for fixture_id in sorted(EXPECTED_IDS)]
    _write_jsonl(dataset, rows + [_dataset_row("non_target")])
    _write_jsonl(
        resolutions,
        [
            _resolution_row("qmsum_meeting_qa_test_0036", "still_unresolved_without_semantic_judge"),
            _resolution_row("qmsum_meeting_qa_test_0070", "confirmed_evidence_miss"),
            _resolution_row("qmsum_meeting_qa_test_0055", "confirmed_generic_or_under_specific"),
            _resolution_row("qmsum_meeting_qa_test_0078", "confirmed_evidence_miss"),
            _resolution_row("qmsum_meeting_qa_test_0094", "still_unresolved_without_semantic_judge"),
            _resolution_row("qmsum_meeting_qa_test_0001", "still_unresolved_without_semantic_judge"),
        ],
    )

    result = t102f.analyze(
        source_dataset=dataset,
        task102e_resolution=resolutions,
        output_dir=output_dir,
        target_dataset_path=target_dataset,
    )

    assert result["decision"] == "PASS"
    assert {row["fixture_id"] for row in result["target_rows"]} == EXPECTED_IDS
    assert result["next_task_decision"]["next_task"] == "T102G — QMSum Target-row Remediation Rerun"
    assert result["claim_status_update"]["T103"]["status"] == "BLOCKED_BY_DEFAULT"
    for relative in t102f.OUTPUT_RELATIVE_PATHS:
        assert (output_dir / relative).exists()
    assert target_dataset.exists()


def test_policy_is_evidence_focused_and_keeps_claims_bounded() -> None:
    policy = t102f.build_remediation_policy()

    suffix = policy["prompt_suffix"]
    assert "using only evidence from the meeting context" in suffix
    assert "not discussed" in suffix
    assert policy["max_new_tokens_decision"]["selected"] == 384
    assert "QMSum semantic correctness is proven." in policy["blocked_behavior"]


def test_target_dataset_excludes_generated_outputs(tmp_path: Path) -> None:
    target_dataset = tmp_path / "target.jsonl"
    source_rows = [_dataset_row(fixture_id) | {"generated_text": "must not copy"} for fixture_id in EXPECTED_IDS]

    manifest = t102f.write_target_dataset(source_rows, target_dataset)

    written = [json.loads(line) for line in target_dataset.read_text(encoding="utf-8").splitlines()]
    assert manifest["row_count"] == 6
    assert all("generated_text" not in row for row in written)
    assert all("generated" not in row.get("prompt", "").lower() for row in written)


def test_dataset_plan_notes_runner_filter_gap_and_no_leakage() -> None:
    plan = t102f.build_target_dataset_plan(target_dataset_path=Path("data/eval/qmsum_meeting_qa_target_rows_task102f.jsonl"))

    assert plan["fixture_id_filter_exists"] is False
    assert plan["target_only_dataset_needed"] is True
    assert plan["leakage_guard"]["previous_generated_outputs_in_prompt_inputs"] is False


def test_no_model_loading_in_task102f_analyzer() -> None:
    source = inspect.getsource(t102f)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
