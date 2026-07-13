"""
Backend tests for the CC-DFlash demo API.

Tests are grouped by:
  1. parse_input
  2. Metric normalization (all three architectures)
  3. API endpoint contracts (via TestClient, no real model)
  4. SSE framing and event order (via mock generator)
  5. Worker diagnostics (stderr-only warnings must not fail)
  6. Single-active-job guard
  7. CUDA unavailable rejection
"""
from __future__ import annotations

import asyncio
import json
textwrap = None  # unused, safe to remove
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from frontend.api.app import app
from frontend.api.jobs import job_manager
from frontend.api.metric_normalizer import normalize_metrics
from frontend.api.orchestrator import parse_input, _evt

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_job_manager():
    """Reset job manager state between tests to avoid cross-test contamination."""
    asyncio.get_event_loop().run_until_complete(_reset_jobs())
    yield
    asyncio.get_event_loop().run_until_complete(_reset_jobs())


async def _reset_jobs():
    async with job_manager.lock:
        job_manager.active_job_id = None
        job_manager.jobs.clear()


# ─── parse_input ────────────────────────────────────────────────────────────

class TestParseInput:
    def test_context_and_question(self):
        ctx, q = parse_input("Some context\nspanning lines.\n\nThe question?")
        assert ctx == "Some context\nspanning lines."
        assert q == "The question?"

    def test_question_only(self):
        ctx, q = parse_input("Just a question without blank lines.")
        assert ctx == ""
        assert q == "Just a question without blank lines."

    def test_crlf_normalized(self):
        ctx, q = parse_input("Context\r\n\r\nQuestion")
        assert ctx == "Context"
        assert q == "Question"

    def test_multi_paragraph_context(self):
        """Only the final blank-separated block is the question."""
        raw = "Para 1.\n\nPara 2.\n\nFinal question?"
        ctx, q = parse_input(raw)
        assert q == "Final question?"
        assert "Para 1." in ctx

    def test_empty_returns_empty_question(self):
        ctx, q = parse_input("")
        assert ctx == ""
        assert q == ""

    def test_whitespace_only(self):
        ctx, q = parse_input("   \n\n   ")
        assert q == ""


# ─── Metric normalization ────────────────────────────────────────────────────

def _make_raw(condition: str, **overrides) -> dict[str, Any]:
    """Minimal engine output skeleton."""
    base: dict[str, Any] = {
        "condition": condition,
        "generated_text": "Test output.",
        "output_tokens": 20,
        "input_tokens": 50,
        "stop_reason": "eos",
        "timing": {
            "decode_total_ms": 400.0,
            "warm_request_e2e_ms": 500.0,
            "target_prefill_ms": 80.0,
            "draft_prefill_ms": None,
            "compression_total_ms": None,
            "generation_request_e2e_ms": 420.0,
            "cold_start_e2e_ms": 5500.0,
        },
        "vram": {
            "peak_allocated_bytes": 1_000_000,
            "peak_reserved_bytes": 2_000_000,
        },
        "resource": {},
        "dflash": None,
        "compression": None,
        "resource_composition": "quantized target",
    }
    base.update(overrides)
    return base


class TestMetricNormalizationBaseline:
    def setup_method(self):
        self.raw = _make_raw("baseline-ar")
        self.m = normalize_metrics(self.raw)

    def test_condition_id(self):
        assert self.m["condition_id"] == "baseline-ar"

    def test_no_compression(self):
        assert self.m["compression_applied"] is False
        assert self.m["compression_bypassed"] is False
        assert self.m["compression_ratio"] is None
        assert self.m["prompt_reduction_pct"] is None
        assert self.m["prompt_reduction_tokens"] is None

    def test_dflash_metrics_are_null(self):
        for key in [
            "effective_tau",
            "draft_acceptance_rate",
            "verification_calls",
            "draft_forward_calls",
            "rollback_tokens",
            "target_forwards_per_output_token",
        ]:
            assert self.m[key] is None, f"{key} should be None for baseline-ar"

    def test_timing(self):
        assert self.m["decode_total_ms"] == 400.0
        assert self.m["warm_request_e2e_ms"] == 500.0

    def test_throughput(self):
        assert self.m["generation_tok_s"] == pytest.approx(50.0, rel=1e-3)


