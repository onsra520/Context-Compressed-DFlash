from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis.breakeven_with_quality import (
    assign_carry_forward_label,
    analyze_condition,
    analyze_phase2,
    containment_per_second,
    e2e_time_s,
)


def _row(**overrides):
    row = {
        "condition": "CC-LLM-R2",
        "tok_per_sec": 10.0,
        "generation_time_s": 2.0,
        "tau_mean": 3.0,
        "t_compress_ms": 500.0,
        "R_actual": 2.0,
        "vram_allocated_gib": 3.0,
        "vram_reserved_gib": 3.2,
    }
    row.update(overrides)
    return row


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _quality_summary(*summaries: dict) -> dict:
    return {"artifacts": [{"summary": summary} for summary in summaries]}


def test_e2e_time_uses_compression_when_present():
    assert e2e_time_s({"generation_time_s": 2.0}) == 2.0
    assert e2e_time_s({"generation_time_s": 2.0, "t_compress_ms": 750.0}) == 2.75


def test_analyze_condition_merges_quality_summary_and_gated_metrics(tmp_path: Path):
    path = tmp_path / "cc.jsonl"
    _write_jsonl(
        path,
        [
            _row(tok_per_sec=8.0, generation_time_s=1.0, t_compress_ms=500.0),
            _row(tok_per_sec=12.0, generation_time_s=3.0, t_compress_ms=1500.0),
        ],
    )
    quality = {
        "rows": 2,
        "exact_containment_count": 1,
        "exact_rate": 0.5,
        "normalized_containment_count": 1,
        "normalized_rate": 0.5,
        "no_containment_count": 1,
    }

    summary = analyze_condition("CC-LLM-R2", path, quality)

    assert summary["rows"] == 2
    assert summary["avg_tok_per_sec"] == 10.0
    assert summary["median_tok_per_sec"] == 10.0
    assert summary["avg_generation_time_s"] == 2.0
    assert summary["avg_e2e_time_s"] == 3.0
    assert summary["avg_t_compress_ms"] == 1000.0
    assert summary["avg_R_actual"] == 2.0
    assert summary["normalized_containment_count"] == 1
    assert summary["quality_gated_avg_e2e_time_s"] == 1.5
    assert summary["normalized_containment_per_second"] == 1 / 6.0


def test_containment_per_second_divides_normalized_matches_by_total_e2e():
    assert containment_per_second(normalized_count=3, total_e2e_time_s=6.0) == 0.5
    assert containment_per_second(normalized_count=3, total_e2e_time_s=0.0) == 0.0


def test_assign_carry_forward_label_is_evidence_bound():
    dflash = {"condition": "DFlash-R1", "normalized_rate": 0.5, "avg_e2e_time_s": 1.0, "max_vram_allocated": 3.5}
    ar_r2 = {"condition": "LLMLingua-AR-R2", "normalized_rate": 0.5, "avg_e2e_time_s": 2.0, "max_vram_allocated": 2.5}
    ar_r3 = {"condition": "LLMLingua-AR-R3", "normalized_rate": 0.17, "avg_e2e_time_s": 2.1, "max_vram_allocated": 2.5}
    cc_r2 = {"condition": "CC-LLM-R2", "normalized_rate": 0.33, "avg_e2e_time_s": 2.0, "max_vram_allocated": 3.5}

    assert assign_carry_forward_label(dflash, dflash)["label"] == "KEEP_BASELINE"
    assert assign_carry_forward_label(ar_r2, dflash)["label"] == "KEEP_LOW_VRAM_BASELINE"
    assert assign_carry_forward_label(ar_r3, dflash)["label"] == "DEPRIORITIZE_FOR_NOW"
    assert assign_carry_forward_label(cc_r2, dflash)["label"] == "WATCHLIST"


def test_analyze_phase2_reads_artifacts_and_quality_summary(tmp_path: Path):
    dflash = tmp_path / "dflash.jsonl"
    cc = tmp_path / "cc.jsonl"
    _write_jsonl(dflash, [_row(condition="DFlash-R1", t_compress_ms=None)])
    _write_jsonl(cc, [_row(condition="CC-LLM-R2")])
    quality_path = tmp_path / "quality.json"
    quality_path.write_text(
        json.dumps(
            _quality_summary(
                {
                    "condition": "DFlash-R1",
                    "rows": 1,
                    "exact_containment_count": 1,
                    "exact_rate": 1.0,
                    "normalized_containment_count": 1,
                    "normalized_rate": 1.0,
                    "no_containment_count": 0,
                },
                {
                    "condition": "CC-LLM-R2",
                    "rows": 1,
                    "exact_containment_count": 0,
                    "exact_rate": 0.0,
                    "normalized_containment_count": 0,
                    "normalized_rate": 0.0,
                    "no_containment_count": 1,
                },
            )
        ),
        encoding="utf-8",
    )

    analysis = analyze_phase2({"DFlash-R1": dflash, "CC-LLM-R2": cc}, quality_path)

    assert set(analysis["conditions"]) == {"DFlash-R1", "CC-LLM-R2"}
    assert analysis["conditions"]["DFlash-R1"]["carry_forward"]["label"] == "KEEP_BASELINE"
    assert analysis["conditions"]["CC-LLM-R2"]["normalized_containment_count"] == 0
