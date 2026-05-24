from pathlib import Path
import tomllib

import pytest

from htfsd.config import DEFAULT_CONFIG_PATH, load_config, resolve_config_path


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


def write_config(repo_root: Path, text: str = CONFIG_TEXT) -> Path:
    config_path = repo_root / DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True)
    config_path.write_text(text, encoding="utf-8")
    return config_path


def touch_model(repo_root: Path, model_dir: str, filename: str) -> Path:
    path = repo_root / model_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("fake gguf", encoding="utf-8")
    return path


def test_resolve_config_path_uses_default_when_omitted(tmp_path: Path):
    config_path = write_config(tmp_path)

    resolved = resolve_config_path(None, repo_root=tmp_path)

    assert resolved == config_path


def test_relative_model_dir_resolves_against_repo_root(tmp_path: Path):
    write_config(tmp_path)

    config = load_config(repo_root=tmp_path)

    assert config.models["qwen_drafter"].model_dir == tmp_path / "models/qwen3-0.6b"


def test_model_device_policy_defaults_by_model_role(tmp_path: Path):
    write_config(tmp_path)

    config = load_config(repo_root=tmp_path)

    assert config.models["qwen_drafter"].expected_device == "cpu"
    assert config.models["qwen_drafter"].n_gpu_layers == 0
    assert config.models["qwen_drafter"].optional is False
    assert config.models["gemma_e2b"].expected_device == "cuda"
    assert config.models["gemma_e2b"].n_gpu_layers == -1
    assert config.models["gemma_e2b"].optional is False
    assert config.models["gemma_e4b"].expected_device == "cuda"
    assert config.models["gemma_e4b"].n_gpu_layers == -1
    assert config.models["gemma_e4b"].optional is True


def test_model_device_policy_can_be_explicitly_configured(tmp_path: Path):
    config_text = CONFIG_TEXT.replace(
        "model_file: null",
        "model_file: null\n    expected_device: auto\n    n_gpu_layers: 12\n    optional: true",
        1,
    )
    write_config(tmp_path, config_text)

    config = load_config(repo_root=tmp_path)

    model = config.models["qwen_drafter"]
    assert model.expected_device == "auto"
    assert model.n_gpu_layers == 12
    assert model.optional is True


def test_invalid_expected_device_is_rejected(tmp_path: Path):
    config_text = CONFIG_TEXT.replace("model_file: null", "model_file: null\n    expected_device: tpu", 1)
    write_config(tmp_path, config_text)

    with pytest.raises(ValueError, match="expected_device"):
        load_config(repo_root=tmp_path)


def test_exactly_one_gguf_is_auto_selected(tmp_path: Path):
    write_config(tmp_path)
    qwen = touch_model(tmp_path, "models/qwen3-0.6b", "qwen.Q4_K_M.gguf")

    config = load_config(repo_root=tmp_path)

    model = config.models["qwen_drafter"]
    assert model.status == "ok"
    assert model.discovered_model_file == qwen
    assert model.candidates == [qwen]


def test_zero_gguf_files_returns_structured_missing_model(tmp_path: Path):
    write_config(tmp_path)
    (tmp_path / "models/qwen3-0.6b").mkdir(parents=True)

    config = load_config(repo_root=tmp_path)

    model = config.models["qwen_drafter"]
    assert model.status == "missing_model_file"
    assert model.error_code == "missing_model"
    assert model.discovered_model_file is None


def test_missing_model_folder_returns_structured_missing_dir(tmp_path: Path):
    write_config(tmp_path)

    config = load_config(repo_root=tmp_path)

    model = config.models["qwen_drafter"]
    assert model.status == "missing_model_dir"
    assert model.error_code == "missing_model_dir"


def test_multiple_gguf_files_returns_structured_ambiguous_model(tmp_path: Path):
    write_config(tmp_path)
    first = touch_model(tmp_path, "models/qwen3-0.6b", "a.gguf")
    second = touch_model(tmp_path, "models/qwen3-0.6b", "b.gguf")

    config = load_config(repo_root=tmp_path)

    model = config.models["qwen_drafter"]
    assert model.status == "ambiguous_model_files"
    assert model.error_code == "ambiguous_model"
    assert model.discovered_model_file is None
    assert model.candidates == [first, second]


def test_explicit_model_file_override_is_used(tmp_path: Path):
    config_text = CONFIG_TEXT.replace(
        "model_file: null",
        "model_file: custom/model.gguf",
        1,
    )
    write_config(tmp_path, config_text)
    model_file = touch_model(tmp_path, "custom", "model.gguf")
    touch_model(tmp_path, "models/qwen3-0.6b", "ignored.gguf")

    config = load_config(repo_root=tmp_path)

    model = config.models["qwen_drafter"]
    assert model.status == "ok"
    assert model.discovered_model_file == model_file
    assert model.candidates == [model_file]


def test_non_gguf_explicit_model_file_is_rejected(tmp_path: Path):
    config_text = CONFIG_TEXT.replace(
        "model_file: null",
        "model_file: custom/model.bin",
        1,
    )
    write_config(tmp_path, config_text)
    touch_model(tmp_path, "custom", "model.bin")

    config = load_config(repo_root=tmp_path)

    model = config.models["qwen_drafter"]
    assert model.status == "missing_model_file"
    assert model.error_code == "model_file_not_gguf"
    assert model.discovered_model_file is None


def test_missing_default_config_raises_clear_error(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="configs/local.example.yaml"):
        load_config(repo_root=tmp_path)


def test_llama_cpp_python_is_not_a_main_dependency():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert "llama-cpp-python" not in "\n".join(pyproject["project"]["dependencies"])
