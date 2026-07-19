import copy
import json
from pathlib import Path

import pytest

from ccdf.benchmark.four_condition.audit import (
    _pair_parity,
    _recompute_row,
    duplicate_keys,
    summarize_errors,
)
from ccdf.benchmark.four_condition.manifest import (
    build_run_manifest,
    expected_key,
    validate_manifest,
)
from ccdf.benchmark.four_condition.runner import (
    CONDITIONS,
    _append_checkpoint,
    prepare_mock_samples,
    run_condition,
    validate_compression_cache,
    write_jsonl,
)
from ccdf.benchmark.four_condition.schema import REQUIRED_FIELDS, SCHEMA, validate_record
from ccdf.config import load_config


def _valid_c1_record() -> dict:
    record = dict.fromkeys(REQUIRED_FIELDS)
    record.update(
        {
            "schema": SCHEMA,
            "condition_id": "C1",
            "runtime_condition": "baseline",
            "phase": "measured",
            "is_warmup": False,
            "status": "success",
            "failure_stage": None,
            "failure_type": None,
            "failure_message": None,
            "original_prompt_text": "Original prompt",
            "compressed_prompt_text": "Compressed prompt",
            "input_prompt_text": "Original prompt",
            "input_prompt_sha256": "unit-hash",
            "generated_token_ids": [1],
            "generated_token_sources": ["autoregressive"],
            "generation_warm_e2e_time_ms": 10.0,
            "pipeline_warm_e2e_time_ms": 10.0,
            "target_prefill_time_ms": 1.0,
            "decode_time_ms": 8.0,
            "generation_time_ms": 9.0,
            "decode_tok_s": 100.0,
            "generation_e2e_tok_s": 100.0,
            "pipeline_e2e_tok_s": 100.0,
            "condition_process_peak_measured": False,
        }
    )
    return record


def test_condition_contract_has_exactly_c1_through_c4() -> None:
    assert list(CONDITIONS) == ["C1", "C2", "C3", "C4"]
    assert [condition.prompt_kind for condition in CONDITIONS.values()] == [
        "original",
        "original",
        "compressed",
        "compressed",
    ]


def test_mock_samples_preserve_canonical_order_and_ids() -> None:
    samples = prepare_mock_samples(load_config("config.yml"))

    assert [sample["sample_id"] for sample in samples] == [f"mock-{index:02d}" for index in range(1, 11)]
    assert [sample["prompt"] for sample in samples] == load_config("config.yml").require(
        "benchmark.prompts"
    )


def test_unified_schema_rejects_missing_and_misassigned_fields() -> None:
    record = _valid_c1_record()
    validate_record(record)

    missing = dict(record)
    missing.pop("seed")
    with pytest.raises(ValueError, match="schema mismatch"):
        validate_record(missing)

    record["draft_calls"] = 1
    with pytest.raises(ValueError, match="AR record has non-null DFlash fields"):
        validate_record(record)


def test_pair_parity_reports_first_mismatch() -> None:
    left = [
        {
            "sample_id": "s1",
            "repetition": 0,
            "generated_token_ids": [10, 20, 30],
            "generated_token_sources": ["autoregressive"] * 3,
            "status": "success",
            "dataset": "canonical_mock",
            "decoded_output": "Final answer: 1",
            "parsed_answer": None,
            "quality_score": 1.0,
            "input_prompt_sha256": "same",
            "target_user_original_tokens": 5,
            "target_user_compressed_tokens": 3,
            "target_full_original_tokens": 12,
            "target_full_compressed_tokens": 10,
        }
    ]
    right = [{**left[0], "generated_token_ids": [10, 21, 30]}]
    right[0]["generated_token_sources"] = ["target_prefill", "correction", "bonus"]

    result = _pair_parity(left, right)[0]

    assert not result["generated_token_parity"]
    assert result["first_mismatch_index"] == 1
    assert result["left_mismatch_token_id"] == 20
    assert result["right_mismatch_token_id"] == 21
    assert result["right_row_type"] == "correction"
    assert result["task_answer_or_quality_preserved"]


