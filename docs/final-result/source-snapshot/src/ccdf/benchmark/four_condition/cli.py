"""CLI for preparing, executing, and auditing four-condition runs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from ...compression.llmlingua import compress_samples
from ...config import load_config
from .audit import audit, render_report
from .manifest import build_run_manifest, write_manifest
from .runner import prepare_mock_samples, read_jsonl, run_condition, write_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yml")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare-mock")
    prepare.add_argument("--output", type=Path, required=True)
    select = sub.add_parser("select-samples")
    select.add_argument("--input", type=Path, required=True)
    select.add_argument("--sample-id", action="append", required=True)
    select.add_argument("--output", type=Path, required=True)
    manifest = sub.add_parser("build-manifest")
    manifest.add_argument("--samples", type=Path, required=True)
    manifest.add_argument("--run-id", required=True)
    manifest.add_argument("--output", type=Path, required=True)
    manifest.add_argument("--workload-name", required=True)
    manifest.add_argument("--warmups", type=int, default=1)
    manifest.add_argument("--repetitions", type=int, default=1)
    manifest.add_argument("--max-new-tokens", type=int)
    manifest.add_argument("--keep-rate", type=float)
    compress = sub.add_parser("compress")
    compress.add_argument("--samples", type=Path, required=True)
    compress.add_argument("--output", type=Path, required=True)
    compress.add_argument("--audit", type=Path, required=True)
    compress.add_argument("--keep-rate", type=float)
    compress.add_argument("--resume", action="store_true")
    run = sub.add_parser("run")
    run.add_argument("--condition", choices=("C1", "C2", "C3", "C4"), required=True)
    run.add_argument("--samples", type=Path, required=True)
    run.add_argument("--compression", type=Path, required=True)
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--resume", action="store_true")
    inspect = sub.add_parser("audit")
    for condition in ("C1", "C2", "C3", "C4"):
        inspect.add_argument(f"--{condition.lower()}", type=Path, required=True)
    inspect.add_argument("--compression", type=Path, required=True)
    inspect.add_argument("--compressor-audit", type=Path, required=True)
    inspect.add_argument("--isolation", type=Path, required=True)
    inspect.add_argument("--manifest", type=Path, required=True)
    inspect.add_argument("--output", type=Path, required=True)
    inspect.add_argument("--report", type=Path, required=True)
    gpu_state = sub.add_parser("capture-gpu-state")
    gpu_state.add_argument("--label", required=True)
    gpu_state.add_argument("--output", type=Path, required=True)
    isolation = sub.add_parser("build-isolation")
    isolation.add_argument("--state", type=Path, action="append", required=True)
    isolation.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    if args.command == "capture-gpu-state":
        command = [
            "rtk",
            "nvidia-smi",
            "--query-compute-apps=pid,process_name,used_memory",
            "--format=csv,noheader",
        ]
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        if completed.returncode:
            raise RuntimeError(f"GPU process query failed: {completed.stderr.strip()}")
        payload = {
            "schema": "ccdf.gpu-boundary-state.v1",
            "label": args.label,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "command": command[1:],
            "compute_processes": [line for line in completed.stdout.splitlines() if line.strip()],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, sort_keys=True))
        return 0
    if args.command == "build-isolation":
        boundaries = [json.loads(path.read_text(encoding="utf-8")) for path in args.state]
        payload = {"schema": "ccdf.condition-isolation.v1", "boundaries": boundaries}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"boundaries": len(boundaries), "output": str(args.output)}))
        return 0
    if args.command == "prepare-mock":
        write_jsonl(args.output, prepare_mock_samples(config))
        print(json.dumps({"samples": 10, "output": str(args.output)}))
        return 0
    if args.command == "select-samples":
        rows = read_jsonl(args.input)
        ids = [str(row["sample_id"]) for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("input samples contain duplicate sample IDs")
        selected = []
        for sample_id in args.sample_id:
            matches = [row for row in rows if row["sample_id"] == sample_id]
            if len(matches) != 1:
                raise ValueError(f"sample selection expected exactly one row for {sample_id}")
            selected.append(matches[0])
        if len(args.sample_id) != len(set(args.sample_id)):
            raise ValueError("sample selection contains duplicate requested IDs")
        write_jsonl(args.output, selected)
        print(json.dumps({"sample_ids": args.sample_id, "output": str(args.output)}))
        return 0
    if args.command == "build-manifest":
        manifest_payload = build_run_manifest(
            config,
            read_jsonl(args.samples),
            run_id=args.run_id,
            repetitions=args.repetitions,
            warmups=args.warmups,
            max_new_tokens=int(
                args.max_new_tokens or config.require("benchmark.smoke_max_new_tokens")
            ),
            requested_keep_rate=args.keep_rate,
            workload_name=args.workload_name,
        )
        write_manifest(args.output, manifest_payload)
        print(json.dumps({"run_id": args.run_id, "output": str(args.output)}))
        return 0
    if args.command == "compress":
        rows, compressor_audit = compress_samples(
            config,
            read_jsonl(args.samples),
            keep_rate=args.keep_rate,
            output_path=args.output,
            resume=args.resume,
        )
        args.audit.parent.mkdir(parents=True, exist_ok=True)
        args.audit.write_text(
            json.dumps(compressor_audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "samples": len(rows),
                    "compression_run_id": compressor_audit["compression_run_id"],
                    "device": compressor_audit["resolved_device"],
                    "output": str(args.output),
                }
            )
        )
        return 0 if compressor_audit["status"] == "success" else 1
    if args.command == "run":
        rows = run_condition(
            config,
            manifest=json.loads(args.manifest.read_text(encoding="utf-8")),
            condition_id=args.condition,
            samples=read_jsonl(args.samples),
            compression_rows=read_jsonl(args.compression),
            output_path=args.output,
            resume=args.resume,
        )
        print(json.dumps({"condition": args.condition, "rows": len(rows), "output": str(args.output)}))
        return 0
    if args.command == "audit":
        result = audit(
            condition_paths={
                "C1": args.c1,
                "C2": args.c2,
                "C3": args.c3,
                "C4": args.c4,
            },
            compression_path=args.compression,
            compressor_audit_path=args.compressor_audit,
            isolation_path=args.isolation,
            manifest_path=args.manifest,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        args.output.with_name("parity-summary.json").write_text(
            json.dumps(result["parity"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        args.output.with_name("quality-summary.json").write_text(
            json.dumps(
                {
                    condition: {
                        "scope": result["quality_scope"],
                        "quality_pass_rate": summary["mock_quality_pass_rate"],
                        "quality_score": summary["quality_score"],
                        "parse_failure_count": summary["parse_failure_count"],
                        "empty_output_count": summary["empty_output_count"],
                    }
                    for condition, summary in result["conditions"].items()
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        args.output.with_name("error-summary.json").write_text(
            json.dumps(
                {
                    **result["error_summary"],
                    "failed_gates": [name for name, passed in result["gates"].items() if not passed],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(render_report(result), encoding="utf-8")
        print(json.dumps({"conclusion": result["conclusion"], "gates": result["gates"]}))
        return 0 if result["pass"] else 1
    raise AssertionError(args.command)
