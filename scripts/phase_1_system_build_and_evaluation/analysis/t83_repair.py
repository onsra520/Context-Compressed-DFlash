from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_system_build_and_evaluation.analysis.t47_quality_refinement import classify_row
from scripts.phase_1_system_build_and_evaluation.analysis.t70_qmsum_diagnostic_audit import normalized_token_overlap


GSM8K_FILE = Path("results/task83_gsm8k_dflash_r1_repair_n30.jsonl")
QMSUM_FILES = {
    "Baseline-AR": Path("results/task83_qmsum_baseline_ar_n30.jsonl"),
    "DFlash-R1": Path("results/task83_qmsum_dflash_r1_n30.jsonl"),
    "LLMLingua-AR-R2": Path("results/task83_qmsum_llmlingua_ar_r2_n30.jsonl"),
    "CC-DFlash-R2": Path("results/task83_qmsum_cc_dflash_r2_n30.jsonl"),
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _number(row: dict[str, Any], *field_names: str) -> float | None:
    for field_name in field_names:
        value = row.get(field_name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _numbers(rows: list[dict[str, Any]], *field_names: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = _number(row, *field_names)
        if value is not None:
            values.append(value)
    return values


def _hit_cap(row: dict[str, Any]) -> bool:
    output_tokens = _number(row, "output_tokens")
    max_new_tokens = _number(row, "max_new_tokens")
    if max_new_tokens is None:
        max_new_tokens = 384
    return output_tokens is not None and output_tokens >= max_new_tokens


def _e2e_times(rows: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for row in rows:
        generation_s = _number(row, "generation_time_s")
        if generation_s is None:
            continue
        t_compress_ms = _number(row, "t_compress_ms") or 0.0
        values.append(generation_s + t_compress_ms / 1000.0)
    return values


def _weighted_tok_s(rows: list[dict[str, Any]], *, include_compression: bool) -> float:
    output_tokens = sum(_numbers(rows, "output_tokens"))
    generation_time = sum(_numbers(rows, "generation_time_s"))
    compression_time = sum(_numbers(rows, "t_compress_ms")) / 1000.0 if include_compression else 0.0
    denom = generation_time + compression_time
    return output_tokens / denom if denom else 0.0


def is_repetition(text: str) -> bool:
    if not text:
        return False
    # Simple heuristic for repetition: same word repeated many times
    words = text.split()
    if len(words) < 20:
        return False
    unique_ratio = len(set(words)) / len(words)
    return unique_ratio < 0.2


def analyze_gsm8k() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = load_jsonl(GSM8K_FILE)
    status = "stable" if len(rows) == 30 else "runtime_watch"
    
    classifications = [
        classify_row(row, row_index=index, condition="DFlash-R1", artifact="DFlash-R1.jsonl")
        for index, row in enumerate(rows, start=1)
    ]
    numeric_match_count = sum(1 for item in classifications if item.get("numeric_match"))
    
    e2e_times = _e2e_times(rows)
    output_tokens = _numbers(rows, "output_tokens")
    
    # Check timing anomaly by looking at avg_e2e. If > 12s roughly, anomaly is there.
    # We will let the user's instructions define the status string based on the data.
    # The prompt: "If DFlash-R1 timing returns to the expected pattern, mark it as stable. If timing is still abnormal, mark it as runtime_watch."
    avg_e2e = round(_mean(e2e_times), 6)
    status = "stable" if len(rows) == 30 and avg_e2e < 12.0 else "runtime_watch"
    
    summary = {
        "dataset": "gsm8k_short",
        "condition": "DFlash-R1",
        "status": status,
        "row_count": len(rows),
        "numeric_match_count": numeric_match_count,
        "numeric_match_rate": round(numeric_match_count / len(rows), 6) if rows else 0.0,
        "avg_output_tokens": round(_mean(output_tokens), 6),
        "avg_generation_latency_s": round(_mean(_numbers(rows, "generation_time_s")), 6),
        "avg_e2e_latency_s": avg_e2e,
        "generation_tok_per_sec_weighted": round(_weighted_tok_s(rows, include_compression=False), 6),
        "e2e_tok_per_sec_weighted": round(_weighted_tok_s(rows, include_compression=True), 6),
        "hit_cap_count": sum(1 for row in rows if _hit_cap(row)),
    }
    return summary, [summary]


def analyze_qmsum() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summaries = []
    summary_out = {
        "status": "stable",
        "caveat": "",
        "conditions": {}
    }
    
    for condition, path in QMSUM_FILES.items():
        rows = load_jsonl(path)
        
        status = "completed" if len(rows) == 30 else "incomplete_rerun"
        if status == "incomplete_rerun":
            summary_out["status"] = "caveated"
            summary_out["caveat"] = f"{condition} incomplete_rerun. Completed rows: {len(rows)}."
            
        overlaps = [normalized_token_overlap(row.get("expected_answer"), row.get("generated_text")) for row in rows]
        empty_output_count = sum(1 for row in rows if not isinstance(row.get("generated_text"), str) or not row["generated_text"].strip())
        repetition_count = sum(1 for row in rows if is_repetition(row.get("generated_text", "")))
        e2e_times = _e2e_times(rows)
        
        cond_summary = {
            "dataset": "qmsum_meeting_qa_long",
            "condition": condition,
            "status": status,
            "row_count": len(rows),
            "avg_answer_token_overlap": round(_mean(overlaps), 6),
            "overlap_proxy": round(_mean(overlaps), 6),
            "empty_output_count": empty_output_count,
            "repetition_count": repetition_count,
            "hit_cap_count": sum(1 for row in rows if _hit_cap(row)),
            "avg_input_tokens": round(_mean(_numbers(rows, "input_tokens")), 6),
            "avg_output_tokens": round(_mean(_numbers(rows, "output_tokens")), 6),
            "avg_generation_latency_s": round(_mean(_numbers(rows, "generation_time_s")), 6),
            "avg_e2e_latency_s": round(_mean(e2e_times), 6),
            "avg_t_compress_ms": round(_mean(_numbers(rows, "t_compress_ms")), 6),
            "avg_t_prefill_ms": round(_mean(_numbers(rows, "t_prefill_ms")), 6),
            "generation_tok_per_sec_weighted": round(_weighted_tok_s(rows, include_compression=False), 6),
            "e2e_tok_per_sec_weighted": round(_weighted_tok_s(rows, include_compression=True), 6),
            "avg_tau_mean": round(_mean(_numbers(rows, "tau_mean")), 6),
            "avg_compression_ratio": round(_mean(_numbers(rows, "actual_compression_ratio", "compression_ratio", "R_actual")), 6),
            "avg_original_input_tokens": round(_mean(_numbers(rows, "original_input_tokens", "N_original")), 6),
            "avg_compressed_input_tokens": round(_mean(_numbers(rows, "compressed_input_tokens", "N_compressed")), 6),
        }
        summary_out["conditions"][condition] = cond_summary
        summaries.append(cond_summary)
        
    return summary_out, summaries


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    gsm8k_summary, gsm8k_table = analyze_gsm8k()
    _write_json(Path("results/task83_gsm8k_dflash_r1_repair_summary.json"), gsm8k_summary)
    _write_csv(Path("results/task83_gsm8k_dflash_r1_repair_table.csv"), gsm8k_table)
    
    qmsum_summary, qmsum_table = analyze_qmsum()
    _write_json(Path("results/task83_qmsum_repair_summary.json"), qmsum_summary)
    _write_csv(Path("results/task83_qmsum_repair_table.csv"), qmsum_table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
