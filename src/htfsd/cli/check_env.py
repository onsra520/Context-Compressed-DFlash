"""Environment check command."""

from __future__ import annotations

import argparse
from pathlib import Path
from pprint import pformat
import sys
import traceback
from typing import Sequence

from htfsd.config import DEFAULT_CONFIG_PATH, load_config
from htfsd.runtime.diagnostics import collect_environment_diagnostics
from htfsd.cli.error_report import write_runtime_error_report

REQUIRED_LOW_TIER_MODELS = ("qwen_drafter", "gemma_e2b")


def main(argv: Sequence[str] | None = None) -> int:
    """Run environment and model-discovery checks."""

    parser = argparse.ArgumentParser(description="Check HTFS-Decoding GGUF environment.")
    parser.add_argument("--config", default=None, help=f"Config path; defaults to {DEFAULT_CONFIG_PATH}")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config = load_config(args.config)
        diagnostics = collect_environment_diagnostics(config)
    except Exception as error:  # pylint: disable=broad-exception-caught
        message = str(error)
        print(message)
        write_runtime_error_report(
            summary="Environment check failed before diagnostics completed.",
            command=["htfsd-check-env", *([] if args.config is None else ["--config", args.config])],
            environment={},
            model_context={},
            error_message=message,
            traceback_text=traceback.format_exc(),
            suspected_cause="The default config file is missing or malformed.",
            proposed_fix="Create configs/local.example.yaml from the expected template and rerun the command.",
            verification_steps=["python scripts/check_env.py"],
        )
        return 1

    print(f"Config: {_display_path(config.config_path, config.repo_root)}")
    print(f"Python: {diagnostics['python']['version']}")
    print(f"Backend: {diagnostics['backend']['name']}")
    print(f"llama_cpp importable: {diagnostics['backend']['llama_cpp_importable']}")
    print(f"llama_cpp supports GPU offload: {diagnostics['backend']['llama_cpp_supports_gpu_offload']}")
    print("Models:")
    for name, model in diagnostics["models"].items():
        print(f"  {name}: {model['status']}")
        print(f"    model_dir: {_display_path(Path(model['model_dir']), config.repo_root)}")
        print(f"    expected_device: {model['expected_device']}")
        print(f"    configured_n_gpu_layers: {model['configured_n_gpu_layers']}")
        print(f"    device_status: {model['device_status']}")
        if model["discovered_model_file"]:
            print(f"    discovered_model_file: {_display_path(Path(model['discovered_model_file']), config.repo_root)}")
        if model["candidates"]:
            print("    candidates:")
            for candidate in model["candidates"]:
                print(f"      - {_display_path(Path(candidate), config.repo_root)}")

    e4b_status = diagnostics["models"]["gemma_e4b"]["status"]
    if e4b_status != "ok":
        print("warning: Gemma E4B is optional for current low-tier smoke tests.")
    for name in ("gemma_e2b", "gemma_e4b"):
        device_status = diagnostics["models"][name]["device_status"]
        if device_status in {"cuda_backend_unavailable", "device_policy_mismatch"}:
            print(
                f"warning: {name} expected CUDA but runtime appears CPU-only "
                f"({device_status})."
            )

    failed_required = [
        name for name in REQUIRED_LOW_TIER_MODELS if diagnostics["models"][name]["status"] != "ok"
    ]
    if failed_required:
        print(f"Required low-tier models are not ready: {', '.join(failed_required)}")
        return 1

    return 0


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
