from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_1_system_build_and_evaluation.analysis.t61b_keep_rate67_calibration import analyze_paths


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
    requested_keep_rate_percent: float | None,
    keep_rate: float,
    original_input_tokens: int,
    compressed_input_tokens: int,
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
        "output_tokens": 80,
        "max_new_tokens": 256,
        "generation_time_s": 2.0,
        "tok_per_sec": 40.0,
        "t_compress_ms": 500.0,
        "R_actual": original_input_tokens / compressed_input_tokens,
        "actual_compression_ratio": original_input_tokens / compressed_input_tokens,
        "original_input_tokens": original_input_tokens,
        "compressed_input_tokens": compressed_input_tokens,
        "compression_ratio": original_input_tokens / compressed_input_tokens,
        "requested_keep_rate_percent": requested_keep_rate_percent,
        "requested_keep_rate": None if requested_keep_rate_percent is None else requested_keep_rate_percent / 100.0,
        "keep_rate": keep_rate,
        "question_preserved": True,
        "protected_suffix_preserved": True,
        "protected_suffix_preview": instruction,
        "final_prompt_preview": final_preview,
        "final_prompt_tail_preview": final_preview,
        "compressed_prompt_preview": final_preview,
    }


def test_analyze_paths_reports_keep_rate_metadata_and_quality_deltas(tmp_path: Path):
    before = tmp_path / "task60.jsonl"
    after = tmp_path / "task61b.jsonl"
    _write_jsonl(
        before,
        [
            _row(
                condition="LLMLingua-AR-R2",
                prompt_id=1,
                expected_answer="6",
                generated_text="Final answer: 2",
                requested_keep_rate_percent=None,
                keep_rate=0.5,
                original_input_tokens=100,
                compressed_input_tokens=50,
            ),
            _row(
                condition="LLMLingua-AR-R2",
                prompt_id=2,
                expected_answer="8",
                generated_text="Final answer: 8",
                requested_keep_rate_percent=None,
                keep_rate=0.5,
                original_input_tokens=100,
                compressed_input_tokens=50,
            ),
        ],
    )
    _write_jsonl(
        after,
        [
            _row(
                condition="LLMLingua-AR-R2",
                prompt_id=1,
                expected_answer="6",
                generated_text="Final answer: 6",
                requested_keep_rate_percent=67.0,
                keep_rate=0.67,
                original_input_tokens=100,
                compressed_input_tokens=67,
            ),
            _row(
                condition="LLMLingua-AR-R2",
                prompt_id=2,
                expected_answer="8",
                generated_text="Final answer: 8",
                requested_keep_rate_percent=67.0,
                keep_rate=0.67,
                original_input_tokens=100,
                compressed_input_tokens=67,
            ),
        ],
    )

    summary, changed = analyze_paths(
        before_paths={"LLMLingua-AR-R2": before},
        after_paths={"LLMLingua-AR-R2": after},
    )

    before_summary = summary["artifacts"]["task60_keep_rate50"]["LLMLingua-AR-R2"]
    after_summary = summary["artifacts"]["task61b_keep_rate67"]["LLMLingua-AR-R2"]
    comparison = summary["comparisons"]["LLMLingua-AR-R2"]

    assert before_summary["avg_keep_rate"] == 0.5
    assert after_summary["requested_keep_rate_percent_values"] == [67.0]
    assert after_summary["requested_keep_rate_values"] == [0.67]
    assert after_summary["avg_keep_rate"] == 0.67
    assert after_summary["avg_kept_token_ratio"] == 0.67
    assert after_summary["numeric_extraction_match_count"] == 2
    assert comparison["numeric_extraction_match_delta"] == 1
    assert comparison["avg_kept_token_ratio_delta"] == 0.17
    assert [row["outcome_label"] for row in changed] == ["FAIL_TO_PASS", "SAME_PASS"]
