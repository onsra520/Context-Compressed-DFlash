"""Resolve canonical configuration for every execution surface."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ccdf.artifacts.writer import write_json
from ccdf.config.loader import load_config
from ccdf.config.schemas import ResolvedConfig
from ccdf.config.validation import IMMUTABLE_OVERRIDE_FIELDS
from ccdf.datasets.hashing import hash_file, hash_json
from ccdf.paths import expand_logical_path, find_shared_root, find_worktree_root, logical_path_metadata


def _resolve_model_paths(source: dict[str, Any], worktree_root: Path, shared_root: Path) -> dict[str, Any]:
    models = deepcopy(source["models"])
    for name, model in models.items():
        logical = str(model["path"])
        model["path_logical"] = logical
        model["path"] = str(
            expand_logical_path(
                logical,
                worktree_root=worktree_root,
                shared_root=shared_root,
                default_scope="shared",
            )
        )
    return models


def _subset_identity(
    source: dict[str, Any], dataset: str, subset: str, worktree_root: Path, shared_root: Path
) -> dict[str, str]:
    try:
        subset_config = source["datasets"][dataset]["subsets"][subset]
    except KeyError as exc:
        raise ValueError(f"unsupported subset: {dataset}/{subset}") from exc
    fixture_path = expand_logical_path(
        subset_config["fixture"], worktree_root=worktree_root, shared_root=shared_root
    )
    manifest_path = expand_logical_path(
        subset_config["manifest"], worktree_root=worktree_root, shared_root=shared_root
    )
    if not fixture_path.is_file():
        raise ValueError(f"dataset fixture missing: {fixture_path}")
    if not manifest_path.is_file():
        raise ValueError(f"dataset manifest missing: {manifest_path}")
    return {
        "fixture_path": str(fixture_path),
        "fixture_path_logical": str(subset_config["fixture"]),
        "fixture_file_hash": hash_file(fixture_path),
        "dataset_manifest": str(manifest_path),
        "dataset_manifest_logical": str(subset_config["manifest"]),
        "dataset_manifest_hash": hash_file(manifest_path),
    }


def resolve_config(
    *,
    dataset: str,
    subset: str = "n10",
    condition_id: str = "baseline-ar",
    execution_mode: str = "benchmark",
    overrides: dict[str, Any] | None = None,
    config_path: Path | None = None,
    worktree_root: Path | None = None,
    shared_root: Path | None = None,
) -> ResolvedConfig:
    source = load_config(config_path)
    if dataset not in source["datasets"]:
        raise ValueError(f"unsupported dataset: {dataset}")
    if condition_id not in {"baseline-ar", "dflash-r1", "llmlingua-ar-r2", "cc-dflash-r2", "llmlingua-ar-r2-gpu", "cc-dflash-r2-gpu"}:
        raise ValueError(f"unsupported condition: {condition_id}")
    if execution_mode not in {"benchmark", "profiling", "smoke"}:
        raise ValueError(f"invalid execution mode: {execution_mode}")

    overrides = overrides or {}
    forbidden = IMMUTABLE_OVERRIDE_FIELDS.intersection(overrides)
    if forbidden:
        raise ValueError(f"immutable override rejected: {sorted(forbidden)}")

    worktree = (worktree_root or find_worktree_root(Path(source["_config_path"]).parent)).resolve()
    shared = (shared_root or find_shared_root(worktree)).resolve()
    section = source["datasets"][dataset]

    # Validate execution overrides before touching dataset files so invalid
    # requests fail for the correct reason even in source-only environments.
    max_new_tokens = int(section["max_new_tokens"])
    if "max_new_tokens" in overrides:
        requested = int(overrides["max_new_tokens"])
        if execution_mode != "smoke" or requested >= max_new_tokens:
            raise ValueError("max_new_tokens override is allowed only for smaller smoke-mode runs")
        max_new_tokens = requested

    identity = _subset_identity(source, dataset, subset, worktree, shared)
    artifacts_root = expand_logical_path(
        source["artifacts"]["root"], worktree_root=worktree, shared_root=shared
    )
    models = _resolve_model_paths(source, worktree, shared)
    gpu_compressor = condition_id.endswith("-gpu")
    if gpu_compressor:
        models["compression"]["device"] = "cuda"
    data = {
        "config_version": source["config_version"],
        "config_path": source["_config_path"],
        "path_context": logical_path_metadata(worktree, shared),
        "dataset": dataset,
        "subset": subset,
        "condition_id": condition_id,
        "execution_mode": execution_mode,
        "canonical": execution_mode == "benchmark" and not overrides,
        "overrides": deepcopy(overrides),
        "models": models,
        "runtime": deepcopy(source["runtime"]),
        "prompts": deepcopy(source["prompts"]),
        "output_contracts": deepcopy(source["output_contracts"]),
        "benchmark": deepcopy(source["benchmark"]),
        "compression": deepcopy(source["compression"]),
        "artifacts": {"root": str(artifacts_root), "root_logical": source["artifacts"]["root"]},
        "evaluator_identity": source["evaluators"][dataset],
        "prompt_policy": deepcopy(section["policy"]),
        **identity,
        "max_new_tokens": max_new_tokens,
    }
    data["condition"] = {
        "condition_id": condition_id,
        "target_model_lock_id": f"target:{source['models']['target']['revision']}",
        "draft_model_lock_id": (
            f"drafter:{source['models']['drafter']['revision']}"
            if condition_id in {"dflash-r1", "cc-dflash-r2", "cc-dflash-r2-gpu"}
            else None
        ),
        "compressor_model_lock_id": (
            f"llmlingua2:{source['models']['compression']['id']}"
            if condition_id in {"llmlingua-ar-r2", "cc-dflash-r2", "llmlingua-ar-r2-gpu", "cc-dflash-r2-gpu"}
            else None
        ),
        "tokenizer_source": source["models"]["target"]["tokenizer"],
        "generation_mode": "autoregressive" if condition_id in {"baseline-ar", "llmlingua-ar-r2", "llmlingua-ar-r2-gpu"} else "dflash",
        "max_new_tokens": max_new_tokens,
        "temperature": source["runtime"]["temperature"],
        "block_size": (
            source["models"]["drafter"]["block_size"] if condition_id in {"dflash-r1", "cc-dflash-r2", "cc-dflash-r2-gpu"} else None
        ),
        "enable_thinking": source["runtime"]["enable_thinking"],
        "stop_token_ids": source["runtime"]["stop_token_ids"],
        "attention_backend": source["runtime"]["attention_backend"],
        "quantization_mode": source["models"]["target"]["quantization"],
        "dataset_manifest_hash": data["dataset_manifest_hash"],
        "fixture_file_hash": data["fixture_file_hash"],
        "prompt_policy_id": section["policy"]["id"],
        "claim_boundary": deepcopy(source["runtime"]["claim_boundary"]),
    }
    return ResolvedConfig(data=data, sha256=hash_json(data))


def write_resolved_config(output_dir: Path, resolved: ResolvedConfig) -> None:
    write_json(output_dir / "resolved_config.json", resolved.data)
    (output_dir / "resolved_config.sha256").write_text(resolved.sha256 + "\n", encoding="utf-8")
