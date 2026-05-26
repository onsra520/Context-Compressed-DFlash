from pathlib import Path

from htfsd.cli import smoke_pair
from htfsd.text_bridge.pair_smoke import run_pair_smoke


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
    def __init__(self, text: str, tokens: int = 2):
        self.text = text
        self.tokens = tokens
        self.prompts = []

    def generate_text(self, prompt: str, *, max_tokens: int, temperature: float, stop=None):
        self.prompts.append(prompt)
        return type("Result", (), {"text": self.text, "completion_tokens": self.tokens})()


class FakeCliBackend:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        FakeCliBackend.instances.append(self)

    def generate_text(self, prompt: str, *, max_tokens: int, temperature: float, stop=None):
        text = " qwen draft" if len(FakeCliBackend.instances) == 1 else " gemma output"
        return type("Result", (), {"text": text, "completion_tokens": 2})()


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


def test_pair_smoke_valid_bridge_uses_prompt_plus_draft():
    qwen = FakeBackend(" draft text", tokens=3)
    gemma = FakeBackend(" final text", tokens=4)

    result = run_pair_smoke(
        prompt="Prompt:",
        qwen_backend=qwen,
        gemma_backend=gemma,
        max_tokens=8,
        temperature=0.0,
    )

    assert result.bridge_status == "valid"
    assert result.rejection_reason is None
    assert result.fallback_count == 0
    assert result.draft_valid_count == 1
    assert result.draft_rejected_count == 0
    assert gemma.prompts == ["Prompt: draft text"]
    assert "acceptance" not in result.metrics
    assert "acceptance " + "rate" not in str(result.metrics).lower()


def test_pair_smoke_rejected_bridge_uses_gemma_fallback_prompt():
    qwen = FakeBackend("<think>unfinished", tokens=1)
    gemma = FakeBackend(" fallback text", tokens=2)

    result = run_pair_smoke(
        prompt="Prompt:",
        qwen_backend=qwen,
        gemma_backend=gemma,
        max_tokens=8,
        temperature=0.0,
    )

    assert result.bridge_status == "rejected"
    assert result.rejection_reason == "contains_unclosed_think"
    assert result.fallback_count == 1
    assert result.draft_valid_count == 0
    assert result.draft_rejected_count == 1
    assert gemma.prompts == ["Prompt:"]


def test_smoke_pair_cli_requires_qwen_and_gemma_e2b_only(tmp_path: Path, monkeypatch, capsys):
    write_project(tmp_path)
    touch_model(tmp_path, "models/qwen3-0.6b", "qwen.gguf")
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    monkeypatch.chdir(tmp_path)
    FakeCliBackend.instances = []
    monkeypatch.setattr(smoke_pair, "LlamaCppBackend", FakeCliBackend)

    exit_code = smoke_pair.main([])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Pair smoke: ok" in output
    assert "bridge_status: valid" in output
    assert "fallback_count: 0" in output
    assert "qwen_expected_device: cpu" in output
    assert "qwen_n_gpu_layers: 0" in output
    assert "gemma_expected_device: cuda" in output
    assert "gemma_n_gpu_layers: -1" in output
    assert "gemma_device_status:" in output
    assert "gemma_e4b" not in output
    assert "acceptance " + "rate" not in output.lower()
    assert "lossless" not in output.lower()
    assert "speedup" not in output.lower()
    assert FakeCliBackend.instances[0].kwargs["n_gpu_layers"] == 0
    assert FakeCliBackend.instances[1].kwargs["n_gpu_layers"] == -1


def test_smoke_pair_cli_fails_when_gemma_e2b_missing(tmp_path: Path, monkeypatch, capsys):
    write_project(tmp_path)
    touch_model(tmp_path, "models/qwen3-0.6b", "qwen.gguf")
    monkeypatch.chdir(tmp_path)

    exit_code = smoke_pair.main([])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "gemma_e2b is not ready: missing_model_dir" in output
