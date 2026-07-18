"""Validation-only CUDA audit for the local LLMLingua-2 compressor."""

from __future__ import annotations

import hashlib
import json
import platform
import statistics
from pathlib import Path

import llmlingua
import torch
import transformers

from ccdf.compression import CompressionConfig, ContextOnlyProtocol, LLMLinguaCompressor
from ccdf.config import load_config


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/artifacts/compression/compressor_validation.json"
WARMUPS = 1
REPETITIONS = 5

CASES = [
    (12, 0.00, "Alice Nguyen", "AX-104", "7319"),
    (24, 0.10, "Bao Tran", "BT-218", "8427"),
    (36, 0.25, "Carla Diaz", "CD-336", "9531"),
    (54, 0.40, "Dev Patel", "DP-454", "1643"),
    (72, 0.50, "Elena Rossi", "ER-572", "2759"),
    (90, 0.60, "Farah Khan", "FK-690", "3861"),
    (108, 0.75, "George Li", "GL-708", "4973"),
    (126, 0.90, "Hana Ito", "HI-826", "5087"),
    (144, 1.00, "Ivan Petrov", "IP-944", "6199"),
    (180, 0.33, "Julia Santos", "JS-180", "7201"),
]


def _sha256_bytes(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _protocol(
    index: int, turns: int, evidence_position: float,
    owner: str, approval_code: str, approved_quantity: str,
) -> ContextOnlyProtocol:
    filler = [
        f"Meeting turn {turn}: distractor candidate Candidate-{turn % 7} proposed draft code "
        f"ZZ-{index}{turn:03d} and preliminary quantity {1000 + index * 100 + turn}; none was approved."
        for turn in range(1, turns + 1)
    ]
    evidence = (
        f"FINAL APPROVED FACT: the approved owner is {owner}; "
        f"the approval code is {approval_code}; the exact approved quantity is {approved_quantity}."
    )
    insertion = round(len(filler) * evidence_position)
    context = " ".join(filler[:insertion] + [evidence] + filler[insertion:])
    return ContextOnlyProtocol(
        context=context,
        question="According to the FINAL APPROVED FACT, who is the owner, what is the approval code, and what exact quantity was approved?",
        output_instruction="Return exactly: Owner: <name>; Approval code: <code>; Quantity: <integer>",
    )


def _protected_fields(rendered: str) -> tuple[str, str]:
    _, suffix = rendered.split("\n\nQuestion:\n", 1)
    question, instruction = suffix.split("\n\n", 1)
    return question, instruction


def main() -> None:
    config = load_config(ROOT / "config.yml")
    reserved_budget_gib = float(config.require("models.compressor.reserved_budget_gib"))
    compressor = LLMLinguaCompressor(
        config.path_for("models.compressor.local_path"),
        device=str(config.require("models.compressor.device")),
        local_files_only=bool(config.require("runtime.local_files_only")),
        reserved_vram_budget_gib=reserved_budget_gib,
    )
    records = []
    compression_config = CompressionConfig(keep_rate=0.5, chunk_max_words=180)

    for index, (turns, evidence_position, owner, approval_code, approved_quantity) in enumerate(CASES, start=1):
        protocol = _protocol(index, turns, evidence_position, owner, approval_code, approved_quantity)
        evidence_occurs_once = all(
            protocol.context.count(fragment) == 1
            for fragment in (owner, approval_code, approved_quantity)
        )
        for _ in range(WARMUPS):
            torch.cuda.synchronize()
            compressor.compress(protocol, compression_config)
            torch.cuda.synchronize()

        repetitions = []
        for repetition in range(1, REPETITIONS + 1):
            backend_calls_before = compressor.backend_compress_prompt_calls
            torch.cuda.synchronize()
            result = compressor.compress(protocol, compression_config)
            torch.cuda.synchronize()
            backend_calls = compressor.backend_compress_prompt_calls - backend_calls_before
            rendered = protocol.render(result.compressed_context)
            question_after, instruction_after = _protected_fields(rendered)
            evidence_fragments = [owner, approval_code, approved_quantity]
            evidence_present = all(fragment in result.compressed_context for fragment in evidence_fragments)
            protected_byte_exact = (
                protocol.question.encode("utf-8") == question_after.encode("utf-8")
                and protocol.output_instruction.encode("utf-8") == instruction_after.encode("utf-8")
            )
            repetitions.append(
                {
                    "repetition": repetition,
                    "original_tokens": result.original_tokens,
                    "compressed_tokens": result.compressed_tokens,
                    "reduction_rate": result.reduction_rate,
                    "latency_ms": result.compression_latency_ms,
                    "peak_allocated_vram_bytes": result.peak_allocated_vram_bytes,
                    "peak_reserved_vram_bytes": result.peak_reserved_vram_bytes,
                    "reserved_vram_budget_bytes": result.reserved_vram_budget_bytes,
                    "reserved_vram_budget_pass": result.reserved_vram_budget_pass,
                    "question_sha256_before": _sha256_bytes(protocol.question),
                    "question_sha256_after": _sha256_bytes(question_after),
                    "instruction_sha256_before": _sha256_bytes(protocol.output_instruction),
                    "instruction_sha256_after": _sha256_bytes(instruction_after),
                    "protected_fields_byte_exact": protected_byte_exact,
                    "required_evidence": evidence_fragments,
                    "required_evidence_occurs_once_in_input": evidence_occurs_once,
                    "required_evidence_present": evidence_present,
                    "backend_compress_prompt_calls": backend_calls,
                    "chunk_count": result.chunk_count,
                    "all_context_words_submitted": result.input_word_count == result.submitted_word_count,
                    "compressed_context_sha256": _sha256_bytes(result.compressed_context),
                    "pass": (
                        protected_byte_exact and evidence_present and evidence_occurs_once
                        and backend_calls == result.chunk_count > 0
                        and result.input_word_count == result.submitted_word_count
                        and result.reserved_vram_budget_pass
                        and result.compressed_tokens < result.original_tokens
                    ),
                }
            )
        latencies = [row["latency_ms"] for row in repetitions]
        records.append(
            {
                "prompt_index": index,
                "context_turns": turns,
                "evidence_position_fraction": evidence_position,
                "warmups": WARMUPS,
                "repetitions": REPETITIONS,
                "original_tokens": repetitions[0]["original_tokens"],
                "compressed_tokens": repetitions[0]["compressed_tokens"],
                "reduction_rate": repetitions[0]["reduction_rate"],
                "latency_ms": {
                    "p50": statistics.median(latencies),
                    "mean": statistics.mean(latencies),
                    "min": min(latencies),
                    "max": max(latencies),
                },
                "peak_allocated_vram_bytes": max(row["peak_allocated_vram_bytes"] for row in repetitions),
                "peak_reserved_vram_bytes": max(row["peak_reserved_vram_bytes"] for row in repetitions),
                "repetition_results": repetitions,
                "pass": all(row["pass"] for row in repetitions),
            }
        )

    payload = {
        "validation_version": "ccdf.compressor-validation.v3",
        "pass": compressor.device_audit["all_tensors_cuda"] and all(row["pass"] for row in records),
        "model_path": str(compressor.model_path),
        "model_config_sha256": hashlib.sha256((compressor.model_path / "config.json").read_bytes()).hexdigest(),
        "model_contract": compressor.model_contract,
        "device_audit": compressor.device_audit,
        "environment": {
            "python_version": platform.python_version(),
            "torch_version": torch.__version__,
            "torch_cuda_version": torch.version.cuda,
            "cuda_available": torch.cuda.is_available(),
            "gpu_name": torch.cuda.get_device_name(0),
            "gpu_compute_capability": list(torch.cuda.get_device_capability(0)),
            "transformers_version": transformers.__version__,
            "llmlingua_version": llmlingua.__version__,
        },
        "reserved_vram_budget": {
            "gib": reserved_budget_gib,
            "bytes": compressor.reserved_vram_budget_bytes,
            "peak_reserved_bytes": max(row["peak_reserved_vram_bytes"] for row in records),
            "pass": all(
                repetition["reserved_vram_budget_pass"]
                for row in records for repetition in row["repetition_results"]
            ),
        },
        "initialization_ms": compressor.initialization_ms,
        "backend_compress_prompt_calls_total": compressor.backend_compress_prompt_calls,
        "measurement": {"warmups_per_prompt": WARMUPS, "repetitions_per_prompt": REPETITIONS, "cuda_synchronize": True},
        "mock_prompt_pass_count": sum(row["pass"] for row in records),
        "mock_prompt_count": len(records),
        "records": records,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("pass", "model_contract", "device_audit", "measurement", "mock_prompt_pass_count", "mock_prompt_count")}, sort_keys=True))
    if not payload["pass"]:
        raise SystemExit("compressor validation failed")


if __name__ == "__main__":
    main()
