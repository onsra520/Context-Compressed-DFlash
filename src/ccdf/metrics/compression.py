"""Compression metric contract placeholder for Rec-T02B."""

from __future__ import annotations


def compression_metric_contract() -> dict[str, object]:
    return {
        "contract_version": "rec-t02b.compression-metrics.v1",
        "status": "reserved_for_Rec-T04A",
        "scope_rule": "compression fields must not be synthesized by benchmark aggregation",
    }
