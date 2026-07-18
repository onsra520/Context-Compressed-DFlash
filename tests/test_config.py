from pathlib import Path
import copy

import pytest

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
