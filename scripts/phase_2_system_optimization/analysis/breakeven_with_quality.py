from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


TASK31_ARTIFACTS = {
    "DFlash-R1": Path("results/phase_1_system_build_and_evaluation/early_experiments/task31_dflash_r1_longctx_text_n6.jsonl"),
    "CC-LLM-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task31_cc_llm_r2_longctx_text_n6.jsonl"),
    "CC-LLM-R3": Path("results/phase_1_system_build_and_evaluation/early_experiments/task31_cc_llm_r3_longctx_text_n6.jsonl"),
    "LLMLingua-AR-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task31_llmlingua_ar_r2_longctx_text_n6.jsonl"),
    "LLMLingua-AR-R3": Path("results/phase_1_system_build_and_evaluation/early_experiments/task31_llmlingua_ar_r3_longctx_text_n6.jsonl"),
}

QUALITY_SUMMARY = Path("results/phase_1_system_build_and_evaluation/early_experiments/task32_answer_quality_summary.json")
DEFAULT_OUTPUT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task33_phase2_breakeven_quality_summary.json")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def e2e_time_s(row: dict[str, Any]) -> float:
    t_compress_ms = row.get("t_compress_ms")
    compression_s = float(t_compress_ms) / 1000.0 if isinstance(t_compress_ms, (int, float)) else 0.0
    return float(row["generation_time_s"]) + compression_s


def _average(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _numeric_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]


def containment_per_second(*, normalized_count: int, total_e2e_time_s: float) -> float:
    return normalized_count / total_e2e_time_s if total_e2e_time_s > 0 else 0.0


