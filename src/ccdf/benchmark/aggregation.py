"""Aggregation from validated run artifacts."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from ccdf.artifacts.writer import assert_artifact_matches, read_jsonl
from ccdf.metrics.dflash import aggregate_tau, validate_dflash_invariants


def aggregate_run_artifact(
    path: Path, *, dataset_manifest_hash: str, resolved_config_hash: str | set[str]
) -> dict[str, Any]:
    assert_artifact_matches(
        path,
        dataset_manifest_hash=dataset_manifest_hash,
        resolved_config_hash=resolved_config_hash,
    )
    rows = read_jsonl(path)
    if any(not row.get("canonical", True) for row in rows):
        raise ValueError("canonical aggregation rejects smoke/noncanonical rows")
    for row in rows:
        validate_dflash_invariants(row)
    by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_condition[row["condition"]["condition_id"]].append(row)
    summaries: dict[str, Any] = {}
    for condition_id, condition_rows in sorted(by_condition.items()):
        summaries[condition_id] = {
            "row_count": len(condition_rows),
            "success_count": sum(1 for row in condition_rows if row["success"]),
            "mean_request_e2e_ms": sum(row["request_e2e_ms"] for row in condition_rows)
            / len(condition_rows),
            **aggregate_tau(condition_rows),
        }
    return {"row_count": len(rows), "conditions": summaries}
