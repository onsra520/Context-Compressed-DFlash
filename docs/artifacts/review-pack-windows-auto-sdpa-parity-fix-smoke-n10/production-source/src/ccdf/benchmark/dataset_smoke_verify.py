"""Independent structural and hash verification for dataset-smoke artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from ..config import Config, load_config


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_dataset_smoke_artifacts(config: Config) -> dict[str, Any]:
    config.validate(require_model_files=False)
    profile = config.resolve_dataset_smoke_profile()
    settings = profile.settings
    root = Path(str(settings["artifact_directory"])).resolve()
    failures: list[str] = []
    required = (
        "resolved_config.json", "environment.json", "sdpa_evidence.json",
        "cohort_manifest.json", "evaluator_lock.json", "compression_stage.json",
        "qmsum_chunk_maps.jsonl", "prepared_input_manifest.jsonl",
        "qmsum_generation_chunk_maps.jsonl", "condition_worker_attempts.json",
        "per_sample_results.jsonl", "pair_parity.json", "condition_summaries.json",
        "gate_matrix.json", "lifecycle.json", "source_hashes.json", "summary.json",
        "artifact_manifest.json",
    )
    for relative in required:
        if not (root / relative).is_file():
            failures.append(f"missing artifact: {relative}")
    if failures:
        return {"pass": False, "failures": failures, "artifact_root": str(root)}

    artifact_manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    for entry in artifact_manifest.get("files", []):
        path = root / entry["path"]
        if not path.is_file():
            failures.append(f"manifest file missing: {entry['path']}")
        elif _hash(path) != entry["sha256"]:
            failures.append(f"artifact hash mismatch: {entry['path']}")

    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    gates = json.loads((root / "gate_matrix.json").read_text(encoding="utf-8"))
    resolved = json.loads((root / "resolved_config.json").read_text(encoding="utf-8"))
    if summary.get("status") != "PASS" or summary.get("gate_pass") is not True:
        failures.append("summary is not PASS")
    if gates.get("pass") is not True or not all(entry.get("pass") for entry in gates.get("entries", [])):
        failures.append("gate matrix is not fully PASS")
    if resolved.get("source_config_sha256") != profile.source_config_sha256:
        failures.append("resolved config SHA does not match current config")
    if summary.get("config_sha256") != profile.source_config_sha256:
        failures.append("summary config SHA does not match current config")

    source_hashes = json.loads((root / "source_hashes.json").read_text(encoding="utf-8"))
    for relative, expected in source_hashes.items():
        path = config.root / relative
        if not path.is_file() or _hash(path) != expected:
            failures.append(f"source hash mismatch: {relative}")

    evaluator = json.loads((root / "evaluator_lock.json").read_text(encoding="utf-8"))
    evaluator_path = config.root / "src/ccdf/benchmark/evaluators.py"
    if evaluator.get("source_sha256") != _hash(evaluator_path):
        failures.append("evaluator source hash mismatch")
    evaluator_config_hash = hashlib.sha256(
        _canonical(settings["evaluators"]).encode("utf-8")
    ).hexdigest()
    if evaluator.get("config_sha256") != evaluator_config_hash or evaluator.get("pass") is not True:
        failures.append("evaluator config/fixture lock mismatch")

    chunks = _read_jsonl(root / "qmsum_chunk_maps.jsonl")
    expected_rows = int(settings["cohorts"]["expected_rows_per_dataset"])
    if len(chunks) != expected_rows:
        failures.append(f"QMSum chunk-map count is {len(chunks)}, expected {expected_rows}")
    for row in chunks:
        ranges = row.get("chunk_token_ranges", [])
        original = int(row.get("original_context_tokens", -1))
        if not ranges or int(ranges[0].get("source_start_token", -1)) != 0:
            failures.append(f"chunk map does not begin at zero: {row.get('fixture_id')}")
            continue
        cursor = 0
        last_start = -1
        for item in ranges:
            start = int(item["source_start_token"])
            end = int(item["source_end_token_exclusive"])
            if start < last_start or start > cursor or end <= start or end > original:
                failures.append(f"invalid/gapped chunk range: {row.get('fixture_id')}")
                break
            cursor = max(cursor, end)
            last_start = start
            if int(item.get("hidden_truncated_tokens", -1)) != 0:
                failures.append(f"hidden chunk truncation: {row.get('fixture_id')}")
        if cursor != original:
            failures.append(f"chunk coverage ends at {cursor}, expected {original}: {row.get('fixture_id')}")
        if float(row.get("coverage_rate", 0.0)) != 1.0:
            failures.append(f"chunk coverage rate is not 1.0: {row.get('fixture_id')}")
        if int(row.get("dropped_tokens", -1)) != 0 or int(row.get("hidden_truncated_tokens", -1)) != 0:
            failures.append(f"dropped/truncated tokens found: {row.get('fixture_id')}")

    generation_chunks = _read_jsonl(root / "qmsum_generation_chunk_maps.jsonl")
    expected_generation_maps = expected_rows * len(settings["conditions"])
    if len(generation_chunks) != expected_generation_maps:
        failures.append(
            f"QMSum generation chunk-map count is {len(generation_chunks)}, "
            f"expected {expected_generation_maps}"
        )
    for row in generation_chunks:
        ranges = row.get("chunk_map", [])
        fixture_id = row.get("fixture_id")
        if not ranges or int(ranges[0].get("source_start_token", -1)) != 0:
            failures.append(f"generation chunk map does not begin at zero: {fixture_id}")
            continue
        cursor = 0
        for item in ranges:
            start = int(item.get("source_start_token", -1))
            end = int(item.get("source_end_token_exclusive", -1))
            if start > cursor or end <= start:
                failures.append(f"invalid/gapped generation chunk range: {fixture_id}")
                break
            cursor = max(cursor, end)
        if float(row.get("coverage_rate", 0.0)) != 1.0:
            failures.append(f"generation coverage rate is not 1.0: {fixture_id}")
        if int(row.get("hidden_truncated_tokens", -1)) != 0:
            failures.append(f"hidden generation truncation: {fixture_id}")

    worker_attempts = json.loads(
        (root / "condition_worker_attempts.json").read_text(encoding="utf-8")
    )
    max_attempts = int(settings["generation"]["condition_worker_max_attempts"])
    if max_attempts != 1:
        failures.append("clean rerun requires exactly one worker attempt")
    for condition in (str(item["name"]) for item in settings["conditions"]):
        selected = [item for item in worker_attempts if item.get("condition") == condition]
        if not selected or int(selected[-1].get("exit_code", 1)) != 0:
            failures.append(f"condition worker did not complete: {condition}")
        if len(selected) > max_attempts:
            failures.append(f"condition worker exceeded retry limit: {condition}")
        if len(selected) != 1 or int(selected[0].get("retry_count", -1)) != 0:
            failures.append(f"condition worker retry policy violated: {condition}")
        if selected and selected[0].get("resume_enabled") is not False:
            failures.append(f"condition worker resume policy violated: {condition}")
        if selected and selected[0].get("faulthandler_enabled") is not True:
            failures.append(f"condition worker faulthandler missing: {condition}")
        for stream in ("stdout_path", "stderr_path"):
            if selected and not (root / str(selected[0].get(stream, ""))).is_file():
                failures.append(f"condition worker missing {stream}: {condition}")
        if [int(item.get("attempt", -1)) for item in selected] != list(range(1, len(selected) + 1)):
            failures.append(f"condition worker attempts are not sequential: {condition}")

    all_rows: list[dict[str, Any]] = []
    condition_names = [str(item["name"]) for item in settings["conditions"]]
    for dataset in ("gsm8k", "qmsum"):
        for condition in condition_names:
            path = root / "raw_runs" / dataset / f"{condition}.jsonl"
            if not path.is_file():
                failures.append(f"missing raw run file: {path.relative_to(root)}")
                continue
            rows = _read_jsonl(path)
            if len(rows) != expected_rows:
                failures.append(f"raw run count mismatch: {path.relative_to(root)}")
            all_rows.extend(rows)
    if len(all_rows) != int(settings["hard_gates"]["successful_condition_runs"]):
        failures.append(f"total run count mismatch: {len(all_rows)}")
    identities = {(row["dataset"], row["condition"], row["fixture_id"]) for row in all_rows}
    if len(identities) != len(all_rows):
        failures.append("duplicate sample/condition run identities")

    parity = json.loads((root / "pair_parity.json").read_text(encoding="utf-8"))
    index = {(row["fixture_id"], row["condition"]): row for row in all_rows}
    for record in parity.get("records", []):
        left = index.get((record["fixture_id"], record["left"]))
        right = index.get((record["fixture_id"], record["right"]))
        if left is None or right is None or not left.get("success") or not right.get("success"):
            failures.append(f"parity record has missing/failed side: {record['fixture_id']}/{record['pair']}")
            continue
        left_result = left["run"]["result"]
        right_result = right["run"]["result"]
        input_match = (
            left_result["protocol_metrics"]["chat_template_input"]["token_ids"]
            == right_result["protocol_metrics"]["chat_template_input"]["token_ids"]
            and left_result["protocol_metrics"]["chat_template_input"].get("chunk_token_ids")
            == right_result["protocol_metrics"]["chat_template_input"].get("chunk_token_ids")
        )
        output_match = left_result["generated_token_ids"] == right_result["generated_token_ids"]
        if input_match != record.get("input_token_ids_match"):
            failures.append(f"input parity evidence mismatch: {record['fixture_id']}/{record['pair']}")
        if output_match != record.get("generated_token_ids_match"):
            failures.append(f"output parity evidence mismatch: {record['fixture_id']}/{record['pair']}")

    sdpa = json.loads((root / "sdpa_evidence.json").read_text(encoding="utf-8"))
    if sdpa.get("config_sha256") != profile.source_config_sha256:
        failures.append("SDPA evidence config SHA mismatch")
    if sdpa.get("configured", {}).get("sdpa_kernel") != config.require("runtime.sdpa_kernel"):
        failures.append("SDPA configured policy mismatch")
    if sdpa.get("actual_kernel_execution_observed") is not False:
        failures.append("SDPA evidence overclaims observed kernel execution")
    interpretation = str(sdpa.get("interpretation", ""))
    if "not evidence" not in interpretation:
        failures.append("SDPA dispatcher interpretation is missing")

    return {
        "pass": not failures,
        "failures": failures,
        "artifact_root": str(root),
        "artifact_files_verified": len(artifact_manifest.get("files", [])),
        "run_rows_verified": len(all_rows),
        "chunk_maps_verified": len(chunks),
        "generation_chunk_maps_verified": len(generation_chunks),
        "condition_worker_attempts_verified": len(worker_attempts),
        "parity_records_verified": len(parity.get("records", [])),
        "config_sha256": profile.source_config_sha256,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    args = parser.parse_args()
    result = verify_dataset_smoke_artifacts(load_config(args.config))
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
