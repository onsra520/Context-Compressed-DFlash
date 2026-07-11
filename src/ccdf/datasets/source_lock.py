"""Source lock construction and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ccdf.datasets.hashing import hash_file
from ccdf.datasets.schemas import BUILDER_VERSION, SOURCE_ARCHIVE_COMMIT, SOURCE_FETCHED_AT


SOURCE_FILES = {
    "gsm8k": {
        "identity": "openai/gsm8k:test",
        "repository": "https://huggingface.co/datasets/openai/gsm8k",
        "archive_relative_path": "data/raw/gsm8k_source.jsonl",
        "license_note": "GSM8K test split; historical raw JSONL retained in archive.",
    },
    "qmsum": {
        "identity": "psunlpgroup/QMSum:test",
        "repository": "https://github.com/Yale-LILY/QMSum",
        "archive_relative_path": "data/raw/qmsum_meeting_qa_source.jsonl",
        "license_note": "QMSum test split meeting QA; historical raw JSONL retained in archive.",
    },
}


def source_path(source_root: Path, dataset: str) -> Path:
    if dataset not in SOURCE_FILES:
        raise ValueError(f"unknown dataset: {dataset}")
    return source_root / SOURCE_FILES[dataset]["archive_relative_path"]


def build_source_lock(source_root: Path) -> dict[str, Any]:
    entries: dict[str, Any] = {}
    for dataset, meta in SOURCE_FILES.items():
        path = source_path(source_root, dataset)
        if not path.exists():
            raise FileNotFoundError(path)
        entries[dataset] = {
            "dataset": dataset,
            "identity": meta["identity"],
            "repository": meta["repository"],
            "resolved_revision": SOURCE_ARCHIVE_COMMIT,
            "file_url": str(path),
            "raw_sha256": hash_file(path),
            "fetched_at": SOURCE_FETCHED_AT,
            "builder_version": BUILDER_VERSION,
            "license_source_note": meta["license_note"],
        }
    return {
        "lock_version": "rec-t02a.source-lock.v1",
        "entries": entries,
        "caveat": (
            "Raw source files are read from the Rec-T01A historical archive and locked by "
            "archive source commit plus file SHA-256; no dynamic branch source is used."
        ),
    }


def validate_source_lock(source_root: Path, lock: dict[str, Any]) -> None:
    for dataset, entry in lock["entries"].items():
        actual = hash_file(source_path(source_root, dataset))
        if actual != entry["raw_sha256"]:
            raise ValueError(f"raw hash mismatch for {dataset}: {actual} != {entry['raw_sha256']}")
        for required in ["identity", "resolved_revision", "file_url", "raw_sha256"]:
            if not entry.get(required):
                raise ValueError(f"source lock for {dataset} missing {required}")
