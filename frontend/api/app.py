"""
FastAPI application for the CC-DFlash three-way comparison demo API.

All SSE events are emitted as dicts; sse-starlette encodes them correctly.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

try:
    import torch as _torch

    def _cuda_available() -> bool:
        return _torch.cuda.is_available()

    def _gpu_name() -> str | None:
        return _torch.cuda.get_device_name(0) if _cuda_available() else None

except ImportError:  # pragma: no cover
    def _cuda_available() -> bool:
        return False

    def _gpu_name() -> str | None:
        return None


from sse_starlette.sse import EventSourceResponse

from .jobs import job_manager
from .orchestrator import run_comparison_job
from .schemas import CompareRequest, JobStatusResponse


def _comparison_unavailable_reason() -> str | None:
    """Return a user-facing prerequisite error before a job is accepted.

    The configured Qwen checkpoints use bitsandbytes 4-bit quantization, so
    accepting a comparison without CUDA only defers an inevitable worker
    failure until after the browser has opened its SSE stream.
    """
    if not _cuda_available():
        return "CUDA is required for the configured 4-bit Qwen comparison models."
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    yield
    # Ensure any leftover active job is cleared on shutdown.
    await job_manager.complete_job(job_manager.active_job_id or "")


app = FastAPI(title="CC-DFlash Demo API", lifespan=lifespan)


@app.get("/api/health")
async def health_check() -> dict:
    return {"status": "ok", "version": "1.1"}


@app.get("/api/capabilities")
async def get_capabilities() -> dict:
    cuda = _cuda_available()
    unavailable_reason = _comparison_unavailable_reason()
    return {
        "cuda_available": cuda,
        "gpu_name": _gpu_name(),
        "compressor_options": ["cpu", "cuda"] if cuda else ["cpu"],
        "comparison_available": unavailable_reason is None,
        "comparison_unavailable_reason": unavailable_reason,
        "job_active": await job_manager.is_busy(),
    }


@app.post("/api/compare", status_code=202)
async def create_compare_job(req: CompareRequest) -> JobStatusResponse:
    if not req.input.strip():
        raise HTTPException(status_code=400, detail="Input cannot be empty")

    if req.compression_device not in ("cpu", "cuda"):
        raise HTTPException(status_code=400, detail="Invalid compression_device")

    if req.compression_device == "cuda" and not _cuda_available():
        raise HTTPException(status_code=400, detail="CUDA is not available on this server")

    unavailable_reason = _comparison_unavailable_reason()
    if unavailable_reason is not None:
        raise HTTPException(status_code=503, detail=unavailable_reason)

    try:
        job_id = await job_manager.create_job()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    job = await job_manager.get_job(job_id)
    job["request"] = {"input": req.input, "compression_device": req.compression_device}

    return JobStatusResponse(job_id=job_id, status="queued")


@app.get("/api/compare/{job_id}")
async def get_job_status(job_id: str) -> dict:
    """Snapshot recovery — allows frontend to poll or reconnect."""
    job = await job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/compare/{job_id}/events")
async def get_job_events(job_id: str, request: Request) -> EventSourceResponse:
    job = await job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return EventSourceResponse(
        run_comparison_job(
            job_id,
            job["request"]["input"],
            job["request"]["compression_device"],
        ),
        ping=20,  # keepalive comment every 20 s to prevent proxy timeouts
    )
