from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task100c_optimization_gap_analysis as t100c


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _row(
    index: int,
    expected_answer: str,
    generated_text: str,
    *,
    output_tokens: int = 120,
    t_compress_ms: float = 18.0,
    generation_time_s: float = 2.0,
    tokens_per_second: float = 60.0,
    tau_mean: float = 5.0,
    r_actual: float = 2.0,
    vram_reserved_gib: float = 4.4,
) -> dict[str, object]:
    fixture_id = f"gsm8k_short_test_{index:04d}"
    return {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "prompt_id": index,
        "benchmark_prompt_index": index,
        "condition": "CC-DFlash-R2",
        "dataset_name": "gsm8k_short",
        "expected_answer": expected_answer,
        "generated_text": generated_text,
        "output_tokens": output_tokens,
        "generated_token_count": output_tokens,
        "max_new_tokens": 256,
        "t_compress_ms": t_compress_ms,
        "generation_time_s": generation_time_s,
        "tokens_per_second": tokens_per_second,
        "tok_per_sec": tokens_per_second,
        "tau_mean": tau_mean,
        "t_prefill_ms": 90.0 + index,
        "R_actual": r_actual,
        "vram_allocated_gib": 4.16,
        "vram_reserved_gib": vram_reserved_gib,
        "prefill_vram_allocated_gib": 4.16,
        "prefill_vram_reserved_gib": vram_reserved_gib,
        "compressor_profile": "light",
        "compressor_device_map": "cuda",
        "requested_compressor_device_map": "cuda",
        "local_files_only": True,
    }


def _fixture_rows() -> list[dict[str, object]]:
    return [
        _row(1, "4", "Reasoning\nFinal answer: 4", generation_time_s=1.0, tokens_per_second=80.0),
        _row(2, "5", "unfinished reasoning +", output_tokens=256, generation_time_s=6.0, tokens_per_second=30.0, tau_mean=2.0),
        _row(3, "6", "Reasoning\nFinal answer: 7", generation_time_s=3.0, tokens_per_second=45.0, tau_mean=8.0),
        _row(4, "8", "", generation_time_s=2.5, t_compress_ms=100.0, r_actual=1.8),
    ]


def _summary(path: Path) -> dict[str, object]:
    return {
        "decision": "PASS_WITH_CAVEAT",
        "light_gpu_n100": {
            "artifact": str(path),
            "row_count": 4,
            "strict_correct_count": 1,
            "cap_limited_incomplete_count": 1,
            "strict_wrong_numeric_count": 1,
            "final_answer_marker_count": 2,
            "answer_missing_count": 1,
            "proxy_uncertain_count": 0,
            "exact_containment_diagnostic_count": 1,
            "avg_t_compress_ms": 38.5,
            "avg_e2e_time_s": 3.5385,
            "avg_tokens_per_second": 53.75,
            "avg_tau_mean": 5.0,
            "avg_R_actual": 1.95,
            "max_vram_reserved_gib": 4.4,
            "metadata_ok": True,
        },
    }


def test_analyzer_reads_fixture_jsonl_and_emits_gap_artifacts(tmp_path: Path) -> None:
    run = tmp_path / "run.jsonl"
    _write_jsonl(run, _fixture_rows())
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps(_summary(run)), encoding="utf-8")

    result = t100c.analyze(
        run_artifact=run,
        task100b_summary=summary,
        output_dir=tmp_path / "out",
    )

    assert result["decision"] == "PASS"
    assert result["quality_gaps"]["strict_correct_count"] == 1
    assert result["quality_gaps"]["cap_limited_incomplete_count"] == 1
    assert result["quality_gaps"]["strict_wrong_numeric_count"] == 1
    assert result["quality_gaps"]["answer_missing_count"] == 1
    assert (tmp_path / "out" / "task100c_gap_summary.json").exists()
    assert (tmp_path / "out" / "task100c_failure_rows.jsonl").exists()
    assert (tmp_path / "out" / "task100c_slowest_rows.jsonl").exists()
    assert (tmp_path / "out" / "task100c_bottleneck_table.csv").exists()
    assert (tmp_path / "out" / "task100c_recommendation.json").exists()
    assert (tmp_path / "out" / "task100c_claim_risk_register.json").exists()


def test_failure_rows_include_labels_previews_and_runtime_fields(tmp_path: Path) -> None:
    run = tmp_path / "run.jsonl"
    _write_jsonl(run, _fixture_rows())

    rows = t100c.build_row_records(t100c.load_jsonl(run), artifact=run)
    failures = t100c.failure_rows(rows)

    labels = {row["category"] for row in failures}
    assert labels == {"cap_limited_incomplete", "strict_wrong_numeric", "answer_missing"}
    assert all("generated_text_tail" in row for row in failures)
    assert all("e2e_time_s" in row for row in failures)
    assert all("notes" in row for row in failures)


def test_bottleneck_summary_and_slowest_rows_are_computed(tmp_path: Path) -> None:
    run = tmp_path / "run.jsonl"
    _write_jsonl(run, _fixture_rows())
    records = t100c.build_row_records(t100c.load_jsonl(run), artifact=run)

    bottlenecks = t100c.runtime_bottlenecks(records)
    slowest = t100c.slowest_rows(records, limit=2)

    assert bottlenecks["e2e_time_s"]["max"] > bottlenecks["e2e_time_s"]["avg"]
    assert bottlenecks["tokens_per_second"]["min"] == 30.0
    assert bottlenecks["failure_latency_correlation"]["failure_row_count"] == 3
    assert slowest[0]["fixture_id"] == "gsm8k_short_test_0002"


def test_claim_risk_register_and_recommendation_proceed_to_t101(tmp_path: Path) -> None:
    run = tmp_path / "run.jsonl"
    _write_jsonl(run, _fixture_rows())
    records = t100c.build_row_records(t100c.load_jsonl(run), artifact=run)
    gap_summary = t100c.build_gap_summary(records, task100b_summary=_summary(run))
    risk_register = t100c.claim_risk_register(gap_summary)
    recommendation = t100c.build_recommendation(gap_summary, risk_register)

    risk_ids = {risk["risk_id"] for risk in risk_register["risks"]}
    assert "final_speedup_not_proven" in risk_ids
    assert "remaining_cap_limited_rows" in risk_ids
    assert recommendation["next_step"] == "T101_Final_Claim_Boundary_Audit"
    assert recommendation["recommend_another_benchmark_by_default"] is False
    assert recommendation["recommend_default_gpu_switch"] is False


def test_missing_fields_are_handled_safely(tmp_path: Path) -> None:
    run = tmp_path / "missing.jsonl"
    _write_jsonl(run, [{"condition": "CC-DFlash-R2", "expected_answer": "9"}])

    records = t100c.build_row_records(t100c.load_jsonl(run), artifact=run)
    gap_summary = t100c.build_gap_summary(records, task100b_summary={})

    assert records[0]["category"] == "answer_missing"
    assert gap_summary["runtime_bottlenecks"]["e2e_time_s"]["avg"] is None
    assert gap_summary["gpu_vram_stability"]["oom_or_cuda_failure"] is False


def test_no_model_loading_in_task100c_analyzer() -> None:
    source = inspect.getsource(t100c)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
