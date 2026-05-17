from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import load_config
from low_tier.drafter import QwenDFlashDrafter
from low_tier.engine import LowTierEngine
from runtime.vllm_adapter import VllmGenerationAdapter, VllmModelHandle, VllmVerificationAdapter
from tokenization.gemma import GemmaTokenizer


def write_trace_jsonl(path: str | Path, trace) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for item in trace:
            handle.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run HTFSD Low Tier generation")
    parser.add_argument("--config", required=True)
    parser.add_argument("--prompt")
    parser.add_argument("--max-new-tokens", type=int)
    parser.add_argument("--decoding", default=None, choices=["greedy", "sampling"])
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--debug-trace")
    return parser


def _build_engine(config) -> LowTierEngine:
    qwen_handle = VllmModelHandle.from_config(config.qwen_drafter)
    e2b_handle = VllmModelHandle.from_config(config.gemma_e2b)
    e2b_llm = e2b_handle.load()
    tokenizer = GemmaTokenizer(e2b_llm.get_tokenizer())
    drafter = QwenDFlashDrafter(VllmGenerationAdapter(qwen_handle))
    verifier = VllmVerificationAdapter(e2b_handle, e2b_llm.get_tokenizer())
    return LowTierEngine(
        drafter=drafter,
        verifier=verifier,
        tokenizer=tokenizer,
        execution_mode=config.runtime.execution_mode,
        default_draft_max_tokens=config.dflash.default_max_tokens,
        hard_draft_max_tokens=config.dflash.hard_max_tokens,
    )


def run_single_prompt(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    decoding = args.decoding or config.decoding.default
    if decoding == "sampling":
        print("sampling mode is experimental and not used for correctness metrics")
    engine = _build_engine(config)
    result = engine.generate(
        args.prompt,
        max_new_tokens=args.max_new_tokens or config.generation.max_new_tokens,
        decoding="greedy" if decoding == "sampling" else decoding,
        stop_on_eos=config.generation.stop_on_eos,
        debug_trace=bool(args.debug_trace),
    )
    print(result.text)
    print(json.dumps(result.metrics.to_dict(), ensure_ascii=False, indent=2))
    if args.debug_trace:
        write_trace_jsonl(args.debug_trace, result.trace)
    return 0


def run_prompt_loop(args: argparse.Namespace) -> int:
    while True:
        prompt = input("htfsd> ").strip()
        if prompt in {"exit", "quit"}:
            return 0
        if not prompt:
            continue
        args.prompt = prompt
        run_single_prompt(args)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.prompt:
        return run_single_prompt(args)
    return run_prompt_loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
