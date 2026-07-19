from pathlib import Path

import pytest

from ccdf import Rec2Config, load_config
from ccdf.core.errors import ConfigurationError


ROOT = Path(__file__).resolve().parents[1]


def test_public_config_imports_remain_stable() -> None:
    config = load_config(ROOT / "config.yml")
    assert isinstance(config, Rec2Config)
    assert config.path == (ROOT / "config.yml").resolve()
    assert config.root == ROOT.resolve()


def test_missing_config_path_uses_domain_error(tmp_path) -> None:
    with pytest.raises(ConfigurationError, match="config file not found"):
        load_config(tmp_path / "missing.yml")


def test_model_profile_rejects_unknown_condition() -> None:
    config = load_config(ROOT / "config.yml")
    with pytest.raises(ConfigurationError, match="unknown condition"):
        config.model_profile("unknown")


def test_compressor_budget_declarations_must_match() -> None:
    config = load_config(ROOT / "config.yml")
    data = {**config.data, "memory": dict(config.data["memory"])}
    data["memory"]["compressor_reserved_budget_gib"] = 2.0
    conflicted = Rec2Config(path=config.path, root=config.root, data=data)

    with pytest.raises(ConfigurationError, match="compressor reserved budget conflict"):
        conflicted.validate()
