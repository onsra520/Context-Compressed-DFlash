from scripts.analyze_task70_qmsum_diagnostic_audit import (
    analyze_rows,
    has_repetition,
    normalized_token_overlap,
)


def _row(condition, expected, generated, *, output_tokens=32, max_new_tokens=32, gen_s=1.0, compress_ms=0.0):
    return {
        "condition": condition,
        "prompt_id": 1,
        "fixture_id": "qmsum_test_1",
        "dataset_name": "qmsum_meeting_qa_long",
        "expected_answer": expected,
        "generated_text": generated,
        "input_tokens": 600,
        "output_tokens": output_tokens,
        "max_new_tokens": max_new_tokens,
        "generation_time_s": gen_s,
        "tok_per_sec": output_tokens / gen_s if gen_s else 0,
        "tokens_per_second": output_tokens / gen_s if gen_s else 0,
        "t_compress_ms": compress_ms,
        "t_prefill_ms": 700.0,
        "R_actual": 2.0 if compress_ms else None,
        "original_input_tokens": 600 if compress_ms else None,
        "compressed_input_tokens": 300 if compress_ms else None,
        "acceptance_lengths": [2, 3] if "DFlash" in condition else [],
        "tau_mean": 2.5 if "DFlash" in condition else 0.0,
        "vram_allocated_gib": 3.0,
        "vram_reserved_gib": 3.5,
    }


def test_normalized_overlap_handles_long_answer_proxy():
    expected = "The designer wanted speech recognition and gesture recognition in the controller."
    generated = "The answer says the controller should use speech recognition plus gesture recognition."

    assert normalized_token_overlap(expected, generated) >= 0.5


def test_repetition_detector_flags_low_diversity_outputs():
    repeated = "meeting meeting meeting meeting meeting meeting meeting meeting meeting meeting"
    varied = "The group discussed the budget, timeline, interface design, and follow-up action items."

    assert has_repetition(repeated) is True
    assert has_repetition(varied) is False


def test_analyze_rows_marks_mnt32_artifacts_stale_and_compares_speed():
    rows_by_condition = {
        "Baseline-AR": [
            _row("Baseline-AR", "speech recognition controller", "speech recognition controller", gen_s=3.0)
            for _ in range(10)
        ],
        "DFlash-R1": [
            _row("DFlash-R1", "speech recognition controller", "speech recognition controller", gen_s=2.0)
            for _ in range(10)
        ],
        "LLMLingua-AR-R2": [
            _row("LLMLingua-AR-R2", "speech recognition controller", "speech recognition controller", gen_s=4.0, compress_ms=500)
            for _ in range(10)
        ],
        "CC-DFlash-R2": [
            _row("CC-DFlash-R2", "speech recognition controller", "speech recognition controller", gen_s=2.0, compress_ms=500)
            for _ in range(10)
        ],
    }

    summary, table, cases = analyze_rows(rows_by_condition)

    assert summary["artifact_readiness"]["has_full_task51_n10_matrix"] is True
    assert summary["artifact_readiness"]["fresh_qmsum_n30_needed"] is True
    assert summary["artifact_readiness"]["reason"] == "STALE_MNT32_AND_N10_ONLY"
    assert summary["comparisons"]["baseline_vs_dflash"]["dflash_generation_speedup_ratio"] > 1
    assert summary["comparisons"]["compressed_pair"]["cc_dflash_e2e_speedup_ratio"] > 1
    assert summary["gsm8k_style_failure_assessment"]["qmsum_tests_gsm8k_arithmetic_failure"] is False
    assert len(table) == 4
    assert {case["case_type"] for case in cases} == {"HIT_CAP"}


def test_analyze_rows_collects_quality_proxy_cases():
    rows_by_condition = {
        "Baseline-AR": [
            _row("Baseline-AR", "budget approval", "", output_tokens=0, max_new_tokens=32),
        ],
        "DFlash-R1": [
            _row("DFlash-R1", "budget approval", "other text", output_tokens=5, max_new_tokens=32),
        ],
        "LLMLingua-AR-R2": [
            _row("LLMLingua-AR-R2", "budget approval", "yes yes yes yes yes yes yes yes yes", output_tokens=9, max_new_tokens=32, compress_ms=500),
        ],
        "CC-DFlash-R2": [
            _row("CC-DFlash-R2", "budget approval", "budget approval", output_tokens=32, max_new_tokens=32, compress_ms=500),
        ],
    }

    summary, _table, cases = analyze_rows(rows_by_condition)

    assert summary["by_condition"]["Baseline-AR"]["empty_output_count"] == 1
    assert summary["by_condition"]["LLMLingua-AR-R2"]["repetition_count"] == 1
    assert summary["by_condition"]["CC-DFlash-R2"]["hit_cap_count"] == 1
    assert {case["case_type"] for case in cases} >= {"EMPTY_OUTPUT", "LOW_OVERLAP", "REPETITION"}
