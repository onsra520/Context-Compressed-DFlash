"""Build read-only diagnostics from sealed mock10 and dataset-smoke FAIL artifacts."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/artifacts/windows-environment-benchmark-rerun/diagnostics"


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _first_difference(left: list[int], right: list[int]) -> dict[str, Any]:
    for index, (left_id, right_id) in enumerate(zip(left, right)):
        if left_id != right_id:
            return {"token_index": index, "left_token_id": left_id, "right_token_id": right_id}
    index = min(len(left), len(right))
    return {
        "token_index": index if len(left) != len(right) else None,
        "left_token_id": left[index] if index < len(left) else None,
        "right_token_id": right[index] if index < len(right) else None,
    }


def mock10() -> dict[str, Any]:
    root = ROOT / "docs/artifacts/rec3-four-condition-mock10"
    parity = json.loads((root / "pair_parity.json").read_text(encoding="utf-8"))
    raw = json.loads((root / "raw_runs.json").read_text(encoding="utf-8"))
    prompt_index = {row["prompt_id"]: row for row in raw["prompts"]}
    failures = []
    pair_definitions = {
        "original_baseline_ar_vs_dflash_r1": ("baseline-ar", "dflash-r1"),
        "compressed_llmlingua_ar_r2_vs_cc_dflash_r2": ("llmlingua-ar-r2", "cc-dflash-r2"),
    }
    for pair in parity:
        if pair["pass"]:
            continue
        left_name, right_name = pair_definitions[pair["pair"]]
        prompt = prompt_index[pair["prompt_id"]]
        left = prompt["runs"][left_name]["result"]
        right = prompt["runs"][right_name]["result"]
        failures.append({
            **pair,
            "left_condition": left_name,
            "right_condition": right_name,
            "left_text": left["text"],
            "right_text": right["text"],
            "left_generated_token_ids": left["generated_token_ids"],
            "right_generated_token_ids": right["generated_token_ids"],
            "first_difference": _first_difference(
                left["generated_token_ids"], right["generated_token_ids"]
            ),
        })
    return {
        "diagnostic_version": "ccdf.windows.mock10-parity-fail.v1",
        "benchmark_was_not_rerun": True,
        "config_sha256": raw["source_config_sha256"],
        "status": "FAIL",
        "failure_gate": "pair_generated_token_parity",
        "pair_count": len(parity),
        "pass_count": sum(row["pass"] for row in parity),
        "failure_count": len(failures),
        "failures": failures,
    }


def dataset_smoke() -> dict[str, Any]:
    root = ROOT / "docs/artifacts/dataset-protocol-evaluator-smoke-n10"
    parity = json.loads((root / "pair_parity.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (root / "per_sample_results.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    index = {(row["fixture_id"], row["condition"]): row for row in rows}
    failures = []
    for pair in parity["records"]:
        if pair["generated_token_ids_match"]:
            continue
        left_row = index[(pair["fixture_id"], pair["left"])]
        right_row = index[(pair["fixture_id"], pair["right"])]
        left = left_row["run"]["result"]
        right = right_row["run"]["result"]
        failures.append({
            **pair,
            "left_output_tokens": left["output_tokens"],
            "right_output_tokens": right["output_tokens"],
            "left_stop_reason": left["stop_reason"],
            "right_stop_reason": right["stop_reason"],
            "left_text": left["text"],
            "right_text": right["text"],
            "left_generated_token_ids": left["generated_token_ids"],
            "right_generated_token_ids": right["generated_token_ids"],
            "first_difference": _first_difference(
                left["generated_token_ids"], right["generated_token_ids"]
            ),
        })
    breakdown = Counter((row["dataset"], row["pair"]) for row in parity["records"])
    passes = Counter(
        (row["dataset"], row["pair"])
        for row in parity["records"] if row["generated_token_ids_match"]
    )
    return {
        "diagnostic_version": "ccdf.windows.dataset-smoke-parity-fail.v1",
        "benchmark_was_not_rerun": True,
        "status": "FAIL",
        "failure_gate": "pair_generated_token_parity_rate",
        "input_parity": f"{parity['input_token_parity_count']}/{parity['pairs']}",
        "generated_parity": f"{parity['generated_token_parity_count']}/{parity['pairs']}",
        "breakdown": [
            {
                "dataset": dataset,
                "pair": pair_name,
                "pass": passes[(dataset, pair_name)],
                "total": total,
                "fail": total - passes[(dataset, pair_name)],
            }
            for (dataset, pair_name), total in sorted(breakdown.items())
        ],
        "failure_count": len(failures),
        "failures": failures,
    }


def main() -> None:
    _write(OUTPUT / "mock10-parity-failure.json", mock10())
    _write(OUTPUT / "dataset-smoke-parity-failure.json", dataset_smoke())
    print(json.dumps({"mock10": "FAIL", "dataset_smoke": "FAIL"}, sort_keys=True))


if __name__ == "__main__":
    main()
