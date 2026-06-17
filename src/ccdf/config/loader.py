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


def resolve_llmlingua_config(config: dict[str, Any] | None, profile: str = "large") -> dict[str, Any]:
    if not config:
        config = {}
    comp = config.get("compression") or {}

    p = str(profile).strip().lower()
    if p in ("large", "large_llmlingua"):
        resolved_profile = "large"
    elif p in ("light", "light_llmlingua"):
        resolved_profile = "light"
    else:
        raise ValueError(f"Unknown compressor profile alias: '{profile}'")

    if resolved_profile == "large":
        if "large_llmlingua" in comp:
            return comp["large_llmlingua"] or {}
        if "llmlingua" in comp:
            return comp["llmlingua"] or {}
        return {}
    elif resolved_profile == "light":
        if "light_llmlingua" in comp:
            return comp["light_llmlingua"] or {}
        raise ValueError(f"Requested compressor profile '{profile}' but compression.light_llmlingua is not configured.")

    return {}