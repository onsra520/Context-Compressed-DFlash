from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_task70_qmsum_diagnostic_audit import (
    _hit_cap,
    _tokens,
    has_repetition,
    load_jsonl,
    normalized_token_overlap,
)
from scripts.analyze_task72_qmsum_cap_hit_proxy_triage import ends_naturally

BEFORE_ARTIFACTS = {
    "LLMLingua-AR-R2": Path("results/task71_qmsum_long_llmlingua_ar_r2_n30_mnt384.jsonl"),
    "CC-DFlash-R2": Path("results/task71_qmsum_long_cc_dflash_r2_n30_mnt384.jsonl"),
}
AFTER_ARTIFACTS = {
    "LLMLingua-AR-R2": Path("results/task73_qmsum_long_llmlingua_ar_r2_n30_mnt384_concise.jsonl"),
    "CC-DFlash-R2": Path("results/task73_qmsum_long_cc_dflash_r2_n30_mnt384_concise.jsonl"),
}
DEFAULT_SUMMARY_OUTPUT = Path("results/task74_qmsum_proxy_case_summary.json")
DEFAULT_TABLE_OUTPUT = Path("results/task74_qmsum_proxy_case_table.csv")
DEFAULT_SAMPLES_OUTPUT = Path("results/task74_qmsum_proxy_case_samples.jsonl")

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
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
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "she",
    "so",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "to",
    "was",
    "were",
    "which",
    "with",
    "would",
}
ENTITY_RE = re.compile(r"\b(?:[A-Z][a-z]+|[A-Z]{2,}|\d+(?:[.,]\d+)*)\b")


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def _compact(text: Any, limit: int = 360) -> str:
    if not isinstance(text, str):
        return ""
    clean = " ".join(text.split())
    return clean[:limit] + ("..." if len(clean) > limit else "")


def _bigrams(tokens: list[str]) -> set[tuple[str, str]]:
    return set(zip(tokens, tokens[1:], strict=False))


def bigram_overlap(reference: Any, generated: Any) -> float:
    reference_bigrams = _bigrams(_tokens(reference))
    generated_bigrams = _bigrams(_tokens(generated))
    if not reference_bigrams:
        return 0.0
    return len(reference_bigrams & generated_bigrams) / len(reference_bigrams)


def _keywords(text: Any) -> set[str]:
    return {token for token in _tokens(text) if len(token) > 2 and token not in STOPWORDS}


def _entities(text: Any) -> set[str]:
    if not isinstance(text, str):
        return set()
    return {match.group(0).lower() for match in ENTITY_RE.finditer(text)}


def _coverage(reference_items: set[str], generated_items: set[str]) -> float:
    if not reference_items:
        return 0.0
    return len(reference_items & generated_items) / len(reference_items)


def lexical_diagnostics(reference: Any, generated: Any) -> dict[str, float]:
    reference_tokens = _tokens(reference)
    generated_tokens = _tokens(generated)
    reference_keywords = _keywords(reference)
    generated_keywords = _keywords(generated)
    reference_entities = _entities(reference)
    generated_entities = _entities(generated)
    length_ratio = len(generated_tokens) / len(reference_tokens) if reference_tokens else 0.0
    return {
        "unigram_overlap": round(normalized_token_overlap(reference, generated), 6),
        "bigram_overlap": round(bigram_overlap(reference, generated), 6),
        "reference_answer_coverage": round(_coverage(set(reference_tokens), set(generated_tokens)), 6)
        if reference_tokens
        else 0.0,
        "generated_to_reference_length_ratio": round(length_ratio, 6),
        "numeric_entity_overlap": round(_coverage(reference_entities, generated_entities), 6),
        "keyword_overlap": round(_coverage(reference_keywords, generated_keywords), 6),
    }


def _contains_reference(reference: Any, generated: Any) -> bool:
    ref = " ".join(_tokens(reference))
    gen = " ".join(_tokens(generated))
    return bool(ref and gen and ref in gen)


def _looks_direct(row: dict[str, Any]) -> bool:
    text = str(row.get("generated_text") or "").strip()
    if not text:
        return False
    tokens = _tokens(text)
    if len(tokens) > 120:
        return False
    if has_repetition(text):
        return False
    return ends_naturally(text)


