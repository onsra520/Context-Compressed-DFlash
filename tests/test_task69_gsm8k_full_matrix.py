from scripts.analyze_task69_gsm8k_full_matrix import analyze_rows


def _row(condition, expected, generated, *, gen_s=1.0, output_tokens=10, compress_ms=0.0, tau=0.0):
    return {
        "condition": condition,
        "prompt_id": 1,
        "dataset_id": "gsm8k_short_test_x",
        "expected_answer": expected,
        "generated_text": generated,
        "output_tokens": output_tokens,
        "input_tokens": 20,
        "generation_time_s": gen_s,
        "tok_per_sec": output_tokens / gen_s,
        "t_compress_ms": compress_ms,
        "tau_mean": tau,
        "acceptance_lengths": [2, 3] if tau else [],
        "max_new_tokens": 384,
        "vram_allocated_gib": 2.5,
        "vram_reserved_gib": 3.0,
        "protected_suffix_preserved": condition.startswith("CC") or condition.startswith("LLM"),
        "question_preserved": condition.startswith("CC") or condition.startswith("LLM"),
        "actual_compression_ratio": 2.5 if condition.startswith("CC") or condition.startswith("LLM") else None,
        "original_input_tokens": 30 if condition.startswith("CC") or condition.startswith("LLM") else None,
        "compressed_input_tokens": 12 if condition.startswith("CC") or condition.startswith("LLM") else None,
    }


def test_analyze_rows_summarizes_quality_latency_and_comparisons():
    rows_by_condition = {
        "Baseline-AR": [
            _row("Baseline-AR", "4", "Final answer: 4", gen_s=2.0, output_tokens=20),
            _row("Baseline-AR", "5", "Final answer: 6", gen_s=1.0, output_tokens=10),
        ],
        "DFlash-R1": [
            _row("DFlash-R1", "4", "Final answer: 4", gen_s=1.0, output_tokens=20, tau=5.0),
            _row("DFlash-R1", "5", "Final answer: 5", gen_s=1.0, output_tokens=10, tau=4.0),
        ],
        "LLMLingua-AR-R2": [
            _row("LLMLingua-AR-R2", "4", "Final answer: 4", gen_s=2.0, output_tokens=20, compress_ms=500),
            _row("LLMLingua-AR-R2", "5", "Final answer: 6", gen_s=2.0, output_tokens=10, compress_ms=500),
        ],
        "CC-DFlash-R2": [
            _row("CC-DFlash-R2", "4", "Final answer: 4", gen_s=1.0, output_tokens=20, compress_ms=500, tau=5.0),
            _row("CC-DFlash-R2", "5", "Final answer: 6", gen_s=1.0, output_tokens=10, compress_ms=500, tau=4.0),
        ],
    }

    summary, table, failures = analyze_rows(rows_by_condition)

    assert summary["by_condition"]["Baseline-AR"]["numeric_matches"] == 1
    assert summary["by_condition"]["DFlash-R1"]["numeric_matches"] == 2
    assert summary["by_condition"]["CC-DFlash-R2"]["avg_t_compress_ms"] == 500
    assert summary["comparisons"]["compressed_pair"]["cc_dflash_beats_llmlingua_ar_on_e2e_speed"] is True
    assert summary["comparisons"]["compressed_pair"]["quality_match"] is True
    assert summary["comparisons"]["quality_gap"]["compressed_quality_acceptability"] == "BELOW_UNCOMPRESSED_BEST"
    assert len(table) == 4
    assert len(failures) == 3
