import json
from pathlib import Path

from htfsd.cli import select_diagnostic_records
from htfsd.metrics.diagnostic_record_selection import (
    render_diagnostic_record_selection_markdown,
    select_diagnostic_record,
    select_diagnostic_records_from_traces,
    summarize_diagnostic_record_selection,
)


SETTINGS = {
    "max_tokens": 64,
    "temperature": 0.0,
    "seed": 42,
    "stop": None,
    "prompt_mode": "raw",
    "capture_raw_output": True,
    "output_summary_max_chars": 120,
}


def selection_record(
    *,
    prompt_id: str = "trace-001",
    contribution_category: str = "valid_draft_continuation",
    bridge_status: str = "valid",
    fallback_count: int = 0,
    draft_valid_count: int = 1,
    draft_rejected_count: int = 0,
    prompt_mode: str = "raw",
    baseline_empty_after_normalization: bool = False,
    low_tier_empty_after_normalization: bool = False,
    normalized_outputs_exact_string_match: bool | None = False,
    generation_settings_match: bool = True,
    extra: dict | None = None,
) -> dict:
    record = {
        "prompt_id": prompt_id,
        "contribution_category": contribution_category,
        "bridge_status": bridge_status,
        "fallback_count": fallback_count,
        "draft_valid_count": draft_valid_count,
        "draft_rejected_count": draft_rejected_count,
        "generation_settings": {**SETTINGS, "prompt_mode": prompt_mode},
        "baseline_empty_after_normalization": baseline_empty_after_normalization,
        "low_tier_empty_after_normalization": low_tier_empty_after_normalization,
        "baseline_normalized_length": 0 if baseline_empty_after_normalization else 12,
        "low_tier_normalized_length": 0 if low_tier_empty_after_normalization else 8,
        "normalized_outputs_exact_string_match": normalized_outputs_exact_string_match,
        "generation_settings_match": generation_settings_match,
        "prompt_coverage_status": "ok",
        "runtime_metadata_match": True,
    }
    if extra:
        record.update(extra)
    return record


def low_record(
    prompt_id: str,
    *,
    bridge_status: str = "valid",
    rejection_reason: str | None = None,
    fallback_count: int = 0,
    draft_valid_count: int = 1,
    draft_rejected_count: int = 0,
    gemma_raw_output: str = "draft output",
    prompt_mode: str = "raw",
    extra: dict | None = None,
) -> dict:
    record = {
        "prompt_id": prompt_id,
        "prompt_summary": "short prompt",
        "bridge_status": bridge_status,
        "rejection_reason": rejection_reason,
        "fallback_count": fallback_count,
        "draft_valid_count": draft_valid_count,
        "draft_rejected_count": draft_rejected_count,
        "qwen_expected_device": "cpu",
        "gemma_expected_device": "cuda",
        "qwen_device_status": "ok",
        "gemma_device_status": "ok",
        "qwen_n_gpu_layers": 0,
        "gemma_n_gpu_layers": -1,
        "qwen_model_file": "models/qwen.gguf",
        "gemma_model_file": "models/gemma.gguf",
        "latency_seconds": 2.0,
        "generation_settings": {**SETTINGS, "prompt_mode": prompt_mode},
        "capture_raw_output": True,
        "raw_prompt": "Prompt.",
        "qwen_raw_output": "Draft.",
        "gemma_raw_output": gemma_raw_output,
    }
    if extra:
        record.update(extra)
    return record


def baseline_record(
    prompt_id: str,
    *,
    baseline_raw_output: str = "baseline output",
    prompt_mode: str = "raw",
) -> dict:
    return {
        "prompt_id": prompt_id,
        "prompt_summary": "short prompt",
        "gemma_model_file": "models/gemma.gguf",
        "gemma_expected_device": "cuda",
        "gemma_device_status": "ok",
        "gemma_n_gpu_layers": -1,
        "latency_seconds": 1.0,
        "trace_kind": "target_baseline",
        "generation_settings": {**SETTINGS, "prompt_mode": prompt_mode},
        "capture_raw_output": True,
        "raw_prompt": "Prompt.",
        "baseline_raw_output": baseline_raw_output,
    }


