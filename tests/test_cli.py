import json
from importlib import import_module

import pytest

import cli.generate as generate
from cli.generate import write_trace_jsonl
from benchmarks.fixtures import load_prompt_fixtures
from benchmarks.baseline_e4b import baseline_row
from benchmarks.low_tier import write_benchmark_row

CycleTrace = import_module("htfsd_types").CycleTrace
GenerateResult = import_module("htfsd_types").GenerateResult
GenerationMetrics = import_module("htfsd_types").GenerationMetrics


def write_config(path):
    path.write_text(
        """
models:
  qwen_drafter: {model_id_or_path: "qwen-local", tensor_parallel_size: 1, dtype: "auto", gpu_memory_utilization: 0.35}
  gemma_e2b: {model_id_or_path: "e2b-local", tensor_parallel_size: 1, dtype: "auto", gpu_memory_utilization: 0.55}
  gemma_e4b_baseline: {model_id_or_path: "e4b-local", tensor_parallel_size: 1, dtype: "auto", gpu_memory_utilization: 0.90}
runtime: {backend: "vllm", execution_mode: "concurrent", max_context_tokens: 4096, seed: 1234}
generation: {max_new_tokens: 128, stop_on_eos: true}
dflash: {parser: "strict_json", required_fields: ["draft_text"], default_max_tokens: 8, hard_max_tokens: 16, experimental_repair: false}
low_tier: {acceptance_policy: "greedy_exact_match", fallback_policy: "single_token_greedy", fallback_tokens_per_cycle: 1}
decoding:
  default: "greedy"
  sampling: {enabled: true, experimental: true, temperature: 0.7, top_p: 0.9}
benchmark:
  fixture_path: "benchmarks/fixtures/prompts.jsonl"
  dataset: {enabled: false, name: null, split: null}
""",
        encoding="utf-8",
    )


def fake_generate_result(text):
    return GenerateResult(
        text=text,
        token_ids=[1],
        metrics=GenerationMetrics(
            generated_tokens=1,
            cycles=1,
            drafted_candidate_tokens=1,
            accepted_tokens=1,
            fallback_tokens=0,
            malformed_dflash_count=0,
            dflash_parse_fail_count=0,
            dflash_schema_invalid_count=0,
            dflash_empty_draft_count=0,
            retokenized_empty_count=0,
            low_acceptance_rate=1.0,
            fallback_rate=0.0,
            total_ms=1.0,
            tokens_per_second=1000.0,
            latency_per_token_ms=1.0,
            execution_mode="concurrent",
            decoding_mode="greedy",
        ),
    )


def latest_log(log_dir):
    return sorted(log_dir.glob("*.json"))[-1]


def test_generate_main_records_run_log_without_model_output(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "generate.yaml"
    write_config(config_path)
    monkeypatch.chdir(tmp_path)

    class FakeEngine:
        def generate(self, *_args, **_kwargs):
            return fake_generate_result("generated model output")

    monkeypatch.setattr(generate, "_build_engine", lambda _config: FakeEngine())

    assert generate.main(["--config", str(config_path), "--prompt", "private prompt"]) == 0

    assert "generated model output" in capsys.readouterr().out
    log_path = latest_log(tmp_path / "logs" / "runs")
    log_text = log_path.read_text(encoding="utf-8")
    row = json.loads(log_text)
    assert row["status"] == "ok"
    assert row["paths"]["config_path"] == "generate.yaml"
    assert row["argv"]["prompt_chars"] == len("private prompt")
    assert "private prompt" not in log_text
    assert "generated model output" not in log_text


def test_generate_config_load_failure_still_records_run_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError):
        generate.main(["--config", "missing.yaml", "--prompt=private prompt"])

    row = json.loads(latest_log(tmp_path / "logs" / "runs").read_text(encoding="utf-8"))
    assert row["status"] == "error"
    assert row["paths"]["config_path"] == "missing.yaml"
    assert row["error"]["exception_type"] == "FileNotFoundError"


def test_write_trace_jsonl(tmp_path):
    output = tmp_path / "trace.jsonl"
    trace = [
        CycleTrace(
            cycle_index=0,
            context_tokens=2,
            dflash_parse_ok=True,
            malformed_dflash=False,
            draft_text_chars=1,
            draft_candidate_tokens=1,
            accepted_tokens=1,
            reject_position=None,
            candidate_exhausted=True,
            fallback_used=False,
            qwen_draft_ms=1.0,
            dflash_parse_ms=0.1,
            gemma_retokenize_ms=0.1,
            e2b_verify_ms=1.0,
            cycle_ms=2.2,
        )
    ]

    write_trace_jsonl(output, trace)

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["cycle_index"] == 0
    assert rows[0]["candidate_exhausted"] is True


def test_load_prompt_fixtures(tmp_path):
    fixture = tmp_path / "prompts.jsonl"
    fixture.write_text('{"id":"a","prompt":"Hello","max_new_tokens":3}\n', encoding="utf-8")

    rows = load_prompt_fixtures(fixture)

    assert rows == [{"id": "a", "prompt": "Hello", "max_new_tokens": 3}]


def test_write_benchmark_row_jsonl(tmp_path):
    output = tmp_path / "low.jsonl"
    write_benchmark_row(
        output,
        {
            "prompt_id": "a",
            "status": "ok",
            "error": None,
            "metrics": {"generated_tokens": 1},
        },
    )

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["prompt_id"] == "a"
    assert rows[0]["status"] == "ok"


def test_baseline_row_shape():
    row = baseline_row(
        prompt_id="p1",
        prompt_tokens=5,
        generated_tokens=7,
        total_ms=100.0,
        output_text="hello",
    )

    assert row["prompt_id"] == "p1"
    assert row["tokens_per_second"] == 70.0
    assert row["latency_per_token_ms"] == 100.0 / 7
    assert row["output_text"] == "hello"
