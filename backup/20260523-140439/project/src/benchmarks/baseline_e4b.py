"""Gemma E4B autoregressive baseline benchmark runner."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.fixtures import load_prompt_fixtures
from benchmarks.rows import benchmark_error_row
from metrics.timers import timer_ms


def baseline_row(  # pylint: disable=too-many-arguments
    *,
    prompt_id: str,
    prompt_tokens: int,
    generated_tokens: int,
    total_ms: float,
    output_text: str,
    peak_vram_mb: float | None = None,
) -> dict:
    """Build a successful Gemma E4B baseline benchmark row."""

    return {
        "prompt_id": prompt_id,
        "prompt_tokens": prompt_tokens,
        "generated_tokens": generated_tokens,
        "total_ms": total_ms,
        "tokens_per_second": generated_tokens / (total_ms / 1000.0) if total_ms > 0 else 0.0,
        "latency_per_token_ms": total_ms / generated_tokens if generated_tokens else 0.0,
        "peak_vram_mb": peak_vram_mb,
        "output_text": output_text,
    }


def run_e4b_baseline(
    *,
    generation_adapter,
    tokenizer,
    fixture_path: str | Path,
    output_path: str | Path,
) -> None:
    """Run Gemma E4B baseline generation over a prompt fixture JSONL file."""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("", encoding="utf-8")
    with output.open("a", encoding="utf-8") as handle:
        for fixture in load_prompt_fixtures(fixture_path):
            try:
                prompt_token_ids = tokenizer.encode(fixture["prompt"], add_special_tokens=False)
                with timer_ms() as elapsed:
                    text = generation_adapter.generate_text(
                        fixture["prompt"],
                        max_tokens=fixture["max_new_tokens"],
                        temperature=0.0,
                        top_p=1.0,
                    )
                generated_token_ids = tokenizer.encode(text, add_special_tokens=False)
                row = baseline_row(
                    prompt_id=fixture["id"],
                    prompt_tokens=len(prompt_token_ids),
                    generated_tokens=len(generated_token_ids),
                    total_ms=elapsed.elapsed_ms,
                    output_text=text,
                )
                row["status"] = "ok"
                row["error"] = None
            except Exception as exc:  # pylint: disable=broad-exception-caught
                # Benchmarks record per-prompt failures and continue the fixture run.
                row = benchmark_error_row(prompt_id=fixture["id"], error=exc)
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
