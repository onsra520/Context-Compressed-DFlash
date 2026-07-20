from __future__ import annotations

import inspect
import importlib
import json
import threading

import torch
from fastapi.testclient import TestClient

from ccdf.api.app import create_app
from ccdf.api.runtime_adapter import LiveCompressionResult, LiveGenerationResult
from ccdf.dflash import generate as dflash_module
from ccdf.dflash.verifier import VerificationResult
from ccdf.inference.baseline import generate_baseline
from ccdf.runtime.engine import RuntimeEngine
from ccdf.runtime.schemas import GenerationSettings, MemoryStats


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.compression_devices: list[str] = []
        self.proposal_only_token = 777

    def analyze_input(self, prompt: str) -> dict[str, int]:
        self.calls.append("analyze")
        return {"characters": len(prompt), "words": len(prompt.split())}

    def generate(self, *, condition_id, prompt, max_new_tokens, on_tokens_committed):
        self.calls.append(condition_id)
        on_tokens_committed([10], f"{condition_id}:first")
        # 777 represents a rejected/unverified proposal and is deliberately not committed.
        on_tokens_committed([11, 12], ":verified")
        dflash = None
        if condition_id != "baseline-ar":
            dflash = {
                "proposed_draft_tokens": 6,
                "accepted_draft_tokens": 3,
                "rejected_draft_tokens": 3,
                "acceptance_rate": 0.5,
                "verify_loops": 2,
                "mean_accepted_tokens_per_loop": 1.5,
            }
        return LiveGenerationResult(
            text=f"{condition_id}:first:verified",
            input_tokens=20 if condition_id != "cc-dflash" else 12,
            output_tokens=4,
            stop_reason="max_new_tokens",
            ttft_ms=12.0,
            generation_latency_ms=100.0,
            dflash=dflash,
        )

    def compress(self, *, prompt: str, device: str) -> LiveCompressionResult:
        self.calls.append("compress")
        self.compression_devices.append(device)
        return LiveCompressionResult(
            prompt="compressed prompt",
            original_input_tokens=20,
            compressed_input_tokens=12,
            removed_tokens=8,
            keep_rate=0.6,
            reduction_rate=0.4,
            latency_ms=25.0,
            requested_device=device,
            resolved_device="cuda:0" if device == "cuda" else "cpu",
            status="COMPRESSED",
            applied=True,
            bypassed=False,
            fallback=False,
        )


def _events(response) -> list[dict]:
    events = []
    for line in response.iter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line.removeprefix("data: ")))
    return events


