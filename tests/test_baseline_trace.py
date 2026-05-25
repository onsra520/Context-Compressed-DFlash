from pathlib import Path

from htfsd.cli import run_baseline_trace
from htfsd.config import load_config
from htfsd.metrics.generation_settings import build_generation_settings
from htfsd.metrics.prompt_sets import default_trace_prompt_texts
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
        self.chat_messages = []

    def generate_text(self, prompt: str, *, max_tokens: int, temperature: float, stop=None):
        self.prompts.append(prompt)
        text = self.outputs[min(len(self.prompts) - 1, len(self.outputs) - 1)]
        return type("Result", (), {"text": text, "completion_tokens": self.tokens})()

    def generate_chat(self, messages: list[dict[str, str]], *, max_tokens: int, temperature: float, stop=None):
        self.chat_messages.append(messages)
        text = self.outputs[min(len(self.chat_messages) - 1, len(self.outputs) - 1)]
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
        generation_settings=build_generation_settings(config),
    )

    assert len(records) == 2
    assert records[0]["trace_kind"] == "target_baseline"
    assert records[0]["prompt_id"] == "baseline-001"
    assert records[0]["gemma_model_file"] == str(gemma_file)
    assert records[0]["gemma_expected_device"] == "cuda"
    assert records[0]["gemma_device_status"] == "ok"
    assert records[0]["gemma_n_gpu_layers"] == -1
    assert records[0]["generation_settings"]["max_tokens"] == 64
    assert records[0]["generation_settings"]["prompt_mode"] == "raw"
    assert records[0]["capture_raw_output"] is False
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
        generation_settings=build_generation_settings(config),
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
        generation_settings=build_generation_settings(config),
    )

    record = records[0]
    assert "raw_prompt" not in record
    assert "gemma_output_text" not in record
    assert len(record["gemma_output_summary"]) <= 120
    assert long_text not in str(record)


def test_baseline_trace_stores_raw_output_only_when_enabled(tmp_path: Path):
    write_project(tmp_path)
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    config = load_config(repo_root=tmp_path)
    diagnostics = {"models": {"gemma_e2b": {"device_status": "ok"}}}

    records = run_target_baseline_trace(
        prompts=["Prompt."],
        config=config,
        diagnostics=diagnostics,
        gemma_backend=FakeGemmaBackend([" raw baseline output"]),
        generation_settings=build_generation_settings(config, capture_raw_output=True),
    )

    record = records[0]
    assert record["capture_raw_output"] is True
    assert record["raw_prompt"] == "Prompt."
    assert record["baseline_raw_output"] == " raw baseline output"


def test_baseline_trace_uses_chat_backend_when_prompt_mode_is_chat(tmp_path: Path):
    write_project(tmp_path)
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    config = load_config(repo_root=tmp_path)
    diagnostics = {"models": {"gemma_e2b": {"device_status": "ok"}}}
    backend = FakeGemmaBackend([" chat output"])

    records = run_target_baseline_trace(
        prompts=["Prompt."],
        config=config,
        diagnostics=diagnostics,
        gemma_backend=backend,
        generation_settings=build_generation_settings(config, prompt_mode="chat", capture_raw_output=True),
    )

    assert backend.prompts == []
    assert backend.chat_messages == [[{"role": "user", "content": "Prompt."}]]
    assert records[0]["generation_settings"]["prompt_mode"] == "chat"
    assert records[0]["baseline_raw_output"] == " chat output"


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
    assert DEFAULT_TRACE_PROMPTS == default_trace_prompt_texts()


def test_baseline_trace_cli_raw_capture_flag_writes_raw_fields(tmp_path: Path, monkeypatch):
    write_project(tmp_path)
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_baseline_trace, "LlamaCppBackend", lambda **kwargs: FakeGemmaBackend([" raw output"]))
    monkeypatch.setattr(
        run_baseline_trace,
        "collect_environment_diagnostics",
        lambda config: {"models": {"gemma_e2b": {"device_status": "ok"}}},
    )

    exit_code = run_baseline_trace.main(["--prompt", "Short prompt.", "--capture-raw-output"])

    report = next((tmp_path / "logs/reports").glob("*-target-baseline-trace.json"))
    text = report.read_text(encoding="utf-8")
    assert exit_code == 0
    assert '"capture_raw_output": true' in text
    assert '"raw_prompt": "Short prompt."' in text


def test_baseline_trace_cli_accepts_prompt_mode_chat(tmp_path: Path, monkeypatch):
    write_project(tmp_path)
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    backend = FakeGemmaBackend([" chat output"])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_baseline_trace, "LlamaCppBackend", lambda **kwargs: backend)
    monkeypatch.setattr(
        run_baseline_trace,
        "collect_environment_diagnostics",
        lambda config: {"models": {"gemma_e2b": {"device_status": "ok"}}},
    )

    exit_code = run_baseline_trace.main(["--prompt", "Short prompt.", "--capture-raw-output", "--prompt-mode", "chat"])

    report = next((tmp_path / "logs/reports").glob("*-target-baseline-trace.json"))
    text = report.read_text(encoding="utf-8")
    assert exit_code == 0
    assert backend.chat_messages == [[{"role": "user", "content": "Short prompt."}]]
    assert '"prompt_mode": "chat"' in text
