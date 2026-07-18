"""Same-target REC-3 mock02 verifier diagnostic; validation-only, no core edits."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import torch
from transformers import DynamicCache


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("PROJECT_ROOT", str(ROOT))

from ccdf.config import load_config  # noqa: E402
from ccdf.determinism import configure_determinism  # noqa: E402
from ccdf.device import attention_runtime_state, synchronize  # noqa: E402
from ccdf.dflash.acceptance import accepted_prefix_tensor  # noqa: E402
from ccdf.dflash.verifier import extract_context_feature  # noqa: E402
from ccdf.inference.sampling import sample  # noqa: E402
from ccdf.runtime.engine import RuntimeEngine  # noqa: E402


RUNNER_PATH = Path(__file__).with_name("run_rec3_four_condition_protocol.py")
SPEC = importlib.util.spec_from_file_location("rec3_protocol_runner", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {RUNNER_PATH}")
REC3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REC3)

ARTIFACT_ROOT = ROOT / "docs/artifacts/rec3-dflash-verifier-diagnostic"
REPORT_PATH = ARTIFACT_ROOT / "diagnostic.json"
RAW_LOGITS_PATH = ARTIFACT_ROOT / "raw_divergence_logits.pt"
BLOCKER_PATH = ARTIFACT_ROOT / "BLOCKER.md"
PROTOCOL_RAW = ROOT / "docs/artifacts/rec3-four-condition-mock10/raw_runs.json"
BLOCK_SIZES = (2, 4, 8, 16)
TOP_K = 5


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _tensor_sha256(tensor: torch.Tensor) -> str:
    value = tensor.detach().to(dtype=torch.float32, device="cpu").contiguous()
    return _sha256_bytes(value.numpy().tobytes())


def _topk(logits: torch.Tensor) -> dict[str, Any]:
    vector = logits.detach().to(dtype=torch.float32).reshape(-1)
    values, ids = torch.topk(vector, k=TOP_K)
    values_host = [float(value) for value in values.cpu().tolist()]
    ids_host = [int(value) for value in ids.cpu().tolist()]
    return {
        "token_ids": ids_host,
        "logits": values_host,
        "top1_token_id": ids_host[0],
        "top1_logit": values_host[0],
        "top2_logit": values_host[1],
        "top1_margin": values_host[0] - values_host[1],
        "full_logit_vector_sha256_float32": _tensor_sha256(vector),
        "vocab_size": int(vector.numel()),
    }


def _mask_record(mask: torch.Tensor | None) -> dict[str, Any]:
    if mask is None:
        return {"kind": "none", "values": None, "shape": None, "dtype": None}
    host = mask.detach().cpu()
    return {
        "kind": "explicit",
        "values": [[int(value) for value in row] for row in host.tolist()],
        "shape": list(host.shape),
        "dtype": str(mask.dtype),
    }


def _cache_layers(cache: DynamicCache) -> list[tuple[torch.Tensor, torch.Tensor]]:
    layers = getattr(cache, "layers", None)
    if layers is None:
        legacy = cache.to_legacy_cache()
        return [(key, value) for key, value in legacy]
    output = []
    for layer in layers:
        keys = getattr(layer, "keys", None)
        values = getattr(layer, "values", None)
        if keys is not None and values is not None:
            output.append((keys, values))
    return output


def _tensor_semantics(left: torch.Tensor, right: torch.Tensor) -> dict[str, Any]:
    same_shape = tuple(left.shape) == tuple(right.shape)
    if not same_shape:
        return {
            "same_shape": False, "left_shape": list(left.shape), "right_shape": list(right.shape),
            "exact_equal": False, "allclose_atol_1e_5_rtol_1e_5": False,
        }
    left_float = left.detach().to(dtype=torch.float32)
    right_float = right.detach().to(dtype=torch.float32)
    difference = (left_float - right_float).abs()
    denominator = right_float.abs().clamp_min(1e-12)
    return {
        "same_shape": True,
        "shape": list(left.shape),
        "left_dtype": str(left.dtype), "right_dtype": str(right.dtype),
        "exact_equal": bool(torch.equal(left, right)),
        "allclose_atol_1e_5_rtol_1e_5": bool(torch.allclose(left_float, right_float, atol=1e-5, rtol=1e-5)),
        "max_abs_diff": float(difference.max().item()) if difference.numel() else 0.0,
        "mean_abs_diff": float(difference.mean().item()) if difference.numel() else 0.0,
        "max_relative_diff": float((difference / denominator).max().item()) if difference.numel() else 0.0,
        "left_sha256_float32": _tensor_sha256(left_float),
        "right_sha256_float32": _tensor_sha256(right_float),
    }


def _cache_semantics(left: DynamicCache, right: DynamicCache, *, label: str) -> dict[str, Any]:
    left_layers = _cache_layers(left)
    right_layers = _cache_layers(right)
    layer_records = []
    for index, ((left_key, left_value), (right_key, right_value)) in enumerate(zip(left_layers, right_layers)):
        layer_records.append({
            "layer_index": index,
            "key": _tensor_semantics(left_key, right_key),
            "value": _tensor_semantics(left_value, right_value),
        })
    return {
        "label": label,
        "left_sequence_length": int(left.get_seq_length()),
        "right_sequence_length": int(right.get_seq_length()),
        "left_layer_count": len(left_layers),
        "right_layer_count": len(right_layers),
        "all_layers_compared": len(left_layers) == len(right_layers) == len(layer_records),
        "all_exact_equal": bool(layer_records) and all(
            record[component]["exact_equal"] for record in layer_records for component in ("key", "value")
        ),
        "allclose_atol_1e_5_rtol_1e_5": bool(layer_records) and all(
            record[component]["allclose_atol_1e_5_rtol_1e_5"]
            for record in layer_records for component in ("key", "value")
        ),
        "max_abs_diff": max(
            (record[component].get("max_abs_diff", float("inf")) for record in layer_records for component in ("key", "value")),
            default=None,
        ),
        "layers": layer_records,
    }


def _locked_prompt() -> tuple[str, dict[str, Any]]:
    payload = json.loads(PROTOCOL_RAW.read_text(encoding="utf-8"))
    prompt = next(item for item in payload["prompts"] if item["prompt_id"] == "rec3_mock_02")
    fixture = REC3._fixture(2, *REC3.CASES[1])
    if prompt["context"] != fixture["context"]:
        raise RuntimeError("stored REC-3 mock02 context differs from frozen fixture")
    if prompt["question"] != fixture["question"] or prompt["output_instruction"] != fixture["output_instruction"]:
        raise RuntimeError("stored REC-3 mock02 protected fields differ from frozen fixture")
    compressed_prompt = str(prompt["compressed_prompt"])
    if _sha256_text(compressed_prompt) != prompt["compressed_prompt_sha256"]:
        raise RuntimeError("stored compressed prompt SHA-256 mismatch")
    return compressed_prompt, {
        "protocol_artifact": str(PROTOCOL_RAW.relative_to(ROOT)),
        "protocol_artifact_sha256": _sha256_file(PROTOCOL_RAW),
        "prompt_id": prompt["prompt_id"],
        "compressed_prompt_sha256": prompt["compressed_prompt_sha256"],
        "compressed_context_sha256": _sha256_text(prompt["compressed_prompt"].split("\n\nQuestion:\n", 1)[0]),
        "question_sha256": _sha256_text(prompt["question"]),
        "instruction_sha256": _sha256_text(prompt["output_instruction"]),
        "compression": prompt["compression"],
    }


def _target_metadata(engine: RuntimeEngine, config: Any) -> dict[str, Any]:
    parameter = next(engine.target.parameters())
    return {
        "model_metadata": engine.model_metadata,
        "target_class": type(engine.target).__name__,
        "target_parameter_dtype": str(parameter.dtype),
        "target_parameter_device": str(parameter.device),
        "drafter_parameter_dtype": str(next(engine.drafter.parameters()).dtype),
        "quantization": config.require("models.dflash.target.quantization"),
        "attention_backend_config": config.require("runtime.attention_backend"),
        "sdpa_kernel_config": config.require("runtime.sdpa_kernel"),
        "awq_split_k_iters": config.require("runtime.awq_split_k_iters"),
        "attention_runtime_state": attention_runtime_state(engine.target),
        "determinism": engine.determinism,
    }


@torch.inference_mode()
def _prefill_target(
    target: Any, input_ids: torch.Tensor, *, explicit_attention_mask: bool
) -> tuple[Any, DynamicCache, torch.Tensor | None, torch.Tensor]:
    cache = DynamicCache()
    positions = torch.arange(input_ids.shape[1], device=input_ids.device).unsqueeze(0)
    mask = torch.ones_like(input_ids) if explicit_attention_mask else None
    kwargs = {
        "position_ids": positions, "past_key_values": cache, "use_cache": True,
        "logits_to_keep": 1, "output_hidden_states": True,
    }
    if mask is not None:
        kwargs["attention_mask"] = mask
    output = target(input_ids, **kwargs)
    return output, cache, mask, positions


@torch.inference_mode()
def _sequential_path(target: Any, input_ids: torch.Tensor) -> dict[str, Any]:
    synchronize(target.device)
    started = time.perf_counter()
    prefill, cache, prefill_mask, prefill_positions = _prefill_target(
        target, input_ids, explicit_attention_mask=True
    )
    seed = int(sample(prefill.logits, 0.0)[0, -1].item())
    steps = []
    next_token = seed
    divergence_logits = None
    prefix = []
    for output_index in range(3):
        prefix.append(next_token)
        if output_index == 2:
            break
        position = int(input_ids.shape[1] + output_index)
        token = torch.tensor([[next_token]], device=input_ids.device, dtype=torch.long)
        mask = torch.ones((1, position + 1), device=input_ids.device, dtype=torch.long)
        positions = torch.tensor([[position]], device=input_ids.device)
        before = int(cache.get_seq_length())
        output = target(
            token, position_ids=positions, attention_mask=mask,
            past_key_values=cache, use_cache=True, logits_to_keep=1,
            output_hidden_states=False,
        )
        after = int(cache.get_seq_length())
        next_token = int(sample(output.logits, 0.0)[0, -1].item())
        if output_index == 1:
            divergence_logits = output.logits[0, -1].detach().clone()
        steps.append({
            "consumed_output_index": output_index,
            "input_token_id": int(token.item()),
            "position_ids": [[int(value) for value in row] for row in positions.cpu().tolist()],
            "attention_mask": _mask_record(mask),
            "cache_length_before": before,
            "cache_length_after": after,
            "next_token_id": next_token,
        })
    synchronize(target.device)
    if divergence_logits is None:
        raise RuntimeError("sequential path did not capture divergence logits")
    return {
        "name": "sequential_one_token_greedy_fresh_cache",
        "generated_prefix_and_next": prefix,
        "same_prefix_token_ids": prefix[:2],
        "divergence_output_index": 2,
        "divergence": _topk(divergence_logits),
        "cache": cache,
        "prefill": {
            "input_ids": [[int(value) for value in row] for row in input_ids.cpu().tolist()],
            "position_ids": [[int(value) for value in row] for row in prefill_positions.cpu().tolist()],
            "attention_mask": _mask_record(prefill_mask),
            "cache_length_after": int(input_ids.shape[1]),
        },
        "steps": steps,
        "elapsed_ms": (time.perf_counter() - started) * 1000.0,
        "raw_logits": divergence_logits.cpu(),
    }


@torch.inference_mode()
def _full_prefix_path(
    target: Any, input_ids: torch.Tensor, prefix_ids: list[int]
) -> dict[str, Any]:
    prefix = torch.tensor([prefix_ids], device=input_ids.device, dtype=torch.long)
    full_ids = torch.cat([input_ids, prefix], dim=1)
    positions = torch.arange(full_ids.shape[1], device=input_ids.device).unsqueeze(0)
    mask = torch.ones_like(full_ids)
    synchronize(target.device)
    started = time.perf_counter()
    output = target(
        full_ids, position_ids=positions, attention_mask=mask,
        use_cache=False, logits_to_keep=1, output_hidden_states=False,
    )
    synchronize(target.device)
    logits = output.logits[0, -1].detach().clone()
    return {
        "name": "full_prefix_greedy_no_cache",
        "input_ids": [[int(value) for value in row] for row in full_ids.cpu().tolist()],
        "same_prefix_token_ids": prefix_ids,
        "position_ids": [[int(value) for value in row] for row in positions.cpu().tolist()],
        "attention_mask": _mask_record(mask),
        "cache": {"enabled": False, "length": None, "crop_boundary": None},
        "divergence_output_index": 2,
        "divergence": _topk(logits),
        "elapsed_ms": (time.perf_counter() - started) * 1000.0,
        "raw_logits": logits.cpu(),
    }


@torch.inference_mode()
def _one_shot_prefix_cache(
    target: Any, input_ids: torch.Tensor, prefix_ids: list[int]
) -> tuple[DynamicCache, dict[str, Any]]:
    prefix = torch.tensor([prefix_ids], device=input_ids.device, dtype=torch.long)
    full_ids = torch.cat([input_ids, prefix], dim=1)
    cache = DynamicCache()
    positions = torch.arange(full_ids.shape[1], device=input_ids.device).unsqueeze(0)
    mask = torch.ones_like(full_ids)
    output = target(
        full_ids, position_ids=positions, attention_mask=mask,
        past_key_values=cache, use_cache=True, logits_to_keep=1,
        output_hidden_states=False,
    )
    logits = output.logits[0, -1].detach().clone()
    return cache, {
        "name": "one_shot_full_prefix_fresh_cache",
        "cache_length": int(cache.get_seq_length()),
        "position_ids": [[int(value) for value in row] for row in positions.cpu().tolist()],
        "attention_mask": _mask_record(mask),
        "divergence": _topk(logits),
        "raw_logits": logits.cpu(),
    }


@torch.inference_mode()
def _draft_proposals(
    target: Any, drafter: Any, input_ids: torch.Tensor, block_size: int
) -> tuple[list[int], int, torch.Tensor]:
    prefill, _, _, _ = _prefill_target(target, input_ids, explicit_attention_mask=False)
    seed = int(sample(prefill.logits, 0.0)[0, -1].item())
    target_hidden = extract_context_feature(prefill.hidden_states, list(drafter.target_layer_ids))
    proposal_count = block_size - 1
    block_ids = torch.full(
        (1, block_size), int(drafter.mask_token_id),
        dtype=torch.long, device=input_ids.device,
    )
    block_ids[:, 0] = seed
    positions = torch.arange(0, input_ids.shape[1] + block_size, device=input_ids.device).unsqueeze(0)
    drafter_dtype = next(drafter.parameters()).dtype
    target_head_parameter = next(target.lm_head.parameters(), None)
    target_head_dtype = target_head_parameter.dtype if target_head_parameter is not None else drafter_dtype
    noise_embedding = target.model.embed_tokens(block_ids).to(dtype=drafter_dtype)
    draft_hidden = drafter(
        target_hidden=target_hidden.to(dtype=drafter_dtype),
        noise_embedding=noise_embedding,
        position_ids=positions,
        past_key_values=DynamicCache(),
        use_cache=True,
        is_causal=False,
    )
    draft_logits = target.lm_head(
        draft_hidden[:, 1 - block_size :, :].to(dtype=target_head_dtype)
    )
    proposals = [int(value) for value in sample(draft_logits, 0.0)[0, :proposal_count].cpu().tolist()]
    return proposals, seed, positions


@torch.inference_mode()
def _block_target_variant(
    target: Any,
    input_ids: torch.Tensor,
    seed: int,
    proposals: list[int],
    block_size: int,
    *,
    explicit_attention_mask: bool,
) -> dict[str, Any]:
    _, cache, prefill_mask, prefill_positions = _prefill_target(
        target, input_ids, explicit_attention_mask=False
    )
    prompt_length = int(input_ids.shape[1])
    start = int(cache.get_seq_length())
    block_ids = torch.tensor([[seed, *proposals]], device=input_ids.device, dtype=torch.long)
    positions = torch.arange(start, start + block_size, device=input_ids.device).unsqueeze(0)
    mask = (
        torch.ones((1, start + block_size), device=input_ids.device, dtype=torch.long)
        if explicit_attention_mask else None
    )
    before = int(cache.get_seq_length())
    kwargs = {
        "position_ids": positions, "past_key_values": cache,
        "use_cache": True, "output_hidden_states": True,
    }
    if mask is not None:
        kwargs["attention_mask"] = mask
    synchronize(target.device)
    started = time.perf_counter()
    output = target(block_ids, **kwargs)
    synchronize(target.device)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    posterior_ids = sample(output.logits, 0.0)[0]
    proposed_tensor = block_ids[0, 1:]
    accepted = int(accepted_prefix_tensor(proposed_tensor, posterior_ids[: len(proposals)]).item())
    correction = int(posterior_ids[accepted].item())
    production_crop_boundary = start + accepted + 1
    length_after_forward = int(cache.get_seq_length())
    divergence_logits = output.logits[0, 1].detach().clone()
    divergence_target_id = int(posterior_ids[1].item())
    cache.crop(prompt_length + 2)
    return {
        "name": "dflash_block_target_verification",
        "block_size": block_size,
        "variant": "explicit_attention_mask" if explicit_attention_mask else "production_attention_mask_none",
        "same_prefix_token_ids": [seed, proposals[0]],
        "input_ids": [[int(value) for value in row] for row in block_ids.cpu().tolist()],
        "proposal_ids": proposals,
        "position_ids": [[int(value) for value in row] for row in positions.cpu().tolist()],
        "attention_mask": _mask_record(mask),
        "prefill_position_ids": [[int(value) for value in row] for row in prefill_positions.cpu().tolist()],
        "prefill_attention_mask": _mask_record(prefill_mask),
        "cache_length_before": before,
        "cache_length_after_forward": length_after_forward,
        "accepted_count": accepted,
        "correction_token_id": correction,
        "production_cache_crop_boundary": production_crop_boundary,
        "same_prefix_semantic_crop_boundary": prompt_length + 2,
        "cache_length_after_same_prefix_crop": int(cache.get_seq_length()),
        "posterior_token_ids": [int(value) for value in posterior_ids.cpu().tolist()],
        "divergence_output_index": 2,
        "divergence_block_logit_index": 1,
        "divergence_target_token_id": divergence_target_id,
        "divergence": _topk(divergence_logits),
        "elapsed_ms": elapsed_ms,
        "cache": cache,
        "raw_logits": divergence_logits.cpu(),
    }


def _strip_private(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key not in {"cache", "raw_logits"}}


def _classify(
    sequential: dict[str, Any],
    full_prefix: dict[str, Any],
    one_shot: dict[str, Any],
    shapes: list[dict[str, Any]],
    prompt_cache_semantics: dict[str, Any],
) -> dict[str, Any]:
    sequential_top1 = sequential["divergence"]["top1_token_id"]
    full_top1 = full_prefix["divergence"]["top1_token_id"]
    one_shot_top1 = one_shot["divergence"]["top1_token_id"]
    production_top1 = {str(item["block_size"]): item["production"]["divergence"]["top1_token_id"] for item in shapes}
    explicit_top1 = {str(item["block_size"]): item["explicit_mask"]["divergence"]["top1_token_id"] for item in shapes}
    positions_valid = all(
        item["production"]["position_ids"][0]
        == list(range(item["production"]["cache_length_before"], item["production"]["cache_length_before"] + item["block_size"]))
        for item in shapes
    )
    crop_valid = all(
        item["production"]["production_cache_crop_boundary"]
        == item["production"]["cache_length_before"] + item["production"]["accepted_count"] + 1
        for item in shapes
    )
    attention_changes_top1 = any(production_top1[key] != explicit_top1[key] for key in production_top1)
    block_shape_changes_top1 = len(set(production_top1.values())) > 1
    block_differs_from_sequential = any(value != sequential_top1 for value in production_top1.values())
    semantic_cache_diff = any(not item["cache_vs_sequential_same_prefix"]["all_exact_equal"] for item in shapes)
    if not positions_valid:
        primary = "indexing_or_position_ids"
    elif not crop_valid:
        primary = "cache_crop_boundary"
    elif attention_changes_top1:
        primary = "attention_mask_semantics"
    elif block_differs_from_sequential and (block_shape_changes_top1 or semantic_cache_diff):
        primary = "block_shape_numerical_drift_on_active_awq_path"
    elif not prompt_cache_semantics["allclose_atol_1e_5_rtol_1e_5"]:
        primary = "cache_content_semantics"
    else:
        primary = "other_or_inconclusive"
    return {
        "primary_classification": primary,
        "active_quantization": "AWQ",
        "sequential_top1_token_id": sequential_top1,
        "full_prefix_no_cache_top1_token_id": full_top1,
        "one_shot_full_prefix_cache_top1_token_id": one_shot_top1,
        "production_block_top1_by_shape": production_top1,
        "explicit_mask_block_top1_by_shape": explicit_top1,
        "indexing_position_ids_pass": positions_valid,
        "cache_crop_boundary_pass": crop_valid,
        "attention_mask_changes_top1": attention_changes_top1,
        "block_shape_changes_top1": block_shape_changes_top1,
        "block_path_differs_from_sequential": block_differs_from_sequential,
        "semantic_cache_diff_observed": semantic_cache_diff,
        "prompt_cache_semantics_allclose": prompt_cache_semantics["allclose_atol_1e_5_rtol_1e_5"],
        "dflash_core_patch_applied": False,
        "dataset_smoke_blocked": primary != "other_or_inconclusive",
    }


def _blocker(report: dict[str, Any]) -> str:
    root = report["classification"]
    return f"""# REC-3 D-Flash verifier diagnostic blocker