def write_trace(path: Path, records: list[dict], mode: str) -> Path:
    prompt_mode = records[0].get("generation_settings", {}).get("prompt_mode", "raw") if records else "raw"
    path.write_text(
        json.dumps(
            {
                "metadata": {
                    "mode": mode,
                    "capture_raw_output": True,
                    "generation_settings": {**SETTINGS, "prompt_mode": prompt_mode},
                },
                "records": records,
            }
        ),
        encoding="utf-8",
    )
    return path


def matching_paths(tmp_path: Path, low_records: list[dict], baseline_records: list[dict]) -> tuple[Path, Path]:
    return (
        write_trace(tmp_path / "low.json", low_records, "live"),
        write_trace(tmp_path / "baseline.json", baseline_records, "target-baseline"),
    )


def test_valid_draft_record_with_complete_metadata_is_eligible():
    selection = select_diagnostic_record(selection_record())

    assert selection.selection_category == "eligible_valid_draft_record"
    assert selection.eligible_for_draft_contribution_diagnostic is True
    assert selection.exclusion_reasons == []


def test_fallback_after_rejection_record_is_excluded_as_fallback_derived():
    selection = select_diagnostic_record(
        selection_record(
            contribution_category="fallback_after_rejection",
            bridge_status="rejected",
            fallback_count=1,
            draft_valid_count=0,
            draft_rejected_count=1,
            extra={"gemma_fallback_used": True},
        )
    )

    assert selection.selection_category == "excluded_fallback_derived_record"
    assert selection.eligible_for_draft_contribution_diagnostic is False
    assert "fallback_derived" in selection.exclusion_reasons


def test_fallback_only_record_is_excluded_as_fallback_derived():
    selection = select_diagnostic_record(
        selection_record(
            contribution_category="fallback_only",
            bridge_status="valid",
            fallback_count=1,
            draft_valid_count=0,
            draft_rejected_count=0,
        )
    )

    assert selection.selection_category == "excluded_fallback_derived_record"
    assert "fallback_derived" in selection.exclusion_reasons


def test_unknown_contribution_record_is_excluded_as_unknown():
    selection = select_diagnostic_record(
        selection_record(
            contribution_category="unknown_contribution",
            extra={"missing_fields": ["generation_settings.prompt_mode"]},
        )
    )

    assert selection.selection_category == "excluded_unknown_contribution_record"
    assert "unknown_contribution" in selection.exclusion_reasons


def test_empty_baseline_record_is_excluded_unless_higher_priority_applies():
    empty_selection = select_diagnostic_record(selection_record(baseline_empty_after_normalization=True))
    fallback_empty_selection = select_diagnostic_record(
        selection_record(
            contribution_category="fallback_after_rejection",
            bridge_status="rejected",
            fallback_count=1,
            draft_valid_count=0,
            draft_rejected_count=1,
            baseline_empty_after_normalization=True,
        )
    )

    assert empty_selection.selection_category == "excluded_empty_baseline_record"
    assert "empty_baseline" in empty_selection.exclusion_reasons
    assert fallback_empty_selection.selection_category == "excluded_fallback_derived_record"
    assert "empty_baseline" in fallback_empty_selection.exclusion_reasons


def test_raw_prompt_mode_with_empty_baseline_emits_prompt_mode_warning():
    selection = select_diagnostic_record(selection_record(prompt_mode="raw", baseline_empty_after_normalization=True))

    assert "prompt_mode_risk" in selection.exclusion_reasons
    assert any("Raw prompt mode" in warning for warning in selection.warnings)


