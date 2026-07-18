"""Cross-request metric aggregation and report rendering."""

from __future__ import annotations

import statistics
from typing import Any, Mapping

from .metrics import token_ids_sha256


def annotate_total_input_reduction(
    prompt_records: list[dict[str, Any]],
    condition_specs: list[Mapping[str, Any]],
) -> None:
    specs = {str(item["name"]): item for item in condition_specs}
    for prompt in prompt_records:
        runs = prompt["runs"]
        for condition, run in runs.items():
            if not run["success"]:
                continue
            metrics = run["result"]["protocol_metrics"]
            spec = specs[condition]
            if str(spec["prompt_kind"]) == "original":
                metrics["total_input_token_reduction"] = None
                continue
            reference_name = str(spec["reduction_reference_condition"])
            reference = runs[reference_name]
            if not reference["success"]:
                continue
            original_tokens = reference["result"]["protocol_metrics"]["chat_template_input"]["token_count"]
            compressed_tokens = metrics["chat_template_input"]["token_count"]
            metrics["total_input_token_reduction"] = (
                1 - (compressed_tokens / original_tokens) if original_tokens else 0.0
            )
            metrics["total_input_token_reduction_reference_condition"] = reference_name


def weighted_dflash_metrics(
    prompt_records: list[dict[str, Any]], conditions: tuple[str, ...]
) -> dict[str, Any] | None:
    counters = {
        "target_prefill_calls": 0,
        "target_verification_calls": 0,
        "target_single_token_calls": 0,
        "accepted_draft_tokens": 0,
        "draft_tokens_proposed": 0,
        "output_tokens": 0,
        "emitted_tokens": 0,
    }
    observed = 0
    for prompt in prompt_records:
        for condition in conditions:
            run = prompt["runs"][condition]
            if not run["success"] or run["result"]["dflash"] is None:
                continue
            observed += 1
            result = run["result"]
            dflash = result["dflash"]
            for key in (
                "target_prefill_calls", "target_verification_calls", "target_single_token_calls",
                "accepted_draft_tokens", "draft_tokens_proposed",
            ):
                counters[key] += int(dflash[key])
            counters["output_tokens"] += int(result["output_tokens"])
            counters["emitted_tokens"] += sum(int(value) for value in dflash["acceptance_lengths"])
    if not observed:
        return None
    target_forwards = (
        counters["target_prefill_calls"]
        + counters["target_verification_calls"]
        + counters["target_single_token_calls"]
    )
    return {
        "measured_rows": observed,
        "counters": counters,
        "weighted_tau": (
            counters["emitted_tokens"] / counters["target_verification_calls"]
            if counters["target_verification_calls"] else 0.0
        ),
        "weighted_draft_acceptance_rate": (
            counters["accepted_draft_tokens"] / counters["draft_tokens_proposed"]
            if counters["draft_tokens_proposed"] else 0.0
        ),
        "target_forwards_per_output_token": (
            target_forwards / counters["output_tokens"] if counters["output_tokens"] else 0.0
        ),
        "formula_scope": (
            f"counter totals across measured rows for {', '.join(conditions)}; excludes warmups"
        ),
    }


