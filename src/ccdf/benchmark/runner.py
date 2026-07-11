"""Synthetic benchmark runner for Rec-T02B contract evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ccdf.artifacts.writer import artifact_record, write_json, write_jsonl_atomic
from ccdf.benchmark.aggregation import aggregate_run_artifact
from ccdf.benchmark.execution import synthetic_row
from ccdf.benchmark.process_isolation import audit_process_isolation
from ccdf.benchmark.schemas import benchmark_schema
from ccdf.datasets.hashing import hash_file
from ccdf.datasets.io import read_jsonl


def _fixture(path: Path) -> dict[str, Any]:
    return read_jsonl(path)[0]


def run_synthetic_benchmark(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    gsm_path = Path("data/eval/gsm8k/gsm8k_n10.jsonl")
    qmsum_path = Path("data/eval/qmsum/qmsum_n10.jsonl")
    gsm = _fixture(gsm_path)
    qmsum = _fixture(qmsum_path)
    dataset_hashes = {"gsm8k": hash_file(gsm_path), "qmsum": hash_file(qmsum_path)}
    rows = [
        synthetic_row(
            run_id="rec-t02b-synthetic",
            dataset="gsm8k",
            fixture_id=gsm["fixture_id"],
            fixture_content_hash=gsm["content_hash"],
            reference_answer=gsm["reference_answer"],
            condition_id=condition,
            dataset_manifest_hash=dataset_hashes["gsm8k"],
        )
        for condition in ["baseline-ar", "dflash-r1"]
    ]
    rows.extend(
        synthetic_row(
            run_id="rec-t02b-synthetic",
            dataset="qmsum",
            fixture_id=qmsum["fixture_id"],
            fixture_content_hash=qmsum["content_hash"],
            reference_answer=qmsum["reference_answer"],
            condition_id=condition,
            dataset_manifest_hash=dataset_hashes["qmsum"],
        )
        for condition in ["baseline-ar", "dflash-r1"]
    )
    rows_path = output_dir / "synthetic_rows.jsonl"
    write_jsonl_atomic(rows_path, rows)
    summary = {
        "summary_version": "rec-t02b.synthetic-summary.v1",
        "row_artifact": artifact_record(rows_path),
        "benchmark_schema": benchmark_schema(),
        "datasets": dataset_hashes,
        "aggregations": {},
    }
    for dataset, dataset_hash in dataset_hashes.items():
        dataset_rows = [row for row in rows if row["dataset"] == dataset]
        dataset_path = output_dir / f"{dataset}_synthetic_rows.jsonl"
        write_jsonl_atomic(dataset_path, dataset_rows)
        config_hashes = {row["resolved_config_hash"] for row in dataset_rows}
        summary["aggregations"][dataset] = aggregate_run_artifact(
            dataset_path,
            dataset_manifest_hash=dataset_hash,
            resolved_config_hash=config_hashes,
        )
    summary["process_isolation"] = audit_process_isolation(["baseline-ar", "dflash-r1"])
    write_json(output_dir / "synthetic_summary.json", summary)
    write_json(output_dir / "process_isolation_audit.json", summary["process_isolation"])
    return summary


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="results/Rec-T02B")
    args = parser.parse_args()
    result = run_synthetic_benchmark(Path(args.output_dir))
    print(json.dumps({"rows": result["row_artifact"], "process_isolation": result["process_isolation"]["pass"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
