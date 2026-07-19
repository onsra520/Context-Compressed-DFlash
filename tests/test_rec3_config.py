from pathlib import Path

from ccdf.config import load_config


ROOT = Path(__file__).resolve().parents[1]


def test_recreated_config_restores_required_compressor_reserve() -> None:
    config = load_config(ROOT / "config.yml")
    assert config.require("memory.compressor_reserved_budget_gib") == 2.25


def test_canonical_contract_is_full_deterministic_mock10() -> None:
    config = load_config(ROOT / "config.yml")
    prompts = config.require("benchmark.prompts")
    assert len(prompts) == len(set(prompts)) == 10
    assert config.require("runtime.temperature") == 0.0
    assert config.require("runtime.enable_thinking") is False
    assert config.require("runtime.attention_backend") == "sdpa"
    assert config.require("runtime.sdpa_kernel") == "math"
    assert config.require("runtime.deterministic") is True
