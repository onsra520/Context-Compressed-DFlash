from importlib import import_module

from metrics.counters import GenerationCounter

CycleTrace = import_module("htfsd_types").CycleTrace


def test_generation_counter_acceptance_and_fallback_rates():
    counter = GenerationCounter(execution_mode="concurrent", decoding_mode="greedy")
    counter.add_cycle(drafted_candidate_tokens=4, accepted_tokens=3, fallback_tokens=0, malformed_reason=None)
    counter.add_cycle(drafted_candidate_tokens=2, accepted_tokens=0, fallback_tokens=1, malformed_reason="parse_fail")

    metrics = counter.to_metrics(total_ms=100.0, generated_tokens=4)

    assert metrics.generated_tokens == 4
    assert metrics.cycles == 2
    assert metrics.drafted_candidate_tokens == 6
    assert metrics.accepted_tokens == 3
    assert metrics.fallback_tokens == 1
    assert metrics.malformed_dflash_count == 1
    assert metrics.dflash_parse_fail_count == 1
    assert metrics.low_acceptance_rate == 0.5
    assert metrics.fallback_rate == 0.25
    assert metrics.tokens_per_second == 40.0
    assert metrics.latency_per_token_ms == 25.0
    assert metrics.execution_mode == "concurrent"
    assert metrics.decoding_mode == "greedy"


def test_generation_counter_zero_denominators_are_safe():
    counter = GenerationCounter(execution_mode="sequential", decoding_mode="greedy")
    metrics = counter.to_metrics(total_ms=0.0, generated_tokens=0)

    assert metrics.low_acceptance_rate == 0.0
    assert metrics.fallback_rate == 0.0
    assert metrics.tokens_per_second == 0.0
    assert metrics.latency_per_token_ms == 0.0


def test_cycle_trace_reject_metadata_full_match():
    trace = CycleTrace(
        cycle_index=0,
        context_tokens=5,
        dflash_parse_ok=True,
        malformed_dflash=False,
        draft_text_chars=12,
        draft_candidate_tokens=3,
        accepted_tokens=3,
        reject_position=None,
        candidate_exhausted=True,
        fallback_used=False,
        qwen_draft_ms=1.0,
        dflash_parse_ms=0.1,
        gemma_retokenize_ms=0.1,
        e2b_verify_ms=2.0,
        cycle_ms=3.2,
    )

    assert trace.reject_position is None
    assert trace.candidate_exhausted is True
