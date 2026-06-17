from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_1_system_build_and_evaluation.analysis.t63_n30_stability import analyze_paths


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _row(prompt_id: int, *, expected: str, generated: str, output_tokens: int = 64) -> dict:
    return {
        "condition": "LLMLingua-AR-R2",
        "prompt_id": prompt_id,
        "benchmark_prompt_index": prompt_id,
        "dataset_id": f"gsm8k_{prompt_id}",
        "expected_answer": expected,
        "generated_text": generated,
        "input_tokens": 96,
        "output_tokens": output_tokens,
        "max_new_tokens": 256,
        "generation_time_s": 2.0,
        "tok_per_sec": 32.0,
        "tokens_per_second": 32.0,
        "t_compress_ms": 500.0,
        "R_actual": 2.0,
        "actual_compression_ratio": 2.0,
        "compression_ratio": 2.0,
        "original_input_tokens": 100,
        "compressed_input_tokens": 50,
        "keep_rate": 0.5,
        "protected_suffix_preserved": True,
        "question_preserved": True,
        "final_prompt_tail_preview": "End with exactly one line: Final answer: <number>",
    }


def test_analyze_paths_compares_n10_and_n30_quality_stability(tmp_path: Path):
    task60 = tmp_path / "task60.jsonl"
    task63 = tmp_path / "task63.jsonl"

    task60_rows = [
        _row(i, expected=str(i), generated=f"Final answer: {i}")
        for i in range(1, 9)
    ] + [
        _row(9, expected="9", generated="Final answer: 90"),
        _row(10, expected="10", generated="Working", output_tokens=256),
    ]
    task63_rows = [
        _row(i, expected=str(i), generated=f"Final answer: {i}")
        for i in range(1, 25)
    ] + [
        _row(i, expected=str(i), generated=f"Final answer: {i}0")
        for i in range(25, 31)
    ]
    _write_jsonl(task60, task60_rows)
    _write_jsonl(task63, task63_rows)

    summary = analyze_paths(
        task60_paths={"LLMLingua-AR-R2": task60},
        task63_paths={"LLMLingua-AR-R2": task63},
    )

    condition = summary["comparisons"]["LLMLingua-AR-R2"]
    task63_summary = summary["artifacts"]["task63_n30"]["LLMLingua-AR-R2"]
    assert task63_summary["rows"] == 30
    assert task63_summary["numeric_extraction_match_count"] == 24
    assert task63_summary["numeric_extraction_rate"] == 0.8
    assert condition["task60_numeric_extraction_rate"] == 0.8
    assert condition["numeric_extraction_rate_delta"] == 0.0
    assert condition["stability_classification"] == "STABLE"
