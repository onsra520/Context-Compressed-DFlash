"""Real model/compressor adapter used by the live demo run manager."""

from __future__ import annotations

import gc
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import torch

from ..compression.llmlingua import adaptive_keep_rate
from ..config import load_config
from ..runtime import RuntimeEngine

CommittedTokenCallback = Callable[[list[int], str], None]


@dataclass(frozen=True)
class LiveGenerationResult:
    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str
    ttft_ms: float
    generation_latency_ms: float
    dflash: dict[str, int | float] | None


@dataclass(frozen=True)
class LiveCompressionResult:
    prompt: str
    original_input_tokens: int
    compressed_input_tokens: int
    removed_tokens: int
    keep_rate: float
    reduction_rate: float
    latency_ms: float
    requested_device: str
    resolved_device: str
    status: str
    applied: bool
    bypassed: bool
    fallback: bool


def _token_count(tokenizer: Any, text: str, *, system: str = "") -> int:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": text})
    kwargs: dict[str, Any] = {
        "tokenize": True,
        "add_generation_prompt": True,
    }
    chat_template = getattr(tokenizer, "chat_template", "") or ""
    if "enable_thinking" in chat_template:
        kwargs["enable_thinking"] = False
    try:
        encoded = tokenizer.apply_chat_template(messages, **kwargs)
    except TypeError:
        kwargs.pop("enable_thinking", None)
        encoded = tokenizer.apply_chat_template(messages, **kwargs)
    return len(encoded)


def _model_devices(model: Any) -> set[str]:
    tensors = [*model.parameters(), *model.buffers()]
    if not tensors:
        raise RuntimeError("compressor has no parameters or buffers")
    return {str(tensor.device) for tensor in tensors}


class RealDemoBackend:
    """Loads and releases one architecture at a time on the configured GPU."""

    def __init__(self, config_path: str | Path = "config.yml") -> None:
        self.config_path = Path(config_path)

    def analyze_input(self, prompt: str) -> dict[str, int]:
        return {
            "characters": len(prompt),
            "words": len(prompt.split()),
        }

    def generate(
        self,
        *,
        condition_id: str,
        prompt: str,
        max_new_tokens: int,
        on_tokens_committed: CommittedTokenCallback,
    ) -> LiveGenerationResult:
        runtime_condition = "baseline" if condition_id == "baseline-ar" else "dflash"
        engine = RuntimeEngine.from_config(self.config_path, condition=runtime_condition)
        first_token_at: float | None = None
        generation_started = 0.0

        def capture(token_ids: list[int], text_delta: str) -> None:
            nonlocal first_token_at
            if first_token_at is None:
                first_token_at = time.perf_counter()
            on_tokens_committed(token_ids, text_delta)

        try:
            generation_started = time.perf_counter()
            output = engine.generate(
                prompt,
                dataset="general",
                max_new_tokens=max_new_tokens,
                temperature=0.0,
                on_tokens_committed=capture,
            )
        finally:
            engine.close()

        if first_token_at is None:
            raise RuntimeError(f"{condition_id} completed without committing an output token")
        dflash = None
        if output.dflash is not None:
            proposed = int(output.dflash.draft_tokens_proposed)
            accepted = int(output.dflash.accepted_draft_tokens)
            loops = int(output.dflash.target_verification_calls)
            dflash = {
                "proposed_draft_tokens": proposed,
                "accepted_draft_tokens": accepted,
                "rejected_draft_tokens": proposed - accepted,
                "acceptance_rate": accepted / proposed if proposed else 0.0,
                "verify_loops": loops,
                "mean_accepted_tokens_per_loop": accepted / loops if loops else 0.0,
            }
        return LiveGenerationResult(
            text=output.text,
            input_tokens=int(output.prompt_tokens),
            output_tokens=int(output.output_tokens),
            stop_reason=output.stop_reason,
            ttft_ms=(first_token_at - generation_started) * 1000.0,
            generation_latency_ms=float(output.timing.generation_total_ms),
            dflash=dflash,
        )

    def compress(self, *, prompt: str, device: str) -> LiveCompressionResult:
        if device not in {"cpu", "cuda"}:
            raise ValueError(f"unsupported compression device: {device}")
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA compression was requested but CUDA is unavailable")

        config = load_config(self.config_path)
        profile = dict(config.require("models.compressor"))
        model_path = Path(profile["local_path"]).resolve()
        requested = "cuda:0" if device == "cuda" else "cpu"
        compressor = None
        target_tokenizer = None
        try:
            from llmlingua import PromptCompressor
            from transformers import AutoTokenizer

            compressor = PromptCompressor(
                model_name=str(model_path),
                device_map=requested,
                model_config={"local_files_only": True, "trust_remote_code": True},
                use_llmlingua2=True,
            )
            compressor.max_batch_size = int(profile.get("max_batch_size", 1))
            devices = _model_devices(compressor.model)
            expected = {"cpu"} if device == "cpu" else {"cuda:0"}
            if devices != expected:
                raise RuntimeError(
                    f"compressor requested {requested} but model tensors resolved to {sorted(devices)}"
                )

            target_tokenizer = AutoTokenizer.from_pretrained(
                str(config.require("models.baseline.tokenizer_path")),
                local_files_only=True,
                trust_remote_code=bool(config.get("models.baseline.trust_remote_code", True)),
            )
            system = str(config.get("prompts.system", ""))
            original_tokens = _token_count(target_tokenizer, prompt, system=system)
            keep_rate = adaptive_keep_rate(config, original_tokens)
            if device == "cuda":
                torch.cuda.synchronize()
            started = time.perf_counter()
            with torch.inference_mode():
                compressed = compressor.compress_prompt_llmlingua2(
                    [prompt],
                    rate=keep_rate,
                    use_context_level_filter=False,
                    use_token_level_filter=True,
                )
            if device == "cuda":
                torch.cuda.synchronize()
            latency_ms = (time.perf_counter() - started) * 1000.0
            compressed_prompt = str(compressed["compressed_prompt_list"][0]).strip()
            compressed_tokens = (
                _token_count(target_tokenizer, compressed_prompt, system=system)
                if compressed_prompt
                else 0
            )

            if not compressed_prompt or compressed_tokens >= original_tokens:
                compressed_prompt = prompt
                compressed_tokens = original_tokens
                applied = False
                bypassed = True
                status = "BYPASSED_NO_REDUCTION"
            else:
                applied = True
                bypassed = False
                status = "COMPRESSED"
            removed = original_tokens - compressed_tokens
            return LiveCompressionResult(
                prompt=compressed_prompt,
                original_input_tokens=original_tokens,
                compressed_input_tokens=compressed_tokens,
                removed_tokens=removed,
                keep_rate=compressed_tokens / original_tokens if original_tokens else 1.0,
                reduction_rate=removed / original_tokens if original_tokens else 0.0,
                latency_ms=latency_ms,
                requested_device=device,
                resolved_device=next(iter(devices)),
                status=status,
                applied=applied,
                bypassed=bypassed,
                fallback=False,
            )
        finally:
            if compressor is not None:
                compressor.model = None
                compressor.tokenizer = None
            del compressor, target_tokenizer
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
