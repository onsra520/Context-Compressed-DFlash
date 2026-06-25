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

from scripts.phase_2_system_optimization.analysis.task95b_quality_proxy_calibration import (
    calibrate_row,
    load_jsonl,
)


DEFAULT_BASE = Path("results/phase_2_system_optimization/final_reruns")
DEFAULT_T105A_DIR = DEFAULT_BASE / "task105a_gsm8k_controlled_speed_matrix"
DEFAULT_OUTPUT_DIR = DEFAULT_BASE / "task106a_gsm8k_cap_limited_attribution_audit"
DEFAULT_BASELINE_JSONL = DEFAULT_T105A_DIR / "runs/baseline_ar_gsm8k_short_seed42_n100_mnt256.jsonl"
DEFAULT_DFLASH_JSONL = DEFAULT_T105A_DIR / "runs/dflash_r1_gsm8k_short_seed42_n100_mnt256.jsonl"
DEFAULT_CC_JSONL = DEFAULT_T105A_DIR / "runs/cc_dflash_r2_light_gpu_gsm8k_short_seed42_n100_mnt256.jsonl"
DEFAULT_T100B_JSONL = (
    DEFAULT_BASE
    / "task100b_light_gpu_n100_controlled_run/runs/20260621_1555_cc_dflash_r2_light_gpu_seed42_n100_mnt256.jsonl"
)

