from __future__ import annotations

import json
from pathlib import Path

from scripts.analyze_task65_mnt384_calibration import analyze_paths


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
    max_new_tokens: int,
    output_tokens: int,
    generation_time_s: float = 2.0,
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


def test_analyze_paths_compares_mnt256_to_mnt384_and_cap_hit_cases(tmp_path: Path):
    before = tmp_path / "task63.jsonl"
    after = tmp_path / "task65.jsonl"
    task64_cases = tmp_path / "task64_cases.jsonl"

    _write_jsonl(
        before,
        [
            _row(prompt_id=1, expected="6", generated="Working but unfinished", max_new_tokens=256, output_tokens=256),
            _row(prompt_id=2, expected="8", generated="Final answer: 80", max_new_tokens=256, output_tokens=80),
            _row(prompt_id=3, expected="10", generated="Final answer: 10", max_new_tokens=256, output_tokens=40),
        ],
    )
    _write_jsonl(
        after,
        [
            _row(prompt_id=1, expected="6", generated="Finished.\nFinal answer: 6", max_new_tokens=384, output_tokens=300),
            _row(prompt_id=2, expected="8", generated="Final answer: 80", max_new_tokens=384, output_tokens=80),
            _row(prompt_id=3, expected="10", generated="Final answer: 10", max_new_tokens=384, output_tokens=40),
        ],
    )
    _write_jsonl(
        task64_cases,
        [
            {
                "condition": "LLMLingua-AR-R2",
                "prompt_id": 1,
                "dataset_id": "gsm8k_1",
                "failure_label": "TRUNCATION_DOMINANT",
                "hit_cap": True,
                "numeric_match": False,
            }
        ],
    )

    summary, changed = analyze_paths(
        task63_paths={"LLMLingua-AR-R2": before},
        task65_paths={"LLMLingua-AR-R2": after},
        task64_cases_path=task64_cases,
    )

    before_summary = summary["artifacts"]["task63_mnt256"]["LLMLingua-AR-R2"]
    after_summary = summary["artifacts"]["task65_mnt384"]["LLMLingua-AR-R2"]
    comparison = summary["comparisons"]["LLMLingua-AR-R2"]
    cap_resolution = summary["task64_cap_hit_case_resolution"]["LLMLingua-AR-R2"]

    assert before_summary["numeric_extraction_match_count"] == 1
    assert after_summary["numeric_extraction_match_count"] == 2
    assert comparison["numeric_extraction_match_delta"] == 1
    assert comparison["hit_token_cap_count_delta"] == -1
    assert comparison["avg_generation_latency_s_delta"] == 0.0
    assert cap_resolution["task64_cases"] == 1
    assert cap_resolution["previous_numeric_failure_count"] == 1
    assert cap_resolution["previous_failure_fixed_count"] == 1
    assert cap_resolution["numeric_match_after_count"] == 1
    assert cap_resolution["still_hit_cap_count"] == 0
    assert cap_resolution["final_answer_marker_count"] == 1
    assert [row["outcome_label"] for row in changed] == ["FAIL_TO_PASS", "SAME_FAIL", "SAME_PASS"]
