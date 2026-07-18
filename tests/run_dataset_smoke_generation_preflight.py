"""Short-output CUDA preflight for one full-context QMSum original prompt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ccdf.benchmark.dataset_smoke import _generation_prompt_chunks, _protocol_for
from ccdf.config import load_config
from ccdf.protocols.orchestrator import chunked_request_record
from ccdf.runtime.engine import RuntimeEngine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=("baseline", "dflash", "both"), default="both")
    parser.add_argument("--fixture-id")
    parser.add_argument("--max-new-tokens", type=int, default=8)
    parser.add_argument("--sdpa-kernel", choices=("math", "auto"))
    parser.add_argument("--context-chunk-size-tokens", type=int)
    parser.add_argument("--fixed-block-size", type=int)
    args = parser.parse_args()
    profile = load_config("config.yml").resolve_dataset_smoke_profile()
    settings, config = profile.settings, profile.config
    if args.sdpa_kernel is not None:
        config.data["runtime"]["sdpa_kernel"] = args.sdpa_kernel
    if args.context_chunk_size_tokens is not None:
        settings["generation"]["qmsum_context_chunk_size_tokens"] = args.context_chunk_size_tokens
    if args.fixed_block_size is not None:
        config.data["optimization"]["block_policy"]["fixed_block_size"] = args.fixed_block_size
    rows = [json.loads(line) for line in Path(settings["cohorts"]["qmsum"]).read_text().splitlines()]
    row = (
        next(value for value in rows if value["fixture_id"] == args.fixture_id)
        if args.fixture_id
        else min(rows, key=lambda value: value["truncation"]["original_words"])
    )
    prompt = _protocol_for(row, settings).render(row["prompt_parts"]["context"])
    item = {
        "fixture_id": row["fixture_id"],
        "dataset": "qmsum",
        "question": row["question"],
        "instruction": row["prompt_parts"]["instruction"],
        "original_context": row["prompt_parts"]["context"],
        "original_prompt": prompt,
    }
    results = {}
    lifecycles = {}
    conditions = ("baseline", "dflash") if args.condition == "both" else (args.condition,)
    for condition in conditions:
        engine = RuntimeEngine(config, condition=condition)
        try:
            lifecycle = []
            prompts, chunk_map = _generation_prompt_chunks(engine, item, "original", settings)
            record = chunked_request_record(
                condition=condition,
                prompt_kind="original",
                prompts=prompts,
                compression={"compression_latency_ms": 0.0},
                engine=engine,
                lifecycle=lifecycle,
                max_new_tokens=args.max_new_tokens,
                temperature=config.require("runtime.temperature"),
                dataset="qmsum",
                measured=True,
                chunk_map=chunk_map,
                merge_policy=settings["generation"]["qmsum_context_merge_policy"],
            )
            results[condition] = record
            lifecycles[condition] = lifecycle
        finally:
            engine.close()
    successful = all(value["success"] for value in results.values())
    print(json.dumps({
        "resolved_sdpa_kernel": config.require("runtime.sdpa_kernel"),
        "fixture_id": row["fixture_id"],
        "success": {key: value["success"] for key, value in results.items()},
        "errors": {key: value.get("error") for key, value in results.items()},
        "prompt_tokens": {key: value.get("result", {}).get("prompt_tokens") for key, value in results.items()},
        "generated_token_parity": successful and len(results) == 2 and (
            results["baseline"]["result"]["generated_token_ids"]
            == results["dflash"]["result"]["generated_token_ids"]
        ),
        "peak_reserved_bytes": {
            key: value.get("result", {}).get("memory", {}).get("peak_reserved_bytes") for key, value in results.items()
        },
        "determinism": {
            key: value.get("result", {}).get("runtime", {}).get("determinism") for key, value in results.items()
        },
        "lifecycle": lifecycles,
    }, indent=2))


if __name__ == "__main__":
    main()
