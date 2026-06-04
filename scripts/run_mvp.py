from __future__ import annotations

import argparse
import importlib.util
import json
import hashlib
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone

import torch

from ccdf.config import load_config
from ccdf.compression.llmlingua import LLMLinguaCompressor
from ccdf.dflash.generate import dflash_generate
from ccdf.dflash.loader import load_draft, load_tokenizer


PROMPTS = [
    "Answer with one word: ready.",
    "Compute 12 + 30. Answer with only the number.",
    "Name the color of a clear daytime sky in one word.",
    "Write the next number: 2, 4, 6, 8,",
    "Say OK if you can read this.",
]

CC_SMOKE_CONTEXT = (
    "The city library bought 48 new math books and 16 science books. "
    "A local donor later added 12 more math books. "
    "The building also has old newspapers, chairs, posters, and unrelated historical notes. "
    "Only the details needed by the question should be used."
)


@dataclass
class SmokeConfig:
    target_path: Path
    draft_path: Path
    tokenizer_path: Path
    device: str
    block_size: int
    max_new_tokens: int
    temperature: float
    raw_config: dict


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
    t_prefill_ms: float = 0.0
    t_prefill_mode: str = "not_measured"
    prefill_vram_allocated_gib: float | None = None
    prefill_vram_reserved_gib: float | None = None
    compression_info: dict = field(default_factory=dict)


@dataclass
class PromptItem:
    prompt_id: int
    text: str
    context: str | None = None
    question: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class PrefillMeasurement:
    elapsed_ms: float
    mode: str
    vram_allocated_gib: float | None
    vram_reserved_gib: float | None


def _read_config(path: str | Path, *, max_new_tokens_override: int | None = None) -> SmokeConfig:
    config = load_config(path)
    model_cfg = config.get("model", {})
    runtime_cfg = config.get("runtime", {})
    benchmark_cfg = config.get("benchmark", {})

    configured_max_new_tokens = min(int(benchmark_cfg.get("max_new_tokens", 16)), 32)
    max_new_tokens = (
        max(1, int(max_new_tokens_override))
        if max_new_tokens_override is not None
        else configured_max_new_tokens
    )

    return SmokeConfig(
        target_path=Path(model_cfg.get("target_id", "models/Qwen3-4B")),
        draft_path=Path(model_cfg.get("draft_id", "models/Qwen3-4B-DFlash-b16")),
        tokenizer_path=Path(model_cfg.get("tokenizer_id", "models/Qwen3-4B")),
        device=str(runtime_cfg.get("device", "cuda:0")),
        block_size=int(benchmark_cfg.get("block_size", 16)),
        max_new_tokens=max_new_tokens,
        temperature=float(benchmark_cfg.get("temperature", 0.0)),
        raw_config=config,
    )


def _condition_keep_rate(condition: str, default_keep_rate: float) -> float | None:
    if condition in {"Baseline-AR", "DFlash-R1"}:
        return None
    if condition in {"CC-LLM-R2", "LLMLingua-AR-R2"}:
        return 0.5
    if condition in {"CC-LLM-R3", "LLMLingua-AR-R3"}:
        return 0.33
    raise ValueError(f"Unsupported condition: {condition}")


def _is_ar_condition(condition: str) -> bool:
    return condition in {"Baseline-AR", "LLMLingua-AR-R2", "LLMLingua-AR-R3"}


def _prepare_cc_prompt(
    question: str,
    compressor: LLMLinguaCompressor,
    keep_rate: float,
    context: str = CC_SMOKE_CONTEXT,
) -> tuple[str, dict]:
    merged_prompt, info = compressor.compress(context=context, question=question, keep_rate=keep_rate)
    compression_info = {
        "t_compress_ms": info["t_compress_ms"],
        "R_actual": info["R_actual"],
        "N_original": info["N_original"],
        "N_compressed": info["N_compressed"],
        "keep_rate": info.get("keep_rate", keep_rate),
        "compressor_model": compressor.model_name,
        "question_preserved": question in merged_prompt,
    }
    return merged_prompt, compression_info


