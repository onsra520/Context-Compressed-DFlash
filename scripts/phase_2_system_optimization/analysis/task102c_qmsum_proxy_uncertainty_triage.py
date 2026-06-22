from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_QMSUM_JSONL = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102_qmsum_light_gpu_n30_feasibility_run/runs/"
    "20260622_151200_cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl"
)
DEFAULT_ROW_LABELS = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102b_qmsum_output_semantic_risk_analysis/task102b_qmsum_row_labels.jsonl"
)
DEFAULT_LOW_PROXY_ROWS = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102b_qmsum_output_semantic_risk_analysis/task102b_qmsum_low_proxy_rows.jsonl"
)
DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102c_qmsum_proxy_uncertainty_triage"
)

OUTPUT_RELATIVE_PATHS = (
    Path("task102c_uncertainty_triage_summary.json"),
    Path("task102c_uncertain_row_triage.jsonl"),
    Path("task102c_triage_table.csv"),
    Path("task102c_claim_update.json"),
    Path("task102c_next_task_decision.json"),
)

BUCKETS = (
    "proxy_false_negative",
    "source_reference_mismatch_possible",
    "evidence_miss_likely",
    "generic_or_under_specific",
    "acceptable_after_proxy_review",
    "unresolved_proxy_limitation",
)

STOPWORDS = {
    "about",
    "after",
    "and",
    "answer",
    "because",
    "but",
    "context",
    "did",
    "for",
    "from",
    "had",
    "has",
    "have",
    "into",
    "meeting",
    "question",
    "that",
    "the",
    "their",
    "there",
    "they",
    "this",
    "using",
    "was",
    "were",
    "what",
    "when",
    "which",
    "with",
}
GENERIC_TERMS = {
    "agenda",
    "answer",
    "context",
    "decision",
    "discussed",
    "discussion",
    "general",
    "meeting",
    "point",
    "project",
    "summary",
    "team",
    "topic",
}


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


def _text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _metric(label_row: dict[str, Any], key: str) -> float | None:
    metrics = label_row.get("metrics")
    if isinstance(metrics, dict):
        value = metrics.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in STOPWORDS
    ]


def _content_tokens(text: str) -> list[str]:
    return [token for token in _tokens(text) if token not in GENERIC_TERMS]


def _overlap(a: str, b: str) -> float | None:
    a_set = set(_content_tokens(a))
    b_set = set(_content_tokens(b))
    if not b_set:
        return None
    return len(a_set & b_set) / len(b_set)


def _extract_question(row: dict[str, Any], label_row: dict[str, Any]) -> str:
    previews = label_row.get("previews")
    if isinstance(previews, dict) and isinstance(previews.get("question"), str) and previews["question"].strip():
        return previews["question"].strip()
    explicit = _text(row, "question", "query")
    if explicit:
        return explicit
    tail = _text(row, "final_prompt_tail_preview")
    if "Answer only the question" in tail:
        before = tail.split("Answer only the question", 1)[0]
        # The prompt tail contains the question right before the protected suffix.
        return before[-220:].strip(" .")
    return ""


def _is_uncertain(label_row: dict[str, Any], low_proxy_ids: set[str]) -> bool:
    fixture_id = str(label_row.get("fixture_id") or label_row.get("dataset_id") or "")
    labels = label_row.get("labels")
    if not isinstance(labels, dict):
        return fixture_id in low_proxy_ids
    return bool(labels.get("low_reference_overlap") or labels.get("proxy_uncertain") or fixture_id in low_proxy_ids)


