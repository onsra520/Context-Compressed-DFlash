from __future__ import annotations

import json
from pathlib import Path

from htfsd.cli.generate_low_tier import main as generate_main
from htfsd.low_tier.generate import run_low_tier_generate
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
        return self.generate_text(messages[-1]["content"], max_tokens=max_tokens, temperature=temperature, stop=stop)


def test_generate_pipeline_returns_response_text_and_metrics() -> None:
    drafter = SequenceBackend(["small draft", "second draft"])
    verifier = SequenceBackend([" verifier one", " verifier two"])

    result = run_low_tier_generate(
        prompt="Start",
        prompt_mode="raw",
        drafter_backend=drafter,
        verifier_backend=verifier,
        draft_block_size=8,
        max_cycles=2,
        max_total_chars=None,
        temperature=0.0,
        stop=None,
        capture_raw_output=True,
    )

    payload = result.to_dict()

    assert payload["trace_type"] == "low_tier_cycle_generate"
    assert payload["response_text"] == "small draft  verifier one second draft  verifier two"
    assert payload["total_cycles"] == 2
    assert payload["bridge_valid_block_count"] == 2
    assert payload["bridge_rejected_block_count"] == 0
    assert payload["cycle_fallback_count"] == 0
    assert payload["metrics"]["response_chars"] == len(payload["response_text"])
    assert payload["metrics"]["drafter_latency_seconds_total"] >= 0
    assert payload["metrics"]["verifier_latency_seconds_total"] >= 0
    assert payload["cycles"][0]["draft_text_chunk"] == "small draft"
    assert payload["cycles"][0]["verifier_text_chunk"] == " verifier one"


def test_generate_pipeline_records_rejected_block_and_fallback_path() -> None:
    drafter = SequenceBackend(["<think>unfinished"])
    verifier = SequenceBackend(["fallback text"])

    result = run_low_tier_generate(
        prompt="Start",
        prompt_mode="raw",
        drafter_backend=drafter,
        verifier_backend=verifier,
        draft_block_size=8,
        max_cycles=1,
        max_total_chars=None,
        temperature=0.0,
        stop=None,
        capture_raw_output=False,
    )

    payload = result.to_dict()

    assert payload["response_text"] == "fallback text"
    assert payload["bridge_valid_block_count"] == 0
    assert payload["bridge_rejected_block_count"] == 1
    assert payload["cycle_fallback_count"] == 1
    assert payload["cycles"][0]["bridge_status"] == "rejected"
    assert payload["cycles"][0]["rejection_reason"] == "contains_unclosed_think"
    assert payload["cycles"][0]["cycle_fallback_count"] == 1


def test_generate_result_serializes_without_forbidden_fields() -> None:
    result = run_low_tier_generate(
        prompt="Start",
        prompt_mode="raw",
        drafter_backend=SequenceBackend(["draft"]),
        verifier_backend=SequenceBackend(["verifier"]),
        draft_block_size=8,
        max_cycles=1,
        max_total_chars=None,
        temperature=0.0,
        stop=None,
        capture_raw_output=False,
    )

    data = result.to_dict()

    assert "bridge_valid_block_count" in data
    assert "cycle_fallback_count" in data
    for forbidden in (
        "accepted_tokens",
        "accepted_blocks",
        "acceptance_rate",
        "speedup",
        "performance_gain",
        "benchmark_score",
    ):
        assert forbidden not in _all_keys(data)
    assert "No draft-acceptance metric is reported." in result.non_claims


def test_generate_cli_prints_text_output_with_metrics(capsys) -> None:
    exit_code = generate_main(
        [
            "--prompt",
            "Hello. Reply in one short sentence.",
            "--draft-block-size",
            "8",
            "--max-cycles",
            "1",
            "--fake",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "RESPONSE:" in output
    assert "METRICS:" in output
    assert "trace_type: low_tier_cycle_generate" in output
    assert "bridge_valid_block_count:" in output
    assert "cycle_fallback_count:" in output


def test_generate_cli_writes_json_and_trace(tmp_path: Path, capsys) -> None:
    exit_code = generate_main(
        [
            "--prompt",
            "Explain caching in one sentence.",
            "--draft-block-size",
            "8",
            "--max-cycles",
            "1",
            "--json",
            "--write-trace",
            "--output-dir",
            str(tmp_path),
            "--fake",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["trace_type"] == "low_tier_cycle_generate"
    assert payload["response_text"]
    trace_files = list(tmp_path.glob("*-low-tier-generate-trace.json"))
    assert trace_files
    trace_payload = json.loads(trace_files[0].read_text())
    assert trace_payload["trace_type"] == "low_tier_cycle_generate"
    assert trace_payload["response_text"] == payload["response_text"]


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
