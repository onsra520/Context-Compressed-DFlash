import json
from pathlib import Path

from htfsd.cli import diagnose_output_comparison
from htfsd.metrics.output_diagnostic_compare import (
    build_diagnostic_output_comparison,
    render_diagnostic_output_comparison_markdown,
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
    gemma_raw_output: str = "same",
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
    baseline_raw_output: str = "same",
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


def fallback_record(prompt_id: str, *, gemma_raw_output: str = "same") -> dict:
    return low_record(
        prompt_id,
        bridge_status="rejected",
        rejection_reason="contains_unclosed_think",
        fallback_count=1,
        draft_valid_count=0,
        draft_rejected_count=1,
        gemma_raw_output=gemma_raw_output,
        extra={"gemma_fallback_used": True},
    )


def test_diagnostic_comparison_succeeds_when_precheck_passes(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001")],
        [baseline_record("baseline-001")],
    )

    result = build_diagnostic_output_comparison(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["diagnostic_ready"] is True
    assert result["precheck_ready"] is True
    assert result["total_records"] == 1


def test_diagnostic_comparison_reports_category_level_exact_string_counts(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [
            low_record("trace-001", gemma_raw_output="same"),
            low_record("trace-002", gemma_raw_output="different"),
        ],
        [
            baseline_record("baseline-001", baseline_raw_output="same"),
            baseline_record("baseline-002", baseline_raw_output="baseline"),
        ],
    )

    result = build_diagnostic_output_comparison(low_tier_path=low_path, baseline_path=baseline_path)
    category = result["category_results"]["valid_draft_continuation"]

    assert result["diagnostic_exact_string_match_count"] == 1
    assert result["diagnostic_exact_string_mismatch_count"] == 1
    assert category["diagnostic_exact_string_match_count"] == 1
    assert category["diagnostic_exact_string_mismatch_count"] == 1


def test_valid_draft_matches_are_counted_separately_from_fallback_matches(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [
            low_record("trace-001", gemma_raw_output="same"),
            fallback_record("trace-002", gemma_raw_output="same"),
        ],
        [
            baseline_record("baseline-001", baseline_raw_output="same"),
            baseline_record("baseline-002", baseline_raw_output="same"),
        ],
    )

    result = build_diagnostic_output_comparison(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["valid_draft_diagnostic_match_count"] == 1
    assert result["fallback_derived_diagnostic_match_count"] == 1
    assert result["valid_draft_diagnostic_mismatch_count"] == 0
    assert result["fallback_derived_diagnostic_mismatch_count"] == 0


def test_fallback_derived_matches_emit_required_warnings(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [fallback_record("trace-001", gemma_raw_output="same")],
        [baseline_record("baseline-001", baseline_raw_output="same")],
    )

    result = build_diagnostic_output_comparison(low_tier_path=low_path, baseline_path=baseline_path)

    assert any("Fallback-derived diagnostic string matches" in warning for warning in result["warnings"])
    assert any("Gemma fallback" in warning for warning in result["record_results"][0]["warnings"])


def test_majority_fallback_derived_traces_emit_trace_level_warning(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [
            fallback_record("trace-001", gemma_raw_output="same"),
            fallback_record("trace-002", gemma_raw_output="same"),
            low_record("trace-003", gemma_raw_output="different"),
        ],
        [
            baseline_record("baseline-001", baseline_raw_output="same"),
            baseline_record("baseline-002", baseline_raw_output="same"),
            baseline_record("baseline-003", baseline_raw_output="baseline"),
        ],
    )

    result = build_diagnostic_output_comparison(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["fallback_after_rejection_count"] == 2
    assert any("Most low-tier records" in warning for warning in result["warnings"])


def test_unknown_records_are_counted_separately(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001", bridge_status="valid", fallback_count=1)],
        [baseline_record("baseline-001")],
    )

    result = build_diagnostic_output_comparison(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["unknown_contribution_count"] == 1
    assert result["unknown_diagnostic_count"] == 1
    assert result["category_results"]["unknown_contribution"]["record_count"] == 1


def test_report_does_not_include_long_raw_outputs(tmp_path: Path):
    long_text = "x" * 500
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001", gemma_raw_output=long_text)],
        [baseline_record("baseline-001", baseline_raw_output=long_text)],
    )
    result = build_diagnostic_output_comparison(low_tier_path=low_path, baseline_path=baseline_path)

    markdown = render_diagnostic_output_comparison_markdown(result)

    assert long_text not in markdown
    assert "low_tier_normalized_length" in markdown
    assert "baseline_normalized_length" in markdown


def test_report_includes_explicit_non_claims(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001")],
        [baseline_record("baseline-001")],
    )
    result = build_diagnostic_output_comparison(low_tier_path=low_path, baseline_path=baseline_path)

    markdown = render_diagnostic_output_comparison_markdown(result)

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


def test_diagnostic_comparison_reports_not_ready_when_precheck_fails(tmp_path: Path):
    broken = low_record("trace-001")
    broken["capture_raw_output"] = False
    broken.pop("raw_prompt")
    broken.pop("qwen_raw_output")
    broken.pop("gemma_raw_output")
    low_path = write_trace(tmp_path / "low.json", [broken], "live", capture_raw_output=False)
    baseline_path = write_trace(tmp_path / "baseline.json", [baseline_record("baseline-001")], "target-baseline")

    result = build_diagnostic_output_comparison(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["diagnostic_ready"] is False
    assert "raw_capture_missing" in result["blocking_reasons"]


def test_diagnostic_cli_writes_markdown_and_json_reports(tmp_path: Path, capsys):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001")],
        [baseline_record("baseline-001")],
    )
    output_dir = tmp_path / "reports"

    exit_code = diagnose_output_comparison.main(
        ["--low-tier", str(low_path), "--baseline", str(baseline_path), "--output-dir", str(output_dir)]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "diagnostic output comparison: ok" in output
    assert "diagnostic_ready: yes" in output
    assert list(output_dir.glob("*-diagnostic-output-comparison.md"))
    assert list(output_dir.glob("*-diagnostic-output-comparison.json"))
