from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_dataset import audit_rows, reproducibility_check, summarize
from scripts.create_dataset import BuildOptions, build_rows, write_jsonl


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def test_audit_dataset_passes_sample_artifact_contract(tmp_path: Path):
    path = tmp_path / "dataset.jsonl"
    rows = build_rows(BuildOptions(output=path, max_samples=2, seed=3))
    write_jsonl(rows, path)

    audit = audit_rows(path)
    audit.reproducibility = {"byte_level_equal": True, "row_level_equal": True, "rows": 2, "mode": "sample", "seed": 41}
    summary = summarize(audit)

    assert summary["status"] == "PASS"
    assert summary["row_count"] == 2
    assert summary["duplicate_id_count"] == 0
    assert summary["source_modes"] == ["sample"]
    assert summary["readiness"]["builder_ready"] is True
    assert summary["readiness"]["sample_artifact_ready"] is True
    assert summary["readiness"]["full_benchmark_dataset_ready"] is False
    assert summary["context_words"]["min"] > 0
    assert summary["context_tokens"]["min"] > 0


def test_audit_dataset_rejects_duplicate_ids(tmp_path: Path):
    path = tmp_path / "dataset.jsonl"
    rows = build_rows(BuildOptions(output=path, max_samples=2, seed=4))
    rows[1]["id"] = rows[0]["id"]
    _write_rows(path, rows)

    audit = audit_rows(path)

    assert audit.status == "FAIL"
    assert any("duplicate row ids" in issue.message for issue in audit.issues)


def test_audit_dataset_rejects_answer_leakage_in_prompt(tmp_path: Path):
    path = tmp_path / "dataset.jsonl"
    rows = build_rows(BuildOptions(output=path, max_samples=1, seed=5))
    rows[0]["prompt"] = rows[0]["prompt"] + f" {rows[0]['ground_truth_answer']}"
    _write_rows(path, rows)

    audit = audit_rows(path)

    assert audit.status == "FAIL"
    assert any("final answer leaked into prompt" in issue.message for issue in audit.issues)


def test_audit_dataset_rejects_missing_runner_field(tmp_path: Path):
    path = tmp_path / "dataset.jsonl"
    rows = build_rows(BuildOptions(output=path, max_samples=1, seed=6))
    del rows[0]["expected_answer"]
    _write_rows(path, rows)

    audit = audit_rows(path)

    assert audit.status == "FAIL"
    assert any("missing runner-compatible fields" in issue.message for issue in audit.issues)


def test_reproducibility_check_uses_deterministic_sample_builder():
    result = reproducibility_check()

    assert result["mode"] == "sample"
    assert result["rows"] == 3
    assert result["row_level_equal"] is True
    assert result["byte_level_equal"] is True
