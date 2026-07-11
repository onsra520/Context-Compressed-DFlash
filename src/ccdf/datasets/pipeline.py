"""Dataset build and reproducibility pipeline for Rec-T02A."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Any

from ccdf.datasets import gsm8k, qmsum
from ccdf.datasets.hashing import hash_file
from ccdf.datasets.io import read_jsonl, write_json, write_jsonl
from ccdf.datasets.manifests import logical_path, stage_manifest, write_stage_manifest
from ccdf.datasets.schemas import dataset_schema
from ccdf.datasets.source_lock import build_source_lock, source_path, validate_source_lock
from ccdf.datasets.validation import SUBSET_SIZES, subset_members, validate_fixtures


def _copy_raw(source_root: Path, staging_root: Path, dataset: str) -> Path:
    raw_src = source_path(source_root, dataset)
    raw_dst = staging_root / "data" / "raw" / dataset / raw_src.name
    raw_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(raw_src, raw_dst)
    return raw_dst


def _write_inventory(path: Path, all_fixtures: dict[str, list[dict[str, Any]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "dataset",
        "fixture_id",
        "content_hash",
        "source_row_hash",
        "split",
        "lineage",
        "truncated",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for dataset in sorted(all_fixtures):
            for row in all_fixtures[dataset]:
                writer.writerow(
                    {
                        "dataset": dataset,
                        "fixture_id": row["fixture_id"],
                        "content_hash": row["content_hash"],
                        "source_row_hash": row["source_row_hash"],
                        "split": row["split"],
                        "lineage": str(row["lineage"]),
                        "truncated": row.get("truncation", {}).get("truncated", False),
                    }
                )


def _write_truncation_audit(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "fixture_id",
        "meeting_id",
        "query_type",
        "query_index",
        "truncated",
        "original_words",
        "retained_words",
        "boundary",
        "strategy",
        "caveat",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_all(
    *,
    source_root: Path,
    staging_root: Path,
    qmsum_query_policy: str = "specific_only",
    qmsum_max_context_words: int | None = 1500,
) -> dict[str, Any]:
    source_root = source_root.resolve()
    staging_root = staging_root.resolve()
    source_lock = build_source_lock(source_root)
    validate_source_lock(source_root, source_lock)
    write_json(staging_root / "source_lock.json", source_lock)
    write_json(staging_root / "dataset_schema.json", dataset_schema())

    all_fixtures: dict[str, list[dict[str, Any]]] = {}
    truncation_rows: list[dict[str, Any]] = []
    lineage: dict[str, Any] = {"datasets": {}}
    frozen_manifest: dict[str, Any] = {"subsets": {}, "eval_files": {}}

    raw_paths = {dataset: _copy_raw(source_root, staging_root, dataset) for dataset in ["gsm8k", "qmsum"]}
    for dataset, raw_path in raw_paths.items():
        raw_manifest = stage_manifest(
            dataset=dataset,
            stage="raw",
            input_paths=[source_path(source_root, dataset)],
            output_paths=[raw_path],
            extra={"source_lock_sha256": source_lock["entries"][dataset]["raw_sha256"]},
        )
        write_stage_manifest(staging_root, raw_manifest)

    gsm_fixtures = gsm8k.build_fixtures(read_jsonl(raw_paths["gsm8k"]), source_lock["entries"]["gsm8k"])
    qmsum_fixtures, truncation_rows = qmsum.build_fixtures(
        read_jsonl(raw_paths["qmsum"]),
        source_lock["entries"]["qmsum"],
        query_policy=qmsum_query_policy,
        max_context_words=qmsum_max_context_words,
    )
    all_fixtures = {"gsm8k": gsm_fixtures, "qmsum": qmsum_fixtures}

    for dataset, fixtures in all_fixtures.items():
        validate_fixtures(fixtures)
        processed_path = staging_root / "data" / "processed" / dataset / f"{dataset}_processed.jsonl"
        write_jsonl(processed_path, fixtures)
        processed_manifest = stage_manifest(
            dataset=dataset,
            stage="processed",
            input_paths=[raw_paths[dataset]],
            output_paths=[processed_path],
            extra={"fixture_count": len(fixtures)},
        )
        write_stage_manifest(staging_root, processed_manifest)

        members = subset_members(fixtures)
        frozen_manifest["subsets"][dataset] = members
        frozen_manifest["eval_files"][dataset] = {}
        lineage["datasets"][dataset] = {
            "source_lock": source_lock["entries"][dataset],
            "processed_sha256": hash_file(processed_path),
            "fixture_count": len(fixtures),
        }
        for subset, size in SUBSET_SIZES.items():
            eval_path = staging_root / "data" / "eval" / dataset / f"{dataset}_{subset}.jsonl"
            write_jsonl(eval_path, fixtures[:size])
            eval_manifest = stage_manifest(
                dataset=dataset,
                stage=f"eval_{subset}",
                input_paths=[processed_path],
                output_paths=[eval_path],
                extra={"subset": subset, "fixture_ids": members[subset]},
            )
            write_stage_manifest(staging_root, eval_manifest)
            frozen_manifest["eval_files"][dataset][subset] = {
                "path": logical_path(eval_path),
                "sha256": hash_file(eval_path),
                "fixture_count": size,
                "fixture_ids": members[subset],
            }

    write_json(staging_root / "dataset_lineage.json", lineage)
    write_json(staging_root / "frozen_subset_manifest.json", frozen_manifest)
    _write_inventory(staging_root / "fixture_inventory.csv", all_fixtures)
    _write_truncation_audit(staging_root / "truncation_audit.csv", truncation_rows)
    return {
        "source_lock": source_lock,
        "lineage": lineage,
        "frozen_subset_manifest": frozen_manifest,
        "fixture_counts": {dataset: len(rows) for dataset, rows in all_fixtures.items()},
    }


def run_reproducibility_audit(source_root: Path, audit_root: Path) -> dict[str, Any]:
    run_a = audit_root / "staging-a"
    run_b = audit_root / "staging-b"
    build_all(source_root=source_root, staging_root=run_a)
    build_all(source_root=source_root, staging_root=run_b)
    compared = [
        "source_lock.json",
        "dataset_schema.json",
        "dataset_lineage.json",
        "frozen_subset_manifest.json",
        "fixture_inventory.csv",
        "truncation_audit.csv",
    ]
    results: list[dict[str, Any]] = []
    for relative in compared:
        a = run_a / relative
        b = run_b / relative
        results.append(
            {
                "artifact": relative,
                "run_a_sha256": hash_file(a),
                "run_b_sha256": hash_file(b),
                "byte_identical": a.read_bytes() == b.read_bytes(),
            }
        )
    pass_audit = all(row["byte_identical"] for row in results)
    return {
        "audit_version": "rec-t02a.reproducibility.v1",
        "pass": pass_audit,
        "compared_artifacts": results,
        "staging_roots": [str(run_a), str(run_b)],
    }
