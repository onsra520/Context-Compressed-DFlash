"""Config-driven orchestration for the four-condition protocol."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from typing import Any, Mapping

import torch

from ..compression import CompressionConfig, LLMLinguaCompressor
from ..config import Config
from ..runtime.device import GIB, synchronize
from ..runtime.engine import RuntimeEngine
from ..validation.environment import validate_environment
from ..benchmark.aggregation import (
    annotate_total_input_reduction,
    condition_metrics,
    metric_validity,
    render_final_report,
    weighted_dflash_metrics,
)
from ..benchmark.metrics import (
    output_quality_record,
    pair_record,
    sha256_bytes,
    sha256_text,
    token_ids_sha256,
)
from .conditions import (
    ARTIFACT_FILENAMES,
    PROTOCOL_VERSION,
    build_fixtures,
    input_quality_record,
    json_fixture,
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _cuda_memory(label: str) -> dict[str, Any]:
    synchronize()
    if not torch.cuda.is_available():
        return {"label": label, "cuda_available": False}
    return {
        "label": label,
        "cuda_available": True,
        "allocated_bytes": int(torch.cuda.memory_allocated()),
        "reserved_bytes": int(torch.cuda.memory_reserved()),
        "max_allocated_bytes": int(torch.cuda.max_memory_allocated()),
        "max_reserved_bytes": int(torch.cuda.max_memory_reserved()),
    }


def _capture_chat_template_input(engine: RuntimeEngine, prompt: str) -> dict[str, Any]:
    token_tensor = engine.encode_prompt(prompt)
    synchronize()
    token_ids = [int(value) for value in token_tensor.detach().cpu().reshape(-1).tolist()]
    del token_tensor
    return {
        "token_ids": token_ids,
        "token_count": len(token_ids),
        "token_ids_sha256": token_ids_sha256(token_ids),
        "tokenizer_name_or_path": str(getattr(engine.tokenizer, "name_or_path", "")),
        "hash_encoding": "sha256(canonical JSON array of ordered integer token IDs)",
    }


def request_record(
    *,
    condition: str,
    prompt_kind: str,
    prompt: str,
    compression: dict[str, Any],
    engine: RuntimeEngine,
    lifecycle: list[dict[str, Any]],
    max_new_tokens: int,
    temperature: float,
    dataset: str,
    measured: bool,
) -> dict[str, Any]:
    try:
        chat_input = _capture_chat_template_input(engine, prompt)
        synchronize()
        start = time.perf_counter()
        result = engine.generate(
            prompt,
            dataset=dataset,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
        ).to_dict()
        synchronize()
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        timing = result["timing"]
        memory = result["memory"]
        compression_ms = (
            float(compression["compression_latency_ms"])
            if prompt_kind == "compressed" else 0.0
        )
        request_peak = {
            "peak_allocated_bytes": memory["peak_allocated_bytes"],
            "peak_reserved_bytes": memory["peak_reserved_bytes"],
            "allocated_before_bytes": memory["allocated_before_bytes"],
            "reserved_before_bytes": memory["reserved_before_bytes"],
            "allocated_after_bytes": memory["allocated_after_bytes"],
            "reserved_after_bytes": memory["reserved_after_bytes"],
        }
        compression_peak = ({
            "peak_allocated_bytes": compression["peak_allocated_vram_bytes"],
            "peak_reserved_bytes": compression["peak_reserved_vram_bytes"],
        } if prompt_kind == "compressed" else None)
        full_request_peak = {
            "peak_allocated_bytes": max(
                request_peak["peak_allocated_bytes"],
                compression_peak["peak_allocated_bytes"] if compression_peak else 0,
            ),
            "peak_reserved_bytes": max(
                request_peak["peak_reserved_bytes"],
                compression_peak["peak_reserved_bytes"] if compression_peak else 0,
            ),
            "measurement_scope": (
                "compression stage plus production generation-request stage; "
                "stages use separate GPU residency"
            ),
        }
        context_metrics = ({
            "context_tokenizer": compression["context_tokenizer"],
            "context_original_tokens": compression["original_tokens"],
            "context_compressed_tokens": compression["compressed_tokens"],
            "context_reduction_rate": compression["reduction_rate"],
        } if prompt_kind == "compressed" else {
            "context_tokenizer": None,
            "context_original_tokens": None,
            "context_compressed_tokens": None,
            "context_reduction_rate": None,
        })
        result["protocol_metrics"] = {
            "measured": measured,
            "raw_rendered_prompt_sha256": sha256_text(prompt),
            "chat_template_input": chat_input,
            **context_metrics,
            "total_input_token_reduction": None,
            "total_input_token_reduction_scope": (
                "Qwen chat-template input tokens; populated only for compressed conditions"
            ),
            "compression_latency_ms": compression_ms,
            "prefill_latency_ms": timing["target_prefill_ms"],
            "draft_prefill_latency_ms": timing["draft_prefill_ms"],
            "decode_latency_ms": timing["decode_total_ms"],
            "generation_latency_ms": timing["generation_total_ms"],
            "stage_sum_warm_e2e_ms": compression_ms + timing["warm_request_ms"],
            "stage_sum_warm_e2e_scope": (
                "separately synchronized compression and production warm-request stages; "
                "excludes model load/unload and protocol warmup"
            ),
            "request_wall_clock_ms": elapsed_ms,
            "output_tokens": result["output_tokens"],
            "decode_tok_s": result["metrics"]["decode_tok_s"],
            "cap_hit": (
                result["output_tokens"] >= max_new_tokens
                or result["stop_reason"] == "max_new_tokens"
            ),
            "stage_vram": {"compression": compression_peak, "generation_request": request_peak},
            "generation_request_peak_vram": request_peak,
            "full_request_peak_vram": full_request_peak,
        }
        lifecycle.append({
            "event": "request_complete",
            "condition": condition,
            "prompt_kind": prompt_kind,
            "measured": measured,
            "memory": _cuda_memory(f"after_{condition}_{prompt_kind}"),
        })
        return {
            "success": True,
            "condition": condition,
            "prompt_kind": prompt_kind,
            "measured": measured,
            "result": result,
        }
    except Exception as exc:
        is_oom = "out of memory" in str(exc).lower()
        lifecycle.append({
            "event": "request_error",
            "condition": condition,
            "prompt_kind": prompt_kind,
            "measured": measured,
            "oom": is_oom,
            "error": f"{type(exc).__name__}: {exc}",
            "memory": _cuda_memory("request_error"),
        })
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        return {
            "success": False,
            "condition": condition,
            "prompt_kind": prompt_kind,
            "measured": measured,
            "oom": is_oom,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _run_condition(
    *,
    condition_spec: Mapping[str, Any],
    prepared: list[dict[str, Any]],
    config: Config,
    lifecycle: list[dict[str, Any]],
    dataset: str,
) -> dict[str, Any]:
    condition = str(condition_spec["name"])
    prompt_kind = str(condition_spec["prompt_kind"])
    workload_start = time.perf_counter()
    lifecycle.append({
        "event": "before_load", "condition": condition,
        "memory": _cuda_memory(f"before_{condition}_load"),
    })
    engine = RuntimeEngine(config, condition=str(condition_spec["runtime_condition"]))
    lifecycle.append({
        "event": "after_load", "condition": condition,
        "memory": _cuda_memory(f"after_{condition}_load"),
    })
    try:
        prompt_key = f"{prompt_kind}_prompt"
        warmup_result = request_record(
            condition=condition,
            prompt_kind=prompt_kind,
            prompt=prepared[0][prompt_key],
            compression=prepared[0]["compression"],
            engine=engine,
            lifecycle=lifecycle,
            max_new_tokens=int(config.require("runtime.max_new_tokens")),
            temperature=float(config.require("runtime.temperature")),
            dataset=dataset,
            measured=False,
        )
        rows = {}
        for item in prepared:
            rows[item["prompt_id"]] = request_record(
                condition=condition,
                prompt_kind=prompt_kind,
                prompt=item[prompt_key],
                compression=item["compression"],
                engine=engine,
                lifecycle=lifecycle,
                max_new_tokens=int(config.require("runtime.max_new_tokens")),
                temperature=float(config.require("runtime.temperature")),
                dataset=dataset,
                measured=True,
            )
        return {"rows": rows, "warmup": warmup_result}
    finally:
        engine.close()
        lifecycle.append({
            "event": "after_close", "condition": condition,
            "memory": _cuda_memory(f"after_{condition}_close"),
        })
        elapsed_ms = (time.perf_counter() - workload_start) * 1000.0
        lifecycle.append({
            "event": "condition_lifecycle_complete",
            "condition": condition,
            "workload_wall_clock_ms": elapsed_ms,
            "lifecycle_amortized_ms_per_measured_request": elapsed_ms / len(prepared),
            "scope": (
                "engine load, one warmup, measured fixture requests, and engine close"
            ),
        })


def _rate_gate(count: int, total: int, required_rate: float) -> bool:
    return total > 0 and (count / total) >= required_rate


def run_active_profile(source_config: Config) -> dict[str, Any]:
    profile = source_config.resolve_active_protocol_profile()
    config = profile.config
    residency = {
        "compressor_stage": str(config.require("memory.compressor_residency_mode")),
        "generation_stage": str(config.require("memory.generation_residency_mode")),
    }
    if set(residency.values()) != {"staged"}:
        raise RuntimeError(
            "four-condition orchestration requires staged compressor/generation residency"
        )
    environment = validate_environment(config)
    if not torch.cuda.is_available():
        raise RuntimeError("active protocol profile requires configured CUDA runtime")
    artifact_root = profile.path_for("artifact_directory")
    artifact_root.mkdir(parents=True, exist_ok=True)
    paths = {key: artifact_root / filename for key, filename in ARTIFACT_FILENAMES.items()}
    fixtures = build_fixtures(profile)
    _write_json(paths["fixtures"], [json_fixture(item) for item in fixtures])

    compression_settings = profile.require("compression")
    compression_config = CompressionConfig(
        keep_rate=float(compression_settings["keep_rate"]),
        min_context_tokens=int(compression_settings["min_context_tokens"]),
        chunk_max_words=int(compression_settings["chunk_max_words"]),
    )
    workload_start = time.perf_counter()
    lifecycle: list[dict[str, Any]] = [{"event": "start", "memory": _cuda_memory("start")}]
    compressor = LLMLinguaCompressor(
        config.path_for("models.compressor.local_path"),
        device=str(config.require("models.compressor.device")),
        local_files_only=bool(config.require("runtime.local_files_only")),
        reserved_vram_budget_gib=float(config.require("models.compressor.reserved_budget_gib")),
    )
    compressor_contract = dict(compressor.model_contract)
    compressor_device_audit = dict(compressor.device_audit)
    lifecycle.append({"event": "compressor_loaded", "memory": _cuda_memory("compressor_loaded")})
    prepared: list[dict[str, Any]] = []
    try:
        for item in fixtures:
            protocol = item["protocol"]
            synchronize()
            compression = compressor.compress(protocol, compression_config)
            synchronize()
            compressed_prompt = protocol.render(compression.compressed_context)
            original_prompt = protocol.render(protocol.context)
            input_quality = input_quality_record(
                item, compression.compressed_context, original_prompt, compressed_prompt
            )
            prepared.append({
                **json_fixture(item),
                "original_prompt": original_prompt,
                "compressed_prompt": compressed_prompt,
                "original_prompt_sha256": sha256_text(original_prompt),
                "compressed_prompt_sha256": sha256_text(compressed_prompt),
                "compression": {
                    "context_tokenizer": str(
                        getattr(compressor.tokenizer, "name_or_path", compressor.model_path)
                    ),
                    "original_tokens": compression.original_tokens,
                    "compressed_tokens": compression.compressed_tokens,
                    "reduction_rate": compression.reduction_rate,
                    "compression_latency_ms": compression.compression_latency_ms,
                    "peak_allocated_vram_bytes": compression.peak_allocated_vram_bytes,
                    "peak_reserved_vram_bytes": compression.peak_reserved_vram_bytes,
                    "reserved_vram_budget_bytes": compression.reserved_vram_budget_bytes,
                    "reserved_vram_budget_pass": compression.reserved_vram_budget_pass,
                    "chunk_count": compression.chunk_count,
                    "input_word_count": compression.input_word_count,
                    "submitted_word_count": compression.submitted_word_count,
                },
                "input_quality": input_quality,
            })
    finally:
        compressor.close()
        lifecycle.append({"event": "compressor_closed", "memory": _cuda_memory("compressor_closed")})

    condition_specs = list(profile.require("conditions"))
    condition_runs: dict[str, dict[str, Any]] = {}
    for condition_spec in condition_specs:
        condition = str(condition_spec["name"])
        condition_runs[condition] = _run_condition(
            condition_spec=condition_spec,
            prepared=prepared,
            config=config,
            lifecycle=lifecycle,
            dataset=str(profile.require("dataset")),
        )

    contract = profile.require("prompt_contract")
    parity_pairs = list(profile.require("parity_pairs"))
    prompt_records = []
    for item in prepared:
        prompt_id = item["prompt_id"]
        runs = {
            str(spec["name"]): condition_runs[str(spec["name"])]["rows"][prompt_id]
            for spec in condition_specs
        }
        output_quality = {
            condition: output_quality_record(
                run["result"]["text"],
                item["expected_fields"],
                strict_pattern=str(contract["strict_output_pattern"]),
                tolerant_pattern=str(contract["tolerant_field_pattern"]),
            ) if run["success"] else {
                "format_compliant": False,
                "parsed_fields": None,
                "expected_fields": item["expected_fields"],
                "field_matches": {field: False for field in item["expected_fields"]},
                "exact_field_match": False,
            }
            for condition, run in runs.items()
        }
        pairs = [
            pair_record(
                runs[str(pair["left"])], runs[str(pair["right"])], name=str(pair["name"])
            )
            for pair in parity_pairs
        ]
        prompt_records.append({
            **item, "runs": runs, "pair_token_parity": pairs,
            "output_quality": output_quality,
        })

    annotate_total_input_reduction(prompt_records, condition_specs)
    all_runs = [run for prompt in prompt_records for run in prompt["runs"].values()]
    all_pairs = [pair for prompt in prompt_records for pair in prompt["pair_token_parity"]]
    warmups = [condition_runs[str(spec["name"])]["warmup"] for spec in condition_specs]
    input_count = sum(prompt["input_quality"]["pass"] for prompt in prompt_records)
    pair_count = sum(pair["pass"] for pair in all_pairs)
    success_count = sum(run["success"] for run in all_runs)
    warmup_count = sum(run["success"] for run in warmups)
    exact_quality_count = sum(
        quality["exact_field_match"]
        for prompt in prompt_records for quality in prompt["output_quality"].values()
    )
    strict_format_count = sum(
        quality["format_compliant"]
        for prompt in prompt_records for quality in prompt["output_quality"].values()
    )
    validity = metric_validity(prompt_records, condition_specs)
    oom_count = sum(
        entry.get("event") == "request_error" and entry.get("oom") is True
        for entry in lifecycle
    )
    memory_limit_bytes = int(float(profile.require("hard_gates.dflash_peak_reserved_vram_gib")) * GIB)
    metrics_by_condition = {
        str(spec["name"]): condition_metrics(
            prompt_records, spec, peak_reserved_limit_bytes=memory_limit_bytes
        )
        for spec in condition_specs
    }
    dflash_conditions = tuple(
        str(spec["name"]) for spec in condition_specs
        if str(spec["runtime_condition"]) == "dflash"
    )
    memory_gate_pass = bool(dflash_conditions) and all(
        metrics_by_condition[name]["peak_reserved_vram_gate_pass"] is True
        for name in dflash_conditions
    )
    active_block = int(config.require("optimization.block_policy.fixed_block_size"))
    actual_block_gate = all(
        metrics_by_condition[name]["verification_block_sizes"] == [active_block]
        for name in dflash_conditions
    )
    gates = profile.require("hard_gates")
    hard_gates = {
        "condition_success": _rate_gate(
            success_count, len(all_runs), float(gates["condition_success_rate"])
        ),
        "pair_generated_token_parity": _rate_gate(
            pair_count, len(all_pairs), float(gates["pair_generated_token_parity_rate"])
        ),
        "exact_field_quality": _rate_gate(
            exact_quality_count, len(all_runs), float(gates["exact_field_quality_rate"])
        ),
        "protected_question_instruction_and_evidence": _rate_gate(
            input_count, len(prompt_records), float(gates["protected_input_rate"])
        ),
        "metric_validity": _rate_gate(
            int(validity["valid_rows"]), int(validity["checked_rows"]),
            float(gates["metric_validity_rate"]),
        ),
        "no_oom": oom_count <= int(gates["max_oom_events"]),
        "warmups": warmup_count == len(warmups),
        "configured_verification_block_observed": actual_block_gate,
        "compressor_cuda_resident": compressor_device_audit["all_tensors_cuda"],
        "dflash_peak_reserved_vram": memory_gate_pass,
    }
    workload_wall_clock_ms = (time.perf_counter() - workload_start) * 1000.0
    canonical_block = int(source_config.require("optimization.block_policy.fixed_block_size"))
    summary = {
        "active_profile": profile.name,
        "source_config_sha256": profile.source_config_sha256,
        "verification_block_size": active_block,
        "canonical_block_size": canonical_block,
        "canonical_config_mutated": False,
        "protocol_pass": all(hard_gates.values()),
        "quality_pass": hard_gates["exact_field_quality"],
        "metric_validity_pass": hard_gates["metric_validity"],
        "memory_gate_pass": memory_gate_pass,
        "overall_pass": all(hard_gates.values()),
        "hard_gates": hard_gates,
        "input_protocol_protected_and_evidence": f"{input_count}/{len(prompt_records)}",
        "pair_token_parity": f"{pair_count}/{len(all_pairs)}",
        "condition_success": f"{success_count}/{len(all_runs)}",
        "warmup_success": f"{warmup_count}/{len(warmups)}",
        "oom_event_count": oom_count,
        "output_format_compliance": f"{strict_format_count}/{len(all_runs)}",
        "strict_format_is_separate_from_exact_field_quality": True,
        "output_exact_field_quality": f"{exact_quality_count}/{len(all_runs)}",
        "metric_validity": validity,
        "conditions": metrics_by_condition,
        "global_dflash": weighted_dflash_metrics(prompt_records, dflash_conditions),
        "memory_gate": {
            "residency": residency,
            "compressor_and_generation_overlap": False,
            "compressor_budget_added_to_dflash_limit": False,
            "peak_reserved_limit_gib": float(gates["dflash_peak_reserved_vram_gib"]),
            "peak_reserved_limit_bytes": memory_limit_bytes,
            "conditions": {
                name: {
                    "peak_reserved_bytes": metrics_by_condition[name][
                        "max_full_request_peak_reserved_bytes"
                    ],
                    "pass": metrics_by_condition[name]["peak_reserved_vram_gate_pass"],
                }
                for name in dflash_conditions
            },
            "pass": memory_gate_pass,
        },
        "metric_scopes": {
            "per_condition_p50_and_mean": (
                "measured fixture requests for that condition; excludes warmup and model load/unload"
            ),
            "weighted_dflash": (
                "summed runtime counters over measured requests for that D-Flash condition; "
                "excludes warmup"
            ),
            "stage_sum_warm_e2e_ms": (
                "separately synchronized compression and production request stages; "
                "excludes warmup and model load/unload"
            ),
            "workload_wall_clock_ms": (
                "compressor lifecycle plus condition engine lifecycles, including warmups and "
                "all measured requests"
            ),
        },
        "workload": {
            "workload_wall_clock_ms": workload_wall_clock_ms,
            "lifecycle_amortized_ms_per_measured_request": workload_wall_clock_ms / len(all_runs),
            "measured_request_count": len(all_runs),
            "scope": (
                "compressor lifecycle plus all condition engine lifecycles, each with one warmup"
            ),
        },
    }
    config_snapshot = profile.snapshot()
    config_snapshot.update({
        "canonical_fixed_block_size": canonical_block,
        "active_profile_fixed_block_size": active_block,
        "canonical_config_mutated": False,
    })
    payload = {
        "validation_version": PROTOCOL_VERSION,
        "active_profile": profile.name,
        "source_config_sha256": profile.source_config_sha256,
        "resolved_config_snapshot": config_snapshot,
        "protocol": {
            "residency": residency,
            "conditions": condition_specs,
            "parity_pairs": parity_pairs,
            "context_only_compression": True,
            "question_and_instruction_byte_exact": True,
            "max_new_tokens": config.require("runtime.max_new_tokens"),
            "temperature": config.require("runtime.temperature"),
            "fixed_verification_block_size": active_block,
            "canonical_block_size": canonical_block,
            "cuda_synchronize_before_after_each_measured_request": True,
        },
        "metric_formulas": {
            "context_reduction_rate": (
                "1 - compressed_context_tokens / original_context_tokens; compressor tokenizer"
            ),
            "total_input_token_reduction": (
                "1 - compressed Qwen chat-template tokens / paired original tokens"
            ),
            "stage_sum_warm_e2e_ms": (
                "compression_latency_ms + synchronized production warm_request_ms"
            ),
            "decode_tok_s": "max(output_tokens - 1, 0) / (decode_total_ms / 1000)",
            "weighted_tau": "sum(acceptance_lengths) / sum(target_verification_calls)",
            "weighted_draft_acceptance_rate": (
                "sum(accepted_draft_tokens) / sum(draft_tokens_proposed)"
            ),
            "target_forwards_per_output_token": (
                "sum(target prefill + verification + single-token calls) / sum(output_tokens)"
            ),
        },
        "environment": environment,
        "compressor": {
            "model_contract": compressor_contract,
            "device_audit": compressor_device_audit,
        },
        "lifecycle": lifecycle,
        "prompts": prompt_records,
        "summary": summary,
    }
    _write_json(paths["raw"], payload)
    _write_json(paths["summary"], summary)
    sealed_summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    summary_sha = sha256_bytes(paths["summary"].read_bytes())
    paths["report"].write_text(
        render_final_report(sealed_summary, summary_sha), encoding="utf-8"
    )
    _write_json(paths["gates"], {
        "active_profile": profile.name,
        "source_config_sha256": profile.source_config_sha256,
        "overall_pass": sealed_summary["overall_pass"],
        "hard_gates": sealed_summary["hard_gates"],
        "memory_gate": sealed_summary["memory_gate"],
        "strict_format": {
            "hard_gate": False,
            "compliance": sealed_summary["output_format_compliance"],
            "separate_from_exact_field_quality": True,
        },
    })
    _write_json(paths["protected_hashes"], [
        {
            "prompt_id": prompt["prompt_id"],
            "question_sha256": prompt["input_quality"]["question_sha256"],
            "instruction_sha256": prompt["input_quality"]["instruction_sha256"],
            "protected_fields_byte_exact": prompt["input_quality"][
                "protected_fields_byte_exact"
            ],
            "pass": prompt["input_quality"]["pass"],
        }
        for prompt in prompt_records
    ])
    _write_json(paths["parity"], [
        {"prompt_id": prompt["prompt_id"], **pair}
        for prompt in prompt_records for pair in prompt["pair_token_parity"]
    ])
    _write_json(paths["config_snapshot"], config_snapshot)
    ending_config_sha = hashlib.sha256(source_config.path.read_bytes()).hexdigest()
    if ending_config_sha != profile.source_config_sha256:
        raise RuntimeError("config.yml changed while the protocol was running")
    return sealed_summary
