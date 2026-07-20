"""FastAPI surface for the arbitrary-prompt live streaming demo."""

from __future__ import annotations

from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from .jobs import DemoRunManager
from .runtime_adapter import RealDemoBackend
from .schemas import CreateRunRequest, CreateRunResponse


PROMPT_SAMPLES = [
    {
        "id": "concise-explanation",
        "label": "Giải thích ngắn",
        "prompt": "Explain speculative decoding in three concise bullet points.",
    },
    {
        "id": "context-question",
        "label": "Context + câu hỏi",
        "prompt": (
            "A small inference service runs an autoregressive target model. A draft model "
            "proposes several tokens, and the target verifies the proposal before output is "
            "committed. Context compression happens before target prefill.\n\n"
            "Why must unverified proposal tokens stay hidden from the user?"
        ),
    },
]


def create_app(*, backend: object | None = None) -> FastAPI:
    run_manager = DemoRunManager(backend or RealDemoBackend())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await run_manager.start()
        yield
        await run_manager.stop()

    demo_app = FastAPI(title="CCDF Live Streaming Demo", version="1.0", lifespan=lifespan)
    demo_app.state.run_manager = run_manager

    @demo_app.get("/api/demo/capabilities")
    async def capabilities() -> dict:
        cuda_available = torch.cuda.is_available()
        return {
            "real_model": True,
            "token_streaming": True,
            "sequential_execution": True,
            "cuda_available": cuda_available,
            "gpu_name": torch.cuda.get_device_name(0) if cuda_available else None,
            "compression_devices": ["cuda", "cpu"],
            "default_compression_device": "cuda",
            "max_new_tokens": {"minimum": 1, "maximum": 256, "default": 64},
        }

    @demo_app.get("/api/demo/prompt-samples")
    async def prompt_samples() -> dict:
        return {"samples": PROMPT_SAMPLES}

    @demo_app.post("/api/demo/runs", response_model=CreateRunResponse, status_code=202)
    async def create_run(payload: CreateRunRequest) -> CreateRunResponse:
        if payload.compression_device == "cuda" and not torch.cuda.is_available():
            raise HTTPException(
                status_code=400,
                detail="CUDA compression was requested but CUDA is unavailable",
            )
        run_id = await run_manager.create_run(
            prompt=payload.prompt,
            compression_device=payload.compression_device,
            max_new_tokens=payload.max_new_tokens,
        )
        return CreateRunResponse(run_id=run_id, status="queued")

    @demo_app.get("/api/demo/runs/{run_id}/events")
    async def run_events(
        run_id: str,
        request: Request,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        if not await run_manager.exists(run_id):
            raise HTTPException(status_code=404, detail="Run not found")
        try:
            after_sequence = int(last_event_id or "0")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Last-Event-ID must be an integer") from exc
        return StreamingResponse(
            run_manager.stream_sse(run_id, request=request, after_sequence=after_sequence),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @demo_app.get("/api/demo/runs/{run_id}")
    async def get_run(run_id: str) -> dict:
        snapshot = await run_manager.snapshot(run_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return snapshot

    @demo_app.post("/api/demo/runs/{run_id}/cancel")
    async def cancel_run(run_id: str) -> dict:
        snapshot = await run_manager.cancel(run_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return snapshot

    return demo_app


app = create_app()
