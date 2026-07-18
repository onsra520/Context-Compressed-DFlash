"""Local-only model loaders for baseline, target, and drafter roles."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

import torch

from ..config import Config
from ..runtime.device import assert_cuda_only, attention_runtime_state
from ..errors import ConfigurationError, ModelContractError


def _dtype(name: str) -> torch.dtype:
    normalized = str(name).lower()
    if normalized in {"bf16", "bfloat16"}:
        return torch.bfloat16
    if normalized in {"fp16", "float16"}:
        return torch.float16
    if normalized in {"fp32", "float32"}:
        return torch.float32
    raise ConfigurationError(f"unsupported dtype: {name}")


def _prepare_awq_compatibility() -> bool:
    """Provide the activation alias required by the installed AWQ integration."""
    activations = importlib.import_module("transformers.activations")

    if not hasattr(activations, "PytorchGELUTanh"):
        activations.PytorchGELUTanh = activations.GELUTanh
        return True
    return False


def _prepare_awq_deterministic_kernel(enabled: bool, split_k_iters: int = 1) -> dict[str, Any]:
    """Avoid Triton split-K atomic accumulation in deterministic mode."""
    if enabled and int(split_k_iters) != 1:
        raise ConfigurationError("deterministic canonical runtime requires awq_split_k_iters=1")
    module = importlib.import_module("awq.modules.linear.gemm")
    if not enabled or module.awq_ext is not None or not module.TRITON_AVAILABLE:
        return {"applied": False, "triton_split_k_iters": None}
    current = module.awq_gemm_triton
    if getattr(current, "_ccdf_split_k_one", False):
        return {"applied": True, "triton_split_k_iters": 1}

    def split_k_one(*args: Any, **kwargs: Any):
        kwargs["split_k_iters"] = 1
        return current(*args, **kwargs)

    split_k_one._ccdf_split_k_one = True
    module.awq_gemm_triton = split_k_one
    return {"applied": True, "triton_split_k_iters": 1}


def _prepare_triton_build_headers() -> bool:
    """Use an installed Python header directory when the running minor header is absent."""
    import sys
    import sysconfig

    from triton import knobs

    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    current_header = Path(sysconfig.get_paths()["include"]) / "Python.h"
    fallback_header_dir = Path(sys.prefix) / ".python-dev-headers" / "usr" / "include" / version
    if not current_header.exists() and fallback_header_dir.joinpath("Python.h").exists():
        knobs.build.cudacrt_path = str(fallback_header_dir)
        return True
    return False


def _load_pretrained(
    cls: Any,
    *,
    path: Path,
    profile: dict[str, Any],
    attention_backend: str,
    local_files_only: bool,
) -> Any:
    workarounds = {
        "awq_profile": False,
        "activation_alias_applied": False,
        "triton_header_override_applied": False,
        "torch_disable_native_jit_environment": os.environ.get("TORCH_DISABLE_NATIVE_JIT"),
        "isolated_triton_cache": os.environ.get("TRITON_CACHE_DIR"),
        "awq_deterministic_kernel": getattr(
            importlib.import_module("awq.modules.linear.gemm").awq_gemm_triton,
            "_ccdf_split_k_one",
            False,
        ) if str(profile.get("quantization", "")).startswith("awq") else False,
    }
    if str(profile.get("quantization", "")).startswith("awq"):
        workarounds["awq_profile"] = True
        workarounds["triton_header_override_applied"] = _prepare_triton_build_headers()
        workarounds["activation_alias_applied"] = _prepare_awq_compatibility()
    configured_device_map = profile["device_map"]
    if isinstance(configured_device_map, str) and configured_device_map.startswith("cuda"):
        index = int(configured_device_map.split(":", 1)[1]) if ":" in configured_device_map else 0
        configured_device_map = {"": index}
    kwargs: dict[str, Any] = {
        "local_files_only": local_files_only,
        "device_map": configured_device_map,
        "dtype": _dtype(profile["dtype"]),
    }
    if bool(profile["trust_remote_code"]):
        kwargs["trust_remote_code"] = True
    if attention_backend and attention_backend != "auto":
        kwargs["attn_implementation"] = attention_backend
    try:
        model = cls.from_pretrained(path, **kwargs)
    except TypeError as exc:
        if "attn_implementation" not in str(exc):
            raise
        kwargs.pop("attn_implementation", None)
        model = cls.from_pretrained(path, **kwargs)
        if getattr(model, "config", None) is not None:
            model.config._attn_implementation = attention_backend
    model._ccdf_runtime_workarounds = workarounds
    model._ccdf_requested_dtype = str(profile.get("dtype", "bfloat16"))
    floating_dtypes = sorted(
        {
            str(tensor.dtype).removeprefix("torch.")
            for tensor in (*tuple(model.parameters()), *tuple(model.buffers()))
            if tensor.is_floating_point()
        }
    )
    model._ccdf_effective_dtypes = floating_dtypes
    return model


def load_tokenizer(
    path: str | Path, *, local_files_only: bool, trust_remote_code: bool
):
    from transformers import AutoTokenizer

    model_path = Path(path).resolve()
    if not model_path.exists():
        raise FileNotFoundError(f"tokenizer path not found: {model_path}")
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        local_files_only=local_files_only,
        trust_remote_code=trust_remote_code,
    )
    if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    return tokenizer


def load_baseline(config: Config):
    from transformers import AutoModelForCausalLM

    profile = config.model_profile("baseline")
    _prepare_awq_compatibility()
    awq_kernel = _prepare_awq_deterministic_kernel(
        bool(config.require("runtime.deterministic")),
        int(config.require("runtime.awq_split_k_iters")),
    )
    path = Path(profile["local_path"]).resolve()
    if not path.exists():
        raise FileNotFoundError(f"baseline model path not found: {path}")
    model = _load_pretrained(
        AutoModelForCausalLM,
        path=path,
        profile=profile,
        attention_backend=str(config.require("runtime.attention_backend")),
        local_files_only=bool(config.require("runtime.local_files_only")),
    )
    model.eval()
    device_audit = assert_cuda_only(model, label="baseline")
    tokenizer = load_tokenizer(
        profile["tokenizer_path"],
        local_files_only=bool(config.require("runtime.local_files_only")),
        trust_remote_code=bool(profile["trust_remote_code"]),
    )
    return model, tokenizer, {
        "role": "baseline",
        "model_id": profile["model_id"],
        "quantization": profile["quantization"],
        "requested_dtype": getattr(model, "_ccdf_requested_dtype", None),
        "effective_dtypes": getattr(model, "_ccdf_effective_dtypes", []),
        "attention": attention_runtime_state(model),
        "runtime_workarounds": getattr(model, "_ccdf_runtime_workarounds", {}),
        "awq_deterministic_kernel": awq_kernel,
        "device_audit": device_audit,
        "local_files_only": bool(config.require("runtime.local_files_only")),
    }


def load_dflash_models(config: Config, target_profile: str = "primary"):
    from transformers import AutoModel, AutoModelForCausalLM

    target_cfg = config.model_profile("dflash", target_profile=target_profile)
    _prepare_awq_compatibility()
    awq_kernel = _prepare_awq_deterministic_kernel(
        bool(config.require("runtime.deterministic")),
        int(config.require("runtime.awq_split_k_iters")),
    )
    drafter_cfg = dict(config.require("models.dflash.drafter"))
    target_path = Path(target_cfg["local_path"]).resolve()
    drafter_path = Path(drafter_cfg["local_path"]).resolve()
    for label, path in (("target", target_path), ("drafter", drafter_path)):
        if not path.exists():
            raise FileNotFoundError(f"{label} model path not found: {path}")
    backend = str(config.require("runtime.attention_backend"))
    local_files_only = bool(config.require("runtime.local_files_only"))
    target = _load_pretrained(
        AutoModelForCausalLM,
        path=target_path,
        profile=target_cfg,
        attention_backend=backend,
        local_files_only=local_files_only,
    )
    drafter = _load_pretrained(
        AutoModel,
        path=drafter_path,
        profile=drafter_cfg,
        attention_backend=backend,
        local_files_only=local_files_only,
    )
    target.eval()
    drafter.eval()
    target_device_audit = assert_cuda_only(target, label="D-Flash target")
    drafter_device_audit = assert_cuda_only(drafter, label="D-Flash drafter")
    tokenizer = load_tokenizer(
        target_cfg["tokenizer_path"],
        local_files_only=local_files_only,
        trust_remote_code=bool(target_cfg["trust_remote_code"]),
    )
    contract = validate_dflash_contract(target, drafter, config)
    return target, drafter, tokenizer, {
        "role": "dflash",
        "target_profile": target_profile,
        "target_model_id": target_cfg["model_id"],
        "target_quantization": target_cfg["quantization"],
        "target_requested_dtype": getattr(target, "_ccdf_requested_dtype", None),
        "target_effective_dtypes": getattr(target, "_ccdf_effective_dtypes", []),
        "drafter_requested_dtype": getattr(drafter, "_ccdf_requested_dtype", None),
        "drafter_effective_dtypes": getattr(drafter, "_ccdf_effective_dtypes", []),
        "drafter_model_id": drafter_cfg["model_id"],
        "contract": contract,
        "target_attention": attention_runtime_state(target),
        "drafter_attention": attention_runtime_state(drafter),
        "target_runtime_workarounds": getattr(target, "_ccdf_runtime_workarounds", {}),
        "drafter_runtime_workarounds": getattr(drafter, "_ccdf_runtime_workarounds", {}),
        "awq_deterministic_kernel": awq_kernel,
        "target_device_audit": target_device_audit,
        "drafter_device_audit": drafter_device_audit,
        "local_files_only": local_files_only,
    }


def validate_dflash_contract(target: Any, drafter: Any, config: Config) -> dict[str, Any]:
    target_config = target.config
    draft_config = drafter.config
    target_layer_ids = list(
        getattr(drafter, "target_layer_ids", draft_config.dflash_config.get("target_layer_ids", []))
    )
    checks = {
        "target_has_embed_tokens": hasattr(getattr(target, "model", None), "embed_tokens"),
        "target_has_lm_head": hasattr(target, "lm_head"),
        "hidden_size_match": int(target_config.hidden_size) == int(draft_config.hidden_size),
        "vocab_size_match": int(target_config.vocab_size) == int(draft_config.vocab_size),
        "target_layer_ids_nonempty": bool(target_layer_ids),
        "target_layers_in_range": all(0 <= int(index) < int(target_config.num_hidden_layers) for index in target_layer_ids),
        "checkpoint_block_size_match": int(getattr(drafter, "block_size", -1))
        == int(config.require("models.dflash.drafter.checkpoint_block_size")),
        "mask_token_id_present": getattr(drafter, "mask_token_id", None) is not None,
    }
    checks["pass"] = all(bool(value) for value in checks.values())
    checks["target_layer_ids"] = target_layer_ids
    checks["checkpoint_block_size"] = int(getattr(drafter, "block_size", -1))
    if not checks["pass"]:
        raise ModelContractError(f"D-Flash model contract failed: {checks}")
    return checks


def maybe_compile(model: Any, *, enabled: bool, mode: str, fullgraph: bool, dynamic: bool) -> Any:
    if not enabled:
        return model
    if not hasattr(torch, "compile"):
        raise ModelContractError("torch.compile is unavailable")
    model.forward = torch.compile(model.forward, mode=mode, fullgraph=fullgraph, dynamic=dynamic)
    return model
