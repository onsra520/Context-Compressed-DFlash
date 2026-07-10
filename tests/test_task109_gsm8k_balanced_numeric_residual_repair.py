from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

import scripts.run_mvp as run_mvp
from scripts.phase_2_system_optimization.analysis import task109_gsm8k_balanced_numeric_residual_repair as t109


POLICY_NAME = "gsm8k_numeric_detail_preserve_v1"
POLICY_SUFFIX = (
    "Use only the numbers and conditions given in the problem. Keep the reasoning concise but "
    "include all necessary arithmetic steps. Do not skip units or constraints. End with exactly "
    "one line in the format: Final answer: <number>. Do not continue after the final answer."
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
    output_tokens: int = 88,
    generation_time_s: float = 2.0,
    t_compress_ms: float = 15.0,
    policy_name: str = POLICY_NAME,
    policy_ok: bool = True,
) -> dict[str, object]:
    return {
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
        "gsm8k_answer_policy_type": policy_name,
        "gsm8k_answer_policy_preserved": policy_ok,
        "gsm8k_policy_suffix_override": policy_ok,
        "gsm8k_output_policy_preview": POLICY_SUFFIX,
    }


def test_runtime_gsm8k_policy_override_accepts_numeric_detail_policy(tmp_path: Path) -> None:
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


def test_cli_accepts_gsm8k_policy_for_non_cc_dflash_condition() -> None:
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


def test_analyzer_selects_t109_when_quality_improves(tmp_path: Path) -> None:
    t105a = tmp_path / "t105a.jsonl"
    t106b = tmp_path / "t106b.jsonl"
    t107b = tmp_path / "t107b.jsonl"
    t109_file = tmp_path / "t109.jsonl"
    baseline = tmp_path / "baseline.jsonl"
    dflash = tmp_path / "dflash.jsonl"
    out = tmp_path / "out"
    
    t105a_rows = []
    t106b_rows = []
    t107b_rows = []
    t109_rows = []
    for i in range(1, 101):
        fid = f"gsm8k_short_test_{i:04d}"
        if i == 1:
            t105a_rows.append(_run_row(fid, "long " * 90, output_tokens=256, policy_ok=False))
            t106b_rows.append(_run_row(fid, "concise work. Final answer: 42", policy_name="gsm8k_concise_final_answer_v1"))
            t107b_rows.append(_run_row(fid, "verified. Final answer: 42", policy_name="gsm8k_minimal_arithmetic_verify_v1"))
            t109_rows.append(_run_row(fid, "detailed. Final answer: 42"))
        elif i == 2:
            t105a_rows.append(_run_row(fid, "bad math. Final answer: 41", policy_ok=False))
            t106b_rows.append(_run_row(fid, "bad math. Final answer: 41", policy_name="gsm8k_concise_final_answer_v1"))
            t107b_rows.append(_run_row(fid, "verified. Final answer: 41", policy_name="gsm8k_minimal_arithmetic_verify_v1"))
            t109_rows.append(_run_row(fid, "detailed. Final answer: 42"))
        elif i == 3:
            t105a_rows.append(_run_row(fid, "work. Final answer: 42", policy_ok=False))
            t106b_rows.append(_run_row(fid, "bad work. Final answer: 43", policy_name="gsm8k_concise_final_answer_v1"))
            t107b_rows.append(_run_row(fid, "verified. Final answer: 43", policy_name="gsm8k_minimal_arithmetic_verify_v1"))
            t109_rows.append(_run_row(fid, "detailed. Final answer: 42"))
        else:
            t105a_rows.append(_run_row(fid, "work. Final answer: 42", policy_ok=False))
            t106b_rows.append(_run_row(fid, "work. Final answer: 42", policy_name="gsm8k_concise_final_answer_v1"))
            t107b_rows.append(_run_row(fid, "work. Final answer: 42", policy_name="gsm8k_minimal_arithmetic_verify_v1"))
            t109_rows.append(_run_row(fid, "work. Final answer: 42"))

    _write_jsonl(t105a, t105a_rows)
    _write_jsonl(t106b, t106b_rows)
    _write_jsonl(t107b, t107b_rows)
    _write_jsonl(t109_file, t109_rows)

    result = t109.analyze(
        t105a_jsonl=t105a,
        t106b_jsonl=t106b,
        t107b_jsonl=t107b,
        t109_jsonl=t109_file,
        output_dir=out,
        expected_n=100,
        baseline_jsonl=baseline,
        dflash_jsonl=dflash,
    )

    assert result["decision"] == "PASS_WITH_CAVEAT"
    assert result["policy_decision"]["rerun_justified"] is True
    assert result["balanced_candidate_decision"]["selected_candidate"] == "T109"
    assert result["balanced_candidate_decision"]["candidate_policy_name"] == POLICY_NAME
    assert result["metadata_audit"]["valid"] is True
    
    for relative in t109.OUTPUT_RELATIVE_PATHS:
        assert (out / relative).exists()


