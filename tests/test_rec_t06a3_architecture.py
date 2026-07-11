import inspect

import ccdf.dflash.generate as dflash_generate
import ccdf.inference.baseline_ar as baseline_ar
import ccdf.inference.oracle as oracle


def test_oracle_is_not_reachable_from_production_modules() -> None:
    baseline_source = inspect.getsource(baseline_ar)
    dflash_source = inspect.getsource(dflash_generate)
    assert "FullPrefixTargetOracle" not in baseline_source
    assert "FullPrefixTargetOracle" not in dflash_source
    assert "target_execution" not in baseline_source
    assert "target_execution" not in dflash_source
    assert "class FullPrefixTargetOracle" in inspect.getsource(oracle)


def test_dflash_uses_block_verifier_not_per_proposal_target_calls() -> None:
    source = inspect.getsource(dflash_generate)
    assert "verifier.verify(" in source
    assert "state.next_token" not in source
    assert "target_single_token_fallback_calls" in source
