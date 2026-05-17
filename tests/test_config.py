import pytest

from htfsd.config import clamp_dflash_max_tokens, load_config, validate_benchmark_decoding


def test_load_config_maps_yaml_to_dataclasses(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
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

    config = load_config(config_file)

    assert config.qwen_drafter.model_id_or_path == "qwen-local"
    assert config.gemma_e2b.model_id_or_path == "e2b-local"
    assert config.gemma_e4b_baseline.model_id_or_path == "e4b-local"
    assert config.runtime.execution_mode == "concurrent"
    assert config.decoding.default == "greedy"
    assert config.decoding.sampling.experimental is True


def test_dflash_max_tokens_clamps_to_hard_limit():
    assert clamp_dflash_max_tokens(requested=32, default=8, hard=16) == 16
    assert clamp_dflash_max_tokens(requested=4, default=8, hard=16) == 4
    assert clamp_dflash_max_tokens(requested=None, default=8, hard=16) == 8


def test_benchmark_low_rejects_sampling_mode():
    with pytest.raises(ValueError, match="benchmark-low only supports greedy"):
        validate_benchmark_decoding("sampling")


def test_sequential_mode_label_is_debug_non_comparable(tmp_path):
    config_file = tmp_path / "config.yaml"
    text = open("configs/local.example.yaml", encoding="utf-8").read()
    config_file.write_text(text.replace('execution_mode: "concurrent"', 'execution_mode: "sequential"'), encoding="utf-8")

    config = load_config(config_file)

    assert config.runtime.execution_mode == "sequential"
