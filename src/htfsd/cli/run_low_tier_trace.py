"""Controlled low-tier runtime trace command."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path
from typing import Sequence

from htfsd.cli.error_report import write_runtime_error_report
from htfsd.config import DEFAULT_CONFIG_PATH, load_config
from htfsd.metrics.run_trace import (
    DEFAULT_TRACE_PROMPTS,
    run_controlled_low_tier_trace,
    write_trace_json,
)
from htfsd.runtime.diagnostics import collect_environment_diagnostics
from htfsd.runtime.llama_cpp_backend import LlamaCppBackend


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a controlled low-tier runtime trace.")
    parser.add_argument("--config", default=None, help=f"Config path; defaults to {DEFAULT_CONFIG_PATH}")
    parser.add_argument(
        "--prompt",
        action="append",
        default=None,
        help="Prompt to trace. May be passed more than once; defaults to the fixed validation set.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config = load_config(args.config)
        qwen_model = config.models["qwen_drafter"]
        gemma_model = config.models["gemma_e2b"]
        if not qwen_model.ok:
            print(f"qwen_drafter is not ready: {qwen_model.status}")
            return 1
        if not gemma_model.ok:
            print(f"gemma_e2b is not ready: {gemma_model.status}")
            return 1

        diagnostics = collect_environment_diagnostics(config)
        qwen_backend = LlamaCppBackend(
            model_path=qwen_model.discovered_model_file,
            n_ctx=config.runtime.n_ctx,
            n_gpu_layers=qwen_model.n_gpu_layers,
            seed=config.runtime.seed,
        )
        gemma_backend = LlamaCppBackend(
            model_path=gemma_model.discovered_model_file,
            n_ctx=config.runtime.n_ctx,
            n_gpu_layers=gemma_model.n_gpu_layers,
            seed=config.runtime.seed,
        )
        prompts = tuple(args.prompt) if args.prompt else DEFAULT_TRACE_PROMPTS
        records = run_controlled_low_tier_trace(
            prompts=prompts,
            config=config,
            diagnostics=diagnostics,
            qwen_backend=qwen_backend,
            gemma_backend=gemma_backend,
        )
        trace_path = write_trace_json(
            records=records,
            output_dir=config.repo_root / "logs/reports",
            metadata={
                "config": _display_path(config.config_path, config.repo_root),
                "runtime_policy": "qwen_cpu_gemma_cuda",
                "raw_outputs_included": False,
            },
        )

        total_fallbacks = sum(int(record["fallback_count"]) for record in records)
        print("Low-tier trace: ok")
        print(f"trace_file: {_display_path(trace_path, config.repo_root)}")
        print(f"trace_records: {len(records)}")
        print(f"fallback_count: {total_fallbacks}")
        print(f"qwen_device_status: {diagnostics['models']['qwen_drafter']['device_status']}")
        print(f"gemma_device_status: {diagnostics['models']['gemma_e2b']['device_status']}")
        return 0
    except Exception as error:  # pylint: disable=broad-exception-caught
        print(str(error))
        diagnostics = {}
        try:
            diagnostics = collect_environment_diagnostics(load_config(args.config))
        except Exception:
            pass
        write_runtime_error_report(
            summary="Controlled low-tier runtime trace failed.",
            command=["htfsd-run-low-tier-trace", *([] if args.config is None else ["--config", args.config])],
            environment=diagnostics,
            model_context=diagnostics.get("models", {}) if isinstance(diagnostics, dict) else {},
            error_message=str(error),
            traceback_text=traceback.format_exc(),
            suspected_cause="One of the low-tier GGUF models could not be loaded or traced.",
            proposed_fix="Run python scripts/check_env.py and verify Qwen CPU plus Gemma CUDA policy first.",
            verification_steps=["python scripts/check_env.py", "python scripts/run_low_tier_trace.py"],
        )
        return 1


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
