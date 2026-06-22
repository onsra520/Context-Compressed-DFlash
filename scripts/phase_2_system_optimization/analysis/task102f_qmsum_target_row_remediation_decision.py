from __future__ import annotations

import argparse
import hashlib
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

DEFAULT_SOURCE_DATASET = Path("data/eval/qmsum_meeting_qa_100.jsonl")
DEFAULT_QMSUM_RUN = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102_qmsum_light_gpu_n30_feasibility_run/runs/"
    "20260622_151200_cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl"
)
DEFAULT_TASK102B_LABELS = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102b_qmsum_output_semantic_risk_analysis/task102b_qmsum_row_labels.jsonl"
)
DEFAULT_TASK102C_TRIAGE = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102c_qmsum_proxy_uncertainty_triage/task102c_uncertain_row_triage.jsonl"
)
DEFAULT_TASK102D_REASSESSMENT = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102d_qmsum_evaluator_proxy_improvement/task102d_row_proxy_reassessment.jsonl"
)
DEFAULT_TASK102E_RESOLUTION = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102e_qmsum_hard_risk_and_residual_uncertainty_resolution/task102e_target_row_resolution.jsonl"
)
DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102f_qmsum_target_row_remediation_decision"
)
DEFAULT_TARGET_DATASET = Path("data/eval/qmsum_meeting_qa_target_rows_task102f.jsonl")

OUTPUT_RELATIVE_PATHS = (
    Path("task102f_target_rows.json"),
    Path("task102f_remediation_policy.json"),
    Path("task102f_rerun_plan.json"),
    Path("task102f_target_dataset_plan.json"),
    Path("task102f_claim_status_update.json"),
    Path("task102f_next_task_decision.json"),
    Path("task102f_target_dataset_manifest.json"),
)

PROMPT_SUFFIX = (
    "Answer the question using only evidence from the meeting context. "
    "Be specific: include the relevant people, actions, decisions, or reasons when they are present. "
    "Avoid generic answers such as 'not discussed' unless the context clearly lacks the requested evidence. "
    "Keep the answer concise but complete in 2-5 sentences."
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_no} is not a JSON object")
        rows.append(payload)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("fixture_id") or row.get("dataset_id") or row.get("id") or "")
        if key:
            indexed[key] = row
    return indexed


def _target_category(final_resolution: str) -> str:
    if final_resolution == "confirmed_evidence_miss":
        return "confirmed_evidence_miss"
    if final_resolution == "confirmed_generic_or_under_specific":
        return "confirmed_generic_or_under_specific"
    return "unresolved_without_semantic_judge"


