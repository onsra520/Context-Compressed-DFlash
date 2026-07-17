"""Command-line entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from .benchmark import run_benchmark
from .config import load_config
from .models.loaders import load_dflash_models
from .runtime.engine import RuntimeEngine
from .validation.environment import validate_environment


def _print(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ccdf-rec2")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate-config", "validate-env", "validate-models", "validation-cycle"):
        item = sub.add_parser(name)
        item.add_argument("--config", default="config.yml")
    run = sub.add_parser("run")
    run.add_argument("--config", default="config.yml")
    run.add_argument("--condition", choices=("baseline", "dflash"), required=True)
    run.add_argument("--target-profile", choices=("primary", "fallback"), default="primary")
    run.add_argument("--prompt", required=True)
    run.add_argument("--dataset", default="general")
    run.add_argument("--max-new-tokens", type=int)
    bench = sub.add_parser("benchmark")
    bench.add_argument("--config", default="config.yml")
    bench.add_argument("--input", required=True)
    bench.add_argument("--conditions", default="baseline,dflash")
    bench.add_argument("--target-profile", choices=("primary", "fallback"), default="primary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    if args.command == "validate-config":
        _print({"pass": True, "warnings": config.validate(False), "root": str(config.root)})
        return 0
    if args.command == "validate-env":
        _print(validate_environment(config))
        return 0
    if args.command == "validate-models":
        target, drafter, _, metadata = load_dflash_models(config)
        _print({"pass": True, "metadata": metadata})
        del target, drafter
        return 0
    if args.command == "validation-cycle":
        payload = {
            "config": {"pass": True, "warnings": config.validate(False)},
            "environment": validate_environment(config),
        }
        target, drafter, tokenizer, metadata = load_dflash_models(config)
        payload["models"] = {"pass": True, "metadata": metadata}
        del target, drafter, tokenizer
        import gc
        import torch

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        _print(payload)
        return 0
    if args.command == "run":
        engine = RuntimeEngine(config, condition=args.condition, target_profile=args.target_profile)
        try:
            result = engine.generate(
                args.prompt,
                dataset=args.dataset,
                max_new_tokens=args.max_new_tokens,
            )
            _print(result.to_dict())
        finally:
            engine.close()
        return 0
    if args.command == "benchmark":
        conditions = [value.strip() for value in args.conditions.split(",") if value.strip()]
        _print(
            run_benchmark(
                config,
                input_path=args.input,
                conditions=conditions,
                target_profile=args.target_profile,
            )
        )
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    sys.exit(main())