def _run(client: TestClient, *, device: str = "cpu") -> tuple[str, list[dict]]:
    created = client.post(
        "/api/demo/runs",
        json={"prompt": "arbitrary prompt", "compression_device": device, "max_new_tokens": 32},
    )
    assert created.status_code == 202
    run_id = created.json()["run_id"]
    with client.stream("GET", f"/api/demo/runs/{run_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _events(response)
    return run_id, events


def test_api_creates_run_and_streams_conditions_in_required_order() -> None:
    backend = FakeBackend()
    with TestClient(create_app(backend=backend)) as client:
        run_id, events = _run(client)
        snapshot = client.get(f"/api/demo/runs/{run_id}").json()

    assert snapshot["status"] == "completed"
    assert backend.calls == ["analyze", "baseline-ar", "d-flash", "compress", "cc-dflash"]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert [
        event["data"]["condition_id"]
        for event in events
        if event["type"] == "condition.started"
    ] == ["baseline-ar", "d-flash", "cc-dflash"]
    event_types = [event["type"] for event in events]
    assert event_types.index("compression.started") > max(
        index
        for index, event in enumerate(events)
        if event["type"] == "condition.completed" and event["data"]["condition_id"] == "d-flash"
    )
    assert event_types[-2:] == ["comparison.completed", "run.completed"]


def test_token_deltas_precede_completion_and_exclude_unverified_proposals() -> None:
    backend = FakeBackend()
    with TestClient(create_app(backend=backend)) as client:
        _, events = _run(client)

    for condition_id in ("baseline-ar", "d-flash", "cc-dflash"):
        delta_indexes = [
            index
            for index, event in enumerate(events)
            if event["type"] == "condition.token_delta"
            and event["data"]["condition_id"] == condition_id
        ]
        completed_index = next(
            index
            for index, event in enumerate(events)
            if event["type"] == "condition.completed"
            and event["data"]["condition_id"] == condition_id
        )
        assert delta_indexes and max(delta_indexes) < completed_index
    streamed_ids = [
        token
        for event in events
        if event["type"] == "condition.token_delta"
        for token in event["data"]["token_ids"]
    ]
    assert backend.proposal_only_token not in streamed_ids


def test_live_metric_formulas_and_acceptance_fields() -> None:
    with TestClient(create_app(backend=FakeBackend())) as client:
        run_id, _ = _run(client)
        conditions = client.get(f"/api/demo/runs/{run_id}").json()["conditions"]

    assert conditions["baseline-ar"]["ttft_ms"] == 12.0
    assert conditions["baseline-ar"]["decode_tok_s"] == 40.0
    assert conditions["baseline-ar"]["pipeline_e2e_ms"] == 100.0
    assert conditions["d-flash"]["acceptance_rate"] == 0.5
    assert conditions["d-flash"]["mean_accepted_tokens_per_loop"] == 1.5
    assert conditions["cc-dflash"]["pipeline_e2e_ms"] == 125.0
    assert conditions["cc-dflash"]["reduction_rate"] == 0.4


def test_cpu_and_cuda_compression_devices_are_forwarded(monkeypatch) -> None:
    app_module = importlib.import_module("ccdf.api.app")
    for device in ("cpu", "cuda"):
        backend = FakeBackend()
        if device == "cuda":
            monkeypatch.setattr(app_module.torch.cuda, "is_available", lambda: True)
        with TestClient(create_app(backend=backend)) as client:
            _run(client, device=device)
        assert backend.compression_devices == [device]


def test_cuda_compression_failure_has_no_cpu_fallback(monkeypatch) -> None:
    class FailingCudaBackend(FakeBackend):
        def compress(self, *, prompt: str, device: str) -> LiveCompressionResult:
            self.compression_devices.append(device)
            raise RuntimeError("synthetic CUDA compressor failure")

    app_module = importlib.import_module("ccdf.api.app")
    monkeypatch.setattr(app_module.torch.cuda, "is_available", lambda: True)
    backend = FailingCudaBackend()
    with TestClient(create_app(backend=backend)) as client:
        run_id, events = _run(client, device="cuda")
        snapshot = client.get(f"/api/demo/runs/{run_id}").json()

    assert snapshot["status"] == "failed"
    assert backend.compression_devices == ["cuda"]
    assert "CUDA compressor failure" in snapshot["error"]
    assert events[-1]["type"] == "run.failed"


def test_cancel_emits_terminal_cancel_event() -> None:
    class BlockingBackend(FakeBackend):
        def __init__(self) -> None:
            super().__init__()
            self.started = threading.Event()
            self.release = threading.Event()

        def generate(self, **kwargs):
            self.started.set()
            self.release.wait(timeout=2)
            return super().generate(**kwargs)

    backend = BlockingBackend()
    with TestClient(create_app(backend=backend)) as client:
        created = client.post(
            "/api/demo/runs",
            json={"prompt": "cancel me", "compression_device": "cpu", "max_new_tokens": 32},
        )
        run_id = created.json()["run_id"]
        assert backend.started.wait(timeout=1)
        cancelled = client.post(f"/api/demo/runs/{run_id}/cancel")
        assert cancelled.status_code == 200
        backend.release.set()
        with client.stream("GET", f"/api/demo/runs/{run_id}/events") as response:
            events = _events(response)
    assert events[-1]["type"] == "run.cancelled"


def test_run_manager_queues_second_run_behind_first() -> None:
    class QueueProbeBackend(FakeBackend):
        def __init__(self) -> None:
            super().__init__()
            self.first_generation_started = threading.Event()
            self.release_first_generation = threading.Event()
            self._blocked_once = False

        def generate(self, **kwargs):
            if not self._blocked_once:
                self._blocked_once = True
                self.first_generation_started.set()
                self.release_first_generation.wait(timeout=2)
            return super().generate(**kwargs)

    backend = QueueProbeBackend()
    payload = {"prompt": "queued prompt", "compression_device": "cpu", "max_new_tokens": 32}
    with TestClient(create_app(backend=backend)) as client:
        first_id = client.post("/api/demo/runs", json=payload).json()["run_id"]
        assert backend.first_generation_started.wait(timeout=1)
        second_id = client.post("/api/demo/runs", json=payload).json()["run_id"]
        assert client.get(f"/api/demo/runs/{second_id}").json()["status"] == "queued"
        backend.release_first_generation.set()
        with client.stream("GET", f"/api/demo/runs/{first_id}/events") as response:
            assert _events(response)[-1]["type"] == "run.completed"
        with client.stream("GET", f"/api/demo/runs/{second_id}/events") as response:
            assert _events(response)[-1]["type"] == "run.completed"

    expected = ["analyze", "baseline-ar", "d-flash", "compress", "cc-dflash"]
    assert backend.calls == expected + expected


def test_capabilities_samples_and_request_validation() -> None:
    with TestClient(create_app(backend=FakeBackend())) as client:
        capabilities = client.get("/api/demo/capabilities")
        samples = client.get("/api/demo/prompt-samples")
        invalid = client.post(
            "/api/demo/runs",
            json={"prompt": "   ", "compression_device": "cpu", "max_new_tokens": 32},
        )
    assert capabilities.status_code == 200
    assert capabilities.json()["token_streaming"] is True
    assert samples.json()["samples"]
    assert invalid.status_code == 422


def test_streaming_hooks_are_optional_for_non_streaming_callers() -> None:
    assert inspect.signature(generate_baseline).parameters["on_tokens_committed"].default is None
    assert inspect.signature(dflash_module.generate_dflash).parameters["on_tokens_committed"].default is None
    assert inspect.signature(RuntimeEngine.generate).parameters["on_tokens_committed"].default is None


def test_dflash_hook_only_emits_verified_tokens(monkeypatch) -> None:
    class Tokenizer:
        def decode(self, token_ids, **kwargs):
            return " ".join(str(token) for token in token_ids)

    class Target(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.device = torch.device("cpu")
            self.model = type("Model", (), {"embed_tokens": torch.nn.Embedding(128, 4)})()
            self.lm_head = torch.nn.Linear(4, 128, bias=False)

    class Drafter(torch.nn.Module):
        block_size = 4
        mask_token_id = 0
        target_layer_ids = [0]

        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.ones(1, dtype=torch.float32))

        def forward(self, *, noise_embedding, **kwargs):
            return torch.zeros_like(noise_embedding)

    class Verifier:
        prompt_length = 1
        cache_length = 3

        def __init__(self, *args, **kwargs):
            pass

        def prefill(self):
            return 10, torch.zeros((1, 1, 4))

        def verify(self, *, start, proposal_count, **kwargs):
            return VerificationResult(
                start=start,
                proposal_count=proposal_count,
                accepted_count=1,
                correction_token_id=99,
                emitted_tokens=[11, 99],
                raw_advance=2,
                all_proposals_accepted=False,
                cache_length_before=start,
                cache_length_after=start + 2,
                target_hidden=torch.zeros((1, 2, 4)),
                proposals=[11, 12],
                verifier_ids=[11, 99],
            )

    monkeypatch.setattr(dflash_module, "TargetVerifier", Verifier)
    monkeypatch.setattr(dflash_module, "sample", lambda logits, temperature: torch.tensor([[11, 12]]))
    monkeypatch.setattr(dflash_module, "reset_peak_memory", lambda: None)
    monkeypatch.setattr(
        dflash_module,
        "current_memory_state",
        lambda: {"allocated_bytes": 0, "reserved_bytes": 0},
    )
    monkeypatch.setattr(dflash_module, "synchronize", lambda device=None: None)
    monkeypatch.setattr(dflash_module, "collect_memory", lambda limit_gib: MemoryStats())
    monkeypatch.setattr(dflash_module, "enforce_memory_gate", lambda memory, label: None)
    committed: list[list[int]] = []
    output = dflash_module.generate_dflash(
        Target(),
        Drafter(),
        Tokenizer(),
        torch.tensor([[1]]),
        GenerationSettings(max_new_tokens=3, temperature=0.0, stop_token_ids=()),
        model_metadata={},
        block_policy=type(
            "Policy",
            (),
            {
                "next_block_size": lambda self: 4,
                "observe": lambda self, count: None,
                "mode": "fixed",
                "rolling_tau": 0.0,
            },
        )(),
        memory_limit_gib=1.0,
        on_tokens_committed=lambda token_ids, text_delta: committed.append(list(token_ids)),
    )
    assert output.generated_token_ids == [10, 11, 99]
    assert committed == [[10], [11, 99]]
    assert 12 not in [token for chunk in committed for token in chunk]
