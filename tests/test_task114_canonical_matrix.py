from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_2_revalidation import task114_canonical_matrix as t114


def _raw_row(condition: str, *, idx: int = 1) -> dict:
    return {
        "condition": condition,
        "benchmark_prompt_index": idx,
        "prompt_hash": "compressed-hash" if condition == "CC-DFlash-R2" else "logical-hash",
        "precompression_prompt_hash": "logical-hash",
        "precompression_input_tokens": 100,
        "input_tokens": 100 if condition != "CC-DFlash-R2" else 50,
        "compressed_input_tokens": 50 if condition == "CC-DFlash-R2" else None,
        "output_tokens": 8,
        "max_new_tokens": 256,
        "generation_time_s": 0.25,
        "t_prefill_ms": 40.0,
        "t_generation_ms": 250.0,
        "t_compress_ms": 10.0 if condition == "CC-DFlash-R2" else 0.0,
        "tokens_per_second": 32.0,
        "peak_allocated_gib": 3.0,
        "peak_reserved_gib": 4.0,
        "vram_allocated_gib": 3.0,
        "vram_reserved_gib": 4.0,
        "is_warmup": False,
        "warmup_prompts": 1,
        "generated_text": "Reasoning.\nFinal answer: 42",
        "expected_answer": "42",
        "compressor_profile": "light" if condition == "CC-DFlash-R2" else None,
        "compressor_device_map": "cuda" if condition == "CC-DFlash-R2" else None,
    }


def _spec(dataset: str, condition: str) -> t114.RunSpec:
    return t114.RunSpec(dataset, condition, 1, Path("unused.jsonl"))


def test_normalize_cc_compression_formulas_and_timing():
    rows = t114.normalize_rows([_raw_row("CC-DFlash-R2")], _spec("gsm8k", "cc_dflash_r2_light_gpu"))
    row = rows[0]
    assert row["compression_retained_ratio"] == 0.5
    assert row["compression_reduction_pct"] == 50.0
    assert row["compression_factor"] == 2.0
    assert row["t_e2e_ms"] == 300.0
    assert row["gsm8k_strict_numeric_correct"] is True
    assert row["full_generated_text_present"] is True


def test_uncompressed_conditions_zero_compress_without_ratios():
    rows = t114.normalize_rows([_raw_row("Baseline-AR")], _spec("gsm8k", "baseline_ar"))
    row = rows[0]
    assert row["t_compress_ms"] == 0.0
    assert row["compressed_input_tokens"] is None
    assert row["compression_retained_ratio"] is None


def test_qmsum_quality_is_proxy_only():
    raw = _raw_row("DFlash-R1")
    raw["generated_text"] = "Alice approved the budget because the migration risk was low."
    raw["expected_answer"] = "Alice approved the budget after reviewing migration risk."
    rows = t114.normalize_rows([raw], _spec("qmsum", "dflash_r1"))
    assert rows[0]["qmsum_reference_recall"] is not None
    assert "qmsum_semantic_correctness" not in rows[0]


def test_smoke_audit_accepts_prompt_token_fairness(tmp_path: Path):
    paths = {}
    for dataset_key in t114.DATASETS:
        for condition_key, condition in t114.CONDITIONS.items():
            raw = _raw_row(condition["runner_condition"])
            rows = t114.normalize_rows([raw], _spec(dataset_key, condition_key))
            path = tmp_path / dataset_key / condition["output_name"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")
            paths[(dataset_key, condition_key)] = path
    audit = t114.audit_smoke(paths)
    assert audit["passed"] is True
    assert audit["failures"] == []


def test_summary_has_exact_six_rows_and_required_metrics():
    rows_by_key = {}
    for dataset_key, condition_key in t114.SUMMARY_ORDER:
        condition = t114.CONDITIONS[condition_key]
        rows_by_key[(dataset_key, condition_key)] = t114.normalize_rows(
            [_raw_row(condition["runner_condition"])],
            _spec(dataset_key, condition_key),
        )
    summary = t114.summarize(rows_by_key)
    assert [(row["dataset"], row["display_name"]) for row in summary] == [
        ("gsm8k", "Baseline-AR"),
        ("gsm8k", "DFlash-R1"),
        ("gsm8k", "CC-DFlash-R2 Light GPU"),
        ("qmsum", "Baseline-AR"),
        ("qmsum", "DFlash-R1"),
        ("qmsum", "CC-DFlash-R2 Light GPU"),
    ]
    assert all("avg_t_e2e_ms" in row for row in summary)
    assert all("max_peak_reserved_gib" in row for row in summary)
