"""Observe configured SDPA policy, allowed backends, and a representative CUDA kernel."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import torch
from torch.nn.functional import scaled_dot_product_attention

from ccdf.config import load_config
from ccdf.runtime.determinism import configure_determinism


def _observed_backend(events: list[str]) -> str | None:
    lowered = [event.lower() for event in events]
    if any("flash_attention" in event or "flash" in event for event in lowered):
        return "flash"
    if any("efficient_attention" in event or "fmha" in event for event in lowered):
        return "memory_efficient"
    if any("scaled_dot_product_attention_math" in event for event in lowered):
        return "math"
    return None


def _profile(policy: str, runtime: dict[str, Any]) -> dict[str, Any]:
    state = configure_determinism(
        seed=int(runtime["seed"]),
        deterministic=bool(runtime["deterministic"]),
        allow_tf32=bool(runtime["allow_tf32"]),
        matmul_precision=str(runtime["matmul_precision"]),
        sdpa_kernel=policy,
    )
    query = torch.randn((1, 8, 64, 64), device="cuda", dtype=torch.float16)
    torch.cuda.synchronize()
    with torch.profiler.profile(
        activities=[torch.profiler.ProfilerActivity.CPU, torch.profiler.ProfilerActivity.CUDA]
    ) as profiler:
        scaled_dot_product_attention(query, query, query, is_causal=True)
        torch.cuda.synchronize()
    events = sorted(
        {
            event.key
            for event in profiler.key_averages()
            if any(
                marker in event.key.lower()
                for marker in ("attention", "scaled_dot_product", "fmha", "flash")
            )
        }
    )
    observed = _observed_backend(events)
    return {
        "configured_policy": policy,
        "configured_attention_backend": runtime["attention_backend"],
        "effective_allowed_backends": state["effective_allowed_backends"],
        "backend_observed": observed,
        "backend_observed_from_profiler": observed is not None,
        "profiler_events": events,
        "probe_shape": [1, 8, 64, 64],
        "probe_dtype": "float16",
        "interpretation": (
            "Profiler events are actual execution evidence for this representative probe only; "
            "enabled backend flags alone are not treated as execution evidence."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the SDPA runtime probe")
    active = config.resolve_active_protocol_profile()
    dataset = config.resolve_dataset_smoke_profile()
    canonical_runtime = dict(config.require("runtime"))
    active_runtime = dict(active.config.require("runtime"))
    if active_runtime["sdpa_kernel"] != dataset.config.require("runtime.sdpa_kernel"):
        raise RuntimeError("active protocol and dataset SDPA policies differ")
    payload = {
        "config_path": str(config.path),
        "config_sha256": hashlib.sha256(config.path.read_bytes()).hexdigest(),
        "canonical_profile": _profile(str(canonical_runtime["sdpa_kernel"]), canonical_runtime),
        "active_profile": _profile(str(active_runtime["sdpa_kernel"]), active_runtime),
        "resolved_profiles": {
            "canonical": "root runtime",
            "active_protocol": active.name,
            "dataset": dataset.name,
        },
    }
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
