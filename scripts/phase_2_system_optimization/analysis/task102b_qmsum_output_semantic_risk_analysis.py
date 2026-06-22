from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_QMSUM_JSONL = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102_qmsum_light_gpu_n30_feasibility_run/runs/"
    "20260622_151200_cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl"
)
DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102b_qmsum_output_semantic_risk_analysis"
)
DEFAULT_TASK100B_SUMMARY = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task100b_light_gpu_n100_controlled_run/summary/"
    "task100b_light_gpu_n100_summary.json"
)

OUTPUT_RELATIVE_PATHS = (
    Path("task102b_qmsum_semantic_risk_summary.json"),
    Path("task102b_qmsum_row_labels.jsonl"),
    Path("task102b_qmsum_low_proxy_rows.jsonl"),
    Path("task102b_qmsum_cap_or_incomplete_rows.jsonl"),
    Path("task102b_qmsum_slowest_rows.jsonl"),
    Path("task102b_qmsum_bottleneck_table.csv"),
    Path("task102b_qmsum_claim_update.json"),
    Path("task102b_next_task_decision.json"),
)

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "but",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "his",
    "in",
    "is",
    "it",
    "its",
    "more",
    "not",
    "of",
    "on",
    "or",
    "she",
    "so",
    "that",
    "the",
    "their",
    "there",
    "they",
    "this",
    "to",
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
    "summary",
    "talked",
    "team",
    "topic",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


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
    seen: list[Any] = []
    for row in rows:
        for key in keys:
            if key not in row:
                continue
            value = row[key]
            if key == "local_files_only":
                bool_value = _boolish(value)
                if bool_value is not None:
                    value = bool_value
            if value not in seen:
                seen.append(value)
    return seen


def normalize_tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in STOPWORDS
    ]


def _content_tokens(text: str) -> list[str]:
    return [token for token in normalize_tokens(text) if token not in GENERIC_TERMS]


def _bigrams(tokens: list[str]) -> set[tuple[str, str]]:
    return set(zip(tokens, tokens[1:]))


def _overlap(output: str, reference: str) -> dict[str, float | None]:
    out_tokens = _content_tokens(output)
    ref_tokens = _content_tokens(reference)
    if not ref_tokens:
        return {
            "unigram_recall": None,
            "unigram_precision": None,
            "bigram_recall": None,
            "length_ratio": None,
        }
    out_set = set(out_tokens)
    ref_set = set(ref_tokens)
    hits = len(out_set & ref_set)
    out_bigrams = _bigrams(out_tokens)
    ref_bigrams = _bigrams(ref_tokens)
    bigram_recall = len(out_bigrams & ref_bigrams) / len(ref_bigrams) if ref_bigrams else None
    return {
        "unigram_recall": hits / len(ref_set),
        "unigram_precision": hits / len(out_set) if out_set else 0.0,
        "bigram_recall": bigram_recall,
        "length_ratio": len(out_tokens) / len(ref_tokens) if ref_tokens else None,
    }


def _keyword_overlap(output: str, signal: str) -> float | None:
    out_set = set(_content_tokens(output))
    signal_set = set(_content_tokens(signal))
    if not signal_set:
        return None
    return len(out_set & signal_set) / len(signal_set)


