#!/usr/bin/env python3
"""Assemble and hash the bounded quality-repair review archive."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import tarfile


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "docs/reviews/10-quality-repair-gsm8k-qmsum-n10"
ARCHIVE = PACK.with_suffix(".tar.gz")


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> int:
    for name in ("QUALITY-REPAIR-MAP.md", "QMSUM-CONTEXT-POLICY.md", "CHANGE-LEDGER.md", "final-report.md"):
        copy_file(ROOT / "docs/quality-repair" / name, PACK / "quality-repair-docs" / name)
    copy_file(ROOT / "docs/quality-repair/final-report.md", PACK / "final-report.md")
    copy_file(ROOT / "data/eval/gsm8k/gsm8k_n10.jsonl", PACK / "gsm8k/samples.jsonl")
    copy_file(ROOT / "data/eval/qmsum/qmsum_n10.jsonl", PACK / "qmsum/samples.jsonl")
    for name in ("dataset_smoke_selection.json", "dataset_manifest.json", "stage3_n10_selection.json"):
        copy_file(ROOT / "data/manifests" / name, PACK / "dataset" / name)
    copy_file(
        ROOT / "docs/reviews/9-stage2-freeze-to-qmsum-n10-audit/canonical/metrics/stage3-guard-audit.json",
        PACK / "canonical/stage3-guard-audit.json",
    )
    copy_file(ROOT / "config.yml", PACK / "config/config.yml")
    copy_file(ROOT / "pyproject.toml", PACK / "config/pyproject.toml")

    sources = [
        "config.yml",
        "src/ccdf/compression/fact_validation.py",
        "src/ccdf/compression/safeguard.py",
        "src/ccdf/compression/llmlingua.py",
        "src/ccdf/datasets/qmsum_context.py",
        "src/ccdf/datasets/pipeline.py",
        "src/ccdf/datasets/schema.py",
        "src/ccdf/config/validation.py",
        "src/ccdf/benchmark/four_condition/cli.py",
        "src/ccdf/benchmark/four_condition/manifest.py",
        "src/ccdf/benchmark/four_condition/runner.py",
        "src/ccdf/benchmark/four_condition/schema.py",
        "src/ccdf/benchmark/four_condition/audit.py",
        "scripts/build_stage3_datasets.py",
        "scripts/build_quality_repair_targeted.py",
        "scripts/run_quality_repair_workload.sh",
        "scripts/package_quality_repair.py",
        "scripts/validate_quality_repair.py",
        "tests/test_compression_safeguard.py",
        "tests/test_dataset_pipeline.py",
        "tests/test_four_condition_protocol.py",
        "tests/test_quality_repair.py",
    ]
    for relative in sources:
        copy_file(ROOT / relative, PACK / "source" / relative)

    manifest_rows = []
    for path in sorted(PACK.rglob("*")):
        if path.is_file() and path.name not in {"package-manifest.sha256"}:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest_rows.append(f"{digest}  {path.relative_to(PACK)}")
    (PACK / "package-manifest.sha256").write_text("\n".join(manifest_rows) + "\n", encoding="utf-8")

    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with tarfile.open(ARCHIVE, "w:gz") as handle:
        handle.add(PACK, arcname=PACK.name)
    print(f"{ARCHIVE} {hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
