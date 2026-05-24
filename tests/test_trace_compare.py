import json
from pathlib import Path

from htfsd.cli import compare_trace_report
from htfsd.metrics.trace_compare import compare_trace_files, render_trace_comparison_markdown


LOW_RECORD_1 = {
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
    "qwen_model_file": "models/qwen.gguf",
    "gemma_model_file": "models/gemma.gguf",
    "latency_seconds": 2.0,
}

LOW_RECORD_2 = {
    **LOW_RECORD_1,
    "prompt_id": "trace-002",
    "fallback_count": 1,
    "draft_valid_count": 0,
    "draft_rejected_count": 1,
    "latency_seconds": 4.0,
}

BASELINE_RECORD_1 = {
    "prompt_id": "baseline-001",
    "gemma_model_file": "models/gemma.gguf",
    "gemma_expected_device": "cuda",
    "gemma_device_status": "ok",
    "gemma_n_gpu_layers": -1,
    "latency_seconds": 1.0,
    "trace_kind": "target_baseline",
}

BASELINE_RECORD_3 = {
    **BASELINE_RECORD_1,
    "prompt_id": "baseline-003",
    "latency_seconds": 3.0,
}


def write_trace(path: Path, records: list[dict], mode: str) -> Path:
    path.write_text(json.dumps({"metadata": {"mode": mode}, "records": records}), encoding="utf-8")
    return path


def test_compare_trace_files_reports_counts_overlap_and_prompt_differences(tmp_path: Path):
    low_path = write_trace(tmp_path / "low.json", [LOW_RECORD_1, LOW_RECORD_2], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [BASELINE_RECORD_1, BASELINE_RECORD_3], "target-baseline")

    result = compare_trace_files(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["low_tier_records"] == 2
    assert result["baseline_records"] == 2
    assert result["prompt_id_overlap"] == 1
    assert result["missing_prompt_ids"] == ["002"]
    assert result["extra_prompt_ids"] == ["003"]
    assert result["low_tier_schema_status"] == "ok"
    assert result["baseline_schema_status"] == "ok"


def test_compare_trace_files_reports_accounting_latency_and_runtime_metadata(tmp_path: Path):
    low_path = write_trace(tmp_path / "low.json", [LOW_RECORD_1, LOW_RECORD_2], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [BASELINE_RECORD_1], "target-baseline")

    result = compare_trace_files(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["low_tier_total_fallback_count"] == 1
    assert result["low_tier_total_draft_valid_count"] == 1
    assert result["low_tier_total_draft_rejected_count"] == 1
    assert result["low_tier_latency_seconds_summary"] == {"count": 2, "min": 2.0, "max": 4.0, "mean": 3.0}
    assert result["baseline_latency_seconds_summary"] == {"count": 1, "min": 1.0, "max": 1.0, "mean": 1.0}
    assert result["low_tier_gemma_device_statuses"] == ["ok"]
    assert result["baseline_gemma_device_statuses"] == ["ok"]
    assert result["qwen_device_statuses"] == ["ok"]
    assert result["gemma_model_file_match"] is True


def test_compare_trace_files_reports_schema_failures_before_comparing(tmp_path: Path):
    bad_low = dict(LOW_RECORD_1)
    bad_low.pop("fallback_count")
    low_path = write_trace(tmp_path / "low.json", [bad_low], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [BASELINE_RECORD_1], "target-baseline")

    result = compare_trace_files(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["low_tier_schema_status"] == "failed"
    assert result["baseline_schema_status"] == "ok"


def test_comparison_markdown_includes_non_claims_without_forbidden_claim_phrases(tmp_path: Path):
    low_path = write_trace(tmp_path / "low.json", [LOW_RECORD_1], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [BASELINE_RECORD_1], "target-baseline")
    result = compare_trace_files(low_tier_path=low_path, baseline_path=baseline_path)

    markdown = render_trace_comparison_markdown(result)

    assert "This is not a benchmark." in markdown
    assert "No performance-improvement claim is made." in markdown
    assert "No output-equivalence claim is made." in markdown
    assert "No draft-acceptance metric is reported." in markdown
    lowered = markdown.lower()
    assert "speedup" not in lowered
    assert "lossless" not in lowered
    assert "acceptance rate" not in lowered


def test_compare_trace_report_cli_writes_markdown(tmp_path: Path, capsys):
    low_path = write_trace(tmp_path / "low.json", [LOW_RECORD_1], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [BASELINE_RECORD_1], "target-baseline")
    output_dir = tmp_path / "reports"

    exit_code = compare_trace_report.main(
        ["--low-tier", str(low_path), "--baseline", str(baseline_path), "--output-dir", str(output_dir)]
    )

    output = capsys.readouterr().out
    reports = list(output_dir.glob("*-trace-comparison-v0.md"))
    assert exit_code == 0
    assert "trace comparison report: ok" in output
    assert "low_tier_records: 1" in output
    assert "baseline_records: 1" in output
    assert reports