def test_analyzer_keeps_t106b_when_strict_drops(tmp_path: Path) -> None:
    t105a = tmp_path / "t105a.jsonl"
    t106b = tmp_path / "t106b.jsonl"
    t107b = tmp_path / "t107b.jsonl"
    t109_file = tmp_path / "t109.jsonl"
    out = tmp_path / "out"
    
    _write_jsonl(t105a, [_run_row("gsm8k_short_test_0001", "Final answer: 42", policy_ok=False)])
    _write_jsonl(t106b, [_run_row("gsm8k_short_test_0001", "Final answer: 42", policy_name="gsm8k_concise_final_answer_v1")])
    _write_jsonl(t107b, [_run_row("gsm8k_short_test_0001", "Final answer: 42", policy_name="gsm8k_minimal_arithmetic_verify_v1")])
    _write_jsonl(t109_file, [_run_row("gsm8k_short_test_0001", "Final answer: 41")]) # lower strict

    result = t109.analyze(
        t105a_jsonl=t105a, t106b_jsonl=t106b, t107b_jsonl=t107b, t109_jsonl=t109_file,
        output_dir=out, expected_n=1, baseline_jsonl=tmp_path/"b", dflash_jsonl=tmp_path/"d"
    )

    assert result["balanced_candidate_decision"]["selected_candidate"] == "T106B"
    assert result["balanced_candidate_decision"]["candidate_policy_name"] == "gsm8k_concise_final_answer_v1"


def test_analyzer_audit_only_when_no_t109_data(tmp_path: Path) -> None:
    t105a = tmp_path / "t105a.jsonl"
    t106b = tmp_path / "t106b.jsonl"
    t107b = tmp_path / "t107b.jsonl"
    out = tmp_path / "out"
    
    _write_jsonl(t105a, [_run_row("gsm8k_short_test_0001", "Final answer: 42", policy_ok=False)])
    _write_jsonl(t106b, [_run_row("gsm8k_short_test_0001", "Final answer: 42", policy_name="gsm8k_concise_final_answer_v1")])
    _write_jsonl(t107b, [_run_row("gsm8k_short_test_0001", "Final answer: 42", policy_name="gsm8k_minimal_arithmetic_verify_v1")])

    result = t109.analyze(
        t105a_jsonl=t105a, t106b_jsonl=t106b, t107b_jsonl=t107b, t109_jsonl=tmp_path/"missing.jsonl",
        output_dir=out, expected_n=1, baseline_jsonl=tmp_path/"b", dflash_jsonl=tmp_path/"d"
    )

    assert result["decision"] == "AUDIT_ONLY"
    assert result["balanced_candidate_decision"]["selected_candidate"] == "T106B"
    assert "audit_only" in result["balanced_candidate_decision"]["reason"]


def test_analyzer_detects_metadata_policy_mismatch(tmp_path: Path) -> None:
    t105a = tmp_path / "t105a.jsonl"
    t106b = tmp_path / "t106b.jsonl"
    t107b = tmp_path / "t107b.jsonl"
    t109_file = tmp_path / "t109.jsonl"
    out = tmp_path / "out"
    
    _write_jsonl(t105a, [_run_row("gsm8k_short_test_0001", "Final answer: 42", policy_ok=False)])
    _write_jsonl(t106b, [_run_row("gsm8k_short_test_0001", "Final answer: 42", policy_name="gsm8k_concise_final_answer_v1")])
    _write_jsonl(t107b, [_run_row("gsm8k_short_test_0001", "Final answer: 42", policy_name="gsm8k_minimal_arithmetic_verify_v1")])
    
    bad_row = _run_row("gsm8k_short_test_0001", "Final answer: 42", policy_name="wrong_policy")
    _write_jsonl(t109_file, [bad_row])

    result = t109.analyze(
        t105a_jsonl=t105a, t106b_jsonl=t106b, t107b_jsonl=t107b, t109_jsonl=t109_file,
        output_dir=out, expected_n=1, baseline_jsonl=tmp_path/"b", dflash_jsonl=tmp_path/"d"
    )

    assert result["decision"] == "PARTIAL"
    assert result["metadata_audit"]["valid"] is False
    assert "policy type mismatch" in " ".join(result["metadata_audit"]["errors"])


def test_task109_analyzer_does_not_import_model_or_cuda_libraries() -> None:
    source = inspect.getsource(t109)
    assert "import torch" not in source
    assert "from torch" not in source
    assert "transformers" not in source
    assert "AutoModel" not in source