def _ends_incomplete(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    dangling = (
        "and",
        "or",
        "but",
        "because",
        "with",
        "such as",
        "including",
        "to",
        "for",
        ":",
        ",",
        ";",
        "-",
    )
    return not stripped.endswith((".", "?", "!", '"', "'", ")", "]")) or lowered.endswith(dangling)


def _failure_flag(row: dict[str, Any]) -> bool:
    for key, value in row.items():
        lowered = key.lower()
        if "oom" in lowered or "cuda" in lowered or "failure" in lowered or "error" in lowered:
            if value in (None, "", False, 0, "False", "false", "none", "None"):
                continue
            return True
    return False


def label_row(row: dict[str, Any]) -> dict[str, Any]:
    generated = _text(row, "generated_text", "output", "answer")
    reference = _text(row, "expected_answer", "reference_answer", "target_answer")
    question = _text(row, "question", "query")
    source = " ".join(
        part
        for part in [
            _text(row, "original_prompt_preview"),
            _text(row, "compressed_prompt_preview"),
            _text(row, "final_prompt_tail_preview"),
        ]
        if part
    )
    output_tokens = _number(row, "generated_token_count", "output_tokens", "new_tokens")
    max_new_tokens = _number(row, "max_new_tokens")
    overlap = _overlap(generated, reference)
    question_overlap = _keyword_overlap(generated, question)
    source_overlap = _keyword_overlap(generated, source)

    empty = not generated.strip()
    cap_close = bool(max_new_tokens and output_tokens and output_tokens >= max_new_tokens * 0.96)
    cap_limited = (not empty) and (cap_close or _ends_incomplete(generated))
    output_content = _content_tokens(generated)
    question_content = set(_content_tokens(question))
    too_short = (not empty) and (len(output_content) < 8 or (question_content and _keyword_overlap(generated, question) == 0))
    mostly_generic = bool(output_content) and (sum(1 for token in output_content if token in GENERIC_TERMS) / len(output_content) > 0.55)
    low_reference = (
        overlap["unigram_recall"] is not None
        and overlap["unigram_recall"] < 0.24
        and (overlap["bigram_recall"] is None or overlap["bigram_recall"] < 0.08)
    )
    possible_evidence_miss = bool(
        (low_reference or too_short)
        and (question_overlap is None or question_overlap < 0.20)
        and (source_overlap is None or source_overlap < 0.08)
    )
    reference_source_overlap = _keyword_overlap(reference, source) if reference and source else None
    source_reference_mismatch_possible = bool(
        low_reference
        and reference_source_overlap is not None
        and reference_source_overlap < 0.18
    )
    proxy_uncertain = bool(
        not reference
        or source_reference_mismatch_possible
        or (
            low_reference
            and not possible_evidence_miss
            and (overlap["length_ratio"] is not None and 0.25 <= overlap["length_ratio"] <= 1.75)
        )
    )
    acceptable = bool(
        not empty
        and not cap_limited
        and not too_short
        and not low_reference
        and not proxy_uncertain
        and overlap["unigram_recall"] is not None
        and overlap["unigram_recall"] >= 0.24
    )
    labels = {
        "completed_answer": bool(generated.strip() and not cap_limited),
        "empty_or_malformed": empty,
        "cap_limited_or_incomplete": cap_limited,
        "low_reference_overlap": bool(low_reference),
        "possible_evidence_miss": bool(possible_evidence_miss),
        "source_reference_mismatch_possible": bool(source_reference_mismatch_possible),
        "too_short_or_generic": bool(too_short or mostly_generic),
        "proxy_uncertain": bool(proxy_uncertain),
        "acceptable_proxy_signal": bool(acceptable),
    }
    return {
        "fixture_id": row.get("fixture_id") or row.get("dataset_id") or row.get("prompt_id"),
        "dataset_id": row.get("dataset_id"),
        "labels": labels,
        "metrics": {
            "output_token_count": output_tokens,
            "max_new_tokens": max_new_tokens,
            "reference_unigram_recall": overlap["unigram_recall"],
            "reference_unigram_precision": overlap["unigram_precision"],
            "reference_bigram_recall": overlap["bigram_recall"],
            "answer_reference_length_ratio": overlap["length_ratio"],
            "output_question_keyword_overlap": question_overlap,
            "output_source_keyword_overlap": source_overlap,
            "t_compress_ms": _number(row, "t_compress_ms"),
            "e2e_time_s": _number(row, "e2e_time_s", "generation_time_s"),
            "tokens_per_second": _number(row, "tokens_per_second", "tok_per_sec"),
            "tau_mean": _number(row, "tau_mean"),
            "t_prefill_ms": _number(row, "t_prefill_ms"),
            "R_actual": _number(row, "R_actual", "r_actual"),
            "vram_allocated_gib": _number(row, "vram_allocated_gib", "prefill_vram_allocated_gib"),
            "vram_reserved_gib": _number(row, "vram_reserved_gib", "prefill_vram_reserved_gib"),
        },
        "previews": {
            "question": question[:240],
            "expected_answer": reference[:360],
            "generated_text": generated[:500],
            "generated_tail": generated[-240:],
        },
        "metadata": {
            "compressor_profile": row.get("compressor_profile"),
            "compressor_device_map": row.get("compressor_device_map"),
            "requested_compressor_device_map": row.get("requested_compressor_device_map"),
            "local_files_only": row.get("local_files_only"),
            "qmsum_answer_policy_type": row.get("qmsum_answer_policy_type"),
        },
        "failure_flag": _failure_flag(row),
    }


def _stats(values: list[float]) -> dict[str, float | None]:
    clean = [value for value in values if value is not None and not math.isnan(value)]
    if not clean:
        return {"avg": None, "min": None, "max": None, "p95": None}
    ordered = sorted(clean)
    p95_index = min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "avg": round(statistics.fmean(clean), 6),
        "min": round(min(clean), 6),
        "max": round(max(clean), 6),
        "p95": round(ordered[p95_index], 6),
    }


