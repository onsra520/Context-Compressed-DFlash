from pathlib import Path

import pytest

from ccdf.paths import expand_logical_path, find_shared_root, validate_worktree_name


def test_worktree_shared_root_and_model_path(tmp_path: Path) -> None:
    primary = tmp_path / "CCDF"
    worktree = primary / ".worktrees" / "rec-6a3-ongoing"
    (worktree / "src" / "ccdf").mkdir(parents=True)
    (worktree / "pyproject.toml").write_text("[project]\nname='ccdf'\n", encoding="utf-8")
    assert find_shared_root(worktree) == primary.resolve()
    resolved = expand_logical_path(
        "@shared/models/target/model",
        worktree_root=worktree,
        shared_root=primary,
    )
    assert resolved == (primary / "models" / "target" / "model").resolve()


def test_worktree_name_contract(tmp_path: Path) -> None:
    valid = tmp_path / ".worktrees" / "rec-6a3-ongoing"
    validate_worktree_name(valid)
    validate_worktree_name(tmp_path / ".worktrees" / "rec-6a3-closed")
    with pytest.raises(ValueError):
        validate_worktree_name(tmp_path / ".worktrees" / "rec-6a3-done")
