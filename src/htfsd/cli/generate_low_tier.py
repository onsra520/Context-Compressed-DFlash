"""Generate one response with the low-tier block-cycle path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback
from typing import Sequence

from htfsd.cli.error_report import write_runtime_error_report
from htfsd.config import DEFAULT_CONFIG_PATH, load_config
from htfsd.low_tier.generate import (
    LowTierGenerateResult,
    run_low_tier_generate,
    with_trace_path,
    write_generate_trace_json,
)
from htfsd.runtime.diagnostics import collect_environment_diagnostics
from htfsd.runtime.llama_cpp_backend import LlamaCppBackend
from htfsd.types import TextGenerationResult


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate with the low-tier block-cycle path.")
    parser.add_argument("--config", default=None, help=f"Config path; defaults to {DEFAULT_CONFIG_PATH}")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--draft-block-size", type=int, default=8)
    parser.add_argument("--max-cycles", type=int, default=4)
    parser.add_argument("--max-total-chars", type=int, default=None)
    parser.add_argument("--prompt-mode", choices=("raw", "instruction", "chat"), default="instruction")
    parser.add_argument("--capture-raw-output", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print the full result as JSON.")
    parser.add_argument("--write-trace", action="store_true")
    parser.add_argument("--output-dir", default=None)
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("--quiet", action="store_true", help="Prefer compact CLI output when possible.")
    verbosity.add_argument("--verbose", action="store_true", help="Allow verbose runtime output.")
    parser.add_argument("--fake", action="store_true", help="Use deterministic fake backends for CLI tests.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        validation_error = _validate_args(args)
        if validation_error:
            print(validation_error)
            return 2
        config = load_config(args.config)
        drafter_model = config.models["drafter"]
        verifier_model = config.models["verifier"]
        temperature = float(config.generation.temperature)

        if args.fake:
            drafter_backend = _RepeatingBackend("draft block")
            verifier_backend = _RepeatingBackend("verifier continuation")
        else:
            if not drafter_model.ok:
                print(f"drafter is not ready: {drafter_model.status}")
                return 1
            if not verifier_model.ok:
                print(f"verifier is not ready: {verifier_model.status}")
                return 1
            drafter_backend = LlamaCppBackend(
                model_path=drafter_model.discovered_model_file,
                n_ctx=config.runtime.n_ctx,
                n_gpu_layers=drafter_model.n_gpu_layers,
                seed=config.runtime.seed,
            )
            verifier_backend = LlamaCppBackend(
                model_path=verifier_model.discovered_model_file,
                n_ctx=config.runtime.n_ctx,
                n_gpu_layers=verifier_model.n_gpu_layers,
                seed=config.runtime.seed,
            )

        result = run_low_tier_generate(
            prompt=args.prompt,
            prompt_mode=args.prompt_mode,
            drafter_backend=drafter_backend,
            verifier_backend=verifier_backend,
            draft_block_size=args.draft_block_size,
            max_cycles=args.max_cycles,
            max_total_chars=args.max_total_chars,
            temperature=temperature,
            stop=None,
            capture_raw_output=args.capture_raw_output,
        )
        if args.write_trace:
            output_dir = Path(args.output_dir) if args.output_dir else config.repo_root / "logs/reports"
            trace_path = write_generate_trace_json(result=result, output_dir=output_dir)
            result = with_trace_path(result, _display_path(trace_path, config.repo_root))
        if args.json:
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        else:
            _print_text_result(result)
        return 0
    except Exception as error:  # pylint: disable=broad-exception-caught
        print(str(error))
        diagnostics = {}
        try:
            diagnostics = collect_environment_diagnostics(load_config(args.config))
        except Exception:
            pass
        write_runtime_error_report(
            summary="Low-tier generation failed.",
            command=["htfsd-generate-low-tier"],
            environment=diagnostics,
            model_context=diagnostics.get("models", {}) if isinstance(diagnostics, dict) else {},
            error_message=str(error),
            traceback_text=traceback.format_exc(),
            suspected_cause="The low-tier block-cycle generation path could not complete.",
            proposed_fix="Run python scripts/check_env.py and verify drafter plus verifier runtime policy first.",
            verification_steps=["python scripts/check_env.py", "python scripts/generate_low_tier.py --prompt 'hello'"],
        )
        return 1


def _print_text_result(result: LowTierGenerateResult) -> None:
    print("RESPONSE:")
    print(result.response_text)
    print()
    print("METRICS:")
    print(f"trace_type: {result.trace_type}")
    print(f"prompt_mode: {result.prompt_mode}")
    print(f"draft_block_size: {result.draft_block_size}")
    print(f"max_cycles: {result.max_cycles}")
    print(f"total_cycles: {result.total_cycles}")
    print(f"bridge_valid_block_count: {result.bridge_valid_block_count}")
    print(f"bridge_rejected_block_count: {result.bridge_rejected_block_count}")
    print(f"cycle_fallback_count: {result.cycle_fallback_count}")
    for key in (
        "total_wall_time_seconds",
        "drafter_latency_seconds_total",
        "verifier_latency_seconds_total",
        "bridge_latency_seconds_total",
        "output_chars",
        "response_chars",
        "response_cleanup_applied",
    ):
        print(f"{key}: {result.metrics[key]}")
    if result.trace_path:
        print(f"trace_path: {result.trace_path}")


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _validate_args(args) -> str | None:  # type: ignore[no-untyped-def]
    if not args.prompt.strip():
        return "prompt must not be blank"
    if args.draft_block_size <= 0:
        return "draft-block-size must be greater than 0"
    if args.max_cycles <= 0:
        return "max-cycles must be greater than 0"
    if args.max_total_chars is not None and args.max_total_chars <= 0:
        return "max-total-chars must be greater than 0"
    return None


class _RepeatingBackend:
    def __init__(self, text: str) -> None:
        self.text = text

    def generate_text(self, prompt: str, *, max_tokens: int, temperature: float, stop=None) -> TextGenerationResult:
        return TextGenerationResult(text=self.text, completion_tokens=max_tokens)

    def generate_chat(self, messages: list[dict[str, str]], *, max_tokens: int, temperature: float, stop=None):
        return TextGenerationResult(text=self.text, completion_tokens=max_tokens)


if __name__ == "__main__":
    sys.exit(main())
