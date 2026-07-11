"""Validation checks for Rec-T02A datasets."""

from __future__ import annotations

from typing import Any

from ccdf.datasets.schemas import validate_fixture

SUBSET_SIZES = {"n10": 10, "n30": 30, "n100": 100}


def validate_unique_ids(fixtures: list[dict[str, Any]]) -> None:
    ids = [row["fixture_id"] for row in fixtures]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate fixture ID detected")


def subset_members(fixtures: list[dict[str, Any]]) -> dict[str, list[str]]:
    if len(fixtures) < max(SUBSET_SIZES.values()):
        raise ValueError(f"need at least {max(SUBSET_SIZES.values())} fixtures")
    return {name: [row["fixture_id"] for row in fixtures[:size]] for name, size in SUBSET_SIZES.items()}


def validate_nested_subsets(members: dict[str, list[str]]) -> None:
    if members["n10"] != members["n30"][:10]:
        raise ValueError("n10 is not the first 10 rows of n30")
    if members["n30"] != members["n100"][:30]:
        raise ValueError("n30 is not the first 30 rows of n100")


def validate_fixtures(fixtures: list[dict[str, Any]]) -> None:
    for fixture in fixtures:
        validate_fixture(fixture)
    validate_unique_ids(fixtures)
    validate_nested_subsets(subset_members(fixtures))
