import pytest

from ccdf.metrics.dflash import validate_dflash_invariants


def structural_row():
    return {
        "target_seed_tokens": 1,
        "target_prefill_calls": 1,
        "target_block_verification_calls": 2,
        "verification_calls": 2,
        "target_single_token_fallback_calls": 0,
        "target_hidden_refresh_calls": 0,
        "total_target_forward_calls": 3,
        "raw_acceptance_lengths": [3, 4],
        "emitted_acceptance_lengths": [3, 2],
        "acceptance_lengths": [3, 2],
        "output_tokens": 6,
        "accepted_draft_tokens": 3,
        "correction_tokens": 1,
        "bonus_target_tokens": 1,
        "draft_tokens_proposed": 8,
        "rollback_tokens": 5,
        "structural_audit": [{"structural_pass": True}, {"structural_pass": True}],
    }


def test_seed_aware_structural_accounting() -> None:
    validate_dflash_invariants(structural_row())


def test_structural_accounting_rejects_hidden_target_calls() -> None:
    row = structural_row()
    row["target_hidden_refresh_calls"] = 1
    row["total_target_forward_calls"] = 4
    with pytest.raises(ValueError, match="hidden refresh"):
        validate_dflash_invariants(row)


def test_runtime_engine_keeps_legacy_tau_row_alias() -> None:
    """Benchmark row v1 still requires the historical tau field name."""
    from pathlib import Path

    source = Path("src/ccdf/runtime/engine.py").read_text(encoding="utf-8")
    assert '"effective_tau": result.effective_tau' in source
    assert (
        '"tau_tokens_advanced_per_verification": result.effective_tau'
        in source
    )
