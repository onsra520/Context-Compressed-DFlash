#!/usr/bin/env python3
"""Create/move CC-DFlash worktrees using rec-<id>-<status> names."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def run(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True)


def normalize_id(value: str) -> str:
    value = value.strip().lower().removeprefix("rec-")
    if not value or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for ch in value):
        raise ValueError("id may contain only letters, numbers, dot and dash")
    return value


def path_for(root: Path, task_id: str, status: str) -> Path:
    return root / ".worktrees" / f"rec-{normalize_id(task_id)}-{status}"


def create(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    target = path_for(root, args.id, "ongoing")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(target)
    command = ["worktree", "add"]
    if args.new_branch:
        command += ["-b", args.new_branch]
    command += [str(target), args.ref]
    run(root, *command)
    print(target)
    print(f"Shared checkpoints: {root / 'models'}")
    print("The @shared model paths in configs/reconstruction.yml resolve to this root.")


def close(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    source = path_for(root, args.id, "ongoing")
    target = path_for(root, args.id, "closed")
    if not source.exists():
        raise FileNotFoundError(source)
    if target.exists():
        raise FileExistsError(target)
    run(root, "worktree", "move", str(source), str(target))
    print(target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="primary CC-DFlash repository root")
    sub = parser.add_subparsers(dest="command", required=True)
    p_create = sub.add_parser("create")
    p_create.add_argument("--id", required=True)
    p_create.add_argument("--ref", default="HEAD")
    p_create.add_argument("--new-branch")
    p_create.set_defaults(func=create)
    p_close = sub.add_parser("close")
    p_close.add_argument("--id", required=True)
    p_close.set_defaults(func=close)
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
