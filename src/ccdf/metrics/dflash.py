"""DFlash structural/accounting invariants and aggregation."""

from __future__ import annotations

from statistics import mean
from typing import Any


def _is_structural_v2(row: dict[str, Any]) -> bool:
    return any(
        key in row
        for key in (
            "target_seed_tokens",
            "target_block_verification_calls",
            "emitted_acceptance_lengths",
            "structural_audit",
        )
    )


def validate_dflash_invariants(row: dict[str, Any]) -> None:
    """Validate Rec-T06A3 structural rows or historical Rec-T05 rows.

    Historical artifacts are retained for audit and use the old convention
    where every verification contributes one correction token. New production
    rows use explicit seed/category/forward counters.
    """

    if not _is_structural_v2(row):
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
        return

    calls = int(row.get("target_block_verification_calls", row.get("verification_calls", 0)))
    verification_calls = int(row.get("verification_calls", calls))
    emitted = list(row.get("emitted_acceptance_lengths", row.get("acceptance_lengths", [])))
    raw = list(row.get("raw_acceptance_lengths", emitted))
    seed = int(row.get("target_seed_tokens", 0))
    output_tokens = int(row.get("output_tokens", seed + sum(emitted)))

    if verification_calls != calls:
        raise ValueError("verification_calls must equal target_block_verification_calls")
    if calls != len(emitted):
        raise ValueError("one emitted acceptance entry is required per block verification")
    if len(raw) != len(emitted):
        raise ValueError("raw/emitted acceptance list length mismatch")
    if any(e < 1 or e > r for e, r in zip(emitted, raw)):
        raise ValueError("emitted acceptance length must be within raw verified advance")
    if output_tokens != seed + sum(emitted):
        raise ValueError("seed-aware emitted token accounting failed")

    accepted = int(row.get("accepted_draft_tokens", 0))
    corrections = int(row.get("correction_tokens", 0))
    bonuses = int(row.get("bonus_target_tokens", 0))
    if accepted + corrections + bonuses != sum(emitted):
        raise ValueError("emitted block-token category accounting failed")
    proposed = int(row.get("draft_tokens_proposed", 0))
    rollback = int(row.get("rollback_tokens", proposed - accepted))
    if rollback != proposed - accepted:
        raise ValueError("rollback_tokens invariant failed")
    if int(row.get("target_single_token_fallback_calls", 0)) != 0:
        raise ValueError("canonical production DFlash must not use single-token fallback")
    if int(row.get("target_hidden_refresh_calls", 0)) != 0:
        raise ValueError("canonical production DFlash must not use hidden refresh target calls")
    total = int(row.get("total_target_forward_calls", 0))
    expected_total = (
        int(row.get("target_prefill_calls", 0))
        + calls
        + int(row.get("target_single_token_fallback_calls", 0))
        + int(row.get("target_hidden_refresh_calls", 0))
    )
    if total and total != expected_total:
        raise ValueError("total target forward accounting failed")
    if any(not block.get("structural_pass", False) for block in row.get("structural_audit", [])):
        raise ValueError("structural block verification failed")


def aggregate_tau(rows: list[dict[str, Any]]) -> dict[str, float]:
    dflash_rows = [
        row
        for row in rows
        if int(row.get("target_block_verification_calls", row.get("verification_calls", 0))) > 0
    ]
    if not dflash_rows:
        return {"mean_per_row_tau": 0.0, "global_weighted_tau": 0.0}
    per_row = []
    total_calls = 0
    total_advanced = 0
    for row in dflash_rows:
        calls = int(row.get("target_block_verification_calls", row["verification_calls"]))
        lengths = row.get("emitted_acceptance_lengths", row.get("acceptance_lengths", []))
        per_row.append(sum(lengths) / calls)
        total_calls += calls
        total_advanced += sum(lengths)
    return {
        "mean_per_row_tau": mean(per_row),
        "global_weighted_tau": total_advanced / total_calls,
    }
