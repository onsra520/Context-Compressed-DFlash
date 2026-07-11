"""Contract validation helpers."""

from __future__ import annotations

from typing import Any

from ccdf.benchmark.schemas import validate_row
from ccdf.metrics.dflash import validate_dflash_invariants


def validate_rows(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        validate_row(row)
        validate_dflash_invariants(row)
