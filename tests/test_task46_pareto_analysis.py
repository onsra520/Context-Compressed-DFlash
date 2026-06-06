from __future__ import annotations

import json
from pathlib import Path

from scripts.analyze_task46_pareto import (
    analyze_task46,
    dominates,
    e2e_latency_s,
    write_summary,
)


def _row(condition: str, idx: int, *, tok_s: float, gen_s: float, compress_ms: float | None = None) -> dict:
    row = {
        "condition": condition,
        "prompt_id": idx,
        "input_tokens": 100,
        "output_tokens": 10,
        "generation_time_s": gen_s,
        "tok_per_sec": tok_s,
        "acceptance_lengths": [] if "AR" in condition else [2, 3],
        "tau_mean": 0.0 if "AR" in condition else 2.5,
        "t_prefill_ms": 5.0,
        "vram_allocated_gib": 2.0,
        "vram_reserved_gib": 3.0,
        "generated_text": "Answer: 4",
    }
    if compress_ms is not None:
        row.update({"t_compress_ms": compress_ms, "R_actual": 2.0})
    return row


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _artifact_summary(path: Path, condition: str, exact: int, normalized_only: int) -> dict:
    return {
        "path": str(path),
        "quality": {
            "exact_containment_count": exact,
            "normalized_containment_count": normalized_only,
            "extracted_answer_match_count": exact,
            "no_containment_count": max(0, 2 - exact - normalized_only),
            "not_evaluable_count": 0,
            "generated_text_present": 2,
            "exact_containment_rate": exact / 2,
            "extracted_answer_match_rate": exact / 2,
        },
        "metrics": {},
        "status": "PASS",
        "row_count": 2,
        "schema_issues": [],
        "schema_warnings": [],
        "protocol": {"status": "PASS" if condition.startswith("CC") or "LLMLingua" in condition else "LEGACY_ACCEPTED"},
    }


def test_e2e_latency_includes_compression_cost():
    assert e2e_latency_s({"generation_time_s": 2.0}) == 2.0
    assert e2e_latency_s({"generation_time_s": 2.0, "t_compress_ms": 750.0}) == 2.75


def test_dominates_handles_higher_and_lower_metrics():
    fast = {
        "avg_tokens_per_second": 4.0,
        "max_vram_reserved_gib": 2.0,
        "quality": {"normalized_containment_rate": 0.5},
    }
    slow = {
        "avg_tokens_per_second": 2.0,
        "max_vram_reserved_gib": 3.0,
        "quality": {"normalized_containment_rate": 0.5},
    }

    assert dominates(fast, slow, ["avg_tokens_per_second", "quality_normalized_rate", "max_vram_reserved_gib"])
    assert not dominates(slow, fast, ["avg_tokens_per_second", "quality_normalized_rate", "max_vram_reserved_gib"])


def test_analyze_task46_reads_audit_and_artifacts(tmp_path: Path):
    paths = {
        "Baseline-AR": tmp_path / "baseline.jsonl",
        "DFlash-R1": tmp_path / "dflash.jsonl",
        "LLMLingua-AR-R2": tmp_path / "ar.jsonl",
        "CC-LLM-R2": tmp_path / "cc.jsonl",
    }
    _write_jsonl(paths["Baseline-AR"], [_row("Baseline-AR", 1, tok_s=1, gen_s=10), _row("Baseline-AR", 2, tok_s=1, gen_s=10)])
    _write_jsonl(paths["DFlash-R1"], [_row("DFlash-R1", 1, tok_s=5, gen_s=2), _row("DFlash-R1", 2, tok_s=5, gen_s=2)])
    _write_jsonl(
        paths["LLMLingua-AR-R2"],
        [_row("LLMLingua-AR-R2", 1, tok_s=1, gen_s=10, compress_ms=1000), _row("LLMLingua-AR-R2", 2, tok_s=1, gen_s=10, compress_ms=1000)],
    )
    _write_jsonl(
        paths["CC-LLM-R2"],
        [_row("CC-LLM-R2", 1, tok_s=4, gen_s=2, compress_ms=1000), _row("CC-LLM-R2", 2, tok_s=4, gen_s=2, compress_ms=1000)],
    )
    audit = {
        "status": "PASS",
        "artifacts": {
            condition: _artifact_summary(path, condition, exact=1, normalized_only=0)
            for condition, path in paths.items()
        },
    }
    audit_path = tmp_path / "audit.json"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")

    summary = analyze_task46(audit_path)

    assert summary["status"] == "PASS"
    assert set(summary["conditions"]) == set(paths)
    assert summary["conditions"]["CC-LLM-R2"]["avg_e2e_latency_s"] == 3.0
    assert summary["comparisons"]["CC-LLM-R2_vs_DFlash-R1"]["decode_throughput_ratio"] == 0.8
    assert "decode_only_front" in summary["pareto"]
    assert "e2e_with_compression_cost_front" in summary["pareto"]

    output = tmp_path / "summary.json"
    write_summary(summary, output)
    assert json.loads(output.read_text())["status"] == "PASS"
