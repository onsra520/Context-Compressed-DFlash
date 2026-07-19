"""Canonical sample contract for manifest-driven Stage 3 benchmarks."""

from __future__ import annotations

from collections import Counter
from typing import Any

SAMPLE_SCHEMA = "ccdf.dataset-sample.v1"
REQUIRED_FIELDS = {
    "schema",
    "sample_id",
    "dataset",
    "split",
    "source_id",
    "source_index",
    "task_type",
    "question",
    "query",
    "context",
    "reference",
    "metadata",
    "source_fingerprint",
    "prompt_version",
    "prompt",
}


def validate_sample(row: dict[str, Any]) -> None:
    missing = REQUIRED_FIELDS - set(row)
    if missing:
        raise ValueError(f"canonical sample missing fields: {sorted(missing)}")
    if row["schema"] != SAMPLE_SCHEMA:
        raise ValueError(f"unexpected canonical sample schema: {row['schema']}")
    if row["dataset"] not in {"gsm8k", "qmsum"}:
        raise ValueError(f"unsupported dataset: {row['dataset']}")
    if row["split"] != "test":
        raise ValueError(f"unsupported split: {row['split']}")
    for field in ("sample_id", "task_type", "reference", "source_fingerprint", "prompt_version", "prompt"):
        if not isinstance(row[field], str) or not row[field].strip():
            raise ValueError(f"canonical sample has empty {field}")
    if len(row["source_fingerprint"]) != 64:
        raise ValueError("source_fingerprint must be a SHA-256 hex digest")
    if not isinstance(row["metadata"], dict):
        raise ValueError("canonical sample metadata must be an object")
    if row["dataset"] == "gsm8k":
        if not isinstance(row["question"], str) or not row["question"].strip():
            raise ValueError("GSM8K sample requires a question")
        if row["query"] is not None or row["context"] != "":
            raise ValueError("GSM8K query must be null and context must be empty")
        if not isinstance(row["source_index"], int) or row["source_id"] is not None:
            raise ValueError("GSM8K source identity must use source_index")
    else:
        if not isinstance(row["query"], str) or not row["query"].strip():
            raise ValueError("QMSum sample requires a query")
        if not isinstance(row["context"], str) or not row["context"].strip():
            raise ValueError("QMSum sample requires a transcript context")
        if row["question"] is not None:
            raise ValueError("QMSum question must be null")
        if not isinstance(row["source_index"], int) or not str(row["source_id"]).strip():
            raise ValueError("QMSum source identity requires meeting ID and index")
        selection = row["metadata"].get("context_selection")
        required = {
            "policy", "budget_tokens", "full_transcript_token_count", "full_chunk_count",
            "selected_chunk_ids", "selected_source_ranges", "selected_context_token_count",
            "selection_keep_rate", "query_term_coverage", "entity_coverage", "number_coverage",
            "selected_context_sha256", "reference_overlap_diagnostic",
        }
        if not isinstance(selection, dict) or required - set(selection):
            raise ValueError("QMSum sample requires explicit query-aware context-selection accounting")
        if selection["policy"] != "query_aware_budgeted":
            raise ValueError("QMSum context-selection policy mismatch")


def validate_samples(
    rows: list[dict[str, Any]],
    *,
    expected_dataset: str,
    expected_split: str,
    expected_count: int,
) -> None:
    if len(rows) != expected_count:
        raise ValueError(f"expected {expected_count} samples, found {len(rows)}")
    for row in rows:
        validate_sample(row)
        if row["dataset"] != expected_dataset or row["split"] != expected_split:
            raise ValueError("dataset/split mismatch in canonical sample set")
    ids = [str(row["sample_id"]) for row in rows]
    duplicates = sorted(key for key, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate canonical sample IDs: {duplicates}")
