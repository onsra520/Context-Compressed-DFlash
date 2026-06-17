from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_1_analysis.analyze_task60_mnt256_calibration import analyze_paths


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _row(
    *,
    condition: str,
    prompt_id: int,
    expected_answer: str,
    generated_text: str,
    max_new_tokens: int,
    output_tokens: int,
) -> dict:
    instruction = "End with exactly one line:\nFinal answer: <number>"
    final_preview = f"Compressed context. Question? {instruction}"
    return {
        "condition": condition,
        "prompt_id": prompt_id,
        "benchmark_prompt_index": prompt_id,
        "dataset_id": f"gsm8k_{prompt_id}",
        "expected_answer": expected_answer,
        "generated_text": generated_text,
        "input_tokens": 80,
        "output_tokens": output_tokens,
        "max_new_tokens": max_new_tokens,
        "generation_time_s": 2.0,
        "tok_per_sec": output_tokens / 2.0,
        "t_compress_ms": 500.0,
        "R_actual": 2.0,
        "actual_compression_ratio": 2.0,
        "original_input_tokens": 100,
        "compressed_input_tokens": 50,
        "compression_ratio": 2.0,
        "keep_rate": 0.5,
        "question_preserved": True,
        "protected_suffix_preserved": True,
        "protected_suffix_preview": instruction,
        "final_prompt_preview": final_preview,
        "final_prompt_tail_preview": final_preview,
        "compressed_prompt_preview": final_preview,
    }


def test_analyze_paths_reports_mnt256_deltas_and_changed_outcomes(tmp_path: Path):
    before = tmp_path / "task59.jsonl"
    after = tmp_path / "task60.jsonl"
    _write_jsonl(
        before,
        [
            _row(
                condition="CC-DFlash-R2",
                prompt_id=1,
                expected_answer="6",
                generated_text="Reasoning but no final answer.",
                max_new_tokens=192,
                output_tokens=192,
            ),
            _row(
                condition="CC-DFlash-R2",
                prompt_id=2,
                expected_answer="8",
                generated_text="Final answer: 8",
                max_new_tokens=192,
                output_tokens=40,
            ),
        ],
    )
    _write_jsonl(
        after,
        [
            _row(
                condition="CC-DFlash-R2",
                prompt_id=1,
                expected_answer="6",
                generated_text="Reasoning completed.\nFinal answer: 6",
                max_new_tokens=256,
                output_tokens=210,
            ),
            _row(
                condition="CC-DFlash-R2",
                prompt_id=2,
                expected_answer="8",
                generated_text="Final answer: 8",
                max_new_tokens=256,
                output_tokens=45,
            ),
        ],
    )

    summary, changed = analyze_paths(
        before_paths={"CC-DFlash-R2": before},
        after_paths={"CC-DFlash-R2": after},
    )

    before_summary = summary["artifacts"]["task59_mnt192"]["CC-DFlash-R2"]
    after_summary = summary["artifacts"]["task60_mnt256"]["CC-DFlash-R2"]
    comparison = summary["comparisons"]["CC-DFlash-R2"]

    assert before_summary["hit_max_new_tokens_count"] == 1
    assert after_summary["max_new_tokens"] == 256
    assert after_summary["numeric_extraction_match_count"] == 2
    assert comparison["numeric_extraction_match_delta"] == 1
    assert comparison["hit_max_new_tokens_delta"] == -1
    assert comparison["avg_e2e_time_s_delta"] == 0.0
    assert [row["outcome_label"] for row in changed] == ["FAIL_TO_PASS", "SAME_PASS"]
