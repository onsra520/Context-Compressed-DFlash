"""Focused full-structural audit for REC-3 mock02 compressed parity divergence."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("PROJECT_ROOT", str(ROOT))

from ccdf.compression import LLMLinguaCompressor  # noqa: E402
from ccdf.config import Rec2Config, load_config  # noqa: E402
from ccdf.device import synchronize  # noqa: E402
from ccdf.runtime.engine import RuntimeEngine  # noqa: E402


RUNNER_PATH = Path(__file__).with_name("run_rec3_four_condition_protocol.py")
SPEC = importlib.util.spec_from_file_location("rec3_protocol_runner", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {RUNNER_PATH}")
REC3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REC3)

OUTPUT_DIR = ROOT / "docs/artifacts/rec3-four-condition-mock10"
OUTPUT = OUTPUT_DIR / "rec3_mock_02_divergence.json"
BLOCKER = OUTPUT_DIR / "BLOCKER.md"
REPETITIONS = 5
ORDERS = (
    ("ar_then_dflash", ("llmlingua-ar-r2", "cc-dflash-r2")),
    ("dflash_then_ar", ("cc-dflash-r2", "llmlingua-ar-r2")),
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _diagnostic_config(config: Rec2Config) -> Rec2Config:
    base = REC3._mock_config(config)
    data = copy.deepcopy(base.data)
    data["optimization"]["full_structural_audit"] = True
    data["optimization"]["compact_structural_audit"] = True
    return Rec2Config(path=base.path, root=base.root, data=data)


def _annotate_structural_audit(audit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cursor = 1  # generated token zero is produced by target prefill
    annotated = []
    for source in audit:
        item = dict(source)
        item["output_index_start"] = cursor
        item["output_index_end_exclusive"] = cursor + int(item["emitted_advance"])
        item["cache_progression_pass"] = (
            item["cache_length_after"] == item["expected_cache_length_after"]
            and item["cache_length_before"] == item["start"]
        )
        annotated.append(item)
        cursor += int(item["emitted_advance"])
    return annotated


def _verifier_token_for_index(
    generated_ids: list[int], audit: list[dict[str, Any]], output_index: int
) -> tuple[int | None, dict[str, Any] | None]:
    if output_index == 0:
        return generated_ids[0] if generated_ids else None, {
            "source": "target_prefill_seed", "output_index": 0,
        }
    for block in audit:
        start = int(block["output_index_start"])
        end = int(block["output_index_end_exclusive"])
        if not start <= output_index < end:
            continue
        relative = output_index - start
        accepted = int(block["accepted_count"])
        verifier_ids = list(block.get("verifier_token_ids") or [])
        proposals = list(block.get("proposal_token_ids") or [])
        emitted = list(block.get("emitted_token_ids") or [])
        if relative < accepted:
            verifier_token = verifier_ids[relative]
            source = "accepted_proposal_verified_by_target"
            proposal_token = proposals[relative]
        else:
            verifier_token = int(block["correction_token_id"])
            source = "target_correction_token"
            proposal_token = proposals[relative] if relative < len(proposals) else None
        return verifier_token, {
            "source": source,
            "block_index": block["block_index"],
            "block_relative_output_index": relative,
            "proposal_token_id": proposal_token,
            "target_verifier_token_id": verifier_token,
            "dflash_emitted_token_id": emitted[relative] if relative < len(emitted) else None,
            "cache_length_before": block["cache_length_before"],
            "cache_length_after": block["cache_length_after"],
            "expected_cache_length_after": block["expected_cache_length_after"],
            "cache_progression_pass": block["cache_progression_pass"],
        }
    return None, None


def _compare_pair(ar_run: dict[str, Any], dflash_run: dict[str, Any]) -> dict[str, Any]:
    ar_ids = list(ar_run["result"]["generated_token_ids"])
    dflash_ids = list(dflash_run["result"]["generated_token_ids"])
    audit = list(dflash_run["result"]["dflash"]["structural_audit"])
    first_divergence = next(
        (index for index, (left, right) in enumerate(zip(ar_ids, dflash_ids)) if left != right),
        min(len(ar_ids), len(dflash_ids)) if len(ar_ids) != len(dflash_ids) else None,
    )
    token_table = []
    for index in range(max(len(ar_ids), len(dflash_ids))):
        verifier_token, verifier_context = _verifier_token_for_index(dflash_ids, audit, index)
        ar_token = ar_ids[index] if index < len(ar_ids) else None
        dflash_token = dflash_ids[index] if index < len(dflash_ids) else None
        token_table.append({
            "output_index": index,
            "greedy_target_token_id": ar_token,
            "dflash_emitted_token_id": dflash_token,
            "dflash_target_verifier_token_id": verifier_token,
            "greedy_equals_dflash": ar_token == dflash_token,
            "greedy_equals_dflash_verifier": ar_token == verifier_token,
            "verifier_context": verifier_context,
        })
    divergence_context = token_table[first_divergence] if first_divergence is not None else None
    return {
        "chat_template_input_token_ids_equal": (
            ar_run["chat_template_input"]["token_ids"]
            == dflash_run["chat_template_input"]["token_ids"]
        ),
        "chat_template_input_sha256_equal": (
            ar_run["chat_template_input"]["token_ids_sha256"]
            == dflash_run["chat_template_input"]["token_ids_sha256"]
        ),
        "generated_token_parity": ar_ids == dflash_ids,
        "first_divergence_output_index": first_divergence,
        "prefix_equal_before_divergence": (
            ar_ids[:first_divergence] == dflash_ids[:first_divergence]
            if first_divergence is not None else True
        ),
        "divergence_context": divergence_context,
        "greedy_target_vs_dflash_verifier_token_table": token_table,
    }


def _run_condition(
    condition: str, prompt: str, config: Rec2Config, order_name: str
) -> dict[str, Any]:
    runtime_condition = "baseline" if condition == "llmlingua-ar-r2" else "dflash"
    engine = RuntimeEngine(config, condition=runtime_condition)
    try:
        chat_input = REC3._capture_chat_template_input(engine, prompt)
        rows = []
        for repetition in range(1, REPETITIONS + 1):
            synchronize()
            started = time.perf_counter()
            result = engine.generate(
                prompt, max_new_tokens=REC3.MAX_NEW_TOKENS, temperature=0.0
            ).to_dict()
            synchronize()
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if result["dflash"] is not None:
                result["dflash"]["structural_audit"] = _annotate_structural_audit(
                    result["dflash"]["structural_audit"]
                )
            rows.append({
                "order": order_name,
                "condition": condition,
                "repetition": repetition,
                "chat_template_input": chat_input,
                "synchronized_wall_clock_ms": elapsed_ms,
                "result": result,
            })
        return {"condition": condition, "rows": rows}
    finally:
        engine.close()


def _blocker_markdown(payload: dict[str, Any]) -> str:
    root = payload["root_cause"]
    return f"""# REC-3 mock02 compressed AR-DFlash blocker

