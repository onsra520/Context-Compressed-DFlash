"""Standalone model-resident runtime engine."""

from __future__ import annotations

import gc
import time
from pathlib import Path
from typing import Any

import torch

from ..config import Config, load_config
from .determinism import configure_determinism
from .device import collect_memory, enforce_memory_gate, reset_peak_memory, synchronize
from ..dflash.generate import generate_dflash
from ..dflash.policy import BlockPolicy
from ..inference.baseline import generate_baseline
from ..models.loaders import load_baseline, load_dflash_models, maybe_compile
from ..schemas import GenerationOutput, GenerationSettings


class RuntimeEngine:
    def __init__(self, config: Config, *, condition: str, target_profile: str = "primary") -> None:
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
            deterministic=bool(self.config.require("runtime.deterministic")),
            allow_tf32=bool(self.config.require("runtime.allow_tf32")),
            matmul_precision=str(self.config.require("runtime.matmul_precision")),
            sdpa_kernel=str(self.config.require("runtime.sdpa_kernel")),
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
        if bool(self.config.require("memory.enforce_after_model_load")):
            reset_peak_memory()
            synchronize()
            stats = collect_memory(
                limit_gib=float(self.config.require("memory.dflash_peak_reserved_limit_gib"))
            )
            enforce_memory_gate(stats, label="D-Flash model load")

    def encode_prompt(self, prompt: str, *, system: str | None = None) -> torch.Tensor:
        system_text = str(self.config.require("prompts.system")) if system is None else system
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
            kwargs["enable_thinking"] = bool(self.config.require("runtime.enable_thinking"))
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
    ) -> GenerationOutput:
        # Reset every request so repetitions and condition order cannot inherit RNG state.
        self.determinism = self._configure_determinism()
        warm_start = time.perf_counter()
        prepare_start = time.perf_counter()
        input_ids = self.encode_prompt(prompt)
        if input_ids.device.type != "cuda":
            raise RuntimeError(f"inference input tensor must be CUDA resident: {input_ids.device}")
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
                self.config.require("optimization.output_contract_mode")
            ),
        )
        if self.condition == "baseline":
            result = generate_baseline(
                self.model,
                self.tokenizer,
                input_ids,
                settings,
                model_metadata=self.model_metadata,
            )
        else:
            policy = BlockPolicy.from_config(dict(self.config.require("optimization.block_policy")))
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
                    self.config.require("optimization.full_structural_audit")
                ),
                compact_structural_audit=bool(
                    self.config.require("optimization.compact_structural_audit")
                ),
                profile_components=bool(self.config.require("optimization.profile_components")),
                gpu_resident_acceptance=bool(
                    self.config.require("optimization.gpu_resident_acceptance")
                ),
                allow_subblock_shapes=bool(
                    self.config.require("optimization.block_policy.allow_subblock_shapes")
                ),
            )
        synchronize()
        result.runtime["determinism"] = dict(self.determinism)
        result.runtime["inference_tensor_audit"] = {
            "input_ids_device": str(input_ids.device),
            "input_ids_cuda": input_ids.device.type == "cuda",
            "generated_intermediate_device_policy": (
                "all inference tensors are allocated from input_ids.device or model.device"
            ),
            "cpu_or_disk_offload": False,
        }
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
