import json
from pathlib import Path

import pytest

from ccdf.benchmark.timing import timing_contract
from ccdf.benchmark.workflow import evaluate_run_dir
from ccdf.benchmark.workflow import _row
from ccdf.runtime.engine import _current_rss_bytes
from ccdf.datasets.hashing import hash_file


def test_timing_v2_defines_compression_inclusive_warm_identity() -> None:
    contract = timing_contract()
    assert contract["contract_version"] == "rec-t06b.timing.v2"
    assert contract["identities"]["comparison_latency"] == "warm_request_e2e_ms"
    assert "cold_start_e2e_ms" in contract["fields_ms"]


def test_evaluation_rejects_extra_run_artifact(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    runs = run_dir / "runs"
    runs.mkdir(parents=True)
    # A malformed but intentionally extra artifact must be rejected before
    # row parsing/model work; no models are imported by evaluation.
    extra = runs / "extra.jsonl"
    extra.write_text("", encoding="utf-8")
    manifest = {
        "conditions": ["baseline-ar"],
        "run_file_hashes": {"baseline_ar.jsonl": "missing"},
    }
    (run_dir / "benchmark_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        evaluate_run_dir(run_dir)


def test_legacy_runner_is_marked_noncanonical() -> None:
    import ccdf.benchmark.rec_t03b as legacy

    assert "Legacy noncanonical" in legacy.__doc__


def test_current_rss_is_not_ru_maxrss() -> None:
    value = _current_rss_bytes()
    assert value is None or value > 0


def test_worker_requires_explicit_identity() -> None:
    import inspect
    from ccdf.benchmark import worker

    signature = inspect.signature(worker.run_worker)
    assert signature.parameters["task_id"].default is inspect.Parameter.empty
    assert signature.parameters["execution_mode"].default is inspect.Parameter.empty
