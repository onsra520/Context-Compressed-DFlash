from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
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

POLICY_NAME = "qmsum_evidence_grounded_concise_v1"
POLICY_SUFFIX = (
    "Answer using only information supported by the meeting transcript. First identify the most relevant evidence "
    "in the transcript mentally, then give a concise answer in 1-3 sentences. If the transcript does not contain "
    "enough evidence, say that the transcript does not provide enough information. Do not invent details."
)

DEFAULT_BASE_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task108b_qmsum_targeted_repair_attempt"
)
DEFAULT_OUTPUT_DIR = DEFAULT_BASE_DIR
DEFAULT_RUN_ARTIFACT = DEFAULT_BASE_DIR / "runs/cc_dflash_r2_light_gpu_qmsum_targeted_evidence_grounded.jsonl"
DEFAULT_BEFORE_JSONL = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task105b_qmsum_controlled_runtime_matrix/runs/"
    "cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl"
)
DEFAULT_TARGET_DATASET = Path("data/eval/qmsum_meeting_qa_target_rows_task102f.jsonl")
DEFAULT_T103D_CLOSURE = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task103d_qmsum_deep_fix_closure_decision/task103d_closure_summary.json"
)

OUTPUT_RELATIVE_PATHS = (
    Path("summary/task108b_repair_summary.json"),
    Path("summary/task108b_target_rows.json"),
    Path("summary/task108b_condition_metrics.json"),
    Path("summary/task108b_before_after_proxy_comparison.json"),
    Path("summary/task108b_output_shape_audit.json"),
    Path("summary/task108b_residual_risk_delta.json"),
    Path("summary/task108b_claim_update.json"),
    Path("summary/task108b_next_task_decision.json"),
    Path("tables/task108b_qmsum_targeted_repair_table.csv"),
)

GENERATED_OUTPUT_LEAK_FIELDS = {
    "generated_text",
    "generated_answer",
    "model_answer",
    "model_output",
    "output",
    "prediction",
    "response",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "his",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "might",
    "not",
    "of",
    "on",
    "only",
    "or",
    "she",
    "should",
    "so",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "to",
    "use",
    "used",
    "using",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "will",
    "with",
    "would",
    "you",
}

