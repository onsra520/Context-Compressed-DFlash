"""YAML loading with deterministic environment and project-root expansion."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from ..core.errors import ConfigurationError
from .model import Rec2Config


def _expand(value: Any, project_root: Path) -> Any:
    if isinstance(value, str):
        expanded = value.replace("${PROJECT_ROOT}", str(project_root))
        return os.path.expandvars(os.path.expanduser(expanded))
    if isinstance(value, list):
        return [_expand(item, project_root) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item, project_root) for key, item in value.items()}
    return value


def load_config(path: str | Path = "config.yml") -> Rec2Config:
    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise ConfigurationError(f"config file not found: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigurationError("root config must be a mapping")
    project_root = Path(os.environ.get("PROJECT_ROOT", config_path.parent)).expanduser().resolve()
    expanded = _expand(raw, project_root)
    config = Rec2Config(path=config_path, root=project_root, data=expanded)
    config.validate(require_model_files=False)
    return config