def label_case(before_row: dict[str, Any], after_row: dict[str, Any]) -> dict[str, Any]:
    before_generated = before_row.get("generated_text")
    after_generated = after_row.get("generated_text")
    expected = after_row.get("expected_answer") or before_row.get("expected_answer")
    before_diag = lexical_diagnostics(expected, before_generated)
    after_diag = lexical_diagnostics(expected, after_generated)
    before_cap = _hit_cap(before_row)
    after_cap = _hit_cap(after_row)
    direct = _looks_direct(after_row)
    after_overlap = after_diag["unigram_overlap"]
    after_keyword = after_diag["keyword_overlap"]
    after_bigram = after_diag["bigram_overlap"]
    length_ratio = after_diag["generated_to_reference_length_ratio"]
    overlap_delta = after_diag["unigram_overlap"] - before_diag["unigram_overlap"]

    if before_cap and not after_cap and direct and after_keyword >= 0.45 and after_overlap >= 0.30:
        label = "TRUNCATION_FIXED"
    elif direct and after_keyword >= 0.55 and after_overlap >= 0.30:
        label = "ACCEPTABLE_CONCISE_ANSWER"
    elif direct and overlap_delta < -0.05 and after_keyword >= 0.45 and after_overlap >= 0.20:
        label = "PROXY_MISMATCH_CONCISE_ANSWER"
    elif direct and (after_overlap < 0.15 or after_keyword < 0.35 or length_ratio < 0.12):
        label = "ANSWER_TOO_SHORT_OR_UNSUPPORTED"
    elif overlap_delta <= -0.10 and after_overlap < 0.30:
        label = "TRUE_QUALITY_DEGRADATION_POSSIBLE"
    elif before_cap and not after_cap:
        label = "TRUNCATION_FIXED"
    else:
        label = "UNCLEAR"

    return {
        "label": label,
        "before_hit_cap": before_cap,
        "after_hit_cap": after_cap,
        "before_cut_mid_sentence": before_cap and not ends_naturally(before_generated),
        "after_concise_complete": direct,
        "after_answers_directly": direct and after_keyword >= 0.35,
        "before_diagnostics": before_diag,
        "after_diagnostics": after_diag,
        "overlap_delta": round(overlap_delta, 6),
        "containment_before": _contains_reference(expected, before_generated),
        "containment_after": _contains_reference(expected, after_generated),
        "generated_text_length_before": len(str(before_generated or "")),
        "generated_text_length_after": len(str(after_generated or "")),
    }


