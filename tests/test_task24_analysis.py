from __future__ import annotations

from pathlib import Path

from scripts.phase_1_analysis.analyze_task24_matrix import (
    compute_generation_speed_ratio,
    summarize_fixture,
    summarize_rows,
)


def test_summarize_rows_computes_means_medians_and_e2e_time():
    rows = [
        {
            "tok_per_sec": 10.0,
            "input_tokens": 20,
            "output_tokens": 5,
            "tau_mean": 2.0,
            "generation_time_s": 1.0,
            "vram_allocated_gib": 3.0,
            "vram_reserved_gib": 3.2,
            "t_compress_ms": 500.0,
            "R_actual": 2.0,
        },
        {
            "tok_per_sec": 20.0,
            "input_tokens": 30,
            "output_tokens": 15,
            "tau_mean": 4.0,
            "generation_time_s": 2.0,
            "vram_allocated_gib": 3.5,
            "vram_reserved_gib": 3.6,
            "t_compress_ms": 1500.0,
            "R_actual": 4.0,
        },
    ]

    summary = summarize_rows("CC-LLM-R2", rows)

    assert summary["rows"] == 2
    assert summary["avg_tok_s"] == 15.0
    assert summary["median_tok_s"] == 15.0
    assert summary["avg_input_tokens"] == 25.0
    assert summary["avg_output_tokens"] == 10.0
    assert summary["avg_tau_mean"] == 3.0
    assert summary["avg_t_compress_ms"] == 1000.0
    assert summary["avg_r_actual"] == 3.0
    assert summary["max_vram_allocated"] == 3.5
    assert summary["max_vram_reserved"] == 3.6
    assert summary["avg_e2e_time_s"] == 2.5


def test_compute_generation_speed_ratio_divides_condition_averages():
    ratio = compute_generation_speed_ratio(
        {"avg_tok_s": 30.0},
        {"avg_tok_s": 20.0},
    )

    assert ratio == 1.5


def test_summarize_fixture_reports_length_and_domains(tmp_path: Path):
    fixture = tmp_path / "fixture.jsonl"
    fixture.write_text(
        '\n'.join(
            [
                '{"id":"a","domain":"finance","context":"ctx","question":"q","expected_answer":"a","evidence":"a","noise_type":"mixed","approximate_context_words":120}',
                '{"id":"b","domain":"ops","context":"ctx","question":"q","expected_answer":"a","evidence":"a","noise_type":"mixed","approximate_context_words":180}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = summarize_fixture(fixture)

    assert summary["count"] == 2
    assert summary["avg_approximate_context_words"] == 150.0
    assert summary["min_approximate_context_words"] == 120
    assert summary["max_approximate_context_words"] == 180
    assert summary["domains"] == ["finance", "ops"]
