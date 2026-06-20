from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis.task94_light_vs_large_compressor_controlled_comparison import (
    analyze,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _row(profile: str, *, expected: str, generated: str, compress_ms: float, ratio: float) -> dict:
    return {
        "compressor_profile": profile,
        "condition": "CC-DFlash-R2",
        "expected_answer": expected,
        "generated_text": generated,
        "t_compress_ms": compress_ms,
        "R_actual": ratio,
        "generation_time_s": 2.0,
        "tok_per_sec": 50.0,
        "tau_mean": 5.0,
        "t_prefill_ms": 100.0,
        "output_tokens": 64,
        "local_files_only": True,
        "compressor_path": f"models/{profile}",
        "resolved_compressor_path": f"/repo/models/{profile}",
        "question_preserved": True,
        "protected_suffix_preserved": True,
    }


def test_task94_analysis_summarizes_expected_deltas(tmp_path: Path) -> None:
    large_path = tmp_path / "large.jsonl"
    light_path = tmp_path / "light.jsonl"

    _write_jsonl(
        large_path,
        [
            _row("large", expected="4", generated="Final answer: 4", compress_ms=1200.0, ratio=2.5),
            _row("large", expected="5", generated="Final answer: 5", compress_ms=1000.0, ratio=2.5),
        ],
    )
    _write_jsonl(
        light_path,
        [
            _row("light", expected="4", generated="Final answer: 4", compress_ms=400.0, ratio=2.0),
            _row("light", expected="5", generated="Final answer: 7", compress_ms=500.0, ratio=2.0),
        ],
    )

    summary = analyze(large_path, light_path)

    assert summary["profiles"]["large"]["numeric_extraction_match_count"] == 2
    assert summary["profiles"]["light"]["numeric_extraction_match_count"] == 1
    assert summary["comparison"]["rows_match_expected_n10"] is False
    assert summary["comparison"]["large_over_light_t_compress_ratio"] == 2200.0 / 900.0
    assert summary["comparison"]["light_minus_large_avg_R_actual"] == -0.5
    assert summary["comparison"]["decision"]["status"] == "PASS_WITH_CAVEAT"
