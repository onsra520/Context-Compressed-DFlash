from __future__ import annotations

from pathlib import Path

import pytest

from ccdf.artifacts.writer import assert_artifact_matches, read_jsonl, write_jsonl_atomic
from ccdf.benchmark.aggregation import aggregate_run_artifact
from ccdf.benchmark.execution import synthetic_row
from ccdf.benchmark.process_isolation import audit_process_isolation
from ccdf.benchmark.runner import run_synthetic_benchmark
from ccdf.benchmark.schemas import validate_row
from ccdf.evaluation import gsm8k, qmsum
from ccdf.metrics.dflash import aggregate_tau, validate_dflash_invariants
from ccdf.paths import find_worktree_root


def _row(mode: str = "benchmark") -> dict:
    return synthetic_row(
        run_id="test",
        dataset="gsm8k",
        fixture_id="gsm8k_test_000000_deadbeef",
        fixture_content_hash="deadbeef",
        reference_answer="18",
        condition_id="dflash-r1",
        dataset_manifest_hash="manifest-hash",
        measurement_mode=mode,
    )


def test_schema_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    row = _row()
    write_jsonl_atomic(path, [row])
    loaded = read_jsonl(path)
    assert loaded == [row]


def test_invalid_row_rejected() -> None:
    row = _row()
    row.pop("generated_text")
    with pytest.raises(ValueError, match="missing required"):
        validate_row(row)


def test_field_scope_rejects_tokenizer_mixing() -> None:
    row = _row()
    row["quality"]["tokenizer_source"] = "other"
    with pytest.raises(ValueError, match="tokenizer scope"):
        validate_row(row)


def test_benchmark_and_profiling_modes_are_separate() -> None:
    profiling = _row("profiling")
    validate_row(profiling)
    benchmark = _row("benchmark")
    benchmark["draft_proposal_ms"] = 1.0
    with pytest.raises(ValueError, match="profiling fields"):
        validate_row(benchmark)


def test_dflash_invariants_and_tau() -> None:
    row = _row()
    validate_dflash_invariants(row)
    assert aggregate_tau([row])["global_weighted_tau"] == 4.0
    row["accepted_draft_tokens"] += 1
    with pytest.raises(ValueError, match="accepted_draft_tokens"):
        validate_dflash_invariants(row)


def test_process_isolation() -> None:
    audit = audit_process_isolation(["baseline-ar", "dflash-r1"])
    assert audit["pass"] is True
    assert len({record["pid"] for record in audit["records"]}) == 2


def test_evaluators_are_deterministic() -> None:
    assert gsm8k.evaluate("Final answer: 1,234", "1234") == gsm8k.evaluate(
        "Final answer: 1,234", "1234"
    )
    assert qmsum.evaluate("alpha beta", "alpha gamma") == qmsum.evaluate(
        "alpha beta", "alpha gamma"
    )


def test_summary_rejects_stale_artifact(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    row = _row()
    write_jsonl_atomic(path, [row])
    assert_artifact_matches(
        path,
        dataset_manifest_hash=row["dataset_manifest_hash"],
        resolved_config_hash=row["resolved_config_hash"],
    )
    with pytest.raises(ValueError, match="dataset_manifest_hash"):
        assert_artifact_matches(
            path,
            dataset_manifest_hash="stale",
            resolved_config_hash=row["resolved_config_hash"],
        )


@pytest.mark.skipif(
    not (find_worktree_root() / "data/eval/gsm8k/gsm8k_n10.jsonl").is_file(),
    reason="synthetic runner samples frozen fixtures",
)
def test_synthetic_runner_outputs_summary(tmp_path: Path) -> None:
    summary = run_synthetic_benchmark(tmp_path)
    assert summary["process_isolation"]["pass"] is True
    rows = read_jsonl(tmp_path / "synthetic_rows.jsonl")
    assert len(rows) == 4
    # Aggregation reads a single manifest/config cohort and rejects mixed stale rows.
    gsm_rows = [row for row in rows if row["dataset"] == "gsm8k"]
    aggregate = aggregate_run_artifact(
        tmp_path / "gsm8k_synthetic_rows.jsonl",
        dataset_manifest_hash=gsm_rows[0]["dataset_manifest_hash"],
        resolved_config_hash={row["resolved_config_hash"] for row in gsm_rows},
    )
    assert aggregate["row_count"] == 2



def test_smoke_mode_is_valid_nonprofiling_mode() -> None:
    smoke = _row("smoke")
    validate_row(smoke)

    smoke["draft_proposal_ms"] = 1.0
    with pytest.raises(ValueError, match="profiling fields"):
        validate_row(smoke)
