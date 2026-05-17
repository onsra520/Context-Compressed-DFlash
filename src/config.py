"""YAML configuration loading and validation helpers."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

import yaml

_types = import_module("htfsd_types")
AppConfig = _types.AppConfig
BenchmarkConfig = _types.BenchmarkConfig
BenchmarkDatasetConfig = _types.BenchmarkDatasetConfig
DecodingConfig = _types.DecodingConfig
DFlashConfig = _types.DFlashConfig
GenerationConfig = _types.GenerationConfig
LowTierConfig = _types.LowTierConfig
ModelConfig = _types.ModelConfig
RuntimeConfig = _types.RuntimeConfig
SamplingConfig = _types.SamplingConfig


def _model_config(data: dict[str, Any]) -> ModelConfig:
    return ModelConfig(
        model_id_or_path=str(data["model_id_or_path"]),
        tensor_parallel_size=int(data.get("tensor_parallel_size", 1)),
        dtype=str(data.get("dtype", "auto")),
        gpu_memory_utilization=(
            float(data["gpu_memory_utilization"])
            if data.get("gpu_memory_utilization") is not None
            else None
        ),
    )


def load_config(path: str | Path) -> AppConfig:
    """Load an HTFSD application config from a YAML file."""

    with Path(path).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    models = raw["models"]
    runtime = raw["runtime"]
    generation = raw["generation"]
    dflash = raw["dflash"]
    low_tier = raw["low_tier"]
    decoding = raw["decoding"]
    sampling = decoding["sampling"]
    benchmark = raw["benchmark"]
    dataset = benchmark["dataset"]

    return AppConfig(
        qwen_drafter=_model_config(models["qwen_drafter"]),
        gemma_e2b=_model_config(models["gemma_e2b"]),
        gemma_e4b_baseline=_model_config(models["gemma_e4b_baseline"]),
        runtime=RuntimeConfig(
            backend=str(runtime["backend"]),
            execution_mode=str(runtime["execution_mode"]),
            max_context_tokens=int(runtime["max_context_tokens"]),
            seed=int(runtime["seed"]),
        ),
        generation=GenerationConfig(
            max_new_tokens=int(generation["max_new_tokens"]),
            stop_on_eos=bool(generation["stop_on_eos"]),
        ),
        dflash=DFlashConfig(
            parser=str(dflash["parser"]),
            required_fields=list(dflash["required_fields"]),
            default_max_tokens=int(dflash["default_max_tokens"]),
            hard_max_tokens=int(dflash["hard_max_tokens"]),
            experimental_repair=bool(dflash["experimental_repair"]),
        ),
        low_tier=LowTierConfig(
            acceptance_policy=str(low_tier["acceptance_policy"]),
            fallback_policy=str(low_tier["fallback_policy"]),
            fallback_tokens_per_cycle=int(low_tier["fallback_tokens_per_cycle"]),
        ),
        decoding=DecodingConfig(
            default=str(decoding["default"]),
            sampling=SamplingConfig(
                enabled=bool(sampling["enabled"]),
                experimental=bool(sampling["experimental"]),
                temperature=float(sampling["temperature"]),
                top_p=float(sampling["top_p"]),
            ),
        ),
        benchmark=BenchmarkConfig(
            fixture_path=str(benchmark["fixture_path"]),
            dataset=BenchmarkDatasetConfig(
                enabled=bool(dataset["enabled"]),
                name=dataset["name"],
                split=dataset["split"],
            ),
        ),
    )


def clamp_dflash_max_tokens(*, requested: int | None, default: int, hard: int) -> int:
    """Clamp a requested D-Flash token cap to the configured hard limit."""

    value = default if requested is None else requested
    if value < 0:
        return 0
    return min(value, hard)


def validate_benchmark_decoding(decoding_mode: str) -> None:
    """Reject benchmark decoding modes outside the greedy MVP path."""

    if decoding_mode != "greedy":
        raise ValueError("benchmark-low only supports greedy decoding in the MVP")
