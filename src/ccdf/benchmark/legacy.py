"""Explicit boundary for historical benchmark runners."""

from __future__ import annotations


LEGACY_TASKS = {"Rec-T03B", "Rec-T04B"}


def legacy_canonical_status(*, task_id: str, requested_canonical: bool) -> tuple[bool, str]:
    if task_id in LEGACY_TASKS:
        return False, "legacy benchmark path is always noncanonical"
    return bool(requested_canonical), "requested canonical status"
