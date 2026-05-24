"""Smoke test for the Qwen GGUF to Gemma E2B GGUF pair path."""

from __future__ import annotations

import argparse
import sys
import traceback
from typing import Sequence

from htfsd.cli.error_report import write_runtime_error_report
from htfsd.config import DEFAULT_CONFIG_PATH, load_config
from htfsd.runtime.diagnostics import collect_environment_diagnostics
from htfsd.runtime.llama_cpp_backend import LlamaCppBackend
from htfsd.text_bridge.pair_smoke import run_pair_smoke


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a tiny Qwen to Gemma E2B GGUF pair smoke test.")
    parser.add_argument("--config", default=None, help=f"Config path; defaults to {DEFAULT_CONFIG_PATH}")
    parser.add_argument("--prompt", default="Write one short sentence about hierarchical decoding.")
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
        qwen_backend = LlamaCppBackend(
            model_path=qwen_model.discovered_model_file,
            n_ctx=config.runtime.n_ctx,
            n_gpu_layers=config.runtime.n_gpu_layers,
            seed=config.runtime.seed,
        )
        gemma_backend = LlamaCppBackend(
            model_path=gemma_model.discovered_model_file,
            n_ctx=config.runtime.n_ctx,
            n_gpu_layers=config.runtime.n_gpu_layers,
            seed=config.runtime.seed,
        )
        result = run_pair_smoke(
            prompt=args.prompt,
            qwen_backend=qwen_backend,
            gemma_backend=gemma_backend,
            max_tokens=config.generation.max_tokens,
            temperature=config.generation.temperature,
        )
        print("Pair smoke: ok")
        print(f"bridge_status: {result.bridge_status}")
        print(f"rejection_reason: {result.rejection_reason}")
        print(f"fallback_count: {result.fallback_count}")
        print(f"draft_valid_count: {result.draft_valid_count}")
        print(f"draft_rejected_count: {result.draft_rejected_count}")
        print(f"latency_seconds: {result.latency_seconds:.6f}")
        print(f"qwen_decode_tokens_per_second: {result.qwen_decode_tokens_per_second}")
        print(f"gemma_decode_tokens_per_second: {result.gemma_decode_tokens_per_second}")
        print(f"gemma_output_text:{result.gemma_output_text}")
        return 0
    except Exception as error:  # pylint: disable=broad-exception-caught
        print(str(error))
        diagnostics = {}
        try:
            diagnostics = collect_environment_diagnostics(load_config(args.config))
        except Exception:
            pass
        write_runtime_error_report(
            summary="Qwen to Gemma E2B pair smoke test failed.",
            command=["htfsd-smoke-pair", *([] if args.config is None else ["--config", args.config])],
            environment=diagnostics,
            model_context=diagnostics.get("models", {}) if isinstance(diagnostics, dict) else {},
            error_message=str(error),
            traceback_text=traceback.format_exc(),
            suspected_cause="One of the required low-tier GGUF models could not be loaded or generated from.",
            proposed_fix="Run python scripts/check_env.py and verify Qwen and Gemma E2B model directories each contain exactly one .gguf file.",
            verification_steps=["python scripts/check_env.py", "python scripts/smoke_gguf_pair.py"],
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
