from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from htfsd.benchmarks.fixtures import load_prompt_fixtures
from htfsd.config import validate_benchmark_decoding


def write_benchmark_row(path: str | Path, row: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_low_tier_benchmark(
    *,
    engine,
    fixture_path: str | Path,
    output_path: str | Path,
    decoding: str = "greedy",
) -> None:
    validate_benchmark_decoding(decoding)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("", encoding="utf-8")
    for fixture in load_prompt_fixtures(fixture_path):
        try:
            result = engine.generate(
                fixture["prompt"],
                max_new_tokens=fixture["max_new_tokens"],
                decoding="greedy",
            )
            row = {
                "prompt_id": fixture["id"],
                "status": "ok",
                "error": None,
                "prompt": fixture["prompt"],
                "metrics": result.metrics.to_dict(),
                "output_text": result.text,
            }
        except Exception as exc:
            row = {
                "prompt_id": fixture["id"],
                "status": "error",
                "error": str(exc),
                "prompt": fixture["prompt"],
            }
        write_benchmark_row(output_path, row)
