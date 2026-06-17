from scripts.phase_1_analysis.analyze_task72_qmsum_cap_hit_proxy_triage import (
    analyze_rows,
    ends_naturally,
    label_cap_hit_case,
)


def _row(condition, prompt_id, expected, generated, *, output_tokens=384, max_new_tokens=384, gen_s=1.0, compress_ms=0.0):
    return {
        "condition": condition,
        "prompt_id": prompt_id,
        "fixture_id": f"qmsum_{prompt_id}",
        "expected_answer": expected,
        "generated_text": generated,
        "output_tokens": output_tokens,
        "max_new_tokens": max_new_tokens,
        "input_tokens": 1000,
        "generation_time_s": gen_s,
        "tok_per_sec": output_tokens / gen_s if gen_s else 0.0,
        "t_compress_ms": compress_ms,
        "t_prefill_ms": 400.0,
        "original_input_tokens": 1000 if compress_ms else None,
        "compressed_input_tokens": 500 if compress_ms else None,
        "R_actual": 2.0 if compress_ms else None,
        "vram_allocated_gib": 3.0,
        "vram_reserved_gib": 4.0,
    }


def test_ends_naturally_detects_incomplete_tails():
    assert ends_naturally("The committee approved the schedule.") is True
    assert ends_naturally("The committee approved the schedule and") is False
    assert ends_naturally("The committee approved the schedule because") is False


def test_label_cap_hit_case_identifies_core_labels():
    expected = "budget approval and schedule changes"
    uncompressed = _row("Baseline-AR", 1, expected, "budget approval and schedule changes.", output_tokens=20)
    compressed_loss = _row("LLMLingua-AR-R2", 1, expected, "the meeting discussed unrelated catering", compress_ms=500)
    truncation = _row("LLMLingua-AR-R2", 2, expected, "budget approval and schedule changes because", compress_ms=500)
    acceptable = _row("LLMLingua-AR-R2", 3, expected, "budget approval and schedule changes.", compress_ms=500)
    proxy = _row("LLMLingua-AR-R2", 4, expected, "the chair summarized a different agenda.", compress_ms=500)

    assert label_cap_hit_case(compressed_loss, [uncompressed]) == "COMPRESSION_LOSS_POSSIBLE"
    assert label_cap_hit_case(truncation, []) == "TRUNCATION_LIKELY"
    assert label_cap_hit_case(acceptable, []) == "ACCEPTABLE_DESPITE_CAP"
    assert label_cap_hit_case(proxy, []) == "PROXY_WEAKNESS"


def test_analyze_rows_reports_cap_overlap_and_decisions():
    expected = "budget approval and schedule changes"
    rows_by_condition = {
        "Baseline-AR": [
            _row("Baseline-AR", 1, expected, "budget approval and schedule changes.", output_tokens=20, max_new_tokens=384),
            _row("Baseline-AR", 2, expected, "budget approval and schedule changes.", output_tokens=20, max_new_tokens=384),
        ],
        "DFlash-R1": [
            _row("DFlash-R1", 1, expected, "budget approval and schedule changes.", output_tokens=20, max_new_tokens=384),
            _row("DFlash-R1", 2, expected, "budget approval and schedule changes.", output_tokens=20, max_new_tokens=384),
        ],
        "LLMLingua-AR-R2": [
            _row("LLMLingua-AR-R2", 1, expected, "budget approval and schedule changes because", compress_ms=500),
            _row("LLMLingua-AR-R2", 2, expected, "budget approval and schedule changes.", compress_ms=500),
        ],
        "CC-DFlash-R2": [
            _row("CC-DFlash-R2", 1, expected, "budget approval and schedule changes because", compress_ms=500),
            _row("CC-DFlash-R2", 3, expected, "budget approval and schedule changes because", compress_ms=500),
        ],
    }

    summary, table, cases = analyze_rows(rows_by_condition)

    assert summary["cap_hit_overlap"]["shared_prompt_ids"] == [1]
    assert summary["cap_hit_overlap"]["llmlingua_only_prompt_ids"] == [2]
    assert summary["cap_hit_overlap"]["cc_dflash_only_prompt_ids"] == [3]
    assert summary["decisions"]["qmsum_n100_justified"] is False
    assert summary["decisions"]["prompt_refinement_recommended"] is True
    assert summary["decisions"]["mnt512_compressed_only_justified"] is True
    assert len(table) == 4
    assert {case["label"] for case in cases} >= {"TRUNCATION_LIKELY", "ACCEPTABLE_DESPITE_CAP"}
