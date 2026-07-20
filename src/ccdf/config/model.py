"""Typed access to the expanded CCDF configuration tree."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..core.errors import ConfigurationError


def _require(mapping: Mapping[str, Any], dotted: str) -> Any:
    current: Any = mapping
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise ConfigurationError(f"missing required config key: {dotted}")
        current = current[part]
    return current


@dataclass(frozen=True)
class Rec2Config:
    path: Path
    root: Path
    data: dict[str, Any]

    def get(self, dotted: str, default: Any = None) -> Any:
        current: Any = self.data
        for part in dotted.split("."):
            if not isinstance(current, Mapping) or part not in current:
                return default
            current = current[part]
        return current

    def require(self, dotted: str) -> Any:
        return _require(self.data, dotted)

    def path_for(self, dotted: str) -> Path:
        value = self.require(dotted)
        if not isinstance(value, str):
            raise ConfigurationError(f"config key is not a path string: {dotted}")
        return Path(value).resolve()

    def model_profile(self, condition: str, target_profile: str = "primary") -> dict[str, Any]:
        if condition == "baseline":
            return dict(self.require("models.baseline"))
        if condition != "dflash":
            raise ConfigurationError(f"unknown condition: {condition}")
        target = dict(self.require("models.dflash.target"))
        if target_profile == "fallback":
            target = {
                **target,
                "model_id": target["fallback_model_id"],
                "local_path": target["fallback_local_path"],
                "quantization": target["fallback_quantization"],
                "tokenizer_path": target["fallback_local_path"],
            }
        elif target_profile != "primary":
            raise ConfigurationError(f"unknown target profile: {target_profile}")
        return target

    def validate(self, require_model_files: bool = False) -> list[str]:
        from .validation import validate_config

        return validate_config(self, require_model_files=require_model_files)
