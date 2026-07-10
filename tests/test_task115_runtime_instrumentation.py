from pathlib import Path


def test_live_dflash_generation_reports_full_scope_and_acceptance_metrics():
    source = Path("src/ccdf/dflash/generate.py").read_text(encoding="utf-8")

    assert "generation_start = _cuda_time() if return_stats else None" in source
    assert "draft_proposal_time" in source
    assert "target_verification_time" in source
    assert "verification_call_count" in source
    assert "rejection_or_rollback_count" in source
    assert "time_per_output_token=total_generation_time / num_output_tokens" in source
