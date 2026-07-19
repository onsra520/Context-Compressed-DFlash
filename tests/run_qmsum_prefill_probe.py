"""Single-process baseline AWQ prefill plus one incremental decode probe."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import time
from typing import Any

import psutil
import torch
from torch.nn.attention import SDPBackend, sdpa_kernel
from transformers import DynamicCache

from ccdf.benchmark.dataset_smoke import _protocol_for
from ccdf.config import load_config
from ccdf.runtime.engine import RuntimeEngine


def _append(path: Path, event: str, **fields: Any) -> None:
    record = {
        "event": event,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
    print(json.dumps(record, sort_keys=True), flush=True)


def _backend_context(name: str):
    backend = {
        "flash": SDPBackend.FLASH_ATTENTION,
        "math": SDPBackend.MATH,
        "efficient": SDPBackend.EFFICIENT_ATTENTION,
    }.get(name)
    return nullcontext() if backend is None else sdpa_kernel(backend, set_priority=True)


def _observed_backend(events: list[str]) -> str:
    lowered = [event.lower() for event in events]
    if any("flash_attention" in event or "flash_attn" in event for event in lowered):
        return "flash"
    if any("efficient_attention" in event or "fmha" in event for event in lowered):
        return "efficient"
    if any("scaled_dot_product_attention_math" in event or "_safe_softmax" in event for event in lowered):
        return "math"
    return "other"


def _top_cuda_operators(profiler: Any, limit: int = 30) -> list[dict[str, Any]]:
    rows = []
    for event in profiler.key_averages():
        cuda_total = float(getattr(event, "self_device_time_total", 0.0))
        if cuda_total <= 0:
            cuda_total = float(getattr(event, "self_cuda_time_total", 0.0))
        if cuda_total <= 0:
            continue
        rows.append({
            "operator": event.key,
            "self_device_time_us": cuda_total,
            "device_time_total_us": float(getattr(event, "device_time_total", 0.0)),
            "count": int(event.count),
        })
    return sorted(rows, key=lambda row: row["self_device_time_us"], reverse=True)[:limit]


def _forward(
    model: Any,
    input_ids: torch.Tensor,
    *,
    mask_mode: str,
    forward_path: str,
    use_cache: bool,
) -> tuple[Any, DynamicCache | None]:
    mask = torch.ones_like(input_ids) if mask_mode == "ones" else None
    if forward_path == "generate":
        generated = model.generate(
            input_ids,
            attention_mask=mask,
            max_new_tokens=1,
            do_sample=False,
            use_cache=use_cache,
            pad_token_id=getattr(model.config, "eos_token_id", None),
        )
        return generated, None
    cache = DynamicCache() if use_cache else None
    kwargs: dict[str, Any] = {
        "attention_mask": mask,
        "past_key_values": cache,
        "use_cache": use_cache,
        "logits_to_keep": 1,
        "output_hidden_states": False,
    }
    if forward_path == "project":
        kwargs["position_ids"] = torch.arange(
            input_ids.shape[1], device=input_ids.device
        ).unsqueeze(0)
    output = model(input_ids, **kwargs)
    return output, cache


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--backend", choices=("auto", "flash", "math", "efficient"), required=True)
    parser.add_argument("--mask", choices=("none", "ones"), required=True)
    parser.add_argument(
        "--forward-path", choices=("project", "standard", "generate"), required=True
    )
    parser.add_argument("--use-cache", choices=("true", "false"), default="true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--memory-snapshot", type=Path)
    parser.add_argument("--progress", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    use_cache = args.use_cache == "true"
    started = time.perf_counter()
    payload: dict[str, Any] = {
        "status": "ERROR",
        "length": args.length,
        "backend_requested": args.backend,
        "mask_mode": args.mask,
        "forward_path": args.forward_path,
        "use_cache": use_cache,
    }
    engine: RuntimeEngine | None = None
    try:
        config = load_config("config.yml").resolve_dataset_smoke_profile()
        rows = [
            json.loads(line)
            for line in Path(config.settings["cohorts"]["qmsum"])
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        row = next(
            item for item in rows
            if item["fixture_id"] == "qmsum_test_meeting0015_specific_05_8afeb1a1"
        )
        protocol = _protocol_for(row, config.settings)
        prompt = protocol.render(protocol.context)
        load_start = time.perf_counter()
        engine = RuntimeEngine(config.config, condition="baseline")
        torch.cuda.synchronize()
        model_load_seconds = time.perf_counter() - load_start
        _append(
            args.progress,
            "model_loaded",
            model_load_seconds=model_load_seconds,
            torch_allocated_bytes=torch.cuda.memory_allocated(),
            torch_reserved_bytes=torch.cuda.memory_reserved(),
            host_working_set_bytes=psutil.Process().memory_info().rss,
        )

        tokenize_start = time.perf_counter()
        full_input = engine.encode_prompt(prompt)
        torch.cuda.synchronize()
        tokenize_seconds = time.perf_counter() - tokenize_start
        full_count = int(full_input.shape[1])
        if full_count != 6289:
            raise RuntimeError(f"expected rendered input 6289 tokens, found {full_count}")
        if args.length > full_count:
            raise ValueError(f"probe length {args.length} exceeds rendered input {full_count}")
        input_ids = full_input[:, : args.length].contiguous()
        del full_input
        _append(
            args.progress,
            "tokenize_complete",
            token_count=args.length,
            full_rendered_token_count=full_count,
            tokenize_seconds=tokenize_seconds,
            chat_template_calls=1,
        )

        warmup_ids = input_ids[:, : min(128, args.length)]
        # Warm-up is deliberately short and uses normal auto dispatch. Backend
        # forcing applies only to the measured request so a backend that rejects
        # the 128-token warm-up is still tested on the requested input shape.
        with torch.inference_mode(), _backend_context("auto"):
            _forward(
                engine.model,
                warmup_ids,
                mask_mode=args.mask,
                forward_path=args.forward_path,
                use_cache=use_cache,
            )
            torch.cuda.synchronize()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        if args.memory_snapshot is not None:
            torch.cuda.memory._record_memory_history(max_entries=100000)
        torch.cuda.synchronize()

        _append(args.progress, "prefill_start", token_count=args.length)
        prefill_started = time.perf_counter()
        activities = [
            torch.profiler.ProfilerActivity.CPU,
            torch.profiler.ProfilerActivity.CUDA,
        ]
        profiler_context = (
            torch.profiler.profile(
                activities=activities,
                record_shapes=False,
                profile_memory=True,
                with_stack=False,
            )
            if args.profile else nullcontext()
        )
        with torch.inference_mode(), _backend_context(args.backend), profiler_context as profiler:
            output, cache = _forward(
                engine.model,
                input_ids,
                mask_mode=args.mask,
                forward_path=args.forward_path,
                use_cache=use_cache,
            )
            torch.cuda.synchronize()
        prefill_seconds = time.perf_counter() - prefill_started
        first_token = (
            int(output[0, -1].item())
            if args.forward_path == "generate"
            else int(output.logits[0, -1].argmax().item())
        )
        first_token_latency_seconds = time.perf_counter() - prefill_started
        _append(
            args.progress,
            "prefill_complete",
            prefill_seconds=prefill_seconds,
            first_token_latency_seconds=first_token_latency_seconds,
            first_token_id=first_token,
        )

        decode_seconds = None
        if use_cache and args.forward_path != "generate":
            _append(args.progress, "decode_start", token_count=1)
            decode_started = time.perf_counter()
            token = torch.tensor([[first_token]], device=input_ids.device, dtype=torch.long)
            decode_mask = (
                torch.ones((1, args.length + 1), device=input_ids.device, dtype=torch.long)
                if args.mask == "ones" else None
            )
            decode_kwargs: dict[str, Any] = {
                "attention_mask": decode_mask,
                "past_key_values": cache,
                "use_cache": True,
                "logits_to_keep": 1,
                "output_hidden_states": False,
            }
            if args.forward_path == "project":
                decode_kwargs["position_ids"] = torch.tensor(
                    [[args.length]], device=input_ids.device
                )
            with torch.inference_mode(), _backend_context(args.backend):
                decode_output = engine.model(token, **decode_kwargs)
                torch.cuda.synchronize()
            decode_seconds = time.perf_counter() - decode_started
            second_token = int(decode_output.logits[0, -1].argmax().item())
            _append(
                args.progress,
                "decode_complete",
                decode_seconds=decode_seconds,
                first_token_id=first_token,
                second_token_id=second_token,
            )

        events: list[str] = []
        top_cuda: list[dict[str, Any]] = []
        if args.profile:
            events = sorted({event.key for event in profiler.key_averages()})
            top_cuda = _top_cuda_operators(profiler)
            if args.trace is not None:
                args.trace.parent.mkdir(parents=True, exist_ok=True)
                profiler.export_chrome_trace(str(args.trace))
        observed = _observed_backend(events) if args.profile else "not_profiled"
        if args.backend != "auto" and args.profile and observed != args.backend:
            raise RuntimeError(
                f"forced backend {args.backend} executed {observed}; silent fallback rejected"
            )
        if args.memory_snapshot is not None:
            args.memory_snapshot.parent.mkdir(parents=True, exist_ok=True)
            torch.cuda.memory._dump_snapshot(str(args.memory_snapshot))
            torch.cuda.memory._record_memory_history(enabled=None)

        payload.update({
            "status": "PASS",
            "model_load_seconds": model_load_seconds,
            "tokenize_seconds": tokenize_seconds,
            "chat_template_calls": 1,
            "full_rendered_token_count": full_count,
            "prefill_seconds": prefill_seconds,
            "first_token_latency_seconds": first_token_latency_seconds,
            "decode_seconds": decode_seconds,
            "first_token_id": first_token,
            "backend_observed": observed,
            "profiler_events": [
                event for event in events
                if any(marker in event.lower() for marker in (
                    "attention", "scaled_dot_product", "flash", "efficient",
                    "gemm", "matmul", "triton", "awq",
                ))
            ],
            "top_cuda_operators": top_cuda,
            "torch": {
                "allocated_bytes": torch.cuda.memory_allocated(),
                "reserved_bytes": torch.cuda.memory_reserved(),
                "max_allocated_bytes": torch.cuda.max_memory_allocated(),
                "max_reserved_bytes": torch.cuda.max_memory_reserved(),
            },
            "host_working_set_bytes": psutil.Process().memory_info().rss,
            "versions": {
                "python": platform.python_version(),
                "torch": torch.__version__,
                "transformers": __import__("transformers").__version__,
                "cuda_runtime": torch.version.cuda,
                "device": torch.cuda.get_device_name(0),
            },
            "duration_seconds": time.perf_counter() - started,
        })
    except torch.OutOfMemoryError as exc:
        payload.update({
            "status": "OOM",
            "error": f"{type(exc).__name__}: {exc}",
            "torch": {
                "allocated_bytes": torch.cuda.memory_allocated() if torch.cuda.is_available() else None,
                "reserved_bytes": torch.cuda.memory_reserved() if torch.cuda.is_available() else None,
                "max_allocated_bytes": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None,
                "max_reserved_bytes": torch.cuda.max_memory_reserved() if torch.cuda.is_available() else None,
            },
            "host_working_set_bytes": psutil.Process().memory_info().rss,
            "duration_seconds": time.perf_counter() - started,
        })
    except Exception as exc:
        payload.update({
            "status": "REJECTED" if args.backend != "auto" else "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
            "host_working_set_bytes": psutil.Process().memory_info().rss,
            "duration_seconds": time.perf_counter() - started,
        })
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if engine is not None:
            engine.close()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if payload["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
