"""Restore the locked n10 cohorts from pinned raw sources without prefix truncation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from ccdf.config import load_config
from ccdf.data.pipeline import (
    BUILDER_VERSION,
    COHORT_VERSION,
    RAW_FILENAMES,
    SCHEMA_VERSION,
    SOURCE_SPECS,
    _file_hash,
    _gsm8k,
    _qmsum_rows,
    _read_jsonl,
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(_canonical(row) + "\n" for row in rows), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reference_map(path: Path, dataset: str) -> dict[tuple[int, ...], str]:
    rows = _read_jsonl(path)
    if dataset == "gsm8k":
        return {(int(row["lineage"]["upstream_row_index"]),): str(row["reference_answer"]) for row in rows}
    return {
        (int(row["lineage"]["meeting_index"]), int(row["lineage"]["query_index"])):
        str(row["reference_answer"])
        for row in rows
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument("--raw-root", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    settings = config.require("dataset_smoke")
    selection_path = Path(settings["cohorts"]["selection_manifest"])
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    expected_rows = int(settings["cohorts"]["expected_rows_per_dataset"])
    if len(selection["gsm8k"]) != expected_rows or len(selection["qmsum"]) != expected_rows:
        raise ValueError("selection manifest row count does not match config")

    raw_paths = {
        dataset: args.raw_root.resolve() / "raw" / dataset / RAW_FILENAMES[dataset]
        for dataset in ("gsm8k", "qmsum")
    }
    for dataset, path in raw_paths.items():
        actual = _file_hash(path)
        expected = SOURCE_SPECS[dataset]["expected_raw_sha256"]
        if actual != expected:
            raise ValueError(f"raw source drift for {dataset}: {actual} != {expected}")

    cohort_paths = {
        dataset: Path(settings["cohorts"][dataset]).resolve()
        for dataset in ("gsm8k", "qmsum")
    }
    previous_references = {
        dataset: _reference_map(cohort_paths[dataset], dataset)
        for dataset in ("gsm8k", "qmsum")
    }
    raw_gsm8k = _read_jsonl(raw_paths["gsm8k"])
    gsm8k_rows = []
    for selector in selection["gsm8k"]:
        index = int(selector["upstream_row_index"])
        row = _gsm8k(
            raw_gsm8k[index], index, _file_hash(raw_paths["gsm8k"]), SOURCE_SPECS["gsm8k"]["revision"]
        )
        if row["reference_answer"] != previous_references["gsm8k"][(index,)]:
            raise ValueError(f"GSM8K reference changed at source row {index}")
        gsm8k_rows.append(row)

    raw_qmsum = _read_jsonl(raw_paths["qmsum"])
    qmsum_rows = []
    for selector in selection["qmsum"]:
        meeting_index = int(selector["meeting_index"])
        query_index = int(selector["query_index"])
        candidates = _qmsum_rows(
            raw_qmsum[meeting_index], meeting_index, _file_hash(raw_paths["qmsum"]),
            SOURCE_SPECS["qmsum"]["revision"],
        )
        row = next(item for item in candidates if int(item["lineage"]["query_index"]) == query_index)
        if row["reference_answer"] != previous_references["qmsum"][(meeting_index, query_index)]:
            raise ValueError(f"QMSum reference changed at meeting/query {meeting_index}/{query_index}")
        qmsum_rows.append(row)

    _write_jsonl(cohort_paths["gsm8k"], gsm8k_rows)
    _write_jsonl(cohort_paths["qmsum"], qmsum_rows)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "builder_version": BUILDER_VERSION,
        "cohort_version": COHORT_VERSION,
        "selection_policy": selection["selection_policy"],
        "selection_manifest": str(selection_path.relative_to(config.root)),
        "selection_manifest_sha256": _sha256(selection_path),
        "seed": int(config.require("datasets.seed")),
        "sample_size": expected_rows,
        "datasets": {
            dataset: {
                "split": "test",
                "source_revision": SOURCE_SPECS[dataset]["revision"],
                "expected_raw_sha256": SOURCE_SPECS[dataset]["expected_raw_sha256"],
                "source_lock_pass": _file_hash(raw_paths[dataset]) == SOURCE_SPECS[dataset]["expected_raw_sha256"],
                "sample_path": str(cohort_paths[dataset].relative_to(config.root)),
                "sample_sha256": _sha256(cohort_paths[dataset]),
                "sample_row_count": expected_rows,
                "sample_row_ids": [row["fixture_id"] for row in (gsm8k_rows if dataset == "gsm8k" else qmsum_rows)],
                "full_context": dataset == "qmsum",
                "empty_context": dataset == "gsm8k",
            }
            for dataset in ("gsm8k", "qmsum")
        },
    }
    manifest_path = Path(settings["cohorts"]["manifest"]).resolve()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