def triage_row(qmsum_row: dict[str, Any], label_row: dict[str, Any]) -> dict[str, Any]:
    fixture_id = str(label_row.get("fixture_id") or qmsum_row.get("fixture_id") or qmsum_row.get("dataset_id") or "")
    labels = label_row.get("labels") if isinstance(label_row.get("labels"), dict) else {}
    metrics = label_row.get("metrics") if isinstance(label_row.get("metrics"), dict) else {}
    previews = label_row.get("previews") if isinstance(label_row.get("previews"), dict) else {}
    generated = _text(qmsum_row, "generated_text") or str(previews.get("generated_text", ""))
    reference = _reference_text(qmsum_row, previews)
    question = _extract_question(qmsum_row, label_row)
    source = " ".join(
        piece
        for piece in [
            _text(qmsum_row, "compressed_prompt_preview"),
            _text(qmsum_row, "original_prompt_preview"),
            _text(qmsum_row, "final_prompt_tail_preview"),
        ]
        if piece
    )
    ref_recall = _metric(label_row, "reference_unigram_recall")
    source_overlap = _metric(label_row, "output_source_keyword_overlap")
    question_overlap = _overlap(generated, question)
    direct_reference_overlap = _overlap(generated, reference)
    output_tokens = _metric(label_row, "output_token_count")
    if output_tokens is None:
        output_tokens = float(len(generated.split())) if generated else 0.0
    generic_ratio = _generic_ratio(generated)

    secondary: list[str] = []
    if labels.get("low_reference_overlap") or (ref_recall is not None and ref_recall < 0.24):
        secondary.append("low_reference_overlap")
    if question and (question_overlap is None or question_overlap < 0.12):
        secondary.append("low_question_overlap")
    if source and (source_overlap is None or source_overlap < 0.10):
        secondary.append("low_source_overlap")
    if not reference:
        secondary.append("reference_missing")
    if not source:
        secondary.append("source_missing")
    if output_tokens < 35:
        secondary.append("output_short")
    if output_tokens > 120 and ref_recall is not None and ref_recall < 0.12:
        secondary.append("output_long_but_offtopic")
    if ref_recall is not None and source_overlap is not None and 0.10 <= ref_recall < 0.24 and source_overlap >= 0.14:
        secondary.append("possible_paraphrase")
    if labels.get("source_reference_mismatch_possible"):
        secondary.append("possible_entity_mismatch")
    if labels.get("cap_limited_or_incomplete"):
        secondary.append("possible_cap_tail_issue")

    if not reference or (not source and not question):
        bucket = "unresolved_proxy_limitation"
        rationale = "Required reference/source/question signals are missing, so deterministic triage cannot decide."
    elif (ref_recall or 0.0) < 0.08 and (source_overlap or 0.0) < 0.08:
        bucket = "evidence_miss_likely"
        rationale = "Output has very low reference and source overlap, indicating a likely evidence miss or off-target answer."
    elif (ref_recall or 0.0) >= 0.24 or (
        not labels.get("low_reference_overlap")
        and direct_reference_overlap is not None
        and direct_reference_overlap >= 0.24
        and (source_overlap or 0.0) >= 0.12
    ):
        bucket = "acceptable_after_proxy_review"
        rationale = "Combined deterministic reference/source signals are sufficient despite the earlier proxy warning."
    elif (source_overlap or 0.0) >= 0.18:
        bucket = "proxy_false_negative"
        rationale = "Output appears grounded and relevant, while reference overlap is low enough to suggest paraphrase or lexical mismatch."
    elif output_tokens < 35 or generic_ratio >= 0.35:
        bucket = "generic_or_under_specific"
        rationale = "Output is short or generic enough that lexical uncertainty is likely an under-specific answer risk."
    elif (source_overlap or 0.0) >= 0.10 and labels.get("source_reference_mismatch_possible"):
        bucket = "source_reference_mismatch_possible"
        rationale = "Output has some source grounding but does not align lexically with the reference; deterministic evidence cannot decide fault."
    else:
        bucket = "unresolved_proxy_limitation"
        rationale = "Deterministic signals are mixed and insufficient for a stronger bucket without human or LLM judging."

    return {
        "fixture_id": fixture_id,
        "question_preview": question[:260],
        "reference_preview": reference[:360],
        "generated_preview": generated[:500],
        "generated_tail": generated[-260:],
        "t102b_labels": labels,
        "overlap_metrics": {
            "reference_unigram_recall": ref_recall,
            "reference_bigram_recall": _metric(label_row, "reference_bigram_recall"),
            "output_source_keyword_overlap": source_overlap,
            "output_question_keyword_overlap": question_overlap,
            "direct_reference_overlap": direct_reference_overlap,
        },
        "primary_bucket": bucket,
        "secondary_flags": sorted(set(secondary)),
        "rationale_short": rationale,
        "runtime": {
            "t_compress_ms": _metric(label_row, "t_compress_ms"),
            "e2e_time_s": _metric(label_row, "e2e_time_s"),
            "tokens_per_second": _metric(label_row, "tokens_per_second"),
            "tau_mean": _metric(label_row, "tau_mean"),
            "output_token_count": output_tokens,
        },
    }


