"""Project/worktree path discovery and logical path expansion.

CC-DFlash worktrees live below ``.worktrees/`` while large model checkpoints
remain in the primary repository root.  Runtime code must never assume that
``Path.cwd()`` is the primary checkout.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

WORKTREE_NAME_RE = re.compile(r"^rec-[a-z0-9][a-z0-9.-]*-(ongoing|closed)$", re.IGNORECASE)


def find_worktree_root(start: Path | None = None) -> Path:
    """Return the checkout/worktree root containing ``pyproject.toml`` and ``src``."""

    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "src" / "ccdf").is_dir():
            return candidate
    raise FileNotFoundError(
        f"cannot locate CC-DFlash worktree root from {current}; "
        "set CCDF_WORKTREE_ROOT explicitly"
    )


def _git_common_root(worktree_root: Path) -> Path | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(worktree_root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    common = Path(proc.stdout.strip()).resolve()
    if common.name == ".git":
        return common.parent
    # Bare repositories and unusual layouts are not assumed to own checkpoints.
    return None


def find_shared_root(worktree_root: Path | None = None) -> Path:
    """Return the primary repository root that owns ``models/``.

    Resolution order:
    1. ``CCDF_SHARED_ROOT``;
    2. Git common-dir parent (works for linked worktrees);
    3. parent of ``.worktrees/<name>``;
    4. the current worktree root.
    """

    env = os.environ.get("CCDF_SHARED_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    if worktree_root is not None:
        root = Path(worktree_root)
    elif os.environ.get("CCDF_WORKTREE_ROOT"):
        root = Path(os.environ["CCDF_WORKTREE_ROOT"])
    else:
        root = find_worktree_root()
    root = root.expanduser().resolve()
    git_root = _git_common_root(root)
    if git_root is not None:
        return git_root
    if root.parent.name == ".worktrees":
        return root.parent.parent.resolve()
    return root


def validate_worktree_name(path: Path) -> None:
    """Validate the requested ``rec-<id>-<status>`` worktree convention."""

    if path.parent.name != ".worktrees":
        raise ValueError("worktree must be a direct child of .worktrees/")
    if not WORKTREE_NAME_RE.fullmatch(path.name):
        raise ValueError(
            "worktree name must match rec-<id>-ongoing or rec-<id>-closed"
        )


def expand_logical_path(
    value: str | Path,
    *,
    worktree_root: Path,
    shared_root: Path,
    default_scope: str = "worktree",
) -> Path:
    """Expand ``@shared/`` and ``@worktree/`` paths without relying on cwd."""

    raw = os.path.expandvars(os.path.expanduser(str(value)))
    if raw.startswith("@shared/"):
        return (shared_root / raw.removeprefix("@shared/")).resolve()
    if raw == "@shared":
        return shared_root.resolve()
    if raw.startswith("@worktree/"):
        return (worktree_root / raw.removeprefix("@worktree/")).resolve()
    if raw == "@worktree":
        return worktree_root.resolve()
    path = Path(raw)
    if path.is_absolute():
        return path.resolve()
    base = shared_root if default_scope == "shared" else worktree_root
    return (base / path).resolve()


def logical_path_metadata(worktree_root: Path, shared_root: Path) -> dict[str, str | bool]:
    return {
        "worktree_root": str(worktree_root),
        "shared_root": str(shared_root),
        "is_linked_worktree": worktree_root != shared_root,
        "models_root": str((shared_root / "models").resolve()),
    }
