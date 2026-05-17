import json

from htfsd.cli.generate import write_trace_jsonl
from htfsd.benchmarks.fixtures import load_prompt_fixtures
from htfsd.benchmarks.baseline_e4b import baseline_row
from htfsd.benchmarks.low_tier import write_benchmark_row
from htfsd.types import CycleTrace


def test_write_trace_jsonl(tmp_path):
    output = tmp_path / "trace.jsonl"
    trace = [
        CycleTrace(
            cycle_index=0,
            context_tokens=2,
            dflash_parse_ok=True,
            malformed_dflash=False,
            draft_text_chars=1,
            draft_candidate_tokens=1,
            accepted_tokens=1,
            reject_position=None,
            candidate_exhausted=True,
            fallback_used=False,
            qwen_draft_ms=1.0,
            dflash_parse_ms=0.1,
            gemma_retokenize_ms=0.1,
            e2b_verify_ms=1.0,
            cycle_ms=2.2,
        )
    ]

    write_trace_jsonl(output, trace)

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["cycle_index"] == 0
    assert rows[0]["candidate_exhausted"] is True


def test_load_prompt_fixtures(tmp_path):
    fixture = tmp_path / "prompts.jsonl"
    fixture.write_text('{"id":"a","prompt":"Hello","max_new_tokens":3}\n', encoding="utf-8")

    rows = load_prompt_fixtures(fixture)

    assert rows == [{"id": "a", "prompt": "Hello", "max_new_tokens": 3}]


def test_write_benchmark_row_jsonl(tmp_path):
    output = tmp_path / "low.jsonl"
    write_benchmark_row(
        output,
        {
            "prompt_id": "a",
            "status": "ok",
            "error": None,
            "metrics": {"generated_tokens": 1},
        },
    )

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["prompt_id"] == "a"
    assert rows[0]["status"] == "ok"


def test_baseline_row_shape():
    row = baseline_row(
        prompt_id="p1",
        prompt_tokens=5,
        generated_tokens=7,
        total_ms=100.0,
        output_text="hello",
    )

    assert row["prompt_id"] == "p1"
    assert row["tokens_per_second"] == 70.0
    assert row["latency_per_token_ms"] == 100.0 / 7
    assert row["output_text"] == "hello"
