"""Build and independently verify the QMSum prefill deep-audit review pack."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "docs/artifacts"
STAGING = ARTIFACTS / "review-pack-qmsum-prefill-deep-audit"
ARCHIVE = ROOT / "docs/reviews/review-pack-qmsum-prefill-deep-audit.zip"

EVIDENCE_DIRECTORIES = (
    "qmsum-prefill-deep-audit",
    "qmsum-prefill-deep-audit-supplemental-efficient",
    "qmsum-prefill-deep-audit-supplemental-flash",
    "qmsum-prefill-deep-audit-supplemental-generate-none",
    "qmsum-prefill-deep-audit-supplemental-generate-ones",
    "qmsum-prefill-deep-audit-postpatch",
    "qmsum-prefill-deep-audit-postpatch-no-profile",
)

SOURCE_FILES = (
    "config.yml",
    "src/ccdf/inference/baseline.py",
    "src/ccdf/runtime/engine.py",
    "src/ccdf/protocols/orchestrator.py",
    "src/ccdf/benchmark/dataset_smoke.py",
    "src/ccdf/schemas.py",
    "tests/run_qmsum_prefill_probe.py",
    "tests/run_qmsum_prefill_deep_audit.py",
    "tests/test_prefill_runner_overhead.py",
    "tests/test_dataset_smoke_watchdog.py",
    "scripts/build_qmsum_prefill_deep_audit_review_pack.py",
)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _write_command_record(name: str, record: dict[str, object]) -> None:
    path = STAGING / "validation" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _assert_allowed(path: Path) -> None:
    relative = path.relative_to(STAGING)
    lowered_parts = {part.lower() for part in relative.parts}
    forbidden_parts = {"models", ".venv", "__pycache__", ".cache", "cache"}
    if lowered_parts & forbidden_parts:
        raise RuntimeError(f"forbidden directory in review pack: {relative}")
    if path.suffix.lower() == ".zip":
        raise RuntimeError(f"nested ZIP forbidden: {relative}")


def main() -> None:
    if STAGING.exists() or ARCHIVE.exists():
        raise FileExistsError("refusing to replace an existing review pack or archive")

    required = [ARTIFACTS / name for name in EVIDENCE_DIRECTORIES]
    required.extend(ROOT / name for name in SOURCE_FILES)
    required.extend((
        ARTIFACTS / "qmsum-runtime-timeout-diagnostic/PARTIAL_RUN_DIAGNOSTIC.md",
        ARTIFACTS / "qmsum-runtime-timeout-diagnostic/emergency-process-snapshot.json",
    ))
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"required evidence missing: {missing}")

    STAGING.mkdir(parents=True)
    evidence_root = STAGING / "evidence"
    for name in EVIDENCE_DIRECTORIES:
        shutil.copytree(ARTIFACTS / name, evidence_root / name)

    prior_root = evidence_root / "prior-guarded-runtime"
    prior_root.mkdir(parents=True)
    shutil.copy2(
        ARTIFACTS / "qmsum-runtime-timeout-diagnostic/PARTIAL_RUN_DIAGNOSTIC.md",
        prior_root,
    )
    shutil.copy2(
        ARTIFACTS / "qmsum-runtime-timeout-diagnostic/emergency-process-snapshot.json",
        prior_root,
    )

    source_root = STAGING / "source"
    for relative in SOURCE_FILES:
        destination = source_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)

    git_records = {
        "git-status.json": _run(["git", "status", "--short"]),
        "git-head.json": _run(["git", "rev-parse", "HEAD"]),
        "git-diff-check.json": _run(["git", "diff", "--check"]),
        "git-diff-relevant.json": _run([
            "git",
            "diff",
            "--",
            "src/ccdf/inference/baseline.py",
            "src/ccdf/runtime/engine.py",
            "src/ccdf/protocols/orchestrator.py",
            "src/ccdf/benchmark/dataset_smoke.py",
            "tests/test_prefill_runner_overhead.py",
            "tests/run_qmsum_prefill_probe.py",
            "tests/run_qmsum_prefill_deep_audit.py",
        ]),
    }
    for name, record in git_records.items():
        _write_command_record(name, record)

    tests = _run([
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_prefill_runner_overhead.py",
        "tests/test_dataset_smoke_watchdog.py",
        "tests/test_dataset_smoke_protocol.py",
        "tests/test_config.py",
    ])
    lint = _run([
        sys.executable,
        "-m",
        "ruff",
        "check",
        "src/ccdf/protocols/orchestrator.py",
        "src/ccdf/runtime/engine.py",
        "src/ccdf/inference/baseline.py",
        "src/ccdf/benchmark/dataset_smoke.py",
        "tests/test_prefill_runner_overhead.py",
        "tests/run_qmsum_prefill_probe.py",
        "tests/run_qmsum_prefill_deep_audit.py",
    ])
    _write_command_record("pytest.json", tests)
    _write_command_record("ruff.json", lint)
    if tests["exit_code"] != 0 or lint["exit_code"] != 0:
        raise RuntimeError("validation failed; refusing to package")

    files = sorted(
        path
        for path in STAGING.rglob("*")
        if path.is_file() and path.name != "verified-manifest.json"
    )
    for path in files:
        _assert_allowed(path)

    manifest = {
        "manifest_version": "qmsum-prefill-deep-audit.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive_policy": {
            "models_included": False,
            "large_datasets_included": False,
            "virtual_environment_included": False,
            "cache_included": False,
            "nested_zip_included": False,
        },
        "execution_policy": {
            "n10_rerun": False,
            "n10_admission": "PROHIBITED_PROJECTED_14.14_HOURS_AND_PHYSICAL_VRAM_GATE",
            "commit_or_push": False,
            "dependency_changes": False,
            "dflash_core_changes_by_this_audit": False,
        },
        "verification": {
            "status": "PASS",
            "method": "archive entry set, byte count, and SHA-256 rechecked after ZIP creation",
        },
        "files": [
            {
                "path": path.relative_to(STAGING).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _hash(path),
            }
            for path in files
        ],
    }
    manifest_path = STAGING / "verified-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in STAGING.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(STAGING).as_posix())

    failures: list[str] = []
    with zipfile.ZipFile(ARCHIVE) as archive:
        names = set(archive.namelist())
        expected = {entry["path"] for entry in manifest["files"]}
        expected.add("verified-manifest.json")
        if names != expected:
            failures.append("archive entry set differs from manifest plus manifest file")
        for entry in manifest["files"]:
            payload = archive.read(entry["path"])
            if len(payload) != entry["bytes"]:
                failures.append(f"size mismatch: {entry['path']}")
            if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
                failures.append(f"sha256 mismatch: {entry['path']}")
        if json.loads(archive.read("verified-manifest.json")) != manifest:
            failures.append("manifest payload mismatch")
    if failures:
        raise RuntimeError(f"archive verification failed: {failures}")

    sidecar = ARCHIVE.with_suffix(ARCHIVE.suffix + ".sha256")
    sidecar.write_text(f"{_hash(ARCHIVE)}  {ARCHIVE.name}\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "archive": str(ARCHIVE),
        "archive_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": _hash(ARCHIVE),
        "verified_files": len(manifest["files"]),
        "n10_rerun": False,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
