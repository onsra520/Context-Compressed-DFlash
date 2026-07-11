"""Schema constants and validation for reconstructed dataset fixtures."""

from __future__ import annotations

from typing import Any

DATASET_SCHEMA_VERSION = "rec-t02a.dataset.v1"
BUILDER_VERSION = "rec-t02a.builder.v1"
SOURCE_ARCHIVE_ID = "20260711-043859"
SOURCE_ARCHIVE_COMMIT = "d638c3496131ba6bae0f2c6e89676e37fee7155a"
SOURCE_FETCHED_AT = "2026-07-11T04:38:59Z"

REQUIRED_FIXTURE_FIELDS = {
    "fixture_id",
    "dataset",
    "split",
    "content_hash",
    "source_row_hash",
    "question",
    "reference_answer",
    "prompt_parts",
    "prompt",
    "lineage",
}


def dataset_schema() -> dict[str, Any]:
    return {
        "schema_version": DATASET_SCHEMA_VERSION,
        "fixture_required_fields": sorted(REQUIRED_FIXTURE_FIELDS),
        "stable_identity": {
            "gsm8k": ["split", "upstream_row_index", "content_hash_prefix"],
            "qmsum": ["split", "meeting_id", "query_type", "query_index", "content_hash_prefix"],
        },
        "qmsum_query_policy_allowed": [
            "specific_only",
            "general_only",
            "specific_and_general",
        ],
        "subsets": {"n10": 10, "n30": 30, "n100": 100},
    }


def validate_fixture(row: dict[str, Any]) -> None:
    missing = REQUIRED_FIXTURE_FIELDS.difference(row)
    if missing:
        raise ValueError(f"fixture missing required fields: {sorted(missing)}")
    if row["content_hash"][:8] not in row["fixture_id"]:
        raise ValueError(f"fixture id does not include content hash prefix: {row['fixture_id']}")
    if row["prompt_parts"]["question"] != row["question"]:
        raise ValueError(f"prompt question mismatch for {row['fixture_id']}")
    if row["reference_answer"] == "":
        raise ValueError(f"empty reference answer for {row['fixture_id']}")
