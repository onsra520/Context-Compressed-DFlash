from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task102h_qmsum_remediation_reassessment as t102h


TARGET_IDS = [
    "qmsum_meeting_qa_test_0036",
    "qmsum_meeting_qa_test_0070",
    "qmsum_meeting_qa_test_0055",
    "qmsum_meeting_qa_test_0078",
    "qmsum_meeting_qa_test_0094",
    "qmsum_meeting_qa_test_0001",
]


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _original_row(fixture_id: str, generated: str = "A generic old answer.") -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "question": "Which groups were heavily impacted?",
        "expected_answer": "Members discussed students, indigenous residents, rural residents, aboriginal people, and Black lives.",
        "generated_text": generated,
        "original_context_preview": "Members discussed students, indigenous residents, rural residents, aboriginal people, Black lives, police brutality, internet access, and education.",
        "output_tokens": 24,
        "generated_token_count": 24,
        "max_new_tokens": 384,
    }


def _remediated_row(fixture_id: str, generated: str) -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "question": "Which groups were heavily impacted?",
        "expected_answer": "Members discussed students, indigenous residents, rural residents, aboriginal people, and Black lives.",
        "generated_text": generated,
        "original_context_preview": "Members discussed students, indigenous residents, rural residents, aboriginal people, Black lives, police brutality, internet access, and education.",
        "output_tokens": 64,
        "generated_token_count": 64,
        "max_new_tokens": 384,
        "generation_time_s": 4.0,
        "t_compress_ms": 120.0,
    }


def _prior_row(fixture_id: str, final_resolution: str) -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "final_resolution": final_resolution,
        "final_status": "confirmed_quality_failure"
        if final_resolution.startswith("confirmed")
        else "still_unresolved",
        "question": "Which groups were heavily impacted?",
        "reference_answer_preview": "Members discussed students, indigenous residents, rural residents, aboriginal people, and Black lives.",
        "source_prompt_preview": "Members discussed students, indigenous residents, rural residents, aboriginal people, Black lives, police brutality, internet access, and education.",
    }


def test_analyzer_pairs_original_and_remediated_rows_by_fixture_id(tmp_path: Path) -> None:
    original = tmp_path / "original.jsonl"
    remediated = tmp_path / "remediated.jsonl"
    prior = tmp_path / "prior.jsonl"
    output_dir = tmp_path / "out"
    _write_jsonl(original, [_original_row(fixture_id) for fixture_id in TARGET_IDS])
    _write_jsonl(
        remediated,
        [
            _remediated_row(
                fixture_id,
                "Members discussed students, indigenous residents, rural residents, aboriginal people, and Black lives.",
            )
            for fixture_id in reversed(TARGET_IDS)
        ],
    )
    _write_jsonl(prior, [_prior_row(fixture_id, "confirmed_evidence_miss") for fixture_id in TARGET_IDS])

    result = t102h.analyze(
        original_jsonl=original,
        task102e_resolution=prior,
        remediated_jsonl=remediated,
        output_dir=output_dir,
    )

    assert result["summary"]["target_rows_total"] == 6
    assert {row["fixture_id"] for row in result["row_assessments"]} == set(TARGET_IDS)
    for relative in t102h.OUTPUT_RELATIVE_PATHS:
        assert (output_dir / relative).exists()


def test_resolved_by_targeted_policy_classification() -> None:
    assessment = t102h.assess_row(
        fixture_id="row",
        original_row=_original_row("row", "The old answer missed the requested groups."),
        remediated_row=_remediated_row(
            "row",
            "Members discussed students, indigenous residents, rural residents, aboriginal people, and Black lives.",
        ),
        prior_row=_prior_row("row", "confirmed_evidence_miss"),
    )

    assert assessment["remediation_outcome"] == "resolved_by_targeted_policy"
    assert assessment["final_risk_bucket"] == "resolved_proxy_supported"
    assert "reference_overlap_improved" in assessment["secondary_flags"]


