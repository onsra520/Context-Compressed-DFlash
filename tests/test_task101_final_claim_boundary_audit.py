from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task101_final_claim_boundary_audit as t101


def _write_inputs(root: Path) -> dict[str, Path]:
    claim_language = root / "task100a_claim_language.json"
    task100b_summary = root / "task100b_summary.json"
    task100c_risks = root / "task100c_claim_risk_register.json"

    claim_language.write_text(
        json.dumps(
            {
                "allowed": [
                    "The light GPU placement path is a promising bounded candidate.",
                ],
                "blocked": [
                    "Final speedup is proven.",
                    "Final quality is proven.",
                    "Deployment readiness is proven.",
                ],
            }
        ),
        encoding="utf-8",
    )
    task100b_summary.write_text(
        json.dumps(
            {
                "light_gpu_n100": {
                    "row_count": 100,
                    "strict_correct_count": 79,
                    "cap_limited_incomplete_count": 15,
                    "final_answer_marker_count": 85,
                    "strict_wrong_numeric_count": 6,
                    "avg_t_compress_ms": 17.35,
                    "avg_e2e_time_s": 2.88,
                    "avg_tokens_per_second": 59.83,
                    "avg_R_actual": 2.0,
                    "max_vram_reserved_gib": 4.43,
                    "compressor_profile": "light",
                    "compressor_device_map": "cuda",
                    "local_files_only": True,
                }
            }
        ),
        encoding="utf-8",
    )
    task100c_risks.write_text(
        json.dumps(
            {
                "risks": [
                    {"risk_id": "final_speedup_not_proven", "blocked_claim": "final speedup is proven"},
                    {"risk_id": "final_quality_not_proven", "blocked_claim": "final quality is proven"},
                    {
                        "risk_id": "deployment_8gb_readiness_not_proven",
                        "blocked_claim": "deployment or 8GB readiness is proven",
                    },
                    {"risk_id": "full_benchmark_not_run", "blocked_claim": "full benchmark completed"},
                ]
            }
        ),
        encoding="utf-8",
    )
    return {
        "claim_language": claim_language,
        "task100b_summary": task100b_summary,
        "task100c_risks": task100c_risks,
    }


def test_script_writes_all_expected_artifacts(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    out = tmp_path / "out"

    result = t101.audit(
        task100a_claim_language=inputs["claim_language"],
        task100b_summary=inputs["task100b_summary"],
        task100c_claim_risk_register=inputs["task100c_risks"],
        output_dir=out,
    )

    assert result["decision"] == "PASS"
    for name in t101.OUTPUT_FILENAMES:
        assert (out / name).exists()


def test_matrix_includes_required_claim_areas(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)

    result = t101.audit(
        task100a_claim_language=inputs["claim_language"],
        task100b_summary=inputs["task100b_summary"],
        task100c_claim_risk_register=inputs["task100c_risks"],
        output_dir=tmp_path / "out",
    )

    claim_areas = {row["claim_area"] for row in result["claim_boundary_matrix"]["claims"]}
    assert claim_areas == {
        "Speed / latency",
        "Quality",
        "GPU / 8GB feasibility",
        "QMSum / long-context semantics",
        "DFlash-R1 comparison",
        "Compressor placement/default",
        "n100/full benchmark",
    }


def test_blocked_claims_cover_final_claims_and_default_gpu_switch(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    result = t101.audit(
        task100a_claim_language=inputs["claim_language"],
        task100b_summary=inputs["task100b_summary"],
        task100c_claim_risk_register=inputs["task100c_risks"],
        output_dir=tmp_path / "out",
    )

    blocked_text = " ".join(claim["claim"] for claim in result["blocked_claims"]["claims"]).lower()
    assert "final universal speedup" in blocked_text
    assert "final correctness" in blocked_text
    assert "deployment readiness" in blocked_text
    assert "qmsum semantic correctness" in blocked_text
    assert "full matrix" in blocked_text
    assert "gpu placement is now the default" in blocked_text


def test_allowed_claims_are_bounded_not_absolute(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    result = t101.audit(
        task100a_claim_language=inputs["claim_language"],
        task100b_summary=inputs["task100b_summary"],
        task100c_claim_risk_register=inputs["task100c_risks"],
        output_dir=tmp_path / "out",
    )

    allowed_text = " ".join(claim["claim"] for claim in result["allowed_claims"]["claims"]).lower()
    assert "controlled gsm8k" in allowed_text
    assert "bounded" in allowed_text
    assert "universal" not in allowed_text
    assert "proven" not in allowed_text


def test_reworded_no_badges_and_vietnamese_snippets_exist(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    result = t101.audit(
        task100a_claim_language=inputs["claim_language"],
        task100b_summary=inputs["task100b_summary"],
        task100c_claim_risk_register=inputs["task100c_risks"],
        output_dir=tmp_path / "out",
    )

    rewrites = result["reworded_no_badges"]["rewrites"]
    assert rewrites["No universal speedup claim"] == "Bounded GSM8K Light GPU speed evidence only"
    assert rewrites["No default GPU switch"] == "GPU placement remains runtime/gated candidate"

    snippets = result["report_language_snippets"]
    assert snippets["primary_language"] == "vi"
    assert snippets["vietnamese"]["allowed"]
    assert snippets["english"]["labels"]


def test_no_model_loading_in_task101_audit_script() -> None:
    source = inspect.getsource(t101)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
