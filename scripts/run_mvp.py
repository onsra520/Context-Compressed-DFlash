from __future__ import annotations

import argparse
import importlib.util
import json
import hashlib
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone

import torch

from ccdf.config import load_config
from ccdf.dflash.generate import dflash_generate
from ccdf.dflash.loader import load_draft, load_tokenizer


PROMPTS = [
    "Answer with one word: ready.",
    "Compute 12 + 30. Answer with only the number.",
    "Name the color of a clear daytime sky in one word.",
    "Write the next number: 2, 4, 6, 8,",
    "Say OK if you can read this.",
]


@dataclass
class SmokeConfig:
    target_path: Path
    draft_path: Path
    tokenizer_path: Path
    device: str
    block_size: int
    max_new_tokens: int
    temperature: float


@dataclass
class VramSnapshot:
    label: str
    allocated_gib: float
    reserved_gib: float
    free_gib: float
    total_gib: float


@dataclass
class PromptMetrics:
    prompt_id: int
    prompt_text: str
    input_tokens: int
    output_tokens: int
    generation_time_s: float
    tok_per_s: float
    acceptance_lengths: list[int]
    tau_mean: float
    vram_after: VramSnapshot


def _read_config(path: str | Path) -> SmokeConfig:
    config = load_config(path)
    model_cfg = config.get("model", {})
    runtime_cfg = config.get("runtime", {})
    benchmark_cfg = config.get("benchmark", {})

    return SmokeConfig(
        target_path=Path(model_cfg.get("target_id", "models/Qwen3-4B")),
        draft_path=Path(model_cfg.get("draft_id", "models/Qwen3-4B-DFlash-b16")),
        tokenizer_path=Path(model_cfg.get("tokenizer_id", "models/Qwen3-4B")),
        device=str(runtime_cfg.get("device", "cuda:0")),
        block_size=int(benchmark_cfg.get("block_size", 16)),
        max_new_tokens=min(int(benchmark_cfg.get("max_new_tokens", 16)), 32),
        temperature=float(benchmark_cfg.get("temperature", 0.0)),
    )


def _require_cuda() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the DFlash-R1 smoke benchmark")


def _attention_backend() -> str:
    if importlib.util.find_spec("flash_attn") is None:
        print("Backend warning: flash_attn not installed; using torch.sdpa fallback.")
        return "sdpa"
    return "flash_attention_2"


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _vram(label: str) -> VramSnapshot:
    torch.cuda.synchronize()
    free, total = torch.cuda.mem_get_info()
    snapshot = VramSnapshot(
        label=label,
        allocated_gib=torch.cuda.memory_allocated() / 1024**3,
        reserved_gib=torch.cuda.memory_reserved() / 1024**3,
        free_gib=free / 1024**3,
        total_gib=total / 1024**3,
    )
    print(
        f"VRAM {label}: allocated={snapshot.allocated_gib:.2f}GiB "
        f"reserved={snapshot.reserved_gib:.2f}GiB free={snapshot.free_gib:.2f}GiB "
        f"total={snapshot.total_gib:.2f}GiB"
    )
    return snapshot


def _load_target_4bit(target_path: Path, device: str, attn_implementation: str):
    if importlib.util.find_spec("bitsandbytes") is None:
        raise RuntimeError("bitsandbytes is required for 4-bit NF4 target loading")

    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    return AutoModelForCausalLM.from_pretrained(
        str(target_path),
        attn_implementation=attn_implementation,
        quantization_config=quantization_config,
        device_map={"": device},
        dtype=torch.bfloat16,
    ).eval()