## Decision

Dataset smoke remains blocked. Using the same active AWQ target and identical compressed
`rec3_mock_02` prefix, the three target-forward paths do not select the same token at output index 2.

Primary classification: `{root['primary_classification']}`.

## Locked contract

- Quantization: AWQ (not NF4)
- SDPA kernel: math
- AWQ split K iterations: 1
- Fixture/prompt/compression output: unchanged and hash-locked
- D-Flash core patch applied: false

## Findings

- Sequential one-token fresh-cache top-1: `{root['sequential_top1_token_id']}`
- Full-prefix no-cache top-1: `{root['full_prefix_no_cache_top1_token_id']}`
- One-shot full-prefix cache top-1: `{root['one_shot_full_prefix_cache_top1_token_id']}`
- Production block top-1 by shape: `{root['production_block_top1_by_shape']}`
- Explicit-mask block top-1 by shape: `{root['explicit_mask_block_top1_by_shape']}`
- Position/index validation: `{root['indexing_position_ids_pass']}`
- Cache crop validation: `{root['cache_crop_boundary_pass']}`
- Attention mask changes top-1: `{root['attention_mask_changes_top1']}`
- Semantic cache difference observed: `{root['semantic_cache_diff_observed']}`

The review pack contains per-layer key/value cache comparisons and raw full-vocabulary logits.
No D-Flash core change is made in this diagnostic batch.
"""


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("REC-3 verifier diagnostic requires CUDA")
    compressed_prompt, input_contract = _locked_prompt()
    config = REC3._mock_config(load_config(ROOT / "config.yml"))
    determinism = configure_determinism(
        seed=int(config.require("runtime.seed")), deterministic=True,
        allow_tf32=bool(config.require("runtime.allow_tf32")),
        matmul_precision=str(config.require("runtime.matmul_precision")),
        sdpa_kernel=str(config.require("runtime.sdpa_kernel")),
    )
    engine = RuntimeEngine(config, condition="dflash")
    raw_logits: dict[str, torch.Tensor] = {}
    try:
        input_ids = engine.encode_prompt(compressed_prompt)
        target = engine.target
        drafter = engine.drafter
        metadata = _target_metadata(engine, config)

        sequential = _sequential_path(target, input_ids)
        prefix_ids = list(sequential["same_prefix_token_ids"])
        full_prefix = _full_prefix_path(target, input_ids, prefix_ids)
        one_shot_cache, one_shot = _one_shot_prefix_cache(target, input_ids, prefix_ids)
        sequential_cache = sequential["cache"]
        sequential_vs_one_shot = _cache_semantics(
            sequential_cache, one_shot_cache,
            label="sequential fresh cache vs one-shot full-prefix fresh cache at identical prefix",
        )

        # Isolate prompt-cache semantics before any generated token is appended.
        _, baseline_prompt_cache, _, _ = _prefill_target(target, input_ids, explicit_attention_mask=True)
        _, dflash_prompt_cache, _, _ = _prefill_target(target, input_ids, explicit_attention_mask=False)
        prompt_cache_semantics = _cache_semantics(
            baseline_prompt_cache, dflash_prompt_cache,
            label="explicit-ones baseline prefill vs mask-none D-Flash prefill",
        )

        raw_logits["sequential_one_token"] = sequential["raw_logits"]
        raw_logits["full_prefix_no_cache"] = full_prefix["raw_logits"]
        raw_logits["one_shot_full_prefix_cache"] = one_shot["raw_logits"]
        shapes = []
        for block_size in BLOCK_SIZES:
            proposals, seed, drafter_positions = _draft_proposals(
                target, drafter, input_ids, block_size
            )
            if seed != prefix_ids[0] or proposals[0] != prefix_ids[1]:
                raise RuntimeError(
                    f"block size {block_size} does not share locked first-divergence prefix: "
                    f"seed={seed}, first_proposal={proposals[0]}, prefix={prefix_ids}"
                )
            production = _block_target_variant(
                target, input_ids, seed, proposals, block_size,
                explicit_attention_mask=False,
            )
            explicit = _block_target_variant(
                target, input_ids, seed, proposals, block_size,
                explicit_attention_mask=True,
            )
            cache_vs_sequential = _cache_semantics(
                sequential_cache, production["cache"],
                label=f"sequential prefix cache vs production block-{block_size} cropped to same prefix",
            )
            raw_logits[f"block_{block_size}_production_mask_none"] = production["raw_logits"]
            raw_logits[f"block_{block_size}_explicit_attention_mask"] = explicit["raw_logits"]
            shapes.append({
                "block_size": block_size,
                "drafter_position_ids": [[int(value) for value in row] for row in drafter_positions.cpu().tolist()],
                "production": _strip_private(production),
                "explicit_mask": _strip_private(explicit),
                "cache_vs_sequential_same_prefix": cache_vs_sequential,
            })

        classification = _classify(
            sequential, full_prefix, one_shot, shapes, prompt_cache_semantics
        )
        report = {
            "diagnostic_version": "ccdf.rec3-dflash-verifier-diagnostic.v1",
            "environment": REC3._gpu_environment(),
            "input_contract": {
                **input_contract,
                "rendered_chat_input_ids": [[int(value) for value in row] for row in input_ids.cpu().tolist()],
                "rendered_chat_input_token_count": int(input_ids.shape[1]),
                "rendered_chat_input_ids_sha256": REC3._token_ids_sha256(
                    [int(value) for value in input_ids.cpu().reshape(-1).tolist()]
                ),
                "system_prompt": REC3.NEUTRAL_SYSTEM_PROMPT,
                "system_prompt_sha256": _sha256_text(REC3.NEUTRAL_SYSTEM_PROMPT),
            },
            "locked_runtime": {
                "fixture_changed": False, "prompt_changed": False,
                "compression_output_changed": False, "model_changed": False,
                "sdpa_kernel": config.require("runtime.sdpa_kernel"),
                "awq_split_k_iters": config.require("runtime.awq_split_k_iters"),
                "temperature": 0.0, "block_sizes": list(BLOCK_SIZES),
                "determinism": determinism,
            },
            "model_backend": metadata,
            "paths": {
                "sequential_one_token": _strip_private(sequential),
                "full_prefix_no_cache": _strip_private(full_prefix),
                "one_shot_full_prefix_cache": _strip_private(one_shot),
                "block_target_verification": shapes,
            },
            "cache_semantics": {
                "sequential_vs_one_shot_full_prefix": sequential_vs_one_shot,
                "baseline_mask_ones_vs_dflash_mask_none_prompt_prefill": prompt_cache_semantics,
            },
            "classification": classification,
            "raw_logits": {
                "path": str(RAW_LOGITS_PATH.relative_to(ROOT)),
                "format": "torch.save mapping of path label to full float32 vocabulary logit tensor",
                "keys": sorted(raw_logits),
            },
        }
    finally:
        engine.close()

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    torch.save({key: tensor.to(dtype=torch.float32, device="cpu") for key, tensor in raw_logits.items()}, RAW_LOGITS_PATH)
    report["raw_logits"]["sha256"] = _sha256_file(RAW_LOGITS_PATH)
    report["raw_logits"]["bytes"] = RAW_LOGITS_PATH.stat().st_size
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    BLOCKER_PATH.write_text(_blocker(report), encoding="utf-8")
    print(json.dumps({
        "classification": report["classification"],
        "report": str(REPORT_PATH),
        "raw_logits": str(RAW_LOGITS_PATH),
    }, sort_keys=True))
    if report["classification"]["primary_classification"] == "other_or_inconclusive":
        raise SystemExit("REC-3 verifier diagnostic remained inconclusive")


if __name__ == "__main__":
    main()