def _load_fixture_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    if not rows:
        raise ValueError(f"fixture contains no rows: {path}")
    return rows


def _prompt_from_fixture_row(row: dict) -> str:
    return f"{row['context']}\n\n{row['question']}"


def _fixture_metadata(row: dict) -> dict:
    return {
        "prompt_source": "fixture",
        "fixture_id": row["id"],
        "domain": row["domain"],
        "expected_answer": row["expected_answer"],
        "evidence": row["evidence"],
        "approximate_context_words": row["approximate_context_words"],
    }


def _select_prompt_items(
    *,
    prompt_source: str,
    n_prompts: int,
    fixture_path: Path | None,
) -> list[PromptItem]:
    if prompt_source == "smoke":
        return [
            PromptItem(prompt_id=index + 1, text=PROMPTS[index % len(PROMPTS)])
            for index in range(n_prompts)
        ]
    if prompt_source != "fixture":
        raise ValueError(f"Unsupported prompt source: {prompt_source}")
    if fixture_path is None:
        raise ValueError("--fixture is required when --prompt-source=fixture")

    rows = _load_fixture_rows(fixture_path)
    items = []
    for index in range(n_prompts):
        row = rows[index % len(rows)]
        items.append(
            PromptItem(
                prompt_id=index + 1,
                text=_prompt_from_fixture_row(row),
                context=row["context"],
                question=row["question"],
                metadata=_fixture_metadata(row),
            )
        )
    return items


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


def _uses_cuda(device: str) -> bool:
    return str(device).startswith("cuda") and torch.cuda.is_available()


def _measure_target_prefill(target, input_ids: torch.Tensor, *, device: str) -> PrefillMeasurement:
    uses_cuda = _uses_cuda(device)
    if uses_cuda:
        torch.cuda.synchronize()

    started = time.perf_counter()
    with torch.inference_mode():
        target(
            input_ids=input_ids,
            attention_mask=torch.ones_like(input_ids),
            use_cache=True,
        )
    if uses_cuda:
        torch.cuda.synchronize()
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    if not uses_cuda:
        return PrefillMeasurement(
            elapsed_ms=elapsed_ms,
            mode="cpu_timer",
            vram_allocated_gib=None,
            vram_reserved_gib=None,
        )

    return PrefillMeasurement(
        elapsed_ms=elapsed_ms,
        mode="cuda_synchronized",
        vram_allocated_gib=torch.cuda.memory_allocated() / 1024**3,
        vram_reserved_gib=torch.cuda.memory_reserved() / 1024**3,
    )


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


def _generated_text_info(
    tokenizer,
    output_ids,
    *,
    input_tokens: int,
    store_generated_text: bool,
) -> dict:
    if not store_generated_text:
        return {}
    if hasattr(output_ids, "detach"):
        generated_token_ids = output_ids[0, input_tokens:].detach().cpu().tolist()
    else:
        generated_token_ids = output_ids[0][input_tokens:]
    return {
        "generated_text": tokenizer.decode(generated_token_ids, skip_special_tokens=True),
        "generated_token_count": len(generated_token_ids),
    }


def _run_prompt(
    prompt_id: int,
    prompt: str,
    *,
    tokenizer,
    target,
    draft,
    config: SmokeConfig,
    compression_info: dict | None = None,
    store_generated_text: bool = False,
) -> PromptMetrics:
    input_ids = _format_prompt(tokenizer, prompt).to(config.device)
    prefill = _measure_target_prefill(target, input_ids, device=config.device)
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
    row_info = compression_info or {}
    row_info.update(
        _generated_text_info(
            tokenizer,
            result.output_ids,
            input_tokens=int(result.num_input_tokens),
            store_generated_text=store_generated_text,
        )
    )

    print(
        f"prompt_id={prompt_id} input_tokens={int(result.num_input_tokens)} "
        f"output_tokens={output_tokens} generation_time_s={elapsed:.4f} "
        f"tok/s={tok_per_s:.2f} acceptance_lengths={acceptance_lengths} "
        f"tau_mean={tau_mean:.2f} t_prefill_ms={prefill.elapsed_ms:.2f}"
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
        t_prefill_ms=prefill.elapsed_ms,
        t_prefill_mode=prefill.mode,
        prefill_vram_allocated_gib=prefill.vram_allocated_gib,
        prefill_vram_reserved_gib=prefill.vram_reserved_gib,
        compression_info=row_info,
    )


