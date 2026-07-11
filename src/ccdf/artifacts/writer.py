"""Atomic benchmark artifact writing and summary reads."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from ccdf.benchmark.schemas import validate_row
from ccdf.datasets.hashing import canonical_json, hash_file


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(canonical_json(data) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_jsonl_atomic(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            validate_row(row)
            handle.write(canonical_json(row) + "\n")
    os.replace(tmp, path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                validate_row(row)
                rows.append(row)
    return rows


def assert_artifact_matches(
    path: Path, *, dataset_manifest_hash: str, resolved_config_hash: str | set[str]
) -> None:
    allowed_config_hashes = (
        {resolved_config_hash} if isinstance(resolved_config_hash, str) else resolved_config_hash
    )
    for row in read_jsonl(path):
        if row["dataset_manifest_hash"] != dataset_manifest_hash:
            raise ValueError("stale artifact dataset_manifest_hash mismatch")
        if row["resolved_config_hash"] not in allowed_config_hashes:
            raise ValueError("stale artifact resolved_config_hash mismatch")


def artifact_record(path: Path) -> dict[str, Any]:
    return {"path": str(path), "sha256": hash_file(path)}
