"""Benchmark metric aggregation."""

from __future__ import annotations

import statistics
from typing import Any


def summarize(condition: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [row["metrics"] for row in rows]
    timing = [row["timing"] for row in rows]
    memory = [row["memory"] for row in rows]
    summary = {
        "condition": condition,
        "rows": len(rows),
        "mean_decode_tok_s": statistics.fmean(float(value["decode_tok_s"]) for value in metrics),
        "mean_generation_tok_s": statistics.fmean(
            float(value["generation_tok_s"]) for value in metrics
        ),
        "mean_warm_request_tok_s": statistics.fmean(
            float(value["warm_request_tok_s"]) for value in metrics
        ),
        "mean_target_prefill_ms": statistics.fmean(
            float(value["target_prefill_ms"]) for value in timing
        ),
        "mean_decode_total_ms": statistics.fmean(float(value["decode_total_ms"]) for value in timing),
        "peak_reserved_bytes": max(int(value["peak_reserved_bytes"]) for value in memory),
        "memory_gate_pass": all(value.get("gate_pass") is not False for value in memory),
    }
    if condition == "dflash":
        dflash = [row["dflash"] for row in rows]
        summary.update(
            {
                "mean_effective_tau": statistics.fmean(float(value["effective_tau"]) for value in dflash),
                "mean_draft_acceptance_rate": statistics.fmean(
                    float(value["draft_acceptance_rate"]) for value in dflash
                ),
                "mean_target_forwards_per_output_token": statistics.fmean(
                    float(value["target_forwards_per_output_token"]) for value in dflash
                ),
            }
        )
    return summary