REFUSAL_PATTERNS = (
    r"\bdoes not provide enough information\b",
    r"\bnot enough information\b",
    r"\bdoes not contain enough evidence\b",
    r"\btranscript does not provide\b",
    r"\bcannot determine\b",
    r"\bno evidence\b",
    r"\bnot discussed\b",
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


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
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["fixture_id", "row_outcome"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _fixture_id(row: dict[str, Any]) -> str:
    return str(row.get("fixture_id") or row.get("dataset_id") or row.get("id") or "")


def _index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_fixture_id(row): row for row in rows if _fixture_id(row)}


def _number(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def _text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _generated_text(row: dict[str, Any]) -> str:
    return _text(row, "generated_text", "generated_output", "output_text")


def _tokens(text: Any) -> list[str]:
    raw = re.findall(r"[A-Za-z0-9]+", str(text or "").lower())
    return [token for token in raw if token not in STOPWORDS and len(token) > 1]


def _safe_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _round(value: float | None) -> float | None:
    return None if value is None else round(float(value), 6)


def _is_refusal_or_generic(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in REFUSAL_PATTERNS)


def _ends_incomplete(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped.endswith((".", "!", "?", '"', "'", ")", "]")):
        return False
    return stripped.lower().endswith((" and", " but", " because", " due to", " including", " for", " to", " of"))


def _looks_cap_limited(row: dict[str, Any]) -> bool:
    max_new_tokens = _number(row, "max_new_tokens")
    generated_tokens = _number(row, "generated_token_count", "output_tokens", "new_tokens")
    if max_new_tokens and generated_tokens is not None and generated_tokens >= max_new_tokens:
        return True
    return _ends_incomplete(_generated_text(row))


def _has_failure_flag(row: dict[str, Any]) -> bool:
    for key in ("oom", "oom_flag", "cuda_failure", "cuda_error", "runtime_failure", "error", "failure"):
        value = row.get(key)
        if value not in (None, "", False, 0, "False", "false", "none", "None"):
            return True
    lowered = _generated_text(row).lower()
    return "cuda out of memory" in lowered or "runtimeerror: cuda" in lowered


def _proxy_metrics(output: str, reference: str, question: str, source: str) -> dict[str, Any]:
    output_tokens = _tokens(output)
    reference_tokens = _tokens(reference)
    question_tokens = _tokens(question)
    source_tokens = _tokens(source)
    output_set = set(output_tokens)
    reference_set = set(reference_tokens)
    question_set = set(question_tokens)
    source_set = set(source_tokens)
    ref_hits = len(output_set & reference_set)
    return {
        "reference_recall": _round(_safe_ratio(ref_hits, len(reference_set))),
        "reference_precision": _round(_safe_ratio(ref_hits, len(output_set))),
        "reference_f1": _round(_safe_ratio(2 * ref_hits, len(output_set) + len(reference_set))),
        "question_focus_overlap": _round(_safe_ratio(len(output_set & question_set), len(question_set))),
        "source_grounding_overlap": _round(_safe_ratio(len(output_set & source_set), len(output_set))),
        "output_content_terms": len(output_set),
        "output_word_count": len(str(output or "").split()),
        "generic_or_refusal": _is_refusal_or_generic(output),
    }


def _delta(after: float | None, before: float | None) -> float | None:
    if after is None or before is None:
        return None
    return round(after - before, 6)


def _e2e_time(row: dict[str, Any]) -> float | None:
    direct = _number(row, "e2e_time_s", "end_to_end_time_s")
    if direct is not None:
        return direct
    generation = _number(row, "generation_time_s")
    if generation is None:
        return None
    return generation + ((_number(row, "t_compress_ms") or 0.0) / 1000.0)


def _avg(values: list[float | None]) -> float | None:
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    return round(statistics.fmean(clean), 6) if clean else None


def validate_target_dataset(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    ids = [_fixture_id(row) for row in rows]
    errors: list[str] = []
    if len(rows) != len(TARGET_FIXTURE_IDS):
        errors.append(f"expected 6 rows, found {len(rows)}")
    if set(ids) != set(TARGET_FIXTURE_IDS):
        errors.append(f"fixture_ids mismatch: {sorted(set(ids))}")
    if len(ids) != len(set(ids)):
        errors.append("duplicate fixture_id found")
    for row in rows:
        fixture_id = _fixture_id(row) or "<missing-id>"
        missing = [
            key for key in ("id", "context", "question", "expected_answer") if not str(row.get(key, "")).strip()
        ]
        if missing:
            errors.append(f"{fixture_id}: missing required fields {missing}")
        leaked = sorted(field for field in GENERATED_OUTPUT_LEAK_FIELDS if field in row)
        if leaked:
            errors.append(f"{fixture_id}: generated-output fields present {leaked}")
    return {
        "valid": not errors,
        "path": str(path),
        "row_count": len(rows),
        "fixture_ids": ids,
        "expected_fixture_ids": list(TARGET_FIXTURE_IDS),
        "errors": errors,
    }


def audit_run_metadata(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    ids = [_fixture_id(row) for row in rows]
    if len(rows) != len(TARGET_FIXTURE_IDS):
        errors.append(f"expected 6 result rows, found {len(rows)}")
    if set(ids) != set(TARGET_FIXTURE_IDS):
        errors.append(f"fixture_ids mismatch: {sorted(set(ids))}")
    if len(ids) != len(set(ids)):
        errors.append("duplicate fixture_id found")
    for index, row in enumerate(rows, start=1):
        prefix = f"row {index} {_fixture_id(row) or '<missing-id>'}"
        if row.get("condition") != "CC-DFlash-R2":
            errors.append(f"{prefix}: condition={row.get('condition')!r}")
        if row.get("dataset_name") != "qmsum_meeting_qa_long":
            errors.append(f"{prefix}: dataset_name={row.get('dataset_name')!r}")
        if row.get("compressor_profile") != "light":
            errors.append(f"{prefix}: compressor_profile={row.get('compressor_profile')!r}")
        if row.get("compressor_device_map") != "cuda":
            errors.append(f"{prefix}: compressor_device_map={row.get('compressor_device_map')!r}")
        if row.get("requested_compressor_device_map") != "cuda":
            errors.append(f"{prefix}: requested_compressor_device_map={row.get('requested_compressor_device_map')!r}")
        if _boolish(row.get("local_files_only")) is not True:
            errors.append(f"{prefix}: local_files_only={row.get('local_files_only')!r}")
        if _boolish(row.get("qmsum_policy_suffix_override")) is not True:
            errors.append(f"{prefix}: qmsum_policy_suffix_override={row.get('qmsum_policy_suffix_override')!r}")
        if row.get("qmsum_answer_policy_type") != POLICY_NAME:
            errors.append(f"{prefix}: qmsum_answer_policy_type={row.get('qmsum_answer_policy_type')!r}")
        if _boolish(row.get("qmsum_answer_policy_preserved")) is not True:
            errors.append(f"{prefix}: qmsum_answer_policy_preserved={row.get('qmsum_answer_policy_preserved')!r}")
        if not _generated_text(row).strip():
            errors.append(f"{prefix}: empty generated_text")
        if _has_failure_flag(row):
            errors.append(f"{prefix}: OOM/CUDA/runtime failure flag detected")
    return {
        "valid": not errors,
        "row_count": len(rows),
        "fixture_ids": ids,
        "expected_fixture_ids": list(TARGET_FIXTURE_IDS),
        "metadata_confirmed": not errors,
        "policy_name": POLICY_NAME,
        "policy_type_values": sorted({str(row.get("qmsum_answer_policy_type")) for row in rows}),
        "compressor_profile_values": sorted({str(row.get("compressor_profile")) for row in rows}),
        "compressor_device_map_values": sorted({str(row.get("compressor_device_map")) for row in rows}),
        "requested_compressor_device_map_values": sorted({str(row.get("requested_compressor_device_map")) for row in rows}),
        "local_files_only_values": sorted({str(_boolish(row.get("local_files_only"))) for row in rows}),
        "oom_cuda_failure_flags": any(_has_failure_flag(row) for row in rows),
        "errors": errors,
    }


def compare_row(*, before: dict[str, Any], after: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    fixture_id = _fixture_id(after) or _fixture_id(before) or _fixture_id(target)
    reference = _text(target, "expected_answer", "answer") or _text(after, "expected_answer") or _text(before, "expected_answer")
    question = _text(target, "question") or _text(after, "question") or _text(before, "question")
    source = _text(target, "context", "prompt")
    before_text = _generated_text(before)
    after_text = _generated_text(after)
    before_proxy = _proxy_metrics(before_text, reference, question, source)
    after_proxy = _proxy_metrics(after_text, reference, question, source)
    recall_delta = _delta(after_proxy["reference_recall"], before_proxy["reference_recall"])
    f1_delta = _delta(after_proxy["reference_f1"], before_proxy["reference_f1"])
    after_refusal = bool(after_proxy["generic_or_refusal"])
    after_cap_limited = _looks_cap_limited(after)

    if after_refusal:
        row_outcome = "safer_but_uninformative"
    elif (recall_delta is not None and recall_delta >= 0.15) or (f1_delta is not None and f1_delta >= 0.10):
        row_outcome = "proxy_improved"
    elif (recall_delta is not None and recall_delta <= -0.10) or (f1_delta is not None and f1_delta <= -0.10):
        row_outcome = "proxy_regressed"
    else:
        row_outcome = "unchanged_or_no_improvement"

    return {
        "fixture_id": fixture_id,
        "question": question,
        "reference_answer": reference,
        "before_generated_preview": before_text[:500],
        "after_generated_preview": after_text[:500],
        "before_reference_recall": before_proxy["reference_recall"],
        "after_reference_recall": after_proxy["reference_recall"],
        "reference_recall_delta": recall_delta,
        "before_reference_f1": before_proxy["reference_f1"],
        "after_reference_f1": after_proxy["reference_f1"],
        "reference_f1_delta": f1_delta,
        "after_question_focus_overlap": after_proxy["question_focus_overlap"],
        "after_source_grounding_overlap": after_proxy["source_grounding_overlap"],
        "before_output_word_count": before_proxy["output_word_count"],
        "after_output_word_count": after_proxy["output_word_count"],
        "after_generic_or_refusal": after_refusal,
        "after_cap_limited_or_incomplete": after_cap_limited,
        "row_outcome": row_outcome,
    }


def build_condition_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "avg_e2e_time_s": _avg([_e2e_time(row) for row in rows]),
        "avg_generation_time_s": _avg([_number(row, "generation_time_s") for row in rows]),
        "avg_t_compress_ms": _avg([_number(row, "t_compress_ms") for row in rows]),
        "avg_R_actual": _avg([_number(row, "R_actual", "compression_ratio") for row in rows]),
        "max_vram_reserved_gib": max(
            [value for value in [_number(row, "vram_reserved_gib", "max_vram_reserved_gib") for row in rows] if value is not None],
            default=None,
        ),
        "empty_or_malformed_count": sum(1 for row in rows if not _generated_text(row).strip()),
        "cap_limited_or_incomplete_count": sum(1 for row in rows if _looks_cap_limited(row)),
        "refusal_or_insufficient_evidence_count": sum(1 for row in rows if _is_refusal_or_generic(_generated_text(row))),
        "oom_or_cuda_failure": any(_has_failure_flag(row) for row in rows),
    }


def build_output_shape_audit(rows: list[dict[str, Any]], metadata_audit: dict[str, Any]) -> dict[str, Any]:
    metrics = build_condition_metrics(rows)
    return {
        "valid": metadata_audit["valid"]
        and metrics["empty_or_malformed_count"] == 0
        and metrics["cap_limited_or_incomplete_count"] == 0
        and metrics["oom_or_cuda_failure"] is False,
        "row_count": metrics["row_count"],
        "empty_or_malformed_count": metrics["empty_or_malformed_count"],
        "cap_limited_or_incomplete_count": metrics["cap_limited_or_incomplete_count"],
        "refusal_or_insufficient_evidence_count": metrics["refusal_or_insufficient_evidence_count"],
        "oom_or_cuda_failure": metrics["oom_or_cuda_failure"],
        "metadata_audit": metadata_audit,
    }


def summarize_comparisons(comparisons: list[dict[str, Any]], *, output_shape_audit: dict[str, Any]) -> dict[str, Any]:
    improved = sum(1 for row in comparisons if row["row_outcome"] == "proxy_improved")
    safer_refusal = sum(1 for row in comparisons if row["row_outcome"] == "safer_but_uninformative")
    regressed = sum(1 for row in comparisons if row["row_outcome"] == "proxy_regressed")
    unchanged = sum(1 for row in comparisons if row["row_outcome"] == "unchanged_or_no_improvement")
    avg_recall_delta = _avg([row.get("reference_recall_delta") for row in comparisons])
    if not output_shape_audit["metadata_audit"]["valid"]:
        decision = "PARTIAL"
        interpretation = "repair_infrastructure_or_metadata_incomplete"
    elif improved >= 3 and regressed == 0 and safer_refusal <= 1 and output_shape_audit["valid"]:
        decision = "PASS_WITH_CAVEAT"
        interpretation = "targeted_proxy_improvement_supported"
    elif improved > 0 or safer_refusal > 0 or regressed > 0:
        decision = "MIXED_WITH_CAVEAT"
        interpretation = "mixed_targeted_repair_signal"
    else:
        decision = "FAIL_WITH_EVIDENCE"
        interpretation = "no_targeted_proxy_improvement"
    return {
        "decision": decision,
        "interpretation": interpretation,
        "target_rows": len(comparisons),
        "proxy_improved_count": improved,
        "safer_but_uninformative_count": safer_refusal,
        "proxy_regressed_count": regressed,
        "unchanged_or_no_improvement_count": unchanged,
        "avg_reference_recall_delta": avg_recall_delta,
        "output_shape_valid": output_shape_audit["valid"],
    }


def build_residual_risk_delta(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "previous_status": "CLOSED_WITH_PERSISTENT_RESIDUAL_RISK",
        "repair_interpretation": summary["interpretation"],
        "residual_risk_status": "NEEDS_TARGETED_VALIDATION"
        if summary["decision"] in {"PASS_WITH_CAVEAT", "MIXED_WITH_CAVEAT"}
        else "PERSISTENT_RESIDUAL_RISK_REPAIR_FAILED",
        "proxy_improved_count": summary["proxy_improved_count"],
        "safer_but_uninformative_count": summary["safer_but_uninformative_count"],
        "proxy_regressed_count": summary["proxy_regressed_count"],
        "note": "Deterministic proxy movement is not semantic correctness proof.",
    }


def build_claim_update(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "qmsum_claim_status": "TARGETED_REPAIR_ATTEMPT_REQUIRES_VALIDATION"
        if summary["decision"] in {"PASS_WITH_CAVEAT", "MIXED_WITH_CAVEAT"}
        else "TARGETED_REPAIR_ATTEMPT_FAILED_OR_INCONCLUSIVE",
        "allowed_claims": [
            "T108B attempted a targeted QMSum evidence-grounded repair.",
            f"The repair produced {summary['proxy_improved_count']} deterministic proxy-improved rows out of {summary['target_rows']}.",
            "QMSum semantic correctness still requires validation before being claimed.",
        ],
        "blocked_claims": [
            "QMSum semantic correctness is proven.",
            "QMSum residual risk is eliminated.",
            "CC-DFlash wins QMSum.",
            "The repair generalizes to all QMSum rows.",
            "Default switch is authorized.",
            "Phase 2 is closed.",
        ],
    }


def build_next_task_decision(summary: dict[str, Any]) -> dict[str, Any]:
    if summary["decision"] in {"PASS_WITH_CAVEAT", "MIXED_WITH_CAVEAT"}:
        return {
            "next_task": "T108C — QMSum Targeted Repair Validation",
            "next_task_mode": "targeted_repair_validation",
            "reason": "Targeted repair produced enough deterministic movement or mixed signal to require validation before closure.",
        }
    return {
        "next_task": "T108C — Final QMSum Limitation Decision",
        "next_task_mode": "final_qmsum_limitation_decision",
        "reason": "Targeted repair did not improve deterministic proxy/risk enough to justify validation.",
    }


def analyze(
    *,
    run_artifact: Path = DEFAULT_RUN_ARTIFACT,
    before_jsonl: Path = DEFAULT_BEFORE_JSONL,
    target_dataset: Path = DEFAULT_TARGET_DATASET,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    t103d_closure: Path = DEFAULT_T103D_CLOSURE,
) -> dict[str, Any]:
    run_rows = read_jsonl(run_artifact)
    before_rows = read_jsonl(before_jsonl)
    target_rows = read_jsonl(target_dataset)
    closure = read_json(t103d_closure)
    target_audit = validate_target_dataset(target_dataset)
    metadata_audit = audit_run_metadata(run_rows)
    output_shape_audit = build_output_shape_audit(run_rows, metadata_audit)

    before_by_id = _index(before_rows)
    target_by_id = _index(target_rows)
    comparisons = [
        compare_row(before=before_by_id.get(_fixture_id(row), {}), after=row, target=target_by_id.get(_fixture_id(row), {}))
        for row in run_rows
        if _fixture_id(row)
    ]
    comparison_summary = summarize_comparisons(comparisons, output_shape_audit=output_shape_audit)
    condition_metrics = build_condition_metrics(run_rows)
    residual_risk_delta = build_residual_risk_delta(comparison_summary)
    claim_update = build_claim_update(comparison_summary)
    next_task_decision = build_next_task_decision(comparison_summary)

    repair_summary = {
        "task": "T108B",
        "title": "QMSum Targeted Repair Attempt",
        "decision": comparison_summary["decision"],
        "policy_name": POLICY_NAME,
        "policy_suffix": POLICY_SUFFIX,
        "run_artifact": str(run_artifact),
        "before_artifact": str(before_jsonl),
        "target_dataset": str(target_dataset),
        "target_rows": len(run_rows),
        "t103d_prior_status": closure.get("qmsum_deep_fix_status", "CLOSED_WITH_PERSISTENT_RESIDUAL_RISK"),
        "interpretation": comparison_summary["interpretation"],
        "no_qmsum_n100": True,
        "no_full_matrix": True,
        "no_llm_judge": True,
        "no_human_scoring": True,
        "no_default_switch": True,
    }
    target_rows_payload = {
        "target_dataset_audit": target_audit,
        "target_fixture_ids": list(TARGET_FIXTURE_IDS),
        "selection_reason": "Six T103D human-reviewed residual-risk rows from the frozen T102F target dataset.",
    }
    before_after_proxy_comparison = {
        "summary": comparison_summary,
        "rows": comparisons,
    }

    write_json(output_dir / "summary/task108b_repair_summary.json", repair_summary)
    write_json(output_dir / "summary/task108b_target_rows.json", target_rows_payload)
    write_json(output_dir / "summary/task108b_condition_metrics.json", condition_metrics)
    write_json(output_dir / "summary/task108b_before_after_proxy_comparison.json", before_after_proxy_comparison)
    write_json(output_dir / "summary/task108b_output_shape_audit.json", output_shape_audit)
    write_json(output_dir / "summary/task108b_residual_risk_delta.json", residual_risk_delta)
    write_json(output_dir / "summary/task108b_claim_update.json", claim_update)
    write_json(output_dir / "summary/task108b_next_task_decision.json", next_task_decision)
    write_csv(output_dir / "tables/task108b_qmsum_targeted_repair_table.csv", comparisons)

    return {
        "repair_summary": repair_summary,
        "target_rows": target_rows_payload,
        "condition_metrics": condition_metrics,
        "before_after_proxy_comparison": before_after_proxy_comparison,
        "output_shape_audit": output_shape_audit,
        "residual_risk_delta": residual_risk_delta,
        "claim_update": claim_update,
        "next_task_decision": next_task_decision,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze T108B QMSum targeted repair attempt.")
    parser.add_argument("--run-artifact", type=Path, default=DEFAULT_RUN_ARTIFACT)
    parser.add_argument("--before-jsonl", type=Path, default=DEFAULT_BEFORE_JSONL)
    parser.add_argument("--target-dataset", type=Path, default=DEFAULT_TARGET_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--t103d-closure", type=Path, default=DEFAULT_T103D_CLOSURE)
    args = parser.parse_args()
    result = analyze(
        run_artifact=args.run_artifact,
        before_jsonl=args.before_jsonl,
        target_dataset=args.target_dataset,
        output_dir=args.output_dir,
        t103d_closure=args.t103d_closure,
    )
    print(json.dumps(result["repair_summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