## Decision

REC-3 remains blocked before dataset smoke. The compressed `rec3_mock_02` input is byte/token
identical across AR and D-Flash, but greedy AR and the D-Flash target verifier diverge reproducibly.

## Evidence

- Orders: `ar_then_dflash`, `dflash_then_ar`
- Repetitions per order: {REPETITIONS}
- Divergences reproduced: {root['divergent_pairs']}/{root['pair_count']}
- First divergence indices: {root['first_divergence_indices']}
- Structural audits complete: {root['full_structural_audit_pass']}
- Cache progression internally consistent: {root['cache_progression_pass']}
- Classification: `{root['classification']}`

The first divergent D-Flash token is the token selected by the cached block target verifier while
the same-prefix greedy cached target selects another token. This places the observed mismatch in
the D-Flash target-verification/cache numerical path, not in fixture rendering, compressor config,
execution order, or output parsing.

## Separate patch proposal (not applied in this diagnostic batch)

Create a dedicated D-Flash core change that captures target top-2 logits/margins at verification
positions and evaluates an exact-compatible verification policy for near-tie NF4 logits. The patch
must keep Baseline-AR unchanged, preserve real target-forward accounting, and pass exact token parity
on both GSM8K and QMSum before acceptance. Do not adopt a silent per-token oracle fallback.
"""


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("REC-3 mock02 divergence diagnostic requires CUDA")
    config = _diagnostic_config(load_config(ROOT / "config.yml"))
    fixture = REC3._fixture(2, *REC3.CASES[1])
    protocol = fixture["protocol"]
    compressor = LLMLinguaCompressor(
        config.path_for("models.compressor.local_path"),
        device=str(config.require("models.compressor.device")),
        local_files_only=bool(config.require("runtime.local_files_only")),
        reserved_vram_budget_gib=float(config.require("models.compressor.reserved_budget_gib")),
    )
    try:
        compression = compressor.compress(protocol, REC3.COMPRESSION_CONFIG)
        compressed_prompt = protocol.render(compression.compressed_context)
        compressor_contract = {
            "model_contract": compressor.model_contract,
            "device_audit": compressor.device_audit,
            "compression_config": {
                "keep_rate": REC3.COMPRESSION_CONFIG.keep_rate,
                "chunk_max_words": REC3.COMPRESSION_CONFIG.chunk_max_words,
                "min_context_tokens": REC3.COMPRESSION_CONFIG.min_context_tokens,
            },
            "original_context_tokens": compression.original_tokens,
            "compressed_context_tokens": compression.compressed_tokens,
            "compressed_prompt_sha256": _sha256_text(compressed_prompt),
        }
    finally:
        compressor.close()

    order_results = []
    comparisons = []
    for order_name, conditions in ORDERS:
        by_condition = {
            condition: _run_condition(condition, compressed_prompt, config, order_name)
            for condition in conditions
        }
        order_results.append({
            "order": order_name,
            "conditions": [by_condition[condition] for condition in conditions],
        })
        ar_rows = by_condition["llmlingua-ar-r2"]["rows"]
        dflash_rows = by_condition["cc-dflash-r2"]["rows"]
        for repetition, (ar_run, dflash_run) in enumerate(zip(ar_rows, dflash_rows), start=1):
            comparisons.append({
                "order": order_name,
                "repetition": repetition,
                **_compare_pair(ar_run, dflash_run),
            })

    dflash_rows = [
        row for order in order_results for condition in order["conditions"]
        if condition["condition"] == "cc-dflash-r2" for row in condition["rows"]
    ]
    audits = [block for row in dflash_rows for block in row["result"]["dflash"]["structural_audit"]]
    divergent = [item for item in comparisons if not item["generated_token_parity"]]
    verifier_mismatches = [
        item for item in divergent
        if item["divergence_context"] is not None
        and not item["divergence_context"]["greedy_equals_dflash_verifier"]
    ]
    root_cause = {
        "pair_count": len(comparisons),
        "divergent_pairs": len(divergent),
        "first_divergence_indices": sorted({item["first_divergence_output_index"] for item in divergent}),
        "order_invariant": all(
            any(item["order"] == order and not item["generated_token_parity"] for item in comparisons)
            for order, _ in ORDERS
        ),
        "identical_chat_template_inputs": all(item["chat_template_input_token_ids_equal"] for item in comparisons),
        "full_structural_audit_pass": all(
            all(key in block for key in ("proposal_token_ids", "verifier_token_ids", "correction_token_id", "emitted_token_ids"))
            for block in audits
        ),
        "cache_progression_pass": all(block["cache_progression_pass"] for block in audits),
        "greedy_vs_dflash_verifier_mismatch_count": len(verifier_mismatches),
        "classification": (
            "dflash_core_target_verification_cache_numerical_path"
            if divergent and len(verifier_mismatches) == len(divergent)
            else "inconclusive"
        ),
        "core_patch_applied": False,
        "dataset_smoke_blocked": bool(divergent),
    }
    payload = {
        "diagnostic_version": "ccdf.rec3-mock02-divergence.v1",
        "fixture": REC3._json_fixture(fixture),
        "system_prompt": REC3.NEUTRAL_SYSTEM_PROMPT,
        "system_prompt_sha256": _sha256_text(REC3.NEUTRAL_SYSTEM_PROMPT),
        "compressor": compressor_contract,
        "execution_protocol": {
            "orders": [name for name, _ in ORDERS],
            "repetitions_per_order": REPETITIONS,
            "temperature": 0.0,
            "max_new_tokens": REC3.MAX_NEW_TOKENS,
            "full_structural_audit": True,
            "cuda_synchronize_before_timer": True,
        },
        "orders": order_results,
        "comparisons": comparisons,
        "root_cause": root_cause,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if root_cause["classification"].startswith("dflash_core"):
        BLOCKER.write_text(_blocker_markdown(payload), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "root_cause": root_cause}, sort_keys=True))
    if root_cause["classification"] == "inconclusive":
        raise SystemExit("mock02 divergence diagnostic was inconclusive")


if __name__ == "__main__":
    main()
