"""Manifest helpers for staged and frozen datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ccdf.datasets.hashing import hash_file
from ccdf.datasets.io import write_json
from ccdf.datasets.schemas import BUILDER_VERSION, DATASET_SCHEMA_VERSION


def logical_path(path: Path) -> str:
    parts = path.parts
    if "data" in parts:
        idx = len(parts) - 1 - list(reversed(parts)).index("data")
        return "/".join(parts[idx:])
    return str(path)


def stage_manifest(
    *,
    dataset: str,
    stage: str,
    input_paths: list[Path],
    output_paths: list[Path],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "manifest_version": "rec-t02a.stage-manifest.v1",
        "dataset": dataset,
        "stage": stage,
        "schema_version": DATASET_SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "inputs": [{"path": logical_path(path), "sha256": hash_file(path)} for path in input_paths],
        "outputs": [{"path": logical_path(path), "sha256": hash_file(path)} for path in output_paths],
        "extra": extra or {},
    }


def write_stage_manifest(root: Path, manifest: dict[str, Any]) -> Path:
    path = root / "data" / "manifests" / manifest["dataset"] / f"{manifest['stage']}.json"
    write_json(path, manifest)
    return path


def validate_manifest_outputs(manifest: dict[str, Any]) -> None:
    for output in manifest["outputs"]:
        path = Path(output["path"])
        if not path.exists():
            raise FileNotFoundError(path)
        actual = hash_file(path)
        if actual != output["sha256"]:
            raise ValueError(f"manifest output hash mismatch: {path}")
