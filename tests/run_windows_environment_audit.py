"""Windows environment and isolated component probes for the sealed review pack."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
import warnings
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from io import StringIO
from pathlib import Path
from typing import Any, Callable

import torch

from ccdf.compression import CompressionConfig, ContextOnlyProtocol, LLMLinguaCompressor
from ccdf.config import Config, load_config
from ccdf.models.loaders import _load_pretrained, _prepare_awq_compatibility
from ccdf.runtime.device import assert_cuda_only
from ccdf.runtime.engine import RuntimeEngine


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = {
    "torch": ("torch", "torch"),
    "transformers": ("transformers", "transformers"),
    "awq": ("autoawq", "awq"),
    "llmlingua": ("llmlingua", "llmlingua"),
    "accelerate": ("accelerate", "accelerate"),
    "safetensors": ("safetensors", "safetensors"),
    "triton": ("triton", "triton"),
}


def _json_default(value: Any) -> str:
    return str(value)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _run(command: list[str], *, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "duration_seconds": time.perf_counter() - started,
    }


def _package_record(distribution: str, module: str) -> dict[str, Any]:
    try:
        package_version = version(distribution)
    except PackageNotFoundError:
        package_version = None
    spec = importlib.util.find_spec(module)
    return {
        "distribution": distribution,
        "version": package_version,
        "module": module,
        "origin": str(spec.origin) if spec is not None and spec.origin is not None else None,
        "available": spec is not None,
    }


def _warning_classification(message: str) -> dict[str, Any]:
    lowered = message.lower()
    if "expandable_segments" in lowered and ("not supported" in lowered or "unsupported" in lowered):
        category, fatal = "unsupported_on_windows", False
    elif "autoawq" in lowered and "deprecated" in lowered:
        category, fatal = "deprecated_but_operational", False
    elif "torch_dtype" in lowered or "torch.jit.script" in lowered:
        category, fatal = "deprecated_but_operational", False
    elif "bfloat16" in lowered and ("float16" in lowered or "fp16" in lowered):
        category, fatal = "backend_dtype_compatibility", False
    elif "abi" in lowered or "undefined symbol" in lowered or "dll load failed" in lowered:
        category, fatal = "abi_or_version_incompatibility", True
    elif "config" in lowered and ("invalid" in lowered or "unsupported" in lowered):
        category, fatal = "invalid_config", True
    else:
        category, fatal = "unclassified", False
    return {"message": message, "classification": category, "fatal": fatal}


def _tensor_inventory(model: Any) -> dict[str, Any]:
    parameters = list(model.named_parameters())
    buffers = list(model.named_buffers())
    floating = [tensor for _, tensor in (*parameters, *buffers) if tensor.is_floating_point()]
    return {
        "parameter_count": sum(tensor.numel() for _, tensor in parameters),
        "buffer_count": sum(tensor.numel() for _, tensor in buffers),
        "parameter_devices": sorted({str(tensor.device) for _, tensor in parameters}),
        "buffer_devices": sorted({str(tensor.device) for _, tensor in buffers}),
        "floating_dtypes": sorted({str(tensor.dtype).removeprefix("torch.") for tensor in floating}),
        "all_parameters_cuda": bool(parameters) and all(tensor.device.type == "cuda" for _, tensor in parameters),
        "all_buffers_cuda": all(tensor.device.type == "cuda" for _, tensor in buffers),
    }


def _capture_warnings(operation: Callable[[], dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        payload = operation()
    classified = [
        {
            **_warning_classification(str(item.message)),
            "warning_category": item.category.__name__,
            "filename": item.filename,
            "lineno": item.lineno,
        }
        for item in caught
    ]
    return payload, classified


def environment_audit(config: Config) -> dict[str, Any]:
    dataset_profile = config.resolve_dataset_smoke_profile()
    python_environment = {
        "windows_version": platform.platform(),
        "python_version": platform.python_version(),
        "sys_executable": sys.executable,
        "sys_prefix": sys.prefix,
        "virtual_env": os.environ.get("VIRTUAL_ENV"),
        "conda_prefix": os.environ.get("CONDA_PREFIX"),
        "path": os.environ.get("PATH"),
        "pythonpath": os.environ.get("PYTHONPATH"),
        "which_python": shutil.which("python"),
        "project_venv": str((ROOT / ".venv").resolve()),
        "using_project_venv": Path(sys.executable).resolve().is_relative_to((ROOT / ".venv").resolve()),
    }
    packages = {
        label: _package_record(distribution, module)
        for label, (distribution, module) in PACKAGES.items()
    }
    gpu: dict[str, Any] = {
        "cuda_available": torch.cuda.is_available(),
        "torch_cuda_runtime": torch.version.cuda,
        "torch_cuda_driver_version": torch._C._cuda_getDriverVersion() if torch.cuda.is_available() and hasattr(torch._C, "_cuda_getDriverVersion") else None,
        "device_count": torch.cuda.device_count(),
    }
    if torch.cuda.is_available():
        properties = torch.cuda.get_device_properties(0)
        gpu.update({
            "device_name": torch.cuda.get_device_name(0),
            "compute_capability": list(torch.cuda.get_device_capability(0)),
            "total_memory_bytes": int(properties.total_memory),
        })
    nvidia_smi = _run([
        "nvidia-smi",
        "--query-gpu=name,driver_version,compute_cap,memory.total",
        "--format=csv,noheader",
    ])
    pip_check = _run([sys.executable, "-m", "pip", "check"])
    probes: dict[str, Any] = {}
    if torch.cuda.is_available():
        try:
            left = torch.tensor([[1.0, 2.0]], device="cuda")
            right = torch.tensor([[3.0], [4.0]], device="cuda")
            product = left @ right
            with torch.nn.attention.sdpa_kernel(torch.nn.attention.SDPBackend.MATH):
                query = torch.randn((1, 1, 2, 8), device="cuda", dtype=torch.float16)
                sdpa = torch.nn.functional.scaled_dot_product_attention(query, query, query)
            torch.cuda.synchronize()
            probes = {
                "cuda_tensor": {"device": str(left.device), "pass": left.device.type == "cuda"},
                "cuda_matmul": {"value": product.item(), "pass": product.item() == 11.0},
                "sdpa_math": {"device": str(sdpa.device), "shape": list(sdpa.shape), "pass": sdpa.device.type == "cuda"},
            }
        except Exception as error:
            probes = {"pass": False, "error": f"{type(error).__name__}: {error}", "traceback": traceback.format_exc()}
    allocator_env = dict(os.environ)
    allocator_env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,garbage_collection_threshold:0.5"
    allocator_probe = _run([
        sys.executable,
        "-X",
        "faulthandler",
        "-c",
        "import torch; x=torch.ones(1,device='cuda'); torch.cuda.synchronize(); print(x.device)",
    ], env=allocator_env)
    warning_lines = [
        line.strip()
        for line in (allocator_probe["stdout"] + "\n" + allocator_probe["stderr"]).splitlines()
        if "warning" in line.lower() or "expandable_segments" in line.lower()
    ]
    direct_api_scan = _run([
        "rg", "-n", "torch_dtype|torch\\.jit\\.script", "src", "scripts",
        "-g", "*.py",
    ])
    return {
        "audit_version": "ccdf.windows-environment.v1",
        "config_path": str(config.path),
        "config_sha256": sha256(config.path.read_bytes()).hexdigest(),
        "python_environment": python_environment,
        "gpu": gpu,
        "nvidia_smi": nvidia_smi,
        "packages": packages,
        "pip_check": pip_check,
        "cuda_probes": probes,
        "expandable_segments_reproduction": allocator_probe,
        "warnings": [_warning_classification(line) for line in warning_lines],
        "deprecated_project_api_scan": direct_api_scan,
        "trusted_settings": {
            "local_files_only": config.require("runtime.local_files_only"),
            "baseline_dtype": config.require("models.baseline.dtype"),
            "target_dtype": config.require("models.dflash.target.dtype"),
            "drafter_dtype": config.require("models.dflash.drafter.dtype"),
            "runtime_allocator": config.require("runtime.cuda_allocator_conf"),
            "dataset_allocator": dataset_profile.config.require("runtime.cuda_allocator_conf"),
            "dataset_effective_platform": dataset_profile.require("effective_platform"),
            "dataset_platform_override": dataset_profile.require(
                "effective_platform_override"
            ),
        },
    }


def _model_forward(model: Any, token_id: int = 1) -> dict[str, Any]:
    device = next(model.parameters()).device
    input_ids = torch.tensor([[token_id]], dtype=torch.long, device=device)
    with torch.inference_mode():
        output = model(input_ids=input_ids, use_cache=False)
    tensor = output.logits if hasattr(output, "logits") else output.last_hidden_state
    torch.cuda.synchronize()
    return {
        "input_device": str(input_ids.device),
        "output_device": str(tensor.device),
        "output_dtype": str(tensor.dtype).removeprefix("torch."),
        "output_shape": list(tensor.shape),
        "pass": input_ids.device.type == "cuda" and tensor.device.type == "cuda",
    }


def component_probe(config: Config, component: str) -> dict[str, Any]:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"

    def operation() -> dict[str, Any]:
        if component == "compressor":
            compressor = LLMLinguaCompressor(
                config.path_for("models.compressor.local_path"),
                device=str(config.require("models.compressor.device")),
                local_files_only=bool(config.require("runtime.local_files_only")),
                reserved_vram_budget_gib=float(config.require("models.compressor.reserved_budget_gib")),
            )
            try:
                protocol = ContextOnlyProtocol("alpha beta gamma", "Which token is first?", "Answer briefly.")
                result = compressor.compress(protocol, CompressionConfig(keep_rate=0.5, min_context_tokens=1))
                owners = compressor._owners()
                inventory = {
                    name: _tensor_inventory(owner)
                    for name, owner in owners
                    if callable(getattr(owner, "parameters", None))
                }
                return {
                    "model_inventory": inventory,
                    "device_audit": compressor.device_audit,
                    "model_contract": compressor.model_contract,
                    "inference": {
                        "original_tokens": result.original_tokens,
                        "compressed_tokens": result.compressed_tokens,
                        "coverage_rate": result.coverage_rate,
                        "pass": result.original_tokens > 0,
                    },
                }
            finally:
                compressor.close()
        if component == "baseline":
            engine = RuntimeEngine(config, condition="baseline")
            try:
                result = engine.generate("Reply with one word.", max_new_tokens=1)
                return {
                    "model_inventory": _tensor_inventory(engine.model),
                    "model_metadata": engine.model_metadata,
                    "inference": {
                        "generated_token_ids": result.generated_token_ids,
                        "runtime": result.runtime,
                        "pass": len(result.generated_token_ids) == 1,
                    },
                }
            finally:
                engine.close()
        from transformers import AutoModel, AutoModelForCausalLM

        _prepare_awq_compatibility()
        if component == "target":
            profile = config.model_profile("dflash")
            model = _load_pretrained(
                AutoModelForCausalLM,
                path=Path(profile["local_path"]),
                profile=profile,
                attention_backend=str(config.require("runtime.attention_backend")),
                local_files_only=bool(config.require("runtime.local_files_only")),
            )
            try:
                model.eval()
                return {
                    "model_inventory": _tensor_inventory(model),
                    "device_audit": assert_cuda_only(model, label="target probe"),
                    "requested_dtype": getattr(model, "_ccdf_requested_dtype", None),
                    "effective_dtypes": getattr(model, "_ccdf_effective_dtypes", []),
                    "inference": _model_forward(model),
                }
            finally:
                del model
                torch.cuda.empty_cache()
        if component == "drafter":
            profile = dict(config.require("models.dflash.drafter"))
            model = _load_pretrained(
                AutoModel,
                path=Path(profile["local_path"]),
                profile=profile,
                attention_backend=str(config.require("runtime.attention_backend")),
                local_files_only=bool(config.require("runtime.local_files_only")),
            )
            try:
                model.eval()
                device = next(model.parameters()).device
                dtype = next(model.parameters()).dtype
                positions = torch.arange(4, device=device).unsqueeze(0)
                noise = torch.randn((1, 2, int(model.config.hidden_size)), device=device, dtype=dtype)
                target_hidden = torch.randn(
                    (1, 2, len(model.target_layer_ids) * int(model.config.hidden_size)),
                    device=device,
                    dtype=dtype,
                )
                with torch.inference_mode():
                    output = model(
                        position_ids=positions,
                        noise_embedding=noise,
                        target_hidden=target_hidden,
                        use_cache=False,
                        is_causal=False,
                    )
                torch.cuda.synchronize()
                return {
                    "model_inventory": _tensor_inventory(model),
                    "device_audit": assert_cuda_only(model, label="drafter probe"),
                    "requested_dtype": getattr(model, "_ccdf_requested_dtype", None),
                    "effective_dtypes": getattr(model, "_ccdf_effective_dtypes", []),
                    "inference": {
                        "position_device": str(positions.device),
                        "noise_device": str(noise.device),
                        "target_hidden_device": str(target_hidden.device),
                        "output_device": str(output.device),
                        "output_dtype": str(output.dtype).removeprefix("torch."),
                        "output_shape": list(output.shape),
                        "pass": output.device.type == "cuda",
                    },
                }
            finally:
                del model
                torch.cuda.empty_cache()
        raise ValueError(f"unknown component: {component}")

    stdout, stderr = StringIO(), StringIO()
    started = time.perf_counter()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result, caught = _capture_warnings(operation)
        status, error = "PASS", None
    except Exception as exc:
        result, caught = {}, []
        status = "FAIL"
        error = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    textual_warnings = [
        line.strip() for line in stderr.getvalue().splitlines()
        if "warning" in line.lower() or "deprecated" in line.lower() or "bfloat16" in line.lower()
    ]
    return {
        "component": component,
        "status": status,
        "duration_seconds": time.perf_counter() - started,
        "offline_environment": {
            key: os.environ.get(key)
            for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE")
        },
        "local_files_only": bool(config.require("runtime.local_files_only")),
        "result": result,
        "warnings": caught + [_warning_classification(line) for line in textual_warnings],
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "error": error,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument("--phase", choices=("pre-fix", "post-fix"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--component",
        choices=("environment", "compressor", "baseline", "target", "drafter"),
        required=True,
    )
    args = parser.parse_args()
    config = load_config(args.config)
    output_dir = args.output_dir.resolve()
    started = time.perf_counter()
    if args.component == "environment":
        payload = environment_audit(config)
        payload["status"] = "PASS" if payload["pip_check"]["exit_code"] == 0 and all(
            probe.get("pass", False) for probe in payload["cuda_probes"].values()
        ) else "FAIL"
    else:
        payload = component_probe(config, args.component)
    payload.update({
        "phase": args.phase,
        "component": args.component,
        "config_sha256": sha256(config.path.read_bytes()).hexdigest(),
        "command_duration_seconds": time.perf_counter() - started,
    })
    output_path = output_dir / f"{args.component}.json"
    _write_json(output_path, payload)
    print(json.dumps({"path": str(output_path), "status": payload.get("status")}, sort_keys=True))
    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
