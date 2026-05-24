import json
from pathlib import Path

from htfsd.cli import inspect_trace_schema
from htfsd.metrics.trace_schema import (
    required_baseline_trace_fields,
    required_controlled_trace_fields,
    required_live_trace_fields,
    validate_trace_file,
    validate_trace_record,
)


LIVE_RECORD = {
    "prompt_id": "trace-001",
    "bridge_status": "valid",
    "rejection_reason": None,
    "fallback_count": 0,
    "draft_valid_count": 1,
    "draft_rejected_count": 0,
    "qwen_expected_device": "cpu",
    "gemma_expected_device": "cuda",
    "qwen_device_status": "ok",
    "gemma_device_status": "ok",
    "qwen_n_gpu_layers": 0,
    "gemma_n_gpu_layers": -1,
    "qwen_model_file": "models/qwen/model.gguf",
    "gemma_model_file": "models/gemma/model.gguf",
    "latency_seconds": 1.0,
    "prompt_summary": "Prompt.",
    "qwen_output_summary": "Draft.",
    "gemma_output_summary": "Output.",
}


CONTROLLED_RECORD = {
    **LIVE_RECORD,
    "prompt_id": "controlled-001",
    "case_id": "empty_draft",
    "gemma_fallback_used": True,
}

BASELINE_RECORD = {
    "prompt_id": "baseline-001",
    "gemma_model_file": "models/gemma/model.gguf",
    "gemma_expected_device": "cuda",
    "gemma_device_status": "ok",
    "gemma_n_gpu_layers": -1,
    "latency_seconds": 1.0,
    "trace_kind": "target_baseline",
    "prompt_summary": "Prompt.",
    "gemma_output_summary": "Output.",
}


def test_live_trace_required_fields_are_guarded():
    required = required_live_trace_fields()

    assert "fallback_count" in required
    assert "gemma_device_status" in required
    assert "raw_draft_text" not in required
    assert "gemma_output_text" not in required
    assert validate_trace_record(LIVE_RECORD, mode="live").ok is True


def test_controlled_trace_required_fields_include_case_and_fallback_flag():
    required = required_controlled_trace_fields()

    assert "case_id" in required
    assert "gemma_fallback_used" in required
    assert required_live_trace_fields().issubset(required)
    assert validate_trace_record(CONTROLLED_RECORD, mode="controlled-fallback").ok is True


def test_baseline_trace_required_fields_do_not_include_low_tier_fields():
    required = required_baseline_trace_fields()

    assert "trace_kind" in required
    assert "gemma_model_file" in required
    assert "qwen_model_file" not in required
    assert "bridge_status" not in required
    assert "fallback_count" not in required
    assert validate_trace_record(BASELINE_RECORD, mode="target-baseline").ok is True


def test_schema_validator_fails_when_required_field_is_missing():
    record = dict(LIVE_RECORD)
    record.pop("fallback_count")

    result = validate_trace_record(record, mode="live")

    assert result.ok is False
    assert result.missing_fields == ["fallback_count"]


def test_baseline_schema_validator_fails_when_required_field_is_missing():
    record = dict(BASELINE_RECORD)
    record.pop("trace_kind")

    result = validate_trace_record(record, mode="target-baseline")

    assert result.ok is False
    assert result.missing_fields == ["trace_kind"]


def test_schema_validator_does_not_require_raw_text_fields():
    record = dict(LIVE_RECORD)

    result = validate_trace_record(record, mode="live")

    assert result.ok is True
    assert "raw_draft_text" not in record
    assert "gemma_output_text" not in record


def test_validate_trace_file_checks_all_records(tmp_path: Path):
    trace_path = tmp_path / "trace.json"
    bad_record = dict(CONTROLLED_RECORD)
    bad_record.pop("gemma_fallback_used")
    trace_path.write_text(
        json.dumps({"metadata": {"mode": "controlled-fallback"}, "records": [CONTROLLED_RECORD, bad_record]}),
        encoding="utf-8",
    )

    result = validate_trace_file(trace_path, mode="controlled-fallback")

    assert result.ok is False
    assert result.record_count == 2
    assert len(result.record_errors) == 1
    assert result.record_errors[0].missing_fields == ["gemma_fallback_used"]


def test_inspect_trace_schema_cli_reports_ok(tmp_path: Path, capsys):
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps({"metadata": {"mode": "live"}, "records": [LIVE_RECORD]}),
        encoding="utf-8",
    )

    exit_code = inspect_trace_schema.main([str(trace_path), "--mode", "live"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "trace schema: ok" in output
    assert "records: 1" in output
    assert "mode: live" in output


def test_inspect_trace_schema_cli_reports_missing_fields(tmp_path: Path, capsys):
    trace_path = tmp_path / "trace.json"
    bad_record = dict(LIVE_RECORD)
    bad_record.pop("gemma_device_status")
    trace_path.write_text(
        json.dumps({"metadata": {"mode": "live"}, "records": [bad_record]}),
        encoding="utf-8",
    )

    exit_code = inspect_trace_schema.main([str(trace_path), "--mode", "live"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "trace schema: failed" in output
    assert "missing_fields:" in output
    assert "- gemma_device_status" in output
