from __future__ import annotations

import json
from pathlib import Path

from scripts.analyze_task64_cap_hit_triage import analyze_paths


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _row(
    *,
    prompt_id: int,
    expected_answer: str,
    generated_text: str,
    output_tokens: int,
    max_new_tokens: int = 256,
    compressed_preview: str = "compressed prompt with question numbers 4 and 6",
) -> dict:
    return {
        "condition": "LLMLingua-AR-R2",
        "prompt_id": prompt_id,
        "benchmark_prompt_index": prompt_id,
        "dataset_id": f"case_{prompt_id}",
        "expected_answer": expected_answer,
        "generated_text": generated_text,
        "output_tokens": output_tokens,
        "max_new_tokens": max_new_tokens,
        "input_tokens": 80,
        "generation_time_s": 2.0,
        "tok_per_sec": 40.0,
        "t_compress_ms": 500.0,
        "original_input_tokens": 100,
        "compressed_input_tokens": 50,
        "actual_compression_ratio": 2.0,
        "compression_ratio": 2.0,
        "protected_suffix_preserved": True,
        "question_preserved": True,
        "final_prompt_tail_preview": "End with exactly one line: Final answer: <number>",
        "compressed_prompt_preview": compressed_preview,
        "final_prompt_preview": compressed_preview,
    }


def test_analyze_paths_labels_failures_and_cap_hits(tmp_path: Path):
    artifact = tmp_path / "artifact.jsonl"
    dataset = tmp_path / "dataset.jsonl"
    _write_jsonl(
        artifact,
        [
            _row(
                prompt_id=1,
                expected_answer="42",
                generated_text="We compute several steps but have not reached the answer",
                output_tokens=256,
            ),
            _row(
                prompt_id=2,
                expected_answer="12",
                generated_text="The arithmetic gives 9.\nFinal answer: 9",
                output_tokens=40,
            ),
            _row(
                prompt_id=3,
                expected_answer="25",
                generated_text="The correct result is 25. A trailing unrelated check mentions 4.",
                output_tokens=50,
            ),
            _row(
                prompt_id=4,
                expected_answer="7",
                generated_text="Final answer: 7",
                output_tokens=32,
            ),
        ],
    )
    _write_jsonl(
        dataset,
        [
            {"id": f"case_{i}", "question": "What is 4 plus 6?", "expected_answer": str(i)}
            for i in range(1, 5)
        ],
    )

    summary, cases = analyze_paths(
        artifact_paths={"LLMLingua-AR-R2": artifact},
        dataset_path=dataset,
    )

    condition = summary["by_condition"]["LLMLingua-AR-R2"]
    assert condition["total_rows"] == 4
    assert condition["numeric_failures"] == 3
    assert condition["cap_hits"] == 1
    assert condition["cap_hit_failures"] == 1
    assert condition["non_cap_failures"] == 2
    assert condition["projected_upper_bound_matches_if_cap_failures_fixed"] == 2
    assert condition["projected_upper_bound_rate_if_cap_failures_fixed"] == 0.5

    labels = {case["dataset_id"]: case["failure_label"] for case in cases}
    assert labels["case_1"] == "TRUNCATION_DOMINANT"
    assert labels["case_2"] == "REASONING_FAIL"
    assert labels["case_3"] == "EXTRACTION_ISSUE"
