from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task102_qmsum_light_gpu_n30_feasibility_run as t102


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _row(index: int, *, generated_text: str = "Useful QMSum answer.") -> dict[str, object]:
    return {
        "condition": "CC-DFlash-R2",
        "prompt_id": index,
        "benchmark_prompt_index": index,
        "prompt_source": "dataset",
        "dataset_name": "qmsum_meeting_qa_long",
        "dataset_id": f"qmsum_meeting_qa_test_{index:04d}",
        "generated_text": generated_text,
        "generated_token_count": len(generated_text.split()),
        "output_tokens": len(generated_text.split()),
        "max_new_tokens": 384,
        "generation_time_s": 2.0 + index,
        "tokens_per_second": 20.0 + index,
        "tok_per_sec": 20.0 + index,
        "tau_mean": 2.0,
        "t_prefill_ms": 350.0 + index,
        "t_compress_ms": 120.0 + index,
        "R_actual": 2.1,
        "vram_allocated_gib": 4.16,
        "vram_reserved_gib": 5.4,
        "prefill_vram_allocated_gib": 4.16,
        "prefill_vram_reserved_gib": 5.4,
        "compressor_profile": "light",
        "compressor_device_map": "cuda",
        "requested_compressor_device_map": "cuda",
        "local_files_only": True,
        "qmsum_answer_policy_type": "evidence_focused",
        "qmsum_answer_policy_preserved": True,
    }


def test_analyzer_handles_qmsum_fixture_and_writes_expected_outputs(tmp_path: Path) -> None:
    smoke = tmp_path / "smoke.jsonl"
    n30 = tmp_path / "n30.jsonl"
    _write_jsonl(smoke, [_row(i) for i in range(1, 4)])
    _write_jsonl(n30, [_row(i) for i in range(1, 31)])

    result = t102.analyze(smoke_artifact=smoke, n30_artifact=n30, output_dir=tmp_path / "out")

    assert result["decision"] == "PASS_WITH_CAVEAT"
    assert result["run_status"]["smoke"]["row_count"] == 3
    assert result["run_status"]["n30"]["row_count"] == 30
    assert result["run_status"]["n30"]["run_complete"] is True
    for relative in t102.OUTPUT_RELATIVE_PATHS:
        assert (tmp_path / "out" / relative).exists()


def test_run_status_metadata_and_malformed_outputs_are_computed(tmp_path: Path) -> None:
    artifact = tmp_path / "bad.jsonl"
    _write_jsonl(artifact, [_row(1), _row(2, generated_text="")])

    status = t102.summarize_artifact(artifact, expected_rows=3, run_kind="smoke")

    assert status["row_count"] == 2
    assert status["run_complete"] is False
    assert status["empty_or_malformed_output_count"] == 1
    assert status["metadata"]["compressor_profile"] == ["light"]
    assert status["metadata"]["compressor_device_map"] == ["cuda"]
    assert status["metadata"]["local_files_only"] == [True]


def test_next_task_decision_is_t102b_on_completed_n30(tmp_path: Path) -> None:
    smoke = tmp_path / "smoke.jsonl"
    n30 = tmp_path / "n30.jsonl"
    _write_jsonl(smoke, [_row(i) for i in range(1, 4)])
    _write_jsonl(n30, [_row(i) for i in range(1, 31)])

    run_status = t102.build_run_status(smoke_artifact=smoke, n30_artifact=n30)
    decision = t102.build_next_task_decision(run_status)

    assert decision["next_task"] == "T102B — QMSum Output + Semantic-Risk / Proxy / Cap / Latency / VRAM Analysis"
    assert decision["reason"].startswith("QMSum Light GPU feasibility completed")


def test_next_task_decision_is_t102a_on_failure_or_block(tmp_path: Path) -> None:
    smoke = tmp_path / "smoke.jsonl"
    _write_jsonl(smoke, [_row(1)])

    run_status = t102.build_run_status(smoke_artifact=smoke, n30_artifact=None)
    decision = t102.build_next_task_decision(run_status)

    assert decision["next_task"] == "T102A — QMSum Failure Audit / Fix"
    assert "did not complete" in decision["reason"]


def test_claim_status_map_after_completed_feasibility_removes_dflash_broken_claim(tmp_path: Path) -> None:
    smoke = tmp_path / "smoke.jsonl"
    n30 = tmp_path / "n30.jsonl"
    _write_jsonl(smoke, [_row(i) for i in range(1, 4)])
    _write_jsonl(n30, [_row(i) for i in range(1, 31)])

    run_status = t102.build_run_status(smoke_artifact=smoke, n30_artifact=n30)
    claim_map = t102.build_claim_status_map(run_status)

    assert claim_map["QMSum Light GPU"]["status"] == "FEASIBILITY_COMPLETE_PENDING_T102B_ANALYSIS"
    assert claim_map["DFlash-R1 broken claim"]["status"] == "REMOVED"
    assert claim_map["DFlash-R1 broken claim"]["wording"] == "DFlash-R1 retained as reference condition"
    assert claim_map["Final Report Integration"]["active_phase2_next_task"] is False


def test_no_model_loading_in_task102_analyzer() -> None:
    source = inspect.getsource(t102)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
