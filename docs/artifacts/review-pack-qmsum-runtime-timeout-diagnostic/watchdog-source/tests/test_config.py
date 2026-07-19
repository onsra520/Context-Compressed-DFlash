from pathlib import Path
import copy

import pytest

import ccdf.config as config_module
from ccdf.config import Config, load_config
from ccdf.errors import ConfigurationError


def test_config_expands_project_root(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("PROJECT_ROOT", str(root))
    config = load_config(root / "config.yml")
    assert config.path_for("paths.project_root") == root
    assert str(config.require("models.dflash.target.local_path")).startswith(str(root))
    profile = config.resolve_active_protocol_profile()
    assert config.require("memory.dflash_peak_reserved_limit_gib") == profile.require(
        "hard_gates.dflash_peak_reserved_vram_gib"
    )
    assert isinstance(config.require("runtime.seed"), int)
    assert isinstance(config.require("runtime.deterministic"), bool)
    assert isinstance(config.require("runtime.allow_tf32"), bool)
    assert config.require("runtime.attention_backend")
    assert config.require("runtime.sdpa_kernel")
    assert int(config.require("runtime.awq_split_k_iters")) > 0
    assert len(config.require("benchmark.prompts")) == len(profile.require("fixtures"))
    assert config.require("memory.compressor_residency_mode") == "staged"
    assert config.require("memory.generation_residency_mode") == "staged"
    assert config.require("memory.request_cache_policy") == "preserve"
    assert not any("simultaneous" in warning for warning in config.validate(False))


def test_memory_warning_only_applies_to_simultaneous_residency():
    root = Path(__file__).resolve().parents[1]
    canonical = load_config(root / "config.yml")
    data = copy.deepcopy(canonical.data)
    data["memory"]["compressor_residency_mode"] = "simultaneous"
    data["memory"]["generation_residency_mode"] = "simultaneous"
    simultaneous = Config(path=canonical.path, root=canonical.root, data=data)
    assert any("simultaneous" in warning for warning in simultaneous.validate(False))


def test_memory_residency_modes_cannot_describe_mixed_lifecycles():
    root = Path(__file__).resolve().parents[1]
    canonical = load_config(root / "config.yml")
    data = copy.deepcopy(canonical.data)
    data["memory"]["compressor_residency_mode"] = "simultaneous"
    mixed = Config(path=canonical.path, root=canonical.root, data=data)
    with pytest.raises(ConfigurationError, match="same lifecycle"):
        mixed.validate(False)


def test_sdpa_policy_accepts_auto_and_rejects_unknown():
    root = Path(__file__).resolve().parents[1]
    canonical = load_config(root / "config.yml")
    assert canonical.require("runtime.sdpa_kernel") == "math"
    auto_data = copy.deepcopy(canonical.data)
    auto_data["runtime"]["sdpa_kernel"] = "auto"
    Config(path=canonical.path, root=canonical.root, data=auto_data).validate(False)
    invalid_data = copy.deepcopy(canonical.data)
    invalid_data["runtime"]["sdpa_kernel"] = "flash"
    with pytest.raises(ConfigurationError, match="unsupported runtime.sdpa_kernel"):
        Config(path=canonical.path, root=canonical.root, data=invalid_data).validate(False)


def test_active_profiles_use_auto_sdpa_and_dataset_specific_output_limits():
    root = Path(__file__).resolve().parents[1]
    canonical = load_config(root / "config.yml")
    active = canonical.resolve_active_protocol_profile()
    dataset = canonical.resolve_dataset_smoke_profile()

    assert canonical.require("runtime.sdpa_kernel") == "math"
    assert active.config.require("runtime.attention_backend") == "sdpa"
    assert active.config.require("runtime.sdpa_kernel") == "auto"
    assert dataset.config.require("runtime.attention_backend") == "sdpa"
    assert dataset.config.require("runtime.sdpa_kernel") == "auto"
    assert dataset.require("generation.gsm8k_max_new_tokens") == 256
    assert dataset.require("generation.qmsum_max_new_tokens") == 512
    watchdog = dataset.require("watchdog")
    assert 0 < watchdog["no_progress_timeout_seconds"] <= watchdog[
        "condition_wall_clock_timeout_seconds"
    ] <= watchdog["dataset_wall_clock_timeout_seconds"]
    assert str(active.require("review_archive")).endswith(".zip")
    assert str(dataset.require("review_archive")).endswith(".zip")


def test_active_profile_rejects_non_auto_sdpa():
    root = Path(__file__).resolve().parents[1]
    canonical = load_config(root / "config.yml")
    data = copy.deepcopy(canonical.data)
    data["protocol_profiles"]["profiles"]["rec3"]["config_overrides"]["runtime"][
        "sdpa_kernel"
    ] = "math"
    with pytest.raises(ConfigurationError, match="requires sdpa_kernel=auto"):
        Config(path=canonical.path, root=canonical.root, data=data).validate(False)


def test_dataset_profile_uses_config_declared_platform_allocator(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    canonical = load_config(root / "config.yml")

    monkeypatch.setattr(config_module.sys, "platform", "win32")
    windows = canonical.resolve_dataset_smoke_profile()
    assert windows.config.require("runtime.cuda_allocator_conf") is None
    assert windows.require("effective_platform") == "win32"
    assert windows.config.require("optimization.block_policy.fixed_block_size") == 8
    assert windows.require("generation.condition_worker_max_attempts") == 1

    monkeypatch.setattr(config_module.sys, "platform", "linux")
    linux = canonical.resolve_dataset_smoke_profile()
    assert linux.config.require("runtime.cuda_allocator_conf") == (
        "expandable_segments:True,garbage_collection_threshold:0.5"
    )


def test_dataset_watchdog_rejects_inverted_config_owned_limits():
    root = Path(__file__).resolve().parents[1]
    canonical = load_config(root / "config.yml")
    data = copy.deepcopy(canonical.data)
    watchdog = data["dataset_smoke"]["watchdog"]
    watchdog["no_progress_timeout_seconds"] = (
        watchdog["condition_wall_clock_timeout_seconds"] * 2
    )

    with pytest.raises(ConfigurationError, match="no-progress <= condition <= dataset"):
        Config(path=canonical.path, root=canonical.root, data=data).validate(False)
