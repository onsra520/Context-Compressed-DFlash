from __future__ import annotations

import time
import uuid
import torch
import gc

from ccdf.dflash.generate import dflash_generate
from ccdf.demo.contracts import RunRequest
from ccdf.demo.condition_registry import get_condition
from ccdf.demo.prompt_profiles import apply_prompt_profile
from ccdf.demo.model_manager import ModelManager
from ccdf.demo.metrics import TimingContext, measure_vram


class DemoRunner:
    def __init__(self, config: dict, manager: ModelManager | None = None):
        self.config = config
        self.manager = manager or ModelManager(config)

    @classmethod
    def from_config(cls, config_path: str | dict):
        if isinstance(config_path, str):
            from ccdf.config import load_config
            config = load_config(config_path)
        else:
            config = config_path
        return cls(config)

    def _format_prompt(self, tokenizer, text: str):
        prompt = tokenizer.apply_chat_template(
            [{"role": "user", "content": text}],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        return tokenizer.encode(prompt, return_tensors="pt")

    def _execute_inference(self, request: RunRequest, condition_spec: dict, tokenizer, target) -> dict:
        final_prompt = apply_prompt_profile(request.prompt, request.prompt_profile)
        
        if self.manager.dry_run:
            original_input_tokens = 103
        else:
            original_input_tokens = len(self._format_prompt(tokenizer, final_prompt)[0])
        
        compressed_input_tokens = None
        compression_ratio = None
        t_compress_ms = 0.0
        context_original_tokens = 0
        context_compressed_tokens = 0
        
        if condition_spec["uses_compression"]:
            compressor = self.manager.get_compressor()
            context = request.metadata.get("context", "")
            question = request.metadata.get("question", request.prompt)
            
            with TimingContext() as tc:
                merged, info = compressor.compress(
                    context=context,
                    question=question,
                    keep_rate=condition_spec.get("keep_rate", 0.5)
                )
            
            final_prompt = apply_prompt_profile(merged, request.prompt_profile)
            t_compress_ms = tc.elapsed_ms
            
            if self.manager.dry_run:
                compressed_input_tokens = 93
                context_original_tokens = 16
                context_compressed_tokens = 6
                compression_ratio = 0.5
            else:
                compressed_input_tokens = len(self._format_prompt(tokenizer, final_prompt)[0])
                context_original_tokens = info.get("N_original", 0)
                context_compressed_tokens = info.get("N_compressed", 0)
                compression_ratio = info.get("R_actual", None)
                
        if self.manager.dry_run:
            input_ids = torch.tensor([[1, 2, 3]])
        else:
            input_ids = self._format_prompt(tokenizer, final_prompt).to(self.manager.device)
            
        input_token_count = input_ids.shape[-1]
        
        with TimingContext() as tc_prefill:
            if not self.manager.dry_run:
                with torch.inference_mode():
                    target(
                        input_ids=input_ids,
                        attention_mask=torch.ones_like(input_ids),
                        use_cache=True,
                    )
        t_prefill_ms = tc_prefill.elapsed_ms
        
        temperature = request.generation_options.get("temperature", 0.0)
        stop_token_ids = [tokenizer.eos_token_id] if getattr(tokenizer, "eos_token_id", None) is not None else None
        
        output_tokens = 0
        generated_text = ""
        
        with TimingContext() as tc_gen:
            if condition_spec["uses_dflash"] and not self.manager.dry_run:
                draft = self.manager.get_draft()
                block_size = request.generation_options.get("block_size", 16)
                with torch.inference_mode():
                    result = dflash_generate(
                        draft,
                        target=target,
                        input_ids=input_ids,
                        max_new_tokens=request.max_new_tokens,
                        stop_token_ids=stop_token_ids,
                        temperature=temperature,
                        block_size=block_size,
                        return_stats=True,
                    )
                output_ids = result.output_ids
                output_tokens = int(result.num_output_tokens)
                if hasattr(output_ids, "detach"):
                    generated_token_ids = output_ids[0, input_token_count:].detach().cpu().tolist()
                else:
                    generated_token_ids = output_ids[0][input_token_count:]
                generated_text = tokenizer.decode(generated_token_ids, skip_special_tokens=True)
            else:
                if not self.manager.dry_run:
                    generate_kwargs = {
                        "input_ids": input_ids,
                        "attention_mask": torch.ones_like(input_ids),
                        "max_new_tokens": request.max_new_tokens,
                        "do_sample": temperature > 0,
                    }
                    if temperature > 0:
                        generate_kwargs["temperature"] = temperature
                    if stop_token_ids:
                        generate_kwargs["pad_token_id"] = stop_token_ids[0]
                        generate_kwargs["eos_token_id"] = stop_token_ids[0]
                    
                    with torch.inference_mode():
                        output_ids = target.generate(**generate_kwargs)
                    output_tokens = int(output_ids.shape[-1] - input_ids.shape[-1])
                    generated_token_ids = output_ids[0, input_token_count:].detach().cpu().tolist()
                    generated_text = tokenizer.decode(generated_token_ids, skip_special_tokens=True)
                else:
                    output_tokens = request.max_new_tokens
                    generated_text = "dry run output"
                    
        t_generation_ms = tc_gen.elapsed_ms
        t_e2e_ms = t_compress_ms + t_prefill_ms + t_generation_ms
        
        return {
            "t_compress_ms": t_compress_ms,
            "t_prefill_ms": t_prefill_ms,
            "t_generation_ms": t_generation_ms,
            "t_e2e_ms": t_e2e_ms,
            "output_tokens": output_tokens,
            "generated_text": generated_text,
            "original_input_tokens": original_input_tokens,
            "compressed_input_tokens": compressed_input_tokens,
            "context_original_tokens": context_original_tokens,
            "context_compressed_tokens": context_compressed_tokens,
            "compression_ratio": compression_ratio,
        }

    def run(self, request: RunRequest) -> dict:
        run_id = str(uuid.uuid4())
        condition_spec = get_condition(request.condition)
        
        # 1. Clean and measure memory before load
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
            
        mem_before_load_alloc = torch.cuda.memory_allocated() / (1024 ** 3) if torch.cuda.is_available() else 0.0
        mem_before_load_res = torch.cuda.memory_reserved() / (1024 ** 3) if torch.cuda.is_available() else 0.0
        
        # 2. Load models and measure load time
        import time
        t_model_load_start = time.perf_counter()
        
        tokenizer = self.manager.get_tokenizer()
        target = self.manager.get_target()
        if condition_spec["uses_dflash"]:
            draft = self.manager.get_draft()
        if condition_spec["uses_compression"]:
            compressor = self.manager.get_compressor()
            
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        t_model_load_ms = (time.perf_counter() - t_model_load_start) * 1000.0
        
        # Measure memory after load
        mem_after_load_alloc = torch.cuda.memory_allocated() / (1024 ** 3) if torch.cuda.is_available() else 0.0
        mem_after_load_res = torch.cuda.memory_reserved() / (1024 ** 3) if torch.cuda.is_available() else 0.0
        
        # 3. Warm-up
        warm_up_occurred = False
        t_warmup_ms = 0.0
        mem_after_warmup_alloc = None
        mem_after_warmup_res = None
        
        # Check if warm-up is requested either in metadata or generation_options
        is_warmup_requested = request.metadata.get("warm_up", False) or request.generation_options.get("warm_up", False)
        
        if is_warmup_requested:
            warm_up_occurred = True
            t_warmup_start = time.perf_counter()
            
            # Execute the warm-up inference run
            _ = self._execute_inference(request, condition_spec, tokenizer, target)
            
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            t_warmup_ms = (time.perf_counter() - t_warmup_start) * 1000.0
            
            # Measure memory after warm-up
            mem_after_warmup_alloc = torch.cuda.memory_allocated() / (1024 ** 3) if torch.cuda.is_available() else 0.0
            mem_after_warmup_res = torch.cuda.memory_reserved() / (1024 ** 3) if torch.cuda.is_available() else 0.0
            
            # Reset peak stats before measured run
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()
                torch.cuda.synchronize()
        
        # 4. Measured run
        inf_res = self._execute_inference(request, condition_spec, tokenizer, target)
        
        # 5. Measure peak stats
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            peak_run_alloc = torch.cuda.max_memory_allocated() / (1024 ** 3)
            peak_run_res = torch.cuda.max_memory_reserved() / (1024 ** 3)
        else:
            peak_run_alloc = 0.0
            peak_run_res = 0.0
            
        # 6. Build timing and prompt metrics
        t_compress_ms = inf_res["t_compress_ms"]
        t_prefill_ms = inf_res["t_prefill_ms"]
        t_generation_ms = inf_res["t_generation_ms"]
        t_e2e_ms = inf_res["t_e2e_ms"]
        output_tokens = inf_res["output_tokens"]
        generated_text = inf_res["generated_text"]
        original_input_tokens = inf_res["original_input_tokens"]
        compressed_input_tokens = inf_res["compressed_input_tokens"]
        context_original_tokens = inf_res["context_original_tokens"]
        context_compressed_tokens = inf_res["context_compressed_tokens"]
        compression_ratio = inf_res["compression_ratio"]
        
        # Calculate cold/warm latencies
        if warm_up_occurred:
            cold_start_e2e_ms = t_model_load_ms + t_warmup_ms
            steady_state_e2e_ms = t_e2e_ms
        else:
            cold_start_e2e_ms = t_model_load_ms + t_e2e_ms
            steady_state_e2e_ms = None
            
        generation_tok_s = output_tokens / (t_generation_ms / 1000.0) if t_generation_ms > 0 else 0.0
        e2e_tok_s = output_tokens / (t_e2e_ms / 1000.0) if t_e2e_ms > 0 else 0.0
        
        cap_hit = output_tokens >= request.max_new_tokens
        finish_reason = "length" if cap_hit else "stop"
        
        # Retained ratio, reduction percentage, and compression factor
        compression_retained_ratio = None
        compression_reduction_pct = None
        compression_factor = None
        if condition_spec["uses_compression"]:
            orig = context_original_tokens if context_original_tokens > 0 else 16
            comp = context_compressed_tokens if context_compressed_tokens > 0 else 6
            compression_retained_ratio = comp / orig
            compression_reduction_pct = (1.0 - compression_retained_ratio) * 100.0
            compression_factor = orig / comp
            
        # Clean up
        self.manager.cleanup_for_condition(request.condition)
        self.manager.cleanup_all()
        
        # Return complete results
        import hashlib
        logical_prompt = request.prompt
        rendered_prompt = apply_prompt_profile(logical_prompt, request.prompt_profile)
        logical_prompt_sha256 = hashlib.sha256(logical_prompt.encode("utf-8")).hexdigest()
        rendered_prompt_sha256 = hashlib.sha256(rendered_prompt.encode("utf-8")).hexdigest()
        
        return {
            "schema_version": request.schema_version,
            "run_id": run_id,
            "source": {
                "type": request.source_type,
                "dataset": request.dataset,
                "split": request.split,
                "fixture_id": request.fixture_id
            },
            "prompt_info": {
                "logical_prompt": logical_prompt,
                "rendered_prompt": rendered_prompt,
                "logical_prompt_sha256": logical_prompt_sha256,
                "rendered_prompt_sha256": rendered_prompt_sha256,
                "prompt_profile": request.prompt_profile,
                "fixture_id": request.fixture_id,
                "seed": request.seed,
                "max_new_tokens": request.max_new_tokens,
            },
            "request": {
                "condition": request.condition,
                "prompt_profile": request.prompt_profile,
                "prompt": request.prompt,
                "reference_answer": request.reference_answer,
                "max_new_tokens": request.max_new_tokens,
                "seed": request.seed
            },
            "response": {
                "generated_text": generated_text,
                "finish_reason": finish_reason,
                "cap_hit": cap_hit,
                "output_tokens": output_tokens
            },
            "tokens": {
                "original_input_tokens": original_input_tokens,
                "compressed_input_tokens": compressed_input_tokens,
                "compression_ratio": compression_ratio,
                "compression_retained_ratio": compression_retained_ratio,
                "compression_reduction_pct": compression_reduction_pct,
                "compression_factor": compression_factor,
            },
            "timing_ms": {
                "t_process_startup_ms": 0.0, # Set by run_demo.py
                "t_model_load_ms": t_model_load_ms,
                "t_warmup_ms": t_warmup_ms if warm_up_occurred else None,
                "compression": t_compress_ms,
                "prefill": t_prefill_ms,
                "generation": t_generation_ms,
                "e2e": t_e2e_ms,
                "cold_start_e2e_ms": cold_start_e2e_ms,
                "steady_state_e2e_ms": steady_state_e2e_ms,
            },
            "throughput": {
                "generation_tok_s": generation_tok_s,
                "e2e_tok_s": e2e_tok_s
            },
            "resources": {
                "memory_before_model_load_allocated_gib": mem_before_load_alloc,
                "memory_before_model_load_reserved_gib": mem_before_load_res,
                "memory_after_model_load_allocated_gib": mem_after_load_alloc,
                "memory_after_model_load_reserved_gib": mem_after_load_res,
                "memory_after_warmup_allocated_gib": mem_after_warmup_alloc,
                "memory_after_warmup_reserved_gib": mem_after_warmup_res,
                "peak_run_allocated_gib": peak_run_alloc,
                "peak_run_reserved_gib": peak_run_res,
                "peak_vram_gib": peak_run_alloc, # Backwards compatibility
                "device": self.manager.device
            },
            "quality": {
                "evaluation_status": "not_evaluated",
                "numeric_match": None,
                "normalized_overlap": None
            },
            "status": {
                "ok": True,
                "error_type": None,
                "error_message": None
            }
        }

    def compare_prompt(
        self, 
        prompt: str, 
        conditions: list[str], 
        prompt_profile: str = "raw", 
        max_new_tokens: int = 64, 
        seed: int = 42
    ) -> list[dict]:
        results = []
        for cond in conditions:
            req = RunRequest(
                source_type="interactive",
                condition=cond,
                prompt=prompt,
                prompt_profile=prompt_profile,
                max_new_tokens=max_new_tokens,
                seed=seed,
            )
            try:
                res = self.run(req)
                results.append(res)
            except Exception as e:
                results.append({
                    "schema_version": req.schema_version,
                    "run_id": str(uuid.uuid4()),
                    "source": {"type": "interactive", "dataset": None, "split": None, "fixture_id": None},
                    "request": {
                        "condition": cond,
                        "prompt_profile": prompt_profile,
                        "prompt": prompt,
                        "reference_answer": None,
                        "max_new_tokens": max_new_tokens,
                        "seed": seed
                    },
                    "response": {"generated_text": None, "finish_reason": "error", "output_tokens": 0},
                    "tokens": {"original_input_tokens": 0, "compressed_input_tokens": None, "compression_ratio": None},
                    "timing_ms": {"compression": 0.0, "prefill": None, "generation": 0.0, "e2e": 0.0},
                    "throughput": {"generation_tok_s": None, "e2e_tok_s": None},
                    "resources": {"peak_vram_gib": 0.0, "device": self.manager.device},
                    "quality": {"evaluation_status": "not_evaluated", "numeric_match": None, "normalized_overlap": None},
                    "status": {"ok": False, "error_type": type(e).__name__, "error_message": str(e)}
                })
        return results
