from __future__ import annotations

import argparse
import importlib.util
import json
import hashlib
import os
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

BENCHMARK_PROTOCOL_VERSION = "per_prompt_jsonl_v1"

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
class OutputState:
    path: Path
    existing_rows: list[dict]
    completed_prompt_indexes: set[int]
    resumed_from_rows: int
    write_mode: str
    resume_enabled: bool


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
        "compression": "llmlingua",
        "t_compress_ms": info["t_compress_ms"],
        "R_actual": info["R_actual"],
        "N_original": info["N_original"],
        "N_compressed": info["N_compressed"],
        "compressed_input_tokens": info["N_compressed"],
        "keep_rate": info.get("keep_rate", keep_rate),
        "compressor_model": compressor.model_name,
        "question_preserved": question in merged_prompt,
    }
    for field_name in (
        "strategy",
        "compressor_chunked",
        "compressor_chunk_count",
        "compressor_chunking_mode",
        "compressor_chunk_token_budget",
        "compressor_chunk_max_observed_tokens",
        "compressor_chunk_encoder_max_length",
        "compressor_chunk_safety_margin",
        "compressor_chunk_backend_calls",
    ):
        if field_name in info:
            compression_info[field_name] = info[field_name]
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


def _load_jsonl_rows(path: Path) -> list[dict]:
    rows = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: line {lineno} is not valid JSON ({exc})") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}: line {lineno} is not a JSON object")
        rows.append(row)
    return rows


def _row_prompt_index(row: dict) -> int | None:
    value = row.get("benchmark_prompt_index", row.get("prompt_id"))
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _prepare_output_state(
    output_path: Path,
    *,
    condition: str,
    n_prompts: int,
    resume: bool,
    overwrite: bool,
) -> OutputState:
    if resume and overwrite:
        raise ValueError("--resume and --overwrite cannot be used together")

    if output_path.exists():
        if not resume and not overwrite:
            raise FileExistsError(
                f"output exists: {output_path}. Use --resume to continue or --overwrite to replace it."
            )
        if overwrite:
            return OutputState(
                path=output_path,
                existing_rows=[],
                completed_prompt_indexes=set(),
                resumed_from_rows=0,
                write_mode="overwrite",
                resume_enabled=False,
            )

        rows = _load_jsonl_rows(output_path)
        completed: set[int] = set()
        for row_number, row in enumerate(rows, start=1):
            if row.get("condition") != condition:
                raise ValueError(
                    f"{output_path}: row {row_number} condition {row.get('condition')!r} "
                    f"does not match requested condition {condition!r}"
                )
            prompt_index = _row_prompt_index(row)
            if prompt_index is None:
                raise ValueError(f"{output_path}: row {row_number} has no stable prompt index")
            if not 1 <= prompt_index <= n_prompts:
                raise ValueError(
                    f"{output_path}: row {row_number} prompt index {prompt_index} "
                    f"is outside requested range 1..{n_prompts}"
                )
            if prompt_index in completed:
                raise ValueError(f"{output_path}: duplicate benchmark prompt index {prompt_index}")
            completed.add(prompt_index)
        return OutputState(
            path=output_path,
            existing_rows=rows,
            completed_prompt_indexes=completed,
            resumed_from_rows=len(rows),
            write_mode="append_resume",
            resume_enabled=True,
        )

    if resume:
        return OutputState(
            path=output_path,
            existing_rows=[],
            completed_prompt_indexes=set(),
            resumed_from_rows=0,
            write_mode="write_new_resume",
            resume_enabled=True,
        )

    return OutputState(
        path=output_path,
        existing_rows=[],
        completed_prompt_indexes=set(),
        resumed_from_rows=0,
        write_mode="overwrite" if overwrite else "write",
        resume_enabled=False,
    )


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