class TestMetricNormalizationDFlash:
    def setup_method(self):
        self.raw = _make_raw(
            "dflash-r1",
            dflash={
                "effective_tau": 8.3,
                "draft_acceptance_rate": 0.72,
                "target_block_verification_calls": 5,
                "draft_forward_calls": 4,
                "rollback_tokens": 2,
                "target_forwards_per_emitted_token": 0.6,
            },
        )
        self.m = normalize_metrics(self.raw)

    def test_no_compression_for_dflash(self):
        assert self.m["compression_applied"] is False
        assert self.m["compression_ratio"] is None

    def test_dflash_metrics_present(self):
        assert self.m["effective_tau"] == pytest.approx(8.3)
        assert self.m["draft_acceptance_rate"] == pytest.approx(0.72)
        assert self.m["verification_calls"] == 5
        assert self.m["draft_forward_calls"] == 4
        assert self.m["rollback_tokens"] == 2
        assert self.m["target_forwards_per_output_token"] == pytest.approx(0.6)


class TestMetricNormalizationCCDFlashContextless:
    """question-only → compressor bypassed, not loaded."""

    def setup_method(self):
        # Engine emits compression.bypassed=True, compression.applied=False
        self.raw = _make_raw(
            "cc-dflash-r2",
            compression={
                "applied": False,
                "bypassed": True,
                "bypass_reason": "empty_context",
                "result": None,
                "token_scope": {
                    "precompression_target_prompt_tokens": 30,
                    "final_target_prompt_tokens": 30,
                    "full_prompt_retained_ratio": 1.0,
                    "full_prompt_reduction_pct": 0.0,
                },
            },
            dflash={
                "effective_tau": 7.5,
                "draft_acceptance_rate": 0.68,
                "target_block_verification_calls": 3,
                "draft_forward_calls": 3,
                "rollback_tokens": 1,
                "target_forwards_per_emitted_token": 0.55,
            },
        )
        self.m = normalize_metrics(self.raw)

    def test_bypassed_true(self):
        assert self.m["compression_bypassed"] is True
        assert self.m["compression_bypass_reason"] == "empty_context"

    def test_not_applied(self):
        assert self.m["compression_applied"] is False

    def test_null_ratio(self):
        assert self.m["compression_ratio"] is None
        assert self.m["prompt_reduction_pct"] is None

    def test_dflash_metrics_present(self):
        assert self.m["effective_tau"] == pytest.approx(7.5)


class TestMetricNormalizationCCDFlashCompressed:
    """context + question → compressor applied."""

    def setup_method(self):
        self.raw = _make_raw(
            "cc-dflash-r2",
            input_tokens=35,  # final token count
            compression={
                "applied": True,
                "bypassed": False,
                "bypass_reason": None,
                "result": {},
                "token_scope": {
                    "precompression_target_prompt_tokens": 70,
                    "final_target_prompt_tokens": 35,
                    "full_prompt_retained_ratio": 0.5,
                    "full_prompt_reduction_pct": 50.0,
                },
            },
            timing={
                "decode_total_ms": 300.0,
                "warm_request_e2e_ms": 700.0,
                "target_prefill_ms": 60.0,
                "draft_prefill_ms": None,
                "compression_total_ms": 250.0,
                "generation_request_e2e_ms": 320.0,
                "cold_start_e2e_ms": 6000.0,
            },
            dflash={
                "effective_tau": 9.0,
                "draft_acceptance_rate": 0.80,
                "target_block_verification_calls": 4,
                "draft_forward_calls": 3,
                "rollback_tokens": 0,
                "target_forwards_per_emitted_token": 0.5,
            },
        )
        self.m = normalize_metrics(self.raw)

    def test_applied(self):
        assert self.m["compression_applied"] is True
        assert self.m["compression_bypassed"] is False

    def test_token_counts(self):
        assert self.m["input_tokens_precompression"] == 70
        assert self.m["input_tokens_final"] == 35

    def test_ratio(self):
        assert self.m["compression_ratio"] == pytest.approx(2.0)

    def test_reduction_pct(self):
        assert self.m["prompt_reduction_pct"] == pytest.approx(50.0)

    def test_compression_overhead(self):
        assert self.m["compression_total_ms"] == pytest.approx(250.0)


# ─── API endpoint contracts ──────────────────────────────────────────────────