def condition_metrics(
    prompt_records: list[dict[str, Any]],
    condition_spec: Mapping[str, Any],
    *,
    peak_reserved_limit_bytes: int,
) -> dict[str, Any]:
    condition = str(condition_spec["name"])
    successful = [
        prompt["runs"][condition]["result"]
        for prompt in prompt_records if prompt["runs"][condition]["success"]
    ]

    def values(key: str) -> list[float]:
        return [
            float(result["protocol_metrics"][key])
            for result in successful if result["protocol_metrics"][key] is not None
        ]

    dflash_values = [result["dflash"] for result in successful if result["dflash"] is not None]
    reductions = [
        result["protocol_metrics"]["total_input_token_reduction"]
        for result in successful
        if result["protocol_metrics"]["total_input_token_reduction"] is not None
    ]
    block_sizes = sorted({
        int(block_size) for item in dflash_values for block_size in item["block_sizes"]
    })
    max_reserved = max(
        (result["protocol_metrics"]["full_request_peak_vram"]["peak_reserved_bytes"] for result in successful),
        default=None,
    )
    is_dflash = str(condition_spec["runtime_condition"]) == "dflash"
    return {
        "successful_requests": len(successful),
        "runtime_condition": str(condition_spec["runtime_condition"]),
        "prompt_kind": str(condition_spec["prompt_kind"]),
        "mean_chat_template_input_tokens": (
            statistics.mean(
                result["protocol_metrics"]["chat_template_input"]["token_count"]
                for result in successful
            ) if successful else None
        ),
        "mean_context_reduction_rate_compressor_tokenizer": (
            statistics.mean(values("context_reduction_rate"))
            if values("context_reduction_rate") else None
        ),
        "mean_total_input_token_reduction_qwen_tokenizer": (
            statistics.mean(reductions) if reductions else None
        ),
        **{
            f"{aggregate}_{metric}": (
                statistics.median(values(metric)) if aggregate == "p50"
                else statistics.mean(values(metric))
            ) if values(metric) else None
            for metric in (
                "compression_latency_ms", "prefill_latency_ms", "decode_latency_ms",
                "generation_latency_ms", "stage_sum_warm_e2e_ms", "decode_tok_s",
            )
            for aggregate in ("p50", "mean")
        },
        "mean_output_tokens": (
            statistics.mean(result["output_tokens"] for result in successful) if successful else None
        ),
        "cap_hit_count": sum(bool(result["protocol_metrics"]["cap_hit"]) for result in successful),
        "max_full_request_peak_reserved_bytes": max_reserved,
        "max_full_request_peak_allocated_bytes": max(
            (result["protocol_metrics"]["full_request_peak_vram"]["peak_allocated_bytes"] for result in successful),
            default=None,
        ),
        "peak_reserved_limit_bytes": peak_reserved_limit_bytes if is_dflash else None,
        "peak_reserved_vram_gate_pass": (
            max_reserved is not None and max_reserved <= peak_reserved_limit_bytes
        ) if is_dflash else None,
        "format_compliance": sum(
            prompt["output_quality"][condition]["format_compliant"] for prompt in prompt_records
        ),
        "exact_field_quality": sum(
            prompt["output_quality"][condition]["exact_field_match"] for prompt in prompt_records
        ),
        "mean_dflash_tau_unweighted": (
            statistics.mean(item["effective_tau"] for item in dflash_values)
            if dflash_values else None
        ),
        "mean_draft_acceptance_rate_unweighted": (
            statistics.mean(item["draft_acceptance_rate"] for item in dflash_values)
            if dflash_values else None
        ),
        "verification_block_sizes": block_sizes or None,
        "weighted_dflash": weighted_dflash_metrics(prompt_records, (condition,)),
    }


def metric_validity(
    prompt_records: list[dict[str, Any]], condition_specs: list[Mapping[str, Any]]
) -> dict[str, Any]:
    specs = {str(item["name"]): item for item in condition_specs}
    checks: list[bool] = []
    for prompt in prompt_records:
        for condition, run in prompt["runs"].items():
            if not run["success"]:
                checks.append(False)
                continue
            result = run["result"]
            metrics = result["protocol_metrics"]
            chat_input = metrics["chat_template_input"]
            is_original = str(specs[condition]["prompt_kind"]) == "original"
            context_formula = (
                metrics["context_reduction_rate"] is None
                and metrics["context_original_tokens"] is None
                and metrics["context_compressed_tokens"] is None
                if is_original
                else metrics["context_reduction_rate"]
                == 1 - (metrics["context_compressed_tokens"] / metrics["context_original_tokens"])
            )
            stage_formula = metrics["stage_sum_warm_e2e_ms"] == (
                metrics["compression_latency_ms"] + result["timing"]["warm_request_ms"]
            )
            token_count_match = (
                chat_input["token_count"] == result["prompt_tokens"] == len(chat_input["token_ids"])
            )
            tokenizer_hash_match = (
                chat_input["token_ids_sha256"] == token_ids_sha256(chat_input["token_ids"])
            )
            if is_original:
                reduction_valid = metrics["total_input_token_reduction"] is None
            else:
                reference_name = str(specs[condition]["reduction_reference_condition"])
                reference_count = prompt["runs"][reference_name]["result"]["protocol_metrics"][
                    "chat_template_input"
                ]["token_count"]
                reduction_valid = metrics["total_input_token_reduction"] == (
                    1 - (chat_input["token_count"] / reference_count)
                )
            checks.append(
                context_formula and stage_formula and token_count_match
                and tokenizer_hash_match and reduction_valid
            )
    return {"checked_rows": len(checks), "valid_rows": sum(checks), "pass": bool(checks) and all(checks)}