def _print_row_summary(rows: list[dict]) -> None:
    avg_tok_s = statistics.mean(float(row.get("tok_per_sec", 0.0)) for row in rows) if rows else 0.0
    avg_tau = statistics.mean(float(row.get("tau_mean", 0.0)) for row in rows) if rows else 0.0
    max_allocated = max(float(row.get("vram_allocated_gib", 0.0)) for row in rows) if rows else 0.0
    max_reserved = max(float(row.get("vram_reserved_gib", 0.0)) for row in rows) if rows else 0.0
    compression_rows = [
        row for row in rows if "t_compress_ms" in row and "R_actual" in row
    ]

    print("Summary:")
    print(f"measured rows: {len(rows)}")
    print(f"average tok/s: {avg_tok_s:.2f}")
    print(f"average tau_mean: {avg_tau:.2f}")
    if compression_rows:
        avg_t_compress = statistics.mean(float(row["t_compress_ms"]) for row in compression_rows)
        avg_r_actual = statistics.mean(float(row["R_actual"]) for row in compression_rows)
        print(f"average t_compress_ms: {avg_t_compress:.2f}")
        print(f"average R_actual: {avg_r_actual:.2f}")
    print(f"max VRAM allocated: {max_allocated:.2f}GiB")
    print(f"max VRAM reserved: {max_reserved:.2f}GiB")


def _metric_to_row(
    metric: PromptMetrics,
    *,
    condition: str,
    backend_warning: str,
    config: SmokeConfig,
    benchmark_prompt_index: int | None = None,
    warmup_prompts: int = 0,
    resume_enabled: bool = False,
    resumed_from_rows: int = 0,
    output_write_mode: str = "write",
    output_path: Path | None = None,
) -> dict:
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "row_written_at_utc": datetime.now(timezone.utc).isoformat(),
        "condition": condition,
        "prompt_id": metric.prompt_id,
        "benchmark_prompt_index": benchmark_prompt_index or metric.prompt_id,
        "prompt_hash": _prompt_hash(metric.prompt_text),
        "is_warmup": False,
        "warmup_prompts": warmup_prompts,
        "resume_enabled": resume_enabled,
        "resumed_from_rows": resumed_from_rows,
        "output_write_mode": output_write_mode,
        "output_path": str(output_path) if output_path is not None else None,
        "benchmark_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "input_tokens": metric.input_tokens,
        "output_tokens": metric.output_tokens,
        "generation_time_s": metric.generation_time_s,
        "tok_per_sec": metric.tok_per_s,
        "tokens_per_second": metric.tok_per_s,
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
    return row


def _write_jsonl_row(handle, row: dict) -> None:
    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


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
            row = _metric_to_row(
                metric,
                condition=condition,
                backend_warning=backend_warning,
                config=config,
                output_path=output_path,
            )
            _write_jsonl_row(handle, row)


