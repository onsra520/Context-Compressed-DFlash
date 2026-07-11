"""Timing contract descriptions."""

from __future__ import annotations


def timing_contract() -> dict[str, object]:
    return {
        "contract_version": "rec-t06b.timing.v2",
        "benchmark_mode": {
            "boundary_synchronization": "condition/process boundaries only",
            "per_iteration_sync": False,
            "canonical_latency": True,
        },
        "profiling_mode": {
            "deep_component_instrumentation": True,
            "canonical_latency": False,
            "required_measurement_mode": "profiling",
        },
        "fields_ms": [
            "prompt_prepare_ms",
            "compressor_init_ms",
            "compression_total_ms",
            "target_prefill_ms",
            "draft_prefill_ms",
            "decode_total_ms",
            "generation_request_e2e_ms",
            "warm_request_e2e_ms",
            "target_model_init_ms",
            "drafter_model_init_ms",
            "cold_start_e2e_ms",
        ],
        "identities": {
            "generation_request_e2e_ms": "excludes compression_total_ms",
            "warm_request_e2e_ms": "includes compression_total_ms for cc-dflash-r2",
            "cold_start_e2e_ms": "model initialization plus one complete warm request",
            "comparison_latency": "warm_request_e2e_ms",
        },
    }