def build_runtime_summary(labeled_rows: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = [
        "t_compress_ms",
        "e2e_time_s",
        "tokens_per_second",
        "tau_mean",
        "t_prefill_ms",
        "R_actual",
        "vram_allocated_gib",
        "vram_reserved_gib",
        "output_token_count",
        "reference_unigram_recall",
    ]
    stats = {
        name: _stats([row["metrics"].get(name) for row in labeled_rows if row["metrics"].get(name) is not None])
        for name in metric_names
    }

    def top_by(metric: str, reverse: bool = True, limit: int = 5) -> list[dict[str, Any]]:
        rows = [row for row in labeled_rows if row["metrics"].get(metric) is not None]
        rows.sort(key=lambda row: row["metrics"][metric], reverse=reverse)
        return [_compact_row(row) for row in rows[:limit]]

    risky_rows = [row for row in labeled_rows if _is_risky(row)]
    acceptable_rows = [row for row in labeled_rows if row["labels"].get("acceptable_proxy_signal")]
    return {
        "stats": stats,
        "slowest_rows": top_by("e2e_time_s"),
        "highest_t_compress_rows": top_by("t_compress_ms"),
        "lowest_tokens_per_second_rows": top_by("tokens_per_second", reverse=False),
        "highest_vram_reserved_rows": top_by("vram_reserved_gib"),
        "risky_vs_acceptable": {
            "risky_count": len(risky_rows),
            "acceptable_count": len(acceptable_rows),
            "risky_avg_e2e_time_s": _stats([row["metrics"].get("e2e_time_s") for row in risky_rows])["avg"],
            "acceptable_avg_e2e_time_s": _stats([row["metrics"].get("e2e_time_s") for row in acceptable_rows])["avg"],
            "risky_avg_t_compress_ms": _stats([row["metrics"].get("t_compress_ms") for row in risky_rows])["avg"],
            "acceptable_avg_t_compress_ms": _stats(
                [row["metrics"].get("t_compress_ms") for row in acceptable_rows]
            )["avg"],
            "risky_avg_output_tokens": _stats([row["metrics"].get("output_token_count") for row in risky_rows])["avg"],
            "acceptable_avg_output_tokens": _stats(
                [row["metrics"].get("output_token_count") for row in acceptable_rows]
            )["avg"],
            "risky_avg_reference_overlap": _stats(
                [row["metrics"].get("reference_unigram_recall") for row in risky_rows]
            )["avg"],
            "acceptable_avg_reference_overlap": _stats(
                [row["metrics"].get("reference_unigram_recall") for row in acceptable_rows]
            )["avg"],
        },
    }


def _compact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "fixture_id": row["fixture_id"],
        "labels": row["labels"],
        "metrics": row["metrics"],
        "generated_text_preview": row["previews"]["generated_text"][:240],
    }


def _is_risky(row: dict[str, Any]) -> bool:
    labels = row["labels"]
    return any(
        labels.get(name)
        for name in (
            "empty_or_malformed",
            "cap_limited_or_incomplete",
            "low_reference_overlap",
            "possible_evidence_miss",
            "too_short_or_generic",
            "proxy_uncertain",
        )
    )


def _metadata_confirms(rows: list[dict[str, Any]]) -> bool:
    return (
        _unique(rows, "compressor_profile") == ["light"]
        and "cuda" in _unique(rows, "compressor_device_map")
        and (not _unique(rows, "requested_compressor_device_map") or "cuda" in _unique(rows, "requested_compressor_device_map"))
        and True in _unique(rows, "local_files_only")
    )


