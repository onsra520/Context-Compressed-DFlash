"""Timing contract descriptions."""

from __future__ import annotations


def timing_contract() -> dict[str, object]:
    return {
        "contract_version": "rec-t02b.timing.v1",
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
            "model_init_ms",
            "compressor_init_ms",
            "compression_total_ms",
            "target_prefill_ms",
            "draft_prefill_ms",
            "decode_total_ms",
            "request_e2e_ms",
        ],
    }