def _manifest(*, repetitions: int = 2, warmups: int = 1) -> tuple[dict, list[dict]]:
    config = load_config("config.yml")
    samples = prepare_mock_samples(config)[:2]
    return (
        build_run_manifest(
            config,
            samples,
            run_id="unit-run",
            repetitions=repetitions,
            warmups=warmups,
            max_new_tokens=16,
            requested_keep_rate=0.5,
            workload_name="unit-fixture",
        ),
        samples,
    )


def _cache_rows(manifest: dict, samples: list[dict]) -> list[dict]:
    return [
        {
            "sample_id": sample["sample_id"],
            "original_prompt_sha256": entry["prompt_sha256"],
            "compressed_prompt_sha256": f"compressed-{sample['sample_id']}",
            "requested_keep_rate": manifest["requested_keep_rate"],
            "compression_run_id": "compression-unit",
            "status": "success",
        }
        for sample, entry in zip(samples, manifest["workload"]["samples"], strict=True)
    ]


def test_manifest_drives_multiple_repetition_counts() -> None:
    manifest, samples = _manifest(repetitions=3, warmups=2)

    assert manifest["expected_counts"] == {
        "compression_rows": len(samples),
        "per_condition_warmup_rows": 2,
        "per_condition_measured_rows": 6,
        "raw_rows_total": 32,
    }
    assert len({expected_key(row) for row in manifest["expected_records"]}) == 32


def test_manifest_hash_rejects_tampering() -> None:
    manifest, _ = _manifest()
    tampered = copy.deepcopy(manifest)
    tampered["repetitions"] = 99

    with pytest.raises(ValueError, match="hash mismatch"):
        validate_manifest(tampered)


def test_duplicate_raw_composite_keys_are_reported_exactly() -> None:
    row = {
        "condition_id": "C1", "sample_id": "s1", "phase": "measured",
        "repetition": 0, "request_index": 1,
    }

    assert duplicate_keys([row, dict(row)]) == [("C1", "s1", "measured", 0, 1)]


def test_pair_parity_rejects_duplicate_keys_before_indexing() -> None:
    row = {
        "sample_id": "s1", "repetition": 0, "status": "success",
        "generated_token_ids": [1], "input_prompt_sha256": "h",
        "target_user_original_tokens": 2, "target_user_compressed_tokens": 1,
        "target_full_original_tokens": 4, "target_full_compressed_tokens": 3,
    }

    with pytest.raises(ValueError, match="duplicate parity keys"):
        _pair_parity([row, dict(row)], [row])


def test_duplicate_compression_rows_fail_before_cache_indexing() -> None:
    manifest, samples = _manifest()
    rows = _cache_rows(manifest, samples)
    rows.append(dict(rows[0]))

    with pytest.raises(ValueError, match="duplicate compression cache"):
        validate_compression_cache(samples, rows, manifest)


def test_compression_cache_order_is_owned_by_manifest() -> None:
    manifest, samples = _manifest()

    with pytest.raises(ValueError, match="cache sample order"):
        validate_compression_cache(samples, list(reversed(_cache_rows(manifest, samples))), manifest)


def test_compression_cache_prompt_hash_is_checked() -> None:
    manifest, samples = _manifest()
    rows = _cache_rows(manifest, samples)
    rows[0]["original_prompt_sha256"] = "wrong"

    with pytest.raises(ValueError, match="original prompt hash mismatch"):
        validate_compression_cache(samples, rows, manifest)


def test_failure_row_requires_explicit_stage_type_and_message() -> None:
    record = dict.fromkeys(REQUIRED_FIELDS)
    record.update(
        {
            "schema": SCHEMA, "phase": "measured", "is_warmup": False,
            "status": "failed", "failure_stage": "generation",
            "failure_type": "RuntimeError", "failure_message": "injected",
        }
    )
    validate_record(record)
    record["failure_message"] = None
    with pytest.raises(ValueError, match="must identify"):
        validate_record(record)


def test_compressed_pipeline_latency_includes_compressor_latency() -> None:
    record = _valid_c1_record()
    record.update(
        {
            "condition_id": "C3", "prompt_kind": "compressed",
            "compressor_latency_ms": 4.0, "generation_warm_e2e_time_ms": 10.0,
            "pipeline_warm_e2e_time_ms": 14.0,
            "safeguard_validation": {"passed": True},
            "compression_applied": True, "compression_status": "COMPRESSED",
        }
    )
    validate_record(record)
    record["pipeline_warm_e2e_time_ms"] = 10.0
    with pytest.raises(ValueError, match="pipeline E2E arithmetic"):
        validate_record(record)


