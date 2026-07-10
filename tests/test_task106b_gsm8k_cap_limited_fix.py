from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

import scripts.run_mvp as run_mvp
from scripts.phase_2_system_optimization.analysis import task106b_gsm8k_cap_limited_fix as t106b


POLICY_NAME = "gsm8k_concise_final_answer_v1"
POLICY_SUFFIX = (
    "Keep the solution concise. End with exactly one line in the format: "
    "Final answer: <number>. Do not continue after the final answer."
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _dataset_row(fixture_id: str, answer: str = "42") -> dict[str, object]:
    return {
        "id": fixture_id,
        "context": f"Question context for {fixture_id}.",
        "question": "What is the answer?",
        "expected_answer": answer,
        "prompt": f"Question context for {fixture_id}.\n\nQuestion: What is the answer?",
    }


def _run_row(
    fixture_id: str,
    generated: str,
    *,
    condition: str = "CC-DFlash-R2",
    output_tokens: int = 96,
    generation_time_s: float = 2.0,
    t_compress_ms: float = 15.0,
    policy_ok: bool = True,
) -> dict[str, object]:
    row: dict[str, object] = {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "condition": condition,
        "dataset_name": "gsm8k_short",
        "prompt_source": "dataset",
        "expected_answer": "42",
        "generated_text": generated,
        "output_tokens": output_tokens,
        "generated_token_count": output_tokens,
        "max_new_tokens": 256,
        "generation_time_s": generation_time_s,
        "tok_per_sec": 60.0,
        "tokens_per_second": 60.0,
        "tau_mean": 5.5,
        "t_prefill_ms": 90.0,
        "t_compress_ms": t_compress_ms,
        "R_actual": 2.0,
        "vram_allocated_gib": 3.9,
        "vram_reserved_gib": 4.4,
        "prefill_vram_allocated_gib": 3.8,
        "prefill_vram_reserved_gib": 4.3,
        "compressor_profile": "light",
        "compressor_device_map": "cuda",
        "requested_compressor_device_map": "cuda",
        "local_files_only": True,
        "gsm8k_answer_policy_enabled": True,
        "gsm8k_answer_policy_type": POLICY_NAME,
        "gsm8k_answer_policy_preserved": policy_ok,
        "gsm8k_policy_suffix_override": policy_ok,
        "gsm8k_output_policy_preview": POLICY_SUFFIX,
    }
    return row


def test_gsm8k_policy_override_is_dataset_scoped_and_records_metadata(tmp_path: Path) -> None:
    dataset = tmp_path / "gsm8k.jsonl"
    _write_jsonl(dataset, [_dataset_row("gsm8k_short_test_0001")])

    items = run_mvp._select_prompt_items(
        prompt_source="dataset",
        n_prompts=1,
        fixture_path=None,
        dataset_name="gsm8k_short",
        dataset_path=dataset,
        seed=42,
        gsm8k_policy_suffix=POLICY_SUFFIX,
        gsm8k_policy_name=POLICY_NAME,
    )

    item = items[0]
    assert item.protected_suffix == POLICY_SUFFIX
    assert POLICY_SUFFIX in item.text
    assert item.metadata["gsm8k_policy_suffix_override"] is True
    assert item.metadata["gsm8k_answer_policy_type"] == POLICY_NAME
    assert item.gsm8k_policy_suffix_override is True
    assert item.gsm8k_policy_name == POLICY_NAME


def test_qmsum_policy_override_does_not_set_gsm8k_metadata(tmp_path: Path) -> None:
    dataset = tmp_path / "qmsum.jsonl"
    _write_jsonl(dataset, [_dataset_row("qmsum_meeting_qa_test_0001", answer="reference")])

    items = run_mvp._select_prompt_items(
        prompt_source="dataset",
        n_prompts=1,
        fixture_path=None,
        dataset_name="qmsum_meeting_qa_long",
        dataset_path=dataset,
        seed=42,
        qmsum_policy_suffix="Answer briefly.",
        qmsum_policy_name="qmsum_custom",
    )

    assert "qmsum_policy_suffix_override" in items[0].metadata
    assert "gsm8k_policy_suffix_override" not in items[0].metadata


def test_cli_rejects_gsm8k_policy_for_non_gsm8k_dataset() -> None:
    with pytest.raises(SystemExit):
        run_mvp.parse_args(
            [
                "--condition",
                "CC-DFlash-R2",
                "--dataset",
                "qmsum_meeting_qa_long",
                "--gsm8k-policy-suffix",
                POLICY_SUFFIX,
            ]
        )


def test_cli_accepts_gsm8k_policy_for_uncompressed_gsm8k_condition() -> None:
    args = run_mvp.parse_args(
        [
            "--condition",
            "Baseline-AR",
            "--dataset",
            "gsm8k_short",
            "--gsm8k-policy-suffix",
            POLICY_SUFFIX,
            "--gsm8k-policy-name",
            POLICY_NAME,
        ]
    )

    assert args.gsm8k_policy_suffix == POLICY_SUFFIX
    assert args.gsm8k_policy_name == POLICY_NAME


def test_analyzer_writes_outputs_and_detects_cap_limited_improvement(tmp_path: Path) -> None:
    before = tmp_path / "before.jsonl"
    after = tmp_path / "after.jsonl"
    out = tmp_path / "out"
    _write_jsonl(
        before,
        [
            _run_row("gsm8k_short_test_0001", "reasoning " * 90, output_tokens=256, policy_ok=False),
            _run_row("gsm8k_short_test_0002", "bad math. Final answer: 41"),
            _run_row("gsm8k_short_test_0003", "work. Final answer: 42"),
        ],
    )
    _write_jsonl(
        after,
        [
            _run_row("gsm8k_short_test_0001", "concise work. Final answer: 42", output_tokens=48),
            _run_row("gsm8k_short_test_0002", "bad math. Final answer: 41"),
            _run_row("gsm8k_short_test_0003", "work. Final answer: 42"),
        ],
    )

    result = t106b.analyze(before_jsonl=before, fixed_jsonl=after, output_dir=out, expected_n=3)

    assert result["decision"] == "PASS_WITH_CAVEAT"
    assert result["cap_limited_delta"]["before_cap_limited_count"] == 1
    assert result["cap_limited_delta"]["fixed_cap_limited_count"] == 0
    assert result["quality_proxy_delta"]["strict_correct_delta"] == 1
    assert result["metadata_audit"]["valid"] is True
    assert result["next_task_decision"]["next_task"].startswith("T106C")
    for relative in t106b.OUTPUT_RELATIVE_PATHS:
        assert (out / relative).exists()


def test_analyzer_marks_no_improvement_as_candidate_only(tmp_path: Path) -> None:
    before = tmp_path / "before.jsonl"
    after = tmp_path / "after.jsonl"
    out = tmp_path / "out"
    rows = [
        _run_row("gsm8k_short_test_0001", "reasoning " * 90, output_tokens=256),
        _run_row("gsm8k_short_test_0002", "bad math. Final answer: 41"),
    ]
    _write_jsonl(before, rows)
    _write_jsonl(after, rows)

    result = t106b.analyze(before_jsonl=before, fixed_jsonl=after, output_dir=out, expected_n=2)

    assert result["decision"] == "PASS_WITH_CAVEAT"
    assert result["fix_interpretation"] == "fix_not_supported"
    assert result["claim_update"]["quality_preserved_claim"] == "blocked"


def test_analyzer_detects_missing_policy_metadata(tmp_path: Path) -> None:
    before = tmp_path / "before.jsonl"
    after = tmp_path / "after.jsonl"
    out = tmp_path / "out"
    _write_jsonl(before, [_run_row("gsm8k_short_test_0001", "Final answer: 42", policy_ok=False)])
    bad_after = _run_row("gsm8k_short_test_0001", "Final answer: 42", policy_ok=False)
    bad_after["gsm8k_answer_policy_enabled"] = False
    _write_jsonl(after, [bad_after])

    result = t106b.analyze(before_jsonl=before, fixed_jsonl=after, output_dir=out, expected_n=1)

    assert result["decision"] == "PARTIAL"
    assert result["metadata_audit"]["valid"] is False
    assert "gsm8k policy override" in " ".join(result["metadata_audit"]["errors"])


def test_task106b_analyzer_does_not_import_model_or_cuda_libraries() -> None:
    source = inspect.getsource(t106b)

    assert "import torch" not in source
    assert "from torch" not in source
    assert "transformers" not in source
    assert "AutoModel" not in source
