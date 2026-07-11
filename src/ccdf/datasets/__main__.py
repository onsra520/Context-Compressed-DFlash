"""CLI for dataset reconstruction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ccdf.datasets.freeze import freeze_dataset
from ccdf.datasets.io import write_json
from ccdf.datasets.pipeline import build_all, run_reproducibility_audit


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m ccdf.datasets")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("--source-root", default=".archives/20260711-043859/project")
    build.add_argument("--staging", required=True)
    build.add_argument("--qmsum-query-policy", default="specific_only")
    build.add_argument("--qmsum-max-context-words", type=int, default=1500)

    freeze = sub.add_parser("freeze")
    freeze.add_argument("--staging", required=True)
    freeze.add_argument("--project-root", default=".")
    freeze.add_argument("--dataset", default="all")
    freeze.add_argument("--confirm-freeze", action="store_true")
    freeze.add_argument("--overwrite", action="store_true")

    audit = sub.add_parser("audit-reproducibility")
    audit.add_argument("--source-root", default=".archives/20260711-043859/project")
    audit.add_argument("--audit-root", required=True)
    audit.add_argument("--output", required=True)

    args = parser.parse_args()
    if args.command == "build":
        result = build_all(
            source_root=Path(args.source_root),
            staging_root=Path(args.staging),
            qmsum_query_policy=args.qmsum_query_policy,
            qmsum_max_context_words=args.qmsum_max_context_words,
        )
        print(json.dumps(result["fixture_counts"], sort_keys=True))
    elif args.command == "freeze":
        result = freeze_dataset(
            staging_root=Path(args.staging),
            project_root=Path(args.project_root),
            dataset=args.dataset,
            confirm_freeze=args.confirm_freeze,
            overwrite=args.overwrite,
        )
        print(json.dumps({"copied": len(result["copied"])}, sort_keys=True))
    elif args.command == "audit-reproducibility":
        result = run_reproducibility_audit(Path(args.source_root), Path(args.audit_root))
        write_json(Path(args.output), result)
        print(json.dumps({"pass": result["pass"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
