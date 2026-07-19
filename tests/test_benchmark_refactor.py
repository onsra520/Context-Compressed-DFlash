import json

import pytest

from ccdf.benchmark import _summarize, read_jsonl, run_benchmark, write_jsonl
from ccdf.benchmark import runner


def _row(*, speed: float, peak: int, gate: bool | None = True) -> dict:
    return {
        "metrics": {
            "decode_tok_s": speed,
            "generation_tok_s": speed / 2,
            "warm_request_tok_s": speed / 4,
        },
        "timing": {"target_prefill_ms": speed + 1, "decode_total_ms": speed + 2},
        "memory": {"peak_reserved_bytes": peak, "gate_pass": gate},
    }


def test_jsonl_round_trip_preserves_unicode_and_sorted_keys(tmp_path) -> None:
    path = tmp_path / "nested" / "rows.jsonl"
    rows = [{"prompt": "xin chào", "id": "p1"}, {"id": "p2", "prompt": "two"}]

    write_jsonl(path, rows)

    assert read_jsonl(path) == rows
    assert path.read_text(encoding="utf-8").splitlines()[0] == json.dumps(
        rows[0], ensure_ascii=False, sort_keys=True
    )


def test_read_jsonl_reports_contract_line(tmp_path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text("\n" + json.dumps({"id": "missing-prompt"}) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 2 must contain id and prompt"):
        read_jsonl(path)


def test_baseline_aggregation_recomputes_means_and_peak() -> None:
    summary = _summarize("baseline", [_row(speed=2.0, peak=10), _row(speed=4.0, peak=20)])

    assert summary == {
        "condition": "baseline",
        "rows": 2,
        "mean_decode_tok_s": 3.0,
        "mean_generation_tok_s": 1.5,
        "mean_warm_request_tok_s": 0.75,
        "mean_target_prefill_ms": 4.0,
        "mean_decode_total_ms": 5.0,
        "peak_reserved_bytes": 20,
        "memory_gate_pass": True,
    }


def test_aggregation_fails_memory_gate_if_any_row_fails() -> None:
    assert not _summarize("baseline", [_row(speed=2.0, peak=10, gate=False)])["memory_gate_pass"]


def test_runner_writes_rows_summary_and_closes_engine(tmp_path, monkeypatch) -> None:
    inputs = tmp_path / "inputs.jsonl"
    write_jsonl(inputs, [{"id": "p1", "prompt": "prompt", "max_new_tokens": 8}])

    class Config:
        def get(self, dotted, default=None):
            return {"benchmark.repetitions": 1, "benchmark.warmup_requests": 0}.get(dotted, default)

        def require(self, dotted):
            assert dotted == "runtime.max_new_tokens"
            return 8

        def path_for(self, dotted):
            return {
                "benchmark.output_jsonl": tmp_path / "raw.jsonl",
                "benchmark.summary_json": tmp_path / "summary.json",
            }[dotted]

    class Result:
        def to_dict(self):
            return _row(speed=4.0, peak=20)

    class Engine:
        instances = []

        def __init__(self, *args, **kwargs):
            self.closed = False
            self.instances.append(self)

        def generate(self, *args, **kwargs):
            return Result()

        def close(self):
            self.closed = True

    monkeypatch.setattr(runner, "RuntimeEngine", Engine)

    summary = run_benchmark(Config(), input_path=inputs, conditions=["baseline"])

    assert summary["rows"] == 1
    assert summary["conditions"][0]["mean_decode_tok_s"] == 4.0
    assert len((tmp_path / "raw.jsonl").read_text().splitlines()) == 1
    assert json.loads((tmp_path / "summary.json").read_text())["rows"] == 1
    assert Engine.instances[0].closed