def _run_ar_prompt(
    prompt_id: int,
    prompt: str,
    *,
    tokenizer,
    target,
    config: SmokeConfig,
    compression_info: dict | None = None,
    store_generated_text: bool = False,
) -> PromptMetrics:
    input_ids = _format_prompt(tokenizer, prompt).to(config.device)
    prefill = _measure_target_prefill(target, input_ids, device=config.device)
    generate_kwargs = {
        "input_ids": input_ids,
        "attention_mask": torch.ones_like(input_ids),
        "max_new_tokens": config.max_new_tokens,
        "do_sample": config.temperature > 0,
        "pad_token_id": tokenizer.eos_token_id,
        "eos_token_id": tokenizer.eos_token_id,
    }
    if config.temperature > 0:
        generate_kwargs["temperature"] = config.temperature

    torch.cuda.synchronize()
    started = time.perf_counter()
    with torch.inference_mode():
        output_ids = target.generate(**generate_kwargs)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started

    input_tokens = int(input_ids.shape[-1])
    output_tokens = int(output_ids.shape[-1] - input_ids.shape[-1])
    tok_per_s = output_tokens / elapsed if elapsed > 0 else 0.0
    vram_after = _vram(f"after prompt {prompt_id}")
    row_info = compression_info or {}
    row_info.update(
        _generated_text_info(
            tokenizer,
            output_ids,
            input_tokens=input_tokens,
            store_generated_text=store_generated_text,
        )
    )

    print(
        f"prompt_id={prompt_id} input_tokens={input_tokens} "
        f"output_tokens={output_tokens} generation_time_s={elapsed:.4f} "
        f"tok/s={tok_per_s:.2f} acceptance_lengths=[] tau_mean=0.00 "
        f"t_prefill_ms={prefill.elapsed_ms:.2f}"
    )
    return PromptMetrics(
        prompt_id=prompt_id,
        prompt_text=prompt,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        generation_time_s=elapsed,
        tok_per_s=tok_per_s,
        acceptance_lengths=[],
        tau_mean=0.0,
        vram_after=vram_after,
        t_prefill_ms=prefill.elapsed_ms,
        t_prefill_mode=prefill.mode,
        prefill_vram_allocated_gib=prefill.vram_allocated_gib,
        prefill_vram_reserved_gib=prefill.vram_reserved_gib,
        compression_info=row_info,
    )


