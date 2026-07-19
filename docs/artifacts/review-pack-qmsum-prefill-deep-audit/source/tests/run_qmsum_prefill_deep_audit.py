"""Orchestrate isolated, monitored QMSum baseline prefill probes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import psutil

from ccdf.benchmark.dataset_smoke import _terminate_process_tree


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "docs/artifacts/qmsum-prefill-deep-audit"
TIMEOUT_SECONDS = 120.0
PHYSICAL_VRAM_LIMIT_MIB = 7.5 * 1024


def _gpu_state() -> dict[str, Any]:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=memory.used,memory.total,utilization.gpu,utilization.memory",
            "--format=csv,noheader,nounits",
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )
    if completed.returncode != 0:
        return {"error": completed.stderr.strip()}
    values = [part.strip() for part in completed.stdout.strip().split(",")]
    return {
        "memory_used_mib": float(values[0]),
        "memory_total_mib": float(values[1]),
        "gpu_utilization_percent": float(values[2]),
        "memory_utilization_percent": float(values[3]),
    }


def _rss_tree(pid: int) -> tuple[int, list[dict[str, Any]]]:
    try:
        root = psutil.Process(pid)
        processes = [root, *root.children(recursive=True)]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0, []
    rows = []
    total = 0
    for process in processes:
        try:
            rss = int(process.memory_info().rss)
            total += rss
            rows.append({"pid": process.pid, "parent_pid": process.ppid(), "rss_bytes": rss})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return total, rows


def _case_name(case: dict[str, Any]) -> str:
    return (
        f"L{case['length']}-{case['backend']}-{case['mask']}-"
        f"{case['forward_path']}-cache-{case['use_cache']}"
    )


def _run_case(root: Path, case: dict[str, Any], *, profile: bool = False, snapshot: bool = False) -> dict[str, Any]:
    name = _case_name(case)
    case_root = root / "cases" / name
    case_root.mkdir(parents=True, exist_ok=False)
    output = case_root / "result.json"
    progress = case_root / "progress.jsonl"
    trace = case_root / "trace.json"
    memory_snapshot = case_root / "cuda-memory-snapshot.pickle"
    stdout_path = case_root / "stdout.txt"
    stderr_path = case_root / "stderr.txt"
    command = [
        sys.executable,
        "-X",
        "faulthandler",
        str(ROOT / "tests/run_qmsum_prefill_probe.py"),
        "--length",
        str(case["length"]),
        "--backend",
        case["backend"],
        "--mask",
        case["mask"],
        "--forward-path",
        case["forward_path"],
        "--use-cache",
        case["use_cache"],
        "--progress",
        str(progress),
        "--output",
        str(output),
    ]
    if profile:
        command.extend(("--profile", "--trace", str(trace)))
    if snapshot:
        command.extend(("--memory-snapshot", str(memory_snapshot)))
    environment = dict(__import__("os").environ)
    environment.update({
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTHONFAULTHANDLER": "1",
        "PYTHONUNBUFFERED": "1",
    })
    baseline_gpu = _gpu_state()
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    max_gpu = baseline_gpu.get("memory_used_mib", 0.0)
    max_gpu_utilization = baseline_gpu.get("gpu_utilization_percent", 0.0)
    max_rss = 0
    max_rss_processes: list[dict[str, Any]] = []
    termination = None
    monitor_reason = None
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=environment,
            stdout=stdout,
            stderr=stderr,
            text=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            start_new_session=sys.platform != "win32",
        )
        last_gpu_sample = 0.0
        while process.poll() is None:
            now = time.perf_counter()
            rss, rss_processes = _rss_tree(process.pid)
            if rss > max_rss:
                max_rss = rss
                max_rss_processes = rss_processes
            if now - last_gpu_sample >= 0.5:
                gpu = _gpu_state()
                last_gpu_sample = now
                max_gpu = max(max_gpu, gpu.get("memory_used_mib", 0.0))
                max_gpu_utilization = max(
                    max_gpu_utilization, gpu.get("gpu_utilization_percent", 0.0)
                )
                if gpu.get("memory_used_mib", 0.0) > PHYSICAL_VRAM_LIMIT_MIB:
                    monitor_reason = "PHYSICAL_VRAM_LIMIT"
            if now - started >= TIMEOUT_SECONDS:
                monitor_reason = "TIMEOUT"
            if monitor_reason is not None:
                termination = _terminate_process_tree(process, 10.0)
                break
            time.sleep(0.1)
        exit_code = process.poll()
    duration = time.perf_counter() - started
    payload = (
        json.loads(output.read_text(encoding="utf-8"))
        if output.is_file()
        else {
            "status": monitor_reason or "CRASH",
            "error": "worker produced no result artifact",
            **case,
        }
    )
    payload["monitor"] = {
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": duration,
        "timeout_seconds": TIMEOUT_SECONDS,
        "physical_vram_limit_mib": PHYSICAL_VRAM_LIMIT_MIB,
        "baseline_gpu": baseline_gpu,
        "max_physical_vram_used_mib": max_gpu,
        "max_gpu_utilization_percent": max_gpu_utilization,
        "max_process_tree_working_set_bytes": max_rss,
        "max_rss_processes": max_rss_processes,
        "exit_code": exit_code,
        "termination_reason": monitor_reason,
        "termination": termination,
        "command": command,
        "stdout_path": str(stdout_path.relative_to(root)),
        "stderr_path": str(stderr_path.relative_to(root)),
        "progress_path": str(progress.relative_to(root)),
    }
    if monitor_reason is not None:
        payload["status"] = monitor_reason
    (case_root / "monitored-result.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "case": name,
        "status": payload["status"],
        "duration_seconds": duration,
        "max_physical_vram_used_mib": max_gpu,
        "max_process_tree_working_set_bytes": max_rss,
        "backend_observed": payload.get("backend_observed"),
        "prefill_seconds": payload.get("prefill_seconds"),
    }, sort_keys=True), flush=True)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--single-case", help="JSON object for one isolated supplemental case")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--snapshot", action="store_true")
    args = parser.parse_args()
    root = args.output_root.resolve()
    if root.exists():
        raise FileExistsError(f"refusing to replace audit root: {root}")
    root.mkdir(parents=True)
    if args.single_case is not None:
        case = json.loads(args.single_case)
        result = _run_case(root, case, profile=args.profile, snapshot=args.snapshot)
        (root / "summary.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return
    all_results: list[dict[str, Any]] = []

    # The 128-token case is the Windows AWQ short-prompt baseline. The remaining
    # ordered cases are the requested deterministic prefix matrix.
    longest_successful = None
    for length in (128, 512, 1024, 2048, 4096, 6289):
        case = {
            "length": length,
            "backend": "auto",
            "mask": "ones",
            "forward_path": "project",
            "use_cache": "true",
        }
        result = _run_case(root, case, profile=True)
        all_results.append(result)
        if result["status"] == "PASS":
            longest_successful = length
        if result["status"] in {"TIMEOUT", "PHYSICAL_VRAM_LIMIT", "OOM"}:
            break

    if longest_successful is None:
        raise RuntimeError("no length probe succeeded")

    backend_results = []
    for backend in ("auto", "flash", "math", "efficient"):
        case = {
            "length": longest_successful,
            "backend": backend,
            "mask": "none",
            "forward_path": "standard",
            "use_cache": "true",
        }
        result = _run_case(root, case, profile=True, snapshot=backend == "auto")
        all_results.append(result)
        backend_results.append(result)

    audit_cases = (
        ("none", "project", "true"),
        ("ones", "project", "true"),
        ("none", "standard", "true"),
        ("ones", "standard", "true"),
        ("none", "standard", "false"),
        ("ones", "standard", "false"),
    )
    mask_results = []
    existing = {
        (row["mask_mode"], row["forward_path"], str(row["use_cache"]).lower()): row
        for row in all_results
        if row.get("backend_requested") == "auto"
        and row.get("length") == longest_successful
    }
    for mask, forward_path, use_cache in audit_cases:
        identity = (mask, forward_path, use_cache)
        if identity in existing:
            result = existing[identity]
        else:
            case = {
                "length": longest_successful,
                "backend": "auto",
                "mask": mask,
                "forward_path": forward_path,
                "use_cache": use_cache,
            }
            result = _run_case(root, case, profile=True)
            all_results.append(result)
        mask_results.append(result)

    passing_tokens = {
        row.get("first_token_id") for row in mask_results if row.get("status") == "PASS"
    }
    summary = {
        "status": "PASS",
        "longest_successful_length": longest_successful,
        "requested_full_length_reached": longest_successful == 6289,
        "length_results": [
            {
                "length": row["length"],
                "status": row["status"],
                "prefill_seconds": row.get("prefill_seconds"),
                "first_token_latency_seconds": row.get("first_token_latency_seconds"),
                "decode_seconds": row.get("decode_seconds"),
                "backend_observed": row.get("backend_observed"),
                "physical_vram_mib": row["monitor"]["max_physical_vram_used_mib"],
                "working_set_bytes": row["monitor"]["max_process_tree_working_set_bytes"],
                "torch": row.get("torch"),
            }
            for row in all_results
            if row.get("backend_requested") == "auto"
            and row.get("mask_mode") == "ones"
            and row.get("forward_path") == "project"
            and row.get("use_cache") is True
        ],
        "backend_results": [
            {
                "requested": row.get("backend_requested"),
                "observed": row.get("backend_observed"),
                "status": row["status"],
                "error": row.get("error"),
                "prefill_seconds": row.get("prefill_seconds"),
            }
            for row in backend_results
        ],
        "mask_cache_results": [
            {
                "mask": row.get("mask_mode"),
                "forward_path": row.get("forward_path"),
                "use_cache": row.get("use_cache"),
                "status": row["status"],
                "first_token_id": row.get("first_token_id"),
                "backend_observed": row.get("backend_observed"),
                "prefill_seconds": row.get("prefill_seconds"),
            }
            for row in mask_results
        ],
        "output_token_match": len(passing_tokens) == 1,
        "output_token_values": sorted(token for token in passing_tokens if token is not None),
        "cases": len(all_results),
    }
    (root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
