"""Shared real runtime for CLI and benchmark validation."""

from __future__ import annotations

import time
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from ccdf.compression.passthrough import PassthroughCompressor
from ccdf.compression.schemas import CompressionConfig
from ccdf.compression.validation import validate_prompt_invariants
from ccdf.dflash.loader import load_drafter_model
from ccdf.evaluation import gsm8k, qmsum
from ccdf.inference.baseline_ar import generate_baseline
from ccdf.inference.dflash_runtime import generate_dflash_r1
from ccdf.inference.schemas import GenerationConfig
from ccdf.inference.target_loader import load_target_model, load_target_tokenizer
from ccdf.metrics.dflash import validate_dflash_invariants
from ccdf.prompts.contracts import audit_encoded_prompt
from ccdf.prompts.encoder import encode_prompt
from ccdf.prompts.schemas import PromptParts
from ccdf.runtime.schemas import RuntimeRequest


def _current_rss_bytes() -> int | None:
    """Read current resident bytes; ru_maxrss is peak, not current RSS."""
    try:
        resident_pages = int(Path("/proc/self/statm").read_text().split()[1])
        return resident_pages * __import__("os").sysconf("SC_PAGE_SIZE")
    except (OSError, IndexError, ValueError):
        return None


class RuntimeEngine:
    """Load one resolved condition and execute all requests through one pipeline."""

    def __init__(self, resolved: Any) -> None:
        import resource

        self.resolved = resolved
        data = resolved.data
        models = data["models"]
        required_models = ["target"]
        if data["condition_id"] != "baseline-ar":
            required_models.append("drafter")
        if data["condition_id"] == "cc-dflash-r2" and data["dataset"] != "gsm8k":
            required_models.append("compression")
        for name in required_models:
            model_path = Path(models[name]["path"])
            if not model_path.exists():
                raise FileNotFoundError(
                    f"shared {name} model is missing: {model_path}; "
                    f"shared_root={data['path_context']['shared_root']}"
                )

        started = time.perf_counter()
        self.tokenizer = load_target_tokenizer(Path(models["target"]["path"]))
        tokenizer_ms = (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        self.target = load_target_model(
            Path(models["target"]["path"]), device_map=data["runtime"]["device"]
        )
        self.target_model_init_ms = (time.perf_counter() - started) * 1000 + tokenizer_ms

        self.drafter = None
        self.drafter_model_init_ms = 0.0
        if data["condition_id"] != "baseline-ar":
            started = time.perf_counter()
            self.drafter = load_drafter_model(
                Path(models["drafter"]["path"]), device_map=data["runtime"]["device"]
            )
            self.drafter_model_init_ms = (time.perf_counter() - started) * 1000

        self.compressor = None
        self.compressor_init_ms = 0.0
        self.process_rss_before_compressor_bytes = _current_rss_bytes()
        # GSM8K is explicitly short-context bypassed. Avoid loading a CPU model
        # that cannot be used by the canonical condition.
        need_compressor = (
            data["condition_id"] == "cc-dflash-r2"
            and not (data["dataset"] == "gsm8k" and data["compression"].get("short_context_bypass"))
        )
        if need_compressor:
            from ccdf.compression.llmlingua import LLMLinguaCompressor

            started = time.perf_counter()
            self.compressor = LLMLinguaCompressor(
                model_path=Path(models["compression"]["path"]),
                device_map=models["compression"]["device"],
            )
            self.compressor_init_ms = (time.perf_counter() - started) * 1000
        self.process_rss_after_compressor_bytes = _current_rss_bytes()
        self.process_peak_rss_bytes = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
        self.model_init_ms = (
            self.target_model_init_ms + self.drafter_model_init_ms + self.compressor_init_ms
        )

    def close(self) -> None:
        import gc
        import torch

        # Coupled validation loads Baseline and DFlash sequentially in one
        # process. Drop every runtime reference before the next condition so a
        # prior NF4 target cannot keep CUDA allocations alive while the
        # drafter is being loaded.
        self.target = None
        self.drafter = None
        self.compressor = None
        self.tokenizer = None
        self.resolved = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()

    def _parts(self, request: RuntimeRequest) -> PromptParts:
        data = self.resolved.data
        if request.prompt_parts is not None:
            source = request.prompt_parts
            return PromptParts(
                context=source.context,
                question=source.question,
                instruction=data["prompt_policy"]["text"],
                system=data["prompts"].get("system"),
            )
        return PromptParts(
            context="",
            question=request.prompt or "",
            instruction=data["prompt_policy"]["text"],
            system=data["prompts"].get("system"),
        )

    def _compress(self, parts: PromptParts):
        data = self.resolved.data
        context_tokens = len(self.tokenizer.encode(parts.context, add_special_tokens=False))
        config = CompressionConfig(
            keep_rate=data["compression"]["keep_rate"],
            min_context_tokens=data["compression"]["min_context_tokens"],
            chunk_max_words=data["compression"]["chunk_max_words"],
            device_map=data["models"]["compression"]["device"],
        )
        if not parts.context:
            result = PassthroughCompressor().compress(
                context=parts.context, question=parts.question, config=config
            )
            result.backend_metadata["bypass_reason"] = "empty_context"
            return result
        if data["compression"].get("short_context_bypass") and context_tokens < config.min_context_tokens:
            result = PassthroughCompressor().compress(
                context=parts.context, question=parts.question, config=config
            )
            result.backend_metadata["bypass_reason"] = "below_min_context_tokens"
            return result
        if self.compressor is None:
            raise RuntimeError("compression required but compressor was not loaded")
        started = time.perf_counter()
        result = self.compressor.compress(
            context=parts.context, question=parts.question, config=config
        )
        result.compression_total_ms = (time.perf_counter() - started) * 1000
        return result

    def execute(self, request: RuntimeRequest) -> dict[str, Any]:
        if request.resolved.sha256 != self.resolved.sha256:
            raise ValueError("RuntimeRequest resolved config does not match RuntimeEngine")
        data = self.resolved.data
        condition_id = data["condition_id"]
        warm_start = time.perf_counter()

        parts = self._parts(request)
        prompt_start = time.perf_counter()
        pre_encoded = encode_prompt(
            self.tokenizer,
            parts=parts,
            dataset=data["dataset"],
            enable_thinking=data["runtime"]["enable_thinking"],
            device=self.target.device,
        )
        prompt_render_ms = (time.perf_counter() - prompt_start) * 1000
        pre_prompt_audit = audit_encoded_prompt(pre_encoded, data["prompt_policy"]["text"])
        if not pre_prompt_audit["pass"]:
            raise ValueError(f"prompt contract failed: {pre_prompt_audit}")

        compression = None
        bypass_reason = None
        final_parts = parts
        final_encoded = pre_encoded
        if condition_id == "cc-dflash-r2":
            compression = self._compress(parts)
            bypass_reason = compression.backend_metadata.get("bypass_reason") if compression.bypassed else None
            final_parts = replace(parts, context=compression.compressed_context)
            validate_prompt_invariants(parts, compression.compressed_context, dataset=data["dataset"])
            final_encoded = encode_prompt(
                self.tokenizer,
                parts=final_parts,
                dataset=data["dataset"],
                enable_thinking=data["runtime"]["enable_thinking"],
                device=self.target.device,
            )
            final_prompt_audit = audit_encoded_prompt(
                final_encoded, data["prompt_policy"]["text"]
            )
            if not final_prompt_audit["pass"]:
                raise ValueError(f"compressed prompt contract failed: {final_prompt_audit}")
        else:
            final_prompt_audit = pre_prompt_audit

        import torch

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
        generation = GenerationConfig(
            max_new_tokens=data["max_new_tokens"],
            temperature=data["runtime"]["temperature"],
            stop_token_ids=tuple(data["runtime"]["stop_token_ids"]),
            enable_thinking=data["runtime"]["enable_thinking"],
            dataset=data["dataset"],
            prompt_policy_text=data["prompt_policy"]["text"],
            output_contract_settings=data["output_contracts"],
            dflash_block_size=(data["condition"].get("block_size") or None),
        )
        if condition_id == "baseline-ar":
            result = generate_baseline(self.target, self.tokenizer, final_encoded.input_ids, generation)
        else:
            result = generate_dflash_r1(
                self.target, self.drafter, self.tokenizer, final_encoded.input_ids, generation
            )

        result.target_model_init_ms = self.target_model_init_ms
        result.drafter_model_init_ms = self.drafter_model_init_ms
        result.compressor_init_ms = self.compressor_init_ms
        result.model_init_ms = self.model_init_ms
        result.prompt_render_ms = prompt_render_ms
        if compression is not None:
            result.compression_total_ms = compression.compression_total_ms
        result.warm_request_e2e_ms = (time.perf_counter() - warm_start) * 1000

        allocated = reserved = 0
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            allocated = int(torch.cuda.max_memory_allocated())
            reserved = int(torch.cuda.max_memory_reserved())

        dflash = {
            "target_seed_tokens": result.target_seed_tokens,
            "verification_calls": result.verification_calls,
            "target_prefill_calls": result.target_prefill_calls,
            "target_block_verification_calls": result.target_block_verification_calls,
            "target_single_token_fallback_calls": result.target_single_token_fallback_calls,
            "target_hidden_refresh_calls": result.target_hidden_refresh_calls,
            "total_target_forward_calls": result.total_target_forward_calls,
            "draft_forward_calls": result.draft_forward_calls,
            "raw_acceptance_lengths": result.raw_acceptance_lengths,
            "emitted_acceptance_lengths": result.emitted_acceptance_lengths,
            "acceptance_lengths": result.acceptance_lengths,
            "draft_tokens_proposed": result.draft_tokens_proposed,
            "accepted_draft_tokens": result.accepted_draft_tokens,
            "correction_tokens": result.correction_tokens,
            "bonus_target_tokens": result.bonus_target_tokens,
            "rollback_tokens": result.rollback_tokens,
            "effective_tau": result.effective_tau,
            # Backward-compatible Rec-T02B/Rec-T05 benchmark schema alias.
            # Direction B uses effective_tau as the canonical name.
            "tau_tokens_advanced_per_verification": result.effective_tau,
            "draft_acceptance_rate": result.draft_acceptance_rate,
            "target_forwards_per_emitted_token": result.target_forwards_per_emitted_token,
            "structural_audit": result.structural_audit,
            "exact_cached_ar_token_equivalence": "NOT_CLAIMED",
        }
        if condition_id != "baseline-ar":
            validate_dflash_invariants({**dflash, "output_tokens": result.output_token_count})

        health = result.output_health
        if request.reference_answer is not None:
            if data["dataset"] == "gsm8k":
                quality = gsm8k.evaluate(
                    result.generated_text,
                    request.reference_answer,
                    validated_answer=result.validated_answer,
                    cap_hit=result.cap_hit,
                    repetition_detected=result.repetition_detected,
                )
            else:
                quality = qmsum.evaluate(
                    result.generated_text,
                    request.reference_answer,
                    cap_hit=result.cap_hit,
                    repetition_detected=result.repetition_detected,
                    instruction_echo_detected=result.instruction_echo_detected,
                    answer_prefix_count=int(health.get("answer_prefix_count", 0)),
                    repeated_ngram_ratio=float(health.get("repeated_ngram_ratio", 0.0)),
                )
        else:
            quality = {
                "evaluator_version": "not_evaluated",
                "label": "not_evaluated",
                "semantic_correctness": "NOT_CLAIMED" if data["dataset"] == "qmsum" else None,
                "tokenizer_source": "target",
            }

        pre_tokens = len(pre_encoded.input_ids_list)
        final_tokens = len(final_encoded.input_ids_list)
        token_scope = {
            "precompression_target_prompt_tokens": pre_tokens,
            "final_target_prompt_tokens": final_tokens,
            "full_prompt_retained_ratio": final_tokens / pre_tokens if pre_tokens else 1.0,
            "full_prompt_reduction_pct": (1.0 - final_tokens / pre_tokens) * 100 if pre_tokens else 0.0,
            "precompression_input_ids_hash": pre_encoded.input_ids_hash,
            "final_input_ids_hash": final_encoded.input_ids_hash,
            "exact_chat_template_scope": True,
        }
        return {
            "generated_text": result.generated_text,
            "raw_generated_text": result.raw_generated_text,
            "validated_answer": result.validated_answer,
            "output_token_ids": result.output_token_ids,
            "generated_token_ids": result.generated_token_ids,
            "output_tokens": result.output_token_count,
            "input_tokens": result.prompt_token_count,
            "stop_reason": result.stop_reason,
            "eos_hit": result.eos_hit,
            "output_contract_hit": result.output_contract_hit,
            "cap_hit": result.cap_hit,
            "repetition_detected": result.repetition_detected,
            "instruction_echo_detected": result.instruction_echo_detected,
            "degeneration_reason": result.degeneration_reason,
            "output_health": result.output_health,
            "success": True,
            "error": None,
            "timing": {
                "target_model_init_ms": self.target_model_init_ms,
                "drafter_model_init_ms": self.drafter_model_init_ms,
                "compressor_init_ms": self.compressor_init_ms,
                "model_init_ms": self.model_init_ms,
                "prompt_render_ms": prompt_render_ms,
                "prompt_prepare_ms": prompt_render_ms,
                "compression_total_ms": result.compression_total_ms,
                "target_prefill_ms": result.target_prefill_ms,
                "draft_prefill_ms": result.draft_prefill_ms,
                "decode_total_ms": result.decode_total_ms,
                "generation_request_e2e_ms": result.generation_request_e2e_ms,
                "warm_request_e2e_ms": result.warm_request_e2e_ms,
                "request_e2e_ms": result.request_e2e_ms,
                # Generation timing begins after prompt preparation and, by
                # contract, excludes optional context compression.
                "cold_start_e2e_ms": self.model_init_ms + result.warm_request_e2e_ms,
            },
            "vram": {
                "peak_allocated_bytes": allocated,
                "peak_reserved_bytes": reserved,
                "measurement_scope": "generation request after optional compression",
            },
            "resource_composition": (
                "quantized target"
                if condition_id == "baseline-ar"
                else "quantized target + drafter"
                if condition_id == "dflash-r1"
                else "quantized target + drafter + CPU compressor"
            ),
            "resource": {
                "peak_cuda_allocated_bytes": allocated,
                "peak_cuda_reserved_bytes": reserved,
                "target_only_gpu_bytes": None,
                "drafter_incremental_gpu_bytes": None,
                "compressor_gpu_bytes": 0 if condition_id == "cc-dflash-r2" else None,
                "process_rss_before_compressor_bytes": self.process_rss_before_compressor_bytes,
                "process_rss_after_compressor_bytes": self.process_rss_after_compressor_bytes,
                "process_peak_rss_bytes": self.process_peak_rss_bytes,
                "cpu_compressor_memory_delta_bytes": (self.process_rss_after_compressor_bytes - self.process_rss_before_compressor_bytes) if self.process_rss_before_compressor_bytes is not None and self.process_rss_after_compressor_bytes is not None else None,
                "model_composition": (
                    "target-only GPU"
                    if condition_id == "baseline-ar"
                    else "target plus drafter GPU"
                    if condition_id == "dflash-r1"
                    else "target plus drafter GPU; CPU compressor"
                ),
                "unsupported_fields": ["target_only_gpu_bytes", "drafter_incremental_gpu_bytes"],
            },
            "dflash": dflash,
            "compression": {
                "applied": bool(compression and not compression.bypassed),
                "bypassed": bool(compression and compression.bypassed),
                "bypass_reason": bypass_reason,
                "result": asdict(compression) if compression else None,
                "token_scope": token_scope,
            },
            "prompt": {
                "precompression_rendered": pre_encoded.rendered_text,
                "final_rendered": final_encoded.rendered_text,
                "structured_hash": final_encoded.structured_hash,
                "rendered_hash": final_encoded.rendered_hash,
                "input_ids_hash": final_encoded.input_ids_hash,
                "chat_template_used": final_encoded.chat_template_used,
                "enable_thinking_applied": final_encoded.enable_thinking_applied,
                "precompression_contract_audit": pre_prompt_audit,
                "contract_audit": final_prompt_audit,
            },
            # Compatibility keys for existing artifacts/CLI.
            "final_prompt": final_encoded.rendered_text,
            "precompression_prompt": pre_encoded.rendered_text,
            "measurement_mode": request.measurement_mode,
            "quality": quality,
            "claim_boundary": data["runtime"]["claim_boundary"],
        }
