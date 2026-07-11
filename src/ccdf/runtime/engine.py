"""One real model execution path for CLI and benchmarks."""

from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ccdf.compression.llmlingua import LLMLinguaCompressor
from ccdf.compression.passthrough import PassthroughCompressor
from ccdf.compression.schemas import CompressionConfig
from ccdf.compression.validation import prompt_invariants, token_scope_audit
from ccdf.inference.baseline_ar import generate_baseline
from ccdf.inference.dflash_runtime import generate_dflash_r1
from ccdf.inference.schemas import GenerationConfig
from ccdf.inference.target_loader import load_target_model, load_target_tokenizer
from ccdf.dflash.loader import load_drafter_model
from ccdf.evaluation import gsm8k, qmsum
from ccdf.metrics.dflash import validate_dflash_invariants
from ccdf.prompts.renderer import render_prompt
from ccdf.prompts.schemas import PromptParts
from ccdf.runtime.schemas import RuntimeRequest


class RuntimeEngine:
    """Loads a resolved condition once and executes real requests through it."""

    def __init__(self, resolved: Any) -> None:
        self.resolved = resolved
        data = resolved.data
        models = data["models"]
        started = time.perf_counter()
        self.tokenizer = load_target_tokenizer(Path(models["target"]["path"]))
        self.target = load_target_model(Path(models["target"]["path"]), device_map=data["runtime"]["device"])
        self.drafter = None
        self.compressor = None
        if data["condition_id"] != "baseline-ar":
            self.drafter = load_drafter_model(Path(models["drafter"]["path"]), device_map=data["runtime"]["device"])
        if data["condition_id"] == "cc-dflash-r2":
            self.compressor = LLMLinguaCompressor(
                model_path=Path(models["compression"]["path"]),
                device_map=models["compression"]["device"],
            )
        self.model_init_ms = (time.perf_counter() - started) * 1000

    def close(self) -> None:
        import gc
        import torch

        self.target = None
        self.drafter = None
        self.compressor = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def execute(self, request: RuntimeRequest) -> dict[str, Any]:
        data = request.resolved.data
        condition_id = data["condition_id"]
        parts = request.prompt_parts
        compression = None
        token_scope = None
        bypass_reason = None
        if parts is not None:
            pre_prompt = render_prompt(parts)
        else:
            pre_prompt = request.prompt or ""
        prompt = pre_prompt
        if condition_id == "cc-dflash-r2":
            if parts is None:
                compression = PassthroughCompressor().compress(
                    context="", question="", config=CompressionConfig(compression_enabled=False)
                )
                bypass_reason = "unstructured_prompt"
            else:
                config = CompressionConfig(
                    keep_rate=data["compression"]["keep_rate"],
                    min_context_tokens=data["compression"]["min_context_tokens"],
                    chunk_max_words=data["compression"]["chunk_max_words"],
                    device_map=data["models"]["compression"]["device"],
                )
                started = time.perf_counter()
                compression = self.compressor.compress(context=parts.context, question=parts.question, config=config)
                compression.compression_total_ms = (time.perf_counter() - started) * 1000
                bypass_reason = compression.backend_metadata.get("bypass_reason") if compression.bypassed else None
                final_parts = PromptParts(context=compression.compressed_context, question=parts.question, instruction=parts.instruction, system=parts.system)
                prompt = render_prompt(final_parts)
                token_scope = token_scope_audit(parts, compression, target_tokenizer_path=Path(data["models"]["target"]["path"]))
                prompt_audit = prompt_invariants(parts, compression.compressed_context)
                if not prompt_audit["only_context_changed"]:
                    raise ValueError("compression changed non-context prompt content")

        import torch
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
        generation = GenerationConfig(
            max_new_tokens=data["max_new_tokens"],
            temperature=data["runtime"]["temperature"],
            stop_token_ids=tuple(data["runtime"]["stop_token_ids"]),
            enable_thinking=data["runtime"]["enable_thinking"],
        )
        if condition_id == "baseline-ar":
            result = generate_baseline(self.target, self.tokenizer, prompt, generation)
        else:
            result = generate_dflash_r1(self.target, self.drafter, self.tokenizer, prompt, generation)
        if compression is not None:
            result.compressor_init_ms = 0.0
            result.compression_total_ms = compression.compression_total_ms
        allocated = reserved = 0
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            allocated = int(torch.cuda.max_memory_allocated())
            reserved = int(torch.cuda.max_memory_reserved())
        dflash = {
            "verification_calls": result.verification_calls,
            "acceptance_lengths": result.acceptance_lengths,
            "draft_tokens_proposed": result.draft_tokens_proposed,
            "accepted_draft_tokens": result.accepted_draft_tokens,
            "rollback_tokens": result.rollback_tokens,
        }
        if condition_id != "baseline-ar":
            verification_calls = dflash["verification_calls"]
            validate_dflash_invariants({
                **dflash,
                "condition": {"condition_id": condition_id},
                "tau_tokens_advanced_per_verification": sum(dflash["acceptance_lengths"]) / verification_calls if verification_calls else 0.0,
                "draft_acceptance_rate": dflash["accepted_draft_tokens"] / dflash["draft_tokens_proposed"] if dflash["draft_tokens_proposed"] else 0.0,
            })
        quality = None
        if request.reference_answer is not None:
            quality = gsm8k.evaluate(result.generated_text, request.reference_answer, cap_hit=result.stop_reason == "max_new_tokens") if data["dataset"] == "gsm8k" else qmsum.evaluate(result.generated_text, request.reference_answer, cap_hit=result.stop_reason == "max_new_tokens")
        else:
            quality = {"evaluator_version": "not_evaluated", "label": "not_evaluated", "tokenizer_source": "target"}
        return {
            "generated_text": result.generated_text,
            "output_token_ids": result.output_token_ids,
            "output_tokens": result.output_token_count,
            "input_tokens": result.prompt_token_count,
            "stop_reason": result.stop_reason,
            "cap_hit": result.stop_reason == "max_new_tokens",
            "success": True,
            "error": None,
            "timing": {"model_init_ms": self.model_init_ms, "compressor_init_ms": result.compressor_init_ms, "compression_total_ms": result.compression_total_ms, "target_prefill_ms": result.target_prefill_ms, "draft_prefill_ms": result.draft_prefill_ms, "decode_total_ms": result.decode_total_ms, "request_e2e_ms": result.request_e2e_ms},
            "vram": {"peak_allocated_bytes": allocated, "peak_reserved_bytes": reserved, "measurement_scope": "request"},
            "dflash": dflash,
            "compression": {"applied": bool(compression and not compression.bypassed), "bypassed": bool(compression and compression.bypassed), "bypass_reason": bypass_reason, "result": asdict(compression) if compression else None, "token_scope": token_scope},
            "final_prompt": prompt,
            "precompression_prompt": pre_prompt,
            "measurement_mode": request.measurement_mode,
            "quality": quality,
        }
