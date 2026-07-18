from ccdf.schemas import DFlashStats, GenerationOutput, MemoryStats, TimingBreakdown


def test_decode_scope_excludes_the_prefill_seed_token():
    result = GenerationOutput(
        condition="dflash",
        text="",
        prompt_tokens=10,
        output_tokens=20,
        generated_token_ids=list(range(20)),
        stop_reason="max_new_tokens",
        timing=TimingBreakdown(decode_total_ms=200.0, steady_state_decode_ms=100.0, generation_total_ms=300.0, warm_request_ms=400.0),
        memory=MemoryStats(),
        dflash=DFlashStats(acceptance_lengths=[5, 5, 5, 4]),
    )
    assert result.decode_tokens == 19
    assert result.decode_tok_s == 95.0
    assert result.steady_state_decode_tok_s == 190.0
