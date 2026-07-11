"""Freeze staged dataset artifacts into canonical data/eval."""

from __future__ import annotations

import shutil
import json
from pathlib import Path
from typing import Any

from ccdf.datasets.hashing import hash_file
from ccdf.datasets.io import write_json


def _copy_tree_no_overwrite(src: Path, dst: Path, *, overwrite: bool) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        target = dst / path.relative_to(src)
        if target.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite canonical dataset file: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        copied.append({"path": str(target), "sha256": hash_file(target)})
    return copied


def freeze_dataset(
    *,
    staging_root: Path,
    project_root: Path,
    dataset: str = "all",
    confirm_freeze: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    if not confirm_freeze:
        raise PermissionError("freeze requires --confirm-freeze")
    staging_root = staging_root.resolve()
    project_root = project_root.resolve()
    datasets = ["gsm8k", "qmsum"] if dataset == "all" else [dataset]
    frozen_manifest_path = staging_root / "frozen_subset_manifest.json"
    if not frozen_manifest_path.exists():
        raise FileNotFoundError(frozen_manifest_path)
    frozen_manifest = json.loads(frozen_manifest_path.read_text(encoding="utf-8"))
    for name in datasets:
        for subset, entry in frozen_manifest["eval_files"][name].items():
            path = Path(entry["path"])
            if not path.is_absolute():
                path = staging_root / path
            if hash_file(path) != entry["sha256"]:
                raise ValueError(f"staged eval hash mismatch for {name} {subset}: {path}")
    copied: list[dict[str, Any]] = []
    for name in datasets:
        if name not in {"gsm8k", "qmsum"}:
            raise ValueError(f"unknown dataset: {name}")
        copied.extend(
            _copy_tree_no_overwrite(
                staging_root / "data" / "eval" / name,
                project_root / "data" / "eval" / name,
                overwrite=overwrite,
            )
        )
        copied.extend(
            _copy_tree_no_overwrite(
                staging_root / "data" / "manifests" / name,
                project_root / "data" / "manifests" / name,
                overwrite=overwrite,
            )
        )
    manifest = {
        "freeze_version": "rec-t02a.freeze.v1",
        "dataset": dataset,
        "staging_root": str(staging_root),
        "confirm_freeze": confirm_freeze,
        "overwrite": overwrite,
        "copied": copied,
    }
    write_json(project_root / "data" / "manifests" / "freeze_manifest.json", manifest)
    return manifest
