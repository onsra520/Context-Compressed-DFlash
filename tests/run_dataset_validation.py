"""Validation-only real-data fetch/build/reproducibility audit."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from ccdf.data import DatasetBuildConfig, build_datasets, fetch_sources
from ccdf.data.pipeline import COHORT_VERSION, REQUIRED_FIELDS, SOURCE_SPECS


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ARTIFACTS = ROOT / "docs/artifacts/data"
LEGACY = ROOT / ".worktrees/source-main/src/ccdf/datasets"
SEED = 42
SAMPLE_SIZE = 10


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    class DriftResponse(io.BytesIO):
        headers = {"ETag": '"drift-probe"'}

    with tempfile.TemporaryDirectory(prefix="ccdf-fetch-drift-probe-") as temporary:
        try:
            with patch("ccdf.data.pipeline.urllib.request.urlopen", return_value=DriftResponse(b"drifted source\n")):
                fetch_sources(Path(temporary))
        except ValueError as error:
            fetch_drift_probe = {"pass": "source drift" in str(error), "error": str(error)}
        else:
            fetch_drift_probe = {"pass": False, "error": "fetch unexpectedly accepted drifted bytes"}
    fetched = fetch_sources(DATA)
    first = build_datasets(DatasetBuildConfig(DATA, DATA, seed=SEED, sample_size=SAMPLE_SIZE))
    with tempfile.TemporaryDirectory(prefix="ccdf-rework-data-rerun-") as temporary:
        rerun_root = Path(temporary)
        second = build_datasets(DatasetBuildConfig(DATA, rerun_root, seed=SEED, sample_size=SAMPLE_SIZE))
        manifest_byte_match = (
            (DATA / "manifests/dataset_manifest.json").read_bytes()
            == (rerun_root / "manifests/dataset_manifest.json").read_bytes()
        )
        dataset_checks = {}
        for dataset in ("gsm8k", "qmsum"):
            a, b = first["datasets"][dataset], second["datasets"][dataset]
            dataset_checks[dataset] = {
                "row_ids_match": a["sample_row_ids"] == b["sample_row_ids"],
                "raw_hash_match": a["raw_sha256"] == b["raw_sha256"],
                "processed_hash_match": a["processed_sha256"] == b["processed_sha256"],
                "sample_hash_match": a["sample_sha256"] == b["sample_sha256"],
                "sample_count": a["sample_row_count"],
            }

    sample_schema = {}
    for dataset in ("gsm8k", "qmsum"):
        rows = _read_jsonl(DATA / first["datasets"][dataset]["sample_path"])
        sample_schema[dataset] = {
            "fields": sorted(rows[0]),
            "required_fields_present": all(REQUIRED_FIELDS.issubset(row) for row in rows),
            "split_values": sorted({row["split"] for row in rows}),
            "reference_answers_nonempty": all(bool(row["reference_answer"]) for row in rows),
        }

    legacy_source_hashes = {
        path.name: _sha256(path)
        for path in (LEGACY / "schemas.py", LEGACY / "gsm8k.py", LEGACY / "qmsum.py", LEGACY / "validation.py")
    }
    legacy_raw_hashes = {
        "gsm8k": json.loads((ROOT / ".worktrees/source-main/data/manifests/gsm8k/raw.json").read_text())["extra"]["source_lock_sha256"],
        "qmsum": json.loads((ROOT / ".worktrees/source-main/data/manifests/qmsum/raw.json").read_text())["extra"]["source_lock_sha256"],
    }
    with tempfile.TemporaryDirectory(prefix="ccdf-legacy-preprocess-") as temporary:
        legacy_root = Path(temporary)
        preprocessing_comparison = {}
        for dataset in ("gsm8k", "qmsum"):
            legacy_output = legacy_root / f"{dataset}.jsonl"
            command = [
                str(ROOT / ".venv/bin/python"), str(ROOT / "tests/legacy_preprocess_adapter.py"),
                "--dataset", dataset, "--raw", str(DATA / first["datasets"][dataset]["raw_path"]),
                "--revision", SOURCE_SPECS[dataset]["revision"], "--output", str(legacy_output),
            ]
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
            if completed.returncode:
                raise RuntimeError(f"legacy {dataset} preprocessing failed: {completed.stderr}")
            old_rows = _read_jsonl(legacy_output)
            new_rows = _read_jsonl(DATA / first["datasets"][dataset]["processed_path"])
            mismatches = [index for index, (old, new) in enumerate(zip(old_rows, new_rows)) if old != new]
            current_sample_ids = first["datasets"][dataset]["sample_row_ids"]
            legacy_prefix_ids = [row["fixture_id"] for row in old_rows[:SAMPLE_SIZE]]
            preprocessing_comparison[dataset] = {
                "command": command, "legacy_stdout": completed.stdout,
                "old_row_count": len(old_rows), "new_row_count": len(new_rows),
                "row_count_match": len(old_rows) == len(new_rows),
                "schema_match": all(set(old) == set(new) for old, new in zip(old_rows, new_rows)),
                "full_fixture_match": len(old_rows) == len(new_rows) and not mismatches,
                "mismatch_count": len(mismatches) + abs(len(old_rows) - len(new_rows)),
                "first_mismatch_indices": mismatches[:10],
                "legacy_output_sha256": _sha256(legacy_output),
                "new_output_sha256": _sha256(DATA / first["datasets"][dataset]["processed_path"]),
                "legacy_prefix_sample_ids": legacy_prefix_ids,
                "rec3_seeded_sample_ids": current_sample_ids,
                "sampling_exact_match": legacy_prefix_ids == current_sample_ids,
            }
    comparison = {
        "comparison_mode": "programmatic old/new execution on identical raw rows",
        "legacy_source_root": str(LEGACY), "legacy_source_hashes": legacy_source_hashes,
        "cohort": {
            "current_version": COHORT_VERSION,
            "status": "REC-3-versioned",
            "datasets": {
                dataset: {
                    "legacy_raw_sha256": legacy_raw_hashes[dataset],
                    "rec3_raw_sha256": first["datasets"][dataset]["raw_sha256"],
                    "same_raw_as_legacy_cohort": legacy_raw_hashes[dataset] == first["datasets"][dataset]["raw_sha256"],
                }
                for dataset in ("gsm8k", "qmsum")
            },
            "reason": "QMSum upstream test JSONL differs from the archived REC-T02A raw cohort; REC-3 pins the current upstream revision and hash.",
        },
        "preprocessing": preprocessing_comparison,
        "sampling": {
            "legacy_strategy": "source-order prefix",
            "rec3_strategy": first["sampling_strategy"],
            "versioned_difference": True,
            "deterministic_rerun_manifest_byte_match": manifest_byte_match,
        },
    }
    all_checks_pass = fetch_drift_probe["pass"] and manifest_byte_match and all(
        dataset[key]
        for dataset in dataset_checks.values()
        for key in ("row_ids_match", "raw_hash_match", "processed_hash_match", "sample_hash_match")
    ) and all(dataset["sample_count"] == SAMPLE_SIZE for dataset in dataset_checks.values()) and all(
        result["row_count_match"] and result["schema_match"] and result["full_fixture_match"]
        for result in preprocessing_comparison.values()
    ) and all(first["datasets"][name]["source_lock_pass"] for name in ("gsm8k", "qmsum"))
    payload = {
        "validation_version": "ccdf.dataset-validation.rec3.v1",
        "cohort_version": COHORT_VERSION,
        "pass": all_checks_pass,
        "seed": SEED,
        "sample_size": SAMPLE_SIZE,
        "fetched_paths": {key: str(value) for key, value in fetched.items()},
        "fetch_drift_probe": fetch_drift_probe,
        "manifest_byte_match": manifest_byte_match,
        "dataset_checks": dataset_checks,
        "sample_schema": sample_schema,
        "source_comparison": comparison,
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "dataset_validation.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (ARTIFACTS / "source_comparison.json").write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.copyfile(DATA / "manifests/dataset_manifest.json", ARTIFACTS / "dataset_manifest.json")
    shutil.copyfile(DATA / "manifests/source_fetch.json", ARTIFACTS / "source_fetch_manifest.json")
    print(json.dumps({"pass": payload["pass"], "manifest_byte_match": manifest_byte_match, "dataset_checks": dataset_checks}, sort_keys=True))
    if not payload["pass"]:
        raise SystemExit("dataset validation failed")


if __name__ == "__main__":
    main()
