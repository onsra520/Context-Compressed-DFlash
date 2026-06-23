from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


TARGET_FIXTURE_IDS = (
    "qmsum_meeting_qa_test_0036",
    "qmsum_meeting_qa_test_0070",
    "qmsum_meeting_qa_test_0055",
    "qmsum_meeting_qa_test_0078",
    "qmsum_meeting_qa_test_0094",
    "qmsum_meeting_qa_test_0001",
)

DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task103c_qmsum_semantic_review_protocol"
)
DEFAULT_TASK103A_BEFORE_AFTER = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task103a_qmsum_evidence_selector_before_answer/summary/"
    "task103a_before_after_assessment.jsonl"
)
DEFAULT_TASK103A_SELECTED_EVIDENCE = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task103a_qmsum_evidence_selector_before_answer/summary/"
    "task103a_selected_evidence.jsonl"
)
DEFAULT_TASK102H_ASSESSMENT = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102h_qmsum_remediation_reassessment/"
    "task102h_before_after_row_assessment.jsonl"
)
DEFAULT_TASK102I_ASSESSMENT = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102i_qmsum_baseline_ar_target_row_mini_check/summary/"
    "task102i_baseline_vs_cc_row_assessment.jsonl"
)

OUTPUT_FILENAMES = (
    "task103c_review_protocol.json",
    "task103c_review_rubric.json",
    "task103c_review_packet.jsonl",
    "task103c_option_matrix.json",
    "task103c_claim_boundary.json",
    "task103c_next_task_decision.json",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_number} is not a JSON object")
        rows.append(payload)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _fixture_id(row: dict[str, Any]) -> str:
    return str(row.get("fixture_id") or row.get("dataset_id") or row.get("id") or "")


def _index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        fixture_id = _fixture_id(row)
        if fixture_id:
            indexed[fixture_id] = row
    return indexed


def _first_text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return ""


def build_review_rubric() -> dict[str, Any]:
    return {
        "rubric_name": "task103c_qmsum_residual_row_semantic_review_v1",
        "review_scope": "six residual QMSum target rows only",
        "labels": [
            {
                "label": "correct_supported",
                "meaning": "The answer directly addresses the question and is supported by the provided source/evidence packet.",
            },
            {
                "label": "partially_correct_or_incomplete",
                "meaning": "The answer contains some supported information but omits required entities/actions/numbers/reasons or is materially incomplete.",
            },
            {
                "label": "unsupported_or_wrong",
                "meaning": "The answer is contradicted by, unsupported by, or off-topic relative to the provided source/evidence packet.",
            },
            {
                "label": "cannot_determine_from_available_context",
                "meaning": "The packet does not provide enough context to distinguish model failure from source/reference mismatch or insufficient evidence.",
            },
        ],
        "scoring_dimensions": [
            {
                "name": "answers_the_question",
                "prompt": "Does the output directly answer the user question rather than a nearby or generic topic?",
            },
            {
                "name": "uses_correct_evidence",
                "prompt": "Is the answer grounded in the supplied meeting source/evidence packet?",
            },
            {
                "name": "required_entities_actions_numbers_reasons",
                "prompt": "Does the answer include required people, actions, decisions, numbers, or reasons when present?",
            },
            {
                "name": "avoids_hallucination",
                "prompt": "Does the answer avoid unsupported details not present in the packet?",
            },
            {
                "name": "avoids_unsupported_not_discussed",
                "prompt": "Does the answer avoid saying 'not discussed' or equivalent unless the packet truly lacks evidence?",
            },
            {
                "name": "completeness",
                "prompt": "Is the answer complete enough for the question while remaining concise?",
            },
            {
                "name": "reference_source_mismatch_risk",
                "prompt": "Could the reference answer require evidence not available in the supplied source/evidence packet?",
            },
        ],
        "review_rules": [
            "Use only the review packet content; do not use external knowledge.",
            "Do not infer semantic correctness from lexical overlap alone.",
            "Prefer cannot_determine_from_available_context when the packet lacks decisive evidence.",
            "Record a short rationale for every label if review execution is later approved.",
        ],
        "review_performed_in_task103c": False,
    }


