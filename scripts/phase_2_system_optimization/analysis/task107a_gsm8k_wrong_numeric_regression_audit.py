from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_system_build_and_evaluation.analysis.t47_quality_refinement import normalize_numeric
from scripts.phase_2_system_optimization.analysis.task95b_quality_proxy_calibration import (
    calibrate_row,
    load_jsonl,
)


DEFAULT_BASE = Path("results/phase_2_system_optimization/final_reruns")
DEFAULT_T105A_DIR = DEFAULT_BASE / "task105a_gsm8k_controlled_speed_matrix"
DEFAULT_T106B_DIR = DEFAULT_BASE / "task106b_gsm8k_cap_limited_fix"
DEFAULT_OUTPUT_DIR = DEFAULT_BASE / "task107a_gsm8k_wrong_numeric_regression_audit"
DEFAULT_BEFORE_JSONL = DEFAULT_T105A_DIR / "runs/cc_dflash_r2_light_gpu_gsm8k_short_seed42_n100_mnt256.jsonl"
DEFAULT_FIXED_JSONL = (
    DEFAULT_T106B_DIR / "runs/cc_dflash_r2_light_gpu_gsm8k_seed42_n100_mnt256_concise_final_answer.jsonl"
)
DEFAULT_BASELINE_JSONL = DEFAULT_T105A_DIR / "runs/baseline_ar_gsm8k_short_seed42_n100_mnt256.jsonl"
DEFAULT_DFLASH_JSONL = DEFAULT_T105A_DIR / "runs/dflash_r1_gsm8k_short_seed42_n100_mnt256.jsonl"

OUTPUT_RELATIVE_PATHS = (
    "summary/task107a_audit_summary.json",
    "summary/task107a_wrong_numeric_before_after.json",
    "summary/task107a_wrong_numeric_fixture_overlap.json",
    "summary/task107a_wrong_numeric_row_audit.jsonl",
    "summary/task107a_attribution_counts.json",
    "summary/task107a_t107b_fix_options.json",
    "summary/task107a_claim_update.json",
    "summary/task107a_next_task_decision.json",
    "tables/task107a_wrong_numeric_regression_table.csv",
)

ID_KEYS = ("fixture_id", "dataset_id", "sample_id", "id", "question_id")
NUMBER_RE = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["fixture_id", "primary_attribution"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fixture_id(row: dict[str, Any], index: int) -> str:
    for key in ID_KEYS:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return f"row_{index:04d}"


def _preview(text: Any, limit: int = 280) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def _tail(text: Any, limit: int = 360) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    return ("..." if len(compact) > limit else "") + compact[-limit:]


def _numbers(text: Any) -> list[str]:
    if not isinstance(text, str):
        return []
    values: list[str] = []
    for match in NUMBER_RE.finditer(text):
        normalized = normalize_numeric(match.group(0))
        if normalized is not None:
            values.append(normalized)
    return values


def _number_present(expected: Any, text: Any) -> bool:
    expected_numeric = normalize_numeric(expected)
    if expected_numeric is not None:
        return expected_numeric in _numbers(text)
    return isinstance(expected, str) and isinstance(text, str) and expected in text


def _avg(values: list[float]) -> float | None:
    return round(mean(values), 6) if values else None


def _numeric(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _calibrate(path: Path, profile: str) -> list[dict[str, Any]]:
    calibrated: list[dict[str, Any]] = []
    for index, row in enumerate(load_jsonl(path), start=1):
        item = calibrate_row(row, profile=profile, row_index=index, pair_id=_fixture_id(row, index), artifact=path)
        item["fixture_id"] = _fixture_id(row, index)
        item["raw_row"] = row
        calibrated.append(item)
    return calibrated


def _by_fixture(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["fixture_id"]): row for row in rows}


def _wrong_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row["fixture_id"]) for row in rows if row["calibrated_label"] == "strict_wrong_numeric"}


