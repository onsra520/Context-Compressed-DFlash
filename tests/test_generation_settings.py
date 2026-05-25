from htfsd.metrics.generation_settings import build_generation_settings
from htfsd.metrics.prompt_sets import DEFAULT_TRACE_PROMPT_SET, default_trace_prompts
from htfsd.types import GenerationConfig, HTFSDConfig, RuntimeConfig


def test_generation_settings_default_to_trace_safe_values(tmp_path):
    config = HTFSDConfig(
        repo_root=tmp_path,
        config_path=tmp_path / "configs/local.example.yaml",
        models={},
        runtime=RuntimeConfig(backend="llama_cpp", n_ctx=2048, seed=42),
        generation=GenerationConfig(max_tokens=64, temperature=0.0),
    )

    settings = build_generation_settings(config)

    assert settings.max_tokens == 64
    assert settings.temperature == 0.0
    assert settings.seed == 42
    assert settings.stop is None
    assert settings.prompt_mode == "raw"
    assert settings.capture_raw_output is False
    assert settings.output_summary_max_chars == 120
    assert settings.to_metadata()["capture_raw_output"] is False


def test_generation_settings_accept_cli_overrides(tmp_path):
    config = HTFSDConfig(
        repo_root=tmp_path,
        config_path=tmp_path / "configs/local.example.yaml",
        models={},
        runtime=RuntimeConfig(backend="llama_cpp", n_ctx=2048, seed=42),
        generation=GenerationConfig(max_tokens=64, temperature=0.0),
    )

    settings = build_generation_settings(
        config,
        max_tokens=16,
        temperature=0.2,
        capture_raw_output=True,
    )

    assert settings.max_tokens == 16
    assert settings.temperature == 0.2
    assert settings.capture_raw_output is True


def test_generation_settings_accept_prompt_mode_chat(tmp_path):
    config = HTFSDConfig(
        repo_root=tmp_path,
        config_path=tmp_path / "configs/local.example.yaml",
        models={},
        runtime=RuntimeConfig(backend="llama_cpp", n_ctx=2048, seed=42),
        generation=GenerationConfig(max_tokens=64, temperature=0.0),
    )

    settings = build_generation_settings(config, prompt_mode="chat")

    assert settings.prompt_mode == "chat"


def test_generation_settings_reject_unknown_prompt_mode(tmp_path):
    config = HTFSDConfig(
        repo_root=tmp_path,
        config_path=tmp_path / "configs/local.example.yaml",
        models={},
        runtime=RuntimeConfig(backend="llama_cpp", n_ctx=2048, seed=42),
        generation=GenerationConfig(max_tokens=64, temperature=0.0),
    )

    try:
        build_generation_settings(config, prompt_mode="template")
    except ValueError as error:
        assert "Unsupported prompt_mode" in str(error)
    else:
        raise AssertionError("expected unsupported prompt mode to be rejected")


def test_default_trace_prompt_set_is_centralized():
    prompts = default_trace_prompts()

    assert DEFAULT_TRACE_PROMPT_SET.prompt_set_id == "phase-1-controlled-trace-v1"
    assert len(prompts) == 3
    assert prompts[0].prompt_id == "prompt-001"
    assert prompts[0].text.startswith("Explain speculative decoding")
