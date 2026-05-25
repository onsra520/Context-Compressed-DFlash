from pathlib import Path

from htfsd.cli.check_env import main


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
  n_gpu_layers: -1
  seed: 42
generation:
  max_tokens: 64
  temperature: 0.0
"""


def write_project(repo_root: Path, config_text: str = CONFIG_TEXT) -> None:
    (repo_root / "pyproject.toml").write_text("[project]\nname='tmp'\n", encoding="utf-8")
    config_path = repo_root / "configs/local.example.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(config_text, encoding="utf-8")


def touch_model(repo_root: Path, model_dir: str, filename: str) -> Path:
    path = repo_root / model_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("fake gguf", encoding="utf-8")
    return path


def test_check_env_uses_default_config_when_omitted(tmp_path: Path, monkeypatch, capsys):
    write_project(tmp_path)
    touch_model(tmp_path, "models/qwen3-0.6b", "qwen.gguf")
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.gguf")
    monkeypatch.chdir(tmp_path)

    exit_code = main([])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Config: configs/local.example.yaml" in output
    assert "drafter: ok" in output
    assert "verifier: ok" in output
    assert "target: optional_missing" in output
    assert "warning" in output


def test_check_env_fails_for_required_missing_models(tmp_path: Path, monkeypatch, capsys):
    write_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main([])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "drafter: missing_model_dir" in output
    assert "verifier: missing_model_dir" in output
    assert "target model is optional for current low-tier diagnostics" in output


def test_check_env_fails_for_ambiguous_required_model(tmp_path: Path, monkeypatch, capsys):
    write_project(tmp_path)
    touch_model(tmp_path, "models/qwen3-0.6b", "qwen.gguf")
    touch_model(tmp_path, "models/gemma-4-e2b-it", "a.gguf")
    touch_model(tmp_path, "models/gemma-4-e2b-it", "b.gguf")
    monkeypatch.chdir(tmp_path)

    exit_code = main([])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "verifier: ambiguous_model_files" in output
    assert "a.gguf" in output
    assert "b.gguf" in output


def test_missing_default_config_returns_error_and_writes_report(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='tmp'\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main([])

    output = capsys.readouterr().out
    reports = list((tmp_path / "logs/errors").glob("*-runtime-error.md"))
    assert exit_code == 1
    assert "config file not found" in output
    assert "Create configs/local.example.yaml" in output
    assert len(reports) == 1
