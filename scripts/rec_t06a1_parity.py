"""Run the frozen Rec-T06A token-level parity matrix on real local models."""

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


def generated(result):
    return result.output_token_ids[result.prompt_token_count :]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--modes", nargs="+", default=["block1", "reject_all", "oracle_draft", "normal"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lock = model_lock()
    tokenizer = load_target_tokenizer(Path(lock["target"]["path"]))
    target = load_target_model(Path(lock["target"]["path"]), device_map="cuda")
    drafter = load_drafter_model(Path(lock["drafter"]["path"]))
    report = {"max_new_tokens": args.max_new_tokens, "rows": []}
    for dataset in ("gsm8k", "qmsum"):
        rows = [json.loads(line) for line in Path(f"data/eval/{dataset}/{dataset}_n10.jsonl").read_text().splitlines()[: args.count]]
        for row in rows:
            prompt = render_prompt(PromptParts(**row["prompt_parts"]))
            baseline = generate_baseline(target, tokenizer, prompt, GenerationConfig(max_new_tokens=args.max_new_tokens))
            item = {"dataset": dataset, "fixture_id": row["fixture_id"], "baseline": generated(baseline), "modes": {}}
            for mode in args.modes:
                dflash_mode = "normal" if mode == "block1" else mode
                block_size = 1 if mode == "block1" else 16
                result = generate_dflash_r1(target, drafter, tokenizer, prompt, GenerationConfig(max_new_tokens=args.max_new_tokens, dflash_mode=dflash_mode, dflash_block_size=block_size))
                tokens = generated(result)
                item["modes"][mode] = {"tokens": tokens, "equal": tokens == item["baseline"], "stop_reason": result.stop_reason, "acceptance_lengths": result.acceptance_lengths, "verification_calls": result.verification_calls, "draft_tokens_proposed": result.draft_tokens_proposed, "cache_audit": result.cache_audit}
            report["rows"].append(item)
            print(f"{dataset} {row['fixture_id']} complete", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