def _cap_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row["fixture_id"]) for row in rows if row["calibrated_label"] == "cap_limited_incomplete"}


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = Counter(row["calibrated_label"] for row in rows)
    return {
        "row_count": len(rows),
        "strict_correct_count": sum(1 for row in rows if row["strict_correct"]),
        "strict_wrong_numeric_count": labels.get("strict_wrong_numeric", 0),
        "cap_limited_incomplete_count": labels.get("cap_limited_incomplete", 0),
        "format_or_extraction_sensitive_count": labels.get("format_or_extraction_sensitive", 0),
        "answer_missing_count": labels.get("answer_missing", 0),
        "proxy_uncertain_count": labels.get("proxy_uncertain", 0),
        "final_answer_marker_count": sum(1 for row in rows if row["final_answer_marker_present"]),
        "avg_output_tokens": _avg(
            [
                float(row["raw_row"].get("output_tokens", row["raw_row"].get("generated_token_count")))
                for row in rows
                if isinstance(row["raw_row"].get("output_tokens", row["raw_row"].get("generated_token_count")), (int, float))
            ]
        ),
        "avg_t_compress_ms": _avg(
            [
                float(row["raw_row"]["t_compress_ms"])
                for row in rows
                if isinstance(row["raw_row"].get("t_compress_ms"), (int, float))
            ]
        ),
    }


def _label_snapshot(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "present": False,
            "label": None,
            "strict_correct": False,
            "strict_extracted_answer": None,
            "final_answer_marker_present": False,
            "output_tokens": None,
            "generated_text_preview": "",
        }
    return {
        "present": True,
        "label": row["calibrated_label"],
        "strict_correct": row["strict_correct"],
        "strict_extracted_answer": row["strict_extracted_answer"],
        "final_answer_marker_present": row["final_answer_marker_present"],
        "output_tokens": row["output_tokens"],
        "generated_text_preview": _preview(row["raw_row"].get("generated_text"), 180),
    }


