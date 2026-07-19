"""Build first-divergence evidence from sealed mock10 and dataset raw runs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _first_difference(left: list[int], right: list[int]) -> int | None:
    for index, (left_token, right_token) in enumerate(zip(left, right)):
        if left_token != right_token:
            return index
    return min(len(left), len(right)) if len(left) != len(right) else None


def _block_state(result: dict[str, Any], token_index: int) -> dict[str, Any]:
    chunks = result.get("generated_token_id_chunks")
    subrequests = result.get("subrequests")
    if chunks and subrequests:
        cursor = 0
        for chunk_index, chunk in enumerate(chunks):
            if cursor <= token_index < cursor + len(chunk):
                subresult = subrequests[chunk_index]["result"]
                return {
                    "location": "logical_context_chunk",
                    "logical_chunk_index": chunk_index,
                    "global_token_index": token_index,
                    "local_token_index": token_index - cursor,
                    "subrequest_state": _block_state(subresult, token_index - cursor),
                }
            cursor += len(chunk)
        return {"location": "outside_logical_chunks", "token_index": token_index}
    dflash = result.get("dflash")
    if not dflash:
        return {"location": "not_dflash"}
    if token_index == 0:
        return {
            "location": "target_prefill_seed",
            "target_prefill_calls": dflash["target_prefill_calls"],
        }
    cursor = 1
    for block_index, advance in enumerate(dflash["acceptance_lengths"]):
        advance = int(advance)
        if cursor <= token_index < cursor + advance:
            audit = dflash["structural_audit"][block_index]
            return {
                "location": "verification_block",
                "block_index": block_index,
                "emitted_position_in_block": token_index - cursor,
                "block_size": dflash["block_sizes"][block_index],
                "acceptance_length": advance,
                "audit": audit,
                "verifier_counters": {
                    key: dflash[key]
                    for key in (
                        "target_prefill_calls",
                        "target_verification_calls",
                        "target_single_token_calls",
                        "draft_forward_calls",
                        "accepted_draft_tokens",
                        "draft_tokens_proposed",
                        "rollback_tokens",
                        "correction_tokens",
                        "bonus_tokens",
                    )
                },
            }
        cursor += advance
    return {"location": "outside_recorded_blocks", "token_index": token_index}


def _stopping_state(result: dict[str, Any], token_index: int) -> dict[str, Any]:
    metrics = result.get("protocol_metrics", {})
    return {
        "first_divergence_token_index": token_index,
        "output_tokens": result["output_tokens"],
        "stop_reason": result["stop_reason"],
        "cap_hit": bool(metrics.get("cap_hit", result["stop_reason"] == "max_new_tokens")),
        "last_generated_token_id": result["generated_token_ids"][-1],
    }


def _classification(
    left_token: int | None,
    right_token: int | None,
    stop_token_ids: set[int],
    same_input: bool,
    block_state: dict[str, Any],
) -> dict[str, str]:
    if (left_token in stop_token_ids) != (right_token in stop_token_ids):
        return {
            "category": "eos/stopping",
            "reason": "first divergence is EOS versus a non-EOS emitted token",
        }
    cursor = block_state
    while isinstance(cursor.get("subrequest_state"), dict):
        cursor = cursor["subrequest_state"]
    audit = cursor.get("audit", {})
    if same_input and audit.get("structural_pass") is True:
        return {
            "category": "block verification",
            "reason": (
                "target top-1 differs between AR single-token and D-Flash block-shaped verification "
                "despite matching rendered input and passing cache/block structural checks; raw "
                "artifacts do not isolate SDPA numerical drift from quantized block-shape drift"
            ),
        }
    return {
        "category": "other",
        "reason": "insufficient evidence for EOS, punctuation, cache, block, or SDPA classification",
    }


def _record(
    *,
    suite: str,
    fixture_id: str,
    pair: str,
    left_condition: str,
    right_condition: str,
    left_result: dict[str, Any],
    right_result: dict[str, Any],
    same_input: bool,
    rendered_input: dict[str, Any],
    stop_token_ids: set[int],
) -> dict[str, Any] | None:
    left_ids = [int(token) for token in left_result["generated_token_ids"]]
    right_ids = [int(token) for token in right_result["generated_token_ids"]]
    index = _first_difference(left_ids, right_ids)
    if index is None:
        return None
    left_token = left_ids[index] if index < len(left_ids) else None
    right_token = right_ids[index] if index < len(right_ids) else None
    block = _block_state(right_result, index)
    return {
        "suite": suite,
        "fixture_id": fixture_id,
        "pair": pair,
        "left_condition": left_condition,
        "right_condition": right_condition,
        "rendered_input": rendered_input,
        "rendered_input_match": same_input,
        "first_divergence": {
            "token_index": index,
            "ar_greedy_token_id": left_token,
            "dflash_emitted_token_id": right_token,
            "left_prefix_token_ids": left_ids[: index + 1],
            "right_prefix_token_ids": right_ids[: index + 1],
        },
        "left_generated_ids": left_ids,
        "right_generated_ids": right_ids,
        "left_generated_ids_sha256": hashlib.sha256(
            json.dumps(left_ids, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "right_generated_ids_sha256": hashlib.sha256(
            json.dumps(right_ids, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "dflash_block_and_cache_state": block,
        "left_stopping_state": _stopping_state(left_result, index),
        "right_stopping_state": _stopping_state(right_result, index),
        "classification": _classification(
            left_token, right_token, stop_token_ids, same_input, block
        ),
    }


def _mock_failures(root: Path, stop_token_ids: set[int]) -> list[dict[str, Any]]:
    raw = _read_json(root / "raw_runs.json")
    pair_specs = {
        str(pair["name"]): pair
        for pair in raw["resolved_config_snapshot"]["profile_settings"]["parity_pairs"]
    }
    failures = []
    for prompt in raw["prompts"]:
        for pair in prompt["pair_token_parity"]:
            if pair["pass"]:
                continue
            spec = pair_specs[str(pair["pair"])]
            left_condition = str(spec["left"])
            right_condition = str(spec["right"])
            left = prompt["runs"][left_condition]["result"]
            right = prompt["runs"][right_condition]["result"]
            chat = right["protocol_metrics"]["chat_template_input"]
            record = _record(
                suite="mock10",
                fixture_id=prompt["prompt_id"],
                pair=pair["pair"],
                left_condition=left_condition,
                right_condition=right_condition,
                left_result=left,
                right_result=right,
                same_input=bool(pair["chat_template_input_token_ids_equal"]),
                rendered_input={
                    "token_ids": chat["token_ids"],
                    "token_ids_sha256": chat["token_ids_sha256"],
                    "token_count": chat["token_count"],
                },
                stop_token_ids=stop_token_ids,
            )
            if record:
                failures.append(record)
    return failures


def _dataset_failures(root: Path, stop_token_ids: set[int]) -> list[dict[str, Any]]:
    rows = _read_jsonl(root / "per_sample_results.jsonl")
    index = {(row["dataset"], row["fixture_id"], row["condition"]): row for row in rows}
    parity = _read_json(root / "pair_parity.json")
    failures = []
    for pair in parity["records"]:
        if pair["generated_token_ids_match"]:
            continue
        left_row = index[(pair["dataset"], pair["fixture_id"], pair["left"])]
        right_row = index[(pair["dataset"], pair["fixture_id"], pair["right"])]
        left = left_row["run"]["result"]
        right = right_row["run"]["result"]
        chat = right["protocol_metrics"]["chat_template_input"]
        record = _record(
            suite=f"dataset:{pair['dataset']}",
            fixture_id=pair["fixture_id"],
            pair=pair["pair"],
            left_condition=pair["left"],
            right_condition=pair["right"],
            left_result=left,
            right_result=right,
            same_input=bool(pair["input_token_ids_match"]),
            rendered_input={
                "token_ids": chat["token_ids"],
                "token_ids_sha256": chat["token_ids_sha256"],
                "token_count": chat["token_count"],
                "chunk_token_ids": chat.get("chunk_token_ids"),
                "chunk_token_ids_sha256": chat.get("chunk_token_ids_sha256"),
            },
            stop_token_ids=stop_token_ids,
        )
        if record:
            failures.append(record)
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args()
    from ccdf.config import load_config

    config = load_config(args.config)
    stop_token_ids = {int(value) for value in config.require("runtime.stop_token_ids")}
    root = args.artifact_root.resolve()
    failures = [
        *_mock_failures(root / "mock10", stop_token_ids),
        *_dataset_failures(root / "dataset-smoke", stop_token_ids),
    ]
    payload = {
        "diagnostic_version": "ccdf.windows-auto-sdpa-parity.v1",
        "config_sha256": hashlib.sha256(config.path.read_bytes()).hexdigest(),
        "failure_count": len(failures),
        "failures": failures,
        "classification_counts": {
            category: sum(
                failure["classification"]["category"] == category for failure in failures
            )
            for category in (
                "eos/stopping",
                "punctuation",
                "block verification",
                "cache progression",
                "SDPA numerical drift",
                "other",
            )
        },
        "claim_boundary": (
            "The diagnostic classifies only what sealed raw evidence proves; it does not relabel "
            "unisolated block-shape drift as SDPA drift."
        ),
    }
    output = root / "parity-diagnostics" / "first-divergences.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "failure_count": len(failures)}, indent=2))


if __name__ == "__main__":
    main()
