"""Process-local JSONL benchmark helper."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Iterable

from ..config import Config
from ..runtime.engine import RuntimeEngine


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if "id" not in row or "prompt" not in row:
            raise ValueError(f"line {line_number} must contain id and prompt")
        rows.append(row)
    return rows


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def run_benchmark(
    config: Config,
    *,
    input_path: str | Path,
    conditions: list[str],
    target_profile: str = "primary",
) -> dict[str, Any]:
    inputs = read_jsonl(input_path)
    repetitions = int(config.require("benchmark.repetitions"))
    warmups = int(config.require("benchmark.warmup_requests"))
    all_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for condition in conditions:
        engine = RuntimeEngine(config, condition=condition, target_profile=target_profile)
        try:
            for index in range(warmups):
                engine.generate(inputs[index % len(inputs)]["prompt"], max_new_tokens=32)
            condition_rows: list[dict[str, Any]] = []
            for repetition in range(repetitions):
                for item in inputs:
                    result = engine.generate(
                        item["prompt"],
                        dataset=str(item.get("dataset", "general")),
                        max_new_tokens=int(item.get("max_new_tokens", config.require("runtime.max_new_tokens"))),
                    )
                    record = {
                        "id": item["id"],
                        "repetition": repetition,
                        **result.to_dict(),
                    }
                    all_rows.append(record)
                    condition_rows.append(record)
            summaries.append(_summarize(condition, condition_rows))
        finally:
            engine.close()
    output = config.path_for("benchmark.output_jsonl")
    write_jsonl(output, all_rows)
    summary = {"conditions": summaries, "rows": len(all_rows), "output_jsonl": str(output)}
    summary_path = config.path_for("benchmark.summary_json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _summarize(condition: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [row["metrics"] for row in rows]
    timing = [row["timing"] for row in rows]
    memory = [row["memory"] for row in rows]
    summary = {
        "condition": condition,
        "rows": len(rows),
        "mean_decode_tok_s": statistics.fmean(float(value["decode_tok_s"]) for value in metrics),
        "mean_generation_tok_s": statistics.fmean(float(value["generation_tok_s"]) for value in metrics),
        "mean_warm_request_tok_s": statistics.fmean(float(value["warm_request_tok_s"]) for value in metrics),
        "mean_target_prefill_ms": statistics.fmean(float(value["target_prefill_ms"]) for value in timing),
        "mean_decode_total_ms": statistics.fmean(float(value["decode_total_ms"]) for value in timing),
        "peak_reserved_bytes": max(int(value["peak_reserved_bytes"]) for value in memory),
        "memory_gate_pass": all(value.get("gate_pass") is not False for value in memory),
    }
    if condition == "dflash":
        dflash = [row["dflash"] for row in rows]
        summary.update(
            {
                "mean_effective_tau": statistics.fmean(float(value["effective_tau"]) for value in dflash),
                "mean_draft_acceptance_rate": statistics.fmean(
                    float(value["draft_acceptance_rate"]) for value in dflash
                ),
                "mean_target_forwards_per_output_token": statistics.fmean(
                    float(value["target_forwards_per_output_token"]) for value in dflash
                ),
            }
        )
    return summary
