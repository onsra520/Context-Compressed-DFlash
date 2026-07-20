"""In-memory single-worker run queue and ordered SSE event log."""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from contextlib import suppress
from dataclasses import asdict
from typing import Any, AsyncIterator

from fastapi import Request

from .runtime_adapter import LiveCompressionResult, LiveGenerationResult

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
CONDITIONS = ("baseline-ar", "d-flash", "cc-dflash")


class RunCancelled(RuntimeError):
    pass


class DemoRunManager:
    def __init__(self, backend: object) -> None:
        self.backend = backend
        self._runs: dict[str, dict[str, Any]] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker(), name="ccdf-demo-worker")

    async def stop(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None

    async def create_run(self, *, prompt: str, compression_device: str, max_new_tokens: int) -> str:
        await self.start()
        run_id = str(uuid.uuid4())
        async with self._lock:
            self._runs[run_id] = {
                "run_id": run_id,
                "status": "queued",
                "prompt": prompt,
                "compression_device": compression_device,
                "max_new_tokens": max_new_tokens,
                "created_at": time.time(),
                "events": [],
                "next_sequence": 1,
                "conditions": {},
                "compression": None,
                "comparison": None,
                "error": None,
                "condition": asyncio.Condition(),
                "cancel_event": threading.Event(),
            }
        await self._queue.put(run_id)
        return run_id

    async def exists(self, run_id: str) -> bool:
        async with self._lock:
            return run_id in self._runs

    async def _emit(self, run_id: str, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        run = self._runs[run_id]
        event = {
            "sequence": run["next_sequence"],
            "type": event_type,
            "run_id": run_id,
            "timestamp": time.time(),
            "data": data,
        }
        run["next_sequence"] += 1
        run["events"].append(event)
        async with run["condition"]:
            run["condition"].notify_all()
        return event

    async def snapshot(self, run_id: str) -> dict[str, Any] | None:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            return {
                key: value
                for key, value in run.items()
                if key not in {"condition", "cancel_event", "next_sequence"}
            }

    async def cancel(self, run_id: str) -> dict[str, Any] | None:
        run = self._runs.get(run_id)
        if run is None:
            return None
        if run["status"] in TERMINAL_STATUSES:
            return await self.snapshot(run_id)
        run["cancel_event"].set()
        if run["status"] == "queued":
            run["status"] = "cancelled"
            await self._emit(run_id, "run.cancelled", {"status": "cancelled"})
        return await self.snapshot(run_id)

    async def stream_sse(
        self,
        run_id: str,
        *,
        request: Request,
        after_sequence: int = 0,
    ) -> AsyncIterator[str]:
        run = self._runs[run_id]
        cursor = 0
        while cursor < len(run["events"]) and run["events"][cursor]["sequence"] <= after_sequence:
            cursor += 1
        while True:
            while cursor < len(run["events"]):
                event = run["events"][cursor]
                cursor += 1
                payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                yield f"id: {event['sequence']}\nevent: {event['type']}\ndata: {payload}\n\n"
            if run["status"] in TERMINAL_STATUSES:
                break
            if await request.is_disconnected():
                break
            async with run["condition"]:
                if cursor < len(run["events"]) or run["status"] in TERMINAL_STATUSES:
                    continue
                await run["condition"].wait()

    async def _worker(self) -> None:
        while True:
            run_id = await self._queue.get()
            try:
                run = self._runs[run_id]
                if run["status"] != "cancelled":
                    await self._execute(run_id)
            finally:
                self._queue.task_done()

    def _check_cancelled(self, run: dict[str, Any]) -> None:
        if run["cancel_event"].is_set():
            raise RunCancelled("run cancellation requested")

    async def _execute(self, run_id: str) -> None:
        run = self._runs[run_id]
        current_stage = "run"
        try:
            run["status"] = "running"
            await self._emit(run_id, "run.started", {"status": "running"})
            current_stage = "input"
            analysis = await asyncio.to_thread(self.backend.analyze_input, run["prompt"])
            self._check_cancelled(run)
            await self._emit(run_id, "input.analyzed", analysis)
            for condition_id in CONDITIONS:
                await self._emit(run_id, "condition.queued", {"condition_id": condition_id})

            current_stage = "baseline-ar"
            baseline = await self._run_condition(run, "baseline-ar", run["prompt"])
            current_stage = "d-flash"
            await self._run_condition(run, "d-flash", run["prompt"])

            current_stage = "compression"
            self._check_cancelled(run)
            await self._emit(
                run_id,
                "compression.started",
                {"device": run["compression_device"]},
            )
            compression: LiveCompressionResult = await asyncio.to_thread(
                self.backend.compress,
                prompt=run["prompt"],
                device=run["compression_device"],
            )
            self._check_cancelled(run)
            compression_data = asdict(compression)
            compression_data.pop("prompt")
            run["compression"] = compression_data
            await self._emit(run_id, "compression.completed", compression_data)

            current_stage = "cc-dflash"
            await self._run_condition(
                run,
                "cc-dflash",
                compression.prompt,
                compression=compression,
                original_input_tokens=baseline.input_tokens,
            )
            current_stage = "comparison"
            comparison = {
                "pipeline_e2e_ms": {
                    condition_id: metrics["pipeline_e2e_ms"]
                    for condition_id, metrics in run["conditions"].items()
                },
                "compression_reduction_rate": compression.reduction_rate,
                "dflash_acceptance_rate": run["conditions"]["d-flash"]["acceptance_rate"],
            }
            run["comparison"] = comparison
            await self._emit(run_id, "comparison.completed", comparison)
            run["status"] = "completed"
            await self._emit(run_id, "run.completed", {"status": "completed"})
        except RunCancelled:
            run["status"] = "cancelled"
            await self._emit(run_id, "run.cancelled", {"status": "cancelled", "stage": current_stage})
        except Exception as exc:
            run["status"] = "failed"
            run["error"] = str(exc)
            await self._emit(
                run_id,
                "run.failed",
                {"status": "failed", "stage": current_stage, "error": str(exc)},
            )

    async def _run_condition(
        self,
        run: dict[str, Any],
        condition_id: str,
        prompt: str,
        *,
        compression: LiveCompressionResult | None = None,
        original_input_tokens: int | None = None,
    ) -> LiveGenerationResult:
        run_id = run["run_id"]
        self._check_cancelled(run)
        await self._emit(run_id, "condition.started", {"condition_id": condition_id})
        loop = asyncio.get_running_loop()
        first_token = True

        def committed(token_ids: list[int], text_delta: str) -> None:
            nonlocal first_token
            self._check_cancelled(run)
            if first_token:
                asyncio.run_coroutine_threadsafe(
                    self._emit(
                        run_id,
                        "condition.first_token",
                        {"condition_id": condition_id, "token_ids": token_ids},
                    ),
                    loop,
                ).result()
                first_token = False
            asyncio.run_coroutine_threadsafe(
                self._emit(
                    run_id,
                    "condition.token_delta",
                    {
                        "condition_id": condition_id,
                        "token_ids": token_ids,
                        "text_delta": text_delta,
                    },
                ),
                loop,
            ).result()

        result: LiveGenerationResult = await asyncio.to_thread(
            self.backend.generate,
            condition_id=condition_id,
            prompt=prompt,
            max_new_tokens=run["max_new_tokens"],
            on_tokens_committed=committed,
        )
        self._check_cancelled(run)
        metrics: dict[str, Any] = {
            "condition_id": condition_id,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "ttft_ms": result.ttft_ms,
            "generation_latency_ms": result.generation_latency_ms,
            "decode_tok_s": (
                result.output_tokens / (result.generation_latency_ms / 1000.0)
                if result.generation_latency_ms > 0
                else 0.0
            ),
            "pipeline_e2e_ms": result.generation_latency_ms,
            "stop_reason": result.stop_reason,
            "proposed_draft_tokens": None,
            "accepted_draft_tokens": None,
            "rejected_draft_tokens": None,
            "acceptance_rate": None,
            "verify_loops": None,
            "mean_accepted_tokens_per_loop": None,
        }
        if result.dflash is not None:
            metrics.update(result.dflash)
        if compression is not None:
            metrics.update(
                {
                    "original_input_tokens": original_input_tokens,
                    "compressed_input_tokens": result.input_tokens,
                    "removed_tokens": (
                        max((original_input_tokens or 0) - result.input_tokens, 0)
                        if compression.applied
                        else 0
                    ),
                    "keep_rate": (
                        result.input_tokens / original_input_tokens
                        if compression.applied and original_input_tokens
                        else 1.0
                    ),
                    "reduction_rate": (
                        max((original_input_tokens or 0) - result.input_tokens, 0)
                        / original_input_tokens
                        if compression.applied and original_input_tokens
                        else 0.0
                    ),
                    "compression_latency_ms": compression.latency_ms,
                    "compression_device": compression.resolved_device,
                    "compression_status": compression.status,
                    "compression_fallback": compression.fallback,
                    "compression_bypassed": compression.bypassed,
                    "pipeline_e2e_ms": compression.latency_ms + result.generation_latency_ms,
                    "generation_component_ms": result.generation_latency_ms,
                }
            )
        run["conditions"][condition_id] = metrics
        await self._emit(run_id, "condition.metrics", metrics)
        await self._emit(
            run_id,
            "condition.completed",
            {"condition_id": condition_id, "text": result.text, "metrics": metrics},
        )
        return result
