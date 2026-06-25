from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task105b_qmsum_controlled_runtime_matrix"
)
DEFAULT_RUN_DIR = DEFAULT_OUTPUT_DIR / "runs"
DEFAULT_BASELINE = DEFAULT_RUN_DIR / "baseline_ar_qmsum_seed42_n30_mnt384.jsonl"
DEFAULT_DFLASH = DEFAULT_RUN_DIR / "dflash_r1_qmsum_seed42_n30_mnt384.jsonl"
DEFAULT_OPTIMIZED = DEFAULT_RUN_DIR / "cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl"

STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "because",
    "been",
    "but",
    "did",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "into",
    "its",
    "not",
    "that",
    "the",
    "their",
    "then",
    "there",
    "they",
    "this",
    "was",
    "were",
    "what",
    "when",
    "which",
    "who",
    "why",
    "with",
    "would",
}
GENERIC_TERMS = {
    "answer",
    "context",
    "discussion",
    "meeting",
    "mentioned",
    "question",
    "said",
    "summary",
    "team",
    "topic",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: line {line_number} is not a JSON object")
        rows.append(payload)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else ["condition"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _numeric(row: dict[str, Any], *keys: str) -> float | None:
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


def _text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


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


def _unique(rows: list[dict[str, Any]], *keys: str) -> list[Any]:
    values: list[Any] = []
    for row in rows:
        for key in keys:
            if key not in row:
                continue
            value = row[key]
            bool_value = _boolish(value) if key == "local_files_only" else None
            if bool_value is not None:
                value = bool_value
            if value not in values:
                values.append(value)
    return values


def _numbers(values: list[float | None]) -> list[float]:
    return [float(value) for value in values if isinstance(value, (int, float))]


def _avg(values: list[float | None]) -> float | None:
    nums = _numbers(values)
    return round(mean(nums), 6) if nums else None


def _min(values: list[float | None]) -> float | None:
    nums = _numbers(values)
    return round(min(nums), 6) if nums else None


def _max(values: list[float | None]) -> float | None:
    nums = _numbers(values)
    return round(max(nums), 6) if nums else None


def _rate(count: int, total: int) -> float | None:
    return round(count / total, 6) if total else None


def _e2e_time(row: dict[str, Any]) -> float | None:
    direct = _numeric(row, "e2e_time_s", "end_to_end_time_s")
    if direct is not None:
        return direct
    generation = _numeric(row, "generation_time_s")
    if generation is None:
        return None
    return generation + ((_numeric(row, "t_compress_ms") or 0.0) / 1000.0)


def _stats(rows: list[dict[str, Any]], metric: str, *keys: str) -> dict[str, float | None]:
    values = [_numeric(row, *keys) for row in rows]
    return {
        f"avg_{metric}": _avg(values),
        f"min_{metric}": _min(values),
        f"max_{metric}": _max(values),
    }


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in STOPWORDS and token not in GENERIC_TERMS
    ]


def _reference_overlap(row: dict[str, Any]) -> dict[str, float | None]:
    generated = _tokenize(_text(row, "generated_text"))
    reference = _tokenize(_text(row, "expected_answer", "reference_answer"))
    if not reference:
        return {"reference_unigram_recall": None, "reference_unigram_precision": None}
    generated_set = set(generated)
    reference_set = set(reference)
    hits = len(generated_set & reference_set)
    return {
        "reference_unigram_recall": round(hits / len(reference_set), 6) if reference_set else None,
        "reference_unigram_precision": round(hits / len(generated_set), 6) if generated_set else 0.0,
    }


def _ends_incomplete(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped.endswith((".", "!", "?", '"', "'")):
        return False
    lowered = stripped.lower()
    return lowered.endswith(
        (
            " and",
            " but",
            " because",
            " due to",
            " with",
            " without",
            " including",
            " such as",
            " for",
            " to",
            " of",
        )
    )


def _cap_limited_or_incomplete(row: dict[str, Any]) -> bool:
    output_tokens = _numeric(row, "output_tokens", "generated_token_count")
    max_new_tokens = _numeric(row, "max_new_tokens")
    if output_tokens is not None and max_new_tokens is not None and output_tokens >= max_new_tokens:
        return True
    return _ends_incomplete(_text(row, "generated_text"))


def _failure_flags(rows: list[dict[str, Any]]) -> dict[str, Any]:
    messages: list[str] = []
    for row in rows:
        for key, value in row.items():
            lowered_key = str(key).lower()
            if not any(token in lowered_key for token in ("failure", "error", "oom", "cuda")):
                continue
            if value in (None, "", False):
                continue
            messages.append(f"{key}={value}")
    lowered_messages = [message.lower() for message in messages]
    return {
        "messages": messages,
        "oom_or_cuda_failure": any("oom" in message or "cuda" in message for message in lowered_messages),
    }


def _metadata_ok(
    rows: list[dict[str, Any]],
    *,
    expected_condition: str,
    expected_n: int,
    optimized: bool,
) -> bool:
    if len(rows) != expected_n:
        return False
    for row in rows:
        if row.get("condition") != expected_condition:
            return False
        if row.get("dataset_name") != "qmsum_meeting_qa_long":
            return False
        if row.get("prompt_source") != "dataset":
            return False
        if row.get("max_new_tokens") != 384:
            return False
        if optimized:
            if row.get("compressor_profile") != "light":
                return False
            if str(row.get("compressor_device_map")) not in {"cuda", "cuda:0"}:
                return False
            if str(row.get("requested_compressor_device_map")) not in {"cuda", "cuda:0"}:
                return False
            if row.get("local_files_only") is not True:
                return False
    return True


def _condition_notes(summary: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if not summary["row_count_ok"]:
        notes.append("row count mismatch")
    if not summary["metadata_ok"]:
        notes.append("metadata mismatch")
    if summary["oom_or_cuda_failure"]:
        notes.append("OOM/CUDA failure flag present")
    return notes


def _summarize_condition(
    *,
    label: str,
    expected_condition: str,
    path: Path,
    expected_n: int,
    optimized: bool = False,
) -> dict[str, Any]:
    rows = load_jsonl(path)
    flags = _failure_flags(rows)
    overlaps = [_reference_overlap(row) for row in rows]
    e2e_values = [_e2e_time(row) for row in rows]
    empty_or_malformed = sum(1 for row in rows if not _text(row, "generated_text"))
    cap_limited = sum(1 for row in rows if _cap_limited_or_incomplete(row))
    low_reference_overlap = sum(
        1
        for item in overlaps
        if isinstance(item.get("reference_unigram_recall"), (int, float))
        and item["reference_unigram_recall"] < 0.15
    )
    summary: dict[str, Any] = {
        "condition": label,
        "repo_condition": expected_condition,
        "artifact": str(path),
        "row_count": len(rows),
        "expected_row_count": expected_n,
        "row_count_ok": len(rows) == expected_n,
        "metadata_ok": _metadata_ok(
            rows,
            expected_condition=expected_condition,
            expected_n=expected_n,
            optimized=optimized,
        ),
        "dataset_names": _unique(rows, "dataset_name"),
        "prompt_sources": _unique(rows, "prompt_source"),
        "max_new_tokens_values": _unique(rows, "max_new_tokens"),
        "fixture_ids": [str(row.get("fixture_id") or row.get("dataset_id") or row.get("prompt_id")) for row in rows],
        "empty_or_malformed_output_count": empty_or_malformed,
        "empty_or_malformed_output_rate": _rate(empty_or_malformed, len(rows)),
        "cap_limited_or_incomplete_count": cap_limited,
        "cap_limited_or_incomplete_rate": _rate(cap_limited, len(rows)),
        "low_reference_overlap_count": low_reference_overlap,
        "low_reference_overlap_rate": _rate(low_reference_overlap, len(rows)),
        "avg_reference_unigram_recall": _avg([item["reference_unigram_recall"] for item in overlaps]),
        "avg_reference_unigram_precision": _avg([item["reference_unigram_precision"] for item in overlaps]),
        "failure_flags": flags,
        "oom_or_cuda_failure": flags["oom_or_cuda_failure"],
        "avg_e2e_time_s": _avg(e2e_values),
        "min_e2e_time_s": _min(e2e_values),
        "max_e2e_time_s": _max(e2e_values),
    }
    summary.update(_stats(rows, "generation_time_s", "generation_time_s"))
    summary.update(_stats(rows, "tokens_per_second", "tokens_per_second", "tok_per_sec"))
    summary.update(_stats(rows, "tau_mean", "tau_mean"))
    summary.update(_stats(rows, "t_prefill_ms", "t_prefill_ms"))
    summary.update(_stats(rows, "t_compress_ms", "t_compress_ms"))
    summary.update(_stats(rows, "R_actual", "R_actual", "actual_compression_ratio", "compression_ratio"))
    summary.update(_stats(rows, "vram_allocated_gib", "vram_allocated_gib"))
    summary.update(_stats(rows, "vram_reserved_gib", "vram_reserved_gib"))
    summary.update(_stats(rows, "prefill_vram_allocated_gib", "prefill_vram_allocated_gib"))
    summary.update(_stats(rows, "prefill_vram_reserved_gib", "prefill_vram_reserved_gib"))
    summary.update(_stats(rows, "output_tokens", "output_tokens", "generated_token_count"))
    if optimized:
        summary.update(
            {
                "compressor_profiles": _unique(rows, "compressor_profile"),
                "compressor_device_maps": _unique(rows, "compressor_device_map"),
                "requested_compressor_device_maps": _unique(rows, "requested_compressor_device_map"),
                "local_files_only_values": _unique(rows, "local_files_only"),
                "qmsum_answer_policy_types": _unique(rows, "qmsum_answer_policy_type"),
                "qmsum_answer_policy_enabled_values": _unique(rows, "qmsum_answer_policy_enabled"),
                "compressor_paths_present": all(bool(row.get("compressor_path")) for row in rows),
                "resolved_compressor_paths_present": all(bool(row.get("resolved_compressor_path")) for row in rows),
            }
        )
    summary["notes"] = _condition_notes(summary)
    return summary


def _speed_comparison(optimized: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    optimized_e2e = optimized.get("avg_e2e_time_s")
    reference_e2e = reference.get("avg_e2e_time_s")
    percent_lower: float | None = None
    delta: float | None = None
    if isinstance(optimized_e2e, (int, float)) and isinstance(reference_e2e, (int, float)):
        delta = round(optimized_e2e - reference_e2e, 6)
        if reference_e2e > 0:
            percent_lower = round((reference_e2e - optimized_e2e) / reference_e2e * 100.0, 6)
    return {
        "reference_condition": reference["condition"],
        "optimized_avg_e2e_time_s": optimized_e2e,
        "reference_avg_e2e_time_s": reference_e2e,
        "avg_e2e_time_s_delta_optimized_minus_reference": delta,
        "optimized_percent_lower_e2e_time": percent_lower,
        "optimized_is_faster": delta is not None and delta < 0,
    }


def _runtime_ranking(conditions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(
        [
            {
                "condition": label,
                "avg_e2e_time_s": summary.get("avg_e2e_time_s"),
                "avg_generation_time_s": summary.get("avg_generation_time_s"),
                "avg_tokens_per_second": summary.get("avg_tokens_per_second"),
                "avg_t_compress_ms": summary.get("avg_t_compress_ms"),
                "avg_tau_mean": summary.get("avg_tau_mean"),
            }
            for label, summary in conditions.items()
            if isinstance(summary.get("avg_e2e_time_s"), (int, float))
        ],
        key=lambda item: float(item["avg_e2e_time_s"]),
    )
    optimized = conditions["CC-DFlash-R2 Light GPU"]
    return {
        "ranked_conditions": ranked,
        "optimized_vs_baseline_ar": _speed_comparison(optimized, conditions["Baseline-AR"]),
        "optimized_vs_dflash_r1": _speed_comparison(optimized, conditions["DFlash-R1"]),
        "ranking_scope": "Controlled QMSum n30 mnt384 runtime only; not a semantic correctness ranking.",
    }


def _output_completeness(conditions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "scope": "Deterministic output-shape and reference-overlap diagnostics only.",
        "conditions": {
            label: {
                "row_count": summary["row_count"],
                "empty_or_malformed_output_count": summary["empty_or_malformed_output_count"],
                "empty_or_malformed_output_rate": summary["empty_or_malformed_output_rate"],
                "cap_limited_or_incomplete_count": summary["cap_limited_or_incomplete_count"],
                "cap_limited_or_incomplete_rate": summary["cap_limited_or_incomplete_rate"],
                "low_reference_overlap_count": summary["low_reference_overlap_count"],
                "low_reference_overlap_rate": summary["low_reference_overlap_rate"],
                "avg_reference_unigram_recall": summary["avg_reference_unigram_recall"],
                "avg_reference_unigram_precision": summary["avg_reference_unigram_precision"],
            }
            for label, summary in conditions.items()
        },
    }


def _failure_or_resume_audit(conditions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    condition_audit = {
        label: {
            "artifact": summary["artifact"],
            "row_count": summary["row_count"],
            "expected_row_count": summary["expected_row_count"],
            "row_count_ok": summary["row_count_ok"],
            "metadata_ok": summary["metadata_ok"],
            "oom_or_cuda_failure": summary["oom_or_cuda_failure"],
            "notes": summary["notes"],
        }
        for label, summary in conditions.items()
    }
    return {
        "conditions": condition_audit,
        "resume_required": any(
            not summary["row_count_ok"] or not summary["metadata_ok"] or summary["oom_or_cuda_failure"]
            for summary in conditions.values()
        ),
        "preserve_completed_artifacts": True,
        "do_not_substitute_historical_data": True,
    }


def _qmsum_caveat_carryforward() -> dict[str, Any]:
    return {
        "semantic_correctness_claim": "blocked",
        "source": "T103D/T104 carryforward",
        "summary": (
            "QMSum runtime feasibility is measured, but QMSum semantic correctness is not claimed; "
            "T103D closed the deep-fix branch with persistent residual risk."
        ),
        "carryforward_labels": [
            "no QMSum semantic correctness proof",
            "residual QMSum risk persists",
            "runtime/reference alignment only",
        ],
    }


def _claim_update(
    *,
    complete: bool,
    conditions: dict[str, dict[str, Any]],
    runtime_ranking: dict[str, Any],
) -> dict[str, Any]:
    optimized = conditions["CC-DFlash-R2 Light GPU"]
    optimized_vs_baseline = runtime_ranking["optimized_vs_baseline_ar"]
    optimized_vs_dflash = runtime_ranking["optimized_vs_dflash_r1"]
    quality_caveat_required = (
        optimized["cap_limited_or_incomplete_count"] > 0
        or optimized["empty_or_malformed_output_count"] > 0
        or optimized["low_reference_overlap_count"] > 0
    )
    return {
        "decision_scope": "QMSum controlled runtime matrix only.",
        "controlled_matrix_complete": complete,
        "supported_claims": [
            "T105B measured Baseline-AR, DFlash-R1, and CC-DFlash-R2 Light GPU on matched QMSum n30 mnt384 settings."
            if complete
            else "T105B produced partial QMSum runtime evidence; incomplete or mismatched conditions require isolated resume.",
            "Runtime comparisons are bounded to the local QMSum n30 mnt384 setup.",
        ],
        "optimized_vs_baseline_ar": optimized_vs_baseline,
        "optimized_vs_dflash_r1": optimized_vs_dflash,
        "qmsum_semantic_correctness_claim": "blocked",
        "quality_caveat_required": quality_caveat_required,
        "blocked_claims": [
            "QMSum semantic correctness is proven.",
            "Residual QMSum quality risk is closed.",
            "Full benchmark speed claim is complete.",
            "CC-DFlash-R2 Light GPU wins every reference universally.",
            "Default GPU placement or deployment readiness is proven.",
        ],
        "qmsum_caveat_carryforward": True,
    }


def _next_task_decision(complete: bool, has_oom_or_cuda: bool) -> dict[str, Any]:
    if complete and not has_oom_or_cuda:
        return {
            "next_task": "T105C — Benchmark-Scope Claim Closure",
            "reason": "All three QMSum n30 runtime matrix conditions completed with matching metadata.",
            "automatic_extra_benchmark": False,
        }
    return {
        "next_task": "T105B-R — QMSum Controlled Runtime Matrix Isolated Resume",
        "reason": "At least one QMSum matrix condition is incomplete, failed, or has metadata mismatch.",
        "automatic_extra_benchmark": False,
    }


def _table_rows(conditions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, summary in conditions.items():
        rows.append(
            {
                "condition": label,
                "repo_condition": summary["repo_condition"],
                "row_count": summary["row_count"],
                "metadata_ok": summary["metadata_ok"],
                "avg_e2e_time_s": summary["avg_e2e_time_s"],
                "avg_generation_time_s": summary["avg_generation_time_s"],
                "avg_tokens_per_second": summary["avg_tokens_per_second"],
                "avg_t_prefill_ms": summary["avg_t_prefill_ms"],
                "avg_t_compress_ms": summary["avg_t_compress_ms"],
                "avg_R_actual": summary["avg_R_actual"],
                "avg_tau_mean": summary["avg_tau_mean"],
                "max_vram_reserved_gib": summary["max_vram_reserved_gib"],
                "empty_or_malformed_output_count": summary["empty_or_malformed_output_count"],
                "cap_limited_or_incomplete_count": summary["cap_limited_or_incomplete_count"],
                "low_reference_overlap_count": summary["low_reference_overlap_count"],
                "oom_or_cuda_failure": summary["oom_or_cuda_failure"],
                "artifact": summary["artifact"],
            }
        )
    return rows


def analyze(
    *,
    baseline_jsonl: Path = DEFAULT_BASELINE,
    dflash_jsonl: Path = DEFAULT_DFLASH,
    optimized_jsonl: Path = DEFAULT_OPTIMIZED,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    expected_n: int = 30,
) -> dict[str, Any]:
    summary_dir = output_dir / "summary"
    tables_dir = output_dir / "tables"
    conditions = {
        "Baseline-AR": _summarize_condition(
            label="Baseline-AR",
            expected_condition="Baseline-AR",
            path=baseline_jsonl,
            expected_n=expected_n,
        ),
        "DFlash-R1": _summarize_condition(
            label="DFlash-R1",
            expected_condition="DFlash-R1",
            path=dflash_jsonl,
            expected_n=expected_n,
        ),
        "CC-DFlash-R2 Light GPU": _summarize_condition(
            label="CC-DFlash-R2 Light GPU",
            expected_condition="CC-DFlash-R2",
            path=optimized_jsonl,
            expected_n=expected_n,
            optimized=True,
        ),
    }
    failure_audit = _failure_or_resume_audit(conditions)
    complete = not failure_audit["resume_required"]
    has_oom_or_cuda = any(summary["oom_or_cuda_failure"] for summary in conditions.values())
    decision = "PASS_WITH_CAVEAT" if complete and not has_oom_or_cuda else "PARTIAL"
    runtime_ranking = _runtime_ranking(conditions)
    output_completeness = _output_completeness(conditions)
    caveat = _qmsum_caveat_carryforward()
    claim_update = _claim_update(complete=complete, conditions=conditions, runtime_ranking=runtime_ranking)
    next_task_decision = _next_task_decision(complete, has_oom_or_cuda)
    matrix_summary = {
        "task": "T105B",
        "decision": decision,
        "controlled_matrix_complete": complete,
        "dataset": "qmsum_meeting_qa_long",
        "seed": 42,
        "expected_n": expected_n,
        "max_new_tokens": 384,
        "conditions": list(conditions),
        "qmsum_semantic_correctness_claim": "blocked",
        "no_qmsum_n100": True,
        "no_full_matrix": True,
        "no_llm_judge": True,
        "no_human_scoring": True,
    }

    _write_json(summary_dir / "task105b_matrix_summary.json", matrix_summary)
    _write_json(summary_dir / "task105b_condition_metrics.json", conditions)
    _write_json(summary_dir / "task105b_runtime_ranking.json", runtime_ranking)
    _write_json(summary_dir / "task105b_output_completeness_summary.json", output_completeness)
    _write_json(summary_dir / "task105b_failure_or_resume_audit.json", failure_audit)
    _write_json(summary_dir / "task105b_qmsum_caveat_carryforward.json", caveat)
    _write_json(summary_dir / "task105b_claim_update.json", claim_update)
    _write_json(summary_dir / "task105b_next_task_decision.json", next_task_decision)
    _write_csv(
        tables_dir / "task105b_qmsum_controlled_runtime_matrix.csv",
        _table_rows(conditions),
        fieldnames=[
            "condition",
            "repo_condition",
            "row_count",
            "metadata_ok",
            "avg_e2e_time_s",
            "avg_generation_time_s",
            "avg_tokens_per_second",
            "avg_t_prefill_ms",
            "avg_t_compress_ms",
            "avg_R_actual",
            "avg_tau_mean",
            "max_vram_reserved_gib",
            "empty_or_malformed_output_count",
            "cap_limited_or_incomplete_count",
            "low_reference_overlap_count",
            "oom_or_cuda_failure",
            "artifact",
        ],
    )
    return {
        "decision": decision,
        "controlled_matrix_complete": complete,
        "conditions": conditions,
        "runtime_ranking": runtime_ranking,
        "output_completeness_summary": output_completeness,
        "failure_or_resume_audit": failure_audit,
        "qmsum_caveat_carryforward": caveat,
        "claim_update": claim_update,
        "next_task_decision": next_task_decision,
        "matrix_summary": matrix_summary,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Package T105B QMSum controlled runtime matrix evidence.")
    parser.add_argument("--baseline-jsonl", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--dflash-jsonl", type=Path, default=DEFAULT_DFLASH)
    parser.add_argument("--optimized-jsonl", type=Path, default=DEFAULT_OPTIMIZED)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--expected-n", type=int, default=30)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = analyze(
        baseline_jsonl=args.baseline_jsonl,
        dflash_jsonl=args.dflash_jsonl,
        optimized_jsonl=args.optimized_jsonl,
        output_dir=args.output_dir,
        expected_n=args.expected_n,
    )
    print(json.dumps(result["matrix_summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
