import pytest
import os
import json
from pathlib import Path
from ccdf.demo.contracts import RunRequest
from ccdf.demo.runner import DemoRunner
from ccdf.demo.condition_registry import get_condition
from ccdf.demo.writers import flatten_result, write_json, write_jsonl_append, write_flat_csv_append
from ccdf.demo.adapters.gsm8k import gsm8k_row_to_request


def test_condition_registry_rejects_unknown():
    with pytest.raises(ValueError):
        get_condition("unknown_cond")


def test_raw_prompt_unchanged():
    from ccdf.demo.prompt_profiles import apply_prompt_profile
    assert apply_prompt_profile("hello", "raw") == "hello"


def test_gsm8k_profile_explicit():
    from ccdf.demo.prompt_profiles import apply_prompt_profile
    result = apply_prompt_profile("2+2", "gsm8k_concise_final_answer_v1")
    assert "Final answer: <number>" in result
    assert result.startswith("2+2\n\n")


def test_identical_logical_prompt():
    req = RunRequest(source_type="interactive", condition="baseline_ar", prompt="test", max_new_tokens=10)
    runner = DemoRunner({"dry_run": True})
    res = runner.run(req)
    assert res["request"]["prompt"] == "test"


def test_comparison_condition_order():
    runner = DemoRunner({"dry_run": True})
    results = runner.compare_prompt("test", ["baseline_ar", "dflash_r1", "cc_dflash_r2"])
    assert len(results) == 3
    assert results[0]["request"]["condition"] == "baseline_ar"
    assert results[1]["request"]["condition"] == "dflash_r1"
    assert results[2]["request"]["condition"] == "cc_dflash_r2"


def test_baseline_dflash_compression_null():
    runner = DemoRunner({"dry_run": True})
    for cond in ["baseline_ar", "dflash_r1"]:
        res = runner.run(RunRequest(source_type="interactive", condition=cond, prompt="test"))
        assert res["tokens"]["compressed_input_tokens"] is None
        assert res["tokens"]["compression_ratio"] is None
        assert res["timing_ms"]["compression"] == 0.0


def test_cc_dflash_compression_populated():
    runner = DemoRunner({"dry_run": True})
    res = runner.run(RunRequest(source_type="interactive", condition="cc_dflash_r2", prompt="test"))
    assert res["tokens"]["compressed_input_tokens"] is not None
    assert res["tokens"]["compression_ratio"] == 0.5
    assert res["timing_ms"]["compression"] >= 0.0


def test_dataset_adapter_mapping():
    row = {"id": "1", "context": "ctx", "question": "q", "expected_answer": "ans"}
    req = gsm8k_row_to_request(row, "baseline_ar")
    assert req.dataset == "gsm8k"
    assert req.prompt_profile == "gsm8k_concise_final_answer_v1"
    assert req.reference_answer == "ans"
    assert "Question: q" in req.prompt
    assert req.metadata["context"] == "ctx"


def test_interactive_without_reference():
    req = RunRequest(source_type="interactive", condition="baseline_ar", prompt="test")
    assert req.reference_answer is None


def test_comparison_one_failed_condition():
    runner = DemoRunner({"dry_run": True})
    results = runner.compare_prompt("test", ["baseline_ar", "unknown_cond", "dflash_r1"])
    assert len(results) == 3
    assert results[0]["status"]["ok"] is True
    assert results[1]["status"]["ok"] is False
    assert results[1]["status"]["error_type"] == "ValueError"
    assert results[2]["status"]["ok"] is True


def test_csv_flatten():
    runner = DemoRunner({"dry_run": True})
    res = runner.run(RunRequest(source_type="interactive", condition="baseline_ar", prompt="test"))
    flat = flatten_result(res)
    assert flat["condition_display_name"] == "Baseline-AR"


def test_json_serialization(tmp_path):
    runner = DemoRunner({"dry_run": True})
    res = runner.run(RunRequest(source_type="interactive", condition="baseline_ar", prompt="test"))
    out_file = tmp_path / "out.json"
    write_json(res, out_file)
    assert out_file.exists()


def test_jsonl_append(tmp_path):
    runner = DemoRunner({"dry_run": True})
    res = runner.run(RunRequest(source_type="interactive", condition="baseline_ar", prompt="test"))
    out_file = tmp_path / "out.jsonl"
    write_jsonl_append(res, out_file)
    write_jsonl_append(res, out_file)
    lines = out_file.read_text().strip().split("\n")
    assert len(lines) == 2


def test_csv_deterministic_header(tmp_path):
    runner = DemoRunner({"dry_run": True})
    res = runner.run(RunRequest(source_type="interactive", condition="baseline_ar", prompt="test"))
    out_file = tmp_path / "out.csv"
    write_flat_csv_append(res, out_file)
    lines = out_file.read_text().strip().split("\n")
    assert len(lines) == 2
    assert lines[0].startswith("schema_version,run_id,source_type")
