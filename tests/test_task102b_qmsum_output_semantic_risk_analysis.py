from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task102b_qmsum_output_semantic_risk_analysis as t102b


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _row(
    index: int,
    *,
    generated_text: str = "The team chose red and yellow because they match the company color and attract customers.",
    expected_answer: str = "The team chose yellow because it was the company colour and red because it was attractive to customers.",
    output_tokens: int = 18,
    max_new_tokens: int = 384,
) -> dict[str, object]:
    return {
        "condition": "CC-DFlash-R2",
        "fixture_id": f"qmsum_{index:04d}",
        "dataset_name": "qmsum_meeting_qa_long",
        "question": "Why did the team choose red and yellow?",
        "expected_answer": expected_answer,
        "evidence": "Expected answer is the QMSum meeting QA reference answer or summary.",
        "original_prompt_preview": "The meeting says yellow is the company colour and red attracts customers.",
        "compressed_prompt_preview": "yellow company colour red attracts customers",
        "generated_text": generated_text,
        "generated_token_count": output_tokens,
        "output_tokens": output_tokens,
        "max_new_tokens": max_new_tokens,
        "generation_time_s": 4.0 + index,
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
    }


def test_analyzer_writes_expected_outputs_and_labels_fixture_rows(tmp_path: Path) -> None:
    artifact = tmp_path / "qmsum.jsonl"
    rows = [
        _row(1),
        _row(2, generated_text=""),
        _row(3, generated_text="The answer is incomplete and", output_tokens=383),
        _row(4, generated_text="Generic summary of the meeting.", expected_answer="solar energy helps remote users recharge and attracts ecologists"),
    ]
    _write_jsonl(artifact, rows)

    result = t102b.analyze(qmsum_jsonl=artifact, output_dir=tmp_path / "out")

    assert result["decision"] == "PASS_WITH_CAVEAT"
    assert result["summary"]["row_count"] == 4
    assert result["summary"]["label_counts"]["empty_or_malformed"] == 1
    assert result["summary"]["label_counts"]["cap_limited_or_incomplete"] == 1
    assert result["summary"]["label_counts"]["low_reference_overlap"] >= 1
    assert result["summary"]["label_counts"]["acceptable_proxy_signal"] >= 1
    for relative in t102b.OUTPUT_RELATIVE_PATHS:
        assert (tmp_path / "out" / relative).exists()


def test_row_classifier_labels_empty_cap_low_overlap_and_acceptable() -> None:
    acceptable = t102b.label_row(_row(1))
    empty = t102b.label_row(_row(2, generated_text=" "))
    cap = t102b.label_row(_row(3, generated_text="The answer ends with", output_tokens=384))
    low = t102b.label_row(_row(4, generated_text="Unrelated generic meeting summary.", expected_answer="solar remote ecologists recharge"))

    assert acceptable["labels"]["completed_answer"] is True
    assert acceptable["labels"]["acceptable_proxy_signal"] is True
    assert empty["labels"]["empty_or_malformed"] is True
    assert cap["labels"]["cap_limited_or_incomplete"] is True
    assert low["labels"]["low_reference_overlap"] is True


def test_runtime_stats_and_slowest_rows_are_computed(tmp_path: Path) -> None:
    artifact = tmp_path / "qmsum.jsonl"
    _write_jsonl(artifact, [_row(1), _row(2), _row(3)])

    rows = [t102b.label_row(row) for row in t102b.read_jsonl(artifact)]
    runtime = t102b.build_runtime_summary(rows)

    assert runtime["stats"]["t_compress_ms"]["avg"] == 122.0
    assert runtime["stats"]["e2e_time_s"]["max"] == 7.0
    assert runtime["slowest_rows"][0]["fixture_id"] == "qmsum_0003"


def test_claim_update_preserves_boundaries() -> None:
    summary = {
        "row_count": 30,
        "label_counts": {
            "empty_or_malformed": 0,
            "cap_limited_or_incomplete": 0,
            "low_reference_overlap": 12,
            "proxy_uncertain": 3,
        },
        "metadata": {
            "compressor_profile": ["light"],
            "compressor_device_map": ["cuda"],
            "local_files_only": [True],
        },
        "failure_flags": 0,
    }

    claim_update = t102b.build_claim_update(summary)

    assert claim_update["QMSum claim"]["status"] == "CLOSED_AS_BENCHMARK_SCOPED_PROXY_AUDIT"
    assert "QMSum semantic correctness is proven." in claim_update["QMSum claim"]["blocked_wording"]
    assert claim_update["Local 8GB-class feasibility"]["status"] == "STRENGTHENED_LOCAL_OBSERVATION"
    assert "Universal 8GB deployment readiness is proven." in claim_update["Local 8GB-class feasibility"]["blocked_wording"]
    assert claim_update["DFlash-R1 broken"]["status"] == "REMOVED"


def test_next_task_is_t103_when_analysis_is_usable() -> None:
    summary = {
        "row_count": 30,
        "label_counts": {
            "empty_or_malformed": 0,
            "cap_limited_or_incomplete": 0,
            "proxy_uncertain": 2,
        },
        "metadata_confirms_light_gpu": True,
        "failure_flags": 0,
    }

    decision = t102b.build_next_task_decision(summary)

    assert decision["next_task"] == "T103 — Reference Alignment for Speed Claim"
    assert "complete enough" in decision["reason"]


def test_next_task_is_t102a_for_severe_issues() -> None:
    summary = {
        "row_count": 30,
        "label_counts": {
            "empty_or_malformed": 5,
            "cap_limited_or_incomplete": 20,
            "proxy_uncertain": 25,
        },
        "metadata_confirms_light_gpu": False,
        "failure_flags": 1,
    }

    decision = t102b.build_next_task_decision(summary)

    assert decision["next_task"] == "T102A — QMSum Failure Audit / Fix"


def test_no_model_loading_in_task102b_analyzer() -> None:
    source = inspect.getsource(t102b)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
