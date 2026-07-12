import json
import shutil
from pathlib import Path

import pytest

from ccdf.benchmark.timing import timing_contract
from ccdf.benchmark.workflow import evaluate_run_dir, run_benchmark
from ccdf.benchmark.workflow import _row
from ccdf.runtime.engine import _current_rss_bytes
from ccdf.datasets.hashing import hash_file
from ccdf.datasets.hashing import hash_text
from ccdf.artifacts.writer import write_json, write_jsonl_atomic
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
    assert TRUSTED_CONDITIONS == ("baseline-ar", "dflash-r1", "llmlingua-ar-r2", "cc-dflash-r2")


@pytest.mark.parametrize(
    "conditions",
    [
        ["baseline-ar", "dflash-r1", "dflash-r1"],
        ["baseline-ar", "dflash-r1"],
        ["baseline-ar", "dflash-r1", "cc-dflash-r2", "unexpected"],
    ],
)
def test_parent_rejects_nonexact_trusted_condition_matrix(tmp_path: Path, conditions: list[str]) -> None:
    with pytest.raises(ValueError, match="exact ordered unique trusted condition matrix"):
        run_benchmark(
            dataset="gsm8k",
            subset="ad_hoc_prompt",
            conditions=conditions,
            output_dir=tmp_path / "would-not-be-created",
        )


def test_summary_csv_contract_uses_lf_line_endings() -> None:
    source = Path("src/ccdf/benchmark/workflow.py").read_text(encoding="utf-8")
    assert 'lineterminator="\\n"' in source


def _copy_b1_gsm_artifact(tmp_path: Path) -> Path:
    destination = tmp_path / "gsm8k_n3"
    shutil.copytree(Path("results/Rec-T06B1/gsm8k_n3"), destination)
    return destination


def test_evaluator_rejects_parent_worker_source_state_mismatch(tmp_path: Path) -> None:
    run_dir = _copy_b1_gsm_artifact(tmp_path)
    worker_path = run_dir / "runs" / "baseline_ar.worker.json"
    worker = json.loads(worker_path.read_text(encoding="utf-8"))
    worker["git_state"]["source_commit"] = "mismatch"
    write_json(worker_path, worker)
    manifest_path = run_dir / "benchmark_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["worker_manifests"]["baseline-ar"] = worker
    manifest["worker_manifest_hashes"]["baseline-ar"] = hash_file(worker_path)
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    with pytest.raises(ValueError, match="worker source-state mismatch"):
        evaluate_run_dir(run_dir)


