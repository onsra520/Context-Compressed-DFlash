"""Command-line parser construction."""

from __future__ import annotations

import argparse


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
