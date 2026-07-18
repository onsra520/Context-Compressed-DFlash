"""REC-3 fixed verification-block-size ablation on the frozen mock10 prompts."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("PROJECT_ROOT", str(ROOT))

from ccdf.config import Rec2Config, load_config  # noqa: E402
from ccdf.device import synchronize  # noqa: E402
from ccdf.runtime.engine import RuntimeEngine  # noqa: E402


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REC3 = _load_module("rec3_protocol_runner", Path(__file__).with_name("run_rec3_four_condition_protocol.py"))
VERIFIER_DIAG = _load_module(
    "rec3_verifier_diagnostic", Path(__file__).with_name("run_rec3_dflash_verifier_diagnostic.py")
)

ARTIFACT_ROOT = ROOT / "docs/artifacts/rec3-dflash-block-size-ablation-mock10"
REPORT_PATH = ARTIFACT_ROOT / "ablation.json"
SUMMARY_PATH = ARTIFACT_ROOT / "summary.json"
FUTURE_LOGITS_PATH = ARTIFACT_ROOT / "future_token_invariance_logits.pt"
PROTOCOL_RAW = ROOT / "docs/artifacts/rec3-four-condition-mock10/raw_runs.json"
BLOCK_SIZES = (4, 8, 12, 16)
CONDITIONS = ("baseline-ar", "dflash-r1", "llmlingua-ar-r2", "cc-dflash-r2")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _block_config(config: Rec2Config, block_size: int) -> Rec2Config:
    data = copy.deepcopy(config.data)
    data["optimization"]["block_policy"]["mode"] = "fixed"
    data["optimization"]["block_policy"]["fixed_block_size"] = block_size
    return Rec2Config(path=config.path, root=config.root, data=data)


def _locked_prompts() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(PROTOCOL_RAW.read_text(encoding="utf-8"))
    prompts = []
    for source in payload["prompts"]:
        prompts.append({
            "prompt_id": source["prompt_id"],
            "expected_fields": source["expected_fields"],
            "original_prompt": source["original_prompt"],
            "compressed_prompt": source["compressed_prompt"],
            "original_prompt_sha256": source["original_prompt_sha256"],
            "compressed_prompt_sha256": source["compressed_prompt_sha256"],
            "compression": source["compression"],
        })
    if len(prompts) != 10:
        raise RuntimeError(f"expected 10 locked prompts, found {len(prompts)}")
    return prompts, {
        "source_artifact": str(PROTOCOL_RAW.relative_to(ROOT)),
        "source_artifact_sha256": _sha256(PROTOCOL_RAW),
        "prompt_count": len(prompts),
        "prompt_ids": [item["prompt_id"] for item in prompts],
        "original_prompt_sha256": {item["prompt_id"]: item["original_prompt_sha256"] for item in prompts},
        "compressed_prompt_sha256": {item["prompt_id"]: item["compressed_prompt_sha256"] for item in prompts},
    }


def _generate(
    engine: RuntimeEngine,
    prompt: dict[str, Any],
    *,
    condition: str,
    prompt_kind: str,
    block_size: int | None,
) -> dict[str, Any]:
    text = prompt["original_prompt"] if prompt_kind == "original" else prompt["compressed_prompt"]
    chat_input = REC3._capture_chat_template_input(engine, text)
    synchronize()
    started = time.perf_counter()
    result = engine.generate(
        text, max_new_tokens=REC3.MAX_NEW_TOKENS, temperature=0.0
    ).to_dict()
    synchronize()
    wall_ms = (time.perf_counter() - started) * 1000.0
    compression_ms = (
        float(prompt["compression"]["compression_latency_ms"])
        if prompt_kind == "compressed" else 0.0
    )
    quality = REC3._output_quality_record(result["text"], prompt["expected_fields"])
    return {
        "prompt_id": prompt["prompt_id"],
        "condition": condition,
        "prompt_kind": prompt_kind,
        "verification_block_size": block_size,
        "chat_template_input": chat_input,
        "generated_token_ids": result["generated_token_ids"],
        "text": result["text"],
        "output_tokens": result["output_tokens"],
        "stop_reason": result["stop_reason"],
        "quality": quality,
        "metrics": {
            "context_reduction_rate": (
                prompt["compression"]["reduction_rate"] if prompt_kind == "compressed" else None
            ),
            "compression_latency_ms": compression_ms,
            "decode_tok_s": result["metrics"]["decode_tok_s"],
            "generation_latency_ms": result["timing"]["generation_total_ms"],
            "stage_sum_warm_e2e_ms": compression_ms + result["timing"]["warm_request_ms"],
            "synchronized_request_wall_clock_ms": wall_ms,
            "peak_allocated_bytes": result["memory"]["peak_allocated_bytes"],
            "peak_reserved_bytes": result["memory"]["peak_reserved_bytes"],
        },
        "dflash": result["dflash"],
        "runtime": result["runtime"],
        "model": result["model"],
    }


def _run_ar_references(config: Rec2Config, prompts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    engine = RuntimeEngine(config, condition="baseline")
    try:
        # One warmup for each input family, excluded from measured rows.
        engine.generate(prompts[0]["original_prompt"], max_new_tokens=REC3.MAX_NEW_TOKENS, temperature=0.0)
        engine.generate(prompts[0]["compressed_prompt"], max_new_tokens=REC3.MAX_NEW_TOKENS, temperature=0.0)
        return {
            "baseline-ar": {
                prompt["prompt_id"]: _generate(
                    engine, prompt, condition="baseline-ar", prompt_kind="original", block_size=None
                ) for prompt in prompts
            },
            "llmlingua-ar-r2": {
                prompt["prompt_id"]: _generate(
                    engine, prompt, condition="llmlingua-ar-r2", prompt_kind="compressed", block_size=None
                ) for prompt in prompts
            },
        }
    finally:
        engine.close()


def _future_token_invariance(
    engine: RuntimeEngine, compressed_prompt: str
) -> tuple[dict[str, Any], dict[str, torch.Tensor]]:
    input_ids = engine.encode_prompt(compressed_prompt)
    proposals, seed, drafter_positions = VERIFIER_DIAG._draft_proposals(
        engine.target, engine.drafter, input_ids, 16
    )
    vocab_size = int(engine.target.config.vocab_size)
    variants = {
        "original": proposals,
        "shifted_future": [
            proposals[0],
            *[
                (token_id + 7919 * (index + 1)) % vocab_size
                for index, token_id in enumerate(proposals[1:])
            ],
        ],
        "mask_future": [proposals[0], *([int(engine.drafter.mask_token_id)] * (len(proposals) - 1))],
    }
    outputs = {}
    raw = {}
    for name, proposal_ids in variants.items():
        result = VERIFIER_DIAG._block_target_variant(
            engine.target, input_ids, seed, proposal_ids, 16,
            explicit_attention_mask=False,
        )
        outputs[name] = VERIFIER_DIAG._strip_private(result)
        raw[name] = result["raw_logits"].detach().to(dtype=torch.float32, device="cpu")
    reference = raw["original"]
    comparisons = {
        name: {
            "same_seed": outputs[name]["input_ids"][0][0] == outputs["original"]["input_ids"][0][0],
            "same_first_proposal": proposal_ids[0] == variants["original"][0],
            "future_proposals_changed": proposal_ids[1:] != variants["original"][1:] if name != "original" else False,
            "full_logit_vector_exact_equal": bool(torch.equal(reference, raw[name])),
            "max_abs_logit_diff": float((reference - raw[name]).abs().max().item()),
            "reference_sha256": VERIFIER_DIAG._tensor_sha256(reference),
            "candidate_sha256": VERIFIER_DIAG._tensor_sha256(raw[name]),
        }
        for name, proposal_ids in variants.items()
    }
    pass_gate = all(
        comparisons[name]["same_seed"]
        and comparisons[name]["same_first_proposal"]
        and comparisons[name]["future_proposals_changed"]
        and comparisons[name]["full_logit_vector_exact_equal"]
        for name in ("shifted_future", "mask_future")
    )
    return {
        "prompt_id": "rec3_mock_02",
        "block_size": 16,
        "divergence_block_logit_index": 1,
        "seed_token_id": seed,
        "first_proposal_token_id": proposals[0],
        "drafter_position_ids": [[int(value) for value in row] for row in drafter_positions.cpu().tolist()],
        "variants": variants,
        "outputs": outputs,
        "comparisons": comparisons,
        "causal_future_token_invariance_pass": pass_gate,
        "conclusion": (
            "Changing future proposal IDs at fixed shape 16 leaves the full divergence logit vector exactly unchanged; causal leakage is excluded."
            if pass_gate else "Future proposal IDs changed divergence logits; causal leakage remains possible."
        ),
    }, raw


def _run_dflash_block(
    base_config: Rec2Config,
    prompts: list[dict[str, Any]],
    block_size: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None, dict[str, torch.Tensor]]:
    config = _block_config(base_config, block_size)
    engine = RuntimeEngine(config, condition="dflash")
    future = None
    raw_future: dict[str, torch.Tensor] = {}
    try:
        engine.generate(prompts[0]["original_prompt"], max_new_tokens=REC3.MAX_NEW_TOKENS, temperature=0.0)
        engine.generate(prompts[0]["compressed_prompt"], max_new_tokens=REC3.MAX_NEW_TOKENS, temperature=0.0)
        rows = {
            "dflash-r1": {
                prompt["prompt_id"]: _generate(
                    engine, prompt, condition="dflash-r1", prompt_kind="original", block_size=block_size
                ) for prompt in prompts
            },
            "cc-dflash-r2": {
                prompt["prompt_id"]: _generate(
                    engine, prompt, condition="cc-dflash-r2", prompt_kind="compressed", block_size=block_size
                ) for prompt in prompts
            },
        }
        if block_size == 16:
            prompt = next(item for item in prompts if item["prompt_id"] == "rec3_mock_02")
            future, raw_future = _future_token_invariance(engine, prompt["compressed_prompt"])
        return rows, future, raw_future
    finally:
        engine.close()


def _weighted_dflash(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counters = {
        "target_prefill_calls": 0, "target_verification_calls": 0,
        "target_single_token_calls": 0, "accepted_draft_tokens": 0,
        "draft_tokens_proposed": 0, "emitted_tokens": 0, "output_tokens": 0,
    }
    for row in rows:
        dflash = row["dflash"]
        for key in (
            "target_prefill_calls", "target_verification_calls", "target_single_token_calls",
            "accepted_draft_tokens", "draft_tokens_proposed",
        ):
            counters[key] += int(dflash[key])
        counters["emitted_tokens"] += sum(int(value) for value in dflash["acceptance_lengths"])
        counters["output_tokens"] += int(row["output_tokens"])
    target_forwards = (
        counters["target_prefill_calls"]
        + counters["target_verification_calls"]
        + counters["target_single_token_calls"]
    )
    return {
        "counters": counters,
        "weighted_tau": counters["emitted_tokens"] / counters["target_verification_calls"],
        "weighted_acceptance_rate": counters["accepted_draft_tokens"] / counters["draft_tokens_proposed"],
        "target_forwards_per_output_token": target_forwards / counters["output_tokens"],
    }


def _condition_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "exact_field_quality": sum(row["quality"]["exact_field_match"] for row in rows),
        "strict_format_compliance": sum(row["quality"]["format_compliant"] for row in rows),
        "p50_decode_tok_s": statistics.median(row["metrics"]["decode_tok_s"] for row in rows),
        "p50_stage_sum_warm_e2e_ms": statistics.median(row["metrics"]["stage_sum_warm_e2e_ms"] for row in rows),
        "p50_synchronized_request_wall_clock_ms": statistics.median(row["metrics"]["synchronized_request_wall_clock_ms"] for row in rows),
        "max_peak_allocated_bytes": max(row["metrics"]["peak_allocated_bytes"] for row in rows),
        "max_peak_reserved_bytes": max(row["metrics"]["peak_reserved_bytes"] for row in rows),
        "weighted_dflash": _weighted_dflash(rows) if rows[0]["dflash"] is not None else None,
        "context_reduction_rate": (
            statistics.mean(row["metrics"]["context_reduction_rate"] for row in rows)
            if rows[0]["metrics"]["context_reduction_rate"] is not None else None
        ),
    }


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("REC-3 block-size ablation requires CUDA")
    prompts, input_contract = _locked_prompts()
    base_config = REC3._mock_config(load_config(ROOT / "config.yml"))
    canonical_block_size = int(base_config.require("optimization.block_policy.fixed_block_size"))
    workload_started = time.perf_counter()
    ar = _run_ar_references(base_config, prompts)
    block_results = []
    future_invariance = None
    future_logits: dict[str, torch.Tensor] = {}
    for block_size in BLOCK_SIZES:
        dflash, future, raw_future = _run_dflash_block(base_config, prompts, block_size)
        if future is not None:
            future_invariance = future
            future_logits = raw_future
        pairs = []
        for prompt in prompts:
            prompt_id = prompt["prompt_id"]
            for pair_name, ar_condition, dflash_condition in (
                ("original", "baseline-ar", "dflash-r1"),
                ("compressed", "llmlingua-ar-r2", "cc-dflash-r2"),
            ):
                left = ar[ar_condition][prompt_id]
                right = dflash[dflash_condition][prompt_id]
                pairs.append({
                    "prompt_id": prompt_id, "pair": pair_name,
                    "ar_condition": ar_condition, "dflash_condition": dflash_condition,
                    "chat_template_input_token_ids_equal": (
                        left["chat_template_input"]["token_ids"]
                        == right["chat_template_input"]["token_ids"]
                    ),
                    "generated_token_parity": left["generated_token_ids"] == right["generated_token_ids"],
                })
        conditions = {
            "baseline-ar": list(ar["baseline-ar"].values()),
            "dflash-r1": list(dflash["dflash-r1"].values()),
            "llmlingua-ar-r2": list(ar["llmlingua-ar-r2"].values()),
            "cc-dflash-r2": list(dflash["cc-dflash-r2"].values()),
        }
        condition_summaries = {
            condition: _condition_summary(rows) for condition, rows in conditions.items()
        }
        pair_parity = sum(
            pair["chat_template_input_token_ids_equal"] and pair["generated_token_parity"]
            for pair in pairs
        )
        exact_quality = sum(
            summary["exact_field_quality"] for summary in condition_summaries.values()
        )
        strict_format = sum(
            summary["strict_format_compliance"] for summary in condition_summaries.values()
        )
        block_results.append({
            "block_size": block_size,
            "conditions": conditions,
            "condition_summaries": condition_summaries,
            "pairs": pairs,
            "pair_parity": f"{pair_parity}/20",
            "exact_field_quality": f"{exact_quality}/40",
            "strict_format_compliance": f"{strict_format}/40",
            "selection_gate_pass": pair_parity == 20 and exact_quality == 40,
        })

    eligible = [item["block_size"] for item in block_results if item["selection_gate_pass"]]
    selected = max(eligible) if eligible else None
    if future_invariance is None:
        raise RuntimeError("block-16 future-token invariance evidence was not produced")
    summary = {
        "ablation_complete": all(
            len(item["conditions"][condition]) == 10
            for item in block_results for condition in CONDITIONS
        ),
        "block_sizes": list(BLOCK_SIZES),
        "selection_rule": "largest fixed block size with 20/20 pair parity and 40/40 exact-field quality",
        "selected_block_size": selected,
        "canonical_config_block_size_before": canonical_block_size,
        "canonical_config_changed": False,
        "future_token_invariance_pass": future_invariance["causal_future_token_invariance_pass"],
        "results": [
            {
                key: item[key] for key in (
                    "block_size", "pair_parity", "exact_field_quality",
                    "strict_format_compliance", "selection_gate_pass", "condition_summaries",
                )
            } for item in block_results
        ],
        "pass": selected is not None and future_invariance["causal_future_token_invariance_pass"],
    }
    report = {
        "ablation_version": "ccdf.rec3-dflash-block-size-ablation-mock10.v1",
        "input_contract": input_contract,
        "runtime_contract": {
            "model_unchanged": True, "prompt_unchanged": True,
            "compressed_prompt_unchanged": True,
            "sdpa_kernel": base_config.require("runtime.sdpa_kernel"),
            "awq_split_k_iters": base_config.require("runtime.awq_split_k_iters"),
            "temperature": 0.0, "max_new_tokens": REC3.MAX_NEW_TOKENS,
            "block_policy_mode": "fixed", "canonical_config_changed": False,
        },
        "environment": REC3._gpu_environment(),
        "ar_references": ar,
        "block_results": block_results,
        "future_token_invariance": future_invariance,
        "workload_wall_clock_ms": (time.perf_counter() - workload_started) * 1000.0,
        "summary": summary,
    }
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    torch.save(future_logits, FUTURE_LOGITS_PATH)
    report["future_token_invariance"]["raw_logits"] = {
        "path": str(FUTURE_LOGITS_PATH.relative_to(ROOT)),
        "sha256": _sha256(FUTURE_LOGITS_PATH),
        "keys": sorted(future_logits),
        "format": "torch.save float32 full-vocabulary logit vectors",
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    if not summary["pass"]:
        raise SystemExit("REC-3 block-size ablation did not identify an eligible block size")


if __name__ == "__main__":
    main()