def build_option_matrix() -> dict[str, Any]:
    return {
        "options": [
            {
                "option_id": "A",
                "name": "No semantic judge; freeze caveat",
                "description": "Do not perform additional review. Preserve QMSum as deterministic proxy/risk evidence with explicit residual caveats.",
                "benefit": "Fastest and methodologically conservative.",
                "risk": "Does not strengthen QMSum semantic-quality language.",
                "default_when": "Phase 2 should continue with deterministic-only methodology.",
                "recommended_for_stronger_semantic_claim": False,
                "automatic_default": True,
            },
            {
                "option_id": "B",
                "name": "Human review on six target rows",
                "description": "Have a human apply the fixed rubric to all six residual rows using the review packet.",
                "benefit": "Strongest non-LLM review path for a small bounded sample.",
                "risk": "Adds human-review methodology that must be disclosed and may not scale.",
                "default_when": "The user wants a stronger QMSum semantic claim without introducing an LLM judge.",
                "recommended_for_stronger_semantic_claim": True,
                "automatic_default": False,
            },
            {
                "option_id": "C",
                "name": "LLM judge with fixed rubric and evidence packet",
                "description": "Run a controlled LLM judge only after explicit approval, using the frozen rubric and packet.",
                "benefit": "Can provide consistent structured labels if judge setup is accepted.",
                "risk": "Introduces judge-model bias and must not be treated as ground truth.",
                "default_when": "Only after explicit approval for an LLM judge path.",
                "recommended_for_stronger_semantic_claim": False,
                "automatic_default": False,
            },
            {
                "option_id": "D",
                "name": "Hybrid human review only unresolved/conflicting rows",
                "description": "Review only rows whose deterministic labels remain unresolved or conflicting, while freezing clear failures as caveated.",
                "benefit": "Minimizes human-review load while targeting the hardest residual rows.",
                "risk": "Requires a careful pre-declared unresolved/conflict selection rule.",
                "default_when": "The user wants stronger semantic evidence while keeping review small.",
                "recommended_for_stronger_semantic_claim": True,
                "automatic_default": False,
            },
        ],
        "default_recommendation": {
            "if_stronger_qmsum_semantic_claim_is_needed": "Prefer Option B or Option D.",
            "if_phase2_should_continue_without_methodology_change": "Prefer Option A.",
            "do_not_run_llm_judge_without_explicit_approval": True,
            "automatic_llm_judge_default": False,
        },
    }


def build_claim_boundary() -> dict[str, Any]:
    return {
        "qmsum_claim_status": "SEMANTIC_REVIEW_PROTOCOL_PREPARED",
        "semantic_correctness_proven": False,
        "review_performed": False,
        "allowed_claims": [
            "A semantic review protocol was prepared for residual QMSum rows.",
            "QMSum deterministic proxy limitations remain explicitly bounded.",
            "The review packet can support a future approved human or judge review on six target rows.",
        ],
        "blocked_claims": [
            "QMSum semantic correctness is proven.",
            "Human/LLM review was performed.",
            "Query-aware compression is validated by T103C.",
            "The full QMSum matrix is complete.",
            "Residual QMSum risk is eliminated.",
        ],
        "remaining_limitations": [
            "No semantic review was executed in Task103C.",
            "Only six residual target rows are covered by the packet.",
            "The packet combines deterministic artifacts and does not adjudicate semantics.",
            "No LLM judge, human scoring, QMSum rerun, or full matrix was performed.",
        ],
    }


def build_next_task_decision(user_intent: str = "decision_required") -> dict[str, Any]:
    branches = {
        "stronger_semantic_claim": {
            "next_task": "T103C-R — QMSum Human/Semantic Review Execution",
            "reason": "A stronger QMSum semantic claim requires executing the prepared review protocol.",
            "recommended_option": "B or D",
        },
        "deterministic_only": {
            "next_task": "T103D — QMSum Deep Fix Closure Decision",
            "reason": "If deterministic-only methodology is preserved, freeze the caveat and close the QMSum deep-fix branch.",
            "recommended_option": "A",
        },
        "query_aware_compression": {
            "next_task": "T103B — Query-aware Compression Prototype",
            "reason": "Query-aware compression may be explored only after preserving the T103A caveat.",
            "recommended_option": "preserve T103A caveat first",
        },
    }
    selected = branches.get(user_intent)
    return {
        "decision": "USER_DECISION_REQUIRED" if selected is None else "ROUTED",
        "selected_intent": user_intent,
        "next_task": selected["next_task"] if selected else "User choice required: T103C-R, T103D, or T103B",
        "reason": selected["reason"] if selected else "Task103C prepares the protocol but does not execute a review or choose a semantic-claim path automatically.",
        "available_paths": branches,
        "default_guidance": {
            "stronger_qmsum_semantic_claim": "Choose T103C-R with Option B or D.",
            "deterministic_only_methodology": "Choose T103D and freeze the QMSum caveat.",
            "query_aware_compression": "Choose T103B only after preserving the T103A caveat.",
        },
    }


