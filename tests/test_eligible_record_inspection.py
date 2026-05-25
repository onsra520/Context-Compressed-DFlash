import json
from pathlib import Path

from htfsd.cli import inspect_eligible_records
from htfsd.metrics.eligible_record_inspection import (
    build_eligible_record_inspection,
    render_eligible_record_inspection_markdown,
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
    gemma_raw_output: str = "draft output",
    qwen_raw_output: str = "draft",
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
        "qwen_raw_output": qwen_raw_output,
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


def fallback_record(prompt_id: str, *, prompt_mode: str = "raw", gemma_raw_output: str = "fallback") -> dict:
    return low_record(
        prompt_id,
        bridge_status="rejected",
        rejection_reason="contains_unclosed_think",
        fallback_count=1,
        draft_valid_count=0,
        draft_rejected_count=1,
        gemma_raw_output=gemma_raw_output,
        prompt_mode=prompt_mode,
        extra={"gemma_fallback_used": True},
    )


def test_inspection_succeeds_when_selector_is_ready(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001")],
        [baseline_record("baseline-001")],
    )

    result = build_eligible_record_inspection(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["inspection_ready"] is True
    assert result["selector_status"]["selection_ready"] is True


def test_eligible_valid_draft_records_are_listed(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001", gemma_raw_output="draft output")],
        [baseline_record("baseline-001", baseline_raw_output="baseline output")],
    )

    result = build_eligible_record_inspection(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["eligible_record_count"] == 1
    record = result["eligible_records"][0]
    assert record["prompt_id"] == "trace-001"
    assert record["selection_category"] == "eligible_valid_draft_record"
    assert record["contribution_category"] == "valid_draft_continuation"
    assert record["bridge_status"] == "valid"
    assert record["fallback_count"] == 0
    assert "low_tier_preview" in record
    assert "baseline_preview" in record


def test_fallback_unknown_and_empty_baseline_records_are_excluded(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [
            fallback_record("trace-001"),
            low_record("trace-002", bridge_status="valid", fallback_count=1),
            low_record("trace-003", gemma_raw_output="draft output"),
        ],
        [
            baseline_record("baseline-001", baseline_raw_output="fallback"),
            baseline_record("baseline-002", baseline_raw_output="baseline"),
            baseline_record("baseline-003", baseline_raw_output=""),
        ],
    )

    result = build_eligible_record_inspection(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["eligible_record_count"] == 0
    assert result["excluded_record_summary"]["excluded_fallback_derived_record_count"] == 1
    assert result["excluded_record_summary"]["excluded_unknown_contribution_record_count"] == 1
    assert result["excluded_record_summary"]["excluded_empty_baseline_record_count"] == 1


def test_empty_eligible_set_is_handled_cleanly(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [fallback_record("trace-001", prompt_mode="chat")],
        [baseline_record("baseline-001", baseline_raw_output="fallback", prompt_mode="chat")],
    )

    result = build_eligible_record_inspection(low_tier_path=low_path, baseline_path=baseline_path)
    markdown = render_eligible_record_inspection_markdown(result)

    assert result["eligible_record_count"] == 0
    assert "No eligible records were selected." in markdown


def test_report_includes_excluded_record_summary(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001", gemma_raw_output="")],
        [baseline_record("baseline-001", baseline_raw_output="")],
    )

    result = build_eligible_record_inspection(low_tier_path=low_path, baseline_path=baseline_path)
    markdown = render_eligible_record_inspection_markdown(result)

    assert "## Excluded Record Summary" in markdown
    assert "excluded_empty_baseline_record_count" in markdown


def test_report_uses_compact_metadata_and_omits_long_raw_outputs(tmp_path: Path):
    long_text = "x" * 600
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001", gemma_raw_output=long_text, qwen_raw_output=long_text)],
        [baseline_record("baseline-001", baseline_raw_output=long_text)],
    )

    result = build_eligible_record_inspection(low_tier_path=low_path, baseline_path=baseline_path)
    markdown = render_eligible_record_inspection_markdown(result)

    assert long_text not in markdown
    assert "low_tier_normalized_length" in markdown
    assert "baseline_normalized_length" in markdown


def test_report_includes_explicit_non_claims(tmp_path: Path):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001")],
        [baseline_record("baseline-001")],
    )
    result = build_eligible_record_inspection(low_tier_path=low_path, baseline_path=baseline_path)

    markdown = render_eligible_record_inspection_markdown(result)

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


def test_cli_writes_markdown_and_json_reports(tmp_path: Path, capsys):
    low_path, baseline_path = matching_paths(
        tmp_path,
        [low_record("trace-001", gemma_raw_output="draft output")],
        [baseline_record("baseline-001", baseline_raw_output="baseline output")],
    )
    output_dir = tmp_path / "reports"

    exit_code = inspect_eligible_records.main(
        ["--low-tier", str(low_path), "--baseline", str(baseline_path), "--output-dir", str(output_dir)]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "eligible record inspection: ok" in output
    assert "inspection_ready: yes" in output
    assert "eligible_record_count: 1" in output
    assert list(output_dir.glob("*-eligible-record-inspection.md"))
    assert list(output_dir.glob("*-eligible-record-inspection.json"))
