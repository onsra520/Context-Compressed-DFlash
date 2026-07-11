"""Small real-model smoke for canonical Rec-T06A1 generation modes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ccdf.dflash.loader import load_drafter_model
from ccdf.inference.baseline_ar import generate_baseline
from ccdf.inference.dflash_runtime import generate_dflash_r1
from ccdf.inference.model_registry import model_lock
from ccdf.inference.schemas import GenerationConfig
from ccdf.inference.target_loader import load_target_model, load_target_tokenizer
from ccdf.prompts.renderer import render_prompt
from ccdf.prompts.schemas import PromptParts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="gsm8k")
    parser.add_argument("--fixture-index", type=int, default=0)
    parser.add_argument("--max-new-tokens", type=int, default=8)
    parser.add_argument("--mode", default="normal")
    parser.add_argument("--block-size", type=int, default=None)
    args = parser.parse_args()
    row = json.loads(Path(f"data/eval/{args.dataset}/{args.dataset}_n10.jsonl").read_text().splitlines()[args.fixture_index])
    prompt = render_prompt(PromptParts(**row["prompt_parts"]))
    lock = model_lock()
    tokenizer = load_target_tokenizer(Path(lock["target"]["path"]))
    target = load_target_model(Path(lock["target"]["path"]), device_map="cuda")
    drafter = load_drafter_model(Path(lock["drafter"]["path"]))
    base = generate_baseline(target, tokenizer, prompt, GenerationConfig(max_new_tokens=args.max_new_tokens))
    dflash = generate_dflash_r1(target, drafter, tokenizer, prompt, GenerationConfig(max_new_tokens=args.max_new_tokens, dflash_mode=args.mode, dflash_block_size=args.block_size))
    print(json.dumps({"fixture_id": row["fixture_id"], "baseline": base.output_token_ids[base.prompt_token_count:], "dflash": dflash.output_token_ids[dflash.prompt_token_count:], "equal": base.output_token_ids == dflash.output_token_ids, "acceptance_lengths": dflash.acceptance_lengths, "cache_audit": dflash.cache_audit}))


if __name__ == "__main__":
    main()