def _by_prompt(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        value = row.get("benchmark_prompt_index", row.get("prompt_id"))
        if isinstance(value, int) and not isinstance(value, bool):
            result[value] = row
    return result


def _e2e(row: dict[str, Any]) -> float:
    generation = row.get("generation_time_s")
    compress = row.get("t_compress_ms")
    generation_s = float(generation) if isinstance(generation, (int, float)) and not isinstance(generation, bool) else 0.0
    compress_s = float(compress) / 1000.0 if isinstance(compress, (int, float)) and not isinstance(compress, bool) else 0.0
    return generation_s + compress_s


def _condition_summary(condition: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    labels = Counter(case["label"] for case in cases)
    before_caps = sum(1 for case in cases if case["before_hit_cap"])
    after_caps = sum(1 for case in cases if case["after_hit_cap"])
    before_overlaps = [case["before_diagnostics"]["unigram_overlap"] for case in cases]
    after_overlaps = [case["after_diagnostics"]["unigram_overlap"] for case in cases]
    before_outputs = [float(case["before_output_tokens"]) for case in cases if isinstance(case.get("before_output_tokens"), (int, float))]
    after_outputs = [float(case["after_output_tokens"]) for case in cases if isinstance(case.get("after_output_tokens"), (int, float))]
    before_e2e = [float(case["before_e2e_latency_s"]) for case in cases]
    after_e2e = [float(case["after_e2e_latency_s"]) for case in cases]
    after_policy = sum(1 for case in cases if case.get("qmsum_concise_policy_preserved") is True)
    return {
        "condition": condition,
        "rows": len(cases),
        "before_cap_hits": before_caps,
        "after_cap_hits": after_caps,
        "avg_before_output_tokens": round(_mean(before_outputs), 6),
        "avg_after_output_tokens": round(_mean(after_outputs), 6),
        "avg_before_overlap": round(_mean(before_overlaps), 6),
        "avg_after_overlap": round(_mean(after_overlaps), 6),
        "median_before_overlap": round(_median(before_overlaps), 6),
        "median_after_overlap": round(_median(after_overlaps), 6),
        "avg_before_e2e_latency_s": round(_mean(before_e2e), 6),
        "avg_after_e2e_latency_s": round(_mean(after_e2e), 6),
        "qmsum_concise_policy_preserved_count": after_policy,
        "qmsum_concise_policy_preservation_rate": round(after_policy / len(cases), 6) if cases else 0.0,
        "label_counts": dict(sorted(labels.items())),
    }


def _sample_case(condition: str, prompt_id: int, before_row: dict[str, Any], after_row: dict[str, Any]) -> dict[str, Any]:
    labeled = label_case(before_row, after_row)
    return {
        "condition": condition,
        "prompt_id": prompt_id,
        "fixture_id": after_row.get("fixture_id") or before_row.get("fixture_id"),
        "label": labeled["label"],
        "expected_answer": _compact(after_row.get("expected_answer") or before_row.get("expected_answer"), 300),
        "before_generated_snippet": _compact(before_row.get("generated_text"), 420),
        "after_generated_snippet": _compact(after_row.get("generated_text"), 420),
        "before_output_tokens": before_row.get("output_tokens"),
        "after_output_tokens": after_row.get("output_tokens"),
        "before_e2e_latency_s": round(_e2e(before_row), 6),
        "after_e2e_latency_s": round(_e2e(after_row), 6),
        "qmsum_concise_policy_preserved": after_row.get("qmsum_concise_policy_preserved"),
        **labeled,
    }


def _decision(by_condition: dict[str, dict[str, Any]]) -> dict[str, Any]:
    labels = Counter()
    for summary in by_condition.values():
        labels.update(summary["label_counts"])
    acceptable = (
        labels["PROXY_MISMATCH_CONCISE_ANSWER"]
        + labels["ACCEPTABLE_CONCISE_ANSWER"]
        + labels["TRUNCATION_FIXED"]
    )
    concerning = labels["TRUE_QUALITY_DEGRADATION_POSSIBLE"] + labels["ANSWER_TOO_SHORT_OR_UNSUPPORTED"]
    total = sum(labels.values())
    concise_keep = total > 0 and acceptable > concerning and labels["ANSWER_TOO_SHORT_OR_UNSUPPORTED"] < total * 0.30
    revise = not concise_keep or concerning >= acceptable * 0.5
    return {
        "label_counts": dict(sorted(labels.items())),
        "overlap_drop_likely_metric_mismatch": bool(concise_keep and not revise),
        "overlap_drop_likely_true_quality_loss": bool(revise),
        "concise_policy_recommendation": "revise_balanced_policy" if revise else "keep_with_proxy_caveat",
        "mnt512_still_needed": False,
        "qmsum_n100_justified": False,
        "qmsum_n100_reason": "Blocked until QMSum prompt/proxy policy is resolved; no immediate n=100.",
        "total_cases": total,
        "acceptable_or_proxy_cases": acceptable,
        "concerning_cases": concerning,
    }


def analyze_case_pairs(
    before_rows_by_condition: dict[str, list[dict[str, Any]]],
    after_rows_by_condition: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    samples: list[dict[str, Any]] = []
    by_condition: dict[str, dict[str, Any]] = {}
    table: list[dict[str, Any]] = []
    for condition in sorted(set(before_rows_by_condition) & set(after_rows_by_condition)):
        before_by_id = _by_prompt(before_rows_by_condition[condition])
        after_by_id = _by_prompt(after_rows_by_condition[condition])
        condition_cases = [
            _sample_case(condition, prompt_id, before_by_id[prompt_id], after_by_id[prompt_id])
            for prompt_id in sorted(set(before_by_id) & set(after_by_id))
        ]
        samples.extend(condition_cases)
        summary = _condition_summary(condition, condition_cases)
        by_condition[condition] = summary
        table.append(summary)

    summary = {
        "task": "74-qmsum-proxy-case-triage",
        "status": "PASS_WITH_NOTES",
        "by_condition": by_condition,
        "decisions": _decision(by_condition),
        "claim_policy": "read-only preliminary proxy triage; no final speedup/correctness/deployment claim",
    }
    return summary, table, samples


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = [
        "condition",
        "rows",
        "before_cap_hits",
        "after_cap_hits",
        "avg_before_output_tokens",
        "avg_after_output_tokens",
        "avg_before_overlap",
        "avg_after_overlap",
        "avg_before_e2e_latency_s",
        "avg_after_e2e_latency_s",
        "qmsum_concise_policy_preservation_rate",
        "label_counts",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 74 QMSum concise-policy proxy cases")
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--table-output", type=Path, default=DEFAULT_TABLE_OUTPUT)
    parser.add_argument("--samples-output", type=Path, default=DEFAULT_SAMPLES_OUTPUT)
    args = parser.parse_args()

    before = {condition: load_jsonl(path) for condition, path in BEFORE_ARTIFACTS.items()}
    after = {condition: load_jsonl(path) for condition, path in AFTER_ARTIFACTS.items()}
    summary, table, samples = analyze_case_pairs(before, after)
    _write_json(args.summary_output, summary)
    _write_csv(args.table_output, table)
    _write_jsonl(args.samples_output, samples)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "recommendation": summary["decisions"]["concise_policy_recommendation"],
                "mnt512_still_needed": summary["decisions"]["mnt512_still_needed"],
                "qmsum_n100_justified": summary["decisions"]["qmsum_n100_justified"],
                "summary_output": str(args.summary_output),
                "table_output": str(args.table_output),
                "samples_output": str(args.samples_output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
