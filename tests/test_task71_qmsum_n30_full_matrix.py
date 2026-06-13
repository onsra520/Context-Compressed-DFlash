from scripts.analyze_task71_qmsum_n30_full_matrix import analyze_rows


def _row(condition, expected, generated, *, output_tokens=20, max_new_tokens=384, gen_s=1.0, compress_ms=0.0):
    return {
        "condition": condition,
        "prompt_id": 1,
        "fixture_id": "qmsum_case",
        "dataset_name": "qmsum_meeting_qa_long",
        "expected_answer": expected,
        "generated_text": generated,
        "input_tokens": 1000,
        "output_tokens": output_tokens,
        "max_new_tokens": max_new_tokens,
        "generation_time_s": gen_s,
        "tok_per_sec": output_tokens / gen_s,
        "tokens_per_second": output_tokens / gen_s,
        "t_compress_ms": compress_ms,
        "t_prefill_ms": 400.0,
        "R_actual": 2.0 if compress_ms else None,
        "original_input_tokens": 1000 if compress_ms else None,
        "compressed_input_tokens": 500 if compress_ms else None,
        "vram_allocated_gib": 3.0,
        "vram_reserved_gib": 4.0,
        "acceptance_lengths": [2, 3] if "DFlash" in condition else [],
        "tau_mean": 2.5 if "DFlash" in condition else 0.0,
    }


def test_task71_analysis_compares_quality_speed_and_cap_delta():
    expected = "the team chose speech recognition for convenience and product differentiation"
    generated = "The team chose speech recognition because it was convenient and differentiated the product."
    rows_by_condition = {
        "Baseline-AR": [_row("Baseline-AR", expected, generated, output_tokens=20, gen_s=2.0)],
        "DFlash-R1": [_row("DFlash-R1", expected, generated, output_tokens=20, gen_s=1.0)],
        "LLMLingua-AR-R2": [_row("LLMLingua-AR-R2", expected, generated, output_tokens=20, gen_s=2.0, compress_ms=500)],
        "CC-DFlash-R2": [_row("CC-DFlash-R2", expected, generated, output_tokens=20, gen_s=1.0, compress_ms=500)],
    }

    summary, table, cases = analyze_rows(rows_by_condition)

    assert summary["by_condition"]["Baseline-AR"]["rows"] == 1
    assert summary["by_condition"]["CC-DFlash-R2"]["avg_t_compress_ms"] == 500
    assert summary["comparisons"]["baseline_vs_dflash"]["dflash_e2e_speedup_ratio"] > 1
    assert summary["comparisons"]["compressed_pair"]["cc_dflash_e2e_speedup_ratio"] > 1
    assert summary["old_mnt32_problem"]["mnt384_reduced_cap_pressure"] is True
    assert summary["gsm8k_style_failure_assessment"]["qmsum_shows_gsm8k_arithmetic_failure_pattern"] is False
    assert summary["n100_decision"]["justified_next"] is False
    assert len(table) == 4
    assert cases == []


def test_task71_analysis_keeps_cap_cases_for_review():
    expected = "budget approval and schedule changes"
    rows_by_condition = {
        "Baseline-AR": [_row("Baseline-AR", expected, "budget approval", output_tokens=384)],
        "DFlash-R1": [_row("DFlash-R1", expected, "budget approval", output_tokens=384)],
        "LLMLingua-AR-R2": [_row("LLMLingua-AR-R2", expected, "budget approval", output_tokens=384, compress_ms=500)],
        "CC-DFlash-R2": [_row("CC-DFlash-R2", expected, "budget approval", output_tokens=384, compress_ms=500)],
    }

    summary, _table, cases = analyze_rows(rows_by_condition)

    assert summary["by_condition"]["Baseline-AR"]["hit_cap_count"] == 1
    assert {case["case_type"] for case in cases} == {"HIT_CAP"}