def _merge_rows(
    *,
    task103a_before_after: list[dict[str, Any]],
    task103a_selected_evidence: list[dict[str, Any]],
    task102h_assessment: list[dict[str, Any]],
    task102i_assessment: list[dict[str, Any]],
    expected_ids: tuple[str, ...] = TARGET_FIXTURE_IDS,
) -> list[dict[str, Any]]:
    before_by_id = _index(task103a_before_after)
    selected_by_id = _index(task103a_selected_evidence)
    h_by_id = _index(task102h_assessment)
    i_by_id = _index(task102i_assessment)
    merged: list[dict[str, Any]] = []
    missing: list[str] = []
    for fixture_id in expected_ids:
        combined: dict[str, Any] = {"fixture_id": fixture_id}
        for source in (before_by_id, selected_by_id, h_by_id, i_by_id):
            if fixture_id in source:
                combined.update(source[fixture_id])
        if len(combined) == 1:
            missing.append(fixture_id)
        merged.append(combined)
    if missing:
        raise ValueError(f"Missing review rows for fixture IDs: {missing}")
    return merged


def build_review_packet_row(row: dict[str, Any]) -> dict[str, Any]:
    selected_evidence = _first_text(row, "selected_context", "source_preview", "context")
    return {
        "fixture_id": _fixture_id(row),
        "question": _first_text(row, "question"),
        "reference_answer": _first_text(row, "reference_answer", "expected_answer", "ground_truth_answer"),
        "selected_source_evidence": selected_evidence,
        "source_evidence_metadata": {
            "selected_chars": row.get("selected_chars"),
            "selected_count": row.get("selected_count"),
            "reference_used_for_retrieval": row.get("reference_used_for_retrieval"),
            "prior_generated_outputs_used": row.get("prior_generated_outputs_used"),
        },
        "outputs": {
            "original_cc_dflash": _first_text(row, "original_cc_output", "original_generated_answer"),
            "remediated_cc_dflash": _first_text(row, "remediated_cc_output", "remediated_generated_answer"),
            "baseline_ar": _first_text(row, "baseline_ar_output"),
            "evidence_selected_baseline_ar": _first_text(row, "baseline_evidence_output"),
            "evidence_selected_cc_dflash": _first_text(row, "cc_evidence_output"),
        },
        "deterministic_labels": {
            "task102h_prior_status": row.get("prior_status"),
            "task102h_remediation_outcome": row.get("remediation_outcome"),
            "task102h_final_risk_bucket": row.get("final_risk_bucket"),
            "task102i_baseline_category": row.get("category"),
            "task103a_baseline_evidence_category": row.get("baseline_evidence_category"),
            "task103a_cc_evidence_category": row.get("cc_evidence_category"),
            "baseline_evidence_generic_flag": row.get("baseline_evidence_generic_flag"),
            "cc_evidence_generic_flag": row.get("cc_evidence_generic_flag"),
        },
        "deterministic_metrics": {
            "baseline_full_reference_overlap": row.get("baseline_full_reference_overlap"),
            "baseline_evidence_reference_overlap": row.get("baseline_evidence_reference_overlap"),
            "baseline_evidence_reference_bigram_overlap": row.get("baseline_evidence_reference_bigram_overlap"),
            "baseline_evidence_selected_evidence_overlap": row.get("baseline_evidence_selected_evidence_overlap"),
            "cc_remediated_reference_overlap": row.get("cc_remediated_reference_overlap"),
            "cc_evidence_reference_overlap": row.get("cc_evidence_reference_overlap"),
            "cc_evidence_reference_bigram_overlap": row.get("cc_evidence_reference_bigram_overlap"),
            "cc_evidence_selected_evidence_overlap": row.get("cc_evidence_selected_evidence_overlap"),
        },
        "review_fields": {
            "semantic_label": None,
            "answers_the_question": None,
            "uses_correct_evidence": None,
            "required_entities_actions_numbers_reasons": None,
            "avoids_hallucination": None,
            "avoids_unsupported_not_discussed": None,
            "completeness": None,
            "reference_source_mismatch_risk": None,
            "reviewer_notes": "",
        },
    }


