from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task102i_qmsum_baseline_ar_target_row_mini_check as t102i


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


def _dataset_row(fixture_id: str, **extra: object) -> dict[str, object]:
    row = {
        "id": fixture_id,
        "context": "Speaker A: Alice approved the launch plan after the budget review.",
        "question": "What did Alice approve?",
        "expected_answer": "Alice approved the launch plan after the budget review.",
        "prompt": "Meeting transcript:\nSpeaker A: Alice approved the launch plan after the budget review.\n\nQuestion: What did Alice approve?",
    }
    row.update(extra)
    return row


def _run_row(condition: str, fixture_id: str, generated_text: str, **extra: object) -> dict[str, object]:
    row = {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "condition": condition,
        "dataset_name": "qmsum_meeting_qa_long",
        "question": "What did Alice approve?",
        "expected_answer": "Alice approved the launch plan after the budget review.",
        "generated_text": generated_text,
        "generated_token_count": 24,
        "output_tokens": 24,
        "max_new_tokens": 384,
        "generation_time_s": 3.0,
        "tok_per_sec": 20.0,
        "vram_reserved_gib": 4.8,
        "qmsum_policy_suffix_override": True,
        "qmsum_answer_policy_type": "qmsum_targeted_evidence_repair_v1",
    }
    row.update(extra)
    return row


def test_target_dataset_validation_catches_wrong_row_count(tmp_path: Path) -> None:
    dataset = tmp_path / "target.jsonl"
    _write_jsonl(dataset, [_dataset_row("qmsum_meeting_qa_test_0036")])

    audit = t102i.validate_target_dataset(dataset)

    assert audit["valid"] is False
    assert "expected 6 rows" in " ".join(audit["errors"])


def test_target_dataset_validation_rejects_generated_output_leakage(tmp_path: Path) -> None:
    dataset = tmp_path / "target.jsonl"
    rows = [_dataset_row(fixture_id) for fixture_id in EXPECTED_IDS]
    rows[0]["generated_text"] = "leaked previous answer"
    _write_jsonl(dataset, rows)

    audit = t102i.validate_target_dataset(dataset)

    assert audit["valid"] is False
    assert "generated-output fields present" in " ".join(audit["errors"])


def test_classification_labels_baseline_also_fails_or_uncertain() -> None:
    result = t102i.classify_row(
        baseline_metrics={"reference_overlap": 0.05, "reference_bigram_overlap": 0.0, "source_grounding_overlap": 0.02, "generic_flag": True},
        original_metrics={"reference_overlap": 0.04, "reference_bigram_overlap": 0.0, "source_grounding_overlap": 0.02, "generic_flag": True},
        remediated_metrics={"reference_overlap": 0.06, "reference_bigram_overlap": 0.0, "source_grounding_overlap": 0.02, "generic_flag": True},
    )

    assert result == "baseline_also_fails_or_uncertain"


def test_classification_labels_baseline_resolves_proxy_supported() -> None:
    result = t102i.classify_row(
        baseline_metrics={"reference_overlap": 0.55, "reference_bigram_overlap": 0.25, "source_grounding_overlap": 0.20, "generic_flag": False},
        original_metrics={"reference_overlap": 0.50, "reference_bigram_overlap": 0.20, "source_grounding_overlap": 0.18, "generic_flag": False},
        remediated_metrics={"reference_overlap": 0.49, "reference_bigram_overlap": 0.20, "source_grounding_overlap": 0.18, "generic_flag": False},
    )

    assert result == "baseline_resolves_proxy_supported"


def test_classification_labels_compression_path_specific_risk() -> None:
    result = t102i.classify_row(
        baseline_metrics={"reference_overlap": 0.58, "reference_bigram_overlap": 0.25, "source_grounding_overlap": 0.20, "generic_flag": False},
        original_metrics={"reference_overlap": 0.08, "reference_bigram_overlap": 0.0, "source_grounding_overlap": 0.02, "generic_flag": False},
        remediated_metrics={"reference_overlap": 0.10, "reference_bigram_overlap": 0.0, "source_grounding_overlap": 0.02, "generic_flag": True},
    )

    assert result == "compression_path_specific_risk"


def test_interpretation_logic_for_target_model_limitation() -> None:
    interpretation = t102i.interpret_categories(
        [
            "baseline_also_fails_or_uncertain",
            "baseline_also_fails_or_uncertain",
            "proxy_or_reference_limitation_persists",
            "baseline_also_fails_or_uncertain",
            "proxy_or_reference_limitation_persists",
            "baseline_clearly_better_but_not_resolved",
        ]
    )

    assert interpretation["interpretation"] == "TARGET_MODEL_OR_QMSUM_GROUNDING_LIMITATION_SUPPORTED"
    assert interpretation["next_task_decision"]["next_task"] == "T102J — QMSum Residual Risk Stop-or-Judge Decision"


def test_interpretation_logic_for_compression_specific_risk() -> None:
    interpretation = t102i.interpret_categories(
        [
            "compression_path_specific_risk",
            "compression_path_specific_risk",
            "baseline_resolves_proxy_supported",
            "compression_path_specific_risk",
            "baseline_resolves_proxy_supported",
            "baseline_clearly_better_but_not_resolved",
        ]
    )

    assert interpretation["interpretation"] == "COMPRESSION_PATH_SPECIFIC_QMSUM_RISK_SUPPORTED"


def test_analyzer_pairs_rows_and_writes_outputs(tmp_path: Path) -> None:
    dataset = tmp_path / "target.jsonl"
    baseline = tmp_path / "baseline.jsonl"
    original = tmp_path / "original.jsonl"
    remediated = tmp_path / "remediated.jsonl"
    task102h = tmp_path / "task102h.jsonl"
    out = tmp_path / "out"
    _write_jsonl(dataset, [_dataset_row(fixture_id) for fixture_id in EXPECTED_IDS])
    _write_jsonl(
        baseline,
        [
            _run_row("Baseline-AR", fixture_id, "Alice approved the launch plan after the budget review.")
            for fixture_id in EXPECTED_IDS
        ],
    )
    _write_jsonl(
        original,
        [_run_row("CC-DFlash-R2", fixture_id, "The answer is not discussed.") for fixture_id in EXPECTED_IDS],
    )
    _write_jsonl(
        remediated,
        [_run_row("CC-DFlash-R2", fixture_id, "The answer is not discussed.") for fixture_id in EXPECTED_IDS],
    )
    _write_jsonl(task102h, [{"fixture_id": fixture_id, "remediation_outcome": "worsened"} for fixture_id in EXPECTED_IDS])

    result = t102i.analyze(
        baseline_jsonl=baseline,
        original_cc_jsonl=original,
        remediated_cc_jsonl=remediated,
        task102h_assessment=task102h,
        target_dataset=dataset,
        output_dir=out,
    )

    assert result["summary"]["row_count"] == 6
    assert result["next_task_decision"]["next_task"] == "T102J — QMSum Residual Risk Stop-or-Judge Decision"
    for relative in t102i.OUTPUT_RELATIVE_PATHS:
        assert (out / relative).exists()


def test_no_model_loading_in_task102i_analyzer() -> None:
    source = inspect.getsource(t102i)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
