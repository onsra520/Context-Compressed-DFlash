#!/usr/bin/env python3
"""Run isolated repeated requests for one canonical mock prompt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ccdf.config import load_config
from ccdf.runtime.engine import RuntimeEngine
from ccdf.validation.quality import evaluate_complete_answer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yml")
    parser.add_argument("--condition", choices=("baseline", "dflash"), required=True)
    parser.add_argument("--prompt-index", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = load_config(args.config)
    prompt = str(config.require("benchmark.prompts")[args.prompt_index])
    max_new_tokens = int(config.require("runtime.max_new_tokens"))
    engine = RuntimeEngine(config, condition=args.condition)
    try:
        for _ in range(args.warmups):
            engine.generate(prompt)
        rows = []
        for repetition in range(args.repetitions):
            result = engine.generate(prompt)
            quality = evaluate_complete_answer(
                prompt_index=args.prompt_index,
                text=result.text,
                stop_reason=result.stop_reason,
                output_tokens=result.output_tokens,
                max_new_tokens=max_new_tokens,
            )
            rows.append(
                {
                    "condition": args.condition,
                    "prompt_index": args.prompt_index,
                    "repetition": repetition,
                    "generated_token_ids": result.generated_token_ids,
                    "output_tokens": result.output_tokens,
                    "stop_reason": result.stop_reason,
                    "quality_pass": quality.quality_pass,
                    "structural_pass": all(
                        row["structural_pass"] for row in result.dflash.structural_audit
                    ) if result.dflash is not None else None,
                }
            )
    finally:
        engine.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