def _quality_by_condition(quality_summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_condition: dict[str, dict[str, Any]] = {}
    for artifact in quality_summary.get("artifacts", []):
        summary = dict(artifact.get("summary", {}))
        condition = str(summary.get("condition"))
        normalized_row_indexes = [
            int(row["row_index"])
            for row in artifact.get("rows", [])
            if row.get("normalized_match") is True
        ]
        summary["normalized_row_indexes"] = normalized_row_indexes
        by_condition[condition] = summary
    return by_condition


def _quality_gated_e2e_times(rows: list[dict[str, Any]], quality: dict[str, Any]) -> list[float]:
    normalized_indexes = quality.get("normalized_row_indexes") or []
    if normalized_indexes:
        return [
            e2e_time_s(rows[index - 1])
            for index in normalized_indexes
            if 1 <= index <= len(rows)
        ]

    normalized_count = int(quality.get("normalized_containment_count", 0))
    return [e2e_time_s(row) for row in rows[:normalized_count]]


def analyze_condition(condition: str, path: Path, quality: dict[str, Any]) -> dict[str, Any]:
    rows = load_jsonl(path)
    e2e_times = [e2e_time_s(row) for row in rows]
    gated_e2e_times = _quality_gated_e2e_times(rows, quality)
    normalized_count = int(quality.get("normalized_containment_count", 0))
    no_containment_count = int(quality.get("no_containment_count", 0))
    total_e2e = sum(e2e_times)

    return {
        "condition": condition,
        "artifact": str(path),
        "rows": len(rows),
        "avg_tok_per_sec": _average(_numeric_values(rows, "tok_per_sec")),
        "median_tok_per_sec": _median(_numeric_values(rows, "tok_per_sec")),
        "avg_generation_time_s": _average(_numeric_values(rows, "generation_time_s")),
        "avg_e2e_time_s": _average(e2e_times),
        "avg_tau_mean": _average(_numeric_values(rows, "tau_mean")),
        "avg_t_compress_ms": _average(_numeric_values(rows, "t_compress_ms")),
        "avg_R_actual": _average(_numeric_values(rows, "R_actual")),
        "max_vram_allocated": max(_numeric_values(rows, "vram_allocated_gib")),
        "max_vram_reserved": max(_numeric_values(rows, "vram_reserved_gib")),
        "exact_containment_count": int(quality.get("exact_containment_count", 0)),
        "exact_rate": float(quality.get("exact_rate", 0.0)),
        "normalized_containment_count": normalized_count,
        "normalized_rate": float(quality.get("normalized_rate", 0.0)),
        "no_containment_count": no_containment_count,
        "no_containment_rate": no_containment_count / len(rows) if rows else 0.0,
        "quality_gated_avg_e2e_time_s": _average(gated_e2e_times),
        "normalized_containment_per_second": containment_per_second(
            normalized_count=normalized_count,
            total_e2e_time_s=total_e2e,
        ),
    }


def assign_carry_forward_label(summary: dict[str, Any], baseline: dict[str, Any]) -> dict[str, str]:
    condition = str(summary["condition"])
    normalized_rate = float(summary.get("normalized_rate", 0.0))
    baseline_rate = float(baseline.get("normalized_rate", 0.0))
    avg_e2e = float(summary.get("avg_e2e_time_s") or 0.0)
    baseline_e2e = float(baseline.get("avg_e2e_time_s") or 0.0)
    max_vram = float(summary.get("max_vram_allocated") or 0.0)
    baseline_vram = float(baseline.get("max_vram_allocated") or 0.0)
    lower_vram = max_vram < baseline_vram * 0.8 if baseline_vram else False
    competitive_quality = normalized_rate >= max(0.0, baseline_rate - 0.10)

    if condition == "DFlash-R1":
        return {
            "label": "KEEP_BASELINE",
            "reason": "No-compression DFlash control remains the required baseline artifact.",
        }

    if condition == "LLMLingua-AR-R2":
        if lower_vram and competitive_quality:
            return {
                "label": "KEEP_LOW_VRAM_BASELINE",
                "reason": "Matches baseline containment in this fixture while using materially lower VRAM.",
            }
        return {
            "label": "WATCHLIST",
            "reason": "Target-only AR path is useful for low-VRAM comparison, but quality or speed is not yet decisive.",
        }

    if condition == "LLMLingua-AR-R3":
        if normalized_rate < baseline_rate and not competitive_quality:
            return {
                "label": "DEPRIORITIZE_FOR_NOW",
                "reason": "Lower containment than R2/baseline without a stronger low-VRAM advantage.",
            }
        return {
            "label": "WATCHLIST",
            "reason": "Keep only if later evidence shows the stronger compression is useful.",
        }

    if condition.startswith("CC-LLM"):
        if normalized_rate == 0.0:
            return {
                "label": "DEPRIORITIZE_FOR_NOW",
                "reason": "No normalized containment in the current fixture, so e2e tradeoff is not actionable.",
            }
        return {
            "label": "WATCHLIST",
            "reason": "Speculative path has DFlash acceptance data, but current CPU compression overhead prevents an e2e win.",
        }

    return {
        "label": "WATCHLIST",
        "reason": "Condition is not covered by the current conservative policy.",
    }


def analyze_phase2(
    artifact_paths: dict[str, Path] | None = None,
    quality_summary_path: Path = QUALITY_SUMMARY,
) -> dict[str, Any]:
    paths = artifact_paths or TASK31_ARTIFACTS
    quality_summary = json.loads(quality_summary_path.read_text(encoding="utf-8"))
    quality = _quality_by_condition(quality_summary)
    conditions = {
        condition: analyze_condition(condition, path, quality.get(condition, {}))
        for condition, path in paths.items()
    }
    baseline = conditions.get("DFlash-R1") or next(iter(conditions.values()))
    for summary in conditions.values():
        summary["carry_forward"] = assign_carry_forward_label(summary, baseline)

    return {
        "inputs": {
            "artifacts": {condition: str(path) for condition, path in paths.items()},
            "quality_summary": str(quality_summary_path),
        },
        "method": {
            "e2e_time_s": "generation_time_s + t_compress_ms / 1000 when compression exists",
            "quality_gate": "normalized containment from Task 32 deterministic scorer",
            "normalized_containment_per_second": "normalized_containment_count / total_e2e_time_s",
        },
        "conditions": conditions,
    }


def write_analysis(analysis: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def print_analysis(analysis: dict[str, Any]) -> None:
    for condition, summary in analysis["conditions"].items():
        carry = summary["carry_forward"]
        print(
            f"{condition}: rows={summary['rows']} avg_tok_s={_fmt(summary['avg_tok_per_sec'])} "
            f"median_tok_s={_fmt(summary['median_tok_per_sec'])} avg_generation_time_s={_fmt(summary['avg_generation_time_s'])} "
            f"avg_e2e_time_s={_fmt(summary['avg_e2e_time_s'])} avg_tau={_fmt(summary['avg_tau_mean'])} "
            f"avg_t_compress_ms={_fmt(summary['avg_t_compress_ms'])} avg_R_actual={_fmt(summary['avg_R_actual'])} "
            f"max_vram_allocated={_fmt(summary['max_vram_allocated'])} max_vram_reserved={_fmt(summary['max_vram_reserved'])} "
            f"normalized={summary['normalized_containment_count']}/{summary['rows']} "
            f"normalized_rate={summary['normalized_rate']:.2f} no_containment={summary['no_containment_count']} "
            f"quality_gated_avg_e2e={_fmt(summary['quality_gated_avg_e2e_time_s'])} "
            f"containment_per_s={_fmt(summary['normalized_containment_per_second'])} "
            f"label={carry['label']}"
        )
        print(f"  reason={carry['reason']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Phase 2 breakeven with deterministic quality gate")
    parser.add_argument("--quality-summary", default=str(QUALITY_SUMMARY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    analysis = analyze_phase2(quality_summary_path=Path(args.quality_summary))
    write_analysis(analysis, Path(args.output))
    print_analysis(analysis)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