def _run_benchmark_item(
    item: PromptItem,
    *,
    tokenizer,
    target,
    draft,
    config: SmokeConfig,
    compressor: LLMLinguaCompressor | None,
    keep_rate: float | None,
    is_ar: bool,
    store_generated_text: bool,
) -> PromptMetrics:
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
            store_generated_text=store_generated_text,
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
            store_generated_text=store_generated_text,
        )
    if item.metadata:
        metric.compression_info.update(item.metadata)
    return metric


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DFlash/CC-LLM/Baseline-AR smoke benchmark")
    parser.add_argument("--config", default="config.yml")
    parser.add_argument("--condition", default="DFlash-R1")
    parser.add_argument("--n", type=int, default=3)
    parser.add_argument("--output", default="results/dflash_r1_smoke.jsonl")
    parser.add_argument("--prompt-source", choices=["smoke", "fixture"], default="smoke")
    parser.add_argument("--fixture", type=Path, default=None)
    parser.add_argument("--store-generated-text", action="store_true")
    parser.add_argument("--warmup-prompts", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=None,
        help="Override benchmark.max_new_tokens for calibration runs; default config path remains clamped to 32.",
    )
    args = parser.parse_args()
    if args.resume and args.overwrite:
        parser.error("--resume and --overwrite cannot be used together")

    config = _read_config(args.config, max_new_tokens_override=args.max_new_tokens)
    keep_rate = _condition_keep_rate(args.condition, config.raw_config.get("compression", {}).get("llmlingua", {}).get("default_keep_rate", 0.5))
    is_ar = _is_ar_condition(args.condition)
    n_prompts = max(1, args.n)
    warmup_count = max(0, args.warmup_prompts)
    output_path = Path(args.output)
    prompt_items = _select_prompt_items(
        prompt_source=args.prompt_source,
        n_prompts=n_prompts,
        fixture_path=args.fixture,
    )
    warmup_items = _select_prompt_items(
        prompt_source=args.prompt_source,
        n_prompts=warmup_count,
        fixture_path=args.fixture,
    ) if warmup_count else []
    try:
        output_state = _prepare_output_state(
            output_path,
            condition=args.condition,
            n_prompts=len(prompt_items),
            resume=args.resume,
            overwrite=args.overwrite,
        )
    except (FileExistsError, ValueError) as exc:
        parser.error(str(exc))

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
    print(f"Warmup prompts: {len(warmup_items)}")
    print(f"Output path: {output_path}")
    print(f"Resume enabled: {output_state.resume_enabled}")
    print(f"Resumed from rows: {output_state.resumed_from_rows}")
    print(f"Output write mode: {output_state.write_mode}")

    if len(output_state.completed_prompt_indexes) >= len(prompt_items):
        print(
            f"Resume state already complete: {len(output_state.completed_prompt_indexes)}/"
            f"{len(prompt_items)} measured rows present."
        )
        _print_row_summary(output_state.existing_rows)
        print("Final status: PASS")
        return

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

        if warmup_items:
            print("Warmup start")
            for warmup_index, item in enumerate(warmup_items, start=1):
                print(f"Warmup prompt_id={item.prompt_id} warmup_index={warmup_index}/{len(warmup_items)}")
                _run_benchmark_item(
                    item,
                    tokenizer=tokenizer,
                    target=target,
                    draft=draft,
                    config=config,
                    compressor=compressor,
                    keep_rate=keep_rate,
                    is_ar=is_ar,
                    store_generated_text=False,
                )
            print("Warmup complete")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_state.write_mode == "overwrite" and output_path.exists():
            output_path.unlink()

        file_mode = "a" if output_state.resume_enabled else "w"
        written_this_run = 0
        with output_path.open(file_mode, encoding="utf-8") as handle:
            for benchmark_prompt_index, item in enumerate(prompt_items, start=1):
                if benchmark_prompt_index in output_state.completed_prompt_indexes:
                    print(
                        f"Skipping prompt_id={item.prompt_id} benchmark_prompt_index={benchmark_prompt_index} "
                        "because it is already present in resume output."
                    )
                    continue

                print(
                    f"Starting prompt_id={item.prompt_id} condition={args.condition} "
                    f"benchmark_prompt_index={benchmark_prompt_index}/{len(prompt_items)} "
                    f"compression_active={compressor is not None} draft_speculative={not is_ar} "
                    f"output_path={output_path} resume_enabled={output_state.resume_enabled} "
                    f"resumed_from_rows={output_state.resumed_from_rows}"
                )
                metric = _run_benchmark_item(
                    item,
                    tokenizer=tokenizer,
                    target=target,
                    draft=draft,
                    config=config,
                    compressor=compressor,
                    keep_rate=keep_rate,
                    is_ar=is_ar,
                    store_generated_text=args.store_generated_text,
                )
                row = _metric_to_row(
                    metric,
                    condition=args.condition,
                    backend_warning=backend_warning,
                    config=config,
                    benchmark_prompt_index=benchmark_prompt_index,
                    warmup_prompts=len(warmup_items),
                    resume_enabled=output_state.resume_enabled,
                    resumed_from_rows=output_state.resumed_from_rows,
                    output_write_mode=output_state.write_mode,
                    output_path=output_path,
                )
                _write_jsonl_row(handle, row)
                written_this_run += 1
                rows_written_total = output_state.resumed_from_rows + written_this_run
                print(
                    f"Finished prompt_id={item.prompt_id} benchmark_prompt_index={benchmark_prompt_index} "
                    f"output_tokens={metric.output_tokens} tok/s={metric.tok_per_s:.2f}"
                )
                print(f"Wrote row {rows_written_total}/{len(prompt_items)} to {output_path}")

        final_rows = _load_jsonl_rows(output_path)
        if len(final_rows) != len(prompt_items):
            print("Final status: PARTIAL")
            print(f"Measured rows present: {len(final_rows)}/{len(prompt_items)}")
            raise RuntimeError(
                f"benchmark incomplete: expected {len(prompt_items)} measured rows, found {len(final_rows)}"
            )
        _print_row_summary(final_rows)
        print("Final status: PASS")
    except Exception as exc:
        print(f"Final status: FAIL")
        print(f"Failure: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
