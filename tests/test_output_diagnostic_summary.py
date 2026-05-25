import json
from pathlib import Path

from htfsd.cli import summarize_output_diagnostics
from htfsd.metrics.output_diagnostic_summary import (
    build_fallback_aware_output_diagnostic_summary,
    render_fallback_aware_output_diagnostic_summary_markdown,
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


def low_record(
    prompt_id: str,
    *,
    bridge_status: str = "valid",
    rejection_reason: str | None = None,
    fallback_count: int = 0,
    draft_valid_count: int = 1,
    draft_rejected_count: int = 0,
    gemma_raw_output: str = "Gemma low-tier output.",
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
    baseline_raw_output: str = "Gemma baseline output.",
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


def write_trace(path: Path, records: list[dict], mode: str, *, capture_raw_output: bool = True) -> Path:
    prompt_mode = records[0].get("generation_settings", {}).get("prompt_mode", "raw") if records else "raw"
    path.write_text(
        json.dumps(
            {
                "metadata": {
                    "mode": mode,
                    "capture_raw_output": capture_raw_output,
                    "generation_settings": {
                        **SETTINGS,
                        "prompt_mode": prompt_mode,
                        "capture_raw_output": capture_raw_output,
                    },
                },
                "records": records,
            }
        ),
        encoding="utf-8",
    )
    return path


def matching_paths(tmp_path: Path, low_records: list[dict], baseline_records: list[dict]) -> tuple[Path, Path]:
    low_path = write_trace(tmp_path / "low.json", low_records, "live")
    baseline_path = write_trace(tmp_path / "baseline.json", baseline_records, "target-baseline")
    return low_path, baseline_path


def test_summary_succeeds_when_precheck_passes(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001")],
        [baseline_record("baseline-001")],
    )

    summary = build_fallback_aware_output_diagnostic_summary(low_tier_path=low_path, baseline_path=baseline_path)

    assert summary["summary_ready"] is True
    assert summary["precheck_ready"] is True
    assert summary["total_records"] == 1


def test_summary_reports_not_ready_when_precheck_fails(tmp_path: Path):
    broken = low_record("trace-001")
    broken["capture_raw_output"] = False
    broken.pop("raw_prompt")
    broken.pop("qwen_raw_output")
    broken.pop("gemma_raw_output")
    low_path = write_trace(tmp_path / "low.json", [broken], "live", capture_raw_output=False)
    baseline_path = write_trace(tmp_path / "baseline.json", [baseline_record("baseline-001")], "target-baseline")

    summary = build_fallback_aware_output_diagnostic_summary(low_tier_path=low_path, baseline_path=baseline_path)

    assert summary["summary_ready"] is False
    assert summary["precheck_ready"] is False
    assert "raw_capture_missing" in summary["blocking_reasons"]


def test_valid_draft_records_are_summarized_separately(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001", gemma_raw_output="same")],
        [baseline_record("baseline-001", baseline_raw_output="same")],
    )

    category = build_fallback_aware_output_diagnostic_summary(low_tier_path=low_path, baseline_path=baseline_path)[
        "category_summaries"
    ]["valid_draft_continuation"]

    assert category["record_count"] == 1
    assert category["prompt_ids"] == ["trace-001"]
    assert category["diagnostic_exact_string_match_count"] == 1
    assert category["diagnostic_exact_string_mismatch_count"] == 0


def test_fallback_derived_records_are_summarized_separately(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [
            low_record(
                "trace-001",
                bridge_status="rejected",
                rejection_reason="contains_unclosed_think",
                fallback_count=1,
                draft_valid_count=0,
                draft_rejected_count=1,
                gemma_raw_output="fallback",
                extra={"gemma_fallback_used": True},
            )
        ],
        [baseline_record("baseline-001", baseline_raw_output="different")],
    )

    summary = build_fallback_aware_output_diagnostic_summary(low_tier_path=low_path, baseline_path=baseline_path)
    category = summary["category_summaries"]["fallback_after_rejection"]

    assert category["record_count"] == 1
    assert category["diagnostic_exact_string_match_count"] == 0
    assert category["diagnostic_exact_string_mismatch_count"] == 1
    assert any("fallback-derived records" in warning for warning in summary["warnings"])


def test_unknown_records_are_summarized_separately(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [
            low_record(
                "trace-001",
                bridge_status="valid",
                fallback_count=1,
                gemma_raw_output="ambiguous",
            )
        ],
        [baseline_record("baseline-001", baseline_raw_output="ambiguous")],
    )

    summary = build_fallback_aware_output_diagnostic_summary(low_tier_path=low_path, baseline_path=baseline_path)
    category = summary["category_summaries"]["unknown_contribution"]

    assert category["record_count"] == 1
    assert summary["unknown_contribution_count"] == 1
    assert any("unknown contribution category" in warning for warning in summary["warnings"])


def test_majority_fallback_records_emit_trace_level_warning(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [
            low_record(
                "trace-001",
                bridge_status="rejected",
                rejection_reason="empty_after_normalization",
                fallback_count=1,
                draft_valid_count=0,
                draft_rejected_count=1,
                extra={"gemma_fallback_used": True},
            ),
            low_record(
                "trace-002",
                bridge_status="rejected",
                rejection_reason="contains_unclosed_think",
                fallback_count=1,
                draft_valid_count=0,
                draft_rejected_count=1,
                extra={"gemma_fallback_used": True},
            ),
            low_record("trace-003"),
        ],
        [
            baseline_record("baseline-001"),
            baseline_record("baseline-002"),
            baseline_record("baseline-003"),
        ],
    )

    summary = build_fallback_aware_output_diagnostic_summary(low_tier_path=low_path, baseline_path=baseline_path)

    assert summary["fallback_after_rejection_count"] == 2
    assert any("Most low-tier records" in warning for warning in summary["warnings"])


def test_baseline_empty_and_raw_prompt_mode_emit_warnings(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001", gemma_raw_output="visible", prompt_mode="raw")],
        [baseline_record("baseline-001", baseline_raw_output="  \n  ", prompt_mode="raw")],
    )

    summary = build_fallback_aware_output_diagnostic_summary(low_tier_path=low_path, baseline_path=baseline_path)

    assert summary["all_baseline_outputs_present"] is True
    assert summary["category_summaries"]["valid_draft_continuation"]["empty_baseline_count"] == 1
    assert any("baseline outputs are empty after normalization" in warning for warning in summary["warnings"])
    assert any("Raw prompt mode may produce empty Gemma baseline outputs" in warning for warning in summary["warnings"])


def test_report_includes_explicit_non_claims(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001")],
        [baseline_record("baseline-001")],
    )
    summary = build_fallback_aware_output_diagnostic_summary(low_tier_path=low_path, baseline_path=baseline_path)

    markdown = render_fallback_aware_output_diagnostic_summary_markdown(summary)

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


def test_summary_cli_writes_markdown_and_json_reports(tmp_path: Path, capsys):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001")],
        [baseline_record("baseline-001")],
    )
    output_dir = tmp_path / "reports"

    exit_code = summarize_output_diagnostics.main(
        ["--low-tier", str(low_path), "--baseline", str(baseline_path), "--output-dir", str(output_dir)]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "fallback-aware output diagnostic summary: ok" in output
    assert "summary_ready: yes" in output
    assert list(output_dir.glob("*-fallback-aware-output-diagnostic-summary.md"))
    assert list(output_dir.glob("*-fallback-aware-output-diagnostic-summary.json"))
