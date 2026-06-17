from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_1_analysis.analyze_task66_mnt384_rerun_reproducibility import analyze_paths


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _row(
    *,
    prompt_id: int,
    expected: str,
    generated: str,
    generation_time_s: float,
    max_new_tokens: int = 384,
    output_tokens: int = 100,
) -> dict:
    instruction = "End with exactly one line:\nFinal answer: <number>"
    return {
        "condition": "LLMLingua-AR-R2",
        "prompt_id": prompt_id,
        "benchmark_prompt_index": prompt_id,
        "dataset_id": f"gsm8k_{prompt_id}",
        "expected_answer": expected,
        "generated_text": generated,
        "input_tokens": 80,
        "output_tokens": output_tokens,
        "max_new_tokens": max_new_tokens,
        "generation_time_s": generation_time_s,
        "tok_per_sec": output_tokens / generation_time_s,
        "t_compress_ms": 500.0,
        "R_actual": 2.0,
        "actual_compression_ratio": 2.0,
        "compression_ratio": 2.0,
        "original_input_tokens": 100,
        "compressed_input_tokens": 50,
        "keep_rate": 0.5,
        "protected_suffix_preserved": True,
        "question_preserved": True,
        "protected_suffix_preview": instruction,
        "final_prompt_tail_preview": instruction,
        "final_prompt_preview": f"Question?\n\n{instruction}",
        "compressed_prompt_preview": f"Question?\n\n{instruction}",
    }


def test_analyze_paths_marks_first_run_latency_as_noisy_when_rerun_is_much_faster(tmp_path: Path):
    task65 = tmp_path / "task65.jsonl"
    task66 = tmp_path / "task66.jsonl"

    _write_jsonl(
        task65,
        [
            _row(prompt_id=1, expected="6", generated="Final answer: 6", generation_time_s=20.0),
            _row(prompt_id=2, expected="8", generated="Final answer: 80", generation_time_s=20.0),
        ],
    )
    _write_jsonl(
        task66,
        [
            _row(prompt_id=1, expected="6", generated="Final answer: 6", generation_time_s=5.0),
            _row(prompt_id=2, expected="8", generated="Final answer: 80", generation_time_s=5.0),
        ],
    )

    summary, changed = analyze_paths(
        task65_paths={"LLMLingua-AR-R2": task65},
        task66_paths={"LLMLingua-AR-R2": task66},
        noisy_threshold=0.25,
    )

    comparison = summary["comparisons"]["LLMLingua-AR-R2"]
    assert comparison["task65_numeric_extraction_match_count"] == 1
    assert comparison["task66_numeric_extraction_match_count"] == 1
    assert comparison["avg_e2e_latency_s_delta"] == -15.0
    assert comparison["avg_e2e_latency_relative_delta"] == -0.731707
    assert comparison["latency_reproducibility"] == "TASK65_NOISY_TASK66_LOWER"
    assert comparison["task65_latency_appears_noisy"] is True
    assert summary["changed_outcome_counts"] == {"SAME_FAIL": 1, "SAME_PASS": 1}
    assert [row["outcome_label"] for row in changed] == ["SAME_PASS", "SAME_FAIL"]
