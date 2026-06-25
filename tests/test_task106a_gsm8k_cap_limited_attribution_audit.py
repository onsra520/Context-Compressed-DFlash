from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import (
    task106a_gsm8k_cap_limited_attribution_audit as t106a,
)


EXPECTED_IDS = [f"gsm8k_{index:04d}" for index in range(1, 6)]


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _strict_row(fixture_id: str, answer: int = 42, *, condition: str = "Baseline-AR") -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "condition": condition,
        "expected_answer": str(answer),
        "generated_text": f"We solve the arithmetic carefully. Final answer: {answer}",
        "output_tokens": 32,
        "max_new_tokens": 256,
        "e2e_time_s": 2.0,
        "tokens_per_second": 60.0,
    }


def _wrong_row(fixture_id: str, *, condition: str = "CC-DFlash-R2") -> dict[str, object]:
    row = _strict_row(fixture_id, 42, condition=condition)
    row["generated_text"] = "The calculation is close. Final answer: 41"
    return row


def _cap_row(
    fixture_id: str,
    *,
    condition: str = "CC-DFlash-R2",
    include_expected_in_tail: bool = False,
    output_tokens: int = 256,
) -> dict[str, object]:
    tail = " The hidden correct number is 42" if include_expected_in_tail else ""
    repeated = " ".join(["reasoning"] * 80)
    return {
        "fixture_id": fixture_id,
        "condition": condition,
        "expected_answer": "42",
        "generated_text": f"{repeated} and then the computation continues without a final marker{tail}",
        "output_tokens": output_tokens,
        "max_new_tokens": 256,
        "t_compress_ms": 17.0,
        "e2e_time_s": 2.9,
        "tokens_per_second": 58.0,
        "R_actual": 2.0,
    }


def _fixture_inputs(tmp_path: Path) -> dict[str, Path]:
    baseline = [
        _strict_row("gsm8k_0001", condition="Baseline-AR"),
        _strict_row("gsm8k_0002", condition="Baseline-AR"),
        _cap_row("gsm8k_0003", condition="Baseline-AR"),
        _strict_row("gsm8k_0004", condition="Baseline-AR"),
        _strict_row("gsm8k_0005", condition="Baseline-AR"),
    ]
    dflash = [
        _strict_row("gsm8k_0001", condition="DFlash-R1"),
        _strict_row("gsm8k_0002", condition="DFlash-R1"),
        _cap_row("gsm8k_0003", condition="DFlash-R1"),
        _strict_row("gsm8k_0004", condition="DFlash-R1"),
        _strict_row("gsm8k_0005", condition="DFlash-R1"),
    ]
    cc = [
        _strict_row("gsm8k_0001", condition="CC-DFlash-R2"),
        _cap_row("gsm8k_0002", include_expected_in_tail=True),
        _cap_row("gsm8k_0003"),
        _wrong_row("gsm8k_0004"),
        _strict_row("gsm8k_0005", condition="CC-DFlash-R2"),
    ]
    t100b = [
        _strict_row("gsm8k_0001", condition="CC-DFlash-R2"),
        _cap_row("gsm8k_0002"),
        _cap_row("gsm8k_0003"),
        _wrong_row("gsm8k_0004"),
        _strict_row("gsm8k_0005", condition="CC-DFlash-R2"),
    ]
    paths = {
        "baseline_jsonl": tmp_path / "baseline.jsonl",
        "dflash_jsonl": tmp_path / "dflash.jsonl",
        "cc_jsonl": tmp_path / "cc.jsonl",
        "t100b_jsonl": tmp_path / "t100b.jsonl",
    }
    _write_jsonl(paths["baseline_jsonl"], baseline)
    _write_jsonl(paths["dflash_jsonl"], dflash)
    _write_jsonl(paths["cc_jsonl"], cc)
    _write_jsonl(paths["t100b_jsonl"], t100b)
    return paths


