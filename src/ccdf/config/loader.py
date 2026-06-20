from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]


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


def resolve_compressor_model_source(
    profile_config: dict[str, Any] | None,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    cfg = profile_config or {}
    base_dir = Path(repo_root) if repo_root is not None else REPO_ROOT
    model_name = cfg.get("model_name")
    compressor_path = cfg.get("compressor_path")
    local_files_only = bool(cfg.get("local_files_only", False))

    if compressor_path:
        configured_path = Path(str(compressor_path)).expanduser()
        resolved_path = configured_path if configured_path.is_absolute() else (base_dir / configured_path).resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(
                "Configured compressor_path does not exist: "
                f"{compressor_path} (resolved to {resolved_path})"
            )
        return {
            "source": str(resolved_path),
            "source_kind": "compressor_path",
            "model_name": model_name,
            "compressor_path": str(compressor_path),
            "resolved_compressor_path": str(resolved_path),
            "local_files_only": local_files_only,
        }

    return {
        "source": str(model_name) if model_name is not None else None,
        "source_kind": "model_name",
        "model_name": model_name,
        "compressor_path": None,
        "resolved_compressor_path": None,
        "local_files_only": local_files_only,
    }
