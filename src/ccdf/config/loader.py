"""Load the JSON-compatible canonical YAML configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ccdf.config.validation import validate_config


DEFAULT_CONFIG_PATH = Path("configs/reconstruction.yml")


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    validate_config(data)
    return data
