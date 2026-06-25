from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task108b_qmsum_targeted_repair_attempt as t108b


TARGET_IDS = [
    "qmsum_meeting_qa_test_0036",
    "qmsum_meeting_qa_test_0070",
    "qmsum_meeting_qa_test_0055",
    "qmsum_meeting_qa_test_0078",
    "qmsum_meeting_qa_test_0094",
    "qmsum_meeting_qa_test_0001",
]


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _dataset_row(fixture_id: str, **extra: object) -> dict[str, object]:
    row = {
        "id": fixture_id,
        "context": (
            "The transcript discusses students, indigenous residents, rural residents, "
            "aboriginal people, Black lives, police brutality, internet access, and education."
        ),
        "question": "Which groups were heavily impacted?",
        "expected_answer": (
            "Members discussed students, indigenous residents, rural residents, aboriginal people, "
            "and Black lives."
        ),
        "answer": (
            "Members discussed students, indigenous residents, rural residents, aboriginal people, "
            "and Black lives."
        ),
    }
    row.update(extra)
    return row


def _before_row(fixture_id: str, generated: str = "The answer discussed honey bees and whales.") -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "condition": "CC-DFlash-R2",
        "dataset_name": "qmsum_meeting_qa_long",
        "expected_answer": (
            "Members discussed students, indigenous residents, rural residents, aboriginal people, "
            "and Black lives."
        ),
        "question": "Which groups were heavily impacted?",
        "generated_text": generated,
        "output_tokens": 38,
        "generated_token_count": 38,
        "max_new_tokens": 384,
        "generation_time_s": 5.0,
        "t_compress_ms": 129.0,
        "R_actual": 2.19,
        "vram_reserved_gib": 5.4,
    }


def _repair_row(fixture_id: str, generated: str, **extra: object) -> dict[str, object]:
    row = {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "condition": "CC-DFlash-R2",
        "dataset_name": "qmsum_meeting_qa_long",
        "compressor_profile": "light",
        "compressor_device_map": "cuda",
        "requested_compressor_device_map": "cuda",
        "local_files_only": True,
        "qmsum_policy_suffix_override": True,
        "qmsum_answer_policy_type": "qmsum_evidence_grounded_concise_v1",
        "qmsum_answer_policy_preserved": True,
        "expected_answer": (
            "Members discussed students, indigenous residents, rural residents, aboriginal people, "
            "and Black lives."
        ),
        "question": "Which groups were heavily impacted?",
        "generated_text": generated,
        "output_tokens": 44,
        "generated_token_count": 44,
        "max_new_tokens": 384,
        "generation_time_s": 4.0,
        "t_compress_ms": 120.0,
        "R_actual": 2.0,
        "vram_reserved_gib": 5.2,
    }
    row.update(extra)
    return row


def test_target_dataset_validation_rejects_leakage_and_wrong_ids(tmp_path: Path) -> None:
    dataset = tmp_path / "target.jsonl"
    rows = [_dataset_row(fixture_id) for fixture_id in TARGET_IDS]
    rows[0]["generated_text"] = "must not be a prompt input"
    _write_jsonl(dataset, rows[:-1])

    audit = t108b.validate_target_dataset(dataset)

    assert audit["valid"] is False
    errors = " ".join(audit["errors"])
    assert "expected 6 rows" in errors
    assert "generated-output fields present" in errors


def test_run_metadata_requires_light_cuda_and_repair_policy() -> None:
    rows = [
        _repair_row(
            fixture_id,
            "Members discussed students, indigenous residents, rural residents, aboriginal people, and Black lives.",
        )
        for fixture_id in TARGET_IDS
    ]
    rows[0]["qmsum_answer_policy_type"] = "old_policy"

    audit = t108b.audit_run_metadata(rows)

    assert audit["valid"] is False
    assert "qmsum_answer_policy_type" in " ".join(audit["errors"])


def test_row_comparison_detects_proxy_improvement() -> None:
    comparison = t108b.compare_row(
        before=_before_row("row", "The answer discussed honey bees and whales."),
        after=_repair_row(
            "row",
            "Members discussed students, indigenous residents, rural residents, aboriginal people, and Black lives.",
        ),
        target=_dataset_row("row"),
    )

    assert comparison["row_outcome"] == "proxy_improved"
    assert comparison["reference_recall_delta"] > 0
    assert comparison["after_generic_or_refusal"] is False


def test_row_comparison_flags_safer_but_uninformative_refusal() -> None:
    comparison = t108b.compare_row(
        before=_before_row("row", "The answer discussed honey bees and whales."),
        after=_repair_row("row", "The transcript does not provide enough information."),
        target=_dataset_row("row"),
    )

    assert comparison["row_outcome"] == "safer_but_uninformative"
    assert comparison["after_generic_or_refusal"] is True


def test_summary_recommends_validation_when_proxy_improves(tmp_path: Path) -> None:
    dataset = tmp_path / "target.jsonl"
    before = tmp_path / "before.jsonl"
    repair = tmp_path / "repair.jsonl"
    out = tmp_path / "out"
    _write_jsonl(dataset, [_dataset_row(fixture_id) for fixture_id in TARGET_IDS])
    _write_jsonl(before, [_before_row(fixture_id) for fixture_id in TARGET_IDS])
    _write_jsonl(
        repair,
        [
            _repair_row(
                fixture_id,
                "Members discussed students, indigenous residents, rural residents, aboriginal people, and Black lives.",
            )
            for fixture_id in TARGET_IDS
        ],
    )

    result = t108b.analyze(run_artifact=repair, before_jsonl=before, target_dataset=dataset, output_dir=out)

    assert result["repair_summary"]["decision"] == "PASS_WITH_CAVEAT"
    assert result["next_task_decision"]["next_task"].startswith("T108C")
    assert result["next_task_decision"]["next_task_mode"] == "targeted_repair_validation"
    for relative in t108b.OUTPUT_RELATIVE_PATHS:
        assert (out / relative).exists()


def test_summary_routes_to_limitation_decision_when_no_improvement(tmp_path: Path) -> None:
    dataset = tmp_path / "target.jsonl"
    before = tmp_path / "before.jsonl"
    repair = tmp_path / "repair.jsonl"
    out = tmp_path / "out"
    _write_jsonl(dataset, [_dataset_row(fixture_id) for fixture_id in TARGET_IDS])
    _write_jsonl(before, [_before_row(fixture_id) for fixture_id in TARGET_IDS])
    _write_jsonl(repair, [_repair_row(fixture_id, "The answer discussed honey bees and whales.") for fixture_id in TARGET_IDS])

    result = t108b.analyze(run_artifact=repair, before_jsonl=before, target_dataset=dataset, output_dir=out)

    assert result["repair_summary"]["decision"] == "FAIL_WITH_EVIDENCE"
    assert result["next_task_decision"]["next_task_mode"] == "final_qmsum_limitation_decision"
    assert "QMSum semantic correctness is proven." in result["claim_update"]["blocked_claims"]


def test_no_model_loading_in_task108b_analyzer() -> None:
    source = inspect.getsource(t108b)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
