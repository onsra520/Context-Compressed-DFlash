from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task105a_gsm8k_controlled_speed_matrix as t105a


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _row(
    condition: str,
    index: int,
    expected: str,
    generated: str,
    *,
    generation_time_s: float,
    tokens_per_second: float,
    tau_mean: float = 0.0,
    t_compress_ms: float | None = None,
    r_actual: float | None = None,
    output_tokens: int = 96,
    compressor_profile: str | None = None,
    compressor_device_map: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "fixture_id": f"gsm8k_short_test_{index:04d}",
        "dataset_id": f"gsm8k_short_test_{index:04d}",
        "prompt_id": index,
        "benchmark_prompt_index": index,
        "condition": condition,
        "dataset_name": "gsm8k_short",
        "prompt_source": "dataset",
        "expected_answer": expected,
        "generated_text": generated,
        "max_new_tokens": 256,
        "output_tokens": output_tokens,
        "generated_token_count": output_tokens,
        "generation_time_s": generation_time_s,
        "tokens_per_second": tokens_per_second,
        "tok_per_sec": tokens_per_second,
        "tau_mean": tau_mean,
        "t_prefill_ms": 90.0,
        "vram_allocated_gib": 3.0,
        "vram_reserved_gib": 3.5,
        "prefill_vram_allocated_gib": 3.0,
        "prefill_vram_reserved_gib": 3.5,
        "resume_enabled": True,
        "resumed_from_rows": 0,
    }
    if t_compress_ms is not None:
        row["t_compress_ms"] = t_compress_ms
    if r_actual is not None:
        row["R_actual"] = r_actual
    if compressor_profile is not None:
        row["compressor_profile"] = compressor_profile
        row["compressor_path"] = "models/llmlingua-light"
        row["resolved_compressor_path"] = "/repo/models/llmlingua-light"
        row["local_files_only"] = True
    if compressor_device_map is not None:
        row["compressor_device_map"] = compressor_device_map
        row["requested_compressor_device_map"] = compressor_device_map
    return row


def test_analyzer_writes_required_outputs_and_ranks_speed(tmp_path: Path) -> None:
    baseline = tmp_path / "runs" / "baseline.jsonl"
    dflash = tmp_path / "runs" / "dflash.jsonl"
    optimized = tmp_path / "runs" / "optimized.jsonl"
    _write_jsonl(
        baseline,
        [
            _row("Baseline-AR", 1, "1", "Final answer: 1", generation_time_s=3.0, tokens_per_second=30.0),
            _row("Baseline-AR", 2, "2", "Final answer: 2", generation_time_s=3.1, tokens_per_second=31.0),
            _row("Baseline-AR", 3, "3", "Final answer: 0", generation_time_s=3.2, tokens_per_second=32.0),
        ],
    )
    _write_jsonl(
        dflash,
        [
            _row("DFlash-R1", 1, "1", "Final answer: 1", generation_time_s=2.8, tokens_per_second=40.0, tau_mean=5.0),
            _row("DFlash-R1", 2, "2", "Final answer: 2", generation_time_s=2.9, tokens_per_second=41.0, tau_mean=5.1),
            _row("DFlash-R1", 3, "3", "Final answer: 0", generation_time_s=3.0, tokens_per_second=42.0, tau_mean=5.2),
        ],
    )
    _write_jsonl(
        optimized,
        [
            _row(
                "CC-DFlash-R2",
                1,
                "1",
                "Final answer: 1",
                generation_time_s=2.0,
                tokens_per_second=55.0,
                tau_mean=5.5,
                t_compress_ms=15.0,
                r_actual=2.0,
                compressor_profile="light",
                compressor_device_map="cuda",
            ),
            _row(
                "CC-DFlash-R2",
                2,
                "2",
                "Final answer: 2",
                generation_time_s=2.1,
                tokens_per_second=56.0,
                tau_mean=5.6,
                t_compress_ms=16.0,
                r_actual=2.0,
                compressor_profile="light",
                compressor_device_map="cuda",
            ),
            _row(
                "CC-DFlash-R2",
                3,
                "3",
                "Final answer: 3",
                generation_time_s=2.2,
                tokens_per_second=57.0,
                tau_mean=5.7,
                t_compress_ms=17.0,
                r_actual=2.0,
                compressor_profile="light",
                compressor_device_map="cuda",
            ),
        ],
    )

    result = t105a.analyze(
        baseline_jsonl=baseline,
        dflash_jsonl=dflash,
        optimized_jsonl=optimized,
        output_dir=tmp_path / "out",
        expected_n=3,
    )

    assert result["decision"] == "PASS_WITH_CAVEAT"
    assert result["controlled_matrix_complete"] is True
    assert result["conditions"]["CC-DFlash-R2 Light GPU"]["strict_correct_count"] == 3
    assert result["conditions"]["CC-DFlash-R2 Light GPU"]["metadata_ok"] is True
    assert result["speed_ranking"]["ranked_conditions"][0]["condition"] == "CC-DFlash-R2 Light GPU"
    assert result["claim_update"]["qmsum_caveat_carryforward"] is True
    assert result["next_task_decision"]["next_task"].startswith("T105B")
    assert (tmp_path / "out" / "summary" / "task105a_matrix_summary.json").exists()
    assert (tmp_path / "out" / "summary" / "task105a_condition_metrics.json").exists()
    assert (tmp_path / "out" / "summary" / "task105a_speed_ranking.json").exists()
    assert (tmp_path / "out" / "summary" / "task105a_quality_proxy_summary.json").exists()
    assert (tmp_path / "out" / "summary" / "task105a_failure_or_resume_audit.json").exists()
    assert (tmp_path / "out" / "summary" / "task105a_claim_update.json").exists()
    assert (tmp_path / "out" / "summary" / "task105a_next_task_decision.json").exists()
    assert (tmp_path / "out" / "tables" / "task105a_gsm8k_controlled_speed_matrix.csv").exists()


