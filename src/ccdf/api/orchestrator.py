"""
Orchestrator for the three-way CC-DFlash comparison pipeline.

SSE contract: yield dicts like {"event": "name", "data": "json-string"}.
sse-starlette encodes those correctly.  Never yield pre-formatted SSE strings.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from typing import AsyncIterator

from .jobs import job_manager


def parse_input(raw_input: str) -> tuple[str, str]:
    """Split raw prompt into (context, question).

    Separator: last blank line in the text.
    If no blank line is present, context is empty and the whole input is the
    question.
    """
    normalized = raw_input.replace("\r\n", "\n").replace("\r", "\n")
    parts = normalized.rsplit("\n\n", 1)
    if len(parts) == 2:
        ctx = parts[0].strip()
        q = parts[1].strip()
        if ctx and q:
            return ctx, q
    return "", normalized.strip()


def _evt(event: str, data: object) -> dict:
    """Return a dict that sse-starlette encodes as a proper SSE frame.

    Yields: event: <name>\\r\\ndata: <json>\\r\\n\\r\\n
    """
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


async def _run_worker(
    *,
    condition: str,
    context: str,
    question: str,
    env: dict,
    timeout_s: float = 600,
) -> tuple[int, str, str]:
    """Spawn an isolated worker subprocess and return (returncode, stdout, stderr)."""
    cmd = [
        sys.executable,
        "-m",
        "frontend.api.worker",
        "--context",
        context,
        "--question",
        question,
        "--condition",
        condition,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_s
        )
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(proc.communicate(), timeout=5)
        except Exception:
            pass
        raise RuntimeError(f"Condition '{condition}' timed out after {timeout_s:.0f} s")

    return (
        proc.returncode,
        stdout_bytes.decode("utf-8", errors="replace"),
        stderr_bytes.decode("utf-8", errors="replace"),
    )


async def run_comparison_job(
    job_id: str, raw_input: str, compression_device: str
) -> AsyncIterator[dict]:
    """Drive the three-condition comparison and yield SSE event dicts."""
    job = await job_manager.get_job(job_id)

    try:
        context, question = parse_input(raw_input)
        if not question:
            raise ValueError("Empty question is not allowed.")

        job["status"] = "running"
        yield _evt("job.started", {"job_id": job_id})
        yield _evt(
            "input.parsed",
            {
                "context_length": len(context),
                "question_length": len(question),
                "has_context": bool(context),
            },
        )

        cc_condition = (
            "cc-dflash-r2-gpu" if compression_device == "cuda" else "cc-dflash-r2"
        )
        conditions = ["baseline-ar", "dflash-r1", cc_condition]

        # Build PYTHONPATH so the worker subprocess can import both ccdf (src/)
        # and frontend.api (project root).
        root = os.path.abspath(os.getcwd())
        existing_pp = os.environ.get("PYTHONPATH", "")
        new_segments = f"{root}/src:{root}"
        worker_env = os.environ.copy()
        worker_env["PYTHONPATH"] = (
            f"{new_segments}:{existing_pp}" if existing_pp else new_segments
        )

        for condition in conditions:
            yield _evt("condition.started", {"condition_id": condition})

            t0 = time.monotonic()
            returncode, stdout_text, stderr_text = await _run_worker(
                condition=condition,
                context=context,
                question=question,
                env=worker_env,
            )
            elapsed_ms = (time.monotonic() - t0) * 1000

            # --- Parse worker output ---
            # Worker emits exactly one JSON line on stdout.
            # stderr may contain torch/transformers warnings; never fail on that.
            result_obj = None
            parse_error: str | None = None
            for line in reversed(stdout_text.strip().splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        result_obj = json.loads(line)
                        break
                    except json.JSONDecodeError as exc:
                        parse_error = str(exc)

            if returncode != 0:
                diag = (
                    f"Worker process failed for condition '{condition}' "
                    f"(returncode={returncode}, elapsed={elapsed_ms:.0f} ms).\n"
                    f"--- stdout ---\n{stdout_text}\n"
                    f"--- stderr (may include warnings) ---\n{stderr_text}"
                )
                raise RuntimeError(diag)

            if result_obj is None:
                diag = (
                    f"No JSON output from worker for condition '{condition}' "
                    f"(returncode={returncode}, elapsed={elapsed_ms:.0f} ms).\n"
                    f"parse_error={parse_error}\n"
                    f"--- stdout ---\n{stdout_text}\n"
                    f"--- stderr ---\n{stderr_text}"
                )
                raise RuntimeError(diag)

            if result_obj.get("status") == "error":
                diag = (
                    f"Worker execution error for condition '{condition}':\n"
                    f"{result_obj.get('error')}\n"
                    f"--- traceback ---\n{result_obj.get('traceback', '')}\n"
                    f"--- stderr (diagnostics only) ---\n{stderr_text}"
                )
                raise RuntimeError(diag)

            condition_data = result_obj["data"]
            job["results"][condition] = condition_data
            yield _evt("condition.completed", condition_data)

        yield _evt("comparison.completed", job["results"])
        job["status"] = "completed"
        yield _evt("job.completed", {"job_id": job_id})

    except Exception as exc:
        refreshed = await job_manager.get_job(job_id)
        if refreshed is not None:
            refreshed["status"] = "failed"
            refreshed["error"] = str(exc)
        yield _evt("condition.failed", {"error": str(exc)})
        yield _evt("job.failed", {"job_id": job_id, "error": str(exc)})

    finally:
        await job_manager.complete_job(job_id)
