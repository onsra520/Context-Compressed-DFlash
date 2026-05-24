from pathlib import Path

from htfsd.cli import run_baseline_trace
from htfsd.config import load_config
from htfsd.metrics.run_trace import DEFAULT_TRACE_PROMPTS
from htfsd.metrics.baseline_trace import run_target_baseline_trace
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


class FakeGemmaBackend:
    def __init__(self, outputs: list[str], tokens: int = 5):
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


def test_baseline_trace_runs_with_fake_gemma_backend(tmp_path: Path):
    write_project(tmp_path)
    gemma_file = touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    config = load_config(repo_root=tmp_path)
    diagnostics = {"models": {"gemma_e2b": {"device_status": "ok"}}}

    records = run_target_baseline_trace(
        prompts=["Prompt one.", "Prompt two."],
        config=config,
        diagnostics=diagnostics,
        gemma_backend=FakeGemmaBackend([" output one", " output two"]),
    )

    assert len(records) == 2
    assert records[0]["trace_kind"] == "target_baseline"
    assert records[0]["prompt_id"] == "baseline-001"
    assert records[0]["gemma_model_file"] == str(gemma_file)
    assert records[0]["gemma_expected_device"] == "cuda"
    assert records[0]["gemma_device_status"] == "ok"
    assert records[0]["gemma_n_gpu_layers"] == -1
    assert validate_trace_record(records[0], mode="target-baseline").ok is True


def test_baseline_trace_does_not_require_qwen_or_bridge_fields(tmp_path: Path):
    write_project(tmp_path)
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    config = load_config(repo_root=tmp_path)
    diagnostics = {"models": {"gemma_e2b": {"device_status": "ok"}}}

    records = run_target_baseline_trace(
        prompts=["Prompt."],
        config=config,
        diagnostics=diagnostics,
        gemma_backend=FakeGemmaBackend([" output"]),
    )

    record = records[0]
    assert "qwen_model_file" not in record
    assert "bridge_status" not in record
    assert "fallback_count" not in record
    assert validate_trace_record(record, mode="target-baseline").ok is True


def test_baseline_trace_does_not_store_long_raw_text_by_default(tmp_path: Path):
    write_project(tmp_path)
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    config = load_config(repo_root=tmp_path)
    diagnostics = {"models": {"gemma_e2b": {"device_status": "ok"}}}
    long_text = "x" * 500

    records = run_target_baseline_trace(
        prompts=["Prompt."],
        config=config,
        diagnostics=diagnostics,
        gemma_backend=FakeGemmaBackend([long_text]),
    )

    record = records[0]
    assert "raw_prompt" not in record
    assert "gemma_output_text" not in record
    assert len(record["gemma_output_summary"]) <= 120
    assert long_text not in str(record)


def test_baseline_trace_cli_writes_report(tmp_path: Path, monkeypatch, capsys):
    write_project(tmp_path)
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_baseline_trace, "LlamaCppBackend", lambda **kwargs: FakeGemmaBackend([" output"]))
    monkeypatch.setattr(
        run_baseline_trace,
        "collect_environment_diagnostics",
        lambda config: {"models": {"gemma_e2b": {"device_status": "ok"}}},
    )

    exit_code = run_baseline_trace.main(["--prompt", "Short prompt."])

    output = capsys.readouterr().out
    reports = list((tmp_path / "logs/reports").glob("*-target-baseline-trace.json"))
    assert exit_code == 0
    assert "Target baseline trace: ok" in output
    assert "trace_records: 1" in output
    assert reports


def test_baseline_trace_uses_default_prompt_set():
    assert len(DEFAULT_TRACE_PROMPTS) == 3