def test_incomplete_reference_routes_to_resume_task(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.jsonl"
    dflash = tmp_path / "dflash.jsonl"
    optimized = tmp_path / "optimized.jsonl"
    complete_rows = [
        _row("Baseline-AR", 1, "1", "Final answer: 1", generation_time_s=3.0, tokens_per_second=30.0),
        _row("Baseline-AR", 2, "2", "Final answer: 2", generation_time_s=3.0, tokens_per_second=30.0),
    ]
    _write_jsonl(baseline, complete_rows)
    _write_jsonl(dflash, complete_rows[:1])
    _write_jsonl(
        optimized,
        [
            _row(
                "CC-DFlash-R2",
                1,
                "1",
                "Final answer: 1",
                generation_time_s=2.0,
                tokens_per_second=50.0,
                t_compress_ms=15.0,
                r_actual=2.0,
                compressor_profile="light",
                compressor_device_map="cuda",
            ),
            _row(
                "CC-DFlash-R2",
                2,
                "2",
                "Final answer: 2",
                generation_time_s=2.0,
                tokens_per_second=50.0,
                t_compress_ms=15.0,
                r_actual=2.0,
                compressor_profile="light",
                compressor_device_map="cuda",
            ),
        ],
    )

    result = t105a.analyze(
        baseline_jsonl=baseline,
        dflash_jsonl=dflash,
        optimized_jsonl=optimized,
        output_dir=tmp_path / "out",
        expected_n=2,
    )

    assert result["decision"] == "PARTIAL"
    assert result["controlled_matrix_complete"] is False
    assert result["failure_or_resume_audit"]["conditions"]["DFlash-R1"]["row_count_ok"] is False
    assert result["next_task_decision"]["next_task"].startswith("T105A-R")


def test_quality_collapse_blocks_speed_claim_even_when_fast(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.jsonl"
    dflash = tmp_path / "dflash.jsonl"
    optimized = tmp_path / "optimized.jsonl"
    _write_jsonl(
        baseline,
        [_row("Baseline-AR", i, str(i), f"Final answer: {i}", generation_time_s=3.0, tokens_per_second=30.0) for i in range(1, 5)],
    )
    _write_jsonl(
        dflash,
        [_row("DFlash-R1", i, str(i), f"Final answer: {i}", generation_time_s=2.8, tokens_per_second=40.0) for i in range(1, 5)],
    )
    _write_jsonl(
        optimized,
        [
            _row(
                "CC-DFlash-R2",
                i,
                str(i),
                "Final answer: 0",
                generation_time_s=1.8,
                tokens_per_second=60.0,
                t_compress_ms=15.0,
                r_actual=2.0,
                compressor_profile="light",
                compressor_device_map="cuda",
            )
            for i in range(1, 5)
        ],
    )

    result = t105a.analyze(
        baseline_jsonl=baseline,
        dflash_jsonl=dflash,
        optimized_jsonl=optimized,
        output_dir=tmp_path / "out",
        expected_n=4,
    )

    assert result["claim_update"]["bounded_gsm8k_speed_claim_supported"] is False
    assert "quality_proxy_regression" in result["claim_update"]["blocked_claims"]


def test_module_does_not_import_model_libraries() -> None:
    assert "torch" not in t105a.__dict__
    assert "transformers" not in t105a.__dict__
