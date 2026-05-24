from pathlib import Path

from htfsd.config import load_config
from htfsd.runtime.diagnostics import collect_environment_diagnostics, infer_quantization

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
    config_path = repo_root / "configs/local.example.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(text, encoding="utf-8")
    return config_path


def touch_model(repo_root: Path, model_dir: str, filename: str) -> Path:
    path = repo_root / model_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("fake gguf", encoding="utf-8")
    return path


def test_infer_quantization_from_gguf_filename():
    assert infer_quantization(Path("qwen3-0.6b.Q4_K_M.gguf")) == "Q4_K_M"
    assert infer_quantization(Path("gemma.Q8_0.gguf")) == "Q8_0"
    assert infer_quantization(Path("model.gguf")) is None


def test_diagnostics_report_environment_and_llama_cpp_status(tmp_path: Path):
    write_config(tmp_path)
    config = load_config(repo_root=tmp_path)

    diagnostics = collect_environment_diagnostics(config)

    assert diagnostics["python"]["version"]
    assert diagnostics["python"]["executable"]
    assert diagnostics["platform"]["system"]
    assert "is_wsl" in diagnostics["platform"]
    assert diagnostics["backend"]["name"] == "llama_cpp"
    assert diagnostics["backend"]["llama_cpp_importable"] in (True, False)
    assert diagnostics["backend"]["llama_cpp_supports_gpu_offload"] in (True, False)


def test_diagnostics_report_ok_model_discovery(tmp_path: Path):
    write_config(tmp_path)
    model_file = touch_model(tmp_path, "models/qwen3-0.6b", "qwen.Q5_K_M.gguf")
    config = load_config(repo_root=tmp_path)

    diagnostics = collect_environment_diagnostics(config)

    qwen = diagnostics["models"]["qwen_drafter"]
    assert qwen["model_dir"] == str(tmp_path / "models/qwen3-0.6b")
    assert qwen["discovered_model_file"] == str(model_file)
    assert qwen["status"] == "ok"
    assert qwen["expected_device"] == "cpu"
    assert qwen["configured_n_gpu_layers"] == 0
    assert qwen["observed_backend"] == "llama_cpp"
    assert qwen["observed_gpu_offload"] in (True, False, None)
    assert qwen["device_status"] in ("ok", "unknown", "functional_cpu_only")
    assert qwen["quantization"] == "Q5_K_M"


def test_diagnostics_report_missing_and_ambiguous_model_statuses(tmp_path: Path):
    write_config(tmp_path)
    touch_model(tmp_path, "models/gemma-4-e2b-it", "a.gguf")
    touch_model(tmp_path, "models/gemma-4-e2b-it", "b.gguf")
    config = load_config(repo_root=tmp_path)

    diagnostics = collect_environment_diagnostics(config)

    assert diagnostics["models"]["qwen_drafter"]["status"] == "missing_model_dir"
    assert diagnostics["models"]["gemma_e2b"]["status"] == "ambiguous_model_files"
    assert diagnostics["models"]["gemma_e2b"]["candidates"] == [
        str(tmp_path / "models/gemma-4-e2b-it/a.gguf"),
        str(tmp_path / "models/gemma-4-e2b-it/b.gguf"),
    ]


def test_missing_gemma_e4b_is_reported_as_optional_missing(tmp_path: Path):
    write_config(tmp_path, CONFIG_TEXT)
    config = load_config(repo_root=tmp_path)

    diagnostics = collect_environment_diagnostics(config)

    assert diagnostics["models"]["gemma_e4b"]["status"] == "optional_missing"
    assert diagnostics["models"]["gemma_e4b"]["device_status"] == "optional_missing"


def test_diagnostics_report_cuda_unavailable_for_gemma_policy(tmp_path: Path):
    write_config(tmp_path)
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.Q4_K_M.gguf")
    config = load_config(repo_root=tmp_path)

    diagnostics = collect_environment_diagnostics(
        config,
        llama_cpp_supports_gpu_offload=False,
        observed_gpu_offload={"gemma_e2b": False},
    )

    gemma = diagnostics["models"]["gemma_e2b"]
    assert gemma["expected_device"] == "cuda"
    assert gemma["configured_n_gpu_layers"] == -1
    assert gemma["observed_gpu_offload"] is False
    assert gemma["device_status"] == "cuda_backend_unavailable"


def test_diagnostics_report_device_policy_mismatch_when_gemma_runs_cpu_with_cuda_backend(tmp_path: Path):
    write_config(tmp_path)
    touch_model(tmp_path, "models/gemma-4-e2b-it", "gemma.Q4_K_M.gguf")
    config = load_config(repo_root=tmp_path)

    diagnostics = collect_environment_diagnostics(
        config,
        llama_cpp_supports_gpu_offload=True,
        observed_gpu_offload={"gemma_e2b": False},
    )

    assert diagnostics["models"]["gemma_e2b"]["device_status"] == "device_policy_mismatch"
