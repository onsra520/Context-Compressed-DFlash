"""Validation for locked identities and the Rec-T06A3 claim boundary."""

from __future__ import annotations

from typing import Any

from ccdf.inference.model_registry import model_lock

REQUIRED_SECTIONS = {
    "paths",
    "models",
    "runtime",
    "prompts",
    "output_contracts",
    "datasets",
    "benchmark",
    "evaluators",
    "compression",
    "artifacts",
}
IMMUTABLE_OVERRIDE_FIELDS = {
    "models",
    "tokenizer",
    "dataset_manifest",
    "prompt_policy",
    "evaluators",
    "block_size",
    "claim_boundary",
}


def _require_mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"config field {key!r} must be a mapping")
    return value


def validate_config(data: dict[str, Any]) -> None:
    missing = REQUIRED_SECTIONS.difference(data)
    if missing:
        raise ValueError(f"config missing required sections: {sorted(missing)}")

    paths = _require_mapping(data, "paths")
    if paths.get("worktree_layout") != ".worktrees/rec-<id>-<status>":
        raise ValueError("invalid worktree layout")
    if set(paths.get("allowed_worktree_statuses", [])) != {"ongoing", "closed"}:
        raise ValueError("worktree statuses must be ongoing and closed")

    locks = model_lock()
    for name in ("baseline", "target", "drafter"):
        configured = _require_mapping(data["models"], name)
        locked = locks[name]
        if configured.get("id") != locked["model_id"]:
            raise ValueError(f"invalid {name} model id")
        if configured.get("revision") != locked["revision"]:
            raise ValueError(f"invalid {name} model revision")
        if not str(configured.get("path", "")).startswith(("@shared/", "/")):
            raise ValueError(f"{name} model path must be shared-root or absolute")

    compression_model = _require_mapping(data["models"], "compression")
    if not str(compression_model.get("path", "")).startswith(("@shared/", "/")):
        raise ValueError("compression model path must be shared-root or absolute")

    if data["models"]["baseline"].get("tokenizer") != "baseline":
        raise ValueError("baseline tokenizer identity must be baseline")
    if data["models"]["target"].get("tokenizer") != "target":
        raise ValueError("tokenizer identity must be target")
    if int(data["models"]["drafter"].get("block_size", 0)) != 16:
        raise ValueError("DFlash block size must be 16")

    runtime = data["runtime"]
    if not runtime.get("offline_local_only") or runtime.get("enable_thinking") is not False:
        raise ValueError("runtime must be local-only with enable_thinking=false")
    if float(runtime.get("temperature", -1.0)) != 0.0:
        raise ValueError("temperature must be 0.0")
    boundary = _require_mapping(runtime, "claim_boundary")
    expected_boundary = {
        "exact_cached_ar_token_equivalence": "NOT_CLAIMED",
        "target_verified_block_decoding": "REQUIRED_AND_AUDITED",
        "efficient_one_target_forward_per_block": "REQUIRED",
        "quality_preservation_vs_baseline": "EMPIRICALLY_EVALUATED",
        "quantization_lossless": "NEVER_CLAIMED",
        "upstream_equivalence": "NOT_CLAIMED",
    }
    for key, expected in expected_boundary.items():
        if boundary.get(key) != expected:
            raise ValueError(f"invalid claim boundary {key}: expected {expected}")

    for dataset in ("gsm8k", "qmsum"):
        section = _require_mapping(data["datasets"], dataset)
        policy = _require_mapping(section, "policy")
        if not policy.get("id") or not policy.get("text"):
            raise ValueError(f"prompt policy identity missing for {dataset}")
        subsets = _require_mapping(section, "subsets")
        for subset in ("n10", "n30", "n100"):
            identity = _require_mapping(subsets, subset)
            if not identity.get("fixture") or not identity.get("manifest"):
                raise ValueError(f"{dataset}/{subset} must define fixture and manifest")
