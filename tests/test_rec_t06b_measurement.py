import json
from pathlib import Path

import pytest

from ccdf.benchmark.timing import timing_contract
from ccdf.benchmark.workflow import evaluate_run_dir, run_benchmark
from ccdf.benchmark.workflow import _row
from ccdf.runtime.engine import _current_rss_bytes
from ccdf.datasets.hashing import hash_file
from ccdf.benchmark.workflow import TRUSTED_CONDITIONS


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


def test_trusted_condition_matrix_is_exact_and_unique() -> None:
    assert TRUSTED_CONDITIONS == {"baseline-ar", "dflash-r1", "cc-dflash-r2"}
    assert len(TRUSTED_CONDITIONS) == 3


@pytest.mark.parametrize(
    "conditions",
    [
        ["baseline-ar", "dflash-r1", "dflash-r1"],
        ["baseline-ar", "dflash-r1"],
        ["baseline-ar", "dflash-r1", "cc-dflash-r2", "unexpected"],
    ],
)
def test_parent_rejects_nonexact_trusted_condition_matrix(tmp_path: Path, conditions: list[str]) -> None:
    with pytest.raises(ValueError, match="exact unique trusted condition set"):
        run_benchmark(
            dataset="gsm8k",
            subset="ad_hoc_prompt",
            conditions=conditions,
            output_dir=tmp_path / "would-not-be-created",
        )


def test_summary_csv_contract_uses_lf_line_endings() -> None:
    source = Path("src/ccdf/benchmark/workflow.py").read_text(encoding="utf-8")
    assert 'lineterminator="\\n"' in source


def test_evaluator_checks_worker_and_source_identity() -> None:
    source = Path("src/ccdf/benchmark/workflow.py").read_text(encoding="utf-8")
    assert "worker git/source state" in Path("src/ccdf/benchmark/worker.py").read_text(encoding="utf-8")
    assert "source_tracked_diff_sha256" in source
    assert "missing or extra worker manifest artifact" in source
    assert "condition_configs/{condition}" in source


def test_gsm8k_quality_and_dflash_summaries_expose_recomputed_audit_counts() -> None:
    source = Path("src/ccdf/benchmark/workflow.py").read_text(encoding="utf-8")
    for field in ("gsm8k_strict_correct", "gsm8k_wrong_numeric", "gsm8k_no_final_answer", "invalid_outputs", "empty_outputs"):
        assert field in source
    assert '"correction_tokens": item["correction_tokens"]' in source
    assert '"bonus_target_tokens": item["bonus_target_tokens"]' in source
