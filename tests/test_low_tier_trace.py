from pathlib import Path

from htfsd.config import load_config
from htfsd.cli import run_low_tier_trace
from htfsd.metrics.generation_settings import build_generation_settings
from htfsd.metrics.prompt_sets import default_trace_prompt_texts
from htfsd.metrics.run_trace import (
    DEFAULT_CONTROLLED_FALLBACK_CASES,
    DEFAULT_TRACE_PROMPTS,
    run_controlled_fallback_trace_cases,
    run_controlled_low_tier_trace,
)
from htfsd.metrics.trace_schema import validate_trace_record


CONFIG_TEXT = """
models:
  qwen_drafter:
    model_dir: models/qwen3-0.6b
    model_file: null
  gemma_e2b:
    model_dir: models/gemma-4-e2b-it
    model_file: null
  gemma_e4b:
    model_dir: models/gemma-4-e4b-it
    model_file: null
runtime:
  backend: llama_cpp
  n_ctx: 2048
  seed: 42
generation:
  max_tokens: 64
  temperature: 0.0
"""


class SequenceBackend:
    def __init__(self, outputs: list[str], tokens: int = 4):
        self.outputs = outputs
        self.tokens = tokens
        self.prompts = []

    def generate_text(self, prompt: str, *, max_tokens: int, temperature: float, stop=None):
        self.prompts.append(prompt)
        text = self.outputs[min(len(self.prompts) - 1, len(self.outputs) - 1)]
        return type("Result", (), {"text": text, "completion_tokens": self.tokens})()


def write_project(repo_root: Path) -> None:
    (repo_root / "pyproject.toml").write_text("[project]\nname='tmp'\n", encoding="utf-8")
    config_path = repo_root / "configs/local.example.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(CONFIG_TEXT, encoding="utf-8")


def touch_model(repo_root: Path, model_dir: str, filename: str) -> Path:
    path = repo_root / model_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("fake gguf", encoding="utf-8")
    return path


def test_controlled_trace_runs_multiple_prompts_and_records_policy(tmp_path: Path):
    write_project(tmp_path)
    qwen_file = touch_model(tmp_path, "models/qwen3-0.6b", "qwen.gguf")
    gemma_file = touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    config = load_config(repo_root=tmp_path)
    diagnostics = {
        "models": {
            "qwen_drafter": {"device_status": "ok"},
            "gemma_e2b": {"device_status": "ok"},
        }
    }
    qwen = SequenceBackend([" valid draft", "<think>unfinished"], tokens=3)
    gemma = SequenceBackend([" final answer", " fallback answer"], tokens=5)

    records = run_controlled_low_tier_trace(
        prompts=["Prompt one.", "Prompt two."],
        config=config,
        diagnostics=diagnostics,
        qwen_backend=qwen,
        gemma_backend=gemma,
        generation_settings=build_generation_settings(config),
    )

    assert len(records) == 2
    assert records[0]["prompt_id"] == "trace-001"
    assert records[0]["qwen_model_file"] == str(qwen_file)
    assert records[0]["gemma_model_file"] == str(gemma_file)
    assert validate_trace_record(records[0], mode="live").ok is True
    assert records[0]["qwen_expected_device"] == "cpu"
    assert records[0]["qwen_n_gpu_layers"] == 0
    assert records[0]["qwen_device_status"] == "ok"
    assert records[0]["gemma_expected_device"] == "cuda"
    assert records[0]["gemma_n_gpu_layers"] == -1
    assert records[0]["gemma_device_status"] == "ok"
    assert records[0]["bridge_status"] == "valid"
    assert records[0]["generation_settings"]["max_tokens"] == 64
    assert records[0]["generation_settings"]["temperature"] == 0.0
    assert records[0]["generation_settings"]["prompt_mode"] == "raw"
    assert records[0]["capture_raw_output"] is False
    assert records[0]["fallback_count"] == 0
    assert records[1]["bridge_status"] == "rejected"
    assert records[1]["fallback_count"] == 1
    assert records[1]["rejection_reason"] == "contains_unclosed_think"


def test_controlled_trace_uses_default_prompt_set():
    assert len(DEFAULT_TRACE_PROMPTS) == 3
    assert DEFAULT_TRACE_PROMPTS[0].startswith("Explain speculative decoding")
    assert DEFAULT_TRACE_PROMPTS == default_trace_prompt_texts()