def _format_prompt(tokenizer, text: str) -> torch.Tensor:
    prompt = tokenizer.apply_chat_template(
        [{"role": "user", "content": text}],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    return tokenizer.encode(prompt, return_tensors="pt")


def _run_prompt(
    prompt_id: int,
    prompt: str,
    *,
    tokenizer,
    target,
    draft,
    config: SmokeConfig,
) -> PromptMetrics:
    input_ids = _format_prompt(tokenizer, prompt).to(config.device)
    stop_token_ids = [tokenizer.eos_token_id] if tokenizer.eos_token_id is not None else None

    torch.cuda.synchronize()
    started = time.perf_counter()
    result = dflash_generate(
        draft,
        target=target,
        input_ids=input_ids,
        max_new_tokens=config.max_new_tokens,
        stop_token_ids=stop_token_ids,
        temperature=config.temperature,
        block_size=config.block_size,
        return_stats=True,
    )
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started

    output_tokens = int(result.num_output_tokens)
    tok_per_s = output_tokens / elapsed if elapsed > 0 else 0.0
    acceptance_lengths = list(result.acceptance_lengths)
    tau_mean = statistics.mean(acceptance_lengths) if acceptance_lengths else 0.0
    vram_after = _vram(f"after prompt {prompt_id}")

    print(
        f"prompt_id={prompt_id} input_tokens={int(result.num_input_tokens)} "
        f"output_tokens={output_tokens} generation_time_s={elapsed:.4f} "
        f"tok/s={tok_per_s:.2f} acceptance_lengths={acceptance_lengths} "
        f"tau_mean={tau_mean:.2f}"
    )
    return PromptMetrics(
        prompt_id=prompt_id,
        prompt_text=prompt,
        input_tokens=int(result.num_input_tokens),
        output_tokens=output_tokens,
        generation_time_s=elapsed,
        tok_per_s=tok_per_s,
        acceptance_lengths=acceptance_lengths,
        tau_mean=tau_mean,
        vram_after=vram_after,
    )


def _print_summary(metrics: list[PromptMetrics], vram_snapshots: list[VramSnapshot]) -> None:
    avg_tok_s = statistics.mean(item.tok_per_s for item in metrics) if metrics else 0.0
    avg_tau = statistics.mean(item.tau_mean for item in metrics) if metrics else 0.0
    max_allocated = max(snapshot.allocated_gib for snapshot in vram_snapshots)
    max_reserved = max(snapshot.reserved_gib for snapshot in vram_snapshots)

    print("Summary:")
    print(f"average tok/s: {avg_tok_s:.2f}")
    print(f"average tau_mean: {avg_tau:.2f}")
    print(f"max VRAM allocated: {max_allocated:.2f}GiB")
    print(f"max VRAM reserved: {max_reserved:.2f}GiB")
    print("Final status: PASS")


def _write_jsonl(
    output_path: Path,
    *,
    condition: str,
    backend_warning: str,
    config: SmokeConfig,
    metrics: list[PromptMetrics],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for metric in metrics:
            row = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "condition": condition,
                "prompt_id": metric.prompt_id,
                "prompt_hash": _prompt_hash(metric.prompt_text),
                "input_tokens": metric.input_tokens,
                "output_tokens": metric.output_tokens,
                "generation_time_s": metric.generation_time_s,
                "tok_per_sec": metric.tok_per_s,
                "acceptance_lengths": metric.acceptance_lengths,
                "tau_mean": metric.tau_mean,
                "max_new_tokens": config.max_new_tokens,
                "block_size": config.block_size,
                "device": config.device,
                "target_path": str(config.target_path),
                "draft_path": str(config.draft_path),
                "tokenizer_path": str(config.tokenizer_path),
                "backend_warning": backend_warning,
                "vram_allocated_gib": metric.vram_after.allocated_gib,
                "vram_reserved_gib": metric.vram_after.reserved_gib,
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DFlash-R1 baseline smoke benchmark")
    parser.add_argument("--config", default="config.yml")
    parser.add_argument("--condition", default="DFlash-R1")
    parser.add_argument("--n", type=int, default=3)
    parser.add_argument("--output", default="results/dflash_r1_smoke.jsonl")
    args = parser.parse_args()

    if args.condition != "DFlash-R1":
        raise SystemExit(f"Only DFlash-R1 is supported by this smoke runner, got {args.condition}")

    config = _read_config(args.config)
    n_prompts = max(1, args.n)
    prompts = [PROMPTS[i % len(PROMPTS)] for i in range(n_prompts)]

    print("DFlash-R1 smoke benchmark")
    print("Compression: none")
    print(f"Target model path: {config.target_path}")
    print(f"Draft model path: {config.draft_path}")
    print(f"Tokenizer path: {config.tokenizer_path}")
    print(f"Device: {config.device}")
    print(f"Block size: {config.block_size}")
    print(f"Max new tokens: {config.max_new_tokens}")
    print(f"Prompt count: {len(prompts)}")

    try:
        _require_cuda()
        attn_implementation = _attention_backend()
        backend_warning = (
            "flash_attn not installed; using torch.sdpa fallback."
            if attn_implementation == "sdpa"
            else "flash_attn installed; using flash_attention_2."
        )
        vram_snapshots = [_vram("before load")]
        tokenizer = load_tokenizer(str(config.tokenizer_path), trust_remote_code=True)
        target = _load_target_4bit(config.target_path, config.device, attn_implementation)
        vram_snapshots.append(_vram("after target load"))
        draft = load_draft(
            str(config.draft_path),
            device=config.device,
            attn_implementation=attn_implementation,
            trust_remote_code=True,
            dtype=torch.bfloat16,
        )
        vram_snapshots.append(_vram("after draft load"))

        metrics = []
        for idx, prompt in enumerate(prompts, start=1):
            metric = _run_prompt(
                idx,
                prompt,
                tokenizer=tokenizer,
                target=target,
                draft=draft,
                config=config,
            )
            metrics.append(metric)
            vram_snapshots.append(metric.vram_after)

        _write_jsonl(
            Path(args.output),
            condition=args.condition,
            backend_warning=backend_warning,
            config=config,
            metrics=metrics,
        )
        _print_summary(metrics, vram_snapshots)
    except Exception as exc:
        print(f"Final status: FAIL")
        print(f"Failure: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
