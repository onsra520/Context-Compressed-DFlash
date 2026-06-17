from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


TASK24_ARTIFACTS = {
    "DFlash-R1": Path("results/phase_1_system_build_and_evaluation/early_experiments/task24_dflash_r1_n10.jsonl"),
    "CC-LLM-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task24_cc_llm_r2_n10.jsonl"),
    "CC-LLM-R3": Path("results/phase_1_system_build_and_evaluation/early_experiments/task24_cc_llm_r3_n10.jsonl"),
    "LLMLingua-AR-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task24_llmlingua_ar_r2_n10.jsonl"),
    "LLMLingua-AR-R3": Path("results/phase_1_system_build_and_evaluation/early_experiments/task24_llmlingua_ar_r3_n10.jsonl"),
}

LONG_CONTEXT_FIXTURE = Path("tests/fixtures/long_context_smoke.jsonl")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _average(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def summarize_rows(condition: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    t_compress_values = [float(row["t_compress_ms"]) for row in rows if "t_compress_ms" in row]
    r_actual_values = [float(row["R_actual"]) for row in rows if "R_actual" in row]
    e2e_times = [
        float(row["generation_time_s"]) + (float(row.get("t_compress_ms", 0.0)) / 1000.0)
        for row in rows
    ]

    return {
        "condition": condition,
        "rows": len(rows),
        "avg_tok_s": _average([float(row["tok_per_sec"]) for row in rows]),
        "median_tok_s": _median([float(row["tok_per_sec"]) for row in rows]),
        "avg_input_tokens": _average([float(row["input_tokens"]) for row in rows]),
        "avg_output_tokens": _average([float(row["output_tokens"]) for row in rows]),
        "avg_tau_mean": _average([float(row["tau_mean"]) for row in rows]),
        "avg_t_compress_ms": _average(t_compress_values) if t_compress_values else None,
        "avg_r_actual": _average(r_actual_values) if r_actual_values else None,
        "max_vram_allocated": max(float(row["vram_allocated_gib"]) for row in rows),
        "max_vram_reserved": max(float(row["vram_reserved_gib"]) for row in rows),
        "avg_generation_time_s": _average([float(row["generation_time_s"]) for row in rows]),
        "avg_e2e_time_s": _average(e2e_times),
    }


def compute_generation_speed_ratio(numerator: dict[str, Any], denominator: dict[str, Any]) -> float:
    return float(numerator["avg_tok_s"]) / float(denominator["avg_tok_s"])


def summarize_fixture(path: Path) -> dict[str, Any]:
    rows = load_jsonl(path)
    lengths = [int(row["approximate_context_words"]) for row in rows]
    domains = sorted({str(row["domain"]) for row in rows})
    return {
        "count": len(rows),
        "avg_approximate_context_words": _average([float(value) for value in lengths]),
        "min_approximate_context_words": min(lengths),
        "max_approximate_context_words": max(lengths),
        "domains": domains,
    }


def analyze_task24_matrix(
    artifact_paths: dict[str, Path] | None = None,
    fixture_path: Path = LONG_CONTEXT_FIXTURE,
) -> dict[str, Any]:
    paths = artifact_paths or TASK24_ARTIFACTS
    metrics = {
        condition: summarize_rows(condition, load_jsonl(path))
        for condition, path in paths.items()
    }

    comparisons = {
        "cc_llm_r2_vs_dflash_r1_tok_s_ratio": compute_generation_speed_ratio(metrics["CC-LLM-R2"], metrics["DFlash-R1"]),
        "cc_llm_r3_vs_dflash_r1_tok_s_ratio": compute_generation_speed_ratio(metrics["CC-LLM-R3"], metrics["DFlash-R1"]),
        "cc_llm_r2_vs_ar_r2_tok_s_ratio": compute_generation_speed_ratio(metrics["CC-LLM-R2"], metrics["LLMLingua-AR-R2"]),
        "cc_llm_r3_vs_ar_r3_tok_s_ratio": compute_generation_speed_ratio(metrics["CC-LLM-R3"], metrics["LLMLingua-AR-R3"]),
        "cc_llm_r2_vs_dflash_r1_e2e_ratio": metrics["CC-LLM-R2"]["avg_e2e_time_s"] / metrics["DFlash-R1"]["avg_e2e_time_s"],
        "cc_llm_r3_vs_dflash_r1_e2e_ratio": metrics["CC-LLM-R3"]["avg_e2e_time_s"] / metrics["DFlash-R1"]["avg_e2e_time_s"],
        "cc_llm_r2_vs_ar_r2_e2e_ratio": metrics["CC-LLM-R2"]["avg_e2e_time_s"] / metrics["LLMLingua-AR-R2"]["avg_e2e_time_s"],
        "cc_llm_r3_vs_ar_r3_e2e_ratio": metrics["CC-LLM-R3"]["avg_e2e_time_s"] / metrics["LLMLingua-AR-R3"]["avg_e2e_time_s"],
    }

    return {
        "metrics": metrics,
        "comparisons": comparisons,
        "fixture": summarize_fixture(fixture_path),
    }


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def print_analysis(analysis: dict[str, Any]) -> None:
    print("Task 24 matrix metrics:")
    for condition, summary in analysis["metrics"].items():
        print(
            f"{condition}: rows={summary['rows']} avg_tok_s={_fmt(summary['avg_tok_s'])} "
            f"median_tok_s={_fmt(summary['median_tok_s'])} avg_input_tokens={_fmt(summary['avg_input_tokens'])} "
            f"avg_output_tokens={_fmt(summary['avg_output_tokens'])} avg_tau_mean={_fmt(summary['avg_tau_mean'])} "
            f"avg_t_compress_ms={_fmt(summary['avg_t_compress_ms'])} avg_R_actual={_fmt(summary['avg_r_actual'])} "
            f"max_vram_allocated={_fmt(summary['max_vram_allocated'])} max_vram_reserved={_fmt(summary['max_vram_reserved'])} "
            f"avg_e2e_time_s={_fmt(summary['avg_e2e_time_s'])}"
        )

    print("Generation-only ratios:")
    for key, value in analysis["comparisons"].items():
        if key.endswith("_tok_s_ratio"):
            print(f"{key}={value:.2f}")

    print("Approximate end-to-end ratios:")
    for key, value in analysis["comparisons"].items():
        if key.endswith("_e2e_ratio"):
            print(f"{key}={value:.2f}")

    fixture = analysis["fixture"]
    print(
        "Long-context fixture:"
        f" count={fixture['count']}"
        f" avg_approximate_context_words={_fmt(fixture['avg_approximate_context_words'])}"
        f" min_approximate_context_words={fixture['min_approximate_context_words']}"
        f" max_approximate_context_words={fixture['max_approximate_context_words']}"
        f" domains={','.join(fixture['domains'])}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 24 small-matrix artifacts")
    parser.add_argument(
        "--fixture",
        default=str(LONG_CONTEXT_FIXTURE),
        help="Path to the long-context fixture used for descriptive analysis.",
    )
    args = parser.parse_args()

    analysis = analyze_task24_matrix(fixture_path=Path(args.fixture))
    print_analysis(analysis)


if __name__ == "__main__":
    main()