def test_audit_writes_required_artifacts_and_detects_overlap(tmp_path: Path) -> None:
    paths = _fixture_inputs(tmp_path)

    result = t106a.analyze(output_dir=tmp_path / "out", **paths)

    assert result["decision"] == "PASS_WITH_CAVEAT"
    assert result["condition_summaries"]["CC-DFlash-R2 Light GPU"]["cap_limited_incomplete_count"] == 2
    overlap = result["cap_limited_fixture_overlap"]
    assert overlap["cc_only_ids"] == ["gsm8k_0002"]
    assert overlap["shared_by_all_three_ids"] == ["gsm8k_0003"]
    assert overlap["cc_shared_with_any_reference_ids"] == ["gsm8k_0003"]
    for relpath in [
        "summary/task106a_audit_summary.json",
        "summary/task106a_cap_limited_fixture_overlap.json",
        "summary/task106a_cc_cap_limited_row_audit.jsonl",
        "summary/task106a_attribution_counts.json",
        "summary/task106a_t100b_vs_t105a_stability.json",
        "summary/task106a_fix_options.json",
        "summary/task106a_claim_update.json",
        "summary/task106a_next_task_decision.json",
        "tables/task106a_cap_limited_attribution_table.csv",
    ]:
        assert (tmp_path / "out" / relpath).exists()


def test_t100b_vs_t105a_stability_detects_matching_cap_pattern(tmp_path: Path) -> None:
    paths = _fixture_inputs(tmp_path)

    result = t106a.analyze(output_dir=tmp_path / "out", **paths)
    stability = result["t100b_vs_t105a_stability"]

    assert stability["t100b_available"] is True
    assert stability["t100b_cap_limited_count"] == 2
    assert stability["t105a_cc_cap_limited_count"] == 2
    assert stability["shared_cap_limited_ids"] == ["gsm8k_0002", "gsm8k_0003"]
    assert stability["interpretation"] == "stable_repeated_cc_dflash_r2_light_gpu_pattern"


def test_row_attribution_separates_cc_only_from_shared_target_behavior(tmp_path: Path) -> None:
    paths = _fixture_inputs(tmp_path)

    result = t106a.analyze(output_dir=tmp_path / "out", **paths)
    rows = result["cc_cap_limited_row_audit"]
    by_id = {row["fixture_id"]: row for row in rows}

    assert by_id["gsm8k_0002"]["overlap_class"] == "cc_only"
    assert "truncated_before_final_answer" in by_id["gsm8k_0002"]["attribution_tags"]
    assert "final_answer_marker_missing" in by_id["gsm8k_0002"]["attribution_tags"]
    assert "expected_numeric_present_without_marker" in by_id["gsm8k_0002"]["attribution_tags"]
    assert by_id["gsm8k_0003"]["overlap_class"] == "shared_with_references"
    assert "shared_target_or_prompt_cap_behavior" in by_id["gsm8k_0003"]["attribution_tags"]


def test_fix_recommendation_routes_to_t106b_only_for_cc_specific_cap_pattern(tmp_path: Path) -> None:
    paths = _fixture_inputs(tmp_path)

    result = t106a.analyze(output_dir=tmp_path / "out", **paths)
    assert result["fix_options"]["recommended_next_task"] == "T106B"
    assert result["next_task_decision"]["next_task"].startswith("T106B")

    cc_rows = [_strict_row(fixture_id, condition="CC-DFlash-R2") for fixture_id in EXPECTED_IDS]
    cc_rows[2] = _cap_row("gsm8k_0003", condition="CC-DFlash-R2")
    _write_jsonl(paths["cc_jsonl"], cc_rows)
    result_shared_only = t106a.analyze(output_dir=tmp_path / "out2", **paths)

    assert result_shared_only["fix_options"]["recommended_next_task"] == "T106C"
    assert result_shared_only["next_task_decision"]["next_task"].startswith("T106C")


def test_module_does_not_import_model_or_cuda_libraries() -> None:
    source = inspect.getsource(t106a)

    assert "import torch" not in source
    assert "from transformers" not in source
    assert "AutoModel" not in source
