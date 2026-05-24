from pathlib import Path

from htfsd.cli import smoke_gemma, smoke_qwen


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


class FakeBackend:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.text_prompts = []
        self.chat_messages = []

    def generate_text(self, prompt: str, *, max_tokens: int, temperature: float, stop=None):
        self.text_prompts.append(prompt)
        assert prompt
        assert max_tokens == 64
        assert temperature == 0.0
        return type("Result", (), {"text": " raw output", "completion_tokens": 2})()

    def generate_chat(self, messages, *, max_tokens: int, temperature: float, stop=None):
        self.chat_messages.append(messages)
        assert messages == [{"role": "user", "content": "Write a five word greeting."}]
        assert max_tokens == 64
        assert temperature == 0.0
        return type("Result", (), {"text": " chat output", "completion_tokens": 2})()


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


def test_smoke_qwen_uses_default_config_and_prints_draft(tmp_path: Path, monkeypatch, capsys):
    write_project(tmp_path)
    model_path = touch_model(tmp_path, "models/qwen3-0.6b", "qwen.gguf")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(smoke_qwen, "LlamaCppBackend", FakeBackend)

    exit_code = smoke_qwen.main([])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Qwen smoke: ok" in output
    assert "chat output" in output
    assert "expected_device: cpu" in output
    assert "n_gpu_layers: 0" in output
    assert str(model_path.relative_to(tmp_path)) in output


def test_smoke_gemma_default_uses_chat_generation_and_prints_non_empty_text(tmp_path: Path, monkeypatch, capsys):
    write_project(tmp_path)
    model_path = touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(smoke_gemma, "LlamaCppBackend", FakeBackend)

    exit_code = smoke_gemma.main([])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Gemma E2B smoke: ok" in output
    assert "prompt_mode: chat" in output
    assert "expected_device: cuda" in output
    assert "n_gpu_layers: -1" in output
    assert "device_status:" in output
    assert "chat output" in output
    assert str(model_path.relative_to(tmp_path)) in output


def test_smoke_gemma_raw_mode_preserves_raw_generation_path(tmp_path: Path, monkeypatch, capsys):
    write_project(tmp_path)
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(smoke_gemma, "LlamaCppBackend", FakeBackend)

    exit_code = smoke_gemma.main(["--prompt-mode", "raw", "--prompt", "Plain prompt"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "prompt_mode: raw" in output
    assert "raw output" in output


def test_smoke_qwen_fails_when_model_discovery_fails(tmp_path: Path, monkeypatch, capsys):
    write_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = smoke_qwen.main([])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "qwen_drafter is not ready: missing_model_dir" in output
