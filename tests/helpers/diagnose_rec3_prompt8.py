#!/usr/bin/env python3
"""Emit the complete target-forward contract for the REC-3 mock-08 mismatch."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

import torch
import transformers
from transformers.models.qwen3 import modeling_qwen3

from ccdf.config import load_config
from ccdf.runtime.engine import RuntimeEngine


def _row(path: Path, prompt_id: str) -> dict[str, Any]:
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["phase"] == "measured" and row["prompt_id"] == prompt_id and row["repetition"] == 0:
            return row
    raise RuntimeError(f"{prompt_id} repetition 0 is missing from {path}")


def _sha256_values(values: list[int]) -> str:
    encoded = json.dumps(values, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _tensor_summary(tensor: torch.Tensor | None, *, values_limit: int = 512) -> dict[str, Any] | None:
    if tensor is None:
        return None
    cpu = tensor.detach().cpu().contiguous()
    raw = cpu.view(torch.uint8).numpy().tobytes()
    result: dict[str, Any] = {
        "shape": list(tensor.shape),
        "dtype": str(tensor.dtype),
        "device": str(tensor.device),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "numel": tensor.numel(),
    }
    if tensor.numel() <= values_limit:
        result["values"] = cpu.reshape(-1).tolist()
    return result


def _mask_summary(mask: torch.Tensor | None) -> dict[str, Any] | None:
    result = _tensor_summary(mask, values_limit=256)
    if mask is None or result is None:
        return result
    flat = mask.detach().float()
    result["finite_count"] = int(torch.isfinite(flat).sum().item())
    result["zero_count"] = int((flat == 0).sum().item())
    if flat.numel() and flat.ndim >= 2:
        rows = flat.reshape(-1, flat.shape[-2], flat.shape[-1])[0]
        allowed = []
        for row in rows:
            allowed_values = row if mask.dtype == torch.bool else row == 0
            indices = torch.nonzero(allowed_values, as_tuple=False).flatten()
            allowed.append(
                {
                    "count": int(indices.numel()),
                    "first": int(indices[0].item()) if indices.numel() else None,
                    "last": int(indices[-1].item()) if indices.numel() else None,
                }
            )
        result["allowed_keys_by_query"] = allowed
    return result


def _cache_summary(cache: Any) -> dict[str, Any] | None:
    if cache is None:
        return None
    layers = getattr(cache, "layers", [])
    layer_rows = []
    for index, layer in enumerate(layers):
        keys = getattr(layer, "keys", None)
        values = getattr(layer, "values", None)
        if keys is None and hasattr(cache, "key_cache") and index < len(cache.key_cache):
            keys = cache.key_cache[index]
            values = cache.value_cache[index]
        layer_rows.append(
            {
                "layer": index,
                "keys": _tensor_summary(keys, values_limit=0),
                "values": _tensor_summary(values, values_limit=0),
            }
        )
    return {
        "type": type(cache).__name__,
        "sequence_length": int(cache.get_seq_length()),
        "layer_count": len(layer_rows),
        "layers": layer_rows,
    }


def _top(logits: torch.Tensor, count: int = 10) -> dict[str, Any]:
    float_logits = logits.float()
    values, indices = torch.topk(float_logits, count)
    candidates = [
        {"token_id": int(token), "logit": float(value)}
        for value, token in zip(values.detach().cpu(), indices.detach().cpu())
    ]
    argmax_token = int(torch.argmax(float_logits).item())
    maximum = float(float_logits[argmax_token].item())
    tied_tokens = torch.nonzero(float_logits == maximum, as_tuple=False).flatten().detach().cpu().tolist()
    return {
        "winner_token_id": argmax_token,
        "winner_logit": maximum,
        "winner_margin": candidates[0]["logit"] - candidates[1]["logit"],
        "exact_max_tied_token_ids": tied_tokens,
        "candidates": candidates,
    }


class _TargetForwardTracer(AbstractContextManager["_TargetForwardTracer"]):
    def __init__(self, model: Any) -> None:
        self.model = model
        self.calls: list[dict[str, Any]] = []
        self._active: dict[str, Any] | None = None
        self._original_forward = model.forward
        self._original_create_causal_mask = modeling_qwen3.create_causal_mask

    def __enter__(self) -> "_TargetForwardTracer":
        def traced_mask(*args: Any, **kwargs: Any) -> Any:
            mask = self._original_create_causal_mask(*args, **kwargs)
            if self._active is not None:
                self._active["derived_cache_position"] = _tensor_summary(kwargs.get("cache_position"))
                self._active["effective_causal_mask"] = _mask_summary(mask)
            return mask

        def traced_forward(*args: Any, **kwargs: Any) -> Any:
            input_ids = kwargs.get("input_ids", args[0] if args else None)
            cache = kwargs.get("past_key_values")
            record: dict[str, Any] = {
                "call_index": len(self.calls),
                "input_ids": _tensor_summary(input_ids),
                "position_ids": _tensor_summary(kwargs.get("position_ids")),
                "caller_attention_mask": _tensor_summary(kwargs.get("attention_mask")),
                "caller_cache_position": _tensor_summary(kwargs.get("cache_position")),
                "logits_to_keep": kwargs.get("logits_to_keep", 0),
                "use_cache": kwargs.get("use_cache"),
                "output_hidden_states": kwargs.get("output_hidden_states"),
                "cache_before": _cache_summary(cache),
            }
            self._active = record
            try:
                output = self._original_forward(*args, **kwargs)
            finally:
                self._active = None
            logits = output.logits.detach()
            record["logits"] = {
                "shape": list(logits.shape),
                "dtype": str(logits.dtype),
                "device": str(logits.device),
                "positions": [_top(logits[0, index]) for index in range(logits.shape[1])],
            }
            hidden_states = getattr(output, "hidden_states", None)
            if hidden_states:
                final_hidden = hidden_states[-1]
                record["rowwise_lm_head_logits"] = [
                    _top(self.model.lm_head(final_hidden[:, index : index + 1])[0, 0])
                    for index in range(final_hidden.shape[1])
                ]
            record["cache_after"] = _cache_summary(cache)
            self.calls.append(record)
            return output

        self.model.forward = traced_forward
        modeling_qwen3.create_causal_mask = traced_mask
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.model.forward = self._original_forward
        modeling_qwen3.create_causal_mask = self._original_create_causal_mask


@torch.inference_mode()
def _run_condition(config_path: str, condition: str, prompt: str) -> tuple[Any, list[dict[str, Any]]]:
    config = load_config(config_path)
    if condition == "dflash":
        config.data["optimization"]["full_structural_audit"] = True
    engine = RuntimeEngine(config, condition=condition)
    try:
        target = engine.model if condition == "baseline" else engine.target
        with _TargetForwardTracer(target) as tracer:
            result = engine.generate(prompt)
        return result, tracer.calls
    finally:
        engine.close()


def _capture_payload(config_path: str, condition: str, row: dict[str, Any]) -> dict[str, Any]:
    result, calls = _run_condition(config_path, condition, row["prompt"])
    return {
        "condition": condition,
        "generated_token_ids": result.generated_token_ids,
        "stop_reason": result.stop_reason,
        "structural_audit": result.dflash.structural_audit if result.dflash is not None else None,
        "calls": calls,
    }


def _selected_mask_row(call: dict[str, Any], offset: int) -> dict[str, Any] | None:
    mask = call.get("effective_causal_mask")
    if not mask:
        return None
    rows = mask.get("allowed_keys_by_query", [])
    return rows[offset] if offset < len(rows) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yml")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--dflash", type=Path, required=True)
    parser.add_argument("--prompt-id", default="mock-08")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--capture-condition", choices=("baseline", "dflash"), help=argparse.SUPPRESS)
    args = parser.parse_args()

    baseline_row = _row(args.baseline, args.prompt_id)
    dflash_row = _row(args.dflash, args.prompt_id)
    if args.capture_condition:
        row = baseline_row if args.capture_condition == "baseline" else dflash_row
        capture = _capture_payload(args.config, args.capture_condition, row)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(capture, indent=2, sort_keys=True), encoding="utf-8")
        return 0

    baseline_ids = [int(value) for value in baseline_row["generated_token_ids"]]
    dflash_ids = [int(value) for value in dflash_row["generated_token_ids"]]
    mismatch = next(
        index for index, (left, right) in enumerate(zip(baseline_ids, dflash_ids)) if left != right
    )

    captures: dict[str, dict[str, Any]] = {}
    for condition in ("baseline", "dflash"):
        capture_path = args.output.with_name(f"{args.output.stem}-{condition}-capture.json")
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--config",
            args.config,
            "--baseline",
            str(args.baseline),
            "--dflash",
            str(args.dflash),
            "--prompt-id",
            args.prompt_id,
            "--output",
            str(capture_path),
            "--capture-condition",
            condition,
        ]
        subprocess.run(command, check=True)
        captures[condition] = json.loads(capture_path.read_text(encoding="utf-8"))

    baseline_capture = captures["baseline"]
    dflash_capture = captures["dflash"]
    baseline_calls = baseline_capture["calls"]
    dflash_calls = dflash_capture["calls"]
    if baseline_capture["generated_token_ids"] != baseline_ids:
        raise RuntimeError("instrumented Baseline-AR request did not reproduce the canonical raw row")
    if dflash_capture["generated_token_ids"] != dflash_ids:
        raise RuntimeError("instrumented DFlash request did not reproduce the canonical raw row")

    audits = dflash_capture["structural_audit"]
    generated_cursor = 1
    selected_audit: dict[str, Any] | None = None
    selected_offset = -1
    for audit in audits:
        advance = int(audit["emitted_advance"])
        if generated_cursor <= mismatch < generated_cursor + advance:
            selected_audit = audit
            selected_offset = mismatch - generated_cursor
            break
        generated_cursor += advance
    if selected_audit is None:
        raise RuntimeError("failed to locate mismatch in full structural audit")

    block_index = int(selected_audit["block_index"])
    baseline_call = baseline_calls[mismatch]
    dflash_call = dflash_calls[block_index + 1]
    prompt_ids = baseline_calls[0]["input_ids"]["values"]
    dflash_prompt_ids = dflash_calls[0]["input_ids"]["values"]
    common_prefix = baseline_ids[:mismatch]
    baseline_logical_context = prompt_ids + common_prefix
    dflash_logical_context = dflash_prompt_ids + dflash_ids[:mismatch]

    baseline_position = baseline_call["position_ids"]["values"][-1]
    dflash_positions = dflash_call["position_ids"]["values"]
    dflash_position = dflash_positions[selected_offset]
    baseline_cache_position = baseline_call["derived_cache_position"]["values"][-1]
    dflash_cache_positions = dflash_call["derived_cache_position"]["values"]
    dflash_cache_position = dflash_cache_positions[selected_offset]

    payload = {
        "schema": "ccdf.rec2.mock08.execution-contract.v1",
        "software": {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "cuda": torch.version.cuda,
        },
        "raw_reproduction": {
            "baseline": True,
            "dflash": True,
            "baseline_output_count": len(baseline_capture["generated_token_ids"]),
            "dflash_output_count": len(dflash_capture["generated_token_ids"]),
        },
        "mismatch": {
            "generated_index": mismatch,
            "baseline_token_id": baseline_ids[mismatch],
            "dflash_token_id": dflash_ids[mismatch],
            "prefix_ids": common_prefix,
            "prefix_sha256": _sha256_values(common_prefix),
            "prefix_equal": common_prefix == dflash_ids[:mismatch],
        },
        "prompt": {
            "input_ids": prompt_ids,
            "input_length": len(prompt_ids),
            "input_ids_sha256": _sha256_values(prompt_ids),
            "conditions_equal": prompt_ids == dflash_prompt_ids,
        },
        "logical_context_for_mismatch_prediction": {
            "baseline_length": len(baseline_logical_context),
            "dflash_length": len(dflash_logical_context),
            "baseline_sha256": _sha256_values(baseline_logical_context),
            "dflash_sha256": _sha256_values(dflash_logical_context),
            "conditions_equal": baseline_logical_context == dflash_logical_context,
        },
        "selection": {
            "dflash_block_index": block_index,
            "dflash_generated_cursor": generated_cursor,
            "dflash_selected_logit_offset": selected_offset,
            "baseline_selected_logit_offset": 0,
            "baseline_position_id": baseline_position,
            "dflash_position_id": dflash_position,
            "positions_equal": baseline_position == dflash_position,
            "baseline_cache_position": baseline_cache_position,
            "dflash_cache_position": dflash_cache_position,
            "cache_positions_equal": baseline_cache_position == dflash_cache_position,
            "baseline_effective_mask_row": _selected_mask_row(baseline_call, 0),
            "dflash_effective_mask_row": _selected_mask_row(dflash_call, selected_offset),
            "baseline_top_logits": baseline_call["logits"]["positions"][0],
            "dflash_top_logits": dflash_call["logits"]["positions"][selected_offset],
        },
        "baseline_forward": baseline_call,
        "dflash_forward": dflash_call,
        "dflash_full_audit_block": selected_audit,
        "stopping": {
            "stop_token_ids": baseline_row["contract"]["stop_token_ids"],
            "max_new_tokens": baseline_row["contract"]["max_new_tokens"],
            "baseline_stop_reason": baseline_capture["stop_reason"],
            "dflash_stop_reason": dflash_capture["stop_reason"],
            "mismatch_before_stop": mismatch < min(
                len(baseline_capture["generated_token_ids"]),
                len(dflash_capture["generated_token_ids"]),
            ),
        },
        "proof": {
            "same_prompt_input_ids": prompt_ids == dflash_prompt_ids,
            "same_generated_prefix": common_prefix == dflash_ids[:mismatch],
            "same_logical_context": baseline_logical_context == dflash_logical_context,
            "same_selected_position": baseline_position == dflash_position,
            "same_selected_cache_position": baseline_cache_position == dflash_cache_position,
            "baseline_cache_length_before": baseline_call["cache_before"]["sequence_length"],
            "dflash_cache_length_before": dflash_call["cache_before"]["sequence_length"],
            "baseline_selected_token": baseline_call["logits"]["positions"][0]["winner_token_id"],
            "dflash_selected_token": dflash_call["logits"]["positions"][selected_offset]["winner_token_id"],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