CONDITION_LABELS = {
    "baseline": "Baseline-AR",
    "dflash": "DFlash-R1",
    "cc": "CC-DFlash-R2 Light GPU",
    "t100b": "Task100B CC-DFlash-R2 Light GPU",
}
ID_KEYS = ("fixture_id", "dataset_id", "sample_id", "id", "question_id")
NUMBER_RE = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
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
    fieldnames = list(rows[0].keys()) if rows else ["fixture_id", "note"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fixture_id(row: dict[str, Any], fallback_index: int) -> str:
    for key in ID_KEYS:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return f"row_{fallback_index:04d}"


def _preview(text: Any, limit: int = 260) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def _tail(text: Any, limit: int = 320) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    return ("..." if len(compact) > limit else "") + compact[-limit:]


def _rate(count: int, total: int) -> float:
    return round(count / total, 6) if total else 0.0


def _avg(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [row.get(key) for row in rows if isinstance(row.get(key), (int, float))]
    return round(mean(values), 6) if values else None


def _number_present(expected: Any, text: Any) -> bool:
    if expected in (None, "") or not isinstance(text, str):
        return False
    expected_digits = re.sub(r"[^0-9.\-]", "", str(expected))
    if not expected_digits:
        return str(expected).strip() in text
    return expected_digits in [re.sub(r"[^0-9.\-]", "", token) for token in NUMBER_RE.findall(text)]


def _load_and_calibrate(path: Path, profile: str) -> list[dict[str, Any]]:
    raw_rows = load_jsonl(path)
    calibrated: list[dict[str, Any]] = []
    for index, row in enumerate(raw_rows, start=1):
        label = calibrate_row(row, profile=profile, row_index=index, pair_id=_fixture_id(row, index), artifact=path)
        label["raw_row"] = row
        label["fixture_id"] = _fixture_id(row, index)
        calibrated.append(label)
    return calibrated


def _summarize_condition(labels: list[dict[str, Any]]) -> dict[str, Any]:
    label_counts = Counter(row["calibrated_label"] for row in labels)
    rows = len(labels)
    return {
        "rows": rows,
        "strict_correct_count": sum(1 for row in labels if row["strict_correct"]),
        "strict_correct_rate": _rate(sum(1 for row in labels if row["strict_correct"]), rows),
        "cap_limited_incomplete_count": label_counts.get("cap_limited_incomplete", 0),
        "strict_wrong_numeric_count": label_counts.get("strict_wrong_numeric", 0),
        "format_or_extraction_sensitive_count": label_counts.get("format_or_extraction_sensitive", 0),
        "answer_missing_count": label_counts.get("answer_missing", 0),
        "proxy_uncertain_count": label_counts.get("proxy_uncertain", 0),
        "final_answer_marker_present_count": sum(1 for row in labels if row["final_answer_marker_present"]),
        "exact_containment_count": sum(1 for row in labels if row["exact_containment"]),
        "avg_output_tokens": _avg([row["raw_row"] for row in labels], "output_tokens"),
        "avg_t_compress_ms": _avg([row["raw_row"] for row in labels], "t_compress_ms"),
        "avg_e2e_time_s": _avg([row["raw_row"] for row in labels], "e2e_time_s"),
        "avg_R_actual": _avg([row["raw_row"] for row in labels], "R_actual"),
        "calibrated_label_counts": dict(label_counts),
    }


def _by_fixture(labels: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["fixture_id"]): row for row in labels}


def _cap_ids(labels: list[dict[str, Any]]) -> set[str]:
    return {str(row["fixture_id"]) for row in labels if row["calibrated_label"] == "cap_limited_incomplete"}


def _overlap(baseline_labels: list[dict[str, Any]], dflash_labels: list[dict[str, Any]], cc_labels: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = _cap_ids(baseline_labels)
    dflash = _cap_ids(dflash_labels)
    cc = _cap_ids(cc_labels)
    references = baseline | dflash
    return {
        "baseline_cap_limited_count": len(baseline),
        "dflash_cap_limited_count": len(dflash),
        "cc_cap_limited_count": len(cc),
        "baseline_cap_limited_ids": sorted(baseline),
        "dflash_cap_limited_ids": sorted(dflash),
        "cc_cap_limited_ids": sorted(cc),
        "cc_only_count": len(cc - references),
        "cc_only_ids": sorted(cc - references),
        "cc_shared_with_baseline_ids": sorted(cc & baseline),
        "cc_shared_with_dflash_ids": sorted(cc & dflash),
        "cc_shared_with_any_reference_count": len(cc & references),
        "cc_shared_with_any_reference_ids": sorted(cc & references),
        "shared_by_all_three_count": len(cc & baseline & dflash),
        "shared_by_all_three_ids": sorted(cc & baseline & dflash),
    }


def _label_snapshot(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "present": False,
            "label": None,
            "strict_correct": False,
            "final_answer_marker_present": False,
            "output_tokens": None,
            "strict_extracted_answer": None,
        }
    return {
        "present": True,
        "label": row["calibrated_label"],
        "strict_correct": row["strict_correct"],
        "final_answer_marker_present": row["final_answer_marker_present"],
        "output_tokens": row["output_tokens"],
        "strict_extracted_answer": row["strict_extracted_answer"],
        "generated_text_preview": _preview(row["raw_row"].get("generated_text"), 180),
    }


def _attribution_tags(
    cc_row: dict[str, Any],
    baseline_row: dict[str, Any] | None,
    dflash_row: dict[str, Any] | None,
) -> list[str]:
    raw = cc_row["raw_row"]
    tags: list[str] = []
    output_tokens = raw.get("output_tokens", raw.get("generated_token_count"))
    max_new_tokens = raw.get("max_new_tokens")
    generated_text = raw.get("generated_text")
    expected = cc_row.get("expected_answer")

    if (
        isinstance(output_tokens, (int, float))
        and isinstance(max_new_tokens, (int, float))
        and output_tokens >= max_new_tokens
    ):
        tags.append("truncated_before_final_answer")
    if not cc_row["final_answer_marker_present"]:
        tags.append("final_answer_marker_missing")
    if _number_present(expected, generated_text):
        tags.append("expected_numeric_present_without_marker")
    if isinstance(output_tokens, (int, float)) and isinstance(max_new_tokens, (int, float)) and output_tokens >= 0.9 * max_new_tokens:
        tags.append("verbose_or_long_reasoning_near_cap")

    reference_caps = [
        row for row in (baseline_row, dflash_row) if row is not None and row["calibrated_label"] == "cap_limited_incomplete"
    ]
    if reference_caps:
        tags.append("shared_target_or_prompt_cap_behavior")

    reference_token_values = [
        row["raw_row"].get("output_tokens")
        for row in (baseline_row, dflash_row)
        if row is not None and isinstance(row["raw_row"].get("output_tokens"), (int, float))
    ]
    if isinstance(output_tokens, (int, float)) and reference_token_values and output_tokens > max(reference_token_values) + 25:
        tags.append("cc_output_longer_than_references")

    if cc_row["strict_extracted_answer"] not in (None, "") and not cc_row["strict_correct"]:
        tags.append("strict_wrong_numeric_also_detected")
    if not tags:
        tags.append("unknown_static_attribution")
    return tags


def _overlap_class(fixture_id: str, overlap: dict[str, Any]) -> str:
    if fixture_id in set(overlap["cc_only_ids"]):
        return "cc_only"
    if fixture_id in set(overlap["shared_by_all_three_ids"]):
        return "shared_with_references"
    if fixture_id in set(overlap["cc_shared_with_any_reference_ids"]):
        return "shared_with_one_reference"
    return "cc_cap_limited_not_classified"


def _row_audit(
    cc_labels: list[dict[str, Any]],
    baseline_labels: list[dict[str, Any]],
    dflash_labels: list[dict[str, Any]],
    overlap: dict[str, Any],
) -> list[dict[str, Any]]:
    baseline_by_id = _by_fixture(baseline_labels)
    dflash_by_id = _by_fixture(dflash_labels)
    rows: list[dict[str, Any]] = []
    for cc_row in cc_labels:
        if cc_row["calibrated_label"] != "cap_limited_incomplete":
            continue
        fixture_id = str(cc_row["fixture_id"])
        baseline_row = baseline_by_id.get(fixture_id)
        dflash_row = dflash_by_id.get(fixture_id)
        tags = _attribution_tags(cc_row, baseline_row, dflash_row)
        rows.append(
            {
                "fixture_id": fixture_id,
                "expected_answer": cc_row["expected_answer"],
                "expected_numeric": cc_row["expected_numeric"],
                "overlap_class": _overlap_class(fixture_id, overlap),
                "attribution_tags": tags,
                "primary_attribution": _primary_attribution(tags),
                "cc_label": cc_row["calibrated_label"],
                "cc_strict_correct": cc_row["strict_correct"],
                "cc_final_answer_marker_present": cc_row["final_answer_marker_present"],
                "cc_strict_extracted_answer": cc_row["strict_extracted_answer"],
                "cc_exact_containment": cc_row["exact_containment"],
                "cc_output_tokens": cc_row["output_tokens"],
                "cc_max_new_tokens": cc_row["max_new_tokens"],
                "cc_t_compress_ms": cc_row["raw_row"].get("t_compress_ms"),
                "cc_e2e_time_s": cc_row["raw_row"].get("e2e_time_s"),
                "cc_R_actual": cc_row["raw_row"].get("R_actual"),
                "cc_generated_text_preview": _preview(cc_row["raw_row"].get("generated_text")),
                "cc_generated_text_tail": _tail(cc_row["raw_row"].get("generated_text")),
                "baseline_reference": _label_snapshot(baseline_row),
                "dflash_reference": _label_snapshot(dflash_row),
                "notes": _row_notes(tags),
            }
        )
    return rows


def _primary_attribution(tags: list[str]) -> str:
    for candidate in (
        "shared_target_or_prompt_cap_behavior",
        "truncated_before_final_answer",
        "final_answer_marker_missing",
        "expected_numeric_present_without_marker",
        "cc_output_longer_than_references",
        "strict_wrong_numeric_also_detected",
    ):
        if candidate in tags:
            return candidate
    return tags[0] if tags else "unknown_static_attribution"


def _row_notes(tags: list[str]) -> list[str]:
    notes = []
    if "shared_target_or_prompt_cap_behavior" in tags:
        notes.append("At least one historical reference also appears cap-limited on this fixture.")
    if "truncated_before_final_answer" in tags:
        notes.append("CC-DFlash output appears to hit max_new_tokens before a final marker.")
    if "expected_numeric_present_without_marker" in tags:
        notes.append("Expected numeric answer appears somewhere in text, but strict final-answer policy does not rescue it.")
    if "cc_output_longer_than_references" in tags:
        notes.append("CC-DFlash output is materially longer than reference outputs for the same fixture.")
    return notes or ["Static attribution remains inconclusive without a rerun or semantic review."]


def _attribution_counts(row_audit: list[dict[str, Any]]) -> dict[str, Any]:
    tag_counts: Counter[str] = Counter()
    primary_counts: Counter[str] = Counter()
    overlap_counts: Counter[str] = Counter()
    for row in row_audit:
        tag_counts.update(row["attribution_tags"])
        primary_counts[row["primary_attribution"]] += 1
        overlap_counts[row["overlap_class"]] += 1
    return {
        "row_count": len(row_audit),
        "tag_counts": dict(tag_counts),
        "primary_attribution_counts": dict(primary_counts),
        "overlap_class_counts": dict(overlap_counts),
    }


def _t100b_stability(t100b_labels: list[dict[str, Any]] | None, cc_labels: list[dict[str, Any]]) -> dict[str, Any]:
    cc_ids = _cap_ids(cc_labels)
    if t100b_labels is None:
        return {
            "t100b_available": False,
            "interpretation": "t100b_artifact_not_available",
            "t105a_cc_cap_limited_count": len(cc_ids),
        }
    t100b_ids = _cap_ids(t100b_labels)
    shared = t100b_ids & cc_ids
    t100b_summary = _summarize_condition(t100b_labels)
    t105a_summary = _summarize_condition(cc_labels)
    if t100b_ids == cc_ids and t100b_summary["strict_correct_count"] == t105a_summary["strict_correct_count"]:
        interpretation = "stable_repeated_cc_dflash_r2_light_gpu_pattern"
    elif shared:
        interpretation = "partially_stable_repeated_cc_dflash_r2_light_gpu_pattern"
    else:
        interpretation = "not_stable_or_samples_differ"
    return {
        "t100b_available": True,
        "t100b_rows": len(t100b_labels),
        "t105a_cc_rows": len(cc_labels),
        "t100b_strict_correct_count": t100b_summary["strict_correct_count"],
        "t105a_cc_strict_correct_count": t105a_summary["strict_correct_count"],
        "t100b_cap_limited_count": len(t100b_ids),
        "t105a_cc_cap_limited_count": len(cc_ids),
        "t100b_strict_wrong_numeric_count": t100b_summary["strict_wrong_numeric_count"],
        "t105a_cc_strict_wrong_numeric_count": t105a_summary["strict_wrong_numeric_count"],
        "shared_cap_limited_ids": sorted(shared),
        "t100b_only_cap_limited_ids": sorted(t100b_ids - cc_ids),
        "t105a_only_cap_limited_ids": sorted(cc_ids - t100b_ids),
        "interpretation": interpretation,
        "note": "This checks whether the optimized GSM8K cap-limited pattern predates the T102/T103 QMSum branch.",
    }


def _fix_options(overlap: dict[str, Any], counts: dict[str, Any], row_audit: list[dict[str, Any]]) -> dict[str, Any]:
    cc_count = overlap["cc_cap_limited_count"]
    cc_only = overlap["cc_only_count"]
    fixable_tag_names = {
        "truncated_before_final_answer",
        "final_answer_marker_missing",
        "verbose_or_long_reasoning_near_cap",
        "cc_output_longer_than_references",
    }
    fixable_rows = sum(
        1 for row in row_audit if any(tag in fixable_tag_names for tag in row["attribution_tags"])
    )
    cc_specific_fraction = _rate(cc_only, cc_count)
    fixable_fraction = _rate(fixable_rows, max(cc_count, 1))
    if cc_only and fixable_fraction >= 1.0:
        recommended = "T106B"
        recommendation = (
            "Run an optional targeted cap-limited fix investigation before the default-candidate decision. "
            "Candidate fixes should stay scoped to GSM8K answer-finalization or cap-policy behavior."
        )
    else:
        recommended = "T106C"
        recommendation = (
            "No CC-specific cap-limited fix is justified by this static audit; proceed to default-candidate "
            "decision with the cap-limited caveat preserved."
        )
    return {
        "recommended_next_task": recommended,
        "t106b_recommended": recommended == "T106B",
        "cc_specific_cap_limited_fraction": cc_specific_fraction,
        "fixable_static_signal_fraction": fixable_fraction,
        "candidate_fix_options": [
            {
                "option": "answer_finalization_policy",
                "description": "Add or test a narrow GSM8K final-answer encouragement for cap-limited rows only.",
                "scope_guard": "Do not change default prompt/runtime until separately validated.",
            },
            {
                "option": "max_new_tokens_policy_check",
                "description": "Evaluate whether cap-limited rows need a small token-cap policy check rather than quality relabeling.",
                "scope_guard": "No automatic n1000 or full benchmark.",
            },
            {
                "option": "extractor_policy_audit",
                "description": "Only applicable when expected numeric answers appear without final markers; do not count as strict correct.",
                "scope_guard": "Preserve Task95B strict proxy unless explicitly changed by a later task.",
            },
        ],
        "recommendation": recommendation,
    }


def _claim_update() -> dict[str, Any]:
    return {
        "claim_status": "SCOPED_WITH_GSM8K_CAP_LIMITED_CAVEAT",
        "allowed_claims": [
            "Task105A supports a bounded GSM8K speed advantage over Baseline-AR for optimized CC-DFlash-R2 Light GPU.",
            "Task105A does not show optimized CC-DFlash-R2 Light GPU preserving the strict GSM8K proxy versus references.",
            "T106A attributes the strict proxy gap primarily as a cap-limited/final-answer-marker audit target when supported by row evidence.",
        ],
        "blocked_claims": [
            "Optimized CC-DFlash-R2 Light GPU is the overall default winner.",
            "GSM8K quality is preserved versus Baseline-AR or DFlash-R1.",
            "The strict drop was caused by QMSum remediation or T103 changes.",
            "Cap-limited rows should be counted as correct without a policy change.",
            "A fix is validated by this static audit.",
        ],
        "required_language": (
            "GSM8K optimized CC-DFlash-R2 Light GPU remains fast but carries a cap-limited strict-proxy caveat; "
            "T106A is attribution only, not a remediation."
        ),
    }


def _next_task(fix_options: dict[str, Any]) -> dict[str, Any]:
    if fix_options["recommended_next_task"] == "T106B":
        return {
            "next_task": "T106B — Optional Cap-Limited Fix",
            "status": "PLANNED / CONDITIONAL",
            "reason": "Static attribution found CC-specific cap/final-marker/verbosity signals worth a small scoped fix decision.",
        }
    return {
        "next_task": "T106C — Optimized Default Candidate Decision",
        "status": "PLANNED",
        "reason": "Static attribution did not justify a targeted cap-limited fix before candidate decision.",
    }


def _table_rows(row_audit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in row_audit:
        rows.append(
            {
                "fixture_id": row["fixture_id"],
                "overlap_class": row["overlap_class"],
                "primary_attribution": row["primary_attribution"],
                "attribution_tags": "|".join(row["attribution_tags"]),
                "cc_output_tokens": row["cc_output_tokens"],
                "cc_max_new_tokens": row["cc_max_new_tokens"],
                "cc_final_answer_marker_present": row["cc_final_answer_marker_present"],
                "baseline_label": row["baseline_reference"]["label"],
                "dflash_label": row["dflash_reference"]["label"],
                "expected_answer": row["expected_answer"],
            }
        )
    return rows


def analyze(
    baseline_jsonl: Path = DEFAULT_BASELINE_JSONL,
    dflash_jsonl: Path = DEFAULT_DFLASH_JSONL,
    cc_jsonl: Path = DEFAULT_CC_JSONL,
    t100b_jsonl: Path | None = DEFAULT_T100B_JSONL,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    baseline_labels = _load_and_calibrate(baseline_jsonl, "Baseline-AR")
    dflash_labels = _load_and_calibrate(dflash_jsonl, "DFlash-R1")
    cc_labels = _load_and_calibrate(cc_jsonl, "CC-DFlash-R2 Light GPU")
    t100b_labels = _load_and_calibrate(t100b_jsonl, "Task100B CC-DFlash-R2 Light GPU") if t100b_jsonl and t100b_jsonl.exists() else None

    overlap = _overlap(baseline_labels, dflash_labels, cc_labels)
    row_audit = _row_audit(cc_labels, baseline_labels, dflash_labels, overlap)
    attribution_counts = _attribution_counts(row_audit)
    stability = _t100b_stability(t100b_labels, cc_labels)
    fix_options = _fix_options(overlap, attribution_counts, row_audit)
    claim_update = _claim_update()
    next_task_decision = _next_task(fix_options)

    result = {
        "task": "T106A",
        "title": "GSM8K Cap-Limited Attribution Audit",
        "decision": "PASS_WITH_CAVEAT",
        "analysis_only": True,
        "inputs": {
            "baseline_jsonl": str(baseline_jsonl),
            "dflash_jsonl": str(dflash_jsonl),
            "cc_jsonl": str(cc_jsonl),
            "t100b_jsonl": str(t100b_jsonl) if t100b_jsonl else None,
        },
        "condition_summaries": {
            CONDITION_LABELS["baseline"]: _summarize_condition(baseline_labels),
            CONDITION_LABELS["dflash"]: _summarize_condition(dflash_labels),
            CONDITION_LABELS["cc"]: _summarize_condition(cc_labels),
        },
        "cap_limited_fixture_overlap": overlap,
        "cc_cap_limited_row_audit": row_audit,
        "attribution_counts": attribution_counts,
        "t100b_vs_t105a_stability": stability,
        "fix_options": fix_options,
        "claim_update": claim_update,
        "next_task_decision": next_task_decision,
        "scope_guard": {
            "no_benchmark": True,
            "no_model_inference": True,
            "no_gpu_run": True,
            "no_qmsum": True,
            "no_llm_judge": True,
            "no_config_change": True,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "summary/task106a_audit_summary.json", result)
    _write_json(output_dir / "summary/task106a_cap_limited_fixture_overlap.json", overlap)
    _write_jsonl(output_dir / "summary/task106a_cc_cap_limited_row_audit.jsonl", row_audit)
    _write_json(output_dir / "summary/task106a_attribution_counts.json", attribution_counts)
    _write_json(output_dir / "summary/task106a_t100b_vs_t105a_stability.json", stability)
    _write_json(output_dir / "summary/task106a_fix_options.json", fix_options)
    _write_json(output_dir / "summary/task106a_claim_update.json", claim_update)
    _write_json(output_dir / "summary/task106a_next_task_decision.json", next_task_decision)
    _write_csv(output_dir / "tables/task106a_cap_limited_attribution_table.csv", _table_rows(row_audit))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Static T106A GSM8K cap-limited attribution audit")
    parser.add_argument("--baseline-jsonl", type=Path, default=DEFAULT_BASELINE_JSONL)
    parser.add_argument("--dflash-jsonl", type=Path, default=DEFAULT_DFLASH_JSONL)
    parser.add_argument("--cc-jsonl", type=Path, default=DEFAULT_CC_JSONL)
    parser.add_argument("--t100b-jsonl", type=Path, default=DEFAULT_T100B_JSONL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    result = analyze(
        baseline_jsonl=args.baseline_jsonl,
        dflash_jsonl=args.dflash_jsonl,
        cc_jsonl=args.cc_jsonl,
        t100b_jsonl=args.t100b_jsonl,
        output_dir=args.output_dir,
    )
    cc = result["condition_summaries"][CONDITION_LABELS["cc"]]
    overlap = result["cap_limited_fixture_overlap"]
    print("status=PASS_WITH_CAVEAT")
    print(f"cc_strict={cc['strict_correct_count']}/{cc['rows']}")
    print(f"cc_cap_limited={overlap['cc_cap_limited_count']}")
    print(f"cc_only_cap_limited={overlap['cc_only_count']}")
    print(f"next_task={result['next_task_decision']['next_task']}")
    print(f"wrote={args.output_dir}")


if __name__ == "__main__":
    main()
