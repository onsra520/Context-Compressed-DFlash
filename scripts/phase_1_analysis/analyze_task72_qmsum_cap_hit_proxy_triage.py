from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_analysis.analyze_task70_qmsum_diagnostic_audit import (
    _condition_summary,
    _hit_cap,
    _tokens,
    has_repetition,
    load_jsonl,
    normalized_token_overlap,
)


DEFAULT_ARTIFACTS = {
    "Baseline-AR": Path("results/task71_qmsum_long_baseline_ar_n30_mnt384.jsonl"),
    "DFlash-R1": Path("results/task71_qmsum_long_dflash_r1_n30_mnt384.jsonl"),
    "LLMLingua-AR-R2": Path("results/task71_qmsum_long_llmlingua_ar_r2_n30_mnt384.jsonl"),
    "CC-DFlash-R2": Path("results/task71_qmsum_long_cc_dflash_r2_n30_mnt384.jsonl"),
}
DEFAULT_SUMMARY_OUTPUT = Path("results/task72_qmsum_cap_hit_proxy_summary.json")
DEFAULT_CASES_OUTPUT = Path("results/task72_qmsum_cap_hit_proxy_cases.jsonl")
DEFAULT_TABLE_OUTPUT = Path("results/task72_qmsum_cap_hit_proxy_table.csv")
INCOMPLETE_TAIL_WORDS = {
    "and",
    "or",
    "because",
    "with",
    "for",
    "to",
    "of",
    "the",
    "a",
    "an",
    "as",
    "by",
    "that",
    "which",
    "while",
    "but",
    "so",
    "create",
    "develop",
    "include",
    "support",
    "there",
    "is",
}


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def _compact(text: Any, limit: int = 360) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def ends_naturally(text: Any) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    stripped = text.strip()
    tokens = _tokens(stripped)
    if not tokens:
        return False
    if tokens[-1] in INCOMPLETE_TAIL_WORDS:
        return False
    return stripped[-1] in ".!?)\"]'"


def _row_overlap(row: dict[str, Any]) -> float:
    return normalized_token_overlap(row.get("expected_answer"), row.get("generated_text"))


