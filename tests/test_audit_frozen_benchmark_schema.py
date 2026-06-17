from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_frozen_benchmark_schema import audit_artifact


def _base_row(**overrides):
    row = {
        "timestamp": "2026-06-05T00:00:00+00:00",
        "condition": "DFlash-R1",
        "prompt_id": 1,
        "prompt_hash": "abc123",
        "input_tokens": 400,
        "output_tokens": 16,
        "generation_time_s": 2.0,
        "tok_per_sec": 8.0,
        "acceptance_lengths": [4, 4, 8],
        "tau_mean": 5.333333333333333,
        "t_prefill_ms": 123.0,
        "t_prefill_mode": "cuda_synchronized",
        "prefill_vram_allocated_gib": None,
        "prefill_vram_reserved_gib": None,
        "max_new_tokens": 128,
        "block_size": 16,
        "device": "cuda:0",
        "target_path": "models/Qwen3-4B",
        "draft_path": "models/Qwen3-4B-DFlash-b16",
        "tokenizer_path": "models/Qwen3-4B",
        "backend_warning": "flash_attn not installed; using torch.sdpa fallback.",
        "vram_allocated_gib": 3.5,
        "vram_reserved_gib": 3.8,
        "generated_text": "Reasoning...\nAnswer: 26",
        "generated_token_count": 12,
        "prompt_source": "dataset",
        "dataset_id": "gsm8k_short_test_0001",
        "domain": "numeric_qa",
        "expected_answer": "26",
        "evidence": "GSM8K answer is 26.",
        "approximate_context_words": 300,
        "approximate_context_tokens": None,
        "t_compress_ms": None,
        "R_actual": None,
        "N_original": None,
        "N_compressed": None,
        "keep_rate": None,
        "compressor_model": None,
        "question_preserved": None,
        "generation_mode": "dflash",
        "draft_used": True,
    }
    row.update(overrides)
    return row


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_frozen_schema_passes_dflash_row_with_nullable_compression_fields(tmp_path: Path):
    path = tmp_path / "dflash.jsonl"
    _write_jsonl(path, [_base_row()])

    audit = audit_artifact(path)

    assert audit.status == "PASS"
    assert audit.row_count == 1
    assert audit.condition == "DFlash-R1"


def test_frozen_schema_fails_when_generated_text_is_missing(tmp_path: Path):
    path = tmp_path / "missing_text.jsonl"
    row = _base_row()
    del row["generated_text"]
    _write_jsonl(path, [row])

    audit = audit_artifact(path)

    assert audit.status == "FAIL"
    assert any("generated_text" in issue.message for issue in audit.issues)


def test_frozen_schema_fails_when_max_new_tokens_is_too_small(tmp_path: Path):
    path = tmp_path / "short.jsonl"
    _write_jsonl(path, [_base_row(max_new_tokens=32)])

    audit = audit_artifact(path)

    assert audit.status == "FAIL"
    assert any("max_new_tokens" in issue.message and ">= 128" in issue.message for issue in audit.issues)


def test_frozen_schema_passes_baseline_ar_with_empty_acceptance_and_no_draft(tmp_path: Path):
    path = tmp_path / "baseline_ar.jsonl"
    _write_jsonl(
        path,
        [
            _base_row(
                condition="Baseline-AR",
                acceptance_lengths=[],
                tau_mean=0.0,
                draft_path=None,
                block_size=None,
                generation_mode="autoregressive",
                draft_used=False,
            )
        ],
    )

    audit = audit_artifact(path)

    assert audit.status == "PASS"


def test_frozen_schema_passes_compression_row_with_required_non_null_fields(tmp_path: Path):
    path = tmp_path / "cc.jsonl"
    _write_jsonl(
        path,
        [
            _base_row(
                condition="CC-LLM-R2",
                t_compress_ms=50.0,
                R_actual=2.0,
                N_original=100,
                N_compressed=50,
                keep_rate=0.5,
                compressor_model="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
                question_preserved=True,
            )
        ],
    )

    audit = audit_artifact(path)

    assert audit.status == "PASS"


def test_frozen_schema_fails_compression_row_when_nullable_fields_are_missing(tmp_path: Path):
    path = tmp_path / "cc_missing.jsonl"
    row = _base_row(condition="CC-LLM-R2", question_preserved=True)
    del row["t_compress_ms"]
    _write_jsonl(path, [row])

    audit = audit_artifact(path)

    assert audit.status == "FAIL"
    assert any("t_compress_ms" in issue.message for issue in audit.issues)
