import json
from pathlib import Path

from htfsd.cli import preview_output_comparison
from htfsd.metrics.output_preview import (
    build_output_normalization_preview,
    render_output_normalization_preview_markdown,
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
    "prompt_summary": "short prompt",
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
    "gemma_raw_output": "  Alpha\r\nBeta\t\t<keep>  ",
}

BASELINE_RECORD = {
    "prompt_id": "baseline-001",
    "prompt_summary": "short prompt",
    "gemma_model_file": "models/gemma.gguf",
    "gemma_expected_device": "cuda",
    "gemma_device_status": "ok",
    "gemma_n_gpu_layers": -1,
    "latency_seconds": 1.0,
    "trace_kind": "target_baseline",
    "generation_settings": SETTINGS,
    "capture_raw_output": True,
    "raw_prompt": "Prompt.",
    "baseline_raw_output": "Alpha\nBeta\t\t<keep>",
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


def test_preview_builds_records_when_precheck_is_ready(tmp_path: Path):
    low_path = write_trace(tmp_path / "low.json", [LOW_RECORD], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [BASELINE_RECORD], "target-baseline")

    result = build_output_normalization_preview(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["preview_ready"] is True
    assert result["precheck"]["output_comparison_ready"] is True
    assert result["preview_records"][0]["prompt_id"] == "trace-001"
    assert result["preview_records"][0]["low_tier_output_present"] is True
    assert result["preview_records"][0]["baseline_output_present"] is True


def test_preview_blocks_when_precheck_is_not_ready(tmp_path: Path):
    low_record = {**LOW_RECORD, "capture_raw_output": False}
    low_record.pop("raw_prompt")
    low_record.pop("qwen_raw_output")
    low_record.pop("gemma_raw_output")
    low_path = write_trace(tmp_path / "low.json", [low_record], "live", capture_raw_output=False)
    baseline_path = write_trace(tmp_path / "baseline.json", [BASELINE_RECORD], "target-baseline")

    result = build_output_normalization_preview(low_tier_path=low_path, baseline_path=baseline_path)

    assert result["preview_ready"] is False
    assert "raw_capture_missing" in result["blocking_reasons"]
    assert result["preview_records"] == []


def test_preview_uses_conservative_normalization(tmp_path: Path):
    low_path = write_trace(tmp_path / "low.json", [LOW_RECORD], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [BASELINE_RECORD], "target-baseline")

    record = build_output_normalization_preview(low_tier_path=low_path, baseline_path=baseline_path)["preview_records"][0]

    assert record["low_tier_preview"] == "Alpha\nBeta\t\t<keep>"
    assert record["baseline_preview"] == "Alpha\nBeta\t\t<keep>"
    assert "\t\t" in record["low_tier_preview"]
    assert "<keep>" in record["low_tier_preview"]


def test_preview_records_lengths_empty_flags_and_match_preview(tmp_path: Path):
    low_record = {**LOW_RECORD, "gemma_raw_output": "  \r\n  "}
    baseline_record = {**BASELINE_RECORD, "baseline_raw_output": "visible"}
    low_path = write_trace(tmp_path / "low.json", [low_record], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [baseline_record], "target-baseline")

    record = build_output_normalization_preview(low_tier_path=low_path, baseline_path=baseline_path)["preview_records"][0]

    assert record["low_tier_normalized_length"] == 0
    assert record["baseline_normalized_length"] == len("visible")
    assert record["low_tier_empty_after_normalization"] is True
    assert record["baseline_empty_after_normalization"] is False
    assert record["normalized_outputs_exact_string_match"] is False


def test_preview_truncates_preview_text(tmp_path: Path):
    low_record = {**LOW_RECORD, "gemma_raw_output": "x" * 240}
    baseline_record = {**BASELINE_RECORD, "baseline_raw_output": "y" * 240}
    low_path = write_trace(tmp_path / "low.json", [low_record], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [baseline_record], "target-baseline")

    record = build_output_normalization_preview(low_tier_path=low_path, baseline_path=baseline_path, preview_max_chars=20)[
        "preview_records"
    ][0]

    assert record["low_tier_preview"] == ("x" * 20) + "..."
    assert record["baseline_preview"] == ("y" * 20) + "..."


def test_preview_markdown_includes_explicit_non_claims(tmp_path: Path):
    low_path = write_trace(tmp_path / "low.json", [LOW_RECORD], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [BASELINE_RECORD], "target-baseline")
    result = build_output_normalization_preview(low_tier_path=low_path, baseline_path=baseline_path)

    markdown = render_output_normalization_preview_markdown(result)

    assert "This is not an output equality report." in markdown
    assert "Exact string match preview is not target-equivalence validation." in markdown
    assert "No output parity claim is made." in markdown
    assert "No correctness claim is made." in markdown
    assert "No lossless-generation claim is made." in markdown
    assert "No benchmark claim is made." in markdown
    lowered = markdown.lower()
    assert ("outputs are " + "equal") not in lowered
    assert "speed" + "up" not in lowered


def test_preview_cli_writes_markdown_and_json_reports(tmp_path: Path, capsys):
    low_path = write_trace(tmp_path / "low.json", [LOW_RECORD], "live")
    baseline_path = write_trace(tmp_path / "baseline.json", [BASELINE_RECORD], "target-baseline")
    output_dir = tmp_path / "reports"

    exit_code = preview_output_comparison.main(
        ["--low-tier", str(low_path), "--baseline", str(baseline_path), "--output-dir", str(output_dir)]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "output normalization preview: ok" in output
    assert "preview_ready: yes" in output
    assert list(output_dir.glob("*-output-normalization-preview.md"))
    assert list(output_dir.glob("*-output-normalization-preview.json"))


def test_preview_cli_returns_nonzero_when_precheck_blocks(tmp_path: Path, capsys):
    low_record = {**LOW_RECORD, "capture_raw_output": False}
    low_record.pop("raw_prompt")
    low_record.pop("qwen_raw_output")
    low_record.pop("gemma_raw_output")
    low_path = write_trace(tmp_path / "low.json", [low_record], "live", capture_raw_output=False)
    baseline_path = write_trace(tmp_path / "baseline.json", [BASELINE_RECORD], "target-baseline")

    exit_code = preview_output_comparison.main(["--low-tier", str(low_path), "--baseline", str(baseline_path)])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "preview_ready: no" in output
    assert "raw_capture_missing" in output
