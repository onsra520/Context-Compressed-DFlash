from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_1_system_build_and_evaluation.audits.smoke_artifacts import ARTIFACTS, audit_artifact, resolve_artifact_paths


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_audit_artifact_passes_valid_llmlingua_ar_contract(tmp_path: Path):
    path = tmp_path / "llmlingua_ar.jsonl"
    _write_jsonl(
        path,
        [
            {
                "condition": "LLMLingua-AR-R2",
                "prompt_id": 1,
                "input_tokens": 10,
                "output_tokens": 3,
                "generation_time_s": 0.5,
                "tok_per_sec": 6.0,
                "acceptance_lengths": [],
                "tau_mean": 0.0,
                "vram_allocated_gib": 2.5,
                "vram_reserved_gib": 2.6,
                "t_compress_ms": 100.0,
                "R_actual": 2.0,
                "N_original": 20,
                "N_compressed": 10,
                "keep_rate": 0.5,
                "compressor_model": "locked/model",
                "question_preserved": True,
                "generation_mode": "autoregressive",
                "draft_used": False,
            }
        ],
    )

    audit = audit_artifact(path)

    assert audit.status == "PASS"
    assert audit.condition == "LLMLingua-AR-R2"
    assert audit.row_count == 1
    assert audit.issues == []


def test_audit_artifact_warns_for_unknown_condition(tmp_path: Path):
    path = tmp_path / "unknown.jsonl"
    _write_jsonl(
        path,
        [
            {
                "condition": "Unknown-Smoke",
                "prompt_id": 1,
                "input_tokens": 10,
                "output_tokens": 0,
                "generation_time_s": 0.1,
                "tok_per_sec": 0.0,
                "acceptance_lengths": [],
                "tau_mean": 0.0,
                "vram_allocated_gib": 1.0,
                "vram_reserved_gib": 1.1,
            }
        ],
    )

    audit = audit_artifact(path)

    assert audit.status == "WARN"
    assert any("unknown condition" in issue.message for issue in audit.issues)


def test_audit_artifact_fails_for_missing_required_field(tmp_path: Path):
    path = tmp_path / "broken.jsonl"
    _write_jsonl(
        path,
        [
            {
                "condition": "DFlash-R1",
                "prompt_id": 1,
                "input_tokens": 12,
                "output_tokens": 2,
                "generation_time_s": 0.2,
                "tok_per_sec": 10.0,
                "acceptance_lengths": [1],
                "tau_mean": 1.0,
                "vram_allocated_gib": 1.2,
            }
        ],
    )

    audit = audit_artifact(path)

    assert audit.status == "FAIL"
    assert any("vram_reserved_gib" in issue.message for issue in audit.issues)


def test_resolve_artifact_paths_uses_explicit_paths_when_provided():
    explicit = ["results/a.jsonl", "results/b.jsonl"]

    paths = resolve_artifact_paths(explicit)

    assert paths == [Path("results/a.jsonl"), Path("results/b.jsonl")]
    assert paths != ARTIFACTS
