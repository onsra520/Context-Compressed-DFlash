"""Validation for locks and immutable reconstruction identities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ccdf.datasets.hashing import hash_file
from ccdf.inference.model_registry import model_lock


REQUIRED_SECTIONS = {"models", "runtime", "datasets", "benchmark", "evaluators", "compression", "artifacts"}
IMMUTABLE_OVERRIDE_FIELDS = {"models", "tokenizer", "dataset_manifest", "prompt_policy", "evaluators", "block_size"}


def validate_config(data: dict[str, Any]) -> None:
    missing = REQUIRED_SECTIONS.difference(data)
    if missing:
        raise ValueError(f"config missing required sections: {sorted(missing)}")
    locks = model_lock()
    for name in ("target", "drafter"):
        configured = data["models"][name]
        locked = locks[name]
        if configured["revision"] != locked["revision"]:
            raise ValueError(f"invalid {name} model revision")
        if configured["path"] != locked["path"]:
            raise ValueError(f"{name} model lock mismatch")
    if data["models"]["target"]["tokenizer"] != "target":
        raise ValueError("tokenizer identity must be target")
    if data["models"]["drafter"]["block_size"] != 16:
        raise ValueError("DFlash block size must be 16")
    if not data["runtime"]["offline_local_only"] or data["runtime"]["enable_thinking"]:
        raise ValueError("runtime must be local-only with enable_thinking=false")
    for dataset, section in data["datasets"].items():
        manifest = Path(section["manifest"])
        if not manifest.exists():
            raise ValueError(f"dataset manifest missing: {manifest}")
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        expected = manifest_data["outputs"][0]["sha256"]
        actual = hash_file(Path(section["subsets"]["n10"]))
        if actual != expected:
            raise ValueError(f"dataset manifest mismatch for {dataset}")
        if not section["policy"]["id"] or not section["policy"]["text"]:
            raise ValueError(f"prompt policy identity missing for {dataset}")
    if data["runtime"]["temperature"] != 0.0:
        raise ValueError("temperature must be 0.0")
