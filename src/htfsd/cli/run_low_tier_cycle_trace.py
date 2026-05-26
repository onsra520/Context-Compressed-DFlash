"""Run a low-tier block-cycle trace for D-Flash shape alignment."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path
from typing import Sequence

from htfsd.cli.error_report import write_runtime_error_report
from htfsd.config import DEFAULT_CONFIG_PATH, load_config
from htfsd.metrics.cycle_trace_schema import write_cycle_trace_json
from htfsd.metrics.prompt_sets import (
    DEFAULT_TRACE_PROMPT_SET,
    get_trace_prompt_set,
    trace_prompt_set_ids,
)
from htfsd.runtime.diagnostics import collect_environment_diagnostics
from htfsd.runtime.llama_cpp_backend import LlamaCppBackend
from htfsd.text_bridge.cycle_trace import run_low_tier_cycle_trace_for_prompt
from htfsd.types import TextGenerationResult


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a low-tier block-cycle trace.")
    parser.add_argument("--config", default=None, help=f"Config path; defaults to {DEFAULT_CONFIG_PATH}")
    parser.add_argument("--prompt-set", default=DEFAULT_TRACE_PROMPT_SET.prompt_set_id, choices=trace_prompt_set_ids())
    parser.add_argument("--prompt", action="append", default=None)
    parser.add_argument("--prompt-mode", choices=("raw", "chat"), default="raw")
    parser.add_argument("--draft-block-size", type=int, default=8)
    parser.add_argument("--max-cycles", type=int, default=4)
    parser.add_argument("--max-total-tokens", type=int, default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--capture-raw-output", action="store_true")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--fake", action="store_true", help="Use deterministic fake backends for CLI tests.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config = load_config(args.config)
        diagnostics = collect_environment_diagnostics(config)
        drafter_model = config.models["drafter"]
        verifier_model = config.models["verifier"]
        prompt_set = get_trace_prompt_set(args.prompt_set)
        prompts = tuple(args.prompt) if args.prompt else tuple(prompt.text for prompt in prompt_set.prompts)
        prompt_ids = None if args.prompt else tuple(prompt.prompt_id for prompt in prompt_set.prompts)
        prompt_set_id = "custom-cli-prompts" if args.prompt else prompt_set.prompt_set_id
        temperature = float(args.temperature if args.temperature is not None else config.generation.temperature)

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

        drafter_diagnostics = _model_diagnostics(diagnostics, "drafter")
        verifier_diagnostics = _model_diagnostics(diagnostics, "verifier")
        records = [
            run_low_tier_cycle_trace_for_prompt(
                prompt=prompt,
                prompt_id=prompt_ids[index] if prompt_ids else f"cycle-{index + 1:03d}",
                prompt_set_id=prompt_set_id,
                prompt_mode=args.prompt_mode,
                drafter_backend=drafter_backend,
                verifier_backend=verifier_backend,
                draft_block_size=args.draft_block_size,
                max_cycles=args.max_cycles,
                max_total_tokens=args.max_total_tokens,
                temperature=temperature,
                stop=None,
                capture_raw_output=args.capture_raw_output,
                drafter_model_file=str(drafter_model.discovered_model_file)
                if drafter_model.discovered_model_file
                else None,
                verifier_model_file=str(verifier_model.discovered_model_file)
                if verifier_model.discovered_model_file
                else None,
                drafter_device_status=drafter_diagnostics.get("device_status"),
                verifier_device_status=verifier_diagnostics.get("device_status"),
            )
            for index, prompt in enumerate(prompts)
        ]
        output_dir = Path(args.output_dir) if args.output_dir else config.repo_root / "logs/reports"
        trace_path = write_cycle_trace_json(
            records=records,
            output_dir=output_dir,
            metadata={
                "trace_type": "low_tier_cycle_trace",
                "prompt_set_id": prompt_set_id,
                "prompt_count": len(records),
                "prompt_mode": args.prompt_mode,
                "capture_raw_output": args.capture_raw_output,
                "draft_block_size": args.draft_block_size,
                "max_cycles": args.max_cycles,
                "max_total_tokens": args.max_total_tokens,
                "runtime_policy": "drafter_cpu_verifier_cuda",
                "drafter_device_status": drafter_diagnostics.get("device_status"),
                "verifier_device_status": verifier_diagnostics.get("device_status"),
            },
        )
        print("low-tier cycle trace: ok")
        print(f"trace_file: {_display_path(trace_path, config.repo_root)}")
        print(f"trace_records: {len(records)}")
        print(f"total_cycles: {sum(record.total_cycles for record in records)}")
        print(f"bridge_valid_block_count: {sum(record.bridge_valid_block_count for record in records)}")
        print(f"bridge_rejected_block_count: {sum(record.bridge_rejected_block_count for record in records)}")
        print(f"cycle_fallback_count: {sum(record.cycle_fallback_count for record in records)}")
        return 0
    except Exception as error:  # pylint: disable=broad-exception-caught
        print(str(error))
        diagnostics = {}
        try:
            diagnostics = collect_environment_diagnostics(load_config(args.config))
        except Exception:
            pass
        write_runtime_error_report(
            summary="Low-tier cycle trace failed.",
            command=["htfsd-run-low-tier-cycle-trace"],
            environment=diagnostics,
            model_context=diagnostics.get("models", {}) if isinstance(diagnostics, dict) else {},
            error_message=str(error),
            traceback_text=traceback.format_exc(),
            suspected_cause="The low-tier block-cycle trace could not be generated.",
            proposed_fix="Run python scripts/check_env.py and verify drafter plus verifier runtime policy first.",
            verification_steps=["python scripts/check_env.py", "python scripts/run_low_tier_cycle_trace.py"],
        )
        return 1


def _model_diagnostics(diagnostics: dict, role: str) -> dict:
    models = diagnostics.get("models", {})
    aliases = {"drafter": "qwen_drafter", "verifier": "gemma_e2b", "target": "gemma_e4b"}
    return models.get(role) or models.get(aliases.get(role, role), {})


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


class _RepeatingBackend:
    def __init__(self, text: str) -> None:
        self.text = text

    def generate_text(self, prompt: str, *, max_tokens: int, temperature: float, stop=None) -> TextGenerationResult:
        return TextGenerationResult(text=self.text, completion_tokens=max_tokens)

    def generate_chat(self, messages: list[dict[str, str]], *, max_tokens: int, temperature: float, stop=None):
        return TextGenerationResult(text=self.text, completion_tokens=max_tokens)


if __name__ == "__main__":
    sys.exit(main())
