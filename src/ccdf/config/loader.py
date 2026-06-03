from __future__ import annotations

from pathlib import Path
from typing import Any


def load_config(path: str | Path = "config.yml") -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(config_path)

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - dependency issue is environment-specific
        raise RuntimeError("PyYAML is required to load config.yml") from exc

    loaded = yaml.safe_load(config_path.read_text())
    return loaded or {}