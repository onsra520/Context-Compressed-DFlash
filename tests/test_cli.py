import json

from htfsd.cli.generate import write_trace_jsonl
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