def format_metric(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return format(value, ".12g")
    return str(value)


def render_final_report(summary: dict[str, Any], summary_sha256: str) -> str:
    lines = [
        "# Four-condition mock10 final report",
        "",
        f"- Sealed summary SHA-256: `{summary_sha256}`",
        f"- Source `config.yml` SHA-256: `{summary['source_config_sha256']}`",
        f"- Active profile: **{summary['active_profile']}**",
        f"- Overall hard gates: **{'PASS' if summary['overall_pass'] else 'FAIL'}**",
        f"- Active fixed verification block size: **{summary['verification_block_size']}**",
        (
            f"- Canonical Baseline/DFlash block size: **{summary['canonical_block_size']}**; "
            "the active protocol profile does not mutate the canonical benchmark config."
        ),
        f"- Condition success: {summary['condition_success']}",
        f"- Pair generated-token parity: {summary['pair_token_parity']}",
        f"- Exact field quality: {summary['output_exact_field_quality']}",
        (
            "- Protected question/instruction and retained evidence: "
            f"{summary['input_protocol_protected_and_evidence']}"
        ),
        (
            f"- Metric validity: {'PASS' if summary['metric_validity_pass'] else 'FAIL'} "
            f"({summary['metric_validity']['valid_rows']}/{summary['metric_validity']['checked_rows']})"
        ),
        f"- OOM events: {summary['oom_event_count']}",
        f"- D-Flash peak-reserved VRAM gate: {'PASS' if summary['memory_gate_pass'] else 'FAIL'}",
        (
            "- Strict format compliance (reported separately, not an exact-quality hard gate): "
            f"{summary['output_format_compliance']}"
        ),
        "",
        "## Per-condition metrics",
        "",
        (
            "Every p50 and mean below is across measured requests for that condition; warmups "
            "and model load/unload are excluded. Weighted D-Flash values use summed counters "
            "over the same rows."
        ),
        "",
        "| condition | input tokens mean | context reduction mean | target-token reduction mean | compression ms p50 / mean | prefill ms p50 / mean | decode ms p50 / mean | generation ms p50 / mean | stage-sum E2E ms p50 / mean | decode tok/s p50 / mean | peak allocated / reserved bytes | reserved gate | block | weighted tau | weighted acceptance | target forwards/output token |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for condition, metrics in summary["conditions"].items():
        weighted = metrics["weighted_dflash"] or {}
        block_sizes = metrics["verification_block_sizes"]
        block = ",".join(str(value) for value in block_sizes) if block_sizes else "n/a"
        memory_gate = metrics["peak_reserved_vram_gate_pass"]
        lines.append("| " + " | ".join([
            condition,
            format_metric(metrics["mean_chat_template_input_tokens"]),
            format_metric(metrics["mean_context_reduction_rate_compressor_tokenizer"]),
            format_metric(metrics["mean_total_input_token_reduction_qwen_tokenizer"]),
            f"{format_metric(metrics['p50_compression_latency_ms'])} / {format_metric(metrics['mean_compression_latency_ms'])}",
            f"{format_metric(metrics['p50_prefill_latency_ms'])} / {format_metric(metrics['mean_prefill_latency_ms'])}",
            f"{format_metric(metrics['p50_decode_latency_ms'])} / {format_metric(metrics['mean_decode_latency_ms'])}",
            f"{format_metric(metrics['p50_generation_latency_ms'])} / {format_metric(metrics['mean_generation_latency_ms'])}",
            f"{format_metric(metrics['p50_stage_sum_warm_e2e_ms'])} / {format_metric(metrics['mean_stage_sum_warm_e2e_ms'])}",
            f"{format_metric(metrics['p50_decode_tok_s'])} / {format_metric(metrics['mean_decode_tok_s'])}",
            f"{format_metric(metrics['max_full_request_peak_allocated_bytes'])} / {format_metric(metrics['max_full_request_peak_reserved_bytes'])}",
            "n/a" if memory_gate is None else ("PASS" if memory_gate else "FAIL"),
            block,
            format_metric(weighted.get("weighted_tau")),
            format_metric(weighted.get("weighted_draft_acceptance_rate")),
            format_metric(weighted.get("target_forwards_per_output_token")),
        ]) + " |")
    workload = summary["workload"]
    lines.extend([
        "",
        "## Metric scopes",
        "",
        "- Compression latency: synchronized LLMLingua context-compression stage; zero for original-context conditions.",
        "- Prefill/decode/generation latency and decode tok/s: synchronized production generation request.",
        "- Stage-sum E2E: compression plus runtime warm-request latency with separate GPU residency; excludes warmup and model load/unload.",
        (
            f"- Validation workload wall clock: {format_metric(workload['workload_wall_clock_ms'])} ms "
            f"for compressor and engine lifecycles, including warmups and "
            f"{workload['measured_request_count']} measured requests."
        ),
        (
            "- Workload lifecycle-amortized latency: "
            f"{format_metric(workload['lifecycle_amortized_ms_per_measured_request'])} ms per "
            "measured request; not a per-condition request latency."
        ),
        "- Context reduction uses the LLMLingua tokenizer; target-token reduction uses paired Qwen chat-template input counts and is null for original conditions.",
        "",
    ])
    return "\n".join(lines)