def _row_by_prompt(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        prompt_id = row.get("prompt_id")
        if isinstance(prompt_id, int):
            out[prompt_id] = row
    return out


def label_cap_hit_case(row: dict[str, Any], uncompressed_rows: list[dict[str, Any]]) -> str:
    overlap = _row_overlap(row)
    uncompressed_overlap = max((_row_overlap(item) for item in uncompressed_rows), default=0.0)
    natural_end = ends_naturally(row.get("generated_text"))
    repetition = has_repetition(row.get("generated_text"))

    if uncompressed_overlap >= 0.35 and overlap <= uncompressed_overlap - 0.20:
        return "COMPRESSION_LOSS_POSSIBLE"
    if overlap >= 0.35 and natural_end and not repetition:
        return "ACCEPTABLE_DESPITE_CAP"
    if not natural_end and overlap >= 0.20:
        return "TRUNCATION_LIKELY"
    if not natural_end:
        return "LONG_ANSWER_CAP_PRESSURE"
    if overlap < 0.20:
        return "PROXY_WEAKNESS"
    return "UNCLEAR"


def _compressed_cap_cases(
    condition: str,
    rows: list[dict[str, Any]],
    baseline_by_prompt: dict[int, dict[str, Any]],
    dflash_by_prompt: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cap_rows = [row for row in rows if _hit_cap(row)]
    non_cap_rows = [row for row in rows if not _hit_cap(row)]
    cases: list[dict[str, Any]] = []
    labels: Counter[str] = Counter()
    cap_overlaps: list[float] = []
    non_cap_overlaps: list[float] = []
    cut_mid_sentence = 0
    natural_end = 0

    for row in cap_rows:
        prompt_id = row.get("prompt_id")
        peers = []
        if isinstance(prompt_id, int):
            peers = [
                item
                for item in [baseline_by_prompt.get(prompt_id), dflash_by_prompt.get(prompt_id)]
                if item is not None
            ]
        label = label_cap_hit_case(row, peers)
        labels[label] += 1
        overlap = _row_overlap(row)
        cap_overlaps.append(overlap)
        if ends_naturally(row.get("generated_text")):
            natural_end += 1
        else:
            cut_mid_sentence += 1
        peer_overlaps = {peer.get("condition", "unknown"): round(_row_overlap(peer), 6) for peer in peers}
        cases.append(
            {
                "condition": condition,
                "prompt_id": prompt_id,
                "fixture_id": row.get("fixture_id"),
                "label": label,
                "overlap": round(overlap, 6),
                "uncompressed_peer_overlaps": peer_overlaps,
                "output_tokens": row.get("output_tokens"),
                "max_new_tokens": row.get("max_new_tokens"),
                "ends_naturally": ends_naturally(row.get("generated_text")),
                "expected_answer": _compact(row.get("expected_answer"), 260),
                "generated_tail": _compact((row.get("generated_text") or "")[-420:], 420),
                "generated_text_snippet": _compact(row.get("generated_text"), 420),
            }
        )

    for row in non_cap_rows:
        non_cap_overlaps.append(_row_overlap(row))

    output_tokens = [
        float(row["output_tokens"])
        for row in rows
        if isinstance(row.get("output_tokens"), (int, float)) and not isinstance(row.get("output_tokens"), bool)
    ]
    summary = {
        "condition": condition,
        "rows": len(rows),
        "cap_hit_count": len(cap_rows),
        "cap_hit_prompt_ids": [row.get("prompt_id") for row in cap_rows],
        "non_cap_count": len(non_cap_rows),
        "cap_hit_avg_overlap": round(_mean(cap_overlaps), 6),
        "non_cap_avg_overlap": round(_mean(non_cap_overlaps), 6),
        "cap_hit_median_overlap": round(_median(cap_overlaps), 6),
        "non_cap_median_overlap": round(_median(non_cap_overlaps), 6),
        "cut_mid_sentence_count": cut_mid_sentence,
        "natural_end_count": natural_end,
        "label_counts": dict(sorted(labels.items())),
        "output_tokens_min": min(output_tokens, default=0.0),
        "output_tokens_median": _median(output_tokens),
        "output_tokens_avg": _mean(output_tokens),
        "output_tokens_max": max(output_tokens, default=0.0),
    }
    return summary, cases


def _cap_hit_overlap(llm_rows: list[dict[str, Any]], cc_rows: list[dict[str, Any]]) -> dict[str, Any]:
    llm_ids = {row.get("prompt_id") for row in llm_rows if _hit_cap(row)}
    cc_ids = {row.get("prompt_id") for row in cc_rows if _hit_cap(row)}
    return {
        "llmlingua_cap_hit_count": len(llm_ids),
        "cc_dflash_cap_hit_count": len(cc_ids),
        "shared_count": len(llm_ids & cc_ids),
        "shared_prompt_ids": sorted(llm_ids & cc_ids),
        "llmlingua_only_prompt_ids": sorted(llm_ids - cc_ids),
        "cc_dflash_only_prompt_ids": sorted(cc_ids - llm_ids),
    }


def _decisions(compressed_triage: dict[str, dict[str, Any]]) -> dict[str, Any]:
    total_cap = sum(item["cap_hit_count"] for item in compressed_triage.values())
    label_counts: Counter[str] = Counter()
    cut_mid = 0
    natural = 0
    for item in compressed_triage.values():
        label_counts.update(item["label_counts"])
        cut_mid += int(item["cut_mid_sentence_count"])
        natural += int(item["natural_end_count"])
    truncation_like = label_counts["TRUNCATION_LIKELY"] + label_counts["LONG_ANSWER_CAP_PRESSURE"]
    acceptable_or_proxy = label_counts["ACCEPTABLE_DESPITE_CAP"] + label_counts["PROXY_WEAKNESS"]
    mnt512 = total_cap > 0 and truncation_like / total_cap >= 0.60
    prompt_refine = total_cap > 0 and (truncation_like + acceptable_or_proxy) / total_cap >= 0.50
    return {
        "mnt512_compressed_only_justified": mnt512,
        "mnt512_reason": (
            "Many compressed cap-hit rows appear unfinished or under long-answer cap pressure; if tested, use compressed-only n=30 first."
            if mnt512
            else "Do not increase to mnt512 before understanding prompt/proxy behavior."
        ),
        "prompt_refinement_recommended": prompt_refine,
        "prompt_refinement_reason": (
            "Compressed QMSum outputs are often verbose/cap-limited; refine answer style before n=100."
            if prompt_refine
            else "Prompt refinement is not the dominant next action from the current labels."
        ),
        "qmsum_n100_justified": False,
        "qmsum_n100_reason": "Blocked until cap-hit/proxy behavior is resolved or n=100 is explicitly scoped as speed-only.",
        "final_report_synthesis_ready": not mnt512 and not prompt_refine,
        "cut_mid_sentence_count": cut_mid,
        "natural_end_count": natural,
        "label_counts": dict(sorted(label_counts.items())),
    }


def analyze_rows(rows_by_condition: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    by_condition: dict[str, dict[str, Any]] = {}
    for condition in ("Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-DFlash-R2"):
        by_condition[condition], _ = _condition_summary(condition, rows_by_condition[condition])
    baseline_by_prompt = _row_by_prompt(rows_by_condition["Baseline-AR"])
    dflash_by_prompt = _row_by_prompt(rows_by_condition["DFlash-R1"])
    llm_triage, llm_cases = _compressed_cap_cases(
        "LLMLingua-AR-R2",
        rows_by_condition["LLMLingua-AR-R2"],
        baseline_by_prompt,
        dflash_by_prompt,
    )
    cc_triage, cc_cases = _compressed_cap_cases(
        "CC-DFlash-R2",
        rows_by_condition["CC-DFlash-R2"],
        baseline_by_prompt,
        dflash_by_prompt,
    )
    compressed_triage = {
        "LLMLingua-AR-R2": llm_triage,
        "CC-DFlash-R2": cc_triage,
    }
    cases = llm_cases + cc_cases
    table = [by_condition[condition] for condition in ("Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-DFlash-R2")]
    summary = {
        "task": "Task 72 QMSum compressed cap-hit and proxy triage",
        "status": "PASS_WITH_NOTES",
        "by_condition": by_condition,
        "cap_hit_overlap": _cap_hit_overlap(rows_by_condition["LLMLingua-AR-R2"], rows_by_condition["CC-DFlash-R2"]),
        "compressed_cap_hit_triage": compressed_triage,
        "decisions": _decisions(compressed_triage),
        "gsm8k_analogy": {
            "resembles_gsm8k_failure": False,
            "reason": "QMSum failures are long-answer cap/proxy issues, not numeric arithmetic failures.",
        },
        "claim_policy": "Read-only triage; preliminary proxy diagnostics only.",
    }
    return summary, table, cases


def _load_default_rows() -> dict[str, list[dict[str, Any]]]:
    rows_by_condition: dict[str, list[dict[str, Any]]] = {}
    for condition, path in DEFAULT_ARTIFACTS.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing Task 71 artifact for {condition}: {path}")
        rows_by_condition[condition] = load_jsonl(path)
    return rows_by_condition


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "condition",
        "rows",
        "hit_cap_count",
        "avg_answer_token_overlap",
        "normalized_containment_count",
        "empty_output_count",
        "repetition_count",
        "avg_output_tokens",
        "avg_e2e_latency_s",
        "e2e_tok_per_sec_weighted",
        "avg_t_compress_ms",
        "avg_original_input_tokens",
        "avg_compressed_input_tokens",
        "avg_compression_ratio",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Triage Task 71 QMSum compressed cap-hit/proxy behavior.")
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--cases-output", type=Path, default=DEFAULT_CASES_OUTPUT)
    parser.add_argument("--table-output", type=Path, default=DEFAULT_TABLE_OUTPUT)
    args = parser.parse_args(argv)

    summary, table, cases = analyze_rows(_load_default_rows())
    _write_json(args.summary_output, summary)
    _write_jsonl(args.cases_output, cases)
    _write_csv(args.table_output, table)
    print(json.dumps(
        {
            "status": summary["status"],
            "mnt512_compressed_only_justified": summary["decisions"]["mnt512_compressed_only_justified"],
            "prompt_refinement_recommended": summary["decisions"]["prompt_refinement_recommended"],
            "qmsum_n100_justified": summary["decisions"]["qmsum_n100_justified"],
            "summary_output": str(args.summary_output),
            "cases_output": str(args.cases_output),
            "table_output": str(args.table_output),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
