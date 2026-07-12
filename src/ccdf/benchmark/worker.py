"""One-condition Rec-T06B benchmark worker.

This module is deliberately invoked in a fresh Python process by the canonical
benchmark parent.  It owns exactly one resolved RuntimeEngine and exits after
writing its immutable run artifact and worker manifest.
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import time
from pathlib import Path

from ccdf.artifacts.writer import write_json, write_jsonl_atomic
from ccdf.benchmark.workflow import _git_state, _row
from ccdf.config import resolve_config
from ccdf.datasets.hashing import hash_file, hash_json
from ccdf.datasets.io import read_jsonl
from ccdf.prompts.schemas import PromptParts
from ccdf.runtime import RuntimeEngine, RuntimeRequest


def run_worker(*, dataset: str, subset: str, condition: str, output: Path, limit: int | None, task_id: str, execution_mode: str, canonical: bool, canonical_reason: str, expected_config_hash: str | None = None, expected_fixture_ids_hash: str | None = None, expected_git_state: dict | None = None) -> dict:
    resolved = resolve_config(dataset=dataset, subset=subset, condition_id=condition, execution_mode=execution_mode)
    if expected_config_hash is not None and resolved.sha256 != expected_config_hash:
        raise ValueError("worker resolved config hash does not match parent")
    fixtures = read_jsonl(Path(resolved.data["fixture_path"]))
    if limit is not None:
        fixtures = fixtures[:limit]
    fixture_ids_hash = hash_json([row["fixture_id"] for row in fixtures])
    if expected_fixture_ids_hash is not None and fixture_ids_hash != expected_fixture_ids_hash:
        raise ValueError("worker fixture order does not match parent")
    started = time.perf_counter()
    engine = RuntimeEngine(resolved)
    rows = []
    try:
        state = _git_state(Path(resolved.data["path_context"]["worktree_root"]))
        if expected_git_state is not None and state != expected_git_state:
            raise ValueError("worker git/source state does not match parent")
        run_id = f"{task_id.lower()}-{os.getpid()}-{int(time.time())}"
        for fixture in fixtures:
            result = engine.execute(RuntimeRequest(
                resolved=resolved,
                prompt_parts=PromptParts(**fixture["prompt_parts"]),
                reference_answer=fixture["reference_answer"],
                measurement_mode=execution_mode,
            ))
            rows.append(_row(task_id=task_id, run_id=run_id, resolved=resolved, fixture=fixture, result=result, git_state=state, canonical=canonical, canonical_reason=canonical_reason))
    finally:
        engine.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl_atomic(output, rows)
    manifest = {
        "worker_version": "rec-t06b.worker.v1",
        "condition_id": condition,
        "task_id": task_id,
        "execution_mode": execution_mode,
        "canonical": canonical,
        "canonical_reason": canonical_reason,
        "git_state": state,
        "pid": os.getpid(),
        "exit_status": 0,
        "python": sys.version,
        "platform": platform.platform(),
        "environment": {key: os.environ.get(key) for key in ("PYTHONPATH", "CUDA_VISIBLE_DEVICES")},
        "elapsed_ms": (time.perf_counter() - started) * 1000,
        "resolved_config_sha256": resolved.sha256,
        "run_file": output.name,
        "run_file_sha256": hash_file(output),
        "rows": len(rows),
        "resource": rows[-1].get("resource", {}) if rows else {},
        "timing": {
            key: rows[-1].get(key)
            for key in (
                "prompt_prepare_ms", "compression_total_ms", "target_prefill_ms",
                "draft_prefill_ms", "decode_total_ms", "generation_request_e2e_ms",
                "warm_request_e2e_ms", "target_model_init_ms", "drafter_model_init_ms",
                "compressor_init_ms", "cold_start_e2e_ms",
            )
        } if rows else {},
    }
    write_json(output.with_suffix(".worker.json"), manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--subset", required=True)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--execution-mode", required=True, choices=["benchmark", "profiling", "smoke"])
    parser.add_argument("--canonical", required=True, choices=["true", "false"])
    parser.add_argument("--canonical-reason", required=True)
    parser.add_argument("--expected-config-hash")
    parser.add_argument("--expected-fixture-ids-hash")
    parser.add_argument("--expected-source-commit")
    parser.add_argument("--expected-source-dirty")
    parser.add_argument("--expected-tracked-diff-hash")
    parser.add_argument("--expected-untracked-inventory-hash")
    args = parser.parse_args()
    expected_state = None if args.expected_source_commit is None else {"source_commit": args.expected_source_commit, "dirty": args.expected_source_dirty == "true", "tracked_diff_sha256": args.expected_tracked_diff_hash, "relevant_untracked_source_config_inventory_sha256": args.expected_untracked_inventory_hash}
    run_worker(dataset=args.dataset, subset=args.subset, condition=args.condition, output=Path(args.output), limit=args.limit, task_id=args.task_id, execution_mode=args.execution_mode, canonical=args.canonical == "true", canonical_reason=args.canonical_reason, expected_config_hash=args.expected_config_hash, expected_fixture_ids_hash=args.expected_fixture_ids_hash, expected_git_state=expected_state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
