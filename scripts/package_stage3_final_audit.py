#!/usr/bin/env python3
"""Assemble and checksum the portable Stage 3 audit archive."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import tarfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "9-stage2-freeze-to-qmsum-n10-audit"
REVIEW = ROOT / "docs" / "reviews" / PACKAGE_NAME
ARCHIVE = ROOT / "docs" / "reviews" / f"{PACKAGE_NAME}.tar.gz"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy(relative: Path, destination_root: Path) -> None:
    source = ROOT / relative
    target = destination_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _source_files() -> list[Path]:
    explicit = [
        Path("config.yml"),
        Path("pyproject.toml"),
        Path("scripts/build_stage3_datasets.py"),
        Path("scripts/package_stage3_final_audit.py"),
        Path("scripts/prepare_four_condition_diagnostic_rows.py"),
        Path("scripts/run_four_condition.py"),
        Path("scripts/validate_stage3_final_audit.py"),
    ]
    roots = [
        Path("src/ccdf/benchmark/four_condition"),
        Path("src/ccdf/compression"),
        Path("src/ccdf/datasets"),
        Path("src/ccdf/evaluation"),
        Path("tests"),
    ]
    discovered = [
        path.relative_to(ROOT)
        for source_root in roots
        for path in sorted((ROOT / source_root).rglob("*.py"))
        if "__pycache__" not in path.parts
    ]
    return sorted(set(explicit + discovered), key=lambda path: path.as_posix())


def _dataset_files() -> list[Path]:
    return sorted(
        [
            *Path("data/manifests").glob("*.json"),
            *Path("data/eval/gsm8k").glob("*.jsonl"),
            *Path("data/eval/qmsum").glob("*.jsonl"),
        ],
        key=lambda path: path.as_posix(),
    )


def main() -> int:
    if not REVIEW.is_dir():
        raise FileNotFoundError(REVIEW)

    stage_docs = REVIEW / "stage3-docs"
    source_snapshot = REVIEW / "source"
    dataset_snapshot = REVIEW / "dataset-inputs"
    for directory in (stage_docs, source_snapshot, dataset_snapshot):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)

    for path in sorted((ROOT / "docs/stage3").glob("*.md")):
        shutil.copy2(path, stage_docs / path.name)
    shutil.copy2(ROOT / "docs/stage3/FINAL-N10-AUDIT.md", REVIEW / "final-report.md")
    source_files = _source_files()
    for relative in source_files:
        _copy(relative, source_snapshot)
    for relative in _dataset_files():
        _copy(relative, dataset_snapshot)

    source_manifest = REVIEW / "final" / "source-manifest.sha256"
    source_manifest.write_text(
        "".join(
            f"{_sha256(source_snapshot / relative)}  source/{relative.as_posix()}\n"
            for relative in source_files
        ),
        encoding="utf-8",
    )

    package_manifest = REVIEW / "package-manifest.sha256"
    package_files_path = REVIEW / "final" / "package-files.txt"
    payload_before_list = sorted(
        (
            path.relative_to(REVIEW)
            for path in REVIEW.rglob("*")
            if path.is_file() and path not in {package_manifest, package_files_path}
        ),
        key=lambda path: path.as_posix(),
    )
    listed = [*payload_before_list, Path("final/package-files.txt"), Path("package-manifest.sha256")]
    package_files_path.write_text(
        "".join(f"{path.as_posix()}\n" for path in listed), encoding="utf-8"
    )

    payload = sorted(
        (
            path.relative_to(REVIEW)
            for path in REVIEW.rglob("*")
            if path.is_file() and path != package_manifest
        ),
        key=lambda path: path.as_posix(),
    )
    package_manifest.write_text(
        "".join(f"{_sha256(REVIEW / path)}  {path.as_posix()}\n" for path in payload),
        encoding="utf-8",
    )

    for line in package_manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        actual = _sha256(REVIEW / relative)
        if actual != expected:
            raise RuntimeError(f"package checksum mismatch: {relative}")

    with tarfile.open(ARCHIVE, "w:gz") as archive:
        archive.add(REVIEW, arcname=PACKAGE_NAME, recursive=True)

    print(
        f"archive={ARCHIVE.relative_to(ROOT)} files={len(payload) + 1} "
        f"sha256={_sha256(ARCHIVE)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