def _generic_ratio(text: str) -> float:
    toks = _tokens(text)
    if not toks:
        return 1.0
    return sum(1 for tok in toks if tok in GENERIC_TERMS) / len(toks)


def _reference_text(qmsum_row: dict[str, Any], previews: dict[str, Any]) -> str:
    for key in ("expected_answer", "reference_answer", "target_answer"):
        if key in qmsum_row:
            value = qmsum_row.get(key)
            return value.strip() if isinstance(value, str) else ""
    value = previews.get("expected_answer")
    return value.strip() if isinstance(value, str) else ""


def _index_by_fixture(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("fixture_id") or row.get("dataset_id") or "")
        if key:
            out[key] = row
    return out


def build_summary(total_rows: int, triaged_rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(row["primary_bucket"] for row in triaged_rows)
    hard_risk = counts["evidence_miss_likely"] + counts["generic_or_under_specific"]
    unresolved = counts["unresolved_proxy_limitation"]
    proxy_reference = (
        counts["proxy_false_negative"]
        + counts["source_reference_mismatch_possible"]
        + counts["acceptable_after_proxy_review"]
    )
    analyzed = len(triaged_rows)
    return {
        "task": "T102C",
        "total_rows": total_rows,
        "uncertain_rows_analyzed": analyzed,
        "bucket_counts": {bucket: counts.get(bucket, 0) for bucket in BUCKETS},
        "proxy_reference_limitation_rows": proxy_reference,
        "likely_model_or_evidence_failure_rows": counts["evidence_miss_likely"],
        "generic_or_under_specific_rows": counts["generic_or_under_specific"],
        "acceptable_after_proxy_review_count": counts["acceptable_after_proxy_review"],
        "hard_risk_rows": hard_risk,
        "unresolved_rows": unresolved,
        "uncertainty_explained_percent": {
            "proxy_reference_limitation": _percent(proxy_reference, analyzed),
            "likely_model_or_evidence_failure": _percent(counts["evidence_miss_likely"], analyzed),
            "generic_or_under_specific": _percent(counts["generic_or_under_specific"], analyzed),
            "unresolved_deterministic_limitation": _percent(unresolved, analyzed),
        },
    }


def _percent(count: int, total: int) -> float:
    return round(count / total, 6) if total else 0.0


def build_claim_update(summary: dict[str, Any]) -> dict[str, Any]:
    counts = summary.get("bucket_counts", {})
    proxy_reference = (
        counts.get("proxy_false_negative", 0)
        + counts.get("source_reference_mismatch_possible", 0)
        + counts.get("acceptable_after_proxy_review", 0)
    )
    hard = summary.get("hard_risk_rows", 0)
    unresolved = summary.get("unresolved_rows", 0)
    analyzed = summary.get("uncertain_rows_analyzed", 0) or 1
    if unresolved > analyzed * 0.50:
        status = "SCOPED_WITH_PROXY_LIMITATION"
    elif hard >= proxy_reference:
        status = "SCOPED_WITH_QUALITY_RISK"
    else:
        status = "SCOPED_WITH_TRIAGED_RISK"
    return {
        "QMSum claim": {
            "status": status,
            "allowed_wording": [
                "QMSum Light GPU completed n30 without runtime, cap, or malformed-output failures; remaining uncertainty was triaged into proxy/reference limitations, possible evidence misses, and unresolved deterministic-proxy limits.",
                "QMSum evidence supports benchmark-scoped semantic-risk/proxy coverage, not semantic correctness proof.",
            ],
            "blocked_wording": [
                "QMSum semantic correctness is proven.",
                "QMSum quality is fully solved.",
                "Final semantic correctness is proven.",
            ],
        },
        "reason": {
            "proxy_reference_limitation_rows": proxy_reference,
            "hard_risk_rows": hard,
            "unresolved_rows": unresolved,
            "uncertain_rows_analyzed": analyzed,
        },
    }


def build_next_task_decision(summary: dict[str, Any]) -> dict[str, Any]:
    total = summary.get("total_rows", 0) or 1
    analyzed = summary.get("uncertain_rows_analyzed", 0) or 1
    severe = (
        (total >= 10 and summary.get("hard_risk_rows", 0) > total * 0.50)
        or summary.get("unresolved_rows", 0) > analyzed * 0.50
        or analyzed == 0
    )
    if severe:
        return {
            "next_task": "T102A — QMSum Failure Audit / Fix",
            "reason": "T102C found too many hard-risk or unresolved rows to support QMSum claim closure.",
            "automatic_benchmark": False,
        }
    return {
        "next_task": "T103 — Reference Alignment for Speed Claim",
        "reason": "QMSum uncertainty has been triaged enough to proceed to reference alignment.",
        "automatic_benchmark": False,
    }


def _write_triage_table(path: Path, triaged_rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "fixture_id",
                "primary_bucket",
                "secondary_flags",
                "reference_unigram_recall",
                "output_source_keyword_overlap",
                "output_token_count",
                "rationale_short",
            ],
        )
        writer.writeheader()
        for row in triaged_rows:
            writer.writerow(
                {
                    "fixture_id": row["fixture_id"],
                    "primary_bucket": row["primary_bucket"],
                    "secondary_flags": ";".join(row["secondary_flags"]),
                    "reference_unigram_recall": row["overlap_metrics"].get("reference_unigram_recall"),
                    "output_source_keyword_overlap": row["overlap_metrics"].get("output_source_keyword_overlap"),
                    "output_token_count": row["runtime"].get("output_token_count"),
                    "rationale_short": row["rationale_short"],
                }
            )


