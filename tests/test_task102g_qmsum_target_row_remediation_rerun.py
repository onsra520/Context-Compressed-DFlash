from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task102g_qmsum_target_row_remediation_rerun as t102g


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


def _target_dataset_row(fixture_id: str, **extra: object) -> dict[str, object]:
    row = {
        "id": fixture_id,
        "context": f"Meeting context for {fixture_id}.",
        "question": f"What happened in {fixture_id}?",
        "expected_answer": f"Reference answer for {fixture_id}.",
        "prompt": f"Meeting transcript:\nEvidence for {fixture_id}.\n\nQuestion: What happened?",
    }
    row.update(extra)
    return row


def _run_row(fixture_id: str, **extra: object) -> dict[str, object]:
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
        "qmsum_answer_policy_type": "qmsum_targeted_evidence_repair_v1",
        "qmsum_answer_policy_preserved": True,
        "generated_text": f"Evidence-focused output for {fixture_id}.",
        "generated_token_count": 42,
        "output_tokens": 42,
        "max_new_tokens": 384,
        "t_compress_ms": 100.0,
        "generation_time_s": 4.0,
        "tok_per_sec": 20.0,
        "R_actual": 2.0,
        "tau_mean": 2.0,
        "t_prefill_ms": 300.0,
        "vram_allocated_gib": 4.0,
        "vram_reserved_gib": 5.0,
        "expected_answer": f"Reference answer for {fixture_id}.",
    }
    row.update(extra)
    return row


def test_target_dataset_validation_catches_wrong_row_count(tmp_path: Path) -> None:
    dataset = tmp_path / "target.jsonl"
    _write_jsonl(dataset, [_target_dataset_row("qmsum_meeting_qa_test_0036")])

    audit = t102g.validate_target_dataset(dataset)

    assert audit["valid"] is False
    assert "expected 6 rows" in " ".join(audit["errors"])


def test_target_dataset_validation_rejects_generated_output_leakage(tmp_path: Path) -> None:
    dataset = tmp_path / "target.jsonl"
    rows = [_target_dataset_row(fixture_id) for fixture_id in EXPECTED_IDS]
    rows[0]["generated_text"] = "must not enter prompt inputs"
    _write_jsonl(dataset, rows)

    audit = t102g.validate_target_dataset(dataset)

    assert audit["valid"] is False
    assert "generated-output fields present" in " ".join(audit["errors"])


def test_metadata_audit_requires_light_cuda_and_policy_override() -> None:
    rows = [_run_row(fixture_id) for fixture_id in EXPECTED_IDS]
    rows[0]["compressor_device_map"] = "cpu"

    audit = t102g.audit_run_metadata(rows)

    assert audit["valid"] is False
    assert "compressor_device_map" in " ".join(audit["errors"])


def test_analyzer_writes_outputs_and_routes_to_t102h_when_run_is_complete(tmp_path: Path) -> None:
    dataset = tmp_path / "target.jsonl"
    run = tmp_path / "run.jsonl"
    out = tmp_path / "out"
    _write_jsonl(dataset, [_target_dataset_row(fixture_id) for fixture_id in EXPECTED_IDS])
    _write_jsonl(run, [_run_row(fixture_id) for fixture_id in EXPECTED_IDS])

    result = t102g.analyze(run_artifact=run, target_dataset=dataset, output_dir=out)

    assert result["decision"] == "PASS_WITH_CAVEAT"
    assert result["next_task_decision"]["next_task"] == "T102H — QMSum Remediation Reassessment"
    for relative in t102g.OUTPUT_RELATIVE_PATHS:
        assert (out / relative).exists()


def test_next_task_is_t102a_when_run_fails_metadata_gate(tmp_path: Path) -> None:
    dataset = tmp_path / "target.jsonl"
    run = tmp_path / "run.jsonl"
    out = tmp_path / "out"
    _write_jsonl(dataset, [_target_dataset_row(fixture_id) for fixture_id in EXPECTED_IDS])
    rows = [_run_row(fixture_id) for fixture_id in EXPECTED_IDS]
    rows[0]["qmsum_policy_suffix_override"] = False
    _write_jsonl(run, rows)

    result = t102g.analyze(run_artifact=run, target_dataset=dataset, output_dir=out)

    assert result["decision"] == "PARTIAL"
    assert result["next_task_decision"]["next_task"] == "T102A — QMSum Failure Audit / Fix"


def test_no_model_loading_in_task102g_analyzer() -> None:
    source = inspect.getsource(t102g)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