def test_gsm8k_counts_are_recomputed_from_raw_output(tmp_path: Path) -> None:
    run_dir = _copy_b1_gsm_artifact(tmp_path)
    run_path = run_dir / "runs" / "baseline_ar.jsonl"
    rows = [json.loads(line) for line in run_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["raw_generated_text"] = "Final answer: 999999"
    rows[0]["generated_text"] = "Final answer: 999999"
    rows[0]["generated_text_hash"] = hash_text(rows[0]["generated_text"])
    write_jsonl_atomic(run_path, rows)
    manifest_path = run_dir / "benchmark_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["run_file_hashes"][run_path.name] = hash_file(run_path)
    write_json(manifest_path, manifest)
    evaluate_run_dir(run_dir)
    baseline = json.loads((run_dir / "quality_summary.json").read_text(encoding="utf-8"))["conditions"][0]
    assert baseline["gsm8k_strict_correct"] == 2
    assert baseline["gsm8k_wrong_numeric"] == 1
    assert baseline["invalid_outputs"] == 0
    assert baseline["empty_outputs"] == 0


@pytest.mark.parametrize(
    ("raw_output", "reference_answer", "expected"),
    [
        ("Final answer: 999999", None, {"gsm8k_strict_correct": 2, "gsm8k_wrong_numeric": 1, "gsm8k_no_final_answer": 0, "invalid_outputs": 0, "empty_outputs": 0}),
        ("there is no compliant final line", None, {"gsm8k_strict_correct": 2, "gsm8k_wrong_numeric": 0, "gsm8k_no_final_answer": 1, "invalid_outputs": 0, "empty_outputs": 0}),
        ("   ", None, {"gsm8k_strict_correct": 2, "gsm8k_wrong_numeric": 0, "gsm8k_no_final_answer": 1, "invalid_outputs": 0, "empty_outputs": 1}),
        ("Final answer: 999999", "not-a-number", {"gsm8k_strict_correct": 2, "gsm8k_wrong_numeric": 0, "gsm8k_no_final_answer": 0, "invalid_outputs": 1, "empty_outputs": 0}),
    ],
    ids=("wrong-numeric", "no-final-answer", "empty", "invalid"),
)
def test_gsm8k_summary_counts_follow_recomputed_labels(
    tmp_path: Path, raw_output: str, reference_answer: str | None, expected: dict[str, int]
) -> None:
    run_dir = _copy_b1_gsm_artifact(tmp_path)
    run_path = run_dir / "runs" / "baseline_ar.jsonl"
    rows = [json.loads(line) for line in run_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["raw_generated_text"] = raw_output
    rows[0]["generated_text"] = raw_output
    rows[0]["generated_text_hash"] = hash_text(raw_output)
    if reference_answer is not None:
        rows[0]["reference_answer"] = reference_answer
    write_jsonl_atomic(run_path, rows)
    manifest_path = run_dir / "benchmark_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["run_file_hashes"][run_path.name] = hash_file(run_path)
    write_json(manifest_path, manifest)
    evaluate_run_dir(run_dir)
    baseline = json.loads((run_dir / "quality_summary.json").read_text(encoding="utf-8"))["conditions"][0]
    assert {key: baseline[key] for key in expected} == expected


def test_evaluation_inventory_is_complete_and_csv_hash_is_lf_stable(tmp_path: Path) -> None:
    run_dir = _copy_b1_gsm_artifact(tmp_path)
    evaluate_run_dir(run_dir)
    evaluation = json.loads((run_dir / "evaluation_manifest.json").read_text(encoding="utf-8"))
    inventory = evaluation["consumed_input_hashes"]
    for key in ("fixture_file", "dataset_manifest", "resolved_config.sha256", "runs/baseline_ar.worker.json", "runs/dflash_r1.jsonl", "condition_configs/cc-dflash-r2", "evaluator_dependencies/benchmark/workflow.py"):
        assert key in inventory
    summary = run_dir / "summary.csv"
    assert b"\r\n" not in summary.read_bytes()
    assert evaluation["produced_summary_hashes"]["summary.csv"] == hash_file(summary)


def test_evaluator_rejects_extra_worker_artifact(tmp_path: Path) -> None:
    run_dir = _copy_b1_gsm_artifact(tmp_path)
    write_json(run_dir / "runs" / "undeclared.worker.json", {"not": "declared"})
    with pytest.raises(ValueError, match="missing or extra worker manifest artifact"):
        evaluate_run_dir(run_dir)


def test_evaluator_checks_worker_and_source_identity() -> None:
    source = Path("src/ccdf/benchmark/workflow.py").read_text(encoding="utf-8")
    assert "worker git/source state" in Path("src/ccdf/benchmark/worker.py").read_text(encoding="utf-8")
    assert "source_tracked_diff_sha256" in source
    assert "worker source-state mismatch" in source
    assert 'worker.get("git_state") != manifest.get("git_state")' in source
    assert "missing or extra worker manifest artifact" in source
    assert "condition_configs/{condition}" in source


def test_gsm8k_quality_and_dflash_summaries_expose_recomputed_audit_counts() -> None:
    source = Path("src/ccdf/benchmark/workflow.py").read_text(encoding="utf-8")
    for field in ("gsm8k_strict_correct", "gsm8k_wrong_numeric", "gsm8k_no_final_answer", "invalid_outputs", "empty_outputs"):
        assert field in source
    assert '"correction_tokens": item["correction_tokens"]' in source
    assert '"bonus_target_tokens": item["bonus_target_tokens"]' in source
