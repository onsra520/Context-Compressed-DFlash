#!/usr/bin/env python3
"""Validation-only smoke runner plus deterministic/parity result helpers."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
from typing import Any


PROMPT = "Giải thích ngắn gọn vì sao 1 + 1 = 2. Trả lời trong tối đa hai câu."


def _first_difference(expected: list[int], actual: list[int]) -> dict[str, int | None]:
    for index, (left, right) in enumerate(zip(expected, actual)):
        if left != right:
            return {"token_index": index, "expected_token_id": left, "actual_token_id": right}
    index = min(len(expected), len(actual))
    return {
        "token_index": index if len(expected) != len(actual) else None,
        "expected_token_id": expected[index] if index < len(expected) else None,
        "actual_token_id": actual[index] if index < len(actual) else None,
    }


def _determinism(rows: list[dict[str, Any]], prompt_count: int, deterministic: bool) -> dict[str, Any]:
    by_condition: dict[str, Any] = {}
    for condition in ("baseline", "dflash"):
        cases = []
        for prompt_index in range(prompt_count):
            selected = [row for row in rows if row["condition"] == condition and row["prompt_index"] == prompt_index]
            reference = selected[0]["result"]
            texts = [row["result"]["text"] for row in selected]
            sequences = [tuple(row["result"]["generated_token_ids"]) for row in selected]
            counts = [int(row["result"]["output_tokens"]) for row in selected]
            divergences = []
            for row in selected[1:]:
                current = row["result"]
                if current["generated_token_ids"] != reference["generated_token_ids"]:
                    divergences.append({
                        "sequence": row["sequence"], "order_index": row["order_index"],
                        "repetition": row["repetition"],
                        **_first_difference(reference["generated_token_ids"], current["generated_token_ids"]),
                        "expected_decoded_output": reference["text"], "actual_decoded_output": current["text"],
                    })
            uniqueness = {
                "unique_text_count": len(set(texts)),
                "unique_token_sequence_count": len(set(sequences)),
                "unique_output_token_count": len(set(counts)),
            }
            passed = not deterministic or all(value == 1 for value in uniqueness.values())
            cases.append({
                "prompt_index": prompt_index, "repetitions": len(selected), **uniqueness,
                "output_token_count_distribution": dict(sorted(Counter(counts).items())),
                "pass": passed, "reference_token_ids": reference["generated_token_ids"],
                "divergences": divergences,
            })
        by_condition[condition] = {"pass": all(case["pass"] for case in cases), "cases": cases}
    return {"deterministic": deterministic, "by_condition": by_condition, "pass": all(item["pass"] for item in by_condition.values())}


def _parity(rows: list[dict[str, Any]], prompt_count: int) -> dict[str, Any]:
    cases = []
    for prompt_index in range(prompt_count):
        baseline = {(row["order_index"], row["repetition"]): row for row in rows if row["condition"] == "baseline" and row["prompt_index"] == prompt_index}
        dflash = {(row["order_index"], row["repetition"]): row for row in rows if row["condition"] == "dflash" and row["prompt_index"] == prompt_index}
        differences = []
        for key in sorted(set(baseline) | set(dflash)):
            left, right = baseline.get(key), dflash.get(key)
            if left is None or right is None:
                differences.append({"order_index": key[0], "repetition": key[1], "missing_condition": "baseline" if left is None else "dflash"})
            elif left["result"]["generated_token_ids"] != right["result"]["generated_token_ids"]:
                differences.append({
                    "order_index": key[0], "repetition": key[1],
                    **_first_difference(left["result"]["generated_token_ids"], right["result"]["generated_token_ids"]),
                })
        cases.append({"prompt_index": prompt_index, "compared_runs": len(baseline), "pass": not differences and len(baseline) == len(dflash) == 10, "differences": differences})
    return {"pass": all(case["pass"] for case in cases), "cases": cases}


def _reference_covered(prompts: list[str], prompt_index: int, covered: set[str]) -> bool:
    return prompts[prompt_index] in covered


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yml")
    parser.add_argument("--max-new-tokens", type=int, default=32)
    parser.add_argument("--artifact", default="artifacts/benchmark/short_prompt_smoke.json")
    args = parser.parse_args()
    os.environ.setdefault("PROJECT_ROOT", str(Path.cwd()))
    from ccdf.runtime.engine import RuntimeEngine

    results = {}
    for condition in ("baseline", "dflash"):
        engine = RuntimeEngine.from_config(args.config, condition=condition)
        try:
            results[condition] = engine.generate(PROMPT, max_new_tokens=args.max_new_tokens, temperature=0.0).to_dict()
        finally:
            engine.close()
    artifact = Path(args.artifact)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
