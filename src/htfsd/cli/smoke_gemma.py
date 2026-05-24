"""Smoke test for the Gemma E2B GGUF verifier/fallback model."""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path
from typing import Sequence

from htfsd.cli.error_report import write_runtime_error_report
from htfsd.config import DEFAULT_CONFIG_PATH, load_config
from htfsd.runtime.diagnostics import collect_environment_diagnostics
from htfsd.runtime.llama_cpp_backend import LlamaCppBackend


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a tiny Gemma E2B GGUF smoke test.")
    parser.add_argument("--config", default=None, help=f"Config path; defaults to {DEFAULT_CONFIG_PATH}")
    parser.add_argument("--prompt", default="Write one short sentence about verification.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config = load_config(args.config)
        model = config.models["gemma_e2b"]
        if not model.ok:
            print(f"gemma_e2b is not ready: {model.status}")
            return 1
        backend = LlamaCppBackend(
            model_path=model.discovered_model_file,
            n_ctx=config.runtime.n_ctx,
            n_gpu_layers=config.runtime.n_gpu_layers,
            seed=config.runtime.seed,
        )
        start = time.perf_counter()
        result = backend.generate_text(
            args.prompt,
            max_tokens=config.generation.max_tokens,
            temperature=config.generation.temperature,
        )
        elapsed = time.perf_counter() - start
        print("Gemma E2B smoke: ok")
        print(f"model_file: {_display_path(model.discovered_model_file, config.repo_root)}")
        print(f"latency_seconds: {elapsed:.6f}")
        print(f"generated_text:{result.text}")
        return 0
    except Exception as error:  # pylint: disable=broad-exception-caught
        print(str(error))
        diagnostics = {}
        try:
            diagnostics = collect_environment_diagnostics(load_config(args.config))
        except Exception:
            pass
        write_runtime_error_report(
            summary="Gemma E2B smoke test failed.",
            command=["htfsd-smoke-gemma", *([] if args.config is None else ["--config", args.config])],
            environment=diagnostics,
            model_context=diagnostics.get("models", {}) if isinstance(diagnostics, dict) else {},
            error_message=str(error),
            traceback_text=traceback.format_exc(),
            suspected_cause="The Gemma E2B GGUF model could not be loaded or generated from.",
            proposed_fix="Run python scripts/check_env.py and verify models/gemma-4-e2b-it contains exactly one .gguf file.",
            verification_steps=["python scripts/check_env.py", "python scripts/smoke_gemma.py"],
        )
        return 1


def _display_path(path: Path | None, repo_root: Path) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
