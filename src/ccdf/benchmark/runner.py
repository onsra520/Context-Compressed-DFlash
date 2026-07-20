"""Process-local benchmark execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import Rec2Config
from ..runtime.engine import RuntimeEngine
from .aggregation import summarize
from .io import read_jsonl, write_jsonl


def run_benchmark(
    config: Rec2Config,
    *,
    input_path: str | Path,
    conditions: list[str],
    target_profile: str = "primary",
) -> dict[str, Any]:
    inputs = read_jsonl(input_path)
    repetitions = int(config.get("benchmark.repetitions", 1))
    warmups = int(config.get("benchmark.warmup_requests", 0))
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
                        max_new_tokens=int(
                            item.get("max_new_tokens", config.require("runtime.max_new_tokens"))
                        ),
                    )
                    record = {
                        "id": item["id"],
                        "repetition": repetition,
                        **result.to_dict(),
                    }
                    all_rows.append(record)
                    condition_rows.append(record)
            summaries.append(summarize(condition, condition_rows))
        finally:
            engine.close()
    output = config.path_for("benchmark.output_jsonl")
    write_jsonl(output, all_rows)
    summary = {"conditions": summaries, "rows": len(all_rows), "output_jsonl": str(output)}
    summary_path = config.path_for("benchmark.summary_json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
