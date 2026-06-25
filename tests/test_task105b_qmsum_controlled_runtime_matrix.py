from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task105b_qmsum_controlled_runtime_matrix as t105b


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _row(
    condition: str,
    index: int,
    *,
    generation_time_s: float,
    tokens_per_second: float,
    generated_text: str = "The answer cites concrete meeting evidence.",
    output_tokens: int = 96,
    tau_mean: float = 0.0,
    t_compress_ms: float | None = None,
    r_actual: float | None = None,
    compressor_profile: str | None = None,
    compressor_device_map: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "fixture_id": f"qmsum_meeting_qa_test_{index:04d}",
        "dataset_id": f"qmsum_meeting_qa_test_{index:04d}",
        "prompt_id": index,
        "benchmark_prompt_index": index,
        "condition": condition,
        "dataset_name": "qmsum_meeting_qa_long",
        "prompt_source": "dataset",
        "expected_answer": "The meeting reference mentions budget, schedule, and design decisions.",
        "generated_text": generated_text,
        "max_new_tokens": 384,
        "output_tokens": output_tokens,
        "generated_token_count": output_tokens,
        "generation_time_s": generation_time_s,
        "tokens_per_second": tokens_per_second,
        "tok_per_sec": tokens_per_second,
        "tau_mean": tau_mean,
        "t_prefill_ms": 100.0,
        "vram_allocated_gib": 3.0,
        "vram_reserved_gib": 3.5,
        "prefill_vram_allocated_gib": 3.0,
        "prefill_vram_reserved_gib": 3.5,
        "resume_enabled": True,
        "resumed_from_rows": 0,
        "quality_policy": "normalized_text_containment_proxy",
    }
    if t_compress_ms is not None:
        row["t_compress_ms"] = t_compress_ms
    if r_actual is not None:
        row["R_actual"] = r_actual
        row["compression_ratio"] = r_actual
    if compressor_profile is not None:
        row["compression"] = "llmlingua"
        row["compressor_profile"] = compressor_profile
        row["compressor_path"] = "models/llmlingua-light"
        row["resolved_compressor_path"] = "/repo/models/llmlingua-light"
        row["local_files_only"] = True
        row["qmsum_answer_policy_enabled"] = True
        row["qmsum_answer_policy_type"] = "evidence_focused"
    if compressor_device_map is not None:
        row["compressor_device_map"] = compressor_device_map
        row["requested_compressor_device_map"] = compressor_device_map
    return row


def _write_complete_matrix(tmp_path: Path) -> tuple[Path, Path, Path]:
    baseline = tmp_path / "runs" / "baseline.jsonl"
    dflash = tmp_path / "runs" / "dflash.jsonl"
    optimized = tmp_path / "runs" / "optimized.jsonl"
    _write_jsonl(
        baseline,
        [
            _row("Baseline-AR", 1, generation_time_s=5.0, tokens_per_second=20.0),
            _row("Baseline-AR", 2, generation_time_s=5.2, tokens_per_second=21.0),
            _row("Baseline-AR", 3, generation_time_s=5.4, tokens_per_second=22.0),
        ],
    )
    _write_jsonl(
        dflash,
        [
            _row("DFlash-R1", 1, generation_time_s=4.2, tokens_per_second=24.0, tau_mean=2.0),
            _row("DFlash-R1", 2, generation_time_s=4.4, tokens_per_second=25.0, tau_mean=2.1),
            _row("DFlash-R1", 3, generation_time_s=4.6, tokens_per_second=26.0, tau_mean=2.2),
        ],
    )
    _write_jsonl(
        optimized,
        [
            _row(
                "CC-DFlash-R2",
                1,
                generation_time_s=3.2,
                tokens_per_second=30.0,
                tau_mean=2.2,
                t_compress_ms=100.0,
                r_actual=2.1,
                compressor_profile="light",
                compressor_device_map="cuda",
            ),
            _row(
                "CC-DFlash-R2",
                2,
                generation_time_s=3.4,
                tokens_per_second=31.0,
                tau_mean=2.3,
                t_compress_ms=110.0,
                r_actual=2.2,
                compressor_profile="light",
                compressor_device_map="cuda",
            ),
            _row(
                "CC-DFlash-R2",
                3,
                generation_time_s=3.6,
                tokens_per_second=32.0,
                tau_mean=2.4,
                t_compress_ms=120.0,
                r_actual=2.3,
                compressor_profile="light",
                compressor_device_map="cuda",
            ),
        ],
    )
    return baseline, dflash, optimized


