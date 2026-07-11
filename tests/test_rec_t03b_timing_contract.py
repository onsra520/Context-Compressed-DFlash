from __future__ import annotations

from ccdf.benchmark.rec_t03b import decide_gate
from ccdf.inference.schemas import GenerationResult


def test_generation_result_timing_contract_present() -> None:
    result = GenerationResult(
        generated_text="x",
        output_token_ids=[1],
        prompt_token_count=0,
        output_token_count=1,
        stop_reason="max_new_tokens",
        target_prefill_ms=1.0,
        decode_total_ms=2.0,
        request_e2e_ms=3.0,
    )
    assert result.target_prefill_ms > 0
    assert result.decode_total_ms > 0
    assert result.request_e2e_ms > 0


def test_rec_t03b_gate_accepts_complete_workload_limited_matrix() -> None:
    rows = []
    for dataset in ["gsm8k", "qmsum"]:
        for condition in ["baseline-ar", "dflash-r1"]:
            rows.append(
                {
                    "dataset": dataset,
                    "condition": condition,
                    "rows": 10,
                    "global_weighted_tau": 2.0 if condition == "dflash-r1" else 0.0,
                }
            )
    decision = decide_gate(
        rows,
        quality={},
        performance={},
        process_records=[
            {"returncode": 0},
            {"returncode": 0},
            {"returncode": 0},
            {"returncode": 0},
        ],
        max_new_tokens=8,
    )
    assert decision["gate_decision"] == "PASS_WITH_WORKLOAD_LIMITATION"
    assert decision["opens_rec_t04a"] is True