def test_chat_fallback_derived_record_emits_prompt_mode_and_fallback_warning():
    selection = select_diagnostic_record(
        selection_record(
            contribution_category="fallback_after_rejection",
            bridge_status="rejected",
            fallback_count=1,
            draft_valid_count=0,
            draft_rejected_count=1,
            prompt_mode="chat",
        )
    )

    assert selection.selection_category == "excluded_fallback_derived_record"
    assert "prompt_mode_risk" in selection.exclusion_reasons
    assert any("Chat prompt mode" in warning for warning in selection.warnings)
    assert any("fallback" in warning.lower() for warning in selection.warnings)


def test_multiple_exclusion_reasons_are_preserved_and_priority_selects_unknown():
    selection = select_diagnostic_record(
        selection_record(
            contribution_category="unknown_contribution",
            fallback_count=1,
            baseline_empty_after_normalization=True,
            prompt_mode="raw",
            extra={"missing_fields": ["bridge_status"]},
        )
    )

    assert selection.selection_category == "excluded_unknown_contribution_record"
    assert "unknown_contribution" in selection.exclusion_reasons
    assert "fallback_derived" in selection.exclusion_reasons
    assert "empty_baseline" in selection.exclusion_reasons
    assert "prompt_mode_risk" in selection.exclusion_reasons


def test_summary_counts_selection_categories():
    summary = summarize_diagnostic_record_selection(
        [
            selection_record(prompt_id="trace-001"),
            selection_record(
                prompt_id="trace-002",
                contribution_category="fallback_after_rejection",
                bridge_status="rejected",
                fallback_count=1,
                draft_valid_count=0,
                draft_rejected_count=1,
            ),
            selection_record(prompt_id="trace-003", contribution_category="unknown_contribution"),
            selection_record(prompt_id="trace-004", baseline_empty_after_normalization=True),
        ]
    )

    assert summary.total_records == 4
    assert summary.eligible_valid_draft_record_count == 1
    assert summary.excluded_fallback_derived_record_count == 1
    assert summary.excluded_unknown_contribution_record_count == 1
    assert summary.excluded_empty_baseline_record_count == 1
    assert summary.eligible_prompt_ids == ["trace-001"]


def test_trace_selection_reuses_existing_diagnostic_layers(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [
            low_record("trace-001", gemma_raw_output="draft output"),
            low_record("trace-002", gemma_raw_output=""),
        ],
        [
            baseline_record("baseline-001", baseline_raw_output="baseline output"),
            baseline_record("baseline-002", baseline_raw_output=""),
        ],
    )

    summary = select_diagnostic_records_from_traces(low_tier_path=low_path, baseline_path=baseline_path)

    assert summary.selection_ready is True
    assert summary.total_records == 2
    assert summary.eligible_valid_draft_record_count == 1
    assert summary.excluded_empty_baseline_record_count == 1


def test_cli_writes_markdown_and_json_reports(tmp_path: Path, capsys):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001", gemma_raw_output="draft output")],
        [baseline_record("baseline-001", baseline_raw_output="baseline output")],
    )
    output_dir = tmp_path / "reports"

    exit_code = select_diagnostic_records.main(
        ["--low-tier", str(low_path), "--baseline", str(baseline_path), "--output-dir", str(output_dir)]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "diagnostic record selection: ok" in output
    assert "selection_ready: yes" in output
    assert list(output_dir.glob("*-diagnostic-record-selection.md"))
    assert list(output_dir.glob("*-diagnostic-record-selection.json"))


def test_markdown_report_includes_explicit_non_claims():
    summary = summarize_diagnostic_record_selection([selection_record()])

    markdown = render_diagnostic_record_selection_markdown(summary)

    assert "This is not an output equality report." in markdown
    assert "No output parity claim is made." in markdown
    assert "No target-equivalence claim is made." in markdown
    assert "No correctness claim is made." in markdown
    assert "No lossless-generation claim is made." in markdown
    assert "No benchmark claim is made." in markdown
    assert "No draft-acceptance metric is reported." in markdown
    lowered = markdown.lower()
    assert ("outputs are " + "equal") not in lowered
    assert "speed" + "up" not in lowered