def test_controlled_trace_does_not_store_long_raw_output_by_default(tmp_path: Path):
    write_project(tmp_path)
    touch_model(tmp_path, "models/qwen3-0.6b", "qwen.gguf")
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    config = load_config(repo_root=tmp_path)
    diagnostics = {
        "models": {
            "qwen_drafter": {"device_status": "ok"},
            "gemma_e2b": {"device_status": "ok"},
        }
    }
    long_text = "x" * 500

    records = run_controlled_low_tier_trace(
        prompts=["Prompt."],
        config=config,
        diagnostics=diagnostics,
        qwen_backend=SequenceBackend([long_text]),
        gemma_backend=SequenceBackend([long_text]),
        generation_settings=build_generation_settings(config),
    )

    record = records[0]
    assert "raw_draft_text" not in record
    assert "gemma_output_text" not in record
    assert len(record["qwen_output_summary"]) <= 120
    assert len(record["gemma_output_summary"]) <= 120
    assert long_text not in str(record)
    assert record["capture_raw_output"] is False


def test_controlled_trace_stores_raw_output_only_when_enabled(tmp_path: Path):
    write_project(tmp_path)
    touch_model(tmp_path, "models/qwen3-0.6b", "qwen.gguf")
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    config = load_config(repo_root=tmp_path)
    diagnostics = {
        "models": {
            "qwen_drafter": {"device_status": "ok"},
            "gemma_e2b": {"device_status": "ok"},
        }
    }

    records = run_controlled_low_tier_trace(
        prompts=["Prompt."],
        config=config,
        diagnostics=diagnostics,
        qwen_backend=SequenceBackend([" raw draft"]),
        gemma_backend=SequenceBackend([" raw output"]),
        generation_settings=build_generation_settings(config, capture_raw_output=True),
    )

    record = records[0]
    assert record["capture_raw_output"] is True
    assert record["raw_prompt"] == "Prompt."
    assert record["qwen_raw_output"] == " raw draft"
    assert record["gemma_raw_output"] == " raw output"


def test_controlled_trace_does_not_introduce_forbidden_claims(tmp_path: Path):
    write_project(tmp_path)
    touch_model(tmp_path, "models/qwen3-0.6b", "qwen.gguf")
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    config = load_config(repo_root=tmp_path)
    diagnostics = {
        "models": {
            "qwen_drafter": {"device_status": "ok"},
            "gemma_e2b": {"device_status": "ok"},
        }
    }

    records = run_controlled_low_tier_trace(
        prompts=["Prompt."],
        config=config,
        diagnostics=diagnostics,
        qwen_backend=SequenceBackend([" draft"]),
        gemma_backend=SequenceBackend([" output"]),
        generation_settings=build_generation_settings(config),
    )

    serialized = str(records).lower()
    assert "acceptance rate" not in serialized
    assert "lossless" not in serialized
    assert "speedup" not in serialized


def test_low_tier_trace_cli_writes_compact_report(tmp_path: Path, monkeypatch, capsys):
    write_project(tmp_path)
    touch_model(tmp_path, "models/qwen3-0.6b", "qwen.gguf")
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_low_tier_trace, "LlamaCppBackend", lambda **kwargs: SequenceBackend([" draft"]))
    monkeypatch.setattr(
        run_low_tier_trace,
        "collect_environment_diagnostics",
        lambda config: {
            "backend": {"llama_cpp_supports_gpu_offload": True},
            "models": {
                "qwen_drafter": {"device_status": "ok"},
                "gemma_e2b": {"device_status": "ok"},
            },
        },
    )

    exit_code = run_low_tier_trace.main(["--prompt", "Short prompt."])

    output = capsys.readouterr().out
    reports = list((tmp_path / "logs/reports").glob("*-low-tier-trace.json"))
    assert exit_code == 0
    assert "Low-tier trace: ok" in output
    assert "trace_records: 1" in output
    assert reports


