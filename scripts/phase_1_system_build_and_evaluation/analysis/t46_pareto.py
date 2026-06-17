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


DEFAULT_AUDIT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task45_final_artifact_audit_summary.json")
DEFAULT_OUTPUT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task46_pareto_summary.json")
DEFAULT_CSV = Path("results/phase_1_system_build_and_evaluation/early_experiments/task46_pareto_table.csv")

CONDITION_ORDER = ["Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-LLM-R2"]
HIGHER_IS_BETTER = {
    "avg_tokens_per_second",
    "e2e_output_tokens_per_second",
    "quality_normalized_rate",
}
LOWER_IS_BETTER = {
    "avg_e2e_latency_s",
    "max_vram_reserved_gib",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: line {line_number} is not valid JSON ({exc})") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}: line {line_number} is not a JSON object")
        rows.append(row)
    return rows


def _number(row: dict[str, Any], *names: str) -> float | None:
    for name in names:
        value = row.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _numeric_values(rows: list[dict[str, Any]], *names: str) -> list[float]:
    values = []
    for row in rows:
        value = _number(row, *names)
        if value is not None:
            values.append(value)
    return values


def _avg(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _max(values: list[float]) -> float | None:
    return max(values) if values else None


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def e2e_latency_s(row: dict[str, Any]) -> float:
    generation_time_s = _number(row, "generation_time_s") or 0.0
    t_compress_ms = _number(row, "t_compress_ms") or 0.0
    return generation_time_s + (t_compress_ms / 1000.0)


def _quality_from_audit(audit_summary: dict[str, Any], condition: str, rows: int) -> dict[str, Any]:
    quality = dict(audit_summary["artifacts"][condition].get("quality", {}))
    normalized_total = int(quality.get("exact_containment_count", 0)) + int(
        quality.get("normalized_containment_count", 0)
    )
    generated_rows = int(quality.get("generated_text_present", rows))
    denominator = rows or 1
    return {
        "generated_text_rows": generated_rows,
        "exact_containment": int(quality.get("exact_containment_count", 0)),
        "normalized_containment_total": normalized_total,
        "extracted_numeric_matches": int(quality.get("extracted_answer_match_count", 0)),
        "no_containment": int(quality.get("no_containment_count", 0)),
        "not_evaluable": int(quality.get("not_evaluable_count", 0)),
        "exact_containment_rate": float(quality.get("exact_containment_rate", 0.0)),
        "normalized_containment_rate": normalized_total / denominator,
        "extracted_numeric_match_rate": float(quality.get("extracted_answer_match_rate", 0.0)),
        "policy": "diagnostic_only",
    }


def summarize_condition(condition: str, path: Path, audit_summary: dict[str, Any]) -> dict[str, Any]:
    rows = load_jsonl(path)
    decode_latencies = _numeric_values(rows, "generation_time_s")
    e2e_latencies = [e2e_latency_s(row) for row in rows]
    output_tokens = _numeric_values(rows, "output_tokens")
    total_output_tokens = sum(output_tokens)
    total_e2e_latency = sum(e2e_latencies)
    quality = _quality_from_audit(audit_summary, condition, len(rows))

    return {
        "condition": condition,
        "artifact": str(path),
        "rows": len(rows),
        "avg_tokens_per_second": _avg(_numeric_values(rows, "tokens_per_second", "tok_per_sec")),
        "median_tokens_per_second": _median(_numeric_values(rows, "tokens_per_second", "tok_per_sec")),
        "avg_generation_time_s": _avg(decode_latencies),
        "median_generation_time_s": _median(decode_latencies),
        "avg_output_tokens": _avg(output_tokens),
        "avg_input_tokens": _avg(_numeric_values(rows, "input_tokens")),
        "avg_tau_mean": _avg(_numeric_values(rows, "tau_mean")),
        "median_tau_mean": _median(_numeric_values(rows, "tau_mean")),
        "avg_t_prefill_ms": _avg(_numeric_values(rows, "t_prefill_ms")),
        "avg_t_compress_ms": _avg(_numeric_values(rows, "t_compress_ms")),
        "avg_R_actual": _avg(_numeric_values(rows, "R_actual", "r_actual")),
        "max_vram_allocated_gib": _max(_numeric_values(rows, "vram_allocated_gib")),
        "max_vram_reserved_gib": _max(_numeric_values(rows, "vram_reserved_gib")),
        "avg_e2e_latency_s": _avg(e2e_latencies),
        "median_e2e_latency_s": _median(e2e_latencies),
        "e2e_output_tokens_per_second": total_output_tokens / total_e2e_latency if total_e2e_latency > 0 else 0.0,
        "quality": quality,
    }


def compare_conditions(name: str, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_quality = left["quality"]["normalized_containment_rate"]
    right_quality = right["quality"]["normalized_containment_rate"]
    return {
        "comparison": name,
        "left_condition": left["condition"],
        "right_condition": right["condition"],
        "decode_throughput_ratio": _safe_ratio(left.get("avg_tokens_per_second"), right.get("avg_tokens_per_second")),
        "avg_tok_s_delta": (
            left["avg_tokens_per_second"] - right["avg_tokens_per_second"]
            if left.get("avg_tokens_per_second") is not None and right.get("avg_tokens_per_second") is not None
            else None
        ),
        "input_token_ratio": _safe_ratio(left.get("avg_input_tokens"), right.get("avg_input_tokens")),
        "e2e_latency_ratio": _safe_ratio(left.get("avg_e2e_latency_s"), right.get("avg_e2e_latency_s")),
        "e2e_tok_s_ratio": _safe_ratio(left.get("e2e_output_tokens_per_second"), right.get("e2e_output_tokens_per_second")),
        "tau_mean_delta": (
            left["avg_tau_mean"] - right["avg_tau_mean"]
            if left.get("avg_tau_mean") is not None and right.get("avg_tau_mean") is not None
            else None
        ),
        "vram_reserved_delta_gib": (
            left["max_vram_reserved_gib"] - right["max_vram_reserved_gib"]
            if left.get("max_vram_reserved_gib") is not None and right.get("max_vram_reserved_gib") is not None
            else None
        ),
        "quality_normalized_delta": left_quality - right_quality,
        "quality_extracted_numeric_delta": (
            left["quality"]["extracted_numeric_match_rate"] - right["quality"]["extracted_numeric_match_rate"]
        ),
        "compression_cost_delta_ms": (
            (left.get("avg_t_compress_ms") or 0.0) - (right.get("avg_t_compress_ms") or 0.0)
        ),
        "left_is_pareto_dominant_decode_view": False,
        "left_is_pareto_dominant_e2e_view": False,
    }


def _score_for(summary: dict[str, Any], metric: str) -> float | None:
    if metric == "quality_normalized_rate":
        return float(summary["quality"]["normalized_containment_rate"])
    value = summary.get(metric)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def dominates(left: dict[str, Any], right: dict[str, Any], metrics: list[str]) -> bool:
    better_or_equal = True
    strictly_better = False
    for metric in metrics:
        left_value = _score_for(left, metric)
        right_value = _score_for(right, metric)
        if left_value is None or right_value is None:
            return False
        if metric in HIGHER_IS_BETTER:
            if left_value < right_value:
                better_or_equal = False
            if left_value > right_value:
                strictly_better = True
        elif metric in LOWER_IS_BETTER:
            if left_value > right_value:
                better_or_equal = False
            if left_value < right_value:
                strictly_better = True
        else:
            raise KeyError(f"unsupported Pareto metric: {metric}")
    return better_or_equal and strictly_better


def pareto_front(conditions: dict[str, dict[str, Any]], metrics: list[str]) -> list[str]:
    front = []
    for condition, summary in conditions.items():
        if not any(
            dominates(other_summary, summary, metrics)
            for other_condition, other_summary in conditions.items()
            if other_condition != condition
        ):
            front.append(condition)
    return sorted(front, key=lambda item: CONDITION_ORDER.index(item) if item in CONDITION_ORDER else 999)


def rank_conditions(conditions: dict[str, dict[str, Any]], key: str, *, reverse: bool = True) -> list[dict[str, Any]]:
    return [
        {"condition": condition, key: _score_for(summary, key)}
        for condition, summary in sorted(
            conditions.items(),
            key=lambda item: (_score_for(item[1], key) is None, _score_for(item[1], key) or 0.0),
            reverse=reverse,
        )
    ]


def analyze_task46(audit_path: Path = DEFAULT_AUDIT) -> dict[str, Any]:
    audit_summary = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit_summary.get("status") != "PASS":
        raise ValueError(f"Task 45 audit summary is not PASS: {audit_summary.get('status')}")

    artifact_paths = {
        condition: Path(data["path"])
        for condition, data in audit_summary["artifacts"].items()
        if condition in CONDITION_ORDER
    }
    conditions = {
        condition: summarize_condition(condition, artifact_paths[condition], audit_summary)
        for condition in CONDITION_ORDER
    }

    comparisons = {
        "DFlash-R1_vs_Baseline-AR": compare_conditions(
            "DFlash-R1 vs Baseline-AR", conditions["DFlash-R1"], conditions["Baseline-AR"]
        ),
        "LLMLingua-AR-R2_vs_Baseline-AR": compare_conditions(
            "LLMLingua-AR-R2 vs Baseline-AR",
            conditions["LLMLingua-AR-R2"],
            conditions["Baseline-AR"],
        ),
        "CC-LLM-R2_vs_LLMLingua-AR-R2": compare_conditions(
            "CC-LLM-R2 vs LLMLingua-AR-R2",
            conditions["CC-LLM-R2"],
            conditions["LLMLingua-AR-R2"],
        ),
        "CC-LLM-R2_vs_DFlash-R1": compare_conditions(
            "CC-LLM-R2 vs DFlash-R1", conditions["CC-LLM-R2"], conditions["DFlash-R1"]
        ),
        "CC-LLM-R2_vs_Baseline-AR": compare_conditions(
            "CC-LLM-R2 vs Baseline-AR", conditions["CC-LLM-R2"], conditions["Baseline-AR"]
        ),
    }

    comparisons["CC-LLM-R2_vs_DFlash-R1"]["left_is_pareto_dominant_decode_view"] = dominates(
        conditions["CC-LLM-R2"],
        conditions["DFlash-R1"],
        ["avg_tokens_per_second", "quality_normalized_rate", "max_vram_reserved_gib"],
    )
    comparisons["CC-LLM-R2_vs_DFlash-R1"]["left_is_pareto_dominant_e2e_view"] = dominates(
        conditions["CC-LLM-R2"],
        conditions["DFlash-R1"],
        ["e2e_output_tokens_per_second", "quality_normalized_rate", "max_vram_reserved_gib"],
    )

    decode_front_metrics = ["avg_tokens_per_second", "quality_normalized_rate", "max_vram_reserved_gib"]
    e2e_front_metrics = ["e2e_output_tokens_per_second", "quality_normalized_rate", "max_vram_reserved_gib"]

    return {
        "task": "46-pareto-analysis",
        "status": "PASS",
        "inputs": {
            "audit_summary": str(audit_path),
            "artifacts": {condition: str(path) for condition, path in artifact_paths.items()},
        },
        "method": {
            "decode_latency_s": "generation_time_s",
            "compression_latency_s": "t_compress_ms / 1000 when present, otherwise 0",
            "e2e_latency_s": "generation_time_s + t_compress_ms / 1000",
            "e2e_output_tokens_per_second": "sum(output_tokens) / sum(e2e_latency_s)",
            "quality_metric": "diagnostic normalized containment rate from Task 45 audit summary",
            "pareto_decode_metrics": decode_front_metrics,
            "pareto_e2e_metrics": e2e_front_metrics,
        },
        "conditions": conditions,
        "comparisons": comparisons,
        "rankings": {
            "decode_only_tok_s_desc": rank_conditions(conditions, "avg_tokens_per_second"),
            "e2e_tok_s_desc": rank_conditions(conditions, "e2e_output_tokens_per_second"),
            "e2e_latency_asc": rank_conditions(conditions, "avg_e2e_latency_s", reverse=False),
            "quality_normalized_rate_desc": rank_conditions(conditions, "quality_normalized_rate"),
        },
        "pareto": {
            "decode_only_front": pareto_front(conditions, decode_front_metrics),
            "decode_only_metrics": decode_front_metrics,
            "e2e_with_compression_cost_front": pareto_front(conditions, e2e_front_metrics),
            "e2e_with_compression_cost_metrics": e2e_front_metrics,
            "interpretation": (
                "Pareto membership is conservative and uses diagnostic quality, not final semantic correctness. "
                "A condition with high decode throughput can remain non-dominant if it loses quality or uses more VRAM."
            ),
        },
        "interpretation": {
            "decode_only": (
                "CC-LLM-R2 has the highest decode-only throughput, while DFlash-R1 substantially improves "
                "decode throughput over Baseline-AR without CPU compression cost."
            ),
            "e2e_with_compression": (
                "CPU LLMLingua compression adds about four seconds per prompt for compressed conditions. "
                "This materially changes the apparent speed tradeoff and prevents a proven end-to-end "
                "compression-benefit claim from Task 46 alone."
            ),
            "quality": (
                "Diagnostic containment/extraction rates are low across all conditions and lower for compressed "
                "conditions than the no-compression controls, so quality prevents a strong global dominance claim."
            ),
            "claim_policy": (
                "No deployment readiness, confirmed 8 GB fit, final semantic correctness, or proven e2e compression "
                "benefit is claimed."
            ),
        },
    }


def write_summary(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "condition",
        "rows",
        "avg_tokens_per_second",
        "median_tokens_per_second",
        "avg_e2e_latency_s",
        "e2e_output_tokens_per_second",
        "avg_tau_mean",
        "avg_t_prefill_ms",
        "avg_t_compress_ms",
        "avg_R_actual",
        "max_vram_reserved_gib",
        "normalized_containment_total",
        "extracted_numeric_matches",
        "no_containment",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for condition in CONDITION_ORDER:
            item = summary["conditions"][condition]
            quality = item["quality"]
            writer.writerow(
                {
                    "condition": condition,
                    "rows": item["rows"],
                    "avg_tokens_per_second": item["avg_tokens_per_second"],
                    "median_tokens_per_second": item["median_tokens_per_second"],
                    "avg_e2e_latency_s": item["avg_e2e_latency_s"],
                    "e2e_output_tokens_per_second": item["e2e_output_tokens_per_second"],
                    "avg_tau_mean": item["avg_tau_mean"],
                    "avg_t_prefill_ms": item["avg_t_prefill_ms"],
                    "avg_t_compress_ms": item["avg_t_compress_ms"],
                    "avg_R_actual": item["avg_R_actual"],
                    "max_vram_reserved_gib": item["max_vram_reserved_gib"],
                    "normalized_containment_total": quality["normalized_containment_total"],
                    "extracted_numeric_matches": quality["extracted_numeric_matches"],
                    "no_containment": quality["no_containment"],
                }
            )


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def print_summary(summary: dict[str, Any]) -> None:
    print(f"status: {summary['status']}")
    for condition in CONDITION_ORDER:
        item = summary["conditions"][condition]
        print(
            f"{condition}: rows={item['rows']} "
            f"decode_tok_s={_fmt(item['avg_tokens_per_second'])} "
            f"e2e_tok_s={_fmt(item['e2e_output_tokens_per_second'])} "
            f"avg_e2e_s={_fmt(item['avg_e2e_latency_s'])} "
            f"tau={_fmt(item['avg_tau_mean'])} "
            f"quality_norm={item['quality']['normalized_containment_total']}/{item['rows']}"
        )
    print("decode_front:", ", ".join(summary["pareto"]["decode_only_front"]))
    print("e2e_front:", ", ".join(summary["pareto"]["e2e_with_compression_cost_front"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 46 Pareto tradeoffs from audited Task 45 artifacts")
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT), help="Task 45 audit summary JSON")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON summary path")
    parser.add_argument("--csv-output", default=str(DEFAULT_CSV), help="Optional CSV table output path")
    args = parser.parse_args()

    summary = analyze_task46(Path(args.audit))
    write_summary(summary, Path(args.output))
    if args.csv_output:
        write_csv(summary, Path(args.csv_output))
    print_summary(summary)
    print(f"wrote {args.output}")
    if args.csv_output:
        print(f"wrote {args.csv_output}")


if __name__ == "__main__":
    main()
