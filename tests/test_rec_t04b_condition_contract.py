from __future__ import annotations

from ccdf.benchmark.execution import resolved_condition


def test_cc_dflash_condition_uses_dflash_and_compressor() -> None:
    condition = resolved_condition("cc-dflash-r2", "manifest")
    assert condition["generation_mode"] == "dflash"
    assert condition["draft_model_lock_id"] is not None
    assert condition["compressor_model_lock_id"] == "llmlingua2:meetingbank-local"
