"""Load the canonical reconstruction configuration independent of cwd."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from ccdf.config.validation import validate_config
from ccdf.paths import find_worktree_root

DEFAULT_CONFIG_RELATIVE = Path("configs/reconstruction.yml")


def default_config_path() -> Path:
    explicit = os.environ.get("CCDF_CONFIG")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return find_worktree_root() / DEFAULT_CONFIG_RELATIVE


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = (path or default_config_path()).expanduser().resolve()
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("configuration root must be a mapping")
    validate_config(data)
    data["_config_path"] = str(config_path)
    return data
