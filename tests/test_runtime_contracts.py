import math

from ccdf.infrastructure.determinism import configure_determinism
from ccdf.infrastructure.device import EventSpan
from ccdf.runtime.schemas import DFlashStats, GenerationOutput, MemoryStats, TimingBreakdown


def test_generation_output_metric_contract_survives_schema_move() -> None:
    output = GenerationOutput(
        condition="baseline",
        text="ok",
        prompt_tokens=3,
        output_tokens=5,
        generated_token_ids=[1, 2, 3, 4, 5],
        stop_reason="eos",
        timing=TimingBreakdown(decode_total_ms=40.0, generation_total_ms=50.0, warm_request_ms=100.0),
        memory=MemoryStats(),
    )
    payload = output.to_dict()
    assert payload["metrics"] == {
        "decode_tokens": 4,
        "decode_tok_s": 100.0,
        "generation_tok_s": 100.0,
        "warm_request_tok_s": 50.0,
        "steady_state_decode_tok_s": None,
    }


def test_dflash_derived_metrics_survive_schema_move() -> None:
    stats = DFlashStats(
        target_prefill_calls=1,
        target_verification_calls=2,
        acceptance_lengths=[3, 5],
        accepted_draft_tokens=6,
        draft_tokens_proposed=12,
    )
    assert stats.effective_tau == 4.0
    assert stats.acceptance_rate == 0.5


def test_determinism_move_preserves_math_sdpa_contract() -> None:
    state = configure_determinism(
        seed=42,
        deterministic=True,
        allow_tf32=False,
        matmul_precision="high",
        sdpa_kernel="math",
    )
    assert state["seed"] == 42
    assert state["deterministic_algorithms"] is True
    assert state["allow_tf32_effective"] is False
    assert state["sdpa_kernel_policy"] in {"math", None}


def test_disabled_event_span_reports_no_fake_timing() -> None:
    span = EventSpan(enabled=False)
    span.start()
    span.stop()
    assert span.elapsed_ms() is None
    assert math.isfinite(0.0)
