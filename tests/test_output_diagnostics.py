import json
from pathlib import Path

from htfsd.cli import classify_low_tier_trace
from htfsd.metrics.output_diagnostics import (
    classify_low_tier_record,
    classify_low_tier_trace_file,
    render_low_tier_classification_markdown,
    summarize_low_tier_classifications,
    write_low_tier_classification_markdown,
)


GENERATION_SETTINGS = {
    "max_tokens": 64,
    "temperature": 0.0,
    "seed": 42,
    "stop": None,
    "prompt_mode": "raw",
    "capture_raw_output": True,
    "output_summary_max_chars": 120,
}

VALID_RECORD = {
    "prompt_id": "trace-001",
    "bridge_status": "valid",
    "rejection_reason": None,
    "fallback_count": 0,
    "draft_valid_count": 1,
    "draft_rejected_count": 0,
    "generation_settings": GENERATION_SETTINGS,
    "qwen_raw_output": "draft",
    "gemma_raw_output": "continuation",
}

REJECTED_RECORD = {
    "prompt_id": "trace-002",
    "bridge_status": "rejected",
    "rejection_reason": "contains_unclosed_think",
    "fallback_count": 1,
    "draft_valid_count": 0,
    "draft_rejected_count": 1,
    "gemma_fallback_used": True,
    "generation_settings": GENERATION_SETTINGS,
    "qwen_raw_output": "<think>unfinished",
    "gemma_raw_output": "fallback",
}

FALLBACK_ONLY_RECORD = {
    "prompt_id": "trace-003",
    "bridge_status": "rejected",
    "rejection_reason": None,
    "fallback_count": 1,
    "draft_valid_count": 0,
    "draft_rejected_count": 0,
    "generation_settings": GENERATION_SETTINGS,
    "gemma_raw_output": "fallback",
}


def write_trace(path: Path, records: list[dict]) -> Path:
    path.write_text(json.dumps({"metadata": {"mode": "live"}, "records": records}), encoding="utf-8")
    return path


def test_valid_draft_record_classifies_as_valid_draft_continuation():
    result = classify_low_tier_record(VALID_RECORD)

    assert result.category == "valid_draft_continuation"
    assert result.prompt_id == "trace-001"
    assert result.missing_fields == []
    assert result.conflicting_fields == []


def test_rejected_draft_with_fallback_classifies_as_fallback_after_rejection():
    result = classify_low_tier_record(REJECTED_RECORD)

    assert result.category == "fallback_after_rejection"
    assert result.rejection_reason == "contains_unclosed_think"
    assert result.fallback_count == 1
    assert "Gemma fallback" in result.warnings[0]


def test_incomplete_fallback_record_classifies_as_fallback_only():
    result = classify_low_tier_record(FALLBACK_ONLY_RECORD)

    assert result.category == "fallback_only"
    assert result.warnings == [
        "This record used Gemma fallback. Any string match mostly reflects fallback behavior, not successful draft contribution."
    ]


def test_missing_required_fields_classifies_as_unknown_contribution():
    result = classify_low_tier_record({"prompt_id": "broken"})

    assert result.category == "unknown_contribution"
    assert "bridge_status" in result.missing_fields
    assert "fallback_count" in result.missing_fields
    assert "generation_settings.prompt_mode" in result.missing_fields
    assert result.reason == "missing_required_fields"


def test_contradictory_fields_classify_as_unknown_contribution():
    record = {**VALID_RECORD, "fallback_count": 1}

    result = classify_low_tier_record(record)

    assert result.category == "unknown_contribution"
    assert "bridge_status_valid_with_fallback_count" in result.conflicting_fields
    assert result.reason == "conflicting_classification_fields"


def test_summary_counts_categories_and_records_field_issues():
    records = [
        VALID_RECORD,
        REJECTED_RECORD,
        FALLBACK_ONLY_RECORD,
        {"prompt_id": "broken"},
        {**VALID_RECORD, "prompt_id": "conflict", "fallback_count": 1},
    ]

    summary = summarize_low_tier_classifications(records)

    assert summary.total_records == 5
    assert summary.valid_draft_continuation_count == 1
    assert summary.fallback_after_rejection_count == 1
    assert summary.fallback_only_count == 1
    assert summary.unknown_contribution_count == 2
    assert summary.unknown_record_ids == ["broken", "conflict"]
    assert "broken" in summary.missing_fields_by_record
    assert "conflict" in summary.conflicting_fields_by_record


def test_trace_file_classification_reads_records(tmp_path: Path):
    trace_path = write_trace(tmp_path / "trace.json", [VALID_RECORD, REJECTED_RECORD])

    summary = classify_low_tier_trace_file(trace_path)

    assert summary.total_records == 2
    assert summary.valid_draft_continuation_count == 1
    assert summary.fallback_after_rejection_count == 1


def test_markdown_report_includes_non_claims(tmp_path: Path):
    trace_path = write_trace(tmp_path / "trace.json", [VALID_RECORD, REJECTED_RECORD])
    summary = classify_low_tier_trace_file(trace_path)

    markdown = render_low_tier_classification_markdown(summary)

    assert "# Low-Tier Contribution Classification" in markdown
    assert "No output parity claim is made." in markdown
    assert "No target-equivalence claim is made." in markdown
    assert "No correctness claim is made." in markdown
    assert "No lossless-generation claim is made." in markdown
    assert "No benchmark claim is made." in markdown
    assert "No draft-acceptance metric is reported." in markdown
    lowered = markdown.lower()
    assert ("outputs are " + "equal") not in lowered
    assert "speed" + "up" not in lowered


def test_cli_writes_markdown_report(tmp_path: Path, capsys):
    trace_path = write_trace(tmp_path / "trace.json", [VALID_RECORD, REJECTED_RECORD])
    output_dir = tmp_path / "reports"

    exit_code = classify_low_tier_trace.main([str(trace_path), "--output-dir", str(output_dir)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "low-tier classification: ok" in output
    assert "total_records: 2" in output
    assert "valid_draft_continuation_count: 1" in output
    assert "fallback_after_rejection_count: 1" in output
    assert list(output_dir.glob("*-low-tier-classification.md"))


def test_report_writer_does_not_overwrite_same_second_reports(tmp_path: Path):
    summary = summarize_low_tier_classifications([VALID_RECORD])

    first = write_low_tier_classification_markdown(summary=summary, output_dir=tmp_path)
    second = write_low_tier_classification_markdown(summary=summary, output_dir=tmp_path)

    assert first != second
    assert first.exists()
    assert second.exists()
