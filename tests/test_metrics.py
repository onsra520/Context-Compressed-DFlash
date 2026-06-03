from __future__ import annotations

from ccdf.benchmark import (
    MetricsCollector,
    SingleResult,
    compute_exact_match,
    compute_invalid_output_rate,
    compute_tau,
)


def test_exact_match_normalizes_case_and_spacing():
    assert compute_exact_match("  Final Answer ", "final answer")


def test_invalid_output_rate_detects_empty_and_non_alnum_outputs():
    assert compute_invalid_output_rate(["valid answer", "", "###"]) == 2 / 3


def test_tau_averages_acceptance_lengths():
    assert compute_tau([1, 2, 3]) == 2.0


def test_metrics_collector_summary():
    collector = MetricsCollector()
    collector.add(SingleResult("a", "a", original_tokens=100, compressed_tokens=50, acceptance_lengths=[1, 2]))
    summary = collector.summary()
    assert summary["exact_match"] == 1.0
    assert summary["invalid_output_rate"] == 0.0