def build_review_protocol(packet_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "task": "T103C — QMSum Semantic Judge / Human Review Protocol",
        "purpose": "Prepare a controlled semantic-review protocol for six residual QMSum rows without executing review.",
        "review_unit_count": len(packet_rows),
        "fixture_ids": [row["fixture_id"] for row in packet_rows],
        "inputs": [
            "Task102H remediation reassessment",
            "Task102I Baseline-AR mini-check",
            "Task103A evidence-selected before/after assessment",
            "Task103A selected evidence packet",
        ],
        "review_unit_fields": [
            "fixture_id",
            "question",
            "reference_answer",
            "selected_source_evidence",
            "original_cc_dflash_output",
            "remediated_cc_dflash_output",
            "baseline_ar_output",
            "evidence_selected_baseline_ar_output",
            "evidence_selected_cc_dflash_output",
            "deterministic_labels",
            "blank_review_fields",
        ],
        "scope": {
            "protocol_only": True,
            "llm_judge_run": False,
            "human_scoring_performed": False,
            "benchmark_rerun": False,
            "qmsum_n100": False,
            "full_matrix": False,
        },
    }


def generate_protocol_artifacts(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    task103a_before_after_path: Path = DEFAULT_TASK103A_BEFORE_AFTER,
    task103a_selected_evidence_path: Path = DEFAULT_TASK103A_SELECTED_EVIDENCE,
    task102h_assessment_path: Path = DEFAULT_TASK102H_ASSESSMENT,
    task102i_assessment_path: Path = DEFAULT_TASK102I_ASSESSMENT,
) -> dict[str, Any]:
    merged = _merge_rows(
        task103a_before_after=read_jsonl(task103a_before_after_path),
        task103a_selected_evidence=read_jsonl(task103a_selected_evidence_path),
        task102h_assessment=read_jsonl(task102h_assessment_path),
        task102i_assessment=read_jsonl(task102i_assessment_path),
    )
    packet_rows = [build_review_packet_row(row) for row in merged]
    review_protocol = build_review_protocol(packet_rows)
    review_rubric = build_review_rubric()
    option_matrix = build_option_matrix()
    claim_boundary = build_claim_boundary()
    next_task_decision = build_next_task_decision()

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "task103c_review_protocol.json", review_protocol)
    write_json(output_dir / "task103c_review_rubric.json", review_rubric)
    write_jsonl(output_dir / "task103c_review_packet.jsonl", packet_rows)
    write_json(output_dir / "task103c_option_matrix.json", option_matrix)
    write_json(output_dir / "task103c_claim_boundary.json", claim_boundary)
    write_json(output_dir / "task103c_next_task_decision.json", next_task_decision)

    return {
        "review_protocol": review_protocol,
        "review_rubric": review_rubric,
        "review_packet_rows": packet_rows,
        "option_matrix": option_matrix,
        "claim_boundary": claim_boundary,
        "next_task_decision": next_task_decision,
        "output_dir": str(output_dir),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Task103C QMSum semantic review protocol artifacts.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--task103a-before-after", type=Path, default=DEFAULT_TASK103A_BEFORE_AFTER)
    parser.add_argument("--task103a-selected-evidence", type=Path, default=DEFAULT_TASK103A_SELECTED_EVIDENCE)
    parser.add_argument("--task102h-assessment", type=Path, default=DEFAULT_TASK102H_ASSESSMENT)
    parser.add_argument("--task102i-assessment", type=Path, default=DEFAULT_TASK102I_ASSESSMENT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = generate_protocol_artifacts(
        output_dir=args.output_dir,
        task103a_before_after_path=args.task103a_before_after,
        task103a_selected_evidence_path=args.task103a_selected_evidence,
        task102h_assessment_path=args.task102h_assessment,
        task102i_assessment_path=args.task102i_assessment,
    )
    print(json.dumps({key: value for key, value in result.items() if key != "review_packet_rows"}, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