def _references_for(fid: str, baseline_by_id: dict[str, dict[str, Any]], dflash_by_id: dict[str, dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    return baseline_by_id.get(fid), dflash_by_id.get(fid)


def _classify_row(
    *,
    fid: str,
    before: dict[str, Any] | None,
    fixed: dict[str, Any],
    baseline: dict[str, Any] | None,
    dflash: dict[str, Any] | None,
) -> tuple[list[str], str, list[str]]:
    tags: list[str] = []
    notes: list[str] = []
    before_label = before["calibrated_label"] if before else None
    fixed_raw = fixed["raw_row"]
    fixed_text = fixed_raw.get("generated_text")
    expected = fixed.get("expected_answer")
    fixed_tokens = fixed_raw.get("output_tokens", fixed_raw.get("generated_token_count"))
    before_tokens = before["raw_row"].get("output_tokens", before["raw_row"].get("generated_token_count")) if before else None
    expected_present = _number_present(expected, fixed_text)

    reference_wrong = [
        row for row in (baseline, dflash) if row is not None and row["calibrated_label"] == "strict_wrong_numeric"
    ]
    reference_correct = [
        row for row in (baseline, dflash) if row is not None and row["strict_correct"]
    ]
    if reference_wrong:
        tags.append("reference_also_wrong")
    if before_label == "cap_limited_incomplete" and fixed["calibrated_label"] == "strict_wrong_numeric":
        tags.extend(["resolved_cap_but_wrong_number", "answer_changed_after_cap_fix"])
        notes.append("Row moved from cap-limited before T106B to strict wrong numeric after policy.")
    if before is not None and before["calibrated_label"] == "strict_wrong_numeric" and fixed["calibrated_label"] == "strict_wrong_numeric":
        tags.append("persistent_wrong_numeric")
    if expected_present:
        tags.append("expected_answer_appears_but_final_wrong")
    if fixed["strict_extracted_answer"] not in (None, "") and expected_present:
        tags.append("wrong_final_despite_correct_intermediate")
    if isinstance(before_tokens, (int, float)) and isinstance(fixed_tokens, (int, float)) and fixed_tokens < before_tokens * 0.65:
        tags.append("policy_overcompressed_reasoning")
    if isinstance(fixed_tokens, (int, float)) and fixed_tokens <= 80 and not expected_present:
        tags.append("policy_overcompressed_reasoning")
    if reference_correct and not reference_wrong and fixed["calibrated_label"] == "strict_wrong_numeric":
        tags.append("compression_path_specific_wrong_numeric")
    compressed_preview = " ".join(
        str(fixed_raw.get(key, "")) for key in ("compressed_prompt_preview", "compressed_context_preview", "final_prompt_preview")
    )
    if normalize_numeric(expected) is not None and normalize_numeric(expected) not in _numbers(compressed_preview):
        tags.append("compressed_context_missing_needed_detail")
    if fixed["strict_extracted_answer"] not in (None, "") and not expected_present:
        tags.append("arithmetic_error_in_reasoning")

    # Priority order keeps attribution stable and claim-safe.
    if "expected_answer_appears_but_final_wrong" in tags:
        primary = "expected_answer_appears_but_final_wrong"
    elif "resolved_cap_but_wrong_number" in tags:
        primary = "resolved_cap_but_wrong_number"
    elif "reference_also_wrong" in tags and len(reference_wrong) == 2:
        primary = "reference_also_wrong"
    elif "policy_overcompressed_reasoning" in tags:
        primary = "policy_overcompressed_reasoning"
    elif "compressed_context_missing_needed_detail" in tags:
        primary = "compressed_context_missing_needed_detail"
    elif "arithmetic_error_in_reasoning" in tags:
        primary = "arithmetic_error_in_reasoning"
    elif "wrong_final_despite_correct_intermediate" in tags:
        primary = "wrong_final_despite_correct_intermediate"
    elif "reference_also_wrong" in tags:
        primary = "reference_also_wrong"
    else:
        primary = "unknown_requires_rerun_or_manual_review"
        tags.append(primary)
    return sorted(set(tags)), primary, notes


def _decide_next(
    *,
    attribution_counts: Counter[str],
    overlap: dict[str, Any],
    total_wrong: int,
) -> dict[str, Any]:
    if total_wrong == 0:
        return {
            "next_task": "T108A — QMSum Targeted Recheck / Fix Feasibility",
            "t107b_recommended": False,
            "recommended_fix_type": "none",
            "reason": "no_wrong_numeric_rows_after_t106b",
        }
    shared_reference = attribution_counts.get("reference_also_wrong", 0)
    policy_like = (
        attribution_counts.get("policy_overcompressed_reasoning", 0)
        + attribution_counts.get("resolved_cap_but_wrong_number", 0)
        + attribution_counts.get("answer_changed_after_cap_fix", 0)
    )
    extractor_like = (
        attribution_counts.get("expected_answer_appears_but_final_wrong", 0)
        + attribution_counts.get("wrong_final_despite_correct_intermediate", 0)
    )
    if shared_reference >= max(1, total_wrong // 2 + 1):
        return {
            "next_task": "T108A — QMSum Targeted Recheck / Fix Feasibility",
            "t107b_recommended": False,
            "recommended_fix_type": "none",
            "reason": "wrong_numeric_mostly_shared_with_references",
        }
    if extractor_like >= max(1, total_wrong // 2):
        return {
            "next_task": "T107B — Optional GSM8K Policy Refinement Fix",
            "t107b_recommended": True,
            "recommended_fix_type": "extractor_or_policy_audit",
            "reason": "expected_answer_or_intermediate_presence_makes_final_numeric_policy_worth_audit",
            "candidate_policy": (
                "Show only the necessary arithmetic. Verify the calculation once. End with exactly one line: "
                "Final answer: <number>. Do not continue after the final answer."
            ),
        }
    if policy_like >= max(1, total_wrong // 2):
        return {
            "next_task": "T107B — Optional GSM8K Policy Refinement Fix",
            "t107b_recommended": True,
            "recommended_fix_type": "soft_concise_policy_with_minimal_arithmetic_verification",
            "reason": "wrong_numeric_rows_are_mixed_but_policy_or_cap_fix_related",
            "candidate_policy": (
                "Show only the necessary arithmetic. Verify the calculation once. End with exactly one line: "
                "Final answer: <number>. Do not continue after the final answer."
            ),
        }
    return {
        "next_task": "T107B — Optional GSM8K Policy Refinement Fix",
        "t107b_recommended": True,
        "recommended_fix_type": "small_candidate_variant_only",
        "reason": "mixed_wrong_numeric_attribution",
        "candidate_policy": (
            "Show only the necessary arithmetic. Verify the calculation once. End with exactly one line: "
            "Final answer: <number>. Do not continue after the final answer."
        ),
    }


def analyze(
    *,
    before_jsonl: Path = DEFAULT_BEFORE_JSONL,
    fixed_jsonl: Path = DEFAULT_FIXED_JSONL,
    baseline_jsonl: Path = DEFAULT_BASELINE_JSONL,
    dflash_jsonl: Path = DEFAULT_DFLASH_JSONL,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    before_rows = _calibrate(before_jsonl, "T105A CC-DFlash-R2 Light GPU")
    fixed_rows = _calibrate(fixed_jsonl, "T106B CC-DFlash-R2 Light GPU Fixed")
    baseline_rows = _calibrate(baseline_jsonl, "T105A Baseline-AR")
    dflash_rows = _calibrate(dflash_jsonl, "T105A DFlash-R1")

    before_by_id = _by_fixture(before_rows)
    fixed_by_id = _by_fixture(fixed_rows)
    baseline_by_id = _by_fixture(baseline_rows)
    dflash_by_id = _by_fixture(dflash_rows)
    before_wrong = _wrong_ids(before_rows)
    fixed_wrong = _wrong_ids(fixed_rows)
    baseline_wrong = _wrong_ids(baseline_rows)
    dflash_wrong = _wrong_ids(dflash_rows)
    before_cap = _cap_ids(before_rows)

    overlap = {
        "before_wrong_numeric_count": len(before_wrong),
        "fixed_wrong_numeric_count": len(fixed_wrong),
        "wrong_in_both_count": len(before_wrong & fixed_wrong),
        "wrong_in_both_ids": sorted(before_wrong & fixed_wrong),
        "newly_wrong_after_t106b_count": len(fixed_wrong - before_wrong),
        "newly_wrong_after_t106b_ids": sorted(fixed_wrong - before_wrong),
        "fixed_wrong_from_t105a_count": len(before_wrong - fixed_wrong),
        "fixed_wrong_from_t105a_ids": sorted(before_wrong - fixed_wrong),
        "wrong_shared_with_baseline_count": len(fixed_wrong & baseline_wrong),
        "wrong_shared_with_baseline_ids": sorted(fixed_wrong & baseline_wrong),
        "wrong_shared_with_dflash_count": len(fixed_wrong & dflash_wrong),
        "wrong_shared_with_dflash_ids": sorted(fixed_wrong & dflash_wrong),
        "wrong_shared_with_any_reference_count": len(fixed_wrong & (baseline_wrong | dflash_wrong)),
        "wrong_shared_with_any_reference_ids": sorted(fixed_wrong & (baseline_wrong | dflash_wrong)),
        "cc_only_wrong_after_t106b_count": len(fixed_wrong - (baseline_wrong | dflash_wrong)),
        "cc_only_wrong_after_t106b_ids": sorted(fixed_wrong - (baseline_wrong | dflash_wrong)),
        "new_wrong_from_previously_cap_limited_count": len((fixed_wrong - before_wrong) & before_cap),
        "new_wrong_from_previously_cap_limited_ids": sorted((fixed_wrong - before_wrong) & before_cap),
    }

    row_audit: list[dict[str, Any]] = []
    attribution_counts: Counter[str] = Counter()
    primary_counts: Counter[str] = Counter()
    for fid in sorted(fixed_wrong):
        fixed = fixed_by_id[fid]
        before = before_by_id.get(fid)
        baseline, dflash = _references_for(fid, baseline_by_id, dflash_by_id)
        tags, primary, notes = _classify_row(fid=fid, before=before, fixed=fixed, baseline=baseline, dflash=dflash)
        attribution_counts.update(tags)
        primary_counts[primary] += 1
        fixed_raw = fixed["raw_row"]
        before_raw = before["raw_row"] if before else {}
        row_audit.append(
            {
                "fixture_id": fid,
                "expected_answer": fixed.get("expected_answer"),
                "expected_numeric": fixed.get("expected_numeric"),
                "before_label": before["calibrated_label"] if before else None,
                "fixed_label": fixed["calibrated_label"],
                "baseline_label": baseline["calibrated_label"] if baseline else None,
                "dflash_label": dflash["calibrated_label"] if dflash else None,
                "before_extracted_answer": before.get("strict_extracted_answer") if before else None,
                "fixed_extracted_answer": fixed.get("strict_extracted_answer"),
                "baseline_extracted_answer": baseline.get("strict_extracted_answer") if baseline else None,
                "dflash_extracted_answer": dflash.get("strict_extracted_answer") if dflash else None,
                "was_cap_limited_before_t106b": before["calibrated_label"] == "cap_limited_incomplete" if before else False,
                "t106b_created_final_marker": fixed["final_answer_marker_present"] and not (before and before["final_answer_marker_present"]),
                "answer_shorter_after_t106b": (
                    isinstance(before_raw.get("output_tokens"), (int, float))
                    and isinstance(fixed_raw.get("output_tokens"), (int, float))
                    and fixed_raw["output_tokens"] < before_raw["output_tokens"]
                ),
                "before_output_tokens": before_raw.get("output_tokens", before_raw.get("generated_token_count")),
                "fixed_output_tokens": fixed_raw.get("output_tokens", fixed_raw.get("generated_token_count")),
                "expected_number_appears_in_fixed_text": _number_present(fixed.get("expected_answer"), fixed_raw.get("generated_text")),
                "references": {
                    "baseline": _label_snapshot(baseline),
                    "dflash": _label_snapshot(dflash),
                },
                "attribution_tags": tags,
                "primary_attribution": primary,
                "notes": notes,
                "before_generated_text_preview": _preview(before_raw.get("generated_text"), 300),
                "before_generated_text_tail": _tail(before_raw.get("generated_text"), 360),
                "fixed_generated_text_preview": _preview(fixed_raw.get("generated_text"), 300),
                "fixed_generated_text_tail": _tail(fixed_raw.get("generated_text"), 360),
                "compressed_prompt_preview": _preview(fixed_raw.get("compressed_prompt_preview"), 240),
                "final_prompt_tail_preview": _preview(fixed_raw.get("final_prompt_tail_preview"), 240),
            }
        )

    before_after = {
        "before_artifact": str(before_jsonl),
        "fixed_artifact": str(fixed_jsonl),
        "before_summary": _summary(before_rows),
        "fixed_summary": _summary(fixed_rows),
        "delta": {
            "strict_wrong_numeric_delta": len(fixed_wrong) - len(before_wrong),
            "strict_correct_delta": _summary(fixed_rows)["strict_correct_count"] - _summary(before_rows)["strict_correct_count"],
            "cap_limited_delta": _summary(fixed_rows)["cap_limited_incomplete_count"]
            - _summary(before_rows)["cap_limited_incomplete_count"],
            "final_answer_marker_delta": _summary(fixed_rows)["final_answer_marker_count"]
            - _summary(before_rows)["final_answer_marker_count"],
        },
    }

    next_task = _decide_next(attribution_counts=attribution_counts, overlap=overlap, total_wrong=len(fixed_wrong))
    fix_options = {
        "t107b_justified": bool(next_task["t107b_recommended"]),
        "candidate_t107b_policy": (
            "Show only the necessary arithmetic. Verify the calculation once. End with exactly one line: "
            "Final answer: <number>. Do not continue after the final answer."
        ),
        "options": [
            {
                "option": "soft_concise_policy_with_minimal_arithmetic_verification",
                "recommended": next_task.get("recommended_fix_type")
                == "soft_concise_policy_with_minimal_arithmetic_verification",
                "scope_guard": "T107B only; no default switch.",
            },
            {
                "option": "extractor_or_policy_audit",
                "recommended": next_task.get("recommended_fix_type") == "extractor_or_policy_audit",
                "scope_guard": "Only if expected answer appears but final numeric differs.",
            },
            {
                "option": "no_t107b_target_model_limitation",
                "recommended": next_task.get("reason") == "wrong_numeric_mostly_shared_with_references",
                "scope_guard": "Treat as target/reference-shared arithmetic limitation.",
            },
        ],
    }
    claim_update = {
        "claim_status": "SCOPED_GSM8K_CANDIDATE_WITH_WRONG_NUMERIC_CAVEAT",
        "allowed_claims": [
            "T107A audits the wrong-numeric regression after the T106B concise final-answer policy.",
            "The audit attributes wrong-numeric increase using existing T105A/T106B artifacts only.",
            "T106B remains a cap/finalization improvement, but wrong-numeric behavior requires caveated interpretation.",
        ],
        "blocked_claims": [
            "The wrong-numeric issue is fixed.",
            "Quality is fully preserved.",
            "Optimized CC-DFlash should become default.",
            "T107A validates a new policy.",
            "QMSum semantic risk is resolved.",
        ],
    }
    audit_summary = {
        "task": "T107A",
        "title": "GSM8K Wrong-Numeric Regression Audit",
        "decision": "PASS_WITH_CAVEAT",
        "analysis_only": True,
        "no_benchmark_run": True,
        "no_model_inference": True,
        "wrong_numeric_delta": overlap["fixed_wrong_numeric_count"] - overlap["before_wrong_numeric_count"],
        "wrong_numeric_fixture_overlap": overlap,
        "primary_attribution_counts": dict(primary_counts),
        "attribution_tag_counts": dict(attribution_counts),
        "t107b_recommended": next_task["t107b_recommended"],
        "next_task": next_task["next_task"],
    }
    attribution_payload = {
        "primary_attribution_counts": dict(primary_counts),
        "attribution_tag_counts": dict(attribution_counts),
        "row_count": len(row_audit),
    }
    table_rows = [
        {
            "fixture_id": row["fixture_id"],
            "before_label": row["before_label"],
            "fixed_label": row["fixed_label"],
            "baseline_label": row["baseline_label"],
            "dflash_label": row["dflash_label"],
            "before_extracted_answer": row["before_extracted_answer"],
            "fixed_extracted_answer": row["fixed_extracted_answer"],
            "primary_attribution": row["primary_attribution"],
            "attribution_tags": ";".join(row["attribution_tags"]),
        }
        for row in row_audit
    ]

    outputs = {
        "summary/task107a_audit_summary.json": audit_summary,
        "summary/task107a_wrong_numeric_before_after.json": before_after,
        "summary/task107a_wrong_numeric_fixture_overlap.json": overlap,
        "summary/task107a_attribution_counts.json": attribution_payload,
        "summary/task107a_t107b_fix_options.json": fix_options,
        "summary/task107a_claim_update.json": claim_update,
        "summary/task107a_next_task_decision.json": next_task,
    }
    for relative, payload in outputs.items():
        _write_json(output_dir / relative, payload)
    _write_jsonl(output_dir / "summary/task107a_wrong_numeric_row_audit.jsonl", row_audit)
    _write_csv(output_dir / "tables/task107a_wrong_numeric_regression_table.csv", table_rows)

    return {
        "audit_summary": audit_summary,
        "before_after": before_after,
        "wrong_numeric_fixture_overlap": overlap,
        "row_audit": row_audit,
        "attribution_counts": attribution_payload,
        "t107b_fix_options": fix_options,
        "claim_update": claim_update,
        "next_task_decision": next_task,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit Task107A GSM8K wrong-numeric regression from existing artifacts.")
    parser.add_argument("--before-jsonl", type=Path, default=DEFAULT_BEFORE_JSONL)
    parser.add_argument("--fixed-jsonl", type=Path, default=DEFAULT_FIXED_JSONL)
    parser.add_argument("--baseline-jsonl", type=Path, default=DEFAULT_BASELINE_JSONL)
    parser.add_argument("--dflash-jsonl", type=Path, default=DEFAULT_DFLASH_JSONL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = analyze(
        before_jsonl=args.before_jsonl,
        fixed_jsonl=args.fixed_jsonl,
        baseline_jsonl=args.baseline_jsonl,
        dflash_jsonl=args.dflash_jsonl,
        output_dir=args.output_dir,
    )
    print(json.dumps(result["audit_summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
