"""Deterministic hashing helpers for dataset artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_json(data: Any) -> str:
    return hash_text(canonical_json(data))


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_jsonl_rows(rows: list[dict[str, Any]]) -> str:
    payload = "".join(canonical_json(row) + "\n" for row in rows)
    return hash_text(payload)