def test_improved_but_still_risky_classification() -> None:
    assessment = t102h.assess_row(
        fixture_id="row",
        original_row=_original_row("row", "The old answer mentioned bees and whales."),
        remediated_row=_remediated_row("row", "Members discussed students and internet access."),
        prior_row=_prior_row("row", "confirmed_evidence_miss"),
    )

    assert assessment["remediation_outcome"] == "improved_but_still_risky"
    assert assessment["final_risk_bucket"] == "residual_evidence_miss"


def test_unchanged_quality_failure_classification() -> None:
    assessment = t102h.assess_row(
        fixture_id="row",
        original_row=_original_row("row", "The old answer mentioned bees and whales."),
        remediated_row=_remediated_row("row", "The new answer still mentions bees and whales."),
        prior_row=_prior_row("row", "confirmed_evidence_miss"),
    )

    assert assessment["remediation_outcome"] == "unchanged_quality_failure"
    assert assessment["final_risk_bucket"] == "residual_evidence_miss"


def test_still_unresolved_without_semantic_judge_classification() -> None:
    assessment = t102h.assess_row(
        fixture_id="row",
        original_row=_original_row("row", "The old answer mentioned students."),
        remediated_row=_remediated_row("row", "The new answer mentioned students and the question focus."),
        prior_row=_prior_row("row", "still_unresolved_without_semantic_judge"),
    )

    assert assessment["remediation_outcome"] == "still_unresolved_without_semantic_judge"
    assert assessment["final_risk_bucket"] == "residual_unresolved_deterministic_limitation"
    assert "deterministic_evidence_insufficient" in assessment["secondary_flags"]


def test_summary_counts_hard_risk_and_unresolved_rows() -> None:
    assessments = [
        {"remediation_outcome": "resolved_by_targeted_policy", "final_risk_bucket": "resolved_proxy_supported"},
        {"remediation_outcome": "improved_but_still_risky", "final_risk_bucket": "residual_evidence_miss"},
        {"remediation_outcome": "unchanged_quality_failure", "final_risk_bucket": "residual_generic_or_under_specific"},
        {"remediation_outcome": "worsened", "final_risk_bucket": "worsened_output"},
        {
            "remediation_outcome": "still_unresolved_without_semantic_judge",
            "final_risk_bucket": "residual_unresolved_deterministic_limitation",
        },
    ]

    summary = t102h.summarize_assessments(assessments)

    assert summary["resolved_by_targeted_policy_count"] == 1
    assert summary["remaining_hard_risk_count"] == 3
    assert summary["remaining_unresolved_count"] == 1


def test_claim_update_blocks_semantic_correctness_proof() -> None:
    summary = {
        "remaining_hard_risk_count": 0,
        "remaining_unresolved_count": 0,
        "confirmed_failures_reduced_from_task102e": True,
        "unresolved_rows_reduced_from_task102e": True,
    }

    claim = t102h.build_claim_update(summary)

    assert claim["qmsum_claim_status"] == "SCOPED_WITH_REMEDIATED_RISK"
    assert "QMSum semantic correctness is proven." in claim["blocked_wording"]


def test_next_task_is_t103_when_remediated_risk_is_sufficient() -> None:
    decision = t102h.build_next_task_decision({"qmsum_claim_status": "SCOPED_WITH_REMEDIATED_RISK"})

    assert decision["next_task"] == "T103 — Reference Alignment for Speed Claim"
    assert decision["caveat_required"] is False


def test_next_task_is_t102i_when_persistent_residual_risk_remains() -> None:
    decision = t102h.build_next_task_decision({"qmsum_claim_status": "SCOPED_WITH_PERSISTENT_RESIDUAL_RISK"})

    assert decision["next_task"] == "T102I — QMSum Residual Risk Stop-or-Judge Decision"


def test_no_model_loading_in_task102h_analyzer() -> None:
    source = inspect.getsource(t102h)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
