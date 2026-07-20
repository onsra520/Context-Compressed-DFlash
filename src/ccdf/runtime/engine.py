"""Standalone model-resident runtime engine."""

from __future__ import annotations

import gc
import time
from pathlib import Path
from typing import Any, Callable

import torch

from ..config import Rec2Config, load_config
from ..infrastructure.determinism import configure_determinism
from ..infrastructure.device import collect_memory, enforce_memory_gate, reset_peak_memory, synchronize
from ..dflash.generate import generate_dflash
from ..dflash.policy import BlockPolicy
from ..inference.baseline import generate_baseline
from ..models.loaders import load_baseline, load_dflash_models, maybe_compile
from .schemas import GenerationOutput, GenerationSettings


class RuntimeEngine:
    def __init__(self, config: Rec2Config, *, condition: str, target_profile: str = "primary") -> None:
        if condition not in {"baseline", "dflash"}:
            raise ValueError("condition must be baseline or dflash")
        self.config = config
        self.condition = condition
        self.target_profile = target_profile
        self.target = None
        self.drafter = None
        self.model = None
        self.tokenizer = None
        self.model_metadata: dict[str, Any] = {}
        self.seed = int(self.config.require("runtime.seed"))
        self.determinism = self._configure_determinism()
        self._load()

    def _configure_determinism(self) -> dict[str, Any]:
        return configure_determinism(
            seed=self.seed,
            deterministic=bool(self.config.get("runtime.deterministic", True)),
            allow_tf32=bool(self.config.get("runtime.allow_tf32", False)),
            matmul_precision=str(self.config.get("runtime.matmul_precision", "high")),
            sdpa_kernel=str(self.config.get("runtime.sdpa_kernel", "math")),
        )

    @classmethod
    def from_config(
        cls,
        path: str | Path = "config.yml",
        *,
        condition: str,
        target_profile: str = "primary",
    ) -> "RuntimeEngine":
        return cls(load_config(path), condition=condition, target_profile=target_profile)

    def _load(self) -> None:
        if self.condition == "baseline":
            self.model, self.tokenizer, self.model_metadata = load_baseline(self.config)
            self.model_metadata["source_identity"] = dict(
                self.config.require("project.source_identity")
            )
            return
        self.target, self.drafter, self.tokenizer, self.model_metadata = load_dflash_models(
            self.config,
            target_profile=self.target_profile,
        )
        self.model_metadata["source_identity"] = dict(
            self.config.require("project.source_identity")
        )
        compile_cfg = dict(self.config.require("optimization.compile"))
        maybe_compile(
            self.drafter,
            enabled=bool(compile_cfg["drafter_enabled"]),
            mode=str(compile_cfg["mode"]),
            fullgraph=bool(compile_cfg["fullgraph"]),
            dynamic=bool(compile_cfg["dynamic"]),
        )
        if compile_cfg["target_verify_enabled"]:
            maybe_compile(
                self.target,
                enabled=True,
                mode=str(compile_cfg["mode"]),
                fullgraph=bool(compile_cfg["fullgraph"]),
                dynamic=bool(compile_cfg["dynamic"]),
            )
        if self.config.get("memory.enforce_after_model_load", True):
            reset_peak_memory()
            synchronize()
            stats = collect_memory(
                limit_gib=float(self.config.require("memory.dflash_peak_reserved_limit_gib"))
            )
            enforce_memory_gate(stats, label="D-Flash model load")

    def encode_prompt(self, prompt: str, *, system: str | None = None) -> torch.Tensor:
        system_text = system or str(self.config.get("prompts.system", ""))
        messages = []
        if system_text:
            messages.append({"role": "system", "content": system_text})
        messages.append({"role": "user", "content": prompt})
        kwargs = {
            "tokenize": True,
            "add_generation_prompt": True,
            "return_tensors": "pt",
        }
        chat_template = getattr(self.tokenizer, "chat_template", "") or ""
        if "enable_thinking" in chat_template:
            kwargs["enable_thinking"] = bool(self.config.get("runtime.enable_thinking", False))
        try:
            encoded = self.tokenizer.apply_chat_template(messages, **kwargs)
        except TypeError:
            kwargs.pop("enable_thinking", None)
            encoded = self.tokenizer.apply_chat_template(messages, **kwargs)
        device = self.model.device if self.condition == "baseline" else self.target.device
        return encoded.to(device)

    def generate(
        self,
        prompt: str,
        *,
        dataset: str = "general",
        max_new_tokens: int | None = None,
        temperature: float | None = None,
        on_tokens_committed: Callable[[list[int], str], None] | None = None,
    ) -> GenerationOutput:
        # Reset every request so repetitions and condition order cannot inherit RNG state.
        self.determinism = self._configure_determinism()
        warm_start = time.perf_counter()
        prepare_start = time.perf_counter()
        input_ids = self.encode_prompt(prompt)
        prompt_prepare_ms = (time.perf_counter() - prepare_start) * 1000.0
        settings = GenerationSettings(
            max_new_tokens=int(max_new_tokens or self.config.require("runtime.max_new_tokens")),
            temperature=float(
                self.config.require("runtime.temperature") if temperature is None else temperature
            ),
            stop_token_ids=tuple(int(value) for value in self.config.require("runtime.stop_token_ids")),
            dataset=dataset,
            block_size=int(self.config.require("optimization.block_policy.fixed_block_size")),
            output_contract_mode=str(
                self.config.get("optimization.output_contract_mode", "finalize_only")
            ),
        )
        if self.condition == "baseline":
            baseline_kwargs: dict[str, Any] = {"model_metadata": self.model_metadata}
            if on_tokens_committed is not None:
                baseline_kwargs["on_tokens_committed"] = on_tokens_committed
            result = generate_baseline(
                self.model,
                self.tokenizer,
                input_ids,
                settings,
                **baseline_kwargs,
            )
        else:
            policy = BlockPolicy.from_config(dict(self.config.require("optimization.block_policy")))
            dflash_kwargs: dict[str, Any] = {}
            if on_tokens_committed is not None:
                dflash_kwargs["on_tokens_committed"] = on_tokens_committed
            result = generate_dflash(
                self.target,
                self.drafter,
                self.tokenizer,
                input_ids,
                settings,
                model_metadata=self.model_metadata,
                block_policy=policy,
                memory_limit_gib=float(self.config.require("memory.dflash_peak_reserved_limit_gib")),
                full_structural_audit=bool(
                    self.config.get("optimization.full_structural_audit", False)
                ),
                compact_structural_audit=bool(
                    self.config.get("optimization.compact_structural_audit", True)
                ),
                profile_components=bool(self.config.get("optimization.profile_components", False)),
                gpu_resident_acceptance=bool(
                    self.config.get("optimization.gpu_resident_acceptance", True)
                ),
                allow_subblock_shapes=bool(
                    self.config.get("optimization.block_policy.allow_subblock_shapes", True)
                ),
                **dflash_kwargs,
            )
        synchronize()
        result.runtime["determinism"] = dict(self.determinism)
        result.timing.prompt_prepare_ms = prompt_prepare_ms
        result.timing.warm_request_ms = (time.perf_counter() - warm_start) * 1000.0
        return result

    def close(self) -> None:
        self.model = None
        self.target = None
        self.drafter = None
        self.tokenizer = None
        gc.collect()
        if torch.cuda.is_available():
            synchronize()
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
