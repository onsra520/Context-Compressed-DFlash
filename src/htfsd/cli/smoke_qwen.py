"""Smoke test for the Qwen GGUF drafter."""

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
from htfsd.token_tier.qwen_drafter import QwenTextDrafter


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a tiny Qwen GGUF smoke test.")
    parser.add_argument("--config", default=None, help=f"Config path; defaults to {DEFAULT_CONFIG_PATH}")
    parser.add_argument("--prompt", default="Write one short sentence about speculative decoding.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config = load_config(args.config)
        model = config.models["qwen_drafter"]
        if not model.ok:
            print(f"qwen_drafter is not ready: {model.status}")
            return 1
        backend = LlamaCppBackend(
            model_path=model.discovered_model_file,
            n_ctx=config.runtime.n_ctx,
            n_gpu_layers=config.runtime.n_gpu_layers,
            seed=config.runtime.seed,
        )
        drafter = QwenTextDrafter(backend)
        start = time.perf_counter()
        text = drafter.draft(
            args.prompt,
            max_tokens=config.generation.max_tokens,
            temperature=config.generation.temperature,
        )
        elapsed = time.perf_counter() - start
        print("Qwen smoke: ok")
        print(f"model_file: {_display_path(model.discovered_model_file, config.repo_root)}")
        print(f"latency_seconds: {elapsed:.6f}")
        print(f"draft_text:{text}")
        return 0
    except Exception as error:  # pylint: disable=broad-exception-caught
        print(str(error))
        diagnostics = {}
        try:
            diagnostics = collect_environment_diagnostics(load_config(args.config))
        except Exception:
            pass
        write_runtime_error_report(
            summary="Qwen smoke test failed.",
            command=["htfsd-smoke-qwen", *([] if args.config is None else ["--config", args.config])],
            environment=diagnostics,
            model_context=diagnostics.get("models", {}) if isinstance(diagnostics, dict) else {},
            error_message=str(error),
            traceback_text=traceback.format_exc(),
            suspected_cause="The Qwen GGUF model could not be loaded or generated from.",
            proposed_fix="Run python scripts/check_env.py and verify models/qwen3-0.6b contains exactly one .gguf file.",
            verification_steps=["python scripts/check_env.py", "python scripts/smoke_qwen.py"],
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