def analyze(
    *,
    qmsum_jsonl: Path = DEFAULT_QMSUM_JSONL,
    row_labels: Path = DEFAULT_ROW_LABELS,
    low_proxy_rows: Path = DEFAULT_LOW_PROXY_ROWS,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    qmsum_rows = read_jsonl(qmsum_jsonl)
    label_rows = read_jsonl(row_labels)
    low_rows = read_jsonl(low_proxy_rows)
    qmsum_by_id = _index_by_fixture(qmsum_rows)
    low_ids = {str(row.get("fixture_id") or row.get("dataset_id") or "") for row in low_rows}
    uncertain_label_rows = [row for row in label_rows if _is_uncertain(row, low_ids)]
    triaged_rows = [
        triage_row(qmsum_by_id.get(str(row.get("fixture_id") or row.get("dataset_id") or ""), {}), row)
        for row in uncertain_label_rows
    ]
    summary = build_summary(len(qmsum_rows), triaged_rows)
    claim_update = build_claim_update(summary)
    next_task = build_next_task_decision(summary)
    decision = "PASS_WITH_CAVEAT" if next_task["next_task"].startswith("T103") else "PARTIAL"
    result = {
        "decision": decision,
        "summary": summary,
        "claim_update": claim_update,
        "next_task_decision": next_task,
        "inputs": {
            "qmsum_jsonl": str(qmsum_jsonl),
            "row_labels": str(row_labels),
            "low_proxy_rows": str(low_proxy_rows),
        },
    }
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[0], result)
    write_jsonl(output_dir / OUTPUT_RELATIVE_PATHS[1], triaged_rows)
    _write_triage_table(output_dir / OUTPUT_RELATIVE_PATHS[2], triaged_rows)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[3], claim_update)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[4], next_task)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Triage Task102B QMSum proxy-uncertain rows.")
    parser.add_argument("--qmsum-jsonl", type=Path, default=DEFAULT_QMSUM_JSONL)
    parser.add_argument("--row-labels", type=Path, default=DEFAULT_ROW_LABELS)
    parser.add_argument("--low-proxy-rows", type=Path, default=DEFAULT_LOW_PROXY_ROWS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = analyze(
        qmsum_jsonl=args.qmsum_jsonl,
        row_labels=args.row_labels,
        low_proxy_rows=args.low_proxy_rows,
        output_dir=args.output_dir,
    )
    print(json.dumps({"decision": result["decision"], "output_dir": str(args.output_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