def test_controlled_fallback_trace_records_expected_cases(tmp_path: Path):
    write_project(tmp_path)
    touch_model(tmp_path, "models/qwen3-0.6b", "qwen.gguf")
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    config = load_config(repo_root=tmp_path)
    diagnostics = {
        "models": {
            "qwen_drafter": {"device_status": "ok"},
            "gemma_e2b": {"device_status": "ok"},
        }
    }

    records = run_controlled_fallback_trace_cases(
        cases=DEFAULT_CONTROLLED_FALLBACK_CASES,
        config=config,
        diagnostics=diagnostics,
        gemma_backend=SequenceBackend([" fallback output"]),
        generation_settings=build_generation_settings(config),
    )

    by_case = {record["case_id"]: record for record in records}
    assert by_case["valid_plain_draft"]["bridge_status"] == "valid"
    assert by_case["valid_plain_draft"]["fallback_count"] == 0
    assert by_case["valid_plain_draft"]["gemma_fallback_used"] is False
    assert by_case["empty_draft"]["bridge_status"] == "rejected"
    assert by_case["empty_draft"]["rejection_reason"] == "empty_after_normalization"
    assert by_case["empty_draft"]["fallback_count"] == 1
    assert by_case["empty_draft"]["gemma_fallback_used"] is True
    assert by_case["unclosed_think"]["rejection_reason"] == "contains_unclosed_think"
    assert by_case["unclosed_think"]["fallback_count"] == 1
    assert by_case["complete_think_then_empty"]["rejection_reason"] == "empty_after_normalization"
    assert by_case["complete_think_then_empty"]["fallback_count"] == 1


def test_controlled_fallback_trace_records_device_policy(tmp_path: Path):
    write_project(tmp_path)
    touch_model(tmp_path, "models/qwen3-0.6b", "qwen.gguf")
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    config = load_config(repo_root=tmp_path)
    diagnostics = {
        "models": {
            "qwen_drafter": {"device_status": "ok"},
            "gemma_e2b": {"device_status": "ok"},
        }
    }

    records = run_controlled_fallback_trace_cases(
        cases=DEFAULT_CONTROLLED_FALLBACK_CASES[:1],
        config=config,
        diagnostics=diagnostics,
        gemma_backend=SequenceBackend([" output"]),
        generation_settings=build_generation_settings(config),
    )

    record = records[0]
    assert validate_trace_record(record, mode="controlled-fallback").ok is True
    assert record["qwen_model_file"].endswith("qwen.gguf")
    assert record["gemma_model_file"].endswith("gemma.gguf")
    assert record["qwen_expected_device"] == "cpu"
    assert record["qwen_n_gpu_layers"] == 0
    assert record["qwen_device_status"] == "ok"
    assert record["gemma_expected_device"] == "cuda"
    assert record["gemma_n_gpu_layers"] == -1
    assert record["gemma_device_status"] == "ok"


def test_low_tier_trace_cli_controlled_fallback_mode_writes_report(tmp_path: Path, monkeypatch, capsys):
    write_project(tmp_path)
    touch_model(tmp_path, "models/qwen3-0.6b", "qwen.gguf")
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_low_tier_trace, "LlamaCppBackend", lambda **kwargs: SequenceBackend([" gemma output"]))
    monkeypatch.setattr(
        run_low_tier_trace,
        "collect_environment_diagnostics",
        lambda config: {
            "backend": {"llama_cpp_supports_gpu_offload": True},
            "models": {
                "qwen_drafter": {"device_status": "ok"},
                "gemma_e2b": {"device_status": "ok"},
            },
        },
    )

    exit_code = run_low_tier_trace.main(["--mode", "controlled-fallback"])

    output = capsys.readouterr().out
    reports = list((tmp_path / "logs/reports").glob("*-low-tier-trace.json"))
    assert exit_code == 0
    assert "controlled fallback trace: ok" in output
    assert "total_cases: 4" in output
    assert "valid_count: 1" in output
    assert "rejected_count: 3" in output
    assert "fallback_count: 3" in output


def test_low_tier_trace_cli_raw_capture_flag_writes_raw_fields(tmp_path: Path, monkeypatch):
    write_project(tmp_path)
    touch_model(tmp_path, "models/qwen3-0.6b", "qwen.gguf")
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_low_tier_trace, "LlamaCppBackend", lambda **kwargs: SequenceBackend([" raw output"]))
    monkeypatch.setattr(
        run_low_tier_trace,
        "collect_environment_diagnostics",
        lambda config: {
            "backend": {"llama_cpp_supports_gpu_offload": True},
            "models": {
                "qwen_drafter": {"device_status": "ok"},
                "gemma_e2b": {"device_status": "ok"},
            },
        },
    )

    exit_code = run_low_tier_trace.main(["--prompt", "Short prompt.", "--capture-raw-output"])

    report = next((tmp_path / "logs/reports").glob("*-low-tier-trace.json"))
    text = report.read_text(encoding="utf-8")
    assert exit_code == 0
    assert '"capture_raw_output": true' in text
    assert '"raw_prompt": "Short prompt."' in text
