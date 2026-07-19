"""Canonical configuration contract validation."""

from __future__ import annotations

from pathlib import Path

from ..core.errors import ConfigurationError
from .model import Rec2Config


def validate_config(config: Rec2Config, *, require_model_files: bool = False) -> list[str]:
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
        "datasets.qmsum_context_policy",
        "datasets.qmsum_context_budget_tokens",
        "datasets.qmsum_chunk_target_tokens",
        "dataset_smoke.compression.adaptive_keep_rate.enabled",
    ]
    for key in required:
        config.require(key)
    warnings: list[str] = []
    limit = float(config.require("memory.dflash_peak_reserved_limit_gib"))
    reserve = float(config.require("memory.compressor_reserved_budget_gib"))
    model_reserve = float(config.require("models.compressor.reserved_budget_gib"))
    if limit <= 0 or reserve < 0:
        raise ConfigurationError("memory limits must be positive")
    if model_reserve != reserve:
        raise ConfigurationError(
            "compressor reserved budget conflict: models.compressor.reserved_budget_gib "
            "must equal memory.compressor_reserved_budget_gib"
        )
    if limit + reserve > 8.001:
        warnings.append("D-Flash limit plus compressor reserve exceeds 8 GiB")
    if config.require("runtime.attention_backend") != "sdpa":
        raise ConfigurationError("canonical runtime requires attention_backend=sdpa")
    if config.require("runtime.sdpa_kernel") != "math":
        raise ConfigurationError("canonical runtime requires sdpa_kernel=math")
    if int(config.require("runtime.awq_split_k_iters")) != 1:
        raise ConfigurationError("canonical runtime requires awq_split_k_iters=1")
    if config.require("datasets.qmsum_context_policy") != "query_aware_budgeted":
        raise ConfigurationError("QMSum runtime requires query_aware_budgeted context policy")
    context_budget = int(config.require("datasets.qmsum_context_budget_tokens"))
    chunk_target = int(config.require("datasets.qmsum_chunk_target_tokens"))
    if context_budget < 1 or not 200 <= chunk_target <= 400 or chunk_target > context_budget:
        raise ConfigurationError("QMSum token budget/chunk target is invalid")
    adaptive = dict(config.require("dataset_smoke.compression.adaptive_keep_rate"))
    expected = {
        "enabled": True,
        "short_max_target_user_tokens": 127,
        "medium_max_target_user_tokens": 512,
        "short_keep_rate": 0.85,
        "medium_keep_rate": 0.70,
        "long_keep_rate": 0.55,
        "retry_keep_rate": 0.90,
    }
    if adaptive != expected:
        raise ConfigurationError(f"adaptive compression policy must equal {expected}")
    allowed = list(config.require("optimization.block_policy.allowed_block_sizes"))
    checkpoint = int(config.require("models.dflash.drafter.checkpoint_block_size"))
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
            path = Path(config.require(key))
            if not path.exists():
                raise ConfigurationError(f"model path does not exist: {path}")
    return warnings
