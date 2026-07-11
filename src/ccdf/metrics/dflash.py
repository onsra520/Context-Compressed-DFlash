"""DFlash metric invariants and aggregation."""

from __future__ import annotations

from statistics import mean
from typing import Any


def validate_dflash_invariants(row: dict[str, Any]) -> None:
    calls = int(row["verification_calls"])
    lengths = list(row["acceptance_lengths"])
    if calls != len(lengths):
        raise ValueError("verification_calls must equal len(acceptance_lengths)")
    tokens_advanced = sum(lengths)
    if calls:
        expected_tau = tokens_advanced / calls
        if abs(float(row["tau_tokens_advanced_per_verification"]) - expected_tau) > 1e-9:
            raise ValueError("tau mismatch")
    expected_accepted = tokens_advanced - calls if calls else 0
    if int(row["accepted_draft_tokens"]) != expected_accepted:
        raise ValueError("accepted_draft_tokens invariant failed")
    expected_rollback = int(row["draft_tokens_proposed"]) - expected_accepted
    if int(row["rollback_tokens"]) != expected_rollback:
        raise ValueError("rollback_tokens invariant failed")


def aggregate_tau(rows: list[dict[str, Any]]) -> dict[str, float]:
    dflash_rows = [row for row in rows if row["verification_calls"] > 0]
    if not dflash_rows:
        return {"mean_per_row_tau": 0.0, "global_weighted_tau": 0.0}
    per_row = [float(row["tau_tokens_advanced_per_verification"]) for row in dflash_rows]
    total_calls = sum(int(row["verification_calls"]) for row in dflash_rows)
    total_advanced = sum(sum(row["acceptance_lengths"]) for row in dflash_rows)
    return {
        "mean_per_row_tau": mean(per_row),
        "global_weighted_tau": total_advanced / total_calls,
    }
