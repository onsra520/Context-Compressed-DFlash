import json
from pathlib import Path

from htfsd.cli import prepare_output_comparison
from htfsd.metrics.output_compare import (
    normalize_output_preview,
    prepare_output_comparison_precheck,
    render_output_comparison_precheck_markdown,
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

LOW_RECORD = {
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
    "generation_settings": SETTINGS,
    "capture_raw_output": True,
    "raw_prompt": "Prompt.",
    "qwen_raw_output": "Draft.",
    "gemma_raw_output": " Low output.\r\n",
}

BASELINE_RECORD = {
    "prompt_id": "baseline-001",
    "gemma_model_file": "models/gemma.gguf",
    "gemma_expected_device": "cuda",
    "gemma_device_status": "ok",
    "gemma_n_gpu_layers": -1,
    "latency_seconds": 1.0,
    "trace_kind": "target_baseline",
    "generation_settings": SETTINGS,
    "capture_raw_output": True,
    "raw_prompt": "Prompt.",
    "baseline_raw_output": " Baseline output.\r\n",
}


def write_trace(path: Path, records: list[dict], mode: str, capture_raw_output: bool = True) -> Path:
    path.write_text(
        json.dumps(
            {
                "metadata": {
                    "mode": mode,
                    "capture_raw_output": capture_raw_output,
                    "generation_settings": {**SETTINGS, "capture_raw_output": capture_raw_output},
                },
                "records": records,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_precheck_passes_for_raw_capture_traces_with_matching_settings(tmp_path: Path):
    low_path = write_trace(tmp_path / "low.json", [LOW_RECORD], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [BASELINE_RECORD], "target-baseline")

    result = prepare_output_comparison_precheck(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["output_comparison_ready"] is True
    assert result["blocking_reasons"] == []
    assert result["schema_status"] == {"low_tier": "ok", "baseline": "ok"}
    assert result["raw_capture_status"] == {"low_tier": True, "baseline": True}
    assert result["prompt_coverage_status"] == "ok"
    assert result["generation_settings_match"] is True
    assert result["runtime_metadata_match"] is True
    assert result["raw_field_presence_status"] == "ok"


def test_precheck_fails_when_raw_capture_is_missing(tmp_path: Path):
    low_record = {**LOW_RECORD, "capture_raw_output": False}
    low_record.pop("raw_prompt")
    low_record.pop("qwen_raw_output")
    low_record.pop("gemma_raw_output")
    low_path = write_trace(tmp_path / "low.json", [low_record], "live", capture_raw_output=False)
    baseline_path = write_trace(tmp_path / "baseline.json", [BASELINE_RECORD], "target-baseline")

    result = prepare_output_comparison_precheck(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["output_comparison_ready"] is False
    assert "raw_capture_missing" in result["blocking_reasons"]
    assert "raw_fields_missing" in result["blocking_reasons"]


def test_precheck_fails_when_prompt_coverage_differs(tmp_path: Path):
    baseline_record = {**BASELINE_RECORD, "prompt_id": "baseline-002"}
    low_path = write_trace(tmp_path / "low.json", [LOW_RECORD], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [baseline_record], "target-baseline")

    result = prepare_output_comparison_precheck(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["output_comparison_ready"] is False
    assert result["prompt_coverage_status"] == "failed"
    assert "prompt_coverage_mismatch" in result["blocking_reasons"]


def test_precheck_fails_when_generation_settings_differ(tmp_path: Path):
    baseline_record = {
        **BASELINE_RECORD,
        "generation_settings": {**SETTINGS, "max_tokens": 16},
    }
    low_path = write_trace(tmp_path / "low.json", [LOW_RECORD], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [baseline_record], "target-baseline")

    result = prepare_output_comparison_precheck(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["output_comparison_ready"] is False
    assert result["generation_settings_match"] is False
    assert "generation_settings_mismatch" in result["blocking_reasons"]


def test_precheck_fails_when_gemma_model_file_differs(tmp_path: Path):
    baseline_record = {**BASELINE_RECORD, "gemma_model_file": "models/other-gemma.gguf"}
    low_path = write_trace(tmp_path / "low.json", [LOW_RECORD], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [baseline_record], "target-baseline")

    result = prepare_output_comparison_precheck(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["output_comparison_ready"] is False
    assert result["runtime_metadata_match"] is False
    assert "runtime_metadata_mismatch" in result["blocking_reasons"]


def test_normalization_preview_preserves_semantic_content():
    text = "  Alpha\r\nBeta\t\tGamma  "

    normalized = normalize_output_preview(text)
    collapsed = normalize_output_preview(text, collapse_repeated_whitespace=True)

    assert normalized == "Alpha\nBeta\t\tGamma"
    assert collapsed == "Alpha Beta Gamma"


def test_precheck_markdown_includes_explicit_non_claims(tmp_path: Path):
    low_path = write_trace(tmp_path / "low.json", [LOW_RECORD], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [BASELINE_RECORD], "target-baseline")
    result = prepare_output_comparison_precheck(low_tier_path=low_path, baseline_path=baseline_path)

    markdown = render_output_comparison_precheck_markdown(result)

    assert "This is not an output equality report." in markdown
    assert "No output parity claim is made." in markdown
    assert "No exact-generation claim is made." in markdown
    assert "No benchmark claim is made." in markdown
    lowered = markdown.lower()
    assert ("outputs are " + "equal") not in lowered
    assert "lossless" not in lowered
    assert "speed" + "up" not in lowered


def test_prepare_output_comparison_cli_writes_reports(tmp_path: Path, capsys):
    low_path = write_trace(tmp_path / "low.json", [LOW_RECORD], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [BASELINE_RECORD], "target-baseline")
    output_dir = tmp_path / "reports"

    exit_code = prepare_output_comparison.main(
        ["--low-tier", str(low_path), "--baseline", str(baseline_path), "--output-dir", str(output_dir)]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "output comparison precheck: ok" in output
    assert "output_comparison_ready: yes" in output
    assert list(output_dir.glob("*-output-comparison-precheck.md"))
    assert list(output_dir.glob("*-output-comparison-precheck.json"))
