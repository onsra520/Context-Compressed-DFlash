"""Root configuration loader with deterministic path expansion."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .errors import ConfigurationError


def _expand(value: Any, project_root: Path) -> Any:
    if isinstance(value, str):
        expanded = value.replace("${PROJECT_ROOT}", str(project_root))
        return os.path.expandvars(os.path.expanduser(expanded))
    if isinstance(value, list):
        return [_expand(item, project_root) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item, project_root) for key, item in value.items()}
    return value


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
        required = [
            "paths.project_root",
            "paths.baseline_model",
            "paths.dflash_target_model",
            "paths.dflash_drafter_model",
            "paths.compressor_model",
            "models.baseline.model_id",
            "models.baseline.local_path",
            "models.dflash.target.model_id",
            "models.dflash.target.local_path",
            "models.dflash.drafter.model_id",
            "models.dflash.drafter.local_path",
            "memory.dflash_peak_reserved_limit_gib",
            "runtime.attention_backend",
            "runtime.sdpa_kernel",
            "runtime.awq_split_k_iters",
        ]
        for key in required:
            self.require(key)
        warnings: list[str] = []
        limit = float(self.require("memory.dflash_peak_reserved_limit_gib"))
        reserve = float(self.require("memory.compressor_reserved_budget_gib"))
        if limit <= 0 or reserve < 0:
            raise ConfigurationError("memory limits must be positive")
        if limit + reserve > 8.001:
            warnings.append("D-Flash limit plus compressor reserve exceeds 8 GiB")
        if self.require("runtime.attention_backend") != "sdpa":
            raise ConfigurationError("canonical runtime requires attention_backend=sdpa")
        if self.require("runtime.sdpa_kernel") != "math":
            raise ConfigurationError("canonical runtime requires sdpa_kernel=math")
        if int(self.require("runtime.awq_split_k_iters")) != 1:
            raise ConfigurationError("canonical runtime requires awq_split_k_iters=1")
        allowed = list(self.require("optimization.block_policy.allowed_block_sizes"))
        checkpoint = int(self.require("models.dflash.drafter.checkpoint_block_size"))
        if sorted(set(allowed)) != sorted(allowed):
            raise ConfigurationError("allowed block sizes must be unique and sorted")
        if any(int(size) < 2 or int(size) > checkpoint for size in allowed):
            raise ConfigurationError("allowed block sizes must be in [2, checkpoint_block_size]")
        if require_model_files:
            for key in (
                "models.baseline.local_path",
                "models.dflash.target.local_path",
                "models.dflash.drafter.local_path",
            ):
                path = Path(self.require(key))
                if not path.exists():
                    raise ConfigurationError(f"model path does not exist: {path}")
        return warnings


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