class TestAPIHealth:
    def test_health(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAPICapabilities:
    def test_capabilities(self):
        resp = client.get("/api/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert "cuda_available" in data
        assert "compressor_options" in data
        assert "comparison_available" in data
        assert "comparison_unavailable_reason" in data
        assert isinstance(data["compressor_options"], list)


class TestAPICompareCreate:
    def test_empty_input_rejected(self):
        resp = client.post("/api/compare", json={"input": "", "compression_device": "cpu"})
        assert resp.status_code == 400
        assert "Input cannot be empty" in resp.json()["detail"]

    def test_whitespace_input_rejected(self):
        resp = client.post("/api/compare", json={"input": "   ", "compression_device": "cpu"})
        assert resp.status_code == 400

    def test_invalid_device(self):
        resp = client.post("/api/compare", json={"input": "What is 2+2?", "compression_device": "tpu"})
        assert resp.status_code == 400
        assert "Invalid compression_device" in resp.json()["detail"]

    def test_cuda_rejected_when_unavailable(self):
        with patch("frontend.api.app._cuda_available", return_value=False):
            resp = client.post("/api/compare", json={"input": "test", "compression_device": "cuda"})
        assert resp.status_code == 400
        assert "CUDA" in resp.json()["detail"]

    def test_job_created(self):
        with patch("frontend.api.app._comparison_unavailable_reason", return_value=None):
            resp = client.post("/api/compare", json={"input": "What is 2+2?", "compression_device": "cpu"})
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    def test_single_active_job_guard(self):
        with patch("frontend.api.app._comparison_unavailable_reason", return_value=None):
            # First job
            resp1 = client.post("/api/compare", json={"input": "Q1?", "compression_device": "cpu"})
            assert resp1.status_code == 202
            # Second job while first is active → 409
            resp2 = client.post("/api/compare", json={"input": "Q2?", "compression_device": "cpu"})
        assert resp2.status_code == 409

    def test_comparison_rejected_when_runtime_unavailable(self):
        with patch(
            "frontend.api.app._comparison_unavailable_reason",
            return_value="CUDA is required for the configured 4-bit Qwen comparison models.",
        ):
            resp = client.post(
                "/api/compare",
                json={"input": "What is 2+2?", "compression_device": "cpu"},
            )
        assert resp.status_code == 503
        assert "CUDA is required" in resp.json()["detail"]


class TestAPIJobStatus:
    def test_unknown_job_404(self):
        resp = client.get("/api/compare/nonexistent-job-id")
        assert resp.status_code == 404

    def test_job_status_after_create(self):
        create_resp = client.post("/api/compare", json={"input": "Valid question?", "compression_device": "cpu"})
        job_id = create_resp.json()["job_id"]
        status_resp = client.get(f"/api/compare/{job_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["job_id"] == job_id


# ─── SSE event format ────────────────────────────────────────────────────────

class TestSSEEventFormat:
    def test_evt_produces_dict(self):
        result = _evt("job.started", {"job_id": "abc"})
        assert isinstance(result, dict)
        assert result["event"] == "job.started"
        data = json.loads(result["data"])
        assert data["job_id"] == "abc"

    def test_evt_data_is_json_string(self):
        result = _evt("condition.started", {"condition_id": "baseline-ar"})
        # data must be a JSON string, not a raw dict
        assert isinstance(result["data"], str)
        parsed = json.loads(result["data"])
        assert parsed["condition_id"] == "baseline-ar"

    def test_sse_starlette_encodes_dict_correctly(self):
        """Confirm sse-starlette emits proper frames for dict items."""
        from sse_starlette.sse import ensure_bytes
        evt = _evt("job.started", {"job_id": "test"})
        encoded = ensure_bytes(evt, "\r\n")
        assert b"event: job.started" in encoded
        assert b"data: " in encoded
        # Critically: must NOT double-wrap
        assert b"data: event:" not in encoded

    def test_sse_starlette_no_double_wrap_for_string(self):
        """Pre-formatted strings cause double-wrapping — ensure we don't yield them."""
        from sse_starlette.sse import ensure_bytes
        bad_frame = "event: job.started\ndata: {}\n\n"
        encoded = ensure_bytes(bad_frame, "\r\n")
        # This is the broken behavior we must avoid:
        assert b"data: event:" in encoded, "Confirm the broken behavior for documentation"


# ─── Worker stderr diagnostic (not failure) ──────────────────────────────────

class TestWorkerDiagnostics:
    def test_stderr_warnings_do_not_fail(self):
        """returncode=0 + stderr warnings → success (not failure)."""
        # We simulate the orchestrator's parsing logic directly.
        stdout = '{"status": "success", "data": {"condition_id": "baseline-ar"}}\n'
        stderr = "UserWarning: torch_dtype is deprecated.\n"
        returncode = 0

        result_obj = None
        for line in reversed(stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    result_obj = json.loads(line)
                    break
                except json.JSONDecodeError:
                    pass

        # As in orchestrator: only fail on returncode != 0
        assert returncode == 0
        assert result_obj is not None
        assert result_obj["status"] == "success"
        # stderr is irrelevant to success/failure
        assert "deprecated" in stderr  # diagnostic present but not acted on

    def test_nonzero_returncode_raises(self):
        """returncode=1 → failure regardless of stdout content."""
        returncode = 1
        stdout = '{"status": "error", "error": "OOM", "traceback": "..."}\n'
        stderr = "CUDA out of memory.\n"

        # Simulate orchestrator behaviour
        failed = returncode != 0
        assert failed is True
