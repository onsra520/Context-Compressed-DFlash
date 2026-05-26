from __future__ import annotations

import json
from pathlib import Path

from htfsd.cli.run_low_tier_cycle_trace import main as cycle_trace_main
from htfsd.metrics.cycle_trace_schema import (
    CYCLE_NON_CLAIMS,
    LowTierCycle,
    LowTierCycleTraceRecord,
    write_cycle_trace_json,
)
from htfsd.text_bridge.cycle_trace import run_low_tier_cycle_trace_for_prompt
from htfsd.types import TextGenerationResult


class SequenceBackend:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    def generate_text(self, prompt: str, *, max_tokens: int, temperature: float, stop=None) -> TextGenerationResult:
        self.prompts.append(prompt)
        text = self.outputs.pop(0) if self.outputs else ""
        return TextGenerationResult(text=text, completion_tokens=max_tokens)

    def generate_chat(self, messages, *, max_tokens: int, temperature: float, stop=None) -> TextGenerationResult:
        prompt = messages[-1]["content"]
        return self.generate_text(prompt, max_tokens=max_tokens, temperature=temperature, stop=stop)


def test_cycle_trace_schema_serializes_to_json_without_forbidden_fields() -> None:
    record = LowTierCycleTraceRecord(
        prompt_id="prompt-001",
        prompt_summary="Prompt",
        prompt_hash="abc123",
        prompt_set_id="phase-2-controlled-eligibility-v2",
        prompt_mode="raw",
        capture_raw_output=True,
        draft_block_size=8,
        max_cycles=1,
        max_total_tokens=None,
        total_cycles=1,
        bridge_valid_block_count=1,
        bridge_rejected_block_count=0,
        cycle_fallback_count=0,
        runtime_policy="drafter_cpu_verifier_cuda",
        drafter_device_status="ok",
        verifier_device_status="ok",
        drafter_model_file="drafter.gguf",
        verifier_model_file="verifier.gguf",
        cycles=[
            LowTierCycle(
                cycle_id=1,
                draft_block_size=8,
                draft_text_summary="draft",
                bridge_status="valid",
                rejection_reason=None,
                cycle_fallback_count=0,
                drafter_latency_seconds=0.1,
                verifier_latency_seconds=0.2,
                context_length_before=6,
                context_length_after=18,
            )
        ],
        non_claims=list(CYCLE_NON_CLAIMS),
    )

    data = record.to_dict()

    assert data["trace_type"] == "low_tier_cycle_trace"
    assert data["bridge_valid_block_count"] == 1
    assert data["cycles"][0]["draft_block_size"] == 8
    assert data["cycles"][0]["rejection_reason"] is None
    for forbidden in ("accepted_tokens", "acceptance_rate", "speedup", "performance_gain", "benchmark_score"):
        assert forbidden not in _all_keys(data)


def test_cycle_trace_records_valid_and_rejected_paths() -> None:
    drafter = SequenceBackend(["good draft", "<think>unfinished"])
    verifier = SequenceBackend([" verifier one", " fallback two"])

    record = run_low_tier_cycle_trace_for_prompt(
        prompt="Start",
        prompt_id="prompt-001",
        prompt_set_id="phase-2-controlled-eligibility-v2",
        prompt_mode="raw",
        drafter_backend=drafter,
        verifier_backend=verifier,
        draft_block_size=8,
        max_cycles=2,
        max_total_tokens=None,
        temperature=0.0,
        stop=None,
        capture_raw_output=True,
        drafter_model_file="drafter.gguf",
        verifier_model_file="verifier.gguf",
        drafter_device_status="ok",
        verifier_device_status="ok",
    )

    data = record.to_dict()

    assert data["total_cycles"] == 2
    assert data["bridge_valid_block_count"] == 1
    assert data["bridge_rejected_block_count"] == 1
    assert data["cycle_fallback_count"] == 1
    assert data["cycles"][0]["bridge_status"] == "valid"
    assert data["cycles"][1]["bridge_status"] == "rejected"
    assert data["cycles"][1]["rejection_reason"] == "contains_unclosed_think"
    assert data["cycles"][1]["cycle_fallback_count"] == 1
    assert data["cycles"][0]["draft_text_chunk"] == "good draft"
    assert data["cycles"][1]["verifier_raw_output"] == " fallback two"
    assert drafter.prompts[1].startswith("Start good draft")


def test_write_cycle_trace_json_includes_run_level_fields(tmp_path: Path) -> None:
    record = run_low_tier_cycle_trace_for_prompt(
        prompt="Start",
        prompt_id="prompt-001",
        prompt_set_id="phase-2-controlled-eligibility-v2",
        prompt_mode="raw",
        drafter_backend=SequenceBackend(["draft"]),
        verifier_backend=SequenceBackend([" verifier"]),
        draft_block_size=8,
        max_cycles=1,
        max_total_tokens=32,
        temperature=0.0,
        stop=None,
        capture_raw_output=False,
        drafter_model_file="drafter.gguf",
        verifier_model_file="verifier.gguf",
        drafter_device_status="ok",
        verifier_device_status="ok",
    )

    path = write_cycle_trace_json(
        records=[record],
        output_dir=tmp_path,
        metadata={
            "trace_type": "low_tier_cycle_trace",
            "prompt_set_id": "phase-2-controlled-eligibility-v2",
            "draft_block_size": 8,
        },
    )
    payload = json.loads(path.read_text())

    assert payload["metadata"]["trace_type"] == "low_tier_cycle_trace"
    assert payload["records"][0]["prompt_id"] == "prompt-001"
    assert payload["records"][0]["max_total_tokens"] == 32
    assert "cycles" in payload["records"][0]


def test_cycle_trace_cli_args_parse_and_write_report(tmp_path: Path) -> None:
    exit_code = cycle_trace_main(
        [
            "--prompt",
            "Start",
            "--draft-block-size",
            "8",
            "--max-cycles",
            "1",
            "--capture-raw-output",
            "--output-dir",
            str(tmp_path),
            "--fake",
        ]
    )

    assert exit_code == 0
    trace_files = list(tmp_path.glob("*-low-tier-cycle-trace.json"))
    assert trace_files
    payload = json.loads(trace_files[0].read_text())
    assert payload["records"][0]["draft_block_size"] == 8
    assert payload["records"][0]["max_cycles"] == 1


def _all_keys(value) -> set[str]:  # type: ignore[no-untyped-def]
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys.update(_all_keys(item))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for item in value:
            keys.update(_all_keys(item))
        return keys
    return set()
