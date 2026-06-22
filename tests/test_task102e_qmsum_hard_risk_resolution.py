from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task102e_qmsum_hard_risk_resolution as t102e


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _qmsum_row(fixture_id: str, generated: str, reference: str, source: str = "") -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "generated_text": generated,
        "expected_answer": reference,
        "compressed_prompt_preview": source,
        "original_prompt_preview": source,
        "final_prompt_tail_preview": "Why did the team choose the battery design? Answer only the question using the meeting context.",
    }


def _label_row(fixture_id: str, reference_recall: float = 0.05, source_overlap: float = 0.05) -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "labels": {"proxy_uncertain": True, "low_reference_overlap": True},
        "metrics": {
            "reference_unigram_recall": reference_recall,
            "output_source_keyword_overlap": source_overlap,
            "output_token_count": 80,
        },
        "previews": {
            "question": "why did the team choose the battery design",
            "expected_answer": "reference",
            "generated_text": "generated",
        },
    }


def _t102d_row(fixture_id: str, band: str, outcome: str, previous: str = "unresolved_proxy_limitation") -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "improved_confidence_band": band,
        "improved_outcome": outcome,
        "previous_t102c_bucket": previous,
        "metrics": {
            "reference_content_recall": 0.05,
            "source_content_recall": 0.05,
            "question_content_recall": 0.50,
            "entity_reference_recall": 0.0,
            "output_token_count": 80,
        },
    }


def test_resolves_stronger_proxy_support_only_with_deterministic_evidence() -> None:
    qmsum = _qmsum_row(
        "supported",
        "The battery design was chosen because it lowered cost and improved remote charging reliability.",
        "The group chose the battery design for lower cost and reliable remote charging.",
        "battery design lower cost reliable remote charging",
    )
    label = _label_row("supported", reference_recall=0.20, source_overlap=0.20)
    prior = _t102d_row("supported", "unresolved_deterministic_limitation", "remaining_unexplained_uncertain")

    resolved = t102e.resolve_row(qmsum, label, prior)

    assert resolved["final_resolution"] == "resolved_stronger_proxy_support"
    assert resolved["final_status"] == "resolved"


def test_keeps_wrong_topic_row_as_confirmed_evidence_miss() -> None:
    qmsum = _qmsum_row(
        "miss",
        "The meeting discussed microphones and headset noise.",
        "The team discussed spectral subtraction, KL transformation, and VTS techniques.",
        "spectral subtraction KL transformation VTS techniques",
    )
    label = _label_row("miss", reference_recall=0.03, source_overlap=0.03)
    prior = _t102d_row("miss", "hard_quality_risk", "hard_risk", "evidence_miss_likely")

    resolved = t102e.resolve_row(qmsum, label, prior)

    assert resolved["final_resolution"] == "confirmed_evidence_miss"
    assert resolved["final_status"] == "confirmed_quality_failure"


def test_analyzer_writes_outputs_and_routes_remediation(tmp_path: Path) -> None:
    qmsum = tmp_path / "qmsum.jsonl"
    labels = tmp_path / "labels.jsonl"
    t102d = tmp_path / "t102d.jsonl"
    out = tmp_path / "out"
    _write_jsonl(
        qmsum,
        [
            _qmsum_row(
                "supported",
                "The battery design was chosen because it lowered cost and improved remote charging reliability.",
                "The group chose the battery design for lower cost and reliable remote charging.",
                "battery design lower cost reliable remote charging",
            ),
            _qmsum_row(
                "miss",
                "The meeting discussed microphones and headset noise.",
                "The team discussed spectral subtraction and KL transformation.",
                "spectral subtraction KL transformation",
            ),
        ],
    )
    _write_jsonl(labels, [_label_row("supported", 0.20, 0.20), _label_row("miss", 0.03, 0.03)])
    _write_jsonl(
        t102d,
        [
            _t102d_row("supported", "unresolved_deterministic_limitation", "remaining_unexplained_uncertain"),
            _t102d_row("miss", "hard_quality_risk", "hard_risk", "evidence_miss_likely"),
        ],
    )

    result = t102e.analyze(qmsum_jsonl=qmsum, row_labels=labels, t102d_reassessment=t102d, output_dir=out)

    assert result["summary"]["after_unexplained_deterministic_uncertainty_count"] == 0
    assert result["summary"]["after_hard_risk_count"] == 1
    assert result["decision"] == "NEEDS_REMEDIATION_TASK"
    assert result["next_task_decision"]["t103_allowed_to_proceed"] is False
    for relative in t102e.OUTPUT_RELATIVE_PATHS:
        assert (out / relative).exists()


def test_decision_pass_only_when_zero_unresolved_and_zero_hard_risk() -> None:
    assert t102e.decide(
        {
            "after_unexplained_deterministic_uncertainty_count": 0,
            "after_hard_risk_count": 0,
            "confirmed_quality_failure_rows_count": 0,
            "still_unresolved_rows_count": 0,
        }
    ) == "PASS"
    assert t102e.decide(
        {
            "after_unexplained_deterministic_uncertainty_count": 0,
            "after_hard_risk_count": 1,
            "confirmed_quality_failure_rows_count": 1,
            "still_unresolved_rows_count": 0,
        }
    ) == "NEEDS_REMEDIATION_TASK"


def test_no_model_loading_in_task102e_analyzer() -> None:
    source = inspect.getsource(t102e)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
