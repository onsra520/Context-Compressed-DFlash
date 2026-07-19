#!/usr/bin/env python3
"""Diagnostic-only fixed-block-size ablation for one compressed mock prompt."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from ccdf.config import Rec2Config, load_config
from ccdf.runtime.engine import RuntimeEngine
from ccdf.validation.quality import evaluate_complete_answer


def _read_prompt(path: Path, sample_id: str) -> str:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    matches = [row for row in rows if row["sample_id"] == sample_id and row["status"] == "success"]
    if len(matches) != 1:
        raise ValueError(f"expected one successful compression row for {sample_id}")
    return str(matches[0]["compressed_prompt"])


def _config_with_block_size(config: Rec2Config, block_size: int) -> Rec2Config:
    data = copy.deepcopy(config.data)
    data["optimization"]["block_policy"]["mode"] = "fixed"
    data["optimization"]["block_policy"]["fixed_block_size"] = block_size
    data["optimization"]["full_structural_audit"] = True
    return Rec2Config(path=config.path, root=config.root, data=data)


def _run(config: Rec2Config, condition: str, prompt: str, prompt_index: int) -> dict:
    engine = RuntimeEngine(config, condition=condition)
    try:
        if config.get("runtime.target_attention_override"):
            target = engine.model if condition == "baseline" else engine.target
            target.config._attn_implementation = str(
                config.get("runtime.target_attention_override")
            )
        result = engine.generate(prompt, max_new_tokens=int(config.require("benchmark.smoke_max_new_tokens")))
    finally:
        engine.close()
    quality = evaluate_complete_answer(
        prompt_index=prompt_index,
        text=result.text,
        stop_reason=result.stop_reason,
        output_tokens=result.output_tokens,
        max_new_tokens=int(config.require("benchmark.smoke_max_new_tokens")),
    )
    return {
        "generated_token_ids": result.generated_token_ids,
        "decoded_output": result.text,
        "quality_pass": quality.quality_pass,
        "decode_tok_s": result.decode_tok_s,
        "warm_request_tok_s": result.warm_request_tok_s,
        "peak_reserved_bytes": result.memory.peak_reserved_bytes,
        "acceptance_lengths": result.dflash.acceptance_lengths if result.dflash else None,
        "structural_audit": result.dflash.structural_audit if result.dflash else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yml")
    parser.add_argument("--compression", type=Path, required=True)
    parser.add_argument("--sample-id", default="mock-04")
    parser.add_argument("--prompt-index", type=int, default=3)
    parser.add_argument("--block-size", type=int, action="append", required=True)
    parser.add_argument("--target-attention-override")
    parser.add_argument("--load-attention-backend")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    if args.load_attention_backend:
        config.data["runtime"]["attention_backend"] = args.load_attention_backend
    if args.target_attention_override:
        config.data["runtime"]["target_attention_override"] = args.target_attention_override
    prompt = _read_prompt(args.compression, args.sample_id)
    baseline = _run(config, "baseline", prompt, args.prompt_index)
    rows = []
    for block_size in args.block_size:
        dflash = _run(_config_with_block_size(config, block_size), "dflash", prompt, args.prompt_index)
        mismatch = next(
            (
                index
                for index, (left, right) in enumerate(
                    zip(baseline["generated_token_ids"], dflash["generated_token_ids"])
                )
                if left != right
            ),
            min(len(baseline["generated_token_ids"]), len(dflash["generated_token_ids"]))
            if len(baseline["generated_token_ids"]) != len(dflash["generated_token_ids"])
            else None,
        )
        rows.append(
            {
                "block_size": block_size,
                "exact_parity": baseline["generated_token_ids"] == dflash["generated_token_ids"],
                "first_mismatch_index": mismatch,
                "dflash": dflash,
            }
        )
    payload = {
        "schema": "ccdf.stage2.block-size-ablation.v1",
        "scope": "diagnostic_only_no_production_policy_change",
        "target_attention_override": args.target_attention_override,
        "load_attention_backend": args.load_attention_backend,
        "sample_id": args.sample_id,
        "prompt": prompt,
        "baseline": baseline,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
