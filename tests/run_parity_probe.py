#!/usr/bin/env python3
"""Outside-timing token-parity probe for selected canonical prompts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yml")
    parser.add_argument("--prompt-indices", default="0,2,7,8,9")
    parser.add_argument("--artifact", default="docs/artifacts/diagnostics/parity_probe.json")
    args = parser.parse_args()

    from ccdf.config import load_config
    from ccdf.runtime.engine import RuntimeEngine
    from ccdf.validation.quality import evaluate_complete_answer

    config = load_config(args.config)
    prompts = list(config.require("benchmark.prompts"))
    indices = [int(value) for value in args.prompt_indices.split(",")]
    results = {}
    for condition in ("baseline", "dflash"):
        engine = RuntimeEngine(config, condition=condition)
        try:
            results[condition] = {
                str(index): engine.generate(prompts[index], max_new_tokens=256).to_dict()
                for index in indices
            }
        finally:
            engine.close()
    cases = []
    for index in indices:
        baseline = results["baseline"][str(index)]
        dflash = results["dflash"][str(index)]
        cases.append(
            {
                "prompt_index": index,
                "pass": baseline["generated_token_ids"] == dflash["generated_token_ids"],
                "baseline_text": baseline["text"],
                "dflash_text": dflash["text"],
                "baseline_quality": evaluate_complete_answer(prompt_index=index, text=baseline["text"], stop_reason=baseline["stop_reason"], output_tokens=baseline["output_tokens"], max_new_tokens=256).to_dict(),
                "dflash_quality": evaluate_complete_answer(prompt_index=index, text=dflash["text"], stop_reason=dflash["stop_reason"], output_tokens=dflash["output_tokens"], max_new_tokens=256).to_dict(),
            }
        )
    payload = {"excluded_from_canonical_timing": True, "pass": all(case["pass"] for case in cases), "cases": cases}
    destination = Path(args.artifact)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": payload["pass"], "cases": [{"prompt_index": case["prompt_index"], "pass": case["pass"]} for case in cases]}, indent=2))
    return 0 if payload["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
