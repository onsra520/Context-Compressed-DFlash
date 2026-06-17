from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_1_analysis.analyze_task59_suffix_verification import analyze_paths


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _compressed_row(
    *,
    condition: str,
    prompt_id: int,
    expected_answer: str,
    generated_text: str,
    suffix_preserved: bool,
) -> dict:
    instruction = "End with exactly one line:\nFinal answer: <number>"
    final_preview = (
        f"Compressed context. Question text? {instruction}"
        if suffix_preserved
        else "Compressed context. Question text?"
    )
    return {
        "condition": condition,
        "prompt_id": prompt_id,
        "dataset_id": f"gsm8k_{prompt_id}",
        "expected_answer": expected_answer,
        "generated_text": generated_text,
        "output_tokens": 12,
        "max_new_tokens": 192,
        "generation_time_s": 1.0,
        "tok_per_sec": 12.0,
        "t_compress_ms": 100.0,
        "R_actual": 2.0,
        "actual_compression_ratio": 2.0,
        "original_input_tokens": 100,
        "compressed_input_tokens": 50,
        "compression_ratio": 2.0,
        "keep_rate": 0.5,
        "question_preserved": True,
        "protected_suffix_preserved": suffix_preserved,
        "protected_suffix_preview": instruction if suffix_preserved else "",
        "final_prompt_preview": final_preview,
        "final_prompt_tail_preview": final_preview,
        "compressed_prompt_preview": final_preview,
    }


def test_analyze_paths_compares_suffix_fix_and_quality(tmp_path: Path):
    before = tmp_path / "before.jsonl"
    after = tmp_path / "after.jsonl"
    _write_jsonl(
        before,
        [
            _compressed_row(
                condition="LLMLingua-AR-R2",
                prompt_id=1,
                expected_answer="6",
                generated_text="We compute a few steps but stop at 4.",
                suffix_preserved=False,
            )
        ],
    )
    _write_jsonl(
        after,
        [
            _compressed_row(
                condition="LLMLingua-AR-R2",
                prompt_id=1,
                expected_answer="6",
                generated_text="Reasoning.\nFinal answer: 6",
                suffix_preserved=True,
            )
        ],
    )

    summary = analyze_paths(
        before_paths={"LLMLingua-AR-R2": before},
        after_paths={"LLMLingua-AR-R2": after},
    )

    before_summary = summary["artifacts"]["task56_before_suffix_fix"]["LLMLingua-AR-R2"]
    after_summary = summary["artifacts"]["task59_after_suffix_fix"]["LLMLingua-AR-R2"]
    comparison = summary["comparisons"]["LLMLingua-AR-R2"]

    assert before_summary["rows"] == 1
    assert before_summary["protected_suffix_preserved_count"] == 0
    assert before_summary["final_prompt_tail_has_instruction_count"] == 0
    assert before_summary["numeric_extraction_match_count"] == 0
    assert after_summary["protected_suffix_preserved_count"] == 1
    assert after_summary["final_prompt_tail_has_instruction_count"] == 1
    assert after_summary["generated_final_answer_marker_present_count"] == 1
    assert after_summary["numeric_extraction_match_count"] == 1
    assert after_summary["compressed_metadata_complete_rows"] == 1
    assert comparison["protected_suffix_preserved_delta"] == 1
    assert comparison["numeric_extraction_match_delta"] == 1
