from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ccdf.datasets import gsm8k
from ccdf.datasets.freeze import freeze_dataset
from ccdf.datasets.hashing import hash_file
from ccdf.datasets.io import read_jsonl
from ccdf.datasets.pipeline import build_all, run_reproducibility_audit
from ccdf.datasets.source_lock import build_source_lock, validate_source_lock
from ccdf.datasets.validation import subset_members
from ccdf.paths import find_shared_root, find_worktree_root


ARCHIVE_ROOT = find_shared_root(find_worktree_root()) / ".archives/20260711-043859/project"
pytestmark = pytest.mark.skipif(
    not (ARCHIVE_ROOT / "data/raw/gsm8k_source.jsonl").is_file(),
    reason="archived dataset source is available only in the primary repository",
)


def test_stable_ids_repeat_across_builds(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    build_all(source_root=ARCHIVE_ROOT, staging_root=first)
    build_all(source_root=ARCHIVE_ROOT, staging_root=second)
    a = read_jsonl(first / "data" / "processed" / "gsm8k" / "gsm8k_processed.jsonl")
    b = read_jsonl(second / "data" / "processed" / "gsm8k" / "gsm8k_processed.jsonl")
    assert [row["fixture_id"] for row in a[:30]] == [row["fixture_id"] for row in b[:30]]


def test_content_change_changes_gsm8k_id() -> None:
    lock = build_source_lock(ARCHIVE_ROOT)["entries"]["gsm8k"]
    raw = {"question": "One plus one?", "answer": "We add. #### 2"}
    original = gsm8k.changed_content_id(raw, 7, lock)
    changed = gsm8k.changed_content_id({**raw, "question": "One plus two?"}, 7, lock)
    assert original != changed


def test_raw_hash_mismatch_fails(tmp_path: Path) -> None:
    source = tmp_path / "source"
    shutil.copytree(ARCHIVE_ROOT / "data", source / "data")
    lock = build_source_lock(source)
    raw_path = source / "data" / "raw" / "gsm8k_source.jsonl"
    raw_path.write_text(raw_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="raw hash mismatch"):
        validate_source_lock(source, lock)


def test_nested_subsets_are_prefixes(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    build_all(source_root=ARCHIVE_ROOT, staging_root=staging)
    fixtures = read_jsonl(staging / "data" / "processed" / "qmsum" / "qmsum_processed.jsonl")
    members = subset_members(fixtures)
    assert members["n10"] == members["n30"][:10]
    assert members["n30"] == members["n100"][:30]


def test_freeze_requires_confirmation(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    project = tmp_path / "project"
    build_all(source_root=ARCHIVE_ROOT, staging_root=staging)
    with pytest.raises(PermissionError, match="confirm-freeze"):
        freeze_dataset(staging_root=staging, project_root=project)


def test_freeze_refuses_overwrite_without_flag(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    project = tmp_path / "project"
    build_all(source_root=ARCHIVE_ROOT, staging_root=staging)
    freeze_dataset(staging_root=staging, project_root=project, confirm_freeze=True)
    with pytest.raises(FileExistsError):
        freeze_dataset(staging_root=staging, project_root=project, confirm_freeze=True)


def test_reproducibility_audit_is_byte_identical(tmp_path: Path) -> None:
    result = run_reproducibility_audit(ARCHIVE_ROOT, tmp_path / "audit")
    assert result["pass"] is True
    assert all(row["byte_identical"] for row in result["compared_artifacts"])


def test_qmsum_policy_and_truncation_are_explicit(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    build_all(source_root=ARCHIVE_ROOT, staging_root=staging)
    fixture = read_jsonl(staging / "data" / "processed" / "qmsum" / "qmsum_processed.jsonl")[0]
    assert fixture["qmsum_policy"]["query_policy"] == "specific_only"
    assert "truncated" in fixture["truncation"]
    assert fixture["evaluation"]["semantic_correctness"] == "NOT_CLAIMED"


def test_source_revision_and_sha_are_required() -> None:
    lock = build_source_lock(ARCHIVE_ROOT)
    for entry in lock["entries"].values():
        assert entry["resolved_revision"]
        assert entry["raw_sha256"]
        assert len(entry["raw_sha256"]) == 64


def test_processed_lineage_mismatch_blocks_freeze(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    project = tmp_path / "project"
    build_all(source_root=ARCHIVE_ROOT, staging_root=staging)
    eval_path = staging / "data" / "eval" / "gsm8k" / "gsm8k_n10.jsonl"
    before = hash_file(eval_path)
    eval_path.write_text(eval_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert hash_file(eval_path) != before
    manifest = json.loads((staging / "frozen_subset_manifest.json").read_text(encoding="utf-8"))
    assert manifest["eval_files"]["gsm8k"]["n10"]["sha256"] == before
    with pytest.raises(ValueError, match="staged eval hash mismatch"):
        freeze_dataset(staging_root=staging, project_root=project, confirm_freeze=True)
