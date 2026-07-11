from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from ccdf.benchmark.aggregation import aggregate_run_artifact
from ccdf.benchmark.execution import synthetic_row
from ccdf.artifacts.writer import write_jsonl_atomic
from ccdf.config import resolve_config
from ccdf.config.loader import load_config


def test_valid_config_and_stable_resolution() -> None:
    one = resolve_config(dataset="gsm8k", condition_id="baseline-ar")
    two = resolve_config(dataset="gsm8k", condition_id="baseline-ar")
    assert one.data == two.data
    assert one.sha256 == two.sha256


def test_missing_section_and_bad_lock_fail(tmp_path: Path) -> None:
    data = load_config()
    missing = deepcopy(data)
    missing.pop("runtime")
    path = tmp_path / "missing.yml"
    path.write_text(json.dumps(missing), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required"):
        load_config(path)
    bad = deepcopy(data)
    bad["models"]["target"]["revision"] = "wrong"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="revision"):
        load_config(path)


def test_manifest_and_immutable_overrides_fail() -> None:
    with pytest.raises(ValueError, match="immutable override"):
        resolve_config(dataset="gsm8k", overrides={"tokenizer": "other"})
    with pytest.raises(ValueError, match="max_new_tokens override"):
        resolve_config(dataset="gsm8k", overrides={"max_new_tokens": 8})


def test_smoke_override_is_noncanonical_and_aggregation_rejects_it(tmp_path: Path) -> None:
    smoke = resolve_config(dataset="gsm8k", execution_mode="smoke", overrides={"max_new_tokens": 8})
    assert not smoke.canonical
    row = synthetic_row(run_id="test", dataset="gsm8k", fixture_id="f", fixture_content_hash="h", reference_answer="1", condition_id="baseline-ar", dataset_manifest_hash="manifest")
    row["canonical"] = False
    path = tmp_path / "rows.jsonl"
    write_jsonl_atomic(path, [row])
    with pytest.raises(ValueError, match="noncanonical"):
        aggregate_run_artifact(path, dataset_manifest_hash="manifest", resolved_config_hash=row["resolved_config_hash"])


def test_changed_config_changes_resolved_hash() -> None:
    baseline = resolve_config(dataset="gsm8k")
    smoke = resolve_config(dataset="gsm8k", execution_mode="smoke", overrides={"max_new_tokens": 8})
    assert baseline.sha256 != smoke.sha256