def build_target_rows(
    *,
    source_dataset_rows: list[dict[str, Any]],
    qmsum_run_rows: list[dict[str, Any]],
    task102b_rows: list[dict[str, Any]],
    task102c_rows: list[dict[str, Any]],
    task102d_rows: list[dict[str, Any]],
    task102e_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    source_by_id = _index(source_dataset_rows)
    run_by_id = _index(qmsum_run_rows)
    b_by_id = _index(task102b_rows)
    c_by_id = _index(task102c_rows)
    d_by_id = _index(task102d_rows)
    e_by_id = _index(task102e_rows)
    targets = []
    missing = []
    for fixture_id in TARGET_FIXTURE_IDS:
        source = source_by_id.get(fixture_id)
        resolution = e_by_id.get(fixture_id)
        if source is None or resolution is None:
            missing.append(fixture_id)
            continue
        run_row = run_by_id.get(fixture_id, {})
        final_resolution = str(resolution.get("final_resolution") or "")
        targets.append(
            {
                "fixture_id": fixture_id,
                "category": _target_category(final_resolution),
                "task102e_final_resolution": final_resolution,
                "task102e_final_status": resolution.get("final_status"),
                "observed_failure_reason": resolution.get("deterministic_reason"),
                "question": source.get("question"),
                "reference_answer": source.get("expected_answer") or source.get("answer"),
                "task102_generated_answer": run_row.get("generated_text"),
                "source_prompt_preview": str(source.get("prompt") or "")[:900],
                "source_context_preview": str(source.get("context") or "")[:900],
                "prior_labels": {
                    "task102b": b_by_id.get(fixture_id, {}).get("labels"),
                    "task102c": c_by_id.get(fixture_id, {}).get("primary_bucket"),
                    "task102d": {
                        "confidence_band": d_by_id.get(fixture_id, {}).get("improved_confidence_band"),
                        "outcome": d_by_id.get(fixture_id, {}).get("improved_outcome"),
                    },
                    "task102e": {
                        "final_resolution": final_resolution,
                        "final_status": resolution.get("final_status"),
                    },
                },
                "signals": resolution.get("signals", {}),
            }
        )
    if missing:
        raise ValueError(f"missing required target rows: {missing}")
    return targets


def build_remediation_policy() -> dict[str, Any]:
    return {
        "policy_name": "qmsum_targeted_evidence_repair_v1",
        "prompt_suffix": PROMPT_SUFFIX,
        "requirements": [
            "Evidence-focused answer.",
            "Answer the specific question directly.",
            "Use only information supported by the meeting context.",
            "Include specific entities, actions, decisions, or reasons when available.",
            "Avoid generic 'not discussed' unless context clearly lacks evidence.",
            "Prefer complete answer over overly short answer.",
            "Keep answer concise but complete.",
            "Do not add unsupported information.",
            "If evidence is ambiguous, state the most supported answer and avoid overgeneralizing.",
        ],
        "blocked_behavior": [
            "QMSum semantic correctness is proven.",
            "Use prior generated answers as prompt input.",
            "Add unsupported information.",
            "Treat fluent but off-question output as acceptable.",
            "Run QMSum n100 or a full matrix.",
        ],
        "rationale": (
            "Task102B found no cap-limited/incomplete rows, and Task102E residual rows are evidence-targeting, "
            "genericness, or unresolved semantic-risk cases. The remediation should repair evidence focus rather "
            "than increase sample size or tune keep_rate."
        ),
        "max_new_tokens_decision": {
            "selected": 384,
            "alternatives_considered": [384, 512],
            "rationale": (
                "Task102B found cap-limited/incomplete rows at 0/30, so failures are not cap-related. "
                "Use 384 to preserve comparability with the Task102 canonical QMSum run. Reserve 512 only "
                "for a later explicit cap/tail-pressure task if new target-row outputs show truncation."
            ),
        },
        "runner_support_note": (
            "scripts/run_mvp.py currently supports --dataset-path but does not expose a custom QMSum policy suffix flag. "
            "T102G should add or use a runtime-only policy override if the exact qmsum_targeted_evidence_repair_v1 suffix "
            "must be applied; otherwise the target-only rerun would reuse the existing evidence-focused suffix."
        ),
    }


def build_rerun_plan(target_dataset_path: Path) -> dict[str, Any]:
    command = (
        'OUTDIR="results/phase_2_system_optimization/final_reruns/'
        'task102g_qmsum_target_row_remediation_rerun/runs"\n'
        'mkdir -p "$OUTDIR"\n'
        'STAMP="$(date +%Y%m%d_%H%M%S)"\n'
        "PYTHONPATH=src .venv/bin/python scripts/run_mvp.py \\\n"
        "  --condition CC-DFlash-R2 \\\n"
        "  --prompt-source dataset \\\n"
        "  --dataset qmsum_meeting_qa_long \\\n"
        f"  --dataset-path {target_dataset_path} \\\n"
        "  --seed 42 \\\n"
        "  --n 6 \\\n"
        "  --warmup-prompts 0 \\\n"
        "  --max-new-tokens 384 \\\n"
        "  --store-generated-text \\\n"
        "  --resume \\\n"
        "  --compressor-profile light \\\n"
        "  --compressor-device-map cuda \\\n"
        '  --output "$OUTDIR/${STAMP}_cc_dflash_r2_light_gpu_qmsum_target6_seed42_mnt384.jsonl"'
    )
    return {
        "task": "T102G — QMSum Target-row Remediation Rerun",
        "condition": "CC-DFlash-R2",
        "dataset": "qmsum_meeting_qa_long",
        "dataset_path": str(target_dataset_path),
        "compressor_profile": "light",
        "compressor_device_map": "cuda",
        "seed": 42,
        "n": 6,
        "max_new_tokens": 384,
        "target_fixture_ids": list(TARGET_FIXTURE_IDS),
        "run_scope": "target rows only; no n100; no full matrix",
        "requires_cuda_gate": True,
        "requires_runtime_policy_override_for_exact_suffix": True,
        "implementation_precondition": (
            "Confirm or add a runtime-only QMSum policy suffix override before T102G if exact "
            "qmsum_targeted_evidence_repair_v1 wording is required."
        ),
        "command_template": command,
        "stop_conditions": [
            "CUDA unavailable before run.",
            "OOM/CUDA failure.",
            "Runner selects more than the six target rows.",
            "Target dataset contains previous generated_text as prompt input.",
            "Generated artifact is malformed or row count differs from 6.",
        ],
    }


def build_target_dataset_plan(target_dataset_path: Path) -> dict[str, Any]:
    return {
        "fixture_id_filter_exists": False,
        "runner_dataset_path_override_exists": True,
        "target_only_dataset_needed": True,
        "target_dataset_path": str(target_dataset_path),
        "source_dataset_path": str(DEFAULT_SOURCE_DATASET),
        "selection_method": "Create a static JSONL containing only the six original QMSum source/question/reference rows.",
        "leakage_guard": {
            "previous_generated_outputs_in_prompt_inputs": False,
            "copy_only_original_context_question_reference": True,
            "do_not_copy_task102_generated_text": True,
            "target_dataset_prompt_inputs_safe": True,
        },
        "runner_support_gap": (
            "No fixture-id filter is exposed by scripts/run_mvp.py. Use --dataset-path with a target-only dataset. "
            "No custom QMSum policy suffix flag is exposed yet; T102G should verify/add a runtime-only override for "
            "the exact remediation suffix if needed."
        ),
    }


def _safe_dataset_row(row: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "id",
        "dataset_name",
        "context",
        "question",
        "expected_answer",
        "answer",
        "ground_truth_answer",
        "prompt",
        "domain",
        "evidence",
        "approximate_context_words",
        "approximate_prompt_words",
        "quality_policy",
        "source",
        "source_mode",
        "evaluation_role",
        "original_dataset_reference",
    }
    return {key: value for key, value in row.items() if key in allowed}


def write_target_dataset(source_rows: list[dict[str, Any]], target_dataset_path: Path) -> dict[str, Any]:
    rows_by_id = {str(row.get("id") or row.get("fixture_id") or ""): row for row in source_rows}
    target_rows = [_safe_dataset_row(rows_by_id[fixture_id]) for fixture_id in TARGET_FIXTURE_IDS]
    for row in target_rows:
        forbidden = [key for key in row if "generated" in key.lower()]
        if forbidden:
            raise ValueError(f"target dataset row leaked generated fields: {forbidden}")
    write_jsonl(target_dataset_path, target_rows)
    content = target_dataset_path.read_bytes()
    return {
        "dataset_path": str(target_dataset_path),
        "row_count": len(target_rows),
        "fixture_ids": list(TARGET_FIXTURE_IDS),
        "sha256": hashlib.sha256(content).hexdigest(),
        "contains_generated_output_fields": False,
        "created_from": str(DEFAULT_SOURCE_DATASET),
    }


def build_claim_status_update() -> dict[str, Any]:
    return {
        "QMSum claim": {
            "status": "SCOPED_WITH_CONFIRMED_FAILURES",
            "remediation_path_selected": "Option B — target-row remediation rerun",
            "allowed_wording": [
                "QMSum residual quality risk is being handled with a six-row target-only remediation plan.",
                "QMSum remains benchmark-scoped proxy/risk evidence until T102G/T102H complete.",
            ],
            "blocked_wording": [
                "QMSum semantic correctness is proven.",
                "QMSum quality risk has been eliminated.",
                "T103 speed-claim closure can proceed without acknowledging residual QMSum risk.",
                "DFlash-R1 is broken.",
            ],
        },
        "T103": {
            "status": "BLOCKED_BY_DEFAULT",
            "reason": "Wait for T102G/T102H or explicit user acceptance of residual QMSum caveat.",
        },
        "DFlash-R1 broken claim": {
            "status": "REMOVED",
            "wording": "DFlash-R1 remains a reference condition, not a broken baseline.",
        },
    }


def build_next_task_decision() -> dict[str, Any]:
    return {
        "decision": "PASS",
        "next_task": "T102G — QMSum Target-row Remediation Rerun",
        "reason": "Option B selected: rerun only the six residual QMSum target rows with targeted evidence-focused remediation policy.",
        "automatic_benchmark": False,
        "t103_allowed_to_proceed": False,
        "t103_gate": "Wait for T102G/T102H or explicit user approval to carry residual caveat.",
    }


def analyze(
    *,
    source_dataset: Path = DEFAULT_SOURCE_DATASET,
    qmsum_run: Path = DEFAULT_QMSUM_RUN,
    task102b_labels: Path = DEFAULT_TASK102B_LABELS,
    task102c_triage: Path = DEFAULT_TASK102C_TRIAGE,
    task102d_reassessment: Path = DEFAULT_TASK102D_REASSESSMENT,
    task102e_resolution: Path = DEFAULT_TASK102E_RESOLUTION,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    target_dataset_path: Path = DEFAULT_TARGET_DATASET,
) -> dict[str, Any]:
    source_rows = read_jsonl(source_dataset)
    target_rows = build_target_rows(
        source_dataset_rows=source_rows,
        qmsum_run_rows=read_jsonl(qmsum_run),
        task102b_rows=read_jsonl(task102b_labels),
        task102c_rows=read_jsonl(task102c_triage),
        task102d_rows=read_jsonl(task102d_reassessment),
        task102e_rows=read_jsonl(task102e_resolution),
    )
    policy = build_remediation_policy()
    rerun_plan = build_rerun_plan(target_dataset_path)
    dataset_plan = build_target_dataset_plan(target_dataset_path)
    dataset_manifest = write_target_dataset(source_rows, target_dataset_path)
    claim_update = build_claim_status_update()
    next_task = build_next_task_decision()
    result = {
        "decision": "PASS",
        "selected_option": "Option B — target-row remediation rerun",
        "target_rows": target_rows,
        "remediation_policy": policy,
        "rerun_plan": rerun_plan,
        "target_dataset_plan": dataset_plan,
        "target_dataset_manifest": dataset_manifest,
        "claim_status_update": claim_update,
        "next_task_decision": next_task,
        "scope": {
            "benchmark_run": False,
            "model_inference": False,
            "gpu_run": False,
            "qmsum_rerun": False,
            "llm_judge": False,
            "human_semantic_scoring": False,
        },
    }
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[0], {"target_rows": target_rows})
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[1], policy)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[2], rerun_plan)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[3], dataset_plan)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[4], claim_update)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[5], next_task)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[6], dataset_manifest)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan Task102F QMSum target-row remediation rerun.")
    parser.add_argument("--source-dataset", type=Path, default=DEFAULT_SOURCE_DATASET)
    parser.add_argument("--qmsum-run", type=Path, default=DEFAULT_QMSUM_RUN)
    parser.add_argument("--task102b-labels", type=Path, default=DEFAULT_TASK102B_LABELS)
    parser.add_argument("--task102c-triage", type=Path, default=DEFAULT_TASK102C_TRIAGE)
    parser.add_argument("--task102d-reassessment", type=Path, default=DEFAULT_TASK102D_REASSESSMENT)
    parser.add_argument("--task102e-resolution", type=Path, default=DEFAULT_TASK102E_RESOLUTION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--target-dataset-path", type=Path, default=DEFAULT_TARGET_DATASET)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = analyze(
        source_dataset=args.source_dataset,
        qmsum_run=args.qmsum_run,
        task102b_labels=args.task102b_labels,
        task102c_triage=args.task102c_triage,
        task102d_reassessment=args.task102d_reassessment,
        task102e_resolution=args.task102e_resolution,
        output_dir=args.output_dir,
        target_dataset_path=args.target_dataset_path,
    )
    print(
        json.dumps(
            {
                "decision": result["decision"],
                "selected_option": result["selected_option"],
                "next_task": result["next_task_decision"]["next_task"],
                "target_rows": len(result["target_rows"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