def _print_summary(metrics: list[PromptMetrics], vram_snapshots: list[VramSnapshot]) -> None:
    avg_tok_s = statistics.mean(item.tok_per_s for item in metrics) if metrics else 0.0
    avg_tau = statistics.mean(item.tau_mean for item in metrics) if metrics else 0.0
    max_allocated = max(snapshot.allocated_gib for snapshot in vram_snapshots)
    max_reserved = max(snapshot.reserved_gib for snapshot in vram_snapshots)
    compression_metrics = [
        item.compression_info
        for item in metrics
        if "t_compress_ms" in item.compression_info and "R_actual" in item.compression_info
    ]

    print("Summary:")
    print(f"average tok/s: {avg_tok_s:.2f}")
    print(f"average tau_mean: {avg_tau:.2f}")
    if compression_metrics:
        avg_t_compress = statistics.mean(item["t_compress_ms"] for item in compression_metrics)
        avg_r_actual = statistics.mean(item["R_actual"] for item in compression_metrics)
        print(f"average t_compress_ms: {avg_t_compress:.2f}")
        print(f"average R_actual: {avg_r_actual:.2f}")
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
                "t_prefill_ms": metric.t_prefill_ms,
                "t_prefill_mode": metric.t_prefill_mode,
                "prefill_vram_allocated_gib": metric.prefill_vram_allocated_gib,
                "prefill_vram_reserved_gib": metric.prefill_vram_reserved_gib,
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
            row.update(metric.compression_info)
            if condition == "Baseline-AR":
                row.update({"compression": "none", "keep_rate": 1.0})
            if row.get("draft_used") is False:
                row["draft_path"] = None
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DFlash/CC-LLM/Baseline-AR smoke benchmark")
    parser.add_argument("--config", default="config.yml")
    parser.add_argument("--condition", default="DFlash-R1")
    parser.add_argument("--n", type=int, default=3)
    parser.add_argument("--output", default="results/dflash_r1_smoke.jsonl")
    parser.add_argument("--prompt-source", choices=["smoke", "fixture"], default="smoke")
    parser.add_argument("--fixture", type=Path, default=None)
    parser.add_argument("--store-generated-text", action="store_true")
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=None,
        help="Override benchmark.max_new_tokens for calibration runs; default config path remains clamped to 32.",
    )
    args = parser.parse_args()

    config = _read_config(args.config, max_new_tokens_override=args.max_new_tokens)
    keep_rate = _condition_keep_rate(args.condition, config.raw_config.get("compression", {}).get("llmlingua", {}).get("default_keep_rate", 0.5))
    is_ar = _is_ar_condition(args.condition)
    n_prompts = max(1, args.n)
    prompt_items = _select_prompt_items(
        prompt_source=args.prompt_source,
        n_prompts=n_prompts,
        fixture_path=args.fixture,
    )
    compressor = None
    if keep_rate is not None:
        compressor = LLMLinguaCompressor.from_config(config.raw_config)

    print(f"{args.condition} smoke benchmark")
    print("Compression: none" if keep_rate is None else f"Compression: LLMLingua keep_rate={keep_rate}")
    print(f"Target model path: {config.target_path}")
    if is_ar:
        print("Draft model path: not used for autoregressive baseline")
    else:
        print(f"Draft model path: {config.draft_path}")
    print(f"Tokenizer path: {config.tokenizer_path}")
    print(f"Device: {config.device}")
    print(f"Block size: {config.block_size}")
    print(f"Max new tokens: {config.max_new_tokens}")
    print(f"Prompt source: {args.prompt_source}")
    if args.fixture is not None:
        print(f"Fixture path: {args.fixture}")
    print(f"Prompt count: {len(prompt_items)}")

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
        draft = None
        if is_ar:
            print("Draft model: not loaded for autoregressive baseline.")
        else:
            draft = load_draft(
                str(config.draft_path),
                device=config.device,
                attn_implementation=attn_implementation,
                trust_remote_code=True,
                dtype=torch.bfloat16,
            )
            vram_snapshots.append(_vram("after draft load"))

        metrics = []
        for item in prompt_items:
            prompt_for_generation = item.text
            compression_info = None
            if compressor is not None:
                compression_context = item.context if item.context is not None else CC_SMOKE_CONTEXT
                compression_question = item.question if item.question is not None else item.text
                prompt_for_generation, compression_info = _prepare_cc_prompt(
                    compression_question,
                    compressor,
                    keep_rate,
                    context=compression_context,
                )
                if not compression_info["question_preserved"]:
                    raise RuntimeError(f"protected question was not preserved for prompt {item.prompt_id}")

            if is_ar:
                compression_info = compression_info or {}
                compression_info.update(
                    {
                        "generation_mode": "autoregressive",
                        "draft_used": False,
                    }
                )
                metric = _run_ar_prompt(
                    item.prompt_id,
                    prompt_for_generation,
                    tokenizer=tokenizer,
                    target=target,
                    config=config,
                    compression_info=compression_info,
                    store_generated_text=args.store_generated_text,
                )
            else:
                metric = _run_prompt(
                    item.prompt_id,
                    prompt_for_generation,
                    tokenizer=tokenizer,
                    target=target,
                    draft=draft,
                    config=config,
                    compression_info=compression_info,
                    store_generated_text=args.store_generated_text,
                )
            if item.metadata:
                metric.compression_info.update(item.metadata)
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