def test_analyzer_writes_required_outputs_and_ranks_runtime(tmp_path: Path) -> None:
    baseline, dflash, optimized = _write_complete_matrix(tmp_path)

    result = t105b.analyze(
        baseline_jsonl=baseline,
        dflash_jsonl=dflash,
        optimized_jsonl=optimized,
        output_dir=tmp_path / "out",
        expected_n=3,
    )

    assert result["decision"] == "PASS_WITH_CAVEAT"
    assert result["controlled_matrix_complete"] is True
    assert result["conditions"]["CC-DFlash-R2 Light GPU"]["metadata_ok"] is True
    assert result["conditions"]["CC-DFlash-R2 Light GPU"]["avg_t_compress_ms"] == 110.0
    assert result["runtime_ranking"]["ranked_conditions"][0]["condition"] == "CC-DFlash-R2 Light GPU"
    assert result["claim_update"]["qmsum_semantic_correctness_claim"] == "blocked"
    assert result["next_task_decision"]["next_task"].startswith("T105C")
    assert (tmp_path / "out" / "summary" / "task105b_matrix_summary.json").exists()
    assert (tmp_path / "out" / "summary" / "task105b_condition_metrics.json").exists()
    assert (tmp_path / "out" / "summary" / "task105b_runtime_ranking.json").exists()
    assert (tmp_path / "out" / "summary" / "task105b_output_completeness_summary.json").exists()
    assert (tmp_path / "out" / "summary" / "task105b_failure_or_resume_audit.json").exists()
    assert (tmp_path / "out" / "summary" / "task105b_qmsum_caveat_carryforward.json").exists()
    assert (tmp_path / "out" / "summary" / "task105b_claim_update.json").exists()
    assert (tmp_path / "out" / "summary" / "task105b_next_task_decision.json").exists()
    assert (tmp_path / "out" / "tables" / "task105b_qmsum_controlled_runtime_matrix.csv").exists()


def test_incomplete_condition_routes_to_t105b_resume(tmp_path: Path) -> None:
    baseline, dflash, optimized = _write_complete_matrix(tmp_path)
    _write_jsonl(dflash, [_row("DFlash-R1", 1, generation_time_s=4.2, tokens_per_second=24.0)])

    result = t105b.analyze(
        baseline_jsonl=baseline,
        dflash_jsonl=dflash,
        optimized_jsonl=optimized,
        output_dir=tmp_path / "out",
        expected_n=3,
    )

    assert result["decision"] == "PARTIAL"
    assert result["controlled_matrix_complete"] is False
    assert result["failure_or_resume_audit"]["conditions"]["DFlash-R1"]["row_count_ok"] is False
    assert result["next_task_decision"]["next_task"].startswith("T105B-R")


def test_optimized_metadata_mismatch_blocks_complete_matrix(tmp_path: Path) -> None:
    baseline, dflash, optimized = _write_complete_matrix(tmp_path)
    rows = [json.loads(line) for line in optimized.read_text(encoding="utf-8").splitlines()]
    rows[0]["compressor_device_map"] = "cpu"
    _write_jsonl(optimized, rows)

    result = t105b.analyze(
        baseline_jsonl=baseline,
        dflash_jsonl=dflash,
        optimized_jsonl=optimized,
        output_dir=tmp_path / "out",
        expected_n=3,
    )

    assert result["decision"] == "PARTIAL"
    assert result["conditions"]["CC-DFlash-R2 Light GPU"]["metadata_ok"] is False
    assert "metadata mismatch" in result["failure_or_resume_audit"]["conditions"]["CC-DFlash-R2 Light GPU"]["notes"]


def test_cap_limited_outputs_preserve_qmsum_caveat(tmp_path: Path) -> None:
    baseline, dflash, optimized = _write_complete_matrix(tmp_path)
    rows = [json.loads(line) for line in optimized.read_text(encoding="utf-8").splitlines()]
    rows[0]["output_tokens"] = 384
    rows[0]["generated_token_count"] = 384
    rows[0]["generated_text"] = "This answer appears to continue and"
    _write_jsonl(optimized, rows)

    result = t105b.analyze(
        baseline_jsonl=baseline,
        dflash_jsonl=dflash,
        optimized_jsonl=optimized,
        output_dir=tmp_path / "out",
        expected_n=3,
    )

    completeness = result["output_completeness_summary"]["conditions"]["CC-DFlash-R2 Light GPU"]
    assert completeness["cap_limited_or_incomplete_count"] == 1
    assert result["claim_update"]["qmsum_semantic_correctness_claim"] == "blocked"
    assert result["claim_update"]["quality_caveat_required"] is True


def test_analyzer_module_does_not_import_model_stacks() -> None:
    source = inspect.getsource(t105b)
    assert "import torch" not in source
    assert "transformers" not in source