def test_independent_recompute_catches_throughput_drift() -> None:
    record = _valid_c1_record()
    record.update(
        {
            "generated_token_count": 1,
            "compressor_original_tokens": 10, "compressor_compressed_tokens": 8,
            "compressor_token_keep_rate": 0.8,
            "target_user_original_tokens": 10, "target_user_compressed_tokens": 8,
            "target_user_token_reduction": 2, "target_user_keep_rate": 0.8,
            "target_user_compression_ratio": 1.25,
            "target_full_original_tokens": 20, "target_full_compressed_tokens": 18,
            "target_full_token_reduction": 2, "target_full_keep_rate": 0.9,
            "target_full_compression_ratio": 20 / 18,
            "generation_e2e_tok_s": 999.0,
        }
    )

    assert _recompute_row(record) == ["generation_e2e_tok_s"]


def test_expected_key_set_detects_missing_and_extra_repetition() -> None:
    manifest, _ = _manifest(repetitions=2)
    expected = {expected_key(row) for row in manifest["expected_records"]}
    missing = next(iter(expected))
    unexpected = ("C1", "mock-01", "measured", 7, 99)
    actual = (expected - {missing}) | {unexpected}

    assert expected - actual == {missing}
    assert actual - expected == {unexpected}


def test_runtime_error_count_is_recomputed_from_raw_rows() -> None:
    base = {
        "condition_id": "C1", "sample_id": "s1", "phase": "measured",
        "repetition": 0, "request_index": 1,
    }
    rows = [
        {**base, "status": "success", "failure_stage": None, "failure_type": None, "failure_message": None},
        {
            **base, "sample_id": "s2", "request_index": 2, "status": "failed",
            "failure_stage": "generation", "failure_type": "RuntimeError",
            "failure_message": "injected",
        },
    ]

    summary = summarize_errors(rows)

    assert summary["runtime_error_count"] == 1
    assert summary["by_stage"] == {"generation": 1}
    assert summary["by_type"] == {"RuntimeError": 1}


def test_resume_skips_checksum_verified_completed_condition(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest, samples = _manifest(repetitions=1, warmups=1)
    cache = _cache_rows(manifest, samples)
    output = tmp_path / "C1.jsonl"
    rows = []
    for expected in [row for row in manifest["expected_records"] if row["condition_id"] == "C1"]:
        sample_entry = next(
            row for row in manifest["workload"]["samples"]
            if row["sample_id"] == expected["sample_id"]
        )
        cache_entry = next(row for row in cache if row["sample_id"] == expected["sample_id"])
        record = dict.fromkeys(REQUIRED_FIELDS)
        record.update(
            {
                "schema": SCHEMA,
                "manifest_sha256": manifest["manifest_sha256"],
                "condition_id": "C1",
                "sample_id": expected["sample_id"],
                "phase": expected["phase"],
                "repetition": expected["repetition"],
                "request_index": expected["request_index"],
                "is_warmup": expected["phase"] == "warmup",
                "original_prompt_sha256": sample_entry["prompt_sha256"],
                "compressed_prompt_sha256": cache_entry["compressed_prompt_sha256"],
                "status": "failed",
                "failure_stage": "generation",
                "failure_type": "RuntimeError",
                "failure_message": "recorded failure",
            }
        )
        rows.append(record)
    write_jsonl(output, rows)
    for row in rows:
        _append_checkpoint(output.with_suffix(".jsonl.checksums.jsonl"), row)

    class ForbiddenEngine:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("verified completed rows must not reload the model")

    monkeypatch.setattr("ccdf.benchmark.four_condition.runner.RuntimeEngine", ForbiddenEngine)

    resumed = run_condition(
        load_config("config.yml"),
        manifest=manifest,
        condition_id="C1",
        samples=samples,
        compression_rows=cache,
        output_path=output,
        resume=True,
    )

    assert resumed == rows
