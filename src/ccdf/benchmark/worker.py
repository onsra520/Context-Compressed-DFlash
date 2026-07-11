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


def run_worker(*, dataset: str, subset: str, condition: str, output: Path, limit: int | None, task_id: str) -> dict:
    resolved = resolve_config(dataset=dataset, subset=subset, condition_id=condition, execution_mode="benchmark")
    fixtures = read_jsonl(Path(resolved.data["fixture_path"]))
    if limit is not None:
        fixtures = fixtures[:limit]
    started = time.perf_counter()
    engine = RuntimeEngine(resolved)
    rows = []
    try:
        state = _git_state(Path(resolved.data["path_context"]["worktree_root"]))
        run_id = f"{task_id.lower()}-{os.getpid()}-{int(time.time())}"
        for fixture in fixtures:
            result = engine.execute(RuntimeRequest(
                resolved=resolved,
                prompt_parts=PromptParts(**fixture["prompt_parts"]),
                reference_answer=fixture["reference_answer"],
                measurement_mode="benchmark",
            ))
            rows.append(_row(task_id=task_id, run_id=run_id, resolved=resolved, fixture=fixture, result=result, git_state=state))
    finally:
        engine.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl_atomic(output, rows)
    manifest = {
        "worker_version": "rec-t06b.worker.v1",
        "condition_id": condition,
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
    parser.add_argument("--task-id", default="Rec-T06B")
    args = parser.parse_args()
    run_worker(dataset=args.dataset, subset=args.subset, condition=args.condition, output=Path(args.output), limit=args.limit, task_id=args.task_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
