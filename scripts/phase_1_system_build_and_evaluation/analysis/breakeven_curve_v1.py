from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


DEFAULT_PREFILL_ARTIFACT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task39_t_prefill_smoke.jsonl")
DEFAULT_OUTPUT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task40_breakeven_curve_v1_summary.json")
DEFAULT_CONDITION_ARTIFACTS = {
    "DFlash-R1": Path("results/phase_1_system_build_and_evaluation/early_experiments/task31_dflash_r1_longctx_text_n6.jsonl"),
    "CC-LLM-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task31_cc_llm_r2_longctx_text_n6.jsonl"),
    "CC-LLM-R3": Path("results/phase_1_system_build_and_evaluation/early_experiments/task31_cc_llm_r3_longctx_text_n6.jsonl"),
    "LLMLingua-AR-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task31_llmlingua_ar_r2_longctx_text_n6.jsonl"),
    "LLMLingua-AR-R3": Path("results/phase_1_system_build_and_evaluation/early_experiments/task31_llmlingua_ar_r3_longctx_text_n6.jsonl"),
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _numeric_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [
        float(row[key])
        for row in rows
        if isinstance(row.get(key), (int, float)) and not isinstance(row.get(key), bool)
    ]


def _average(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _positive_average(values: list[float]) -> float | None:
    positives = [value for value in values if value > 0]
    return _average(positives)


def _breakeven_required_prefill_ms(t_compress_ms: float | None, r_actual: float | None) -> float | None:
    if t_compress_ms is None or r_actual is None or r_actual <= 1.0:
        return None
    saved_fraction = 1.0 - (1.0 / (r_actual**2))
    if saved_fraction <= 0:
        return None
    return t_compress_ms / saved_fraction


def _saved_fraction(r_actual: float | None) -> float | None:
    if r_actual is None or r_actual <= 1.0:
        return None
    return 1.0 - (1.0 / (r_actual**2))


def summarize_prefill_reference(path: Path) -> dict[str, Any]:
    rows = load_jsonl(path)
    t_prefill_values = _numeric_values(rows, "t_prefill_ms")
    input_token_values = _numeric_values(rows, "input_tokens")
    allocated_values = _numeric_values(rows, "prefill_vram_allocated_gib")
    reserved_values = _numeric_values(rows, "prefill_vram_reserved_gib")
    modes = sorted({str(row.get("t_prefill_mode")) for row in rows if row.get("t_prefill_mode") is not None})

    return {
        "artifact": str(path),
        "rows": len(rows),
        "condition": rows[0].get("condition") if rows else None,
        "avg_t_prefill_ms": _average(t_prefill_values),
        "avg_input_tokens": _average(input_token_values),
        "max_prefill_vram_allocated_gib": max(allocated_values) if allocated_values else None,
        "max_prefill_vram_reserved_gib": max(reserved_values) if reserved_values else None,
        "t_prefill_modes": modes,
    }


def summarize_condition(condition: str, path: Path, reference: dict[str, Any]) -> dict[str, Any]:
    rows = load_jsonl(path)
    avg_t_compress = _average(_numeric_values(rows, "t_compress_ms"))
    avg_r_actual = _average(_numeric_values(rows, "R_actual"))
    avg_keep_rate = _average(_numeric_values(rows, "keep_rate"))
    avg_n_original = _average(_numeric_values(rows, "N_original"))
    avg_n_compressed = _average(_numeric_values(rows, "N_compressed"))
    avg_input_tokens = _average(_numeric_values(rows, "input_tokens"))
    avg_t_prefill = _average(_numeric_values(rows, "t_prefill_ms"))
    rows_with_t_prefill = len(_numeric_values(rows, "t_prefill_ms"))

    saved_fraction = _saved_fraction(avg_r_actual)
    required_full_prefill_ms = _breakeven_required_prefill_ms(avg_t_compress, avg_r_actual)

    reference_t_prefill_ms = reference.get("avg_t_prefill_ms")
    reference_input_tokens = reference.get("avg_input_tokens")
    reference_saved_prefill_ms = None
    reference_margin_ms = None
    estimated_original_prefill_ms = None
    estimated_saved_prefill_ms = None
    estimated_margin_ms = None

    if isinstance(reference_t_prefill_ms, (int, float)) and saved_fraction is not None:
        reference_saved_prefill_ms = float(reference_t_prefill_ms) * saved_fraction
        if avg_t_compress is not None:
            reference_margin_ms = reference_saved_prefill_ms - avg_t_compress

    if (
        isinstance(reference_t_prefill_ms, (int, float))
        and isinstance(reference_input_tokens, (int, float))
        and reference_input_tokens > 0
        and isinstance(avg_n_original, (int, float))
        and saved_fraction is not None
    ):
        estimated_original_prefill_ms = float(reference_t_prefill_ms) * ((avg_n_original / reference_input_tokens) ** 2)
        estimated_saved_prefill_ms = estimated_original_prefill_ms * saved_fraction
        if avg_t_compress is not None:
            estimated_margin_ms = estimated_saved_prefill_ms - avg_t_compress

    if avg_t_compress is None:
        data_status = "no_compression_reference"
    elif rows_with_t_prefill == len(rows) and rows:
        data_status = "measured_compressed_t_prefill_available"
    else:
        data_status = "insufficient_measured_compressed_t_prefill"

    return {
        "condition": condition,
        "artifact": str(path),
        "rows": len(rows),
        "rows_with_t_prefill_ms": rows_with_t_prefill,
        "data_status": data_status,
        "avg_input_tokens": avg_input_tokens,
        "avg_t_prefill_ms": avg_t_prefill,
        "avg_t_compress_ms": avg_t_compress,
        "avg_R_actual": avg_r_actual,
        "avg_keep_rate": avg_keep_rate,
        "avg_N_original": avg_n_original,
        "avg_N_compressed": avg_n_compressed,
        "saved_prefill_fraction_model": saved_fraction,
        "required_full_prefill_ms_for_breakeven": required_full_prefill_ms,
        "reference_prefill_saved_ms": reference_saved_prefill_ms,
        "reference_prefill_margin_ms": reference_margin_ms,
        "estimated_original_prefill_ms_from_quadratic_scaling": estimated_original_prefill_ms,
        "estimated_saved_prefill_ms_from_quadratic_scaling": estimated_saved_prefill_ms,
        "estimated_margin_ms_from_quadratic_scaling": estimated_margin_ms,
    }


def analyze_breakeven_curve_v1(
    *,
    prefill_artifact: Path = DEFAULT_PREFILL_ARTIFACT,
    condition_artifacts: dict[str, Path] | None = None,
) -> dict[str, Any]:
    artifacts = condition_artifacts or DEFAULT_CONDITION_ARTIFACTS
    reference = summarize_prefill_reference(prefill_artifact)
    conditions = {
        condition: summarize_condition(condition, path, reference)
        for condition, path in artifacts.items()
    }

    insufficient = [
        condition
        for condition, summary in conditions.items()
        if summary["data_status"] == "insufficient_measured_compressed_t_prefill"
    ]

    return {
        "status": "PARTIAL",
        "scope": "preliminary_breakeven_curve_v1",
        "prefill_reference": reference,
        "conditions": conditions,
        "interpretation": {
            "measured_compressed_t_prefill_available": not insufficient,
            "insufficient_conditions": insufficient,
            "curve_basis": (
                "Uses Task 39 Baseline-AR measured T_prefill plus Task 31 compressed-condition "
                "T_compress/R_actual. Compressed-condition T_prefill is not yet measured in these artifacts."
            ),
            "claim_policy": (
                "Preliminary planning analysis only; no final speedup, correctness, deploy readiness, "
                "8 GB fit, or proven compression benefit claim."
            ),
        },
    }


def write_summary(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def print_summary(summary: dict[str, Any]) -> None:
    reference = summary["prefill_reference"]
    print(
        "Prefill reference:"
        f" artifact={reference['artifact']}"
        f" rows={reference['rows']}"
        f" avg_t_prefill_ms={_fmt(reference['avg_t_prefill_ms'])}"
        f" avg_input_tokens={_fmt(reference['avg_input_tokens'])}"
        f" modes={','.join(reference['t_prefill_modes'])}"
    )
    for condition, item in summary["conditions"].items():
        print(
            f"{condition}: status={item['data_status']} rows={item['rows']} "
            f"rows_with_t_prefill={item['rows_with_t_prefill_ms']} "
            f"avg_t_compress_ms={_fmt(item['avg_t_compress_ms'])} "
            f"avg_R_actual={_fmt(item['avg_R_actual'])} "
            f"required_full_prefill_ms={_fmt(item['required_full_prefill_ms_for_breakeven'])} "
            f"reference_margin_ms={_fmt(item['reference_prefill_margin_ms'])} "
            f"estimated_margin_ms={_fmt(item['estimated_margin_ms_from_quadratic_scaling'])}"
        )
    print(f"Overall status: {summary['status']}")
    print(f"Curve basis: {summary['interpretation']['curve_basis']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze preliminary CC-DFlash breakeven curve v1")
    parser.add_argument("--prefill-artifact", default=str(DEFAULT_PREFILL_ARTIFACT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    summary = analyze_breakeven_curve_v1(prefill_artifact=Path(args.prefill_artifact))
    write_summary(summary, Path(args.output))
    print_summary(summary)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