def _label_counts(labeled_rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in labeled_rows:
        for label, value in row["labels"].items():
            if value:
                counts[label] += 1
    return {label: counts.get(label, 0) for label in next(iter(labeled_rows), {"labels": {}})["labels"]}


def build_summary(rows: list[dict[str, Any]], labeled_rows: list[dict[str, Any]], task100b_summary: dict[str, Any]) -> dict[str, Any]:
    label_counts = _label_counts(labeled_rows)
    runtime = build_runtime_summary(labeled_rows)
    metadata = {
        "condition": _unique(rows, "condition"),
        "dataset_name": _unique(rows, "dataset_name"),
        "compressor_profile": _unique(rows, "compressor_profile"),
        "compressor_device_map": _unique(rows, "compressor_device_map"),
        "requested_compressor_device_map": _unique(rows, "requested_compressor_device_map"),
        "local_files_only": _unique(rows, "local_files_only"),
        "max_new_tokens": _unique(rows, "max_new_tokens"),
        "qmsum_answer_policy_type": _unique(rows, "qmsum_answer_policy_type"),
    }
    failure_flags = sum(1 for row in labeled_rows if row["failure_flag"])
    task100b_vram = _lookup_nested(task100b_summary, ("light_gpu_n100", "max_vram_reserved_gib"))
    if task100b_vram is None:
        task100b_vram = task100b_summary.get("max_vram_reserved_gib", 4.43)
    return {
        "task": "T102B",
        "source_artifact": str(DEFAULT_QMSUM_JSONL),
        "row_count": len(rows),
        "label_counts": label_counts,
        "metadata": metadata,
        "metadata_confirms_light_gpu": _metadata_confirms(rows),
        "failure_flags": failure_flags,
        "runtime": runtime,
        "compression_gpu_stability": {
            "R_actual_avg": runtime["stats"]["R_actual"]["avg"],
            "R_actual_min": runtime["stats"]["R_actual"]["min"],
            "R_actual_max": runtime["stats"]["R_actual"]["max"],
            "t_compress_ms_avg": runtime["stats"]["t_compress_ms"]["avg"],
            "t_compress_ms_p95": runtime["stats"]["t_compress_ms"]["p95"],
            "max_vram_reserved_gib": runtime["stats"]["vram_reserved_gib"]["max"],
            "max_vram_allocated_gib": runtime["stats"]["vram_allocated_gib"]["max"],
            "oom_cuda_failure_flags": failure_flags,
            "local_8gb_context": {
                "task100b_gsm8k_light_gpu_max_reserved_gib": task100b_vram,
                "task102_qmsum_light_gpu_max_reserved_gib": runtime["stats"]["vram_reserved_gib"]["max"],
                "wording": "Observed on local RTX 4070 8GB-class GPU across GSM8K n100 and QMSum n30; not a universal 8GB deployment guarantee.",
            },
        },
    }


def _lookup_nested(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def build_claim_update(summary: dict[str, Any]) -> dict[str, Any]:
    counts = summary.get("label_counts", {})
    row_count = summary.get("row_count", 0) or 0
    severe_empty = counts.get("empty_or_malformed", 0) >= max(2, row_count * 0.30)
    severe_unusable = counts.get("proxy_uncertain", 0) >= max(1, row_count * 0.75)
    if severe_empty or severe_unusable or not summary.get("metadata_confirms_light_gpu", True):
        qmsum_status = "NOT_CLOSED"
    elif counts.get("low_reference_overlap", 0) > row_count * 0.50 or counts.get("cap_limited_or_incomplete", 0) >= row_count * 0.20:
        qmsum_status = "SCOPED_WITH_RISK"
    else:
        qmsum_status = "CLOSED_AS_BENCHMARK_SCOPED_PROXY_AUDIT"
    return {
        "QMSum claim": {
            "status": qmsum_status,
            "allowed_wording": [
                "QMSum-style long-context prompts were covered by Light GPU feasibility plus deterministic semantic-risk/proxy analysis."
            ],
            "blocked_wording": ["QMSum semantic correctness is proven."],
            "reason": "Deterministic lexical/evidence proxy analysis was produced without an LLM judge.",
        },
        "Local 8GB-class feasibility": {
            "status": "STRENGTHENED_LOCAL_OBSERVATION",
            "allowed_wording": [
                "Observed on local RTX 4070 8GB-class GPU across GSM8K n100 and QMSum n30."
            ],
            "blocked_wording": ["Universal 8GB deployment readiness is proven."],
        },
        "Benchmark-scoped quality": {
            "status": "GSM8K_NUMERIC_PLUS_QMSUM_PROXY",
            "allowed_wording": [
                "Quality evidence covers GSM8K deterministic numeric proxy and QMSum deterministic semantic-risk/proxy audit."
            ],
            "blocked_wording": ["Final semantic correctness is proven."],
        },
        "Speed": {
            "status": "PENDING_T103_REFERENCE_ALIGNMENT",
            "reason": "QMSum Light GPU runtime is measured, but near-DFlash / final speed wording still needs aligned references.",
        },
        "Full matrix": {
            "status": "PENDING_T104",
            "reason": "T102B analyzes one QMSum condition, not a full matrix.",
        },
        "GPU default": {
            "status": "PENDING_T105",
            "reason": "Candidate strengthened, but default decision belongs to T105.",
        },
        "DFlash-R1 broken": {
            "status": "REMOVED",
            "wording": "DFlash-R1 retained as reference condition.",
        },
    }


def build_next_task_decision(summary: dict[str, Any]) -> dict[str, Any]:
    counts = summary.get("label_counts", {})
    row_count = summary.get("row_count", 0) or 0
    severe = (
        counts.get("empty_or_malformed", 0) >= max(2, row_count * 0.30)
        or counts.get("cap_limited_or_incomplete", 0) >= max(1, row_count * 0.50)
        or counts.get("proxy_uncertain", 0) >= max(1, row_count * 0.80)
        or not summary.get("metadata_confirms_light_gpu", False)
        or summary.get("failure_flags", 0) > 0
    )
    if severe:
        return {
            "next_task": "T102A — QMSum Failure Audit / Fix",
            "reason": "Semantic-risk analysis found severe malformed/cap/proxy or metadata issues that block claim closure.",
            "automatic_benchmark": False,
        }
    return {
        "next_task": "T103 — Reference Alignment for Speed Claim",
        "reason": "QMSum feasibility and semantic-risk/proxy analysis are complete enough to proceed to reference alignment.",
        "automatic_benchmark": False,
    }


def _write_bottleneck_table(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stats = summary["runtime"]["stats"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "avg", "min", "max", "p95"])
        writer.writeheader()
        for metric, values in stats.items():
            writer.writerow({"metric": metric, **values})


def analyze(
    *,
    qmsum_jsonl: Path = DEFAULT_QMSUM_JSONL,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    task100b_summary_path: Path = DEFAULT_TASK100B_SUMMARY,
) -> dict[str, Any]:
    rows = read_jsonl(qmsum_jsonl)
    labeled_rows = [label_row(row) for row in rows]
    task100b_summary = load_json(task100b_summary_path)
    summary = build_summary(rows, labeled_rows, task100b_summary)
    summary["source_artifact"] = str(qmsum_jsonl)
    claim_update = build_claim_update(summary)
    next_task = build_next_task_decision(summary)
    decision = "PASS_WITH_CAVEAT" if next_task["next_task"].startswith("T103") else "PARTIAL"
    result = {
        "decision": decision,
        "summary": summary,
        "claim_update": claim_update,
        "next_task_decision": next_task,
    }

    write_json(output_dir / OUTPUT_RELATIVE_PATHS[0], result)
    write_jsonl(output_dir / OUTPUT_RELATIVE_PATHS[1], labeled_rows)
    write_jsonl(
        output_dir / OUTPUT_RELATIVE_PATHS[2],
        [row for row in labeled_rows if row["labels"].get("low_reference_overlap")],
    )
    write_jsonl(
        output_dir / OUTPUT_RELATIVE_PATHS[3],
        [row for row in labeled_rows if row["labels"].get("cap_limited_or_incomplete")],
    )
    write_jsonl(output_dir / OUTPUT_RELATIVE_PATHS[4], summary["runtime"]["slowest_rows"])
    _write_bottleneck_table(output_dir / OUTPUT_RELATIVE_PATHS[5], summary)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[6], claim_update)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[7], next_task)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze Task102B QMSum Light GPU semantic-risk/proxy signals.")
    parser.add_argument("--qmsum-jsonl", type=Path, default=DEFAULT_QMSUM_JSONL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--task100b-summary", type=Path, default=DEFAULT_TASK100B_SUMMARY)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = analyze(
        qmsum_jsonl=args.qmsum_jsonl,
        output_dir=args.output_dir,
        task100b_summary_path=args.task100b_summary,
    )
    print(json.dumps({"decision": result["decision"], "output_dir": str(args.output_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